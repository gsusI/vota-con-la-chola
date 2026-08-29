#!/usr/bin/env python3
"""Run bounded concurrent document downloads from the durable work queue."""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
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
from publicdata_core.http import (  # noqa: E402
    retry_delay_seconds as http_retry_delay_seconds,
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
        "pdf/html",
    ),
    "placsp_contract_docs": (
        "Documentos oficiales de contratacion PLACSP",
        "manifest://placsp_contract_docs",
        "pdf/html",
    ),
    "boe_daily_summaries": (
        "Sumarios diarios oficiales del BOE",
        "https://www.boe.es/datosabiertos/api/boe/sumario",
        "json/xml",
    ),
    "boe_document_xml": (
        "Documentos individuales oficiales del BOE",
        "https://www.boe.es/diario_boe/xml.php",
        "xml",
    ),
}
DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_RAW_ROOT = Path("etl/data/raw/text_documents/parl_initiative_docs")
REQUEST_RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


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
    def __init__(
        self,
        per_host_workers: int,
        hard_failure_threshold: int = 3,
        min_interval_ms: int = 0,
    ) -> None:
        self._per_host_workers = max(1, int(per_host_workers))
        self._hard_failure_threshold = max(1, int(hard_failure_threshold))
        self._min_interval_seconds = max(0, int(min_interval_ms)) / 1000
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._next_start_at: dict[str, float] = {}
        self._inflight: dict[str, int] = {}
        self._host_stats: dict[str, dict[str, Any]] = {}
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

    @contextmanager
    def request_slot(self, url: str):
        """Bound concurrency and pace the start of every actual host request."""

        host = self._host(url)
        semaphore = self.for_url(url)
        semaphore.acquire()
        entered = False
        try:
            with self._lock:
                if self._circuit_key(url) in self._open_circuits:
                    allowed = False
                    wait_seconds = 0.0
                else:
                    allowed = True
                    now = time.monotonic()
                    start_at = max(now, self._next_start_at.get(host, now))
                    self._next_start_at[host] = start_at + self._min_interval_seconds
                    wait_seconds = max(0.0, start_at - now)
            if wait_seconds:
                time.sleep(wait_seconds)
            with self._lock:
                if allowed and self._circuit_key(url) in self._open_circuits:
                    allowed = False
                if allowed:
                    stats = self._stats_for_host(host)
                    stats["requests_started"] += 1
                    stats["throttle_wait_seconds"] += wait_seconds
                    inflight = self._inflight.get(host, 0) + 1
                    self._inflight[host] = inflight
                    stats["peak_inflight"] = max(stats["peak_inflight"], inflight)
                    entered = True
            yield allowed
        finally:
            if entered:
                with self._lock:
                    self._inflight[host] = max(0, self._inflight.get(host, 1) - 1)
            semaphore.release()

    def _stats_for_host(self, host: str) -> dict[str, Any]:
        stats = self._host_stats.get(host)
        if stats is None:
            stats = {
                "requests_started": 0,
                "successes": 0,
                "failures": 0,
                "bytes_received": 0,
                "peak_inflight": 0,
                "throttle_wait_seconds": 0.0,
                "http_status_counts": {},
                "failure_class_counts": {},
            }
            self._host_stats[host] = stats
        return stats

    def is_open(self, url: str) -> bool:
        with self._lock:
            return self._circuit_key(url) in self._open_circuits

    def record_status(
        self,
        url: str,
        http_status: int | None,
        *,
        success: bool | None = None,
        bytes_received: int = 0,
        failure_class: str | None = None,
    ) -> None:
        circuit_key = self._circuit_key(url)
        host = self._host(url)
        with self._lock:
            if success is not None:
                stats = self._stats_for_host(host)
                outcome_key = "successes" if success else "failures"
                stats[outcome_key] += 1
                stats["bytes_received"] += max(0, int(bytes_received))
                status_key = str(http_status) if http_status is not None else "none"
                status_counts = stats["http_status_counts"]
                status_counts[status_key] = status_counts.get(status_key, 0) + 1
                if failure_class:
                    failure_counts = stats["failure_class_counts"]
                    failure_counts[failure_class] = (
                        failure_counts.get(failure_class, 0) + 1
                    )
            if http_status in {401, 403, 429} or (
                http_status is not None and 500 <= http_status <= 599
            ):
                failures = self._hard_failures.get(circuit_key, 0) + 1
                self._hard_failures[circuit_key] = failures
                if failures >= self._hard_failure_threshold:
                    self._open_circuits.add(circuit_key)
            elif (
                success is not False
                and http_status is not None
                and 200 <= http_status < 400
            ):
                self._hard_failures.pop(circuit_key, None)

    def opened_hosts(self) -> list[str]:
        with self._lock:
            return sorted({key.split("|", 1)[0] for key in self._open_circuits})

    def opened_circuits(self) -> list[str]:
        with self._lock:
            return sorted(self._open_circuits)

    def host_slos(self) -> list[dict[str, Any]]:
        with self._lock:
            rows: list[dict[str, Any]] = []
            for host in sorted(self._host_stats):
                stats = self._host_stats[host]
                rows.append(
                    {
                        "host": host,
                        "requests_started": int(stats["requests_started"]),
                        "successes": int(stats["successes"]),
                        "failures": int(stats["failures"]),
                        "bytes_received": int(stats["bytes_received"]),
                        "peak_inflight": int(stats["peak_inflight"]),
                        "throttle_wait_seconds": round(
                            float(stats["throttle_wait_seconds"]), 6
                        ),
                        "http_status_counts": dict(
                            sorted(stats["http_status_counts"].items())
                        ),
                        "failure_class_counts": dict(
                            sorted(stats["failure_class_counts"].items())
                        ),
                        "circuit_open": host
                        in {key.split("|", 1)[0] for key in self._open_circuits},
                    }
                )
            return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run streaming document fetch queue")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--pipeline-id", default="document_fetch")
    parser.add_argument("--worker-id", default="document-fetch-worker")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--per-host-workers", type=int, default=2)
    parser.add_argument("--per-host-min-interval-ms", type=int, default=500)
    parser.add_argument("--host-hard-failure-threshold", type=int, default=3)
    parser.add_argument("--claim-size", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=0, help="0 processes until no ready work")
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--min-free-bytes", type=int, default=0)
    parser.add_argument("--download-attempts", type=int, default=3)
    parser.add_argument("--ca-bundle", default="")
    parser.add_argument("--retry-delay-seconds", type=int, default=60)
    parser.add_argument("--snapshot-date", default="")
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


