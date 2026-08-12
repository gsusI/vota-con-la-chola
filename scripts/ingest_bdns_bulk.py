#!/usr/bin/env python3
"""Durable, bounded-memory ingestion for the national BDNS concessions corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sqlite3
import sys
import threading
import time
import urllib.error
from collections import deque
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.db import (
    apply_schema,
    finish_run,
    seed_sources,
    start_run,
)
from publicdata_connectors_es.money.bdns_bulk import (
    BdnsPage,
    build_bdns_concessions_url,
    parse_bdns_page,
)
from publicdata_core.blobstore import (
    StoredBlob,
    download_to_content_addressed_store,
)
from publicdata_core.http import http_get_bytes
from publicdata_core.util import now_utc_iso, stable_json
from publicdata_ops import (
    claim_work_items,
    collect_futures_with_heartbeat,
    complete_work_items,
    enqueue_work_items,
    ensure_work_queue_schema,
    fail_work_items,
    work_queue_observability,
)
from publicdata_sqlite import (
    open_db,
    upsert_source_records,
)

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_RAW_ROOT = Path("etl/data/raw/bdns/concessions-pages")
SOURCE_ID = "bdns_api_subvenciones"
DEFAULT_PIPELINE = "bdns_concessions"


@dataclass(frozen=True)
class PageOutcome:
    work_item_id: int
    page_number: int
    source_url: str
    stored: StoredBlob | None
    page: BdnsPage | None
    error: str | None
    retryable: bool


class RequestPacer:
    """Serialize request starts without serializing response processing."""

    def __init__(self, interval_seconds: float) -> None:
        self._interval_seconds = max(0.0, float(interval_seconds))
        self._lock = threading.Lock()
        self._next_start = 0.0

    def wait(self) -> None:
        if self._interval_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_start - now)
            if delay:
                time.sleep(delay)
            self._next_start = time.monotonic() + self._interval_seconds


def _failure_circuit_open(
    recent_failures: deque[bool],
    *,
    stop_failure_rate: float,
    window_size: int,
) -> bool:
    """Open only after a full rolling window shows sustained failure."""
    required_samples = max(1, int(window_size))
    if len(recent_failures) < required_samples:
        return False
    threshold = max(0.0, min(1.0, float(stop_failure_rate)))
    failures = sum(recent_failures)
    return failures > 0 and failures / len(recent_failures) >= threshold


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw / (1024.0 * 1024.0) if sys.platform == "darwin" else raw / 1024.0


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return path.name


def _write_report(path: str, payload: dict[str, Any]) -> None:
    if not str(path or "").strip():
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _open_runtime(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    conn = open_db(db_path)
    apply_schema(conn, schema_path)
    seed_sources(conn)
    ensure_work_queue_schema(conn)
    return conn


def _existing_bulk_run(
    conn: sqlite3.Connection,
    pipeline_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM money_bulk_runs WHERE pipeline_id = ?",
        (pipeline_id,),
    ).fetchone()


def enqueue_bdns_pages(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    snapshot_date: str,
    page_size: int,
    max_pages: int,
    timeout: int,
    fetch_bytes: Any = http_get_bytes,
) -> dict[str, Any]:
    first_url = build_bdns_concessions_url(page=0, page_size=page_size)
    payload, content_type = fetch_bytes(first_url, timeout)
    first_page = parse_bdns_page(
        payload,
        feed_url=first_url,
        content_type=content_type,
        expected_page=0,
        expected_page_size=page_size,
    )
    pages_enqueued = first_page.total_pages
    if max_pages > 0:
        pages_enqueued = min(pages_enqueued, int(max_pages))
    existing = _existing_bulk_run(conn, pipeline_id)
    now_iso = now_utc_iso()
    if existing is None:
        ingestion_run_id = start_run(conn, SOURCE_ID, first_url)
        row = conn.execute(
            """
            INSERT INTO money_bulk_runs (
              pipeline_id, ingestion_run_id, source_id, source_url, snapshot_date,
              page_size, total_elements_discovered, total_pages_discovered,
              pages_enqueued, limited_run, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)
            RETURNING money_bulk_run_id
            """,
            (
                pipeline_id,
                ingestion_run_id,
                SOURCE_ID,
                first_url,
                snapshot_date,
                page_size,
                first_page.total_elements,
                first_page.total_pages,
                pages_enqueued,
                int(pages_enqueued < first_page.total_pages),
                now_iso,
                now_iso,
            ),
        ).fetchone()
        conn.commit()
        bulk_run_id = int(row["money_bulk_run_id"])
    else:
        expected = (
            int(existing["page_size"]),
            int(existing["total_elements_discovered"]),
            int(existing["total_pages_discovered"]),
            str(existing["snapshot_date"]),
        )
        observed = (
            int(page_size),
            int(first_page.total_elements),
            int(first_page.total_pages),
            str(snapshot_date),
        )
        if expected != observed:
            raise RuntimeError(
                f"pipeline_id already has a different discovery contract: {pipeline_id}"
            )
        existing_pages = int(existing["pages_enqueued"])
        if pages_enqueued < existing_pages:
            raise RuntimeError(
                "pipeline_id cannot shrink an existing page cohort: "
                f"{pipeline_id} ({existing_pages} -> {pages_enqueued})"
            )
        bulk_run_id = int(existing["money_bulk_run_id"])
        if pages_enqueued > existing_pages:
            conn.execute(
                """
                UPDATE money_bulk_runs
                SET pages_enqueued = ?, limited_run = ?, state = 'running',
                    updated_at = ?, finished_at = NULL
                WHERE money_bulk_run_id = ?
                """,
                (
                    pages_enqueued,
                    int(pages_enqueued < first_page.total_pages),
                    now_iso,
                    bulk_run_id,
                ),
            )
            if existing["ingestion_run_id"] is not None:
                conn.execute(
                    """
                    UPDATE ingestion_runs
                    SET status = 'running', finished_at = NULL,
                        message = ?
                    WHERE run_id = ?
                    """,
                    (
                        (
                            "BDNS bulk cohort expanded: "
                            f"pages={existing_pages}->{pages_enqueued}"
                        ),
                        int(existing["ingestion_run_id"]),
                    ),
                )
            conn.commit()

    def items() -> Any:
        for page_number in range(pages_enqueued):
            yield {
                "item_key": f"page:{page_number:08d}",
                "partition_key": f"block:{page_number // 1000:05d}",
                "payload": {
                    "money_bulk_run_id": bulk_run_id,
                    "page_number": page_number,
                    "page_size": page_size,
                    "snapshot_date": snapshot_date,
                    "source_id": SOURCE_ID,
                    "source_url": build_bdns_concessions_url(
                        page=page_number,
                        page_size=page_size,
                    ),
                },
                "max_attempts": 5,
            }

    queue = enqueue_work_items(
        conn,
        pipeline_id=pipeline_id,
        items=items(),
        batch_size=1_000,
    )
    return {
        "schema_version": "bdns_bulk_enqueue_v1",
        "status": "ok",
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "money_bulk_run_id": bulk_run_id,
        "snapshot_date": snapshot_date,
        "discovery": {
            "page_size": page_size,
            "total_elements": first_page.total_elements,
            "total_pages": first_page.total_pages,
            "pages_enqueued": pages_enqueued,
            "limited_run": pages_enqueued < first_page.total_pages,
        },
        "queue": queue,
        "peak_rss_mb": round(_peak_rss_mb(), 3),
    }


def _fetch_page_item(
    item: Mapping[str, object],
    *,
    raw_root: Path,
    timeout: int,
    max_bytes: int,
    download_attempts: int,
    request_pacer: RequestPacer,
) -> PageOutcome:
    work_item_id = int(item["work_item_id"])
    payload = dict(item.get("payload") or {})
    page_number = int(payload["page_number"])
    page_size = int(payload["page_size"])
    source_url = str(payload["source_url"])
    try:
        request_pacer.wait()
        stored = download_to_content_addressed_store(
            source_url,
            store_root=raw_root,
            timeout=timeout,
            max_bytes=max_bytes,
            max_attempts=download_attempts,
            headers={"Accept": "application/json"},
        )
        page_payload = stored.path.read_bytes()
        if len(page_payload) != stored.bytes:
            raise RuntimeError("stored BDNS page size changed before parse")
        page = parse_bdns_page(
            page_payload,
            feed_url=source_url,
            content_type=stored.content_type,
            expected_page=page_number,
            expected_page_size=page_size,
        )
        return PageOutcome(
            work_item_id,
            page_number,
            source_url,
            stored,
            page,
            None,
            True,
        )
    except Exception as exc:  # noqa: BLE001
        retryable = True
        if isinstance(exc, urllib.error.HTTPError) and exc.code in {
            400,
            404,
            410,
            413,
            414,
            415,
            422,
        }:
            retryable = False
        if "max_bytes" in str(exc) or "mismatch" in str(exc):
            retryable = False
        return PageOutcome(
            work_item_id,
            page_number,
            source_url,
            None,
            None,
            f"{type(exc).__name__}: {exc}"[:2_000],
            retryable,
        )


def _date_token(raw: object) -> str | None:
    value = str(raw or "").strip()
    return value[:10] if len(value) >= 10 else None


def _record_sha256(record: Mapping[str, object]) -> str:
    return hashlib.sha256(stable_json(dict(record)).encode("utf-8")).hexdigest()


def _persist_record_version_lineage(
    conn: sqlite3.Connection,
    *,
    bulk_run_id: int,
    page_fetch_id: int,
    snapshot_date: str,
    records: Sequence[Mapping[str, object]],
    observed_at: str,
) -> int:
    version_rows = [
        (
            SOURCE_ID,
            str(record["source_record_id"]),
            _record_sha256(record),
            observed_at,
            observed_at,
        )
        for record in records
    ]
    conn.executemany(
        """
        INSERT INTO money_source_record_versions (
          source_id, source_record_id, record_sha256, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id, record_sha256) DO UPDATE SET
          last_seen_at=excluded.last_seen_at
        """,
        version_rows,
    )
    sighting_rows = [
        (
            bulk_run_id,
            page_fetch_id,
            SOURCE_ID,
            str(record["source_record_id"]),
            snapshot_date,
            ordinal,
            observed_at,
            SOURCE_ID,
            str(record["source_record_id"]),
            record_sha256,
        )
        for ordinal, (record, record_sha256) in enumerate(
            zip(records, (row[2] for row in version_rows), strict=True)
        )
    ]
    conn.executemany(
        """
        INSERT INTO money_bulk_record_sightings (
          money_bulk_run_id, money_bulk_page_fetch_id, source_id,
          source_record_id, snapshot_date, record_ordinal, observed_at,
          money_source_record_version_id
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, money_source_record_version_id
        FROM money_source_record_versions
        WHERE source_id = ? AND source_record_id = ? AND record_sha256 = ?
        ON CONFLICT(money_bulk_run_id, source_id, source_record_id) DO UPDATE SET
          money_bulk_page_fetch_id=excluded.money_bulk_page_fetch_id,
          snapshot_date=excluded.snapshot_date,
          record_ordinal=excluded.record_ordinal,
          observed_at=excluded.observed_at,
          money_source_record_version_id=excluded.money_source_record_version_id
        """,
        sighting_rows,
    )
    return len(sighting_rows)


def persist_bdns_page(
    conn: sqlite3.Connection,
    *,
    outcome: PageOutcome,
    snapshot_date: str,
    bulk_run_id: int,
) -> int:
    if outcome.stored is None or outcome.page is None:
        raise ValueError("successful stored page is required")
    now_iso = now_utc_iso()
    source_rows = [
        {
            "source_record_id": str(record["source_record_id"]),
            "raw_payload": stable_json(record),
        }
        for record in outcome.page.records
    ]
    pk_map = upsert_source_records(
        conn,
        source_id=SOURCE_ID,
        rows=source_rows,
        snapshot_date=snapshot_date,
        now_iso=now_iso,
    )
    params: list[tuple[object, ...]] = []
    for record in outcome.page.records:
        source_record_id = str(record["source_record_id"])
        source_record_pk = pk_map.get(source_record_id)
        if source_record_pk is None:
            raise RuntimeError(f"missing source_record_pk: {source_record_id}")
        amount = record.get("importe_eur")
        params.append(
            (
                SOURCE_ID,
                source_record_pk,
                source_record_id,
                snapshot_date,
                record.get("source_url"),
                record.get("convocatoria_id"),
                record.get("concesion_id"),
                record.get("organo_convocante"),
                record.get("beneficiario"),
                record.get("beneficiario_id"),
                record.get("program_code"),
                record.get("territory_code"),
                _date_token(record.get("published_at_iso")),
                _date_token(record.get("concession_date")),
                amount,
                "EUR" if amount is not None else None,
                stable_json({"lineage": "source_records.raw_payload"}),
                now_iso,
                now_iso,
            )
        )
    conn.executemany(
        """
        INSERT INTO money_subsidy_records (
          source_id, source_record_pk, source_record_id, source_snapshot_date,
          source_url, call_id, grant_id, granting_body, beneficiary_name,
          beneficiary_identifier, program_code, territory_code, published_date,
          concession_date, amount_eur, currency, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_pk) DO UPDATE SET
          source_record_id=excluded.source_record_id,
          source_snapshot_date=excluded.source_snapshot_date,
          source_url=excluded.source_url,
          call_id=excluded.call_id,
          grant_id=excluded.grant_id,
          granting_body=excluded.granting_body,
          beneficiary_name=excluded.beneficiary_name,
          beneficiary_identifier=excluded.beneficiary_identifier,
          program_code=excluded.program_code,
          territory_code=excluded.territory_code,
          published_date=excluded.published_date,
          concession_date=excluded.concession_date,
          amount_eur=excluded.amount_eur,
          currency=excluded.currency,
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        params,
    )
    conn.execute(
        """
        INSERT INTO money_bulk_page_fetches (
          money_bulk_run_id, work_item_id, page_number, source_url, fetched_at,
          content_sha256, content_type, bytes, raw_path, api_total_elements,
          api_total_pages, records_seen, records_loaded, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(money_bulk_run_id, page_number) DO UPDATE SET
          work_item_id=excluded.work_item_id,
          source_url=excluded.source_url,
          fetched_at=excluded.fetched_at,
          content_sha256=excluded.content_sha256,
          content_type=excluded.content_type,
          bytes=excluded.bytes,
          raw_path=excluded.raw_path,
          api_total_elements=excluded.api_total_elements,
          api_total_pages=excluded.api_total_pages,
          records_seen=excluded.records_seen,
          records_loaded=excluded.records_loaded,
          updated_at=excluded.updated_at
        """,
        (
            bulk_run_id,
            outcome.work_item_id,
            outcome.page_number,
            outcome.source_url,
            now_iso,
            outcome.stored.content_sha256,
            outcome.stored.content_type,
            outcome.stored.bytes,
            str(outcome.stored.path),
            outcome.page.total_elements,
            outcome.page.total_pages,
            outcome.page.number_of_elements,
            len(params),
            now_iso,
            now_iso,
        ),
    )
    page_fetch_row = conn.execute(
        """
        SELECT money_bulk_page_fetch_id
        FROM money_bulk_page_fetches
        WHERE money_bulk_run_id = ? AND page_number = ?
        """,
        (bulk_run_id, outcome.page_number),
    ).fetchone()
    if page_fetch_row is None:
        raise RuntimeError("missing persisted BDNS page lineage")
    _persist_record_version_lineage(
        conn,
        bulk_run_id=bulk_run_id,
        page_fetch_id=int(page_fetch_row[0]),
        snapshot_date=snapshot_date,
        records=outcome.page.records,
        observed_at=now_iso,
    )
    conn.commit()
    return len(params)


