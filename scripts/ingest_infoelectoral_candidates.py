#!/usr/bin/env python3
"""Queue, acquire, and ingest official Infoelectoral candidate archives."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.infoelectoral_es.candidates import (
    candidate_report,
    ingest_candidate_archive,
    upsert_candidate_archive_catalog,
)
from etl.infoelectoral_es.db import seed_sources
from etl.politicos_es.db import apply_schema, finish_run, start_run
from etl.politicos_es.util import now_utc_iso
from publicdata_connectors_es.infoelectoral.candidates import (
    DEFAULT_MAX_ARCHIVE_BYTES,
    DEFAULT_MAX_CANDIDATE_ROWS,
    DEFAULT_MAX_COMPRESSION_RATIO,
    DEFAULT_MAX_MEMBERS,
    DEFAULT_MAX_PARTY_ROWS,
    DEFAULT_MAX_UNCOMPRESSED_BYTES,
    SOURCE_ID,
    CandidateArchiveSpec,
    CandidateArchiveMetrics,
    iter_candidate_archive,
)
from publicdata_core.blobstore import (
    StoredBlob,
    download_to_content_addressed_store,
    stream_response_to_content_addressed_store,
)
from publicdata_ops import (
    claim_work_items,
    complete_work_items,
    enqueue_work_items,
    fail_work_items,
    heartbeat_work_items,
    work_queue_observability,
)
from publicdata_sqlite import open_db


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_PIPELINE_ID = "infoelectoral-candidates-v1"
DEFAULT_STORE_ROOT = Path(
    "etl/data/object-origin/restricted/infoelectoral-candidates"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "infoelectoral-candidate-archive-queue-latest.json"
)
DEFAULT_MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
_ARCHIVE_NAME = re.compile(r"^([0-9]{2})([0-9]{4})([0-9]{2})_MUNI\.zip$")
_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_DATE_IN_DESCRIPTION = re.compile(
    r"\b([0-9]{1,2})\s+de\s+([A-Za-záéíóúÁÉÍÓÚ]+)\s+de\s+([0-9]{4})\b"
)
_ROW_FLOORS = {"02": 1_000, "03": 500, "04": 10_000, "06": 50, "07": 1_000}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _display_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:2_000]


def _official_archive_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "infoelectoral.interior.gob.es"
        or not parsed.path.startswith("/estaticos/docxl/apliextr/")
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(f"candidate archive URL is outside official allowlist: {url}")
    return url


def _description_date(description: str) -> str:
    match = _DATE_IN_DESCRIPTION.search(str(description or ""))
    if match is None:
        raise RuntimeError(f"candidate archive lacks exact election date: {description}")
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        raise RuntimeError(f"candidate archive has unknown month: {match.group(2)}")
    return dt.date(int(match.group(3)), month, int(match.group(1))).isoformat()


def _catalog_specs(conn: sqlite3.Connection) -> list[CandidateArchiveSpec]:
    rows = conn.execute(
        """
        SELECT a.archivo_id, a.tipo_convocatoria, a.id_convocatoria,
               a.nombre_doc, a.descripcion, a.download_url
        FROM infoelectoral_archivos_extraccion AS a
        WHERE lower(a.nombre_doc) LIKE '%_muni.zip'
        ORDER BY a.id_convocatoria, a.tipo_convocatoria, a.archivo_id
        """
    ).fetchall()
    specs: list[CandidateArchiveSpec] = []
    seen_urls: set[str] = set()
    for row in rows:
        filename = str(row["nombre_doc"] or "").strip()
        match = _ARCHIVE_NAME.fullmatch(filename)
        if match is None:
            raise RuntimeError(f"unexpected Infoelectoral archive filename: {filename}")
        election_type = str(row["tipo_convocatoria"] or "").zfill(2)
        election_id = str(row["id_convocatoria"] or "").strip()
        if match.group(1) != election_type or match.group(2) + match.group(3) != election_id:
            raise RuntimeError(f"candidate archive catalog identity mismatch: {filename}")
        if election_type not in _ROW_FLOORS:
            continue
        source_url = _official_archive_url(str(row["download_url"] or ""))
        if source_url in seen_urls:
            raise RuntimeError(f"duplicate candidate archive URL: {source_url}")
        seen_urls.add(source_url)
        specs.append(
            CandidateArchiveSpec(
                archive_id=str(row["archivo_id"]),
                source_url=source_url,
                election_date=_description_date(str(row["descripcion"] or "")),
                election_type_code=election_type,
                election_id=election_id,
            )
        )
    if not specs:
        raise RuntimeError("candidate archive catalog contains no supported MUNI ZIPs")
    return specs


def initialize(conn: sqlite3.Connection, schema: Path) -> None:
    apply_schema(conn, schema)
    seed_sources(conn)


def enqueue_catalog(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    snapshot_date: str,
    max_archive_bytes: int,
    max_attempts: int,
) -> dict[str, Any]:
    specs = _catalog_specs(conn)
    for spec in specs:
        upsert_candidate_archive_catalog(
            conn,
            spec=spec,
            snapshot_date=snapshot_date,
        )
    result = enqueue_work_items(
        conn,
        pipeline_id=pipeline_id,
        items=(
            {
                "item_key": spec.archive_id,
                "partition_key": spec.election_id[:4],
                "priority": int(spec.election_id),
                "max_attempts": int(max_attempts),
                "payload": {
                    "archive_id": spec.archive_id,
                    "source_url": spec.source_url,
                    "election_date": spec.election_date,
                    "election_type_code": spec.election_type_code,
                    "election_id": spec.election_id,
                    "snapshot_date": snapshot_date,
                    "minimum_candidate_rows": _ROW_FLOORS[
                        spec.election_type_code
                    ],
                    "maximum_archive_bytes": int(max_archive_bytes),
                },
            }
            for spec in specs
        ),
    )
    return {
        "schema_version": "infoelectoral_candidate_enqueue_v1",
        "status": "ok",
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "snapshot_date": snapshot_date,
        "supported_election_types": sorted(_ROW_FLOORS),
        "catalog_archives": len(specs),
        "enqueue": result,
        "queue": work_queue_observability(conn, pipeline_id=pipeline_id),
        "public_domain_identity_contract": {
            "official_archive_bytes_retained": True,
            "normalized_dni_persisted": True,
            "normalized_birth_date_persisted": True,
            "source_birth_date_persisted": True,
            "classification_never_suppresses_identity": True,
        },
    }


def _storage_preflight(
    path: Path, *, min_free_bytes: int, reserve_bytes: int
) -> dict[str, Any]:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    required = int(min_free_bytes) + int(reserve_bytes)
    return {
        "schema_version": "storage_capacity_preflight_v1",
        "path": _display_path(path),
        "free_bytes": int(usage.free),
        "min_free_bytes": int(min_free_bytes),
        "reserve_bytes": int(reserve_bytes),
        "required_free_bytes": required,
        "headroom_bytes": int(usage.free) - required,
        "ready": int(usage.free) >= required,
    }


def _spec_from_payload(payload: dict[str, Any]) -> CandidateArchiveSpec:
    return CandidateArchiveSpec(
        archive_id=str(payload["archive_id"]),
        source_url=_official_archive_url(str(payload["source_url"])),
        election_date=dt.date.fromisoformat(str(payload["election_date"])).isoformat(),
        election_type_code=str(payload["election_type_code"]),
        election_id=str(payload["election_id"]),
    )


def _local_or_network_blob(
    *,
    spec: CandidateArchiveSpec,
    local_archive_dir: Path | None,
    store_root: Path,
    timeout: int,
    max_archive_bytes: int,
    insecure_ssl: bool,
    ca_bundle: Path | None,
    heartbeat: Any,
) -> tuple[StoredBlob, str]:
    if local_archive_dir is not None:
        local_path = Path(local_archive_dir) / Path(urlsplit(spec.source_url).path).name
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
        with local_path.open("rb") as handle:
            stored = stream_response_to_content_addressed_store(
                handle,
                url=spec.source_url,
                store_root=store_root,
                max_bytes=max_archive_bytes,
                progress_callback=heartbeat,
            )
        return stored, "local_replay"
    stored = download_to_content_addressed_store(
        spec.source_url,
        store_root=store_root,
        timeout=timeout,
        max_bytes=max_archive_bytes,
        chunk_bytes=1024 * 1024,
        max_attempts=1,
        ca_bundle=ca_bundle,
        insecure_ssl=insecure_ssl,
        progress_callback=heartbeat,
    )
    return stored, "official_network"


def _record_fetch(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    spec: CandidateArchiveSpec,
    stored: StoredBlob,
) -> str:
    fetched_at = now_utc_iso()
    values = (
        run_id,
        SOURCE_ID,
        spec.source_url,
        fetched_at,
        _display_path(stored.path),
        stored.content_sha256,
        stored.content_type or "application/zip",
        stored.bytes,
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
    conn.execute(
        """
        INSERT INTO run_fetches (
          run_id, source_id, source_url, fetched_at, raw_path,
          content_sha256, content_type, bytes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          fetched_at=excluded.fetched_at,
          raw_path=excluded.raw_path,
          content_sha256=excluded.content_sha256,
          content_type=excluded.content_type,
          bytes=excluded.bytes
        """,
        values,
    )
    conn.commit()
    return fetched_at


def _drift_report(
    conn: sqlite3.Connection,
    *,
    archive_id: str,
    incoming_rows: int,
    max_row_drift_ratio: float,
    allow_large_drift: bool,
) -> dict[str, Any]:
    previous = int(
        conn.execute(
            """
            SELECT candidate_rows FROM infoelectoral_candidate_archives
            WHERE archive_id=?
            """,
            (archive_id,),
        ).fetchone()[0]
    )
    ratio = None if previous == 0 else abs(incoming_rows - previous) / previous
    within = previous == 0 or float(ratio) <= float(max_row_drift_ratio)
    return {
        "schema_version": "infoelectoral_candidate_archive_drift_v1",
        "previous_present_rows": previous,
        "incoming_rows": int(incoming_rows),
        "delta_rows": int(incoming_rows) - previous,
        "absolute_drift_ratio": None if ratio is None else round(ratio, 9),
        "max_row_drift_ratio": float(max_row_drift_ratio),
        "allow_large_drift": bool(allow_large_drift),
        "status": "ok" if within else (
            "override" if allow_large_drift else "blocked"
        ),
        "ready": within or bool(allow_large_drift),
    }


def run_worker(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    store_root: Path,
    local_archive_dir: Path | None,
    timeout: int,
    max_items: int,
    batch_rows: int,
    max_archive_bytes: int,
    max_uncompressed_bytes: int,
    max_candidate_rows: int,
    max_members: int,
    max_party_rows: int,
    max_compression_ratio: float,
    min_free_bytes: int,
    max_row_drift_ratio: float,
    allow_large_drift: bool,
    insecure_ssl: bool,
    ca_bundle: Path | None,
) -> dict[str, Any]:
    storage = _storage_preflight(
        store_root,
        min_free_bytes=min_free_bytes,
        reserve_bytes=max_archive_bytes,
    )
    if not storage["ready"]:
        return {
            "schema_version": "infoelectoral_candidate_worker_v1",
            "status": "blocked_storage",
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "storage_preflight": storage,
            "queue": work_queue_observability(conn, pipeline_id=pipeline_id),
        }
    attempted = 0
    succeeded = 0
    failed = 0
    archive_reports: list[dict[str, Any]] = []
    lease_seconds = max(300, timeout * 4)
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
        payload = dict(item["payload"])
        spec = _spec_from_payload(payload)
        run_id = start_run(conn, SOURCE_ID, spec.source_url)
        last_heartbeat = monotonic()

        def heartbeat(*, force: bool = False) -> None:
            nonlocal last_heartbeat
            current = monotonic()
            if not force and current - last_heartbeat < min(60.0, lease_seconds / 3):
                return
            if heartbeat_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[item_id],
                lease_seconds=lease_seconds,
            ) != 1:
                raise RuntimeError(f"candidate worker lost lease: {item_id}")
            last_heartbeat = current

        try:
            stored, acquisition_mode = _local_or_network_blob(
                spec=spec,
                local_archive_dir=local_archive_dir,
                store_root=store_root,
                timeout=timeout,
                max_archive_bytes=max_archive_bytes,
                insecure_ssl=insecure_ssl,
                ca_bundle=ca_bundle,
                heartbeat=heartbeat,
            )
            heartbeat(force=True)
            parser_args = {
                "spec": spec,
                "source_content_sha256": stored.content_sha256,
                "max_archive_bytes": max_archive_bytes,
                "max_uncompressed_bytes": max_uncompressed_bytes,
                "max_members": max_members,
                "max_candidate_rows": max_candidate_rows,
                "max_party_rows": max_party_rows,
                "max_compression_ratio": max_compression_ratio,
            }
            archive_metrics = CandidateArchiveMetrics()
            validated_rows = sum(
                1
                for _ in iter_candidate_archive(
                    stored.path, **parser_args, metrics=archive_metrics
                )
            )
            if archive_metrics.candidate_rows != validated_rows:
                raise RuntimeError("candidate archive metric/validation mismatch")
            if archive_metrics.party_rows < 1:
                raise RuntimeError("candidate archive requires party rows")
            minimum_rows = int(payload["minimum_candidate_rows"])
            if validated_rows < minimum_rows:
                raise RuntimeError(
                    "candidate archive below row floor: "
                    f"observed={validated_rows} minimum={minimum_rows}"
                )
            drift = _drift_report(
                conn,
                archive_id=spec.archive_id,
                incoming_rows=validated_rows,
                max_row_drift_ratio=max_row_drift_ratio,
                allow_large_drift=allow_large_drift,
            )
            if not drift["ready"]:
                raise RuntimeError(
                    "candidate archive source drift blocked: "
                    f"ratio={drift['absolute_drift_ratio']}"
                )
            fetched_at = _record_fetch(
                conn,
                run_id=run_id,
                spec=spec,
                stored=stored,
            )
            ingest = ingest_candidate_archive(
                conn,
                iter_candidate_archive(stored.path, **parser_args),
                spec=spec,
                snapshot_date=str(payload["snapshot_date"]),
                source_content_sha256=stored.content_sha256,
                archive_bytes=stored.bytes,
                raw_path=_display_path(stored.path),
                party_rows=archive_metrics.party_rows,
                batch_rows=batch_rows,
                run_id=run_id,
            )
            if int(ingest["processed"]) != validated_rows:
                raise RuntimeError("candidate archive validation/load mismatch")
            finish_run(
                conn,
                run_id,
                "ok",
                f"candidate archive {spec.archive_id}: {validated_rows}",
                validated_rows,
                validated_rows,
                fetched_at=fetched_at,
                raw_path=Path(_display_path(stored.path)),
            )
            heartbeat(force=True)
            if complete_work_items(
                conn, worker_id=worker_id, work_item_ids=[item_id]
            ) != 1:
                raise RuntimeError(f"candidate worker could not complete item {item_id}")
            succeeded += 1
            archive_reports.append(
                {
                    "archive_id": spec.archive_id,
                    "status": "ok",
                    "candidate_rows": validated_rows,
                    "party_rows": archive_metrics.party_rows,
                    "content_sha256": stored.content_sha256,
                    "bytes": stored.bytes,
                    "raw_path": _display_path(stored.path),
                    "acquisition_mode": acquisition_mode,
                    "tls_verified": (
                        None if acquisition_mode == "local_replay" else not insecure_ssl
                    ),
                    "drift": drift,
                }
            )
        except Exception as exc:
            clean_error = _safe_error(exc)
            retryable = "source drift blocked" not in clean_error
            finish_run(conn, run_id, "error", clean_error, 0, 0)
            fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[item_id],
                error=clean_error,
                retry_delay_seconds=300,
                retryable=retryable,
            )
            conn.execute(
                """
                UPDATE infoelectoral_candidate_archives
                SET status='failed', last_error=?, updated_at=?
                WHERE archive_id=?
                """,
                (clean_error, now_utc_iso(), spec.archive_id),
            )
            conn.commit()
            failed += 1
            archive_reports.append(
                {
                    "archive_id": spec.archive_id,
                    "status": "failed",
                    "error": clean_error,
                }
            )
    return {
        "schema_version": "infoelectoral_candidate_worker_v1",
        "status": "ok" if failed == 0 else "partial",
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "storage_preflight": storage,
        "archives": archive_reports,
        "queue": work_queue_observability(conn, pipeline_id=pipeline_id),
    }


def build_report(
    conn: sqlite3.Connection, *, pipeline_id: str, db_path: Path
) -> dict[str, Any]:
    queue = work_queue_observability(conn, pipeline_id=pipeline_id)
    facts = candidate_report(conn)
    mandates = int(conn.execute("SELECT COUNT(*) FROM mandates").fetchone()[0])
    candidates = int(facts["totals"]["candidate_occurrences"])
    quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    foreign_key_violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    queue_complete = (
        int(queue["items_total"]) > 0
        and int(queue["unfinished_total"]) == 0
        and int(dict(queue["state_counts"])["dead"]) == 0
    )
    real_s1 = queue_complete and mandates + candidates >= 100_000
    return {
        "schema_version": "infoelectoral_candidate_pipeline_report_v1",
        "status": "ok" if queue_complete and facts["status"] == "ok" else "pending",
        "source_id": SOURCE_ID,
        "pipeline_id": pipeline_id,
        "database": {
            "path": _display_path(db_path),
            "quick_check": quick_check,
            "foreign_key_violations": foreign_key_violations,
            "ok": quick_check == "ok" and foreign_key_violations == 0,
        },
        "queue": queue,
        "facts": facts,
        "actor_scale": {
            "mandates": mandates,
            "candidate_occurrences": candidates,
            "actor_candidate_mandate_rows": mandates + candidates,
            "s1_minimum_rows": 100_000,
            "real_s1_row_gate_passed": real_s1,
            "external_identity_verified": False,
            "promotion_gate_passed": False,
        },
        "publication_status": "restricted_raw_local_normalized_not_published",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--pipeline-id", default=DEFAULT_PIPELINE_ID)
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    sub = parser.add_subparsers(dest="command", required=True)

    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--snapshot-date", default=dt.date.today().isoformat())
    enqueue.add_argument("--max-archive-bytes", type=int, default=DEFAULT_MAX_ARCHIVE_BYTES)
    enqueue.add_argument("--max-attempts", type=int, default=5)

    worker = sub.add_parser("worker")
    worker.add_argument("--worker-id", default="infoelectoral-candidate-worker")
    worker.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    worker.add_argument("--local-archive-dir")
    worker.add_argument("--timeout", type=int, default=120)
    worker.add_argument("--max-items", type=int, default=1)
    worker.add_argument("--batch-rows", type=int, default=10_000)
    worker.add_argument("--max-archive-bytes", type=int, default=DEFAULT_MAX_ARCHIVE_BYTES)
    worker.add_argument(
        "--max-uncompressed-bytes",
        type=int,
        default=DEFAULT_MAX_UNCOMPRESSED_BYTES,
    )
    worker.add_argument("--max-candidate-rows", type=int, default=DEFAULT_MAX_CANDIDATE_ROWS)
    worker.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    worker.add_argument("--max-party-rows", type=int, default=DEFAULT_MAX_PARTY_ROWS)
    worker.add_argument(
        "--max-compression-ratio",
        type=float,
        default=DEFAULT_MAX_COMPRESSION_RATIO,
    )
    worker.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    worker.add_argument("--max-row-drift-ratio", type=float, default=0.15)
    worker.add_argument("--allow-large-drift", action="store_true")
    worker.add_argument("--insecure-ssl", action="store_true")
    worker.add_argument("--ca-bundle")

    report = sub.add_parser("report")
    report.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    conn = open_db(db_path)
    try:
        initialize(conn, Path(args.schema))
        if args.command == "enqueue":
            payload = enqueue_catalog(
                conn,
                pipeline_id=args.pipeline_id,
                snapshot_date=dt.date.fromisoformat(args.snapshot_date).isoformat(),
                max_archive_bytes=int(args.max_archive_bytes),
                max_attempts=int(args.max_attempts),
            )
        elif args.command == "worker":
            if args.ca_bundle and args.insecure_ssl:
                raise ValueError("--ca-bundle and --insecure-ssl are mutually exclusive")
            payload = run_worker(
                conn,
                pipeline_id=args.pipeline_id,
                worker_id=args.worker_id,
                store_root=Path(args.store_root),
                local_archive_dir=(
                    Path(args.local_archive_dir) if args.local_archive_dir else None
                ),
                timeout=int(args.timeout),
                max_items=int(args.max_items),
                batch_rows=int(args.batch_rows),
                max_archive_bytes=int(args.max_archive_bytes),
                max_uncompressed_bytes=int(args.max_uncompressed_bytes),
                max_candidate_rows=int(args.max_candidate_rows),
                max_members=int(args.max_members),
                max_party_rows=int(args.max_party_rows),
                max_compression_ratio=float(args.max_compression_ratio),
                min_free_bytes=int(args.min_free_bytes),
                max_row_drift_ratio=float(args.max_row_drift_ratio),
                allow_large_drift=bool(args.allow_large_drift),
                insecure_ssl=bool(args.insecure_ssl),
                ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
            )
        else:
            payload = build_report(
                conn,
                pipeline_id=args.pipeline_id,
                db_path=db_path,
            )
        _write_json(Path(args.report_out), payload)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        if args.command == "report" and args.enforce:
            return 0 if payload["status"] == "ok" else 1
        return 0 if payload["status"] in {"ok", "pending", "partial"} else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