def _validate_payload_contract(
    *, url: str, stored: StoredBlob, contract: object
) -> str | None:
    """Apply bounded, source-declared checks after a streamed download."""

    if contract is None:
        return None
    if not isinstance(contract, Mapping):
        return "validation_contract_not_object"
    parsed = urlparse(url)
    if contract.get("require_https") is True and parsed.scheme.lower() != "https":
        return "validation_contract_https_required"
    expected_host = str(contract.get("expected_host") or "").strip().lower()
    if expected_host and (parsed.hostname or "").lower() != expected_host:
        return "validation_contract_host_mismatch"
    minimum_bytes = contract.get("minimum_bytes")
    if minimum_bytes is not None:
        try:
            if stored.bytes < max(0, int(minimum_bytes)):
                return "validation_contract_minimum_bytes"
        except (TypeError, ValueError):
            return "validation_contract_minimum_bytes_invalid"
    expected_sha256 = str(contract.get("expected_content_sha256") or "").strip()
    if expected_sha256 and stored.content_sha256 != expected_sha256:
        return "validation_contract_expected_sha256_mismatch"

    allowed_types = contract.get("allowed_content_types")
    if allowed_types is not None:
        if not isinstance(allowed_types, list) or not all(
            isinstance(value, str) and value.strip() for value in allowed_types
        ):
            return "validation_contract_content_types_invalid"
        normalized_type = str(stored.content_type or "").split(";", 1)[0].strip().lower()
        if normalized_type not in {value.strip().lower() for value in allowed_types}:
            return "validation_contract_content_type_mismatch"

    required = contract.get("required_ascii_casefolded") or []
    forbidden = contract.get("forbidden_ascii_casefolded") or []
    if not isinstance(required, list) or not isinstance(forbidden, list):
        return "validation_contract_patterns_invalid"
    if not all(isinstance(value, str) and value for value in required + forbidden):
        return "validation_contract_patterns_invalid"
    if required or forbidden:
        with stored.path.open("rb") as handle:
            validation_body = handle.read(1024 * 1024).lower()
        try:
            required_bytes = [value.encode("ascii").lower() for value in required]
            forbidden_bytes = [value.encode("ascii").lower() for value in forbidden]
        except UnicodeEncodeError:
            return "validation_contract_patterns_not_ascii"
        if any(pattern not in validation_body for pattern in required_bytes):
            return "validation_contract_required_pattern_missing"
        if any(pattern in validation_body for pattern in forbidden_bytes):
            return "validation_contract_forbidden_pattern_present"
    return None


