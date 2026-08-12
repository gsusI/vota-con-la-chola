#!/usr/bin/env python3
"""Extract queued documents in bounded parallel batches and persist full text."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.util import now_utc_iso  # noqa: E402
from publicdata_docs.extraction import DocumentExtraction, extract_document_path  # noqa: E402
from publicdata_ops import (  # noqa: E402
    claim_work_items,
    collect_futures_with_heartbeat,
    complete_work_items,
    ensure_work_queue_schema,
    fail_work_items,
    work_queue_stats,
)
from publicdata_sqlite import open_db, table_columns, table_exists  # noqa: E402


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_TEXT_ROOT = Path("etl/data/derived/text")


@dataclass(frozen=True)
class ExtractionOutcome:
    work_item_id: int
    item_key: str
    payload: dict[str, Any]
    extraction: DocumentExtraction | None
    text_sha256: str | None
    text_path: Path | None
    error: str | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run durable text extraction queue")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--text-root", default=str(DEFAULT_TEXT_ROOT))
    parser.add_argument("--pipeline-id", default="text_extraction")
    parser.add_argument("--worker-id", default="text-extraction-worker")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--claim-size", type=int, default=16)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--max-input-bytes", type=int, default=50 * 1024 * 1024)
    parser.add_argument("--max-text-chars", type=int, default=2_000_000)
    parser.add_argument("--excerpt-chars", type=int, default=4_000)
    parser.add_argument("--retry-delay-seconds", type=int, default=60)
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def _store_text(text: str, *, text_root: Path) -> tuple[str, Path]:
    encoded = text.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    final_path = Path(text_root) / digest[:2] / digest[2:4] / f"{digest}.txt.gz"
    if final_path.is_file():
        return digest, final_path
    partial_root = Path(text_root) / ".partial"
    partial_root.mkdir(parents=True, exist_ok=True)
    partial_path = partial_root / f"{uuid.uuid4().hex}.part"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with partial_path.open("xb") as raw_handle:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as zipped:
                zipped.write(encoded)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        if final_path.exists():
            partial_path.unlink(missing_ok=True)
        else:
            os.replace(partial_path, final_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    return digest, final_path


def _extract_item(
    item: Mapping[str, object],
    *,
    text_root: Path,
    max_input_bytes: int,
    max_text_chars: int,
) -> ExtractionOutcome:
    work_item_id = int(item["work_item_id"])
    item_key = str(item["item_key"])
    payload = dict(item.get("payload") or {})
    raw_path = Path(str(payload.get("raw_path") or ""))
    try:
        extraction = extract_document_path(
            raw_path,
            content_type=str(payload.get("content_type") or ""),
            max_input_bytes=max_input_bytes,
            max_text_chars=max_text_chars,
        )
        if not extraction.text:
            raise RuntimeError("empty_extracted_text")
        text_sha256, text_path = _store_text(extraction.text, text_root=text_root)
        return ExtractionOutcome(
            work_item_id,
            item_key,
            payload,
            extraction,
            text_sha256,
            text_path,
            None,
        )
    except Exception as exc:  # noqa: BLE001
        return ExtractionOutcome(
            work_item_id,
            item_key,
            payload,
            None,
            None,
            None,
            f"{type(exc).__name__}: {exc}"[:2_000],
        )


def _ensure_text_columns(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "text_documents"):
        raise RuntimeError("required table missing: text_documents")
    required = {
        "text_path": "text_path TEXT",
        "text_sha256": "text_sha256 TEXT",
        "text_extraction_method": "text_extraction_method TEXT",
        "text_extracted_at": "text_extracted_at TEXT",
        "text_truncated": "text_truncated INTEGER NOT NULL DEFAULT 0",
    }
    existing = table_columns(conn, "text_documents")
    for column, definition in required.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE text_documents ADD COLUMN {definition}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_text_documents_content_sha256 ON text_documents(content_sha256)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_text_documents_text_sha256 ON text_documents(text_sha256)"
    )
    conn.commit()


def persist_extraction_outcomes(
    conn: sqlite3.Connection,
    *,
    successes: list[ExtractionOutcome],
    excerpt_chars: int,
) -> int:
    now_iso = now_utc_iso()
    updated = 0
    for outcome in successes:
        extraction = outcome.extraction
        if extraction is None or outcome.text_path is None or outcome.text_sha256 is None:
            continue
        content_sha256 = str(outcome.payload.get("content_sha256") or "").strip()
        if content_sha256:
            cursor = conn.execute(
                """
                UPDATE text_documents
                SET text_excerpt = ?,
                    text_chars = ?,
                    text_path = ?,
                    text_sha256 = ?,
                    text_extraction_method = ?,
                    text_extracted_at = ?,
                    text_truncated = ?,
                    updated_at = ?
                WHERE content_sha256 = ?
                """,
                (
                    extraction.text[: int(excerpt_chars)],
                    int(extraction.text_chars),
                    str(outcome.text_path),
                    outcome.text_sha256,
                    extraction.method,
                    now_iso,
                    1 if extraction.truncated else 0,
                    now_iso,
                    content_sha256,
                ),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE text_documents
                SET text_excerpt = ?,
                    text_chars = ?,
                    text_path = ?,
                    text_sha256 = ?,
                    text_extraction_method = ?,
                    text_extracted_at = ?,
                    text_truncated = ?,
                    updated_at = ?
                WHERE text_document_id = ?
                """,
                (
                    extraction.text[: int(excerpt_chars)],
                    int(extraction.text_chars),
                    str(outcome.text_path),
                    outcome.text_sha256,
                    extraction.method,
                    now_iso,
                    1 if extraction.truncated else 0,
                    now_iso,
                    int(outcome.payload.get("text_document_id") or 0),
                ),
            )
        updated += max(0, int(cursor.rowcount))
    conn.commit()
    return updated