def report_bdns_bulk_run(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    finalize: bool,
) -> dict[str, Any]:
    run = _existing_bulk_run(conn, pipeline_id)
    if run is None:
        raise RuntimeError(f"unknown money bulk pipeline: {pipeline_id}")
    bulk_run_id = int(run["money_bulk_run_id"])
    page = conn.execute(
        """
        SELECT
          COUNT(*) AS pages_fetched,
          COALESCE(SUM(records_seen), 0) AS records_seen,
          COALESCE(SUM(records_loaded), 0) AS records_loaded,
          COALESCE(SUM(bytes), 0) AS bytes,
          MIN(api_total_elements) AS min_api_total_elements,
          MAX(api_total_elements) AS max_api_total_elements,
          MIN(api_total_pages) AS min_api_total_pages,
          MAX(api_total_pages) AS max_api_total_pages
        FROM money_bulk_page_fetches
        WHERE money_bulk_run_id = ?
        """,
        (bulk_run_id,),
    ).fetchone()
    queue = work_queue_observability(conn, pipeline_id=pipeline_id, top_limit=10)
    current_source_snapshot_rows = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM source_records
            WHERE source_id = ? AND source_snapshot_date = ?
            """,
            (SOURCE_ID, str(run["snapshot_date"])),
        ).fetchone()[0]
    )
    version_lineage = conn.execute(
        """
        SELECT
          COUNT(*) AS sightings_total,
          COUNT(DISTINCT s.source_record_id) AS distinct_source_records,
          COUNT(DISTINCT s.money_source_record_version_id) AS versions_linked,
          SUM(CASE WHEN length(p.content_sha256) = 64 THEN 1 ELSE 0 END)
            AS raw_page_lineage_rows
        FROM money_bulk_record_sightings AS s
        JOIN money_bulk_page_fetches AS p
          ON p.money_bulk_page_fetch_id = s.money_bulk_page_fetch_id
        WHERE s.money_bulk_run_id = ?
        """,
        (bulk_run_id,),
    ).fetchone()
    revision_records_observed = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM money_bulk_record_sightings AS s
            WHERE s.money_bulk_run_id = ?
              AND EXISTS (
                SELECT 1
                FROM money_source_record_versions AS v
                WHERE v.source_id = s.source_id
                  AND v.source_record_id = s.source_record_id
                  AND v.money_source_record_version_id
                    <> s.money_source_record_version_id
              )
            """,
            (bulk_run_id,),
        ).fetchone()[0]
    )
    version_sightings_total = int(version_lineage["sightings_total"])
    version_distinct_source_records = int(version_lineage["distinct_source_records"])
    distinct_snapshot_rows = (
        version_distinct_source_records
        if version_sightings_total > 0
        else current_source_snapshot_rows
    )
    pages_fetched = int(page["pages_fetched"])
    records_seen = int(page["records_seen"])
    pages_enqueued = int(run["pages_enqueued"])
    page_size = int(run["page_size"])
    total_elements = int(run["total_elements_discovered"])
    expected_rows = min(total_elements, pages_enqueued * page_size)
    state_counts = dict(queue["state_counts"])
    checks = {
        "no_dead_pages": int(state_counts.get("dead", 0)) == 0,
        "all_pages_succeeded": int(state_counts.get("succeeded", 0)) == pages_enqueued,
        "page_fetch_rows_complete": pages_fetched == pages_enqueued,
        "page_record_counts_reconcile": records_seen == expected_rows,
        "distinct_snapshot_rows_reconcile": distinct_snapshot_rows == records_seen,
        "api_total_elements_stable": int(page["min_api_total_elements"] or 0)
        == int(page["max_api_total_elements"] or 0)
        == total_elements,
        "api_total_pages_stable": int(page["min_api_total_pages"] or 0)
        == int(page["max_api_total_pages"] or 0)
        == int(run["total_pages_discovered"]),
        "version_sightings_reconcile": version_sightings_total == records_seen,
        "version_sightings_distinct_reconcile": version_distinct_source_records
        == distinct_snapshot_rows,
        "raw_page_version_lineage_complete": int(
            version_lineage["raw_page_lineage_rows"] or 0
        )
        == version_sightings_total,
    }
    terminal = int(queue["unfinished_total"]) == 0
    all_checks = all(checks.values())
    limited_run = bool(run["limited_run"])
    state = str(run["state"])
    if terminal:
        state = (
            "partial"
            if all_checks and limited_run
            else "succeeded"
            if all_checks
            else "failed"
        )
    if finalize and terminal:
        now_iso = now_utc_iso()
        conn.execute(
            """
            UPDATE money_bulk_runs
            SET state = ?, records_seen = ?, records_loaded = ?,
                updated_at = ?, finished_at = ?
            WHERE money_bulk_run_id = ?
            """,
            (
                state,
                records_seen,
                distinct_snapshot_rows,
                now_iso,
                now_iso,
                bulk_run_id,
            ),
        )
        finish_run(
            conn,
            int(run["ingestion_run_id"]),
            "ok" if all_checks else "error",
            (
                f"BDNS bulk {state}: pages={pages_fetched}/{pages_enqueued}; "
                f"records={records_seen}; limited={int(limited_run)}"
            ),
            records_seen,
            distinct_snapshot_rows,
        )
    return {
        "schema_version": "bdns_bulk_run_report_v1",
        "status": state,
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "money_bulk_run_id": bulk_run_id,
        "snapshot_date": str(run["snapshot_date"]),
        "limited_run": limited_run,
        "discovery": {
            "page_size": page_size,
            "total_elements": total_elements,
            "total_pages": int(run["total_pages_discovered"]),
            "pages_enqueued": pages_enqueued,
        },
        "observed": {
            "pages_fetched": pages_fetched,
            "records_seen": records_seen,
            "records_loaded_distinct": distinct_snapshot_rows,
            "bytes": int(page["bytes"]),
            "peak_rss_mb": round(_peak_rss_mb(), 3),
        },
        "record_versions": {
            "sightings_total": version_sightings_total,
            "distinct_source_records": version_distinct_source_records,
            "current_source_rows_for_snapshot": current_source_snapshot_rows,
            "versions_linked": int(version_lineage["versions_linked"]),
            "raw_page_lineage_rows": int(version_lineage["raw_page_lineage_rows"] or 0),
            "records_with_prior_versions": revision_records_observed,
            "raw_payload_duplicated": False,
        },
        "queue": queue,
        "checks": checks,
        "analytical_ingest_gate_passed": terminal and all_checks,
        "promotion_gate_passed": terminal and all_checks and not limited_run,
        "publication_status": "local_raw_captured_not_published",
        "limitations": [
            "Official BDNS fields, including natural-person names and source-published identifiers, are retained exactly; source-side masking remains unchanged.",
            "A limited page cohort proves bounded acquisition and reconciliation, not full-registry completeness.",
        ],
    }


