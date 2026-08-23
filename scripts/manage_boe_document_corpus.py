"""Seed, expand, and inventory a real BOE XML document corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_connectors_es.government.boe_legal import parse_boe_payload
from publicdata_ops import (
    enqueue_work_items,
    ensure_work_queue_schema,
    work_queue_stats,
)
from publicdata_sqlite import open_db, table_exists

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_MANIFEST = Path("etl/data/manifests/boe-document-corpus-lineage.jsonl")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus.json"
)
SUMMARY_PIPELINE = "boe_summary_fetch"
DOCUMENT_PIPELINE = "boe_document_fetch"
SUMMARY_SOURCE_ID = "boe_daily_summaries"
DOCUMENT_SOURCE_ID = "boe_document_xml"
SUMMARY_URL_PREFIX = "https://www.boe.es/datosabiertos/api/boe/sumario/"
BOE_REF_RE = re.compile(r"^BOE-[A-Z]-\d{4}-\d+$", flags=re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BoeCorpusError(RuntimeError):
    """Raised when BOE corpus evidence violates its contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "seed-summaries",
            "requeue-summary-contract-failures",
            "expand-documents",
            "status",
        ),
    )
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument(
        "--summary-date",
        action="append",
        default=[],
        help="Exact official summary date (YYYY-MM-DD); repeat for sparse cohorts",
    )
    parser.add_argument(
        "--boe-id",
        action="append",
        default=[],
        help="Exact BOE document identifier to enqueue from captured summaries",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise BoeCorpusError(f"path escapes repository: {value}") from exc
    return candidate


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_jsonl(path: Path, rows: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise BoeCorpusError(f"{label} must be YYYY-MM-DD") from exc


def date_bounds(
    args: argparse.Namespace, *, required: bool
) -> tuple[date, date] | None:
    start_raw = str(args.start_date or "").strip()
    end_raw = str(args.end_date or "").strip()
    if not start_raw and not end_raw and not required:
        return None
    if not start_raw or not end_raw:
        raise BoeCorpusError("start-date and end-date must be provided together")
    start = parse_iso_date(start_raw, "start-date")
    end = parse_iso_date(end_raw, "end-date")
    if start > end:
        raise BoeCorpusError("start-date must not exceed end-date")
    return start, end


def dates_inclusive(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def exact_summary_dates(args: argparse.Namespace) -> tuple[date, ...]:
    raw_dates = tuple(str(value or "").strip() for value in args.summary_date)
    if not raw_dates:
        return ()
    if str(args.start_date or "").strip() or str(args.end_date or "").strip():
        raise BoeCorpusError(
            "summary-date cannot be combined with start-date or end-date"
        )
    return tuple(sorted({parse_iso_date(value, "summary-date") for value in raw_dates}))


def selected_boe_ids(args: argparse.Namespace) -> tuple[str, ...]:
    selected = tuple(
        sorted({str(value or "").strip().upper() for value in args.boe_id})
    )
    invalid = [value for value in selected if not BOE_REF_RE.fullmatch(value)]
    if invalid:
        raise BoeCorpusError(f"invalid BOE document identifier: {invalid[0]}")
    return selected


def require_tables(connection: sqlite3.Connection) -> None:
    required = {
        "document_fetches",
        "source_records",
        "sources",
        "text_documents",
    }
    missing = sorted(table for table in required if not table_exists(connection, table))
    if missing:
        raise BoeCorpusError(f"required tables missing: {', '.join(missing)}")
    ensure_work_queue_schema(connection)


def official_document_identity(url: str) -> str:
    parsed = urlparse(url)
    ids = parse_qs(parsed.query).get("id") or []
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.boe.es"
        or parsed.path != "/diario_boe/xml.php"
        or len(ids) != 1
        or not BOE_REF_RE.fullmatch(ids[0])
    ):
        raise BoeCorpusError(f"invalid BOE XML source URL: {url}")
    return ids[0].upper()


def seed_summaries(
    connection: sqlite3.Connection,
    *,
    start: date,
    end: date,
    limit: int,
    batch_size: int,
    max_attempts: int,
) -> dict[str, Any]:
    selected_dates = dates_inclusive(start, end)
    if limit > 0:
        selected_dates = selected_dates[:limit]
    items = (
        {
            "item_key": f"{SUMMARY_URL_PREFIX}{day:%Y%m%d}",
            "partition_key": f"{day:%Y-%m}",
            "priority": int(day.strftime("%Y%m%d")),
            "payload": {
                "doc_url": f"{SUMMARY_URL_PREFIX}{day:%Y%m%d}",
                "document_source_id": SUMMARY_SOURCE_ID,
                "publication_date_requested": day.isoformat(),
                "official_public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
            },
            "max_attempts": max_attempts,
        }
        for day in selected_dates
    )
    result = enqueue_work_items(
        connection,
        pipeline_id=SUMMARY_PIPELINE,
        items=items,
        batch_size=batch_size,
    )
    return {
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "summary_dates": [day.isoformat() for day in selected_dates],
        "dates_selected": len(selected_dates),
        "enqueue": result,
        "queue": work_queue_stats(connection, pipeline_id=SUMMARY_PIPELINE),
    }


def seed_exact_summaries(
    connection: sqlite3.Connection,
    *,
    summary_dates: tuple[date, ...],
    limit: int,
    batch_size: int,
    max_attempts: int,
) -> dict[str, Any]:
    if not summary_dates:
        raise BoeCorpusError("at least one summary-date is required")
    selected_dates = list(summary_dates[:limit] if limit > 0 else summary_dates)
    items = (
        {
            "item_key": f"{SUMMARY_URL_PREFIX}{day:%Y%m%d}",
            "partition_key": f"{day:%Y-%m}",
            "priority": int(day.strftime("%Y%m%d")),
            "payload": {
                "doc_url": f"{SUMMARY_URL_PREFIX}{day:%Y%m%d}",
                "document_source_id": SUMMARY_SOURCE_ID,
                "publication_date_requested": day.isoformat(),
                "official_public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
            },
            "max_attempts": max_attempts,
        }
        for day in selected_dates
    )
    result = enqueue_work_items(
        connection,
        pipeline_id=SUMMARY_PIPELINE,
        items=items,
        batch_size=batch_size,
    )
    return {
        "date_range": None,
        "summary_dates": [day.isoformat() for day in selected_dates],
        "dates_selected": len(selected_dates),
        "enqueue": result,
        "queue": work_queue_stats(connection, pipeline_id=SUMMARY_PIPELINE),
    }


def source_record_metadata(raw_payload: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw_payload or "{}"))
    except json.JSONDecodeError as exc:
        raise BoeCorpusError("BOE source_record raw_payload is invalid") from exc
    if not isinstance(parsed, dict):
        raise BoeCorpusError("BOE source_record raw_payload is not an object")
    return parsed


def iter_summary_rows(
    connection: sqlite3.Connection,
    *,
    bounds: tuple[date, date] | None,
    limit: int,
    summary_dates: tuple[date, ...] = (),
) -> list[sqlite3.Row]:
    params: list[Any] = [SUMMARY_SOURCE_ID]
    filters = ["t.source_id = ?"]
    if summary_dates:
        marks = ",".join("?" for _ in summary_dates)
        filters.append(f"t.source_url IN ({marks})")
        params.extend(
            f"{SUMMARY_URL_PREFIX}{summary_date:%Y%m%d}"
            for summary_date in summary_dates
        )
    elif bounds is not None:
        start, end = bounds
        filters.append("t.source_url >= ? AND t.source_url <= ?")
        params.extend(
            [
                f"{SUMMARY_URL_PREFIX}{start:%Y%m%d}",
                f"{SUMMARY_URL_PREFIX}{end:%Y%m%d}",
            ]
        )
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(limit)
    return connection.execute(
        f"""
        SELECT
          t.source_url,
          t.fetched_at,
          t.content_type,
          t.content_sha256,
          t.bytes,
          t.raw_path,
          s.raw_payload
        FROM text_documents AS t
        JOIN source_records AS s ON s.source_record_pk = t.source_record_pk
        WHERE {" AND ".join(filters)}
        ORDER BY t.source_url
        {limit_sql}
        """,
        params,
    ).fetchall()


def expand_documents(
    connection: sqlite3.Connection,
    *,
    bounds: tuple[date, date] | None,
    summary_dates: tuple[date, ...],
    boe_ids: tuple[str, ...],
    limit: int,
    batch_size: int,
    max_attempts: int,
) -> dict[str, Any]:
    summary_rows = iter_summary_rows(
        connection,
        bounds=bounds,
        summary_dates=summary_dates,
        limit=limit,
    )
    requested_boe_ids = set(boe_ids)
    selected_counts: dict[str, int] = {}
    counters = {
        "summaries_parsed": 0,
        "documents_discovered": 0,
        "documents_selected": 0,
        "summary_bytes_verified": 0,
    }

    def items() -> Any:
        for summary in summary_rows:
            summary_url = str(summary["source_url"])
            summary_path = repo_path(str(summary["raw_path"] or ""))
            expected_sha = str(summary["content_sha256"] or "").lower()
            expected_bytes = int(summary["bytes"] or -1)
            if (
                not summary_path.is_file()
                or not SHA256_RE.fullmatch(expected_sha)
                or summary_path.stat().st_size != expected_bytes
                or sha256_file(summary_path) != expected_sha
            ):
                raise BoeCorpusError(
                    f"summary capture drifted: {display_path(summary_path)}"
                )
            source_metadata = source_record_metadata(summary["raw_payload"])
            queue_payload = source_metadata.get("queue_payload") or {}
            if (
                not isinstance(queue_payload, dict)
                or queue_payload.get("synthetic_or_mock_records_counted") is not False
                or queue_payload.get(
                    "official_public_domain_personal_information_retained"
                )
                is not True
            ):
                raise BoeCorpusError(
                    "summary source metadata violates real-data policy"
                )
            records = parse_boe_payload(
                summary_path.read_bytes(),
                feed_url=summary_url,
                content_type=str(summary["content_type"] or "application/json"),
            )
            counters["summaries_parsed"] += 1
            counters["summary_bytes_verified"] += expected_bytes
            requested_date = str(queue_payload.get("publication_date_requested") or "")
            for record in records:
                url = str(record.get("url_xml") or "").strip()
                boe_ref = str(record.get("boe_ref") or "").strip().upper()
                if not url or official_document_identity(url) != boe_ref:
                    raise BoeCorpusError(
                        f"summary contains invalid XML relation: {summary_url}"
                    )
                if str(record.get("publication_date") or "") != requested_date:
                    raise BoeCorpusError(
                        f"summary publication date mismatch: {summary_url}"
                    )
                counters["documents_discovered"] += 1
                if requested_boe_ids and boe_ref not in requested_boe_ids:
                    continue
                selected_counts[boe_ref] = selected_counts.get(boe_ref, 0) + 1
                counters["documents_selected"] += 1
                yield {
                    "item_key": url,
                    "partition_key": requested_date[:7],
                    "priority": int(requested_date.replace("-", "")),
                    "payload": {
                        "doc_url": url,
                        "document_source_id": DOCUMENT_SOURCE_ID,
                        "summary_source_url": summary_url,
                        "summary_content_sha256": expected_sha,
                        "boe_record": record,
                        "official_public_domain_personal_information_retained": True,
                        "synthetic_or_mock_records_counted": False,
                    },
                    "max_attempts": max_attempts,
                }

    selected_items: Any = items()
    if requested_boe_ids:
        selected_items = list(selected_items)
        missing = sorted(requested_boe_ids - set(selected_counts))
        duplicates = sorted(
            boe_id for boe_id, count in selected_counts.items() if count != 1
        )
        if missing:
            raise BoeCorpusError(
                "requested BOE documents missing from captured summaries: "
                + ", ".join(missing)
            )
        if duplicates:
            raise BoeCorpusError(
                "requested BOE documents occur more than once in summaries: "
                + ", ".join(duplicates)
            )
    result = enqueue_work_items(
        connection,
        pipeline_id=DOCUMENT_PIPELINE,
        items=selected_items,
        batch_size=batch_size,
    )
    return {
        **counters,
        "requested_boe_ids": sorted(requested_boe_ids),
        "selected_boe_ids": sorted(selected_counts),
        "enqueue": result,
        "queue": work_queue_stats(connection, pipeline_id=DOCUMENT_PIPELINE),
    }


def requeue_summary_contract_failures(
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    error = "boe_summary_payload_contract_mismatch"
    work_item_ids = [
        int(row["work_item_id"])
        for row in connection.execute(
            """
            SELECT work_item_id
            FROM pipeline_work_items
            WHERE pipeline_id = ? AND state = 'dead' AND last_error = ?
            ORDER BY work_item_id
            """,
            (SUMMARY_PIPELINE, error),
        )
    ]
    if work_item_ids:
        marks = ",".join("?" for _ in work_item_ids)
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        connection.execute(
            f"""
            UPDATE pipeline_work_items
            SET state = 'pending', available_at = ?, lease_owner = NULL,
                lease_expires_at = NULL, completed_at = NULL, last_error = NULL,
                updated_at = ?
            WHERE work_item_id IN ({marks}) AND state = 'dead'
            """,
            (now, now, *work_item_ids),
        )
        connection.commit()
    return {
        "error_contract": error,
        "items_requeued": len(work_item_ids),
        "queue": work_queue_stats(connection, pipeline_id=SUMMARY_PIPELINE),
    }


def export_manifest(
    connection: sqlite3.Connection, *, output_path: Path
) -> dict[str, Any]:
    summary_captures: dict[str, dict[str, Any]] = {}
    for summary in iter_summary_rows(
        connection,
        bounds=None,
        summary_dates=(),
        limit=0,
    ):
        summary_url = str(summary["source_url"])
        summary_path = repo_path(str(summary["raw_path"] or ""))
        summary_sha256 = str(summary["content_sha256"] or "").lower()
        summary_bytes = int(summary["bytes"] or -1)
        if (
            not summary_path.is_file()
            or not SHA256_RE.fullmatch(summary_sha256)
            or summary_path.stat().st_size != summary_bytes
            or sha256_file(summary_path) != summary_sha256
        ):
            raise BoeCorpusError(
                f"BOE summary capture drifted: {display_path(summary_path)}"
            )
        summary_captures[summary_url] = {
            "source_url": summary_url,
            "fetched_at": summary["fetched_at"],
            "content_type": summary["content_type"],
            "path": summary_path.relative_to(REPO_ROOT).as_posix(),
            "bytes": summary_bytes,
            "sha256": summary_sha256,
        }
    query = connection.execute(
        """
        SELECT
          t.source_url,
          t.fetched_at,
          t.content_type,
          t.content_sha256,
          t.bytes,
          t.raw_path,
          s.raw_payload
        FROM text_documents AS t
        JOIN source_records AS s ON s.source_record_pk = t.source_record_pk
        WHERE t.source_id = ?
        ORDER BY t.source_url
        """,
        (DOCUMENT_SOURCE_ID,),
    )
    validated_rows = 0
    referenced_summary_urls: set[str] = set()

    def manifest_rows() -> Any:
        nonlocal validated_rows
        for row in query:
            source_url = str(row["source_url"])
            boe_ref = official_document_identity(source_url)
            raw_path = repo_path(str(row["raw_path"] or ""))
            sha256 = str(row["content_sha256"] or "").lower()
            byte_count = int(row["bytes"] or -1)
            if (
                not raw_path.is_file()
                or not SHA256_RE.fullmatch(sha256)
                or raw_path.stat().st_size != byte_count
                or sha256_file(raw_path) != sha256
            ):
                raise BoeCorpusError(
                    f"BOE document capture drifted: {display_path(raw_path)}"
                )
            metadata = source_record_metadata(row["raw_payload"])
            queue_payload = metadata.get("queue_payload") or {}
            boe_record = queue_payload.get("boe_record") or {}
            summary_url = str(queue_payload.get("summary_source_url") or "")
            summary_capture = summary_captures.get(summary_url)
            if (
                not isinstance(boe_record, dict)
                or str(boe_record.get("boe_ref") or "").upper() != boe_ref
                or summary_capture is None
                or queue_payload.get("summary_content_sha256")
                != summary_capture["sha256"]
                or queue_payload.get("synthetic_or_mock_records_counted") is not False
                or queue_payload.get(
                    "official_public_domain_personal_information_retained"
                )
                is not True
            ):
                raise BoeCorpusError(f"BOE source metadata drifted: {source_url}")
            validated_rows += 1
            referenced_summary_urls.add(summary_url)
            relative = raw_path.relative_to(REPO_ROOT).as_posix()
            yield {
                "schema_version": "boe_document_corpus_lineage_v2",
                "capture_status": "checksum_capture_present",
                "capture": {
                    "path": relative,
                    "bytes": byte_count,
                    "sha256": sha256,
                },
                "source_id": DOCUMENT_SOURCE_ID,
                "source_url": source_url,
                "fetched_at": row["fetched_at"],
                "content_type": row["content_type"],
                "boe_record": boe_record,
                "source_summary": summary_capture,
                "official_public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "remote_mutation_performed": False,
            }

    atomic_write_jsonl(output_path, manifest_rows())
    totals = source_totals(connection, DOCUMENT_SOURCE_ID)
    if validated_rows != totals["rows"]:
        raise BoeCorpusError("BOE manifest row count drifted during export")
    return {
        "path": display_path(output_path),
        "rows": validated_rows,
        "distinct_content_objects": totals["distinct_content_objects"],
        "distinct_summary_captures": len(referenced_summary_urls),
        "available_summary_captures": len(summary_captures),
        "document_bytes": totals["bytes"],
        "bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
    }


def source_totals(connection: sqlite3.Connection, source_id: str) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS rows, COUNT(DISTINCT content_sha256) AS hashes,
               COALESCE(SUM(bytes), 0) AS bytes
        FROM text_documents WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    return {
        "rows": int(row["rows"]),
        "distinct_content_objects": int(row["hashes"]),
        "bytes": int(row["bytes"]),
    }


def build_report(
    connection: sqlite3.Connection,
    *,
    mode: str,
    operation: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    summary_queue = work_queue_stats(connection, pipeline_id=SUMMARY_PIPELINE)
    document_queue = work_queue_stats(connection, pipeline_id=DOCUMENT_PIPELINE)
    invalid_summary_dead_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM pipeline_work_items AS w
        LEFT JOIN document_fetches AS d ON d.doc_url = w.item_key
        WHERE w.pipeline_id = ? AND w.state = 'dead'
          AND COALESCE(d.last_http_status, 0) != 404
        """,
        (SUMMARY_PIPELINE,),
    ).fetchone()[0]
    checks = {
        "manifest_matches_document_rows": (
            manifest["rows"] == source_totals(connection, DOCUMENT_SOURCE_ID)["rows"]
        ),
        "manifest_references_every_summary_capture": (
            mode != "status"
            or manifest["distinct_summary_captures"]
            == source_totals(connection, SUMMARY_SOURCE_ID)["rows"]
        ),
        "summary_queue_terminal": (
            mode not in {"expand-documents", "status"}
            or summary_queue["unfinished_total"] == 0
        ),
        "summary_dead_rows_are_official_404": invalid_summary_dead_rows == 0,
        "document_queue_complete_without_failures": (
            mode != "status"
            or (
                document_queue["unfinished_total"] == 0
                and document_queue["state_counts"]["dead"] == 0
                and document_queue["state_counts"]["succeeded"] == manifest["rows"]
            )
        ),
        "all_captures_checksum_verified": True,
        "public_domain_personal_information_retained": True,
        "no_synthetic_or_mock_records_counted": True,
        "no_remote_mutation_performed": True,
    }
    return {
        "schema_version": "boe_document_corpus_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "mode": mode,
        "policy": {
            "official_boe_https_only": True,
            "exact_summary_to_document_relation_required": True,
            "checksum_and_byte_verification_required": True,
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "remote_mutation_performed": False,
        },
        "operation": operation,
        "summaries": source_totals(connection, SUMMARY_SOURCE_ID),
        "documents": source_totals(connection, DOCUMENT_SOURCE_ID),
        "queues": {
            "summaries": summary_queue,
            "documents": document_queue,
        },
        "manifest": manifest,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit < 0 or args.batch_size < 1 or args.max_attempts < 1:
        print(
            "ERROR: limit must be nonnegative; batch-size/max-attempts must be positive"
        )
        return 2
    try:
        database_path = repo_path(args.db)
        if not database_path.is_file():
            raise BoeCorpusError(f"database missing: {display_path(database_path)}")
        connection = open_db(database_path)
        try:
            require_tables(connection)
            exact_dates = exact_summary_dates(args)
            exact_boe_ids = selected_boe_ids(args)
            if args.mode == "seed-summaries":
                if exact_boe_ids:
                    raise BoeCorpusError("boe-id is only valid with expand-documents")
                if exact_dates:
                    operation = seed_exact_summaries(
                        connection,
                        summary_dates=exact_dates,
                        limit=args.limit,
                        batch_size=args.batch_size,
                        max_attempts=args.max_attempts,
                    )
                else:
                    bounds = date_bounds(args, required=True)
                    if bounds is None:
                        raise BoeCorpusError("date bounds are required")
                    operation = seed_summaries(
                        connection,
                        start=bounds[0],
                        end=bounds[1],
                        limit=args.limit,
                        batch_size=args.batch_size,
                        max_attempts=args.max_attempts,
                    )
            elif args.mode == "requeue-summary-contract-failures":
                if exact_dates or exact_boe_ids:
                    raise BoeCorpusError(
                        "summary-date and boe-id are not valid when requeueing"
                    )
                operation = requeue_summary_contract_failures(connection)
            elif args.mode == "expand-documents":
                operation = expand_documents(
                    connection,
                    bounds=(None if exact_dates else date_bounds(args, required=False)),
                    summary_dates=exact_dates,
                    boe_ids=exact_boe_ids,
                    limit=args.limit,
                    batch_size=args.batch_size,
                    max_attempts=args.max_attempts,
                )
            else:
                if exact_dates or exact_boe_ids:
                    raise BoeCorpusError(
                        "summary-date and boe-id are not valid in status mode"
                    )
                operation = {"status_only": True}
            manifest = export_manifest(
                connection, output_path=repo_path(args.manifest_out)
            )
            report = build_report(
                connection,
                mode=args.mode,
                operation=operation,
                manifest=manifest,
            )
        finally:
            connection.close()
        atomic_write_text(
            repo_path(args.report_out),
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        )
    except (BoeCorpusError, OSError, sqlite3.DatabaseError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.enforce and not all(report["checks"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