def process_text_extraction_queue(
    conn: sqlite3.Connection,
    *,
    text_root: Path,
    pipeline_id: str,
    worker_id: str,
    workers: int,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    max_input_bytes: int,
    max_text_chars: int,
    excerpt_chars: int,
    retry_delay_seconds: int,
) -> dict[str, Any]:
    ensure_work_queue_schema(conn)
    _ensure_text_columns(conn)
    totals = {
        "claimed": 0,
        "succeeded": 0,
        "document_rows_updated": 0,
        "retried": 0,
        "dead": 0,
    }
    failure_samples: list[dict[str, object]] = []

    while max_items <= 0 or totals["claimed"] < max_items:
        remaining = claim_size if max_items <= 0 else min(claim_size, max_items - totals["claimed"])
        if remaining <= 0:
            break
        claimed = claim_work_items(
            conn,
            pipeline_id=pipeline_id,
            worker_id=worker_id,
            limit=remaining,
            lease_seconds=lease_seconds,
        )
        if not claimed:
            break
        totals["claimed"] += len(claimed)
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
            futures = {
                executor.submit(
                    _extract_item,
                    item,
                    text_root=text_root,
                    max_input_bytes=max_input_bytes,
                    max_text_chars=max_text_chars,
                ): int(item["work_item_id"])
                for item in claimed
            }
            outcomes = collect_futures_with_heartbeat(
                conn,
                futures=futures,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
            )

        successes = [outcome for outcome in outcomes if outcome.extraction is not None]
        failures = [outcome for outcome in outcomes if outcome.extraction is None]
        totals["document_rows_updated"] += persist_extraction_outcomes(
            conn,
            successes=successes,
            excerpt_chars=excerpt_chars,
        )
        if successes:
            totals["succeeded"] += complete_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id for outcome in successes],
            )
        for outcome in failures:
            failed = fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id],
                error=str(outcome.error or "extraction_failed"),
                retry_delay_seconds=retry_delay_seconds,
            )
            totals["retried"] += int(failed["retry_total"])
            totals["dead"] += int(failed["dead_total"])
            if len(failure_samples) < 20:
                failure_samples.append(
                    {"item_key": outcome.item_key, "error": outcome.error}
                )

    return {
        "schema_version": "text_extraction_queue_run_v1",
        "status": "ok" if totals["dead"] == 0 else "partial",
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "workers": int(workers),
        "totals": totals,
        "queue": work_queue_stats(conn, pipeline_id=pipeline_id),
        "failure_samples": failure_samples,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return path.name


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {_display_path(db_path)}", file=sys.stderr)
        return 2
    positive = (
        int(args.workers),
        int(args.claim_size),
        int(args.lease_seconds),
        int(args.max_input_bytes),
        int(args.max_text_chars),
        int(args.excerpt_chars),
    )
    if any(value < 1 for value in positive) or int(args.max_items) < 0:
        print("ERROR: worker/size/lease values must be positive", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        report = process_text_extraction_queue(
            conn,
            text_root=Path(args.text_root),
            pipeline_id=str(args.pipeline_id),
            worker_id=str(args.worker_id),
            workers=int(args.workers),
            claim_size=min(10_000, int(args.claim_size)),
            max_items=int(args.max_items),
            lease_seconds=int(args.lease_seconds),
            max_input_bytes=int(args.max_input_bytes),
            max_text_chars=int(args.max_text_chars),
            excerpt_chars=int(args.excerpt_chars),
            retry_delay_seconds=max(0, int(args.retry_delay_seconds)),
        )
    finally:
        conn.close()

    if str(args.report_out or "").strip():
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
