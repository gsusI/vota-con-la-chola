#!/usr/bin/env python3
"""Run bounded concurrent document downloads from the durable work queue."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import urllib.error
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.blobstore import (  # noqa: E402
    StoredBlob,
    download_to_content_addressed_store,
)
from publicdata_core.util import now_utc_iso, stable_json  # noqa: E402
from publicdata_ops import (  # noqa: E402
    claim_work_items,
    collect_futures_with_heartbeat,
    complete_work_items,
    ensure_work_queue_schema,
    fail_work_items,
    work_queue_stats,
)
from publicdata_sqlite import (  # noqa: E402
    open_db,
    table_exists,
    upsert_source_records_with_content_sha256,
)

DOCUMENT_SOURCE_ID = "parl_initiative_docs"
DOCUMENT_SOURCES = {
    DOCUMENT_SOURCE_ID: (
        "Documentos oficiales de iniciativas parlamentarias",
        "manifest://parl_initiative_docs",
    ),
    "placsp_contract_docs": (
        "Documentos oficiales de contratacion PLACSP",
        "manifest://placsp_contract_docs",
    ),
}
DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_RAW_ROOT = Path("etl/data/raw/text_documents/parl_initiative_docs")


@dataclass(frozen=True)
class DownloadOutcome:
    work_item_id: int
    item_key: str
    payload: dict[str, Any]
    stored: StoredBlob | None
    error: str | None
    http_status: int | None
    failure_class: str | None
    retryable: bool


class HostLimiter:
    def __init__(self, per_host_workers: int, hard_failure_threshold: int = 3) -> None:
        self._per_host_workers = max(1, int(per_host_workers))
        self._hard_failure_threshold = max(1, int(hard_failure_threshold))
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._hard_failures: dict[str, int] = {}
        self._open_circuits: set[str] = set()

    @staticmethod
    def _host(url: str) -> str:
        return str(urlparse(url).hostname or "local").lower()

    @classmethod
    def _circuit_key(cls, url: str) -> str:
        parsed = urlparse(url)
        host = cls._host(url)
        parts = [part for part in parsed.path.split("/") if part]
        route = "/".join(parts[:2]) if parts else "root"
        query = parse_qs(parsed.query)
        legislature = str((query.get("legis") or [""])[0]).strip()
        if not legislature and parts and parts[0].lower().startswith("legis"):
            legislature = parts[0][5:]
        legislature_key = f"legis:{legislature}" if legislature else "legis:unknown"
        return f"{host}|{legislature_key}|{route}"

    def for_url(self, url: str) -> threading.BoundedSemaphore:
        host = self._host(url)
        with self._lock:
            semaphore = self._semaphores.get(host)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(self._per_host_workers)
                self._semaphores[host] = semaphore
            return semaphore

    def is_open(self, url: str) -> bool:
        with self._lock:
            return self._circuit_key(url) in self._open_circuits

    def record_status(self, url: str, http_status: int | None) -> None:
        circuit_key = self._circuit_key(url)
        with self._lock:
            if http_status in {401, 403, 429} or (
                http_status is not None and 500 <= http_status <= 599
            ):
                failures = self._hard_failures.get(circuit_key, 0) + 1
                self._hard_failures[circuit_key] = failures
                if failures >= self._hard_failure_threshold:
                    self._open_circuits.add(circuit_key)
            elif http_status is not None and 200 <= http_status < 400:
                self._hard_failures.pop(circuit_key, None)

    def opened_hosts(self) -> list[str]:
        with self._lock:
            return sorted({key.split("|", 1)[0] for key in self._open_circuits})

    def opened_circuits(self) -> list[str]:
        with self._lock:
            return sorted(self._open_circuits)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run streaming document fetch queue")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--pipeline-id", default="document_fetch")
    parser.add_argument("--worker-id", default="document-fetch-worker")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--per-host-workers", type=int, default=2)
    parser.add_argument("--host-hard-failure-threshold", type=int, default=3)
    parser.add_argument("--claim-size", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=0, help="0 processes until no ready work")
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--download-attempts", type=int, default=3)
    parser.add_argument("--ca-bundle", default="")
    parser.add_argument("--retry-delay-seconds", type=int, default=60)
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def _http_status(exc: BaseException) -> int | None:
    if isinstance(exc, urllib.error.HTTPError):
        return int(exc.code)
    value = getattr(exc, "status", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _classify_download_failure(
    *, http_status: int | None, error: str
) -> tuple[str, bool]:
    normalized = str(error or "").lower()
    if "host_circuit_open" in normalized:
        return "host_circuit_open", True
    if "max_bytes" in normalized:
        return "oversize", False
    if "missing_doc_url" in normalized:
        return "invalid_work_item", False
    if http_status in {400, 404, 410, 413, 414, 415, 422}:
        return "not_fetchable", False
    if http_status in {401, 403}:
        return "access_blocked", True
    if http_status == 429:
        return "rate_limited", True
    if http_status is not None and 500 <= http_status <= 599:
        return "upstream_server_error", True
    if "timeout" in normalized:
        return "timeout", True
    if "urlerror" in normalized or "connection" in normalized:
        return "network", True
    return "download_error", True


def _download_item(
    item: Mapping[str, object],
    *,
    raw_root: Path,
    timeout: int,
    max_bytes: int,
    download_attempts: int,
    host_limiter: HostLimiter,
    ca_bundle: Path | None = None,
) -> DownloadOutcome:
    work_item_id = int(item["work_item_id"])
    item_key = str(item["item_key"])
    payload = dict(item.get("payload") or {})
    url = str(payload.get("doc_url") or item_key).strip()
    if not url:
        return DownloadOutcome(
            work_item_id,
            item_key,
            payload,
            None,
            "missing_doc_url",
            None,
            "invalid_work_item",
            False,
        )
    try:
        with host_limiter.for_url(url):
            if host_limiter.is_open(url):
                return DownloadOutcome(
                    work_item_id,
                    item_key,
                    payload,
                    None,
                    "host_circuit_open",
                    None,
                    "host_circuit_open",
                    True,
                )
            stored = download_to_content_addressed_store(
                url,
                store_root=raw_root,
                timeout=timeout,
                max_bytes=max_bytes,
                max_attempts=download_attempts,
                ca_bundle=ca_bundle,
            )
            host_limiter.record_status(url, 200)
        return DownloadOutcome(
            work_item_id, item_key, payload, stored, None, 200, None, False
        )
    except Exception as exc:  # noqa: BLE001
        http_status = _http_status(exc)
        error = f"{type(exc).__name__}: {exc}"[:2_000]
        failure_class, retryable = _classify_download_failure(
            http_status=http_status,
            error=error,
        )
        host_limiter.record_status(url, http_status)
        return DownloadOutcome(
            work_item_id,
            item_key,
            payload,
            None,
            error,
            http_status,
            failure_class,
            retryable,
        )


def _ensure_required_tables(conn: sqlite3.Connection) -> None:
    required = {
        "document_fetches",
        "source_records",
        "sources",
        "text_documents",
    }
    missing = sorted(table for table in required if not table_exists(conn, table))
    if missing:
        raise RuntimeError(f"required tables missing: {', '.join(missing)}")


def _document_source_id(outcome: DownloadOutcome) -> str:
    source_id = str(outcome.payload.get("document_source_id") or DOCUMENT_SOURCE_ID)
    if source_id not in DOCUMENT_SOURCES:
        raise RuntimeError(f"unsupported document source: {source_id}")
    return source_id


def _ensure_document_source(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    now_iso: str,
) -> None:
    if source_id not in DOCUMENT_SOURCES:
        raise RuntimeError(f"unsupported document source: {source_id}")
    name, default_url = DOCUMENT_SOURCES[source_id]
    conn.execute(
        """
        INSERT INTO sources (
          source_id, name, scope, default_url, data_format,
          is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          is_active = 1,
          updated_at = excluded.updated_at
        """,
        (
            source_id,
            name,
            "nacional",
            default_url,
            "pdf/html",
            now_iso,
            now_iso,
        ),
    )


def persist_download_outcomes(
    conn: sqlite3.Connection,
    *,
    successes: list[DownloadOutcome],
    failures: list[DownloadOutcome],
    snapshot_date: str = "",
) -> None:
    now_iso = now_utc_iso()
    source_ids = sorted({_document_source_id(outcome) for outcome in successes + failures})
    for source_id in source_ids:
        _ensure_document_source(conn, source_id=source_id, now_iso=now_iso)

    pk_maps: dict[str, dict[str, int]] = {}
    for source_id in sorted({_document_source_id(outcome) for outcome in successes}):
        source_successes = [
            outcome
            for outcome in successes
            if _document_source_id(outcome) == source_id
        ]
        pk_maps[source_id] = upsert_source_records_with_content_sha256(
            conn,
            source_id=source_id,
            rows=[
                {
                    "source_record_id": outcome.item_key,
                    "raw_payload": stable_json(
                        {
                            "url": outcome.item_key,
                            "snapshot_date": snapshot_date,
                            "fetch_method": "durable_work_queue_stream",
                            "work_item_id": outcome.work_item_id,
                        }
                    ),
                    "content_sha256": str(outcome.stored.content_sha256),
                }
                for outcome in source_successes
                if outcome.stored is not None
            ],
            snapshot_date=snapshot_date or None,
            now_iso=now_iso,
        )

    for outcome in successes:
        stored = outcome.stored
        if stored is None:
            continue
        document_source_id = _document_source_id(outcome)
        source_record_pk = pk_maps.get(document_source_id, {}).get(outcome.item_key)
        if source_record_pk is None:
            raise RuntimeError(f"missing source_record_pk after download: {outcome.item_key}")
        conn.execute(
            """
            INSERT INTO text_documents (
              source_id, source_url, source_record_pk,
              fetched_at, content_type, content_sha256, bytes, raw_path,
              text_excerpt, text_chars, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            ON CONFLICT(source_record_pk) DO UPDATE SET
              source_url = excluded.source_url,
              fetched_at = excluded.fetched_at,
              content_type = excluded.content_type,
              content_sha256 = excluded.content_sha256,
              bytes = excluded.bytes,
              raw_path = excluded.raw_path,
              updated_at = excluded.updated_at
            """,
            (
                document_source_id,
                outcome.item_key,
                int(source_record_pk),
                now_iso,
                stored.content_type,
                stored.content_sha256,
                int(stored.bytes),
                str(stored.path),
                now_iso,
                now_iso,
            ),
        )
        if outcome.payload.get("initiative_id") and table_exists(
            conn, "parl_initiative_documents"
        ):
            conn.execute(
                """
                UPDATE parl_initiative_documents
                SET source_record_pk = ?, updated_at = ?
                WHERE doc_url = ?
                """,
                (int(source_record_pk), now_iso, outcome.item_key),
            )
        if outcome.payload.get("contract_document_id") and table_exists(
            conn, "money_contract_documents"
        ):
            conn.execute(
                """
                UPDATE money_contract_documents
                SET document_source_record_pk = ?, updated_at = ?
                WHERE source_url = ?
                """,
                (int(source_record_pk), now_iso, outcome.item_key),
            )
        conn.execute(
            """
            INSERT INTO document_fetches (
              doc_url, source_id, first_attempt_at, last_attempt_at, attempts,
              fetched_ok, last_http_status, last_error, content_type,
              content_sha256, bytes, raw_path
            ) VALUES (?, ?, ?, ?, 1, 1, 200, NULL, ?, ?, ?, ?)
            ON CONFLICT(doc_url) DO UPDATE SET
              source_id = excluded.source_id,
              last_attempt_at = excluded.last_attempt_at,
              attempts = document_fetches.attempts + 1,
              fetched_ok = 1,
              last_http_status = 200,
              last_error = NULL,
              content_type = excluded.content_type,
              content_sha256 = excluded.content_sha256,
              bytes = excluded.bytes,
              raw_path = excluded.raw_path
            """,
            (
                outcome.item_key,
                document_source_id,
                now_iso,
                now_iso,
                stored.content_type,
                stored.content_sha256,
                int(stored.bytes),
                str(stored.path),
            ),
        )

    for outcome in failures:
        document_source_id = _document_source_id(outcome)
        conn.execute(
            """
            INSERT INTO document_fetches (
              doc_url, source_id, first_attempt_at, last_attempt_at, attempts,
              fetched_ok, last_http_status, last_error
            ) VALUES (?, ?, ?, ?, 1, 0, ?, ?)
            ON CONFLICT(doc_url) DO UPDATE SET
              source_id = excluded.source_id,
              last_attempt_at = excluded.last_attempt_at,
              attempts = document_fetches.attempts + 1,
              fetched_ok = 0,
              last_http_status = excluded.last_http_status,
              last_error = excluded.last_error
            """,
            (
                outcome.item_key,
                document_source_id,
                now_iso,
                now_iso,
                outcome.http_status,
                outcome.error,
            ),
        )
    conn.commit()


def process_document_fetch_queue(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    pipeline_id: str,
    worker_id: str,
    workers: int,
    per_host_workers: int,
    host_hard_failure_threshold: int = 3,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    timeout: int,
    max_bytes: int,
    download_attempts: int,
    retry_delay_seconds: int,
    snapshot_date: str = "",
    ca_bundle: Path | None = None,
) -> dict[str, Any]:
    ensure_work_queue_schema(conn)
    _ensure_required_tables(conn)
    limiter = HostLimiter(per_host_workers, host_hard_failure_threshold)
    totals = {"claimed": 0, "succeeded": 0, "retried": 0, "dead": 0}
    failure_samples: list[dict[str, object]] = []
    failure_class_counts: dict[str, int] = {}

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
                    _download_item,
                    item,
                    raw_root=raw_root,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    download_attempts=download_attempts,
                    host_limiter=limiter,
                    ca_bundle=ca_bundle,
                ): int(item["work_item_id"])
                for item in claimed
            }
            outcomes = collect_futures_with_heartbeat(
                conn,
                futures=futures,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
            )

        successes = [outcome for outcome in outcomes if outcome.stored is not None]
        failures = [outcome for outcome in outcomes if outcome.stored is None]
        persist_download_outcomes(
            conn,
            successes=successes,
            failures=failures,
            snapshot_date=snapshot_date,
        )
        if successes:
            completed = complete_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id for outcome in successes],
            )
            totals["succeeded"] += completed
        for outcome in failures:
            failure_class = str(outcome.failure_class or "download_error")
            failure_class_counts[failure_class] = (
                failure_class_counts.get(failure_class, 0) + 1
            )
            failed = fail_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[outcome.work_item_id],
                error=str(outcome.error or "download_failed"),
                retry_delay_seconds=retry_delay_seconds,
                retryable=outcome.retryable,
            )
            totals["retried"] += int(failed["retry_total"])
            totals["dead"] += int(failed["dead_total"])
            if len(failure_samples) < 20:
                failure_samples.append(
                    {
                        "item_key": outcome.item_key,
                        "http_status": outcome.http_status,
                        "failure_class": outcome.failure_class,
                        "error": outcome.error,
                    }
                )

    if totals["claimed"] > 0 and totals["succeeded"] == 0 and totals["retried"] > 0:
        status = "blocked"
    elif totals["retried"] > 0 or totals["dead"] > 0:
        status = "partial"
    else:
        status = "ok"
    return {
        "schema_version": "document_fetch_queue_run_v1",
        "status": status,
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "workers": int(workers),
        "per_host_workers": int(per_host_workers),
        "opened_hosts": limiter.opened_hosts(),
        "opened_circuits": limiter.opened_circuits(),
        "failure_class_counts": dict(sorted(failure_class_counts.items())),
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
    numeric_values = (
        int(args.workers),
        int(args.per_host_workers),
        int(args.host_hard_failure_threshold),
        int(args.claim_size),
        int(args.lease_seconds),
        int(args.timeout),
        int(args.max_bytes),
        int(args.download_attempts),
    )
    if any(value < 1 for value in numeric_values) or int(args.max_items) < 0:
        print("ERROR: worker/size/lease/timeout values must be positive", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        report = process_document_fetch_queue(
            conn,
            raw_root=Path(args.raw_root),
            pipeline_id=str(args.pipeline_id),
            worker_id=str(args.worker_id),
            workers=int(args.workers),
            per_host_workers=int(args.per_host_workers),
            host_hard_failure_threshold=int(args.host_hard_failure_threshold),
            claim_size=min(10_000, int(args.claim_size)),
            max_items=int(args.max_items),
            lease_seconds=int(args.lease_seconds),
            timeout=int(args.timeout),
            max_bytes=int(args.max_bytes),
            download_attempts=int(args.download_attempts),
            retry_delay_seconds=max(0, int(args.retry_delay_seconds)),
            ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
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