def backfill_record_version_lineage(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    max_pages: int = 0,
) -> dict[str, Any]:
    run = _existing_bulk_run(conn, pipeline_id)
    if run is None:
        raise RuntimeError(f"unknown money bulk pipeline: {pipeline_id}")
    bulk_run_id = int(run["money_bulk_run_id"])
    query = """
        SELECT p.*, COUNT(s.money_bulk_record_sighting_id) AS sightings_total
        FROM money_bulk_page_fetches AS p
        LEFT JOIN money_bulk_record_sightings AS s
          ON s.money_bulk_page_fetch_id = p.money_bulk_page_fetch_id
        WHERE p.money_bulk_run_id = ?
        GROUP BY p.money_bulk_page_fetch_id
        HAVING sightings_total <> p.records_loaded
        ORDER BY p.page_number
    """
    params: list[object] = [bulk_run_id]
    if max_pages > 0:
        query += " LIMIT ?"
        params.append(int(max_pages))
    pages = conn.execute(query, params).fetchall()
    pages_processed = 0
    records_versioned = 0
    for page_row in pages:
        raw_path = Path(str(page_row["raw_path"]))
        payload = raw_path.read_bytes()
        observed_sha256 = hashlib.sha256(payload).hexdigest()
        expected_sha256 = str(page_row["content_sha256"])
        if observed_sha256 != expected_sha256:
            raise RuntimeError(
                f"BDNS raw page checksum mismatch: page={int(page_row['page_number'])}"
            )
        page = parse_bdns_page(
            payload,
            feed_url=str(page_row["source_url"]),
            content_type=str(page_row["content_type"] or "") or None,
            expected_page=int(page_row["page_number"]),
            expected_page_size=int(run["page_size"]),
        )
        if len(page.records) != int(page_row["records_loaded"]):
            raise RuntimeError(
                "BDNS raw page record mismatch during version backfill: "
                f"page={page.page_number}"
            )
        observed_at = now_utc_iso()
        records_versioned += _persist_record_version_lineage(
            conn,
            bulk_run_id=bulk_run_id,
            page_fetch_id=int(page_row["money_bulk_page_fetch_id"]),
            snapshot_date=str(run["snapshot_date"]),
            records=page.records,
            observed_at=observed_at,
        )
        conn.commit()
        pages_processed += 1
    report = report_bdns_bulk_run(conn, pipeline_id=pipeline_id, finalize=False)
    report["version_backfill"] = {
        "pages_processed": pages_processed,
        "records_versioned": records_versioned,
        "max_pages": max(0, int(max_pages)),
        "raw_payload_duplicated": False,
    }
    return report


