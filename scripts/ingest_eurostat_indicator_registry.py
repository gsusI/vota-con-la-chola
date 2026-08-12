#!/usr/bin/env python3
"""Durable, bounded acquisition of official Eurostat indicator cubes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.politicos_es.db import (
    apply_schema,
    finish_run,
    seed_dimensions,
    seed_sources,
    start_run,
)
from publicdata_core.blobstore import download_to_content_addressed_store
from publicdata_core.util import now_utc_iso, sha256_bytes
from publicdata_ops import (
    claim_work_items,
    complete_work_items,
    enqueue_work_items,
    fail_work_items,
    heartbeat_work_items,
    work_queue_observability,
)
from publicdata_policy_es.eurostat_bulk import (
    SOURCE_ID,
    inspect_eurostat_jsonstat,
    load_eurostat_source_records,
)
from publicdata_sqlite import open_db

DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_REGISTRY = Path("etl/data/seeds/eurostat_indicator_registry_v1.json")
DEFAULT_MAXIMUM_CUBE_CELLS = 10_000_000


def _maximum_cube_cells(query: dict[str, Any]) -> int:
    """Keep legacy queued payloads bounded after the registry contract evolved."""

    raw_value = query.get("maximum_cube_cells")
    maximum = DEFAULT_MAXIMUM_CUBE_CELLS if raw_value in (None, "") else int(raw_value)
    if maximum < 1:
        raise RuntimeError("Eurostat maximum_cube_cells must be >= 1")
    return maximum


def load_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "eurostat_indicator_registry_v1":
        raise RuntimeError("Unsupported Eurostat registry schema_version")
    if payload.get("source_id") != SOURCE_ID:
        raise RuntimeError(f"Eurostat registry source_id must be {SOURCE_ID}")
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise RuntimeError("Eurostat registry requires a non-empty queries array")
    query_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in queries:
        if not isinstance(raw, dict):
            raise TypeError("Eurostat registry query must be an object")
        query_id = str(raw.get("query_id") or "").strip()
        dataset_code = str(raw.get("dataset_code") or "").strip().lower()
        source_url = str(raw.get("source_url") or "").strip()
        parsed = urlsplit(source_url)
        if not query_id or query_id in query_ids:
            raise RuntimeError(
                f"Eurostat registry query_id is empty or duplicated: {query_id}"
            )
        if parsed.scheme != "https" or parsed.netloc.lower() != "ec.europa.eu":
            raise RuntimeError(
                f"Eurostat registry URL must use official HTTPS origin: {source_url}"
            )
        if f"/data/{dataset_code}" not in parsed.path.lower():
            raise RuntimeError(
                f"Eurostat dataset_code does not match source_url: {dataset_code}"
            )
        minimum_observations = int(raw.get("minimum_observations") or 0)
        maximum_bytes = int(raw.get("maximum_bytes") or 0)
        maximum_cube_cells = int(raw.get("maximum_cube_cells") or 0)
        if (
            minimum_observations < 1
            or maximum_bytes < 1
            or maximum_cube_cells < minimum_observations
        ):
            raise RuntimeError(f"Eurostat registry bounds are invalid: {query_id}")
        query_ids.add(query_id)
        normalized.append(
            {
                "query_id": query_id,
                "dataset_code": dataset_code,
                "domain_key": str(raw.get("domain_key") or "").strip() or None,
                "source_url": source_url,
                "minimum_observations": minimum_observations,
                "maximum_bytes": maximum_bytes,
                "maximum_cube_cells": maximum_cube_cells,
                "priority": int(raw.get("priority") or 0),
                "max_attempts": max(1, int(raw.get("max_attempts") or 5)),
            }
        )
    return {**payload, "queries": normalized}


def initialize(conn: sqlite3.Connection) -> None:
    apply_schema(conn, DEFAULT_SCHEMA)
    seed_sources(conn)
    seed_dimensions(conn)


def enqueue_registry(
    conn: sqlite3.Connection,
    *,
    registry: dict[str, Any],
    pipeline_id: str,
    snapshot_date: str,
) -> dict[str, Any]:
    items = []
    for query in registry["queries"]:
        url_hash = sha256_bytes(str(query["source_url"]).encode("utf-8"))[:16]
        items.append(
            {
                "item_key": f"{query['query_id']}:{url_hash}",
                "partition_key": str(query["dataset_code"]),
                "priority": int(query["priority"]),
                "max_attempts": int(query["max_attempts"]),
                "payload": {
                    **query,
                    "snapshot_date": snapshot_date,
                },
            }
        )
    result = enqueue_work_items(
        conn,
        pipeline_id=pipeline_id,
        items=items,
        batch_size=1_000,
    )
    return {
        "schema_version": "eurostat_indicator_enqueue_v1",
        "pipeline_id": pipeline_id,
        "snapshot_date": snapshot_date,
        "registry_queries": len(items),
        "enqueue": result,
        "queue": work_queue_observability(conn, pipeline_id=pipeline_id),
    }


def _begin_acquisition(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    item_key: str,
    query: dict[str, Any],
    transport_security: str,
    raw_content_sha256: str,
    raw_path: Path,
    raw_bytes: int,
) -> int:
    now_iso = now_utc_iso()
    row = conn.execute(
        """
        INSERT INTO indicator_bulk_acquisitions (
          pipeline_id, item_key, source_id, dataset_code, source_url,
          source_snapshot_date, transport_security, raw_content_sha256,
          raw_path, raw_bytes, series_loaded, observations_discovered,
          status, error, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'running', NULL, ?, ?)
        ON CONFLICT(pipeline_id, item_key) DO UPDATE SET
          dataset_code=excluded.dataset_code,
          source_url=excluded.source_url,
          source_snapshot_date=excluded.source_snapshot_date,
          transport_security=excluded.transport_security,
          raw_content_sha256=excluded.raw_content_sha256,
          raw_path=excluded.raw_path,
          raw_bytes=excluded.raw_bytes,
          series_loaded=0,
          observations_discovered=0,
          status='running',
          error=NULL,
          updated_at=excluded.updated_at
        RETURNING indicator_bulk_acquisition_id
        """,
        (
            pipeline_id,
            item_key,
            SOURCE_ID,
            str(query["dataset_code"]),
            str(query["source_url"]),
            str(query["snapshot_date"]),
            transport_security,
            raw_content_sha256,
            str(raw_path),
            int(raw_bytes),
            now_iso,
            now_iso,
        ),
    ).fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("Could not resolve indicator_bulk_acquisition_id")
    return int(row["indicator_bulk_acquisition_id"])


def _record_fetch(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    query: dict[str, Any],
    raw_path: Path,
    content_sha256: str,
    content_type: str | None,
    raw_bytes: int,
) -> None:
    fetched_at = now_utc_iso()
    values = (
        run_id,
        SOURCE_ID,
        str(query["source_url"]),
        fetched_at,
        str(raw_path),
        content_sha256,
        content_type,
        int(raw_bytes),
    )
    conn.execute(
        """
        INSERT INTO run_fetches (
          run_id, source_id, source_url, fetched_at, raw_path,
          content_sha256, content_type, bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          source_id=excluded.source_id,
          source_url=excluded.source_url,
          fetched_at=excluded.fetched_at,
          raw_path=excluded.raw_path,
          content_sha256=excluded.content_sha256,
          content_type=excluded.content_type,
          bytes=excluded.bytes
        """,
        values,
    )
    conn.execute(
        """
        INSERT INTO raw_fetches (
          run_id, source_id, source_url, fetched_at, raw_path,
          content_sha256, content_type, bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, content_sha256) DO NOTHING
        """,
        values,
    )
    conn.commit()


def run_worker(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    store_root: Path,
    timeout: int,
    ca_bundle: Path | None,
    insecure_ssl: bool,
    max_items: int,
    source_record_batch_size: int,
) -> dict[str, Any]:
    attempted = 0
    succeeded = 0
    failed = 0
    lease_seconds = max(300, int(timeout) * 4)
    while attempted < int(max_items):
        claimed = claim_work_items(
            conn,
            pipeline_id=pipeline_id,
            worker_id=worker_id,
            limit=1,
            lease_seconds=lease_seconds,
        )
        if not claimed:
            break
        item = claimed[0]
        attempted += 1
        item_id = int(item["work_item_id"])
        item_key = str(item["item_key"])
        query = dict(item["payload"])
        run_id = start_run(conn, SOURCE_ID, str(query["source_url"]))
        acquisition_id: int | None = None
        heartbeat_interval_seconds = max(1.0, min(60.0, lease_seconds / 3.0))
        last_heartbeat = monotonic()

        def heartbeat(
            *,
            force: bool = False,
            claimed_item_id: int = item_id,
            interval_seconds: float = heartbeat_interval_seconds,
        ) -> None:
            nonlocal last_heartbeat
            current = monotonic()
            if not force and current - last_heartbeat < interval_seconds:
                return
            updated = heartbeat_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[claimed_item_id],
                lease_seconds=lease_seconds,
            )
            if updated != 1:
                raise RuntimeError(
                    f"Eurostat worker lost lease for work_item_id={claimed_item_id}"
                )
            last_heartbeat = current

        try:
            stored = download_to_content_addressed_store(
                str(query["source_url"]),
                store_root=store_root,
                timeout=int(timeout),
                max_bytes=int(query["maximum_bytes"]),
                chunk_bytes=1024 * 1024,
                max_attempts=3,
                ca_bundle=ca_bundle,
                insecure_ssl=insecure_ssl,
                progress_callback=heartbeat,
            )
            heartbeat(force=True)
            transport_security = "unverified_tls" if insecure_ssl else "verified_ca"
            maximum_cube_cells = _maximum_cube_cells(query)
            preflight = inspect_eurostat_jsonstat(
                stored.path,
                source_url=str(query["source_url"]),
                expected_dataset_code=str(query["dataset_code"]),
                maximum_cube_cells=maximum_cube_cells,
            )
            heartbeat(force=True)
            if int(preflight["observations"]) < int(query["minimum_observations"]):
                raise RuntimeError(
                    "Eurostat observation floor failed: "
                    f"dataset={query['dataset_code']} observed={preflight['observations']} "
                    f"minimum={query['minimum_observations']}"
                )
            _record_fetch(
                conn,
                run_id=run_id,
                query=query,
                raw_path=stored.path,
                content_sha256=stored.content_sha256,
                content_type=stored.content_type,
                raw_bytes=stored.bytes,
            )
            acquisition_id = _begin_acquisition(
                conn,
                pipeline_id=pipeline_id,
                item_key=item_key,
                query=query,
                transport_security=transport_security,
                raw_content_sha256=stored.content_sha256,
                raw_path=stored.path,
                raw_bytes=stored.bytes,
            )
            loaded = load_eurostat_source_records(
                conn,
                blob_path=stored.path,
                source_url=str(query["source_url"]),
                snapshot_date=str(query["snapshot_date"]),
                raw_content_sha256=stored.content_sha256,
                acquisition_id=acquisition_id,
                domain_key=query.get("domain_key"),
                maximum_cube_cells=maximum_cube_cells,
                batch_size=int(source_record_batch_size),
                progress_callback=heartbeat,
            )
            if int(loaded["observations_discovered"]) != int(preflight["observations"]):
                raise RuntimeError(
                    "Eurostat load/preflight observation mismatch: "
                    f"loaded={loaded['observations_discovered']} preflight={preflight['observations']}"
                )
            conn.execute(
                """
                UPDATE indicator_bulk_acquisitions
                SET series_loaded=?, observations_discovered=?, status='ok',
                    error=NULL, updated_at=?
                WHERE indicator_bulk_acquisition_id=?
                """,
                (
                    int(loaded["series_loaded"]),
                    int(loaded["observations_discovered"]),
                    now_utc_iso(),
                    acquisition_id,
                ),
            )
            conn.commit()
            finish_run(
                conn,
                run_id,
                "ok",
                f"bulk dataset={query['dataset_code']} observations={loaded['observations_discovered']}",
                int(loaded["series_loaded"]),
                int(loaded["series_loaded"]),
                raw_path=stored.path,
            )
            heartbeat(force=True)
            completed = complete_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[item_id],
            )
            if completed != 1:
                raise RuntimeError(
                    f"Eurostat worker could not complete work_item_id={item_id}"
                )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            clean_error = f"{type(exc).__name__}: {exc}"[:2_000]
            if acquisition_id is not None:
                conn.execute(
                    """
                    UPDATE indicator_bulk_acquisitions
                    SET status='error', error=?, updated_at=?
                    WHERE indicator_bulk_acquisition_id=?
                    """,
                    (clean_error, now_utc_iso(), acquisition_id),
                )
                conn.commit()
            finish_run(conn, run_id, "error", clean_error, 0, 0)
            fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[item_id],
                error=clean_error,
                retry_delay_seconds=5,
                retryable=True,
            )
            failed += 1
    return {
        "schema_version": "eurostat_indicator_worker_v1",
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "queue": work_queue_observability(conn, pipeline_id=pipeline_id),
    }


def build_report(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    db_path: Path,
) -> dict[str, Any]:
    queue = work_queue_observability(conn, pipeline_id=pipeline_id)
    acquisitions = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              indicator_bulk_acquisition_id, item_key, dataset_code,
              source_url, source_snapshot_date, transport_security,
              raw_content_sha256, raw_bytes, series_loaded,
              observations_discovered, status, error
            FROM indicator_bulk_acquisitions
            WHERE pipeline_id=?
            ORDER BY dataset_code, item_key
            """,
            (pipeline_id,),
        )
    ]
    acquisition_totals = conn.execute(
        """
        SELECT
          COUNT(*) AS acquisitions,
          COALESCE(SUM(series_loaded), 0) AS series_loaded,
          COALESCE(SUM(observations_discovered), 0) AS observations_discovered,
          COALESCE(SUM(raw_bytes), 0) AS raw_bytes,
          COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END), 0) AS ok_total,
          COALESCE(SUM(CASE WHEN transport_security='verified_ca' THEN 1 ELSE 0 END), 0)
            AS verified_ca_total
        FROM indicator_bulk_acquisitions
        WHERE pipeline_id=?
        """,
        (pipeline_id,),
    ).fetchone()
    mapping = conn.execute(
        """
        SELECT
          COUNT(*) AS source_records,
          COALESCE(SUM(r.observations_discovered), 0) AS observations_discovered
        FROM indicator_bulk_acquisition_records AS r
        JOIN indicator_bulk_acquisitions AS a
          ON a.indicator_bulk_acquisition_id=r.indicator_bulk_acquisition_id
        WHERE a.pipeline_id=?
        """,
        (pipeline_id,),
    ).fetchone()
    normalized = conn.execute(
        """
        SELECT
          COUNT(DISTINCT o.observation_record_id) AS observation_records,
          COUNT(DISTINCT o.indicator_series_id) AS indicator_series,
          COUNT(DISTINCT o.source_record_pk) AS source_records,
          COUNT(DISTINCT CASE WHEN o.source_url LIKE 'https://ec.europa.eu/%'
                              THEN o.observation_record_id END) AS official_url_rows,
          COUNT(DISTINCT CASE WHEN o.methodology_version IS NOT NULL
                               AND trim(o.methodology_version) <> ''
                              THEN o.observation_record_id END) AS methodology_rows
        FROM indicator_observation_records AS o
        WHERE o.source_id=?
        """,
        (SOURCE_ID,),
    ).fetchone()
    observation_storage = conn.execute(
        """
        SELECT
          COALESCE(SUM(length(raw_payload)), 0) AS raw_payload_bytes,
          COALESCE(SUM(CASE WHEN dimensions_json IS NOT NULL THEN 1 ELSE 0 END), 0)
            AS inline_dimensions_rows
        FROM indicator_observation_records
        WHERE source_id=?
        """,
        (SOURCE_ID,),
    ).fetchone()
    series_storage = conn.execute(
        """
        SELECT
          COALESCE(SUM(length(raw_payload)), 0) AS raw_payload_bytes,
          COALESCE(SUM(CASE WHEN dimensions_json IS NOT NULL THEN 1 ELSE 0 END), 0)
            AS dimensions_rows
        FROM indicator_series
        WHERE source_id=?
        """,
        (SOURCE_ID,),
    ).fetchone()
    keyset_query_plan = [
        str(row[3])
        for row in conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT source_record_pk, source_id, source_record_id,
                   source_snapshot_date, raw_payload
            FROM source_records
            WHERE source_id IN ('eurostat_sdmx')
              AND (
                source_id,
                COALESCE(source_snapshot_date, ''),
                source_record_id,
                source_record_pk
              ) > ('', '', '', 0)
            ORDER BY source_id, COALESCE(source_snapshot_date, ''),
                     source_record_id, source_record_pk
            LIMIT 1000
            """
        ).fetchall()
    ]
    quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    foreign_key_errors = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    state_counts = dict(queue["state_counts"])
    acquisitions_total = int(acquisition_totals["acquisitions"])
    discovered = int(acquisition_totals["observations_discovered"])
    observation_records = int(normalized["observation_records"])
    checks = {
        "queue_finished": int(queue["unfinished_total"]) == 0,
        "no_dead_items": int(state_counts.get("dead", 0)) == 0,
        "all_items_succeeded": int(state_counts.get("succeeded", 0))
        == int(queue["items_total"]),
        "all_acquisitions_recorded": acquisitions_total
        == int(state_counts.get("succeeded", 0)),
        "all_acquisitions_ok": int(acquisition_totals["ok_total"])
        == acquisitions_total,
        "verified_tls_for_all_acquisitions": int(
            acquisition_totals["verified_ca_total"]
        )
        == acquisitions_total,
        "source_record_mapping_reconciles": int(mapping["source_records"])
        == int(acquisition_totals["series_loaded"]),
        "discovered_observations_reconcile": int(mapping["observations_discovered"])
        == discovered,
        "normalized_observations_reconcile": observation_records == discovered,
        "official_source_urls_complete": int(normalized["official_url_rows"])
        == observation_records,
        "methodology_complete": int(normalized["methodology_rows"])
        == observation_records,
        "series_dimensions_normalized": int(series_storage["dimensions_rows"])
        == int(normalized["indicator_series"]),
        "observation_dimensions_not_duplicated": int(
            observation_storage["inline_dimensions_rows"]
        )
        == 0,
        "keyset_index_used": any(
            "idx_source_records_indicator_backfill" in step
            for step in keyset_query_plan
        ),
        "million_real_observations": observation_records >= 1_000_000,
        "quick_check": quick_check == "ok",
        "foreign_keys": foreign_key_errors == 0,
    }
    return {
        "schema_version": "eurostat_indicator_registry_report_v1",
        "generated_at": now_utc_iso(),
        "pipeline_id": pipeline_id,
        "source_id": SOURCE_ID,
        "database_file": Path(db_path).name,
        "database_bytes": Path(db_path).stat().st_size,
        "queue": queue,
        "acquisition_totals": {
            key: int(acquisition_totals[key])
            for key in (
                "acquisitions",
                "series_loaded",
                "observations_discovered",
                "raw_bytes",
                "ok_total",
                "verified_ca_total",
            )
        },
        "mapping": {
            "source_records": int(mapping["source_records"]),
            "observations_discovered": int(mapping["observations_discovered"]),
        },
        "normalized": {
            key: int(normalized[key])
            for key in (
                "observation_records",
                "indicator_series",
                "source_records",
                "official_url_rows",
                "methodology_rows",
            )
        },
        "storage": {
            "observation_raw_payload_bytes": int(
                observation_storage["raw_payload_bytes"]
            ),
            "observation_inline_dimensions_rows": int(
                observation_storage["inline_dimensions_rows"]
            ),
            "series_raw_payload_bytes": int(series_storage["raw_payload_bytes"]),
            "series_dimensions_rows": int(series_storage["dimensions_rows"]),
            "keyset_query_plan": keyset_query_plan,
        },
        "quick_check": quick_check,
        "foreign_key_errors": foreign_key_errors,
        "checks": checks,
        "analytical_ingest_gate_passed": all(checks.values()),
        "real_coverage_claim": True,
        "representative_mix_claim": False,
        "promotion_gate_passed": False,
        "publication_status": "local_real_official_not_published",
        "acquisitions": acquisitions,
        "limitations": [
            "Four official Eurostat regional datasets do not establish representative coverage of every policy outcome domain.",
            "Verified local acquisition and normalization do not prove durable public publication or clean-room restore.",
            "Population, GDP, density, and poverty context support accountability analysis but do not prove causal impact.",
        ],
    }


def write_report(payload: dict[str, Any], out: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("enqueue", "worker", "report"))
    parser.add_argument("--db", required=True)
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--snapshot-date", default="")
    parser.add_argument("--worker-id", default="eurostat-worker-1")
    parser.add_argument(
        "--store-root", default="etl/data/object-origin/eurostat-indicators"
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--ca-bundle", default="")
    parser.add_argument("--insecure-ssl", action="store_true")
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--source-record-batch-size", type=int, default=1_000)
    parser.add_argument("--out", default="")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    conn = open_db(db_path)
    try:
        initialize(conn)
        if args.command == "enqueue":
            if not args.snapshot_date:
                raise RuntimeError("--snapshot-date is required for enqueue")
            dt.date.fromisoformat(args.snapshot_date)
            payload = enqueue_registry(
                conn,
                registry=load_registry(Path(args.registry)),
                pipeline_id=args.pipeline_id,
                snapshot_date=args.snapshot_date,
            )
        elif args.command == "worker":
            payload = run_worker(
                conn,
                pipeline_id=args.pipeline_id,
                worker_id=args.worker_id,
                store_root=Path(args.store_root),
                timeout=int(args.timeout),
                ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
                insecure_ssl=bool(args.insecure_ssl),
                max_items=int(args.max_items),
                source_record_batch_size=int(args.source_record_batch_size),
            )
        else:
            payload = build_report(
                conn,
                pipeline_id=args.pipeline_id,
                db_path=db_path,
            )
            if args.enforce and not payload["analytical_ingest_gate_passed"]:
                failed = [key for key, value in payload["checks"].items() if not value]
                raise RuntimeError(
                    "Eurostat indicator gate failed: " + ", ".join(failed)
                )
    finally:
        conn.close()
    write_report(payload, Path(args.out) if args.out else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
