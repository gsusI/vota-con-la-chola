#!/usr/bin/env python3
"""Acquire and bulk-ingest official historical elected-person workbooks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import re
import resource
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.infoelectoral_es.db import seed_sources as seed_infoelectoral_sources
from etl.infoelectoral_es.elected_officials import (
    elected_officials_report,
    ingest_elected_officials,
)
from etl.politicos_es.db import apply_schema, finish_run, start_run
from publicdata_connectors_es.infoelectoral.elected_officials import (
    DEFAULT_MAX_ROWS,
    DEFAULT_MAX_UNCOMPRESSED_BYTES,
    DEFAULT_MAX_WORKBOOK_BYTES,
    ElectedWorkbookSpec,
    SOURCE_ID,
    WORKBOOKS,
    XLSX_CONTENT_TYPE,
    iter_elected_officials,
)
from publicdata_connectors_es.infoelectoral.config import (
    INFOELECTORAL_ELECTED_CATALOG_URL,
)
from publicdata_core.blobstore import (
    StoredBlob,
    download_to_content_addressed_store,
    stream_response_to_content_addressed_store,
)
from publicdata_core.util import now_utc_iso
from publicdata_sqlite import open_db

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_STORE_ROOT = Path("etl/data/object-origin/infoelectoral-elected-officials")
DEFAULT_MANIFEST_ROOT = Path("etl/data/raw/infoelectoral/elected-officials/manifests")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "infoelectoral-elected-officials-real-20260811.json"
)
DEFAULT_MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
OFFICIAL_HOST = "descargas.interior.gob.es"


@dataclass(frozen=True)
class AcquiredWorkbook:
    spec: ElectedWorkbookSpec
    stored: StoredBlob
    acquisition_mode: str
    tls_verified: bool | None


def _display_path(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return Path(path).name


def _safe_error(exc: BaseException) -> str:
    message = str(exc)
    message = message.replace(str(REPO_ROOT.resolve()), ".")
    message = re.sub(r"/(?:Users|home)/[^\s:]+", "<local-path>", message)
    message = re.sub(r"/private/tmp/[^\s:]+", "<temporary-file>", message)
    return f"{type(exc).__name__}: {message}"[:2_000]


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw / (1024.0 * 1024.0) if sys.platform == "darwin" else raw / 1024.0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _storage_preflight(
    path: Path,
    *,
    min_free_bytes: int,
    reserve_bytes: int,
) -> dict[str, Any]:
    if int(min_free_bytes) < 0 or int(reserve_bytes) < 1:
        raise ValueError("storage bounds must be nonnegative and reserve positive")
    Path(path).mkdir(parents=True, exist_ok=True)
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


def _validate_official_source(spec: ElectedWorkbookSpec) -> None:
    parsed = urlsplit(spec.source_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != OFFICIAL_HOST:
        raise RuntimeError(f"unapproved elected-official source URL: {spec.source_url}")
    if not parsed.path.lower().endswith(".xlsx"):
        raise RuntimeError("official elected-official source must be XLSX")


def _local_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    allowed = {spec.chamber for spec in WORKBOOKS}
    for raw in values:
        chamber, separator, path = str(raw).partition("=")
        chamber = chamber.strip().lower()
        if not separator or chamber not in allowed or chamber in overrides:
            raise ValueError(
                "--from-file requires one unique CHAMBER=PATH for congreso or senado"
            )
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        overrides[chamber] = candidate
    if overrides and set(overrides) != allowed:
        raise ValueError("local replay requires both congreso and senado workbooks")
    return overrides


def _store_local(
    path: Path,
    *,
    spec: ElectedWorkbookSpec,
    store_root: Path,
    max_workbook_bytes: int,
) -> StoredBlob:
    with Path(path).open("rb") as handle:
        return stream_response_to_content_addressed_store(
            handle,
            url=spec.source_url,
            store_root=store_root,
            max_bytes=int(max_workbook_bytes),
        )


def _acquire(
    *,
    store_root: Path,
    timeout: int,
    ca_bundle: Path | None,
    insecure_ssl: bool,
    local_files: dict[str, Path],
    max_workbook_bytes: int,
) -> list[AcquiredWorkbook]:
    acquired: list[AcquiredWorkbook] = []
    for spec in WORKBOOKS:
        _validate_official_source(spec)
        if local_files:
            stored = _store_local(
                local_files[spec.chamber],
                spec=spec,
                store_root=store_root,
                max_workbook_bytes=max_workbook_bytes,
            )
            mode = "local_replay_to_content_addressed_store"
            tls_verified: bool | None = None
        else:
            stored = download_to_content_addressed_store(
                spec.source_url,
                store_root=store_root,
                timeout=int(timeout),
                headers={"Accept": XLSX_CONTENT_TYPE},
                max_bytes=int(max_workbook_bytes),
                max_attempts=2,
                ca_bundle=ca_bundle,
                insecure_ssl=bool(insecure_ssl),
            )
            mode = "official_network"
            tls_verified = not bool(insecure_ssl)
        acquired.append(
            AcquiredWorkbook(
                spec=spec,
                stored=stored,
                acquisition_mode=mode,
                tls_verified=tls_verified,
            )
        )
    return acquired


def _validate_workbooks(
    acquired: list[AcquiredWorkbook],
    *,
    max_workbook_bytes: int,
    max_uncompressed_bytes: int,
    max_rows: int,
    minimum_rows: dict[str, int],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in acquired:
        count = sum(
            1
            for _ in iter_elected_officials(
                item.stored.path,
                spec=item.spec,
                source_content_sha256=item.stored.content_sha256,
                max_workbook_bytes=max_workbook_bytes,
                max_uncompressed_bytes=max_uncompressed_bytes,
                max_rows=max_rows,
            )
        )
        if count < int(minimum_rows[item.spec.chamber]):
            raise RuntimeError(
                f"{item.spec.chamber} workbook below minimum row floor: "
                f"observed={count} minimum={minimum_rows[item.spec.chamber]}"
            )
        counts[item.spec.chamber] = count
    if set(counts) != {spec.chamber for spec in WORKBOOKS}:
        raise RuntimeError("validated workbook set does not cover both chambers")
    return {
        "status": "ok",
        "rows_by_chamber": counts,
        "total_rows": sum(counts.values()),
        "minimum_rows_by_chamber": minimum_rows,
        "limits": {
            "max_workbook_bytes": int(max_workbook_bytes),
            "max_uncompressed_bytes": int(max_uncompressed_bytes),
            "max_rows_per_workbook": int(max_rows),
        },
    }


def _manifest_payload(
    acquired: list[AcquiredWorkbook],
    *,
    snapshot_date: str,
) -> dict[str, Any]:
    return {
        "schema_version": "infoelectoral_elected_officials_manifest_v1",
        "source_id": SOURCE_ID,
        "snapshot_date": snapshot_date,
        "official_catalog_url": INFOELECTORAL_ELECTED_CATALOG_URL,
        "identity_assurance": (
            "source_scoped_election_occurrence; cross-election person resolution "
            "not asserted"
        ),
        "workbooks": [
            {
                "chamber": item.spec.chamber,
                "source_url": item.spec.source_url,
                "content_sha256": item.stored.content_sha256,
                "bytes": item.stored.bytes,
                "content_type": item.stored.content_type,
                "raw_path": _display_path(item.stored.path),
                "deduplicated": item.stored.deduplicated,
                "acquisition_mode": item.acquisition_mode,
                "tls_verified": item.tls_verified,
                "etag": item.stored.etag,
                "last_modified": item.stored.last_modified,
            }
            for item in acquired
        ],
    }


def _write_manifest(
    payload: dict[str, Any], *, manifest_root: Path
) -> tuple[Path, str, int]:
    encoded = (
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    snapshot_date = str(payload["snapshot_date"])
    path = Path(manifest_root) / f"{snapshot_date}-{digest[:16]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return path, digest, len(encoded)


def _record_fetches(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    acquired: list[AcquiredWorkbook],
    manifest_path: Path,
    manifest_sha256: str,
    manifest_bytes: int,
) -> str:
    fetched_at = now_utc_iso()
    for item in acquired:
        conn.execute(
            """
            INSERT INTO raw_fetches (
              run_id, source_id, source_url, fetched_at, raw_path,
              content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, content_sha256) DO NOTHING
            """,
            (
                run_id,
                SOURCE_ID,
                item.spec.source_url,
                fetched_at,
                _display_path(item.stored.path),
                item.stored.content_sha256,
                item.stored.content_type or XLSX_CONTENT_TYPE,
                item.stored.bytes,
            ),
        )
    conn.execute(
        """
        INSERT INTO run_fetches (
          run_id, source_id, source_url, fetched_at, raw_path,
          content_sha256, content_type, bytes
        ) VALUES (?, ?, ?, ?, ?, ?, 'application/json', ?)
        ON CONFLICT(run_id) DO UPDATE SET
          fetched_at=excluded.fetched_at,
          raw_path=excluded.raw_path,
          content_sha256=excluded.content_sha256,
          content_type=excluded.content_type,
          bytes=excluded.bytes
        """,
        (
            run_id,
            SOURCE_ID,
            INFOELECTORAL_ELECTED_CATALOG_URL,
            fetched_at,
            _display_path(manifest_path),
            manifest_sha256,
            manifest_bytes,
        ),
    )
    conn.commit()
    return fetched_at


def _record_stream(
    acquired: list[AcquiredWorkbook],
    *,
    max_workbook_bytes: int,
    max_uncompressed_bytes: int,
    max_rows: int,
) -> Any:
    return itertools.chain.from_iterable(
        iter_elected_officials(
            item.stored.path,
            spec=item.spec,
            source_content_sha256=item.stored.content_sha256,
            max_workbook_bytes=max_workbook_bytes,
            max_uncompressed_bytes=max_uncompressed_bytes,
            max_rows=max_rows,
        )
        for item in acquired
    )


def _database_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    foreign_key_violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    return {
        "quick_check": quick_check,
        "foreign_key_violations": foreign_key_violations,
        "ok": quick_check == "ok" and foreign_key_violations == 0,
    }


def _source_drift_report(
    conn: sqlite3.Connection,
    *,
    incoming_counts: dict[str, int],
    max_row_drift_ratio: float,
    allow_large_drift: bool,
) -> dict[str, Any]:
    if not 0 <= float(max_row_drift_ratio) <= 1:
        raise ValueError("max row drift ratio must be between 0 and 1")
    previous_counts = {
        str(row["chamber"]): int(row["rows"])
        for row in conn.execute(
            """
            SELECT chamber, COUNT(*) AS rows
            FROM infoelectoral_elected_officials
            WHERE source_id = ? AND is_present = 1
            GROUP BY chamber
            """,
            (SOURCE_ID,),
        )
    }
    chambers: dict[str, Any] = {}
    within_limit = True
    for spec in WORKBOOKS:
        previous = int(previous_counts.get(spec.chamber, 0))
        incoming = int(incoming_counts.get(spec.chamber, 0))
        delta = incoming - previous
        ratio = None if previous == 0 else abs(delta) / previous
        acceptable = previous == 0 or float(ratio) <= float(max_row_drift_ratio)
        within_limit = within_limit and acceptable
        chambers[spec.chamber] = {
            "previous_present_rows": previous,
            "incoming_rows": incoming,
            "delta_rows": delta,
            "absolute_drift_ratio": None if ratio is None else round(ratio, 9),
            "within_limit": acceptable,
        }
    return {
        "schema_version": "infoelectoral_source_drift_v1",
        "status": "ok" if within_limit else (
            "override" if allow_large_drift else "blocked"
        ),
        "ready": within_limit or bool(allow_large_drift),
        "bootstrap": all(value == 0 for value in previous_counts.values()),
        "max_row_drift_ratio": float(max_row_drift_ratio),
        "allow_large_drift": bool(allow_large_drift),
        "chambers": chambers,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    snapshot_date = dt.date.fromisoformat(args.snapshot_date).isoformat()
    local_files = _local_overrides(list(args.from_file or []))
    if args.ca_bundle and args.insecure_ssl:
        raise ValueError("--ca-bundle and --insecure-ssl are mutually exclusive")
    if int(args.batch_rows) < 1 or int(args.max_rows) < 1:
        raise ValueError("batch and row bounds must be positive")

    reserve_bytes = len(WORKBOOKS) * int(args.max_workbook_bytes)
    storage = _storage_preflight(
        Path(args.store_root),
        min_free_bytes=int(args.min_free_bytes),
        reserve_bytes=reserve_bytes,
    )
    if not storage["ready"]:
        return {
            "schema_version": "infoelectoral_elected_officials_run_v2",
            "status": "blocked_storage",
            "source_id": SOURCE_ID,
            "snapshot_date": snapshot_date,
            "storage_preflight": storage,
            "records_seen": 0,
            "records_loaded": 0,
            "network_attempts": 0,
            "publication_status": "not_published",
        }

    acquired = _acquire(
        store_root=Path(args.store_root),
        timeout=int(args.timeout),
        ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
        insecure_ssl=bool(args.insecure_ssl),
        local_files=local_files,
        max_workbook_bytes=int(args.max_workbook_bytes),
    )
    validation = _validate_workbooks(
        acquired,
        max_workbook_bytes=int(args.max_workbook_bytes),
        max_uncompressed_bytes=int(args.max_uncompressed_bytes),
        max_rows=int(args.max_rows),
        minimum_rows={
            "congreso": int(args.minimum_congreso_rows),
            "senado": int(args.minimum_senado_rows),
        },
    )
    manifest_payload = _manifest_payload(acquired, snapshot_date=snapshot_date)
    manifest_path, manifest_sha256, manifest_bytes = _write_manifest(
        manifest_payload, manifest_root=Path(args.manifest_root)
    )

    conn = open_db(Path(args.db))
    run_id: int | None = None
    try:
        apply_schema(conn, Path(args.schema))
        seed_infoelectoral_sources(conn)
        source_drift = _source_drift_report(
            conn,
            incoming_counts=dict(validation["rows_by_chamber"]),
            max_row_drift_ratio=float(
                getattr(args, "max_row_drift_ratio", 0.15)
            ),
            allow_large_drift=bool(getattr(args, "allow_large_drift", False)),
        )
        if not source_drift["ready"]:
            return {
                "schema_version": "infoelectoral_elected_officials_run_v2",
                "status": "blocked_source_drift",
                "source_id": SOURCE_ID,
                "snapshot_date": snapshot_date,
                "publication_status": "not_published",
                "storage_preflight": storage,
                "transport": {
                    "mode": "local_replay" if local_files else "official_network",
                    "tls_verified": (
                        None if local_files else not bool(args.insecure_ssl)
                    ),
                    "source_specific_insecure_tls": bool(args.insecure_ssl),
                },
                "acquisition": manifest_payload["workbooks"],
                "validation": validation,
                "source_drift": source_drift,
                "records_seen": int(validation["total_rows"]),
                "records_loaded": 0,
            }
        actor_rows_before = int(conn.execute("SELECT COUNT(*) FROM mandates").fetchone()[0])
        run_id = start_run(conn, SOURCE_ID, INFOELECTORAL_ELECTED_CATALOG_URL)
        fetched_at = _record_fetches(
            conn,
            run_id=run_id,
            acquired=acquired,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
            manifest_bytes=manifest_bytes,
        )
        ingest = ingest_elected_officials(
            conn,
            _record_stream(
                acquired,
                max_workbook_bytes=int(args.max_workbook_bytes),
                max_uncompressed_bytes=int(args.max_uncompressed_bytes),
                max_rows=int(args.max_rows),
            ),
            snapshot_date=snapshot_date,
            batch_rows=int(args.batch_rows),
            run_id=run_id,
        )
        source_report = elected_officials_report(conn)
        database = _database_checks(conn)
        actor_rows_after = int(conn.execute("SELECT COUNT(*) FROM mandates").fetchone()[0])
        success = (
            int(ingest["processed"]) == int(validation["total_rows"])
            and int(
                source_report["totals"].get("present_elected_officials") or 0
            )
            == int(validation["total_rows"])
            and source_report["status"] == "ok"
            and database["ok"]
        )
        report = {
            "schema_version": "infoelectoral_elected_officials_run_v2",
            "status": "ok" if success else "failed",
            "source_id": SOURCE_ID,
            "snapshot_date": snapshot_date,
            "official_catalog_url": INFOELECTORAL_ELECTED_CATALOG_URL,
            "publication_status": "local_official_not_published",
            "storage_preflight": storage,
            "transport": {
                "mode": "local_replay" if local_files else "official_network",
                "tls_verified": None if local_files else not bool(args.insecure_ssl),
                "source_specific_insecure_tls": bool(args.insecure_ssl),
            },
            "acquisition": manifest_payload["workbooks"],
            "validation": validation,
            "source_drift": source_drift,
            "ingest": ingest,
            "source_report": source_report,
            "actor_lane": {
                "mandates_before": actor_rows_before,
                "mandates_after": actor_rows_after,
                "net_new_mandates": actor_rows_after - actor_rows_before,
            },
            "database": database,
            "run_id": run_id,
            "raw_manifest_path": _display_path(manifest_path),
            "records_seen": int(validation["total_rows"]),
            "records_loaded": int(ingest["processed"]),
            "peak_rss_mb": round(_peak_rss_mb(), 3),
        }
        finish_run(
            conn,
            run_id,
            "ok" if success else "error",
            f"official elected outcomes {ingest['processed']}/{validation['total_rows']}",
            int(validation["total_rows"]),
            int(ingest["processed"]),
            fetched_at=fetched_at,
            raw_path=Path(_display_path(manifest_path)),
        )
        return report
    except Exception as exc:
        if run_id is not None:
            try:
                finish_run(conn, run_id, "error", _safe_error(exc), 0, 0)
            except sqlite3.Error:
                pass
        raise
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest official Infoelectoral elected-person workbooks"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--snapshot-date", default=dt.date.today().isoformat())
    parser.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    parser.add_argument("--manifest-root", default=str(DEFAULT_MANIFEST_ROOT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--batch-rows", type=int, default=5_000)
    parser.add_argument("--max-workbook-bytes", type=int, default=DEFAULT_MAX_WORKBOOK_BYTES)
    parser.add_argument(
        "--max-uncompressed-bytes",
        type=int,
        default=DEFAULT_MAX_UNCOMPRESSED_BYTES,
    )
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--minimum-congreso-rows", type=int, default=5_000)
    parser.add_argument("--minimum-senado-rows", type=int, default=3_000)
    parser.add_argument("--max-row-drift-ratio", type=float, default=0.15)
    parser.add_argument(
        "--allow-large-drift",
        action="store_true",
        help="Accept a reviewed per-chamber row-count change above the drift limit",
    )
    parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    parser.add_argument("--ca-bundle")
    parser.add_argument("--insecure-ssl", action="store_true")
    parser.add_argument(
        "--from-file",
        action="append",
        default=[],
        metavar="CHAMBER=PATH",
        help="Replay both official workbook files locally; repeat once per chamber",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_path = Path(args.report_out)
    try:
        report = run(args)
    except Exception as exc:
        report = {
            "schema_version": "infoelectoral_elected_officials_run_v2",
            "status": "failed",
            "source_id": SOURCE_ID,
            "snapshot_date": str(args.snapshot_date),
            "publication_status": "not_published",
            "error": _safe_error(exc),
            "peak_rss_mb": round(_peak_rss_mb(), 3),
        }
    _write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