def run_worker(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    raw_root: Path,
    workers: int,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    timeout: int,
    max_bytes: int,
    download_attempts: int,
    retry_delay_seconds: int,
    request_interval_seconds: float,
    stop_failure_rate: float,
    failure_window_size: int,
) -> dict[str, Any]:
    processed = 0
    successes = 0
    failures = 0
    stop_reason = "queue_drained"
    request_pacer = RequestPacer(request_interval_seconds)
    recent_failures: deque[bool] = deque(maxlen=max(1, failure_window_size))
    while max_items <= 0 or processed < max_items:
        limit = min(claim_size, max_items - processed) if max_items > 0 else claim_size
        claimed = claim_work_items(
            conn,
            pipeline_id=pipeline_id,
            worker_id=worker_id,
            limit=max(1, limit),
            lease_seconds=lease_seconds,
        )
        if not claimed:
            break
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(
                    _fetch_page_item,
                    item,
                    raw_root=raw_root,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    download_attempts=download_attempts,
                    request_pacer=request_pacer,
                ): int(item["work_item_id"])
                for item in claimed
            }
            outcomes = collect_futures_with_heartbeat(
                conn,
                futures=futures,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
            )
        payload_by_id = {
            int(item["work_item_id"]): dict(item.get("payload") or {})
            for item in claimed
        }
        for outcome in outcomes:
            processed += 1
            item_payload = payload_by_id[outcome.work_item_id]
            if outcome.error is not None:
                failures += 1
                fail_work_items(
                    conn,
                    worker_id=worker_id,
                    work_item_ids=[outcome.work_item_id],
                    error=outcome.error,
                    retry_delay_seconds=retry_delay_seconds,
                    retryable=outcome.retryable,
                )
                recent_failures.append(True)
                continue
            try:
                persist_bdns_page(
                    conn,
                    outcome=outcome,
                    snapshot_date=str(item_payload["snapshot_date"]),
                    bulk_run_id=int(item_payload["money_bulk_run_id"]),
                )
                completed = complete_work_items(
                    conn,
                    worker_id=worker_id,
                    work_item_ids=[outcome.work_item_id],
                )
                if completed != 1:
                    raise RuntimeError("lost page lease before completion")
                successes += 1
                recent_failures.append(False)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                conn.rollback()
                fail_work_items(
                    conn,
                    worker_id=worker_id,
                    work_item_ids=[outcome.work_item_id],
                    error=f"persist_error: {type(exc).__name__}: {exc}",
                    retry_delay_seconds=retry_delay_seconds,
                    retryable=True,
                )
                recent_failures.append(True)
        if _failure_circuit_open(
            recent_failures,
            stop_failure_rate=stop_failure_rate,
            window_size=failure_window_size,
        ):
            stop_reason = "upstream_failure_rate_circuit_open"
            break
    report = report_bdns_bulk_run(conn, pipeline_id=pipeline_id, finalize=True)
    report["worker"] = {
        "worker_id": worker_id,
        "processed": processed,
        "succeeded": successes,
        "failed_attempts": failures,
        "workers": workers,
        "claim_size": claim_size,
        "request_interval_seconds": request_interval_seconds,
        "stop_failure_rate": stop_failure_rate,
        "failure_window_size": max(1, failure_window_size),
        "stop_reason": stop_reason,
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Durable BDNS bulk ingestion")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--pipeline-id", default=DEFAULT_PIPELINE)
    parser.add_argument("--report-out", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enqueue = subparsers.add_parser("enqueue")
    enqueue.add_argument("--snapshot-date", required=True)
    enqueue.add_argument("--page-size", type=int, default=1_000)
    enqueue.add_argument("--max-pages", type=int, default=0)
    enqueue.add_argument("--timeout", type=int, default=30)

    work = subparsers.add_parser("work")
    work.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    work.add_argument("--worker-id", default="bdns-bulk-worker")
    work.add_argument("--workers", type=int, default=2)
    work.add_argument("--claim-size", type=int, default=4)
    work.add_argument("--max-items", type=int, default=0)
    work.add_argument("--lease-seconds", type=int, default=300)
    work.add_argument("--timeout", type=int, default=30)
    work.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    work.add_argument("--download-attempts", type=int, default=3)
    work.add_argument("--retry-delay-seconds", type=int, default=30)
    work.add_argument("--request-interval-seconds", type=float, default=0.75)
    work.add_argument("--stop-failure-rate", type=float, default=0.5)
    work.add_argument("--failure-window-size", type=int, default=20)

    report = subparsers.add_parser("report")
    report.add_argument("--finalize", action="store_true")
    version_backfill = subparsers.add_parser("backfill-version-lineage")
    version_backfill.add_argument("--max-pages", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    conn = _open_runtime(Path(args.db), Path(args.schema))
    try:
        if args.command == "enqueue":
            report = enqueue_bdns_pages(
                conn,
                pipeline_id=args.pipeline_id,
                snapshot_date=args.snapshot_date,
                page_size=args.page_size,
                max_pages=args.max_pages,
                timeout=args.timeout,
            )
        elif args.command == "work":
            report = run_worker(
                conn,
                pipeline_id=args.pipeline_id,
                worker_id=args.worker_id,
                raw_root=Path(args.raw_root),
                workers=args.workers,
                claim_size=args.claim_size,
                max_items=args.max_items,
                lease_seconds=args.lease_seconds,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                download_attempts=args.download_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
                request_interval_seconds=args.request_interval_seconds,
                stop_failure_rate=args.stop_failure_rate,
                failure_window_size=args.failure_window_size,
            )
        elif args.command == "report":
            report = report_bdns_bulk_run(
                conn,
                pipeline_id=args.pipeline_id,
                finalize=args.finalize,
            )
        else:
            report = backfill_record_version_lineage(
                conn,
                pipeline_id=args.pipeline_id,
                max_pages=args.max_pages,
            )
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    _write_report(args.report_out, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if report.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