def _validate_official_download(
    *,
    url: str,
    source_id: str,
    stored: StoredBlob,
    validation_contract: object = None,
) -> str | None:
    if source_id in {"boe_daily_summaries", "boe_document_xml"}:
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != "www.boe.es":
            return "boe_source_url_not_official_https"
        with stored.path.open("rb") as handle:
            prefix = handle.read(128 * 1024).lstrip()
        if source_id == "boe_daily_summaries":
            if not re.fullmatch(r"/datosabiertos/api/boe/sumario/\d{8}", parsed.path):
                return "boe_summary_url_contract_mismatch"
            is_json_summary = prefix.startswith(b"{") and b'"sumario"' in prefix
            is_xml_summary = (
                prefix.startswith(b"<?xml")
                and b"<response" in prefix
                and b"<sumario" in prefix
            )
            if not is_json_summary and not is_xml_summary:
                return "boe_summary_payload_contract_mismatch"
        else:
            if parsed.path != "/diario_boe/xml.php":
                return "boe_document_url_contract_mismatch"
            expected_ids = parse_qs(parsed.query).get("id") or []
            if len(expected_ids) != 1 or not re.fullmatch(
                r"BOE-[A-Z]-\d{4}-\d+", expected_ids[0], flags=re.IGNORECASE
            ):
                return "boe_document_identifier_missing"
            identifier_match = re.search(
                rb"<identificador>\s*(BOE-[A-Z]-\d{4}-\d+)\s*</identificador>",
                prefix,
                flags=re.IGNORECASE,
            )
            if not prefix.startswith(b"<?xml") or identifier_match is None:
                return "boe_document_xml_contract_mismatch"
            if (
                identifier_match.group(1).decode("ascii").upper()
                != expected_ids[0].upper()
            ):
                return "boe_document_identifier_mismatch"
    return _validate_payload_contract(
        url=url,
        stored=stored,
        contract=validation_contract,
    )


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
    document_source_id = str(payload.get("document_source_id") or DOCUMENT_SOURCE_ID)
    attempts = max(1, int(download_attempts))
    for attempt in range(1, attempts + 1):
        with host_limiter.request_slot(url) as allowed:
            if not allowed:
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
            try:
                stored = download_to_content_addressed_store(
                    url,
                    store_root=raw_root,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    max_attempts=1,
                    ca_bundle=ca_bundle,
                )
            except Exception as exc:  # noqa: BLE001
                http_status = _http_status(exc)
                error = f"{type(exc).__name__}: {exc}"[:2_000]
                failure_class, retryable = _classify_download_failure(
                    http_status=http_status,
                    error=error,
                )
                host_limiter.record_status(
                    url,
                    http_status,
                    success=False,
                    failure_class=failure_class,
                )
                request_retryable = (
                    http_status in REQUEST_RETRYABLE_HTTP_STATUSES
                    or failure_class in {"timeout", "network"}
                )
                if (
                    request_retryable
                    and attempt < attempts
                    and not host_limiter.is_open(url)
                ):
                    retry_after = (
                        str(exc.headers.get("Retry-After") or "")
                        if isinstance(exc, urllib.error.HTTPError)
                        and exc.headers is not None
                        else None
                    )
                    time.sleep(
                        http_retry_delay_seconds(
                            attempt,
                            retry_after=retry_after,
                        )
                    )
                    continue
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
            validation_error = _validate_official_download(
                url=url,
                source_id=document_source_id,
                stored=stored,
                validation_contract=payload.get("validation_contract"),
            )
            if validation_error:
                if not stored.deduplicated:
                    stored.path.unlink(missing_ok=True)
                host_limiter.record_status(
                    url,
                    200,
                    success=False,
                    failure_class="invalid_official_payload",
                )
                return DownloadOutcome(
                    work_item_id,
                    item_key,
                    payload,
                    None,
                    validation_error,
                    200,
                    "invalid_official_payload",
                    False,
                )
            host_limiter.record_status(
                url,
                200,
                success=True,
                bytes_received=int(stored.bytes),
            )
        return DownloadOutcome(
            work_item_id, item_key, payload, stored, None, 200, None, False
        )
    raise RuntimeError("document download attempt loop exhausted")


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
    name, default_url, data_format = DOCUMENT_SOURCES[source_id]
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
            data_format,
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
                            "queue_payload": outcome.payload,
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
    per_host_min_interval_ms: int = 0,
    host_hard_failure_threshold: int = 3,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    timeout: int,
    max_bytes: int,
    min_free_bytes: int = 0,
    download_attempts: int,
    retry_delay_seconds: int,
    snapshot_date: str = "",
    ca_bundle: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    cpu_started = time.process_time()
    ensure_work_queue_schema(conn)
    _ensure_required_tables(conn)
    limiter = HostLimiter(
        per_host_workers,
        host_hard_failure_threshold,
        per_host_min_interval_ms,
    )
    totals = {
        "claimed": 0,
        "succeeded": 0,
        "retried": 0,
        "dead": 0,
        "bytes_received": 0,
        "new_content_objects": 0,
        "deduplicated_content_objects": 0,
    }
    failure_samples: list[dict[str, object]] = []
    failure_class_counts: dict[str, int] = {}
    stop_reason: str | None = None
    raw_root.mkdir(parents=True, exist_ok=True)
    storage: dict[str, Any] = {}

    while max_items <= 0 or totals["claimed"] < max_items:
        remaining = (
            claim_size
            if max_items <= 0
            else min(claim_size, max_items - totals["claimed"])
        )
        if remaining <= 0:
            break
        disk = shutil.disk_usage(raw_root)
        reserve_bytes = max(1, min(int(workers), int(remaining))) * int(max_bytes)
        storage = {
            "free_bytes": int(disk.free),
            "min_free_bytes": int(min_free_bytes),
            "inflight_reserve_bytes": reserve_bytes,
            "required_free_bytes": int(min_free_bytes) + reserve_bytes,
        }
        if int(disk.free) < storage["required_free_bytes"]:
            storage["blocked"] = True
            break
        storage["blocked"] = False
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
        batch_hosts = {
            HostLimiter._host(
                str(outcome.payload.get("doc_url") or outcome.item_key)
            )
            for outcome in outcomes
        }
        totals["bytes_received"] += sum(
            int(outcome.stored.bytes)
            for outcome in successes
            if outcome.stored is not None
        )
        totals["new_content_objects"] += sum(
            1
            for outcome in successes
            if outcome.stored is not None and not outcome.stored.deduplicated
        )
        totals["deduplicated_content_objects"] += sum(
            1
            for outcome in successes
            if outcome.stored is not None and outcome.stored.deduplicated
        )
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
        if (
            not successes
            and batch_hosts
            and batch_hosts <= set(limiter.opened_hosts())
        ):
            stop_reason = "all_claimed_hosts_circuit_open"
            break

    if storage.get("blocked") is True:
        status = "blocked_storage"
    elif totals["claimed"] > 0 and totals["succeeded"] == 0 and totals["retried"] > 0:
        status = "blocked"
    elif totals["retried"] > 0 or totals["dead"] > 0:
        status = "partial"
    else:
        status = "ok"
    elapsed_seconds = max(0.000001, time.monotonic() - started)
    cpu_seconds = max(0.0, time.process_time() - cpu_started)
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    succeeded = int(totals["succeeded"])
    host_slos = limiter.host_slos()
    network_requests_started = sum(
        int(row["requests_started"]) for row in host_slos
    )
    return {
        "schema_version": "document_fetch_queue_run_v3",
        "status": status,
        "pipeline_id": pipeline_id,
        "worker_id": worker_id,
        "stop_reason": stop_reason,
        "workers": int(workers),
        "per_host_workers": int(per_host_workers),
        "host_policy": {
            "per_host_workers": int(per_host_workers),
            "per_host_min_interval_ms": int(per_host_min_interval_ms),
            "hard_failure_threshold": int(host_hard_failure_threshold),
        },
        "host_slos": host_slos,
        "opened_hosts": limiter.opened_hosts(),
        "opened_circuits": limiter.opened_circuits(),
        "failure_class_counts": dict(sorted(failure_class_counts.items())),
        "totals": totals,
        "performance": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "cpu_seconds": round(cpu_seconds, 6),
            "peak_rss_bytes": peak_rss_bytes,
            "items_per_second": round(succeeded / elapsed_seconds, 6),
            "bytes_per_second": round(
                int(totals["bytes_received"]) / elapsed_seconds, 6
            ),
            "elapsed_seconds_per_1000_succeeded": (
                round(elapsed_seconds * 1000 / succeeded, 6)
                if succeeded
                else None
            ),
            "bytes_per_1000_succeeded": (
                round(int(totals["bytes_received"]) * 1000 / succeeded, 3)
                if succeeded
                else None
            ),
            "logical_requests": int(totals["claimed"]),
            "network_requests_started": network_requests_started,
            "network_request_upper_bound": (
                int(totals["claimed"]) * int(download_attempts)
            ),
        },
        "queue": work_queue_stats(conn, pipeline_id=pipeline_id),
        "failure_samples": failure_samples,
        "storage": storage,
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
    if (
        any(value < 1 for value in numeric_values)
        or int(args.max_items) < 0
        or int(args.min_free_bytes) < 0
        or int(args.per_host_min_interval_ms) < 0
    ):
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
            per_host_min_interval_ms=int(args.per_host_min_interval_ms),
            host_hard_failure_threshold=int(args.host_hard_failure_threshold),
            claim_size=min(10_000, int(args.claim_size)),
            max_items=int(args.max_items),
            lease_seconds=int(args.lease_seconds),
            timeout=int(args.timeout),
            max_bytes=int(args.max_bytes),
            min_free_bytes=int(args.min_free_bytes),
            download_attempts=int(args.download_attempts),
            retry_delay_seconds=max(0, int(args.retry_delay_seconds)),
            snapshot_date=str(args.snapshot_date),
            ca_bundle=Path(args.ca_bundle) if args.ca_bundle else None,
        )
    finally:
        conn.close()

    if str(args.report_out or "").strip():
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{report_path.name}.", dir=report_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=True, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, report_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
