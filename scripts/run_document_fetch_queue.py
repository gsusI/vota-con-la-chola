#!/usr/bin/env python3
"""Run bounded concurrent document downloads from the durable work queue."""

from __future__ import annotations

import argparse
import json
import math
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
from collections.abc import Callable, Mapping
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
    network_requests_started: int = 0
    bytes_received: int = 0


class HostLimiter:
    def __init__(
        self,
        per_host_workers: int,
        hard_failure_threshold: int = 3,
        min_interval_ms: int = 0,
        request_budgets: Mapping[str, int] | None = None,
        require_explicit_budget: bool = False,
        initial_request_budget_usage: Mapping[str, int] | None = None,
    ) -> None:
        self._per_host_workers = max(1, int(per_host_workers))
        self._hard_failure_threshold = max(1, int(hard_failure_threshold))
        self._min_interval_seconds = max(0, int(min_interval_ms)) / 1000
        self._request_budgets = {
            str(host).strip().lower(): max(1, int(limit))
            for host, limit in (request_budgets or {}).items()
        }
        self._initial_request_budget_usage = {
            str(host).strip().lower(): max(0, int(requests_reserved))
            for host, requests_reserved in (
                initial_request_budget_usage or {}
            ).items()
            if str(host).strip()
        }
        self._require_explicit_budget = bool(require_explicit_budget)
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._next_start_at: dict[str, float] = {}
        self._inflight: dict[str, int] = {}
        self._host_stats: dict[str, dict[str, Any]] = {}
        self._hard_failures: dict[str, int] = {}
        self._open_circuits: set[str] = set()
        self._budget_exhausted_hosts: set[str] = set()
        self._unbudgeted_hosts: set[str] = set()

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
                stats = self._stats_for_host(host)
                budget = self._request_budgets.get(host)
                cumulative_requests = self._initial_request_budget_usage.get(
                    host, 0
                ) + int(stats["requests_started"])
                if self._require_explicit_budget and budget is None:
                    self._unbudgeted_hosts.add(host)
                    allowed = False
                    wait_seconds = 0.0
                elif budget is not None and cumulative_requests >= budget:
                    self._budget_exhausted_hosts.add(host)
                    allowed = False
                    wait_seconds = 0.0
                elif self._circuit_key(url) in self._open_circuits:
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
                    budget = self._request_budgets.get(host)
                    cumulative_requests = self._initial_request_budget_usage.get(
                        host, 0
                    ) + int(stats["requests_started"])
                    if budget is not None and cumulative_requests >= budget:
                        self._budget_exhausted_hosts.add(host)
                        allowed = False
                    else:
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

    def budget_block_reason(self, url: str) -> str | None:
        host = self._host(url)
        with self._lock:
            if host in self._unbudgeted_hosts:
                return "host_request_budget_missing"
            if host in self._budget_exhausted_hosts:
                return "host_request_budget_exhausted"
        return None

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
            if (
                http_status in {401, 403, 429}
                or (http_status is not None and 500 <= http_status <= 599)
                or failure_class in {"timeout", "network"}
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

    def budget_exhausted_hosts(self) -> list[str]:
        with self._lock:
            return sorted(self._budget_exhausted_hosts)

    def unbudgeted_hosts(self) -> list[str]:
        with self._lock:
            return sorted(self._unbudgeted_hosts)

    def host_slos(self) -> list[dict[str, Any]]:
        with self._lock:
            rows: list[dict[str, Any]] = []
            for host in sorted(self._host_stats):
                stats = self._host_stats[host]
                prior_budget_usage = self._initial_request_budget_usage.get(host, 0)
                current_requests = int(stats["requests_started"])
                rows.append(
                    {
                        "host": host,
                        "request_budget": self._request_budgets.get(host),
                        "request_budget_remaining": (
                            max(
                                0,
                                int(self._request_budgets[host])
                                - prior_budget_usage
                                - current_requests,
                            )
                            if host in self._request_budgets
                            else None
                        ),
                        "request_budget_exhausted": host
                        in self._budget_exhausted_hosts,
                        "requests_started": current_requests,
                        "request_budget_used_prior": prior_budget_usage,
                        "request_budget_used_cumulative": prior_budget_usage
                        + current_requests,
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
    parser.add_argument(
        "--host-request-budget",
        action="append",
        default=[],
        metavar="HOST=REQUESTS",
    )
    parser.add_argument("--require-explicit-host-budget", action="store_true")
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
    parser.add_argument(
        "--progress-min-interval-seconds",
        type=float,
        default=10.0,
        help=(
            "Minimum wall interval between atomic progress publications; "
            "the first completed batch and final report are always published"
        ),
    )
    return parser.parse_args(argv)


def _parse_host_request_budgets(values: list[str]) -> dict[str, int]:
    budgets: dict[str, int] = {}
    for raw in values:
        host, separator, limit_text = str(raw or "").strip().partition("=")
        normalized_host = host.strip().lower()
        if not separator or not normalized_host:
            raise ValueError(f"invalid host request budget: {raw}")
        if normalized_host in budgets:
            raise ValueError(f"duplicate host request budget: {normalized_host}")
        try:
            limit = int(limit_text)
        except ValueError as exc:
            raise ValueError(f"invalid host request budget: {raw}") from exc
        if limit < 1:
            raise ValueError(f"host request budget must be positive: {raw}")
        budgets[normalized_host] = limit
    return dict(sorted(budgets.items()))


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
    if "host_request_budget_missing" in normalized:
        return "host_request_budget_missing", False
    if "host_request_budget_exhausted" in normalized:
        return "host_request_budget_exhausted", False
    if "host_circuit_open" in normalized:
        return "host_circuit_open", True
    if "redirect_not_allowed" in normalized:
        return "redirect_not_allowed", False
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
    network_requests_started = 0
    for attempt in range(1, attempts + 1):
        with host_limiter.request_slot(url) as allowed:
            if not allowed:
                budget_reason = host_limiter.budget_block_reason(url)
                return DownloadOutcome(
                    work_item_id,
                    item_key,
                    payload,
                    None,
                    budget_reason or "host_circuit_open",
                    None,
                    budget_reason or "host_circuit_open",
                    budget_reason is None,
                    network_requests_started,
                )
            network_requests_started += 1
            try:
                stored = download_to_content_addressed_store(
                    url,
                    store_root=raw_root,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    max_attempts=1,
                    ca_bundle=ca_bundle,
                    follow_redirects=False,
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
                    network_requests_started,
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
                    bytes_received=int(stored.bytes),
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
                    network_requests_started,
                    int(stored.bytes),
                )
            host_limiter.record_status(
                url,
                200,
                success=True,
                bytes_received=int(stored.bytes),
            )
        return DownloadOutcome(
            work_item_id,
            item_key,
            payload,
            stored,
            None,
            200,
            None,
            False,
            network_requests_started,
            int(stored.bytes),
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


def _ensure_request_event_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_fetch_request_events (
          document_fetch_request_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          work_item_id INTEGER NOT NULL
            REFERENCES pipeline_work_items(work_item_id) ON DELETE CASCADE,
          pipeline_id TEXT NOT NULL,
          queue_attempt_number INTEGER NOT NULL CHECK (queue_attempt_number >= 1),
          worker_id TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_host TEXT NOT NULL,
          outcome_state TEXT NOT NULL
            CHECK (outcome_state IN ('succeeded', 'failed')),
          network_requests_started INTEGER NOT NULL
            CHECK (network_requests_started >= 0),
          http_status INTEGER,
          failure_class TEXT,
          bytes_received INTEGER NOT NULL DEFAULT 0 CHECK (bytes_received >= 0),
          recorded_at TEXT NOT NULL,
          UNIQUE (work_item_id, queue_attempt_number)
        );
        CREATE INDEX IF NOT EXISTS idx_document_fetch_request_events_pipeline
          ON document_fetch_request_events (
            pipeline_id,
            source_host,
            outcome_state,
            document_fetch_request_event_id
          );
        """
    )
    conn.commit()


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
    pipeline_id: str,
    worker_id: str,
    snapshot_date: str = "",
) -> None:
    now_iso = now_utc_iso()
    outcomes = successes + failures
    source_ids = sorted({_document_source_id(outcome) for outcome in outcomes})
    for source_id in source_ids:
        _ensure_document_source(conn, source_id=source_id, now_iso=now_iso)

    if outcomes:
        work_item_ids = [int(outcome.work_item_id) for outcome in outcomes]
        placeholders = ",".join("?" for _ in work_item_ids)
        attempt_numbers = {
            int(row["work_item_id"]): int(row["attempts"])
            for row in conn.execute(
                f"""
                SELECT work_item_id, attempts
                FROM pipeline_work_items
                WHERE work_item_id IN ({placeholders})
                """,
                work_item_ids,
            ).fetchall()
        }
        if len(attempt_numbers) != len(outcomes):
            raise RuntimeError("request telemetry work-item lookup mismatch")
        conn.executemany(
            """
            INSERT INTO document_fetch_request_events (
              work_item_id, pipeline_id, queue_attempt_number, worker_id,
              source_url, source_host, outcome_state,
              network_requests_started, http_status, failure_class,
              bytes_received, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_item_id, queue_attempt_number) DO UPDATE SET
              worker_id = excluded.worker_id,
              source_url = excluded.source_url,
              source_host = excluded.source_host,
              outcome_state = excluded.outcome_state,
              network_requests_started = excluded.network_requests_started,
              http_status = excluded.http_status,
              failure_class = excluded.failure_class,
              bytes_received = excluded.bytes_received,
              recorded_at = excluded.recorded_at
            """,
            [
                (
                    int(outcome.work_item_id),
                    pipeline_id,
                    int(attempt_numbers[int(outcome.work_item_id)]),
                    worker_id,
                    outcome.item_key,
                    HostLimiter._host(
                        str(outcome.payload.get("doc_url") or outcome.item_key)
                    ),
                    "succeeded" if outcome.stored is not None else "failed",
                    int(outcome.network_requests_started),
                    outcome.http_status,
                    outcome.failure_class,
                    int(outcome.bytes_received),
                    now_iso,
                )
                for outcome in outcomes
            ],
        )

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


def durable_request_telemetry(
    conn: sqlite3.Connection, *, pipeline_id: str
) -> dict[str, Any]:
    host_rows = conn.execute(
        """
        SELECT
          source_host,
          COUNT(*) AS queue_attempt_events,
          COALESCE(SUM(network_requests_started), 0) AS network_requests_started,
          COALESCE(SUM(CASE WHEN outcome_state = 'succeeded' THEN 1 ELSE 0 END), 0)
            AS succeeded_attempts,
          COALESCE(SUM(CASE WHEN outcome_state = 'failed' THEN 1 ELSE 0 END), 0)
            AS failed_attempts,
          COALESCE(SUM(bytes_received), 0) AS bytes_received
        FROM document_fetch_request_events
        WHERE pipeline_id = ?
        GROUP BY source_host
        ORDER BY source_host
        """,
        (pipeline_id,),
    ).fetchall()
    hosts = [
        {
            "host": str(row["source_host"]),
            "queue_attempt_events": int(row["queue_attempt_events"] or 0),
            "network_requests_started": int(row["network_requests_started"] or 0),
            "succeeded_attempts": int(row["succeeded_attempts"] or 0),
            "failed_attempts": int(row["failed_attempts"] or 0),
            "bytes_received": int(row["bytes_received"] or 0),
        }
        for row in host_rows
    ]
    return {
        "storage": "sqlite_document_fetch_request_events_v1",
        "queue_attempt_events": sum(row["queue_attempt_events"] for row in hosts),
        "network_requests_started": sum(
            row["network_requests_started"] for row in hosts
        ),
        "succeeded_attempts": sum(row["succeeded_attempts"] for row in hosts),
        "failed_attempts": sum(row["failed_attempts"] for row in hosts),
        "bytes_received": sum(row["bytes_received"] for row in hosts),
        "hosts": hosts,
    }


def request_budget_recovery_usage(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    download_attempts: int,
) -> dict[str, Any]:
    telemetry = durable_request_telemetry(conn, pipeline_id=pipeline_id)
    actual_by_host = {
        str(row["host"]): int(row["network_requests_started"])
        for row in telemetry["hosts"]
    }
    conservative_by_host: dict[str, int] = {}
    unmatched_attempts = 0
    rows = conn.execute(
        """
        SELECT w.item_key, w.payload_json, COUNT(*) AS unmatched_attempts
        FROM pipeline_work_attempts a
        JOIN pipeline_work_items w ON w.work_item_id = a.work_item_id
        LEFT JOIN document_fetch_request_events e
          ON e.work_item_id = a.work_item_id
         AND e.queue_attempt_number = a.attempt_number
        WHERE w.pipeline_id = ?
          AND e.document_fetch_request_event_id IS NULL
        GROUP BY w.work_item_id, w.item_key, w.payload_json
        ORDER BY w.work_item_id
        """,
        (pipeline_id,),
    ).fetchall()
    for row in rows:
        payload = json.loads(str(row["payload_json"] or "{}"))
        url = str(payload.get("doc_url") or row["item_key"] or "")
        host = HostLimiter._host(url)
        attempts = int(row["unmatched_attempts"] or 0)
        unmatched_attempts += attempts
        conservative_by_host[host] = conservative_by_host.get(host, 0) + (
            attempts * max(1, int(download_attempts))
        )
    hosts = sorted(set(actual_by_host) | set(conservative_by_host))
    budget_usage_by_host = {
        host: actual_by_host.get(host, 0) + conservative_by_host.get(host, 0)
        for host in hosts
    }
    return {
        "policy": "durable_events_plus_full_bound_for_unmatched_attempts_v1",
        "durable_network_requests_started": sum(actual_by_host.values()),
        "unmatched_queue_attempts": unmatched_attempts,
        "conservative_unmatched_request_reservations": sum(
            conservative_by_host.values()
        ),
        "budget_usage_by_host": budget_usage_by_host,
    }


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
    host_request_budgets: Mapping[str, int] | None = None,
    require_explicit_host_budget: bool = False,
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
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_min_interval_seconds: float = 10.0,
) -> dict[str, Any]:
    started = time.monotonic()
    cpu_started = time.process_time()
    ensure_work_queue_schema(conn)
    _ensure_required_tables(conn)
    _ensure_request_event_schema(conn)
    request_budget_recovery = request_budget_recovery_usage(
        conn,
        pipeline_id=pipeline_id,
        download_attempts=download_attempts,
    )
    limiter = HostLimiter(
        per_host_workers,
        host_hard_failure_threshold,
        per_host_min_interval_ms,
        request_budgets=host_request_budgets,
        require_explicit_budget=require_explicit_host_budget,
        initial_request_budget_usage=request_budget_recovery[
            "budget_usage_by_host"
        ],
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
    completed_batches = 0
    published_checkpoints = 0
    last_progress_published_at: float | None = None

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
            pipeline_id=pipeline_id,
            worker_id=worker_id,
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
        completed_batches += 1
        progress_now = time.monotonic()
        publish_progress = progress_callback is not None and (
            last_progress_published_at is None
            or float(progress_min_interval_seconds) <= 0
            or progress_now - last_progress_published_at
            >= float(progress_min_interval_seconds)
        )
        if publish_progress:
            published_checkpoints += 1
            progress_callback(
                {
                    "schema_version": "document_fetch_queue_progress_v1",
                    "status": "running",
                    "updated_at": now_utc_iso(),
                    "pipeline_id": pipeline_id,
                    "worker_id": worker_id,
                    "checkpoint_sequence": published_checkpoints,
                    "completed_batches": completed_batches,
                    "totals": dict(totals),
                    "queue": work_queue_stats(conn, pipeline_id=pipeline_id),
                    "host_slos": limiter.host_slos(),
                    "failure_class_counts": dict(
                        sorted(failure_class_counts.items())
                    ),
                    "failure_samples": list(failure_samples),
                    "storage": dict(storage),
                }
            )
            last_progress_published_at = progress_now
        if (
            not successes
            and batch_hosts
            and batch_hosts
            <= set(
                limiter.opened_hosts()
                + limiter.budget_exhausted_hosts()
                + limiter.unbudgeted_hosts()
            )
        ):
            stop_reason = "all_claimed_hosts_blocked_by_circuit_or_budget"
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
    request_telemetry = durable_request_telemetry(conn, pipeline_id=pipeline_id)
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
            "download_attempts_per_queue_attempt": int(download_attempts),
            "request_budgets": dict(sorted((host_request_budgets or {}).items())),
            "require_explicit_host_budget": bool(require_explicit_host_budget),
        },
        "host_slos": host_slos,
        "durable_request_telemetry": request_telemetry,
        "request_budget_recovery": request_budget_recovery,
        "progress_checkpoints": {
            "callback_enabled": progress_callback is not None,
            "completed_batches": completed_batches,
            "published_checkpoints": published_checkpoints,
            "min_interval_seconds": max(
                0.0, float(progress_min_interval_seconds)
            ),
            "publication": "atomic_replace_first_batch_then_time_bounded_v2",
        },
        "opened_hosts": limiter.opened_hosts(),
        "opened_circuits": limiter.opened_circuits(),
        "budget_exhausted_hosts": limiter.budget_exhausted_hosts(),
        "unbudgeted_hosts": limiter.unbudgeted_hosts(),
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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        parent_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


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
        or not math.isfinite(float(args.progress_min_interval_seconds))
        or float(args.progress_min_interval_seconds) < 0
    ):
        print("ERROR: worker/size/lease/timeout values must be positive", file=sys.stderr)
        return 2

    try:
        host_request_budgets = _parse_host_request_budgets(
            list(args.host_request_budget or [])
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.require_explicit_host_budget and not host_request_budgets:
        print(
            "ERROR: --require-explicit-host-budget needs at least one host budget",
            file=sys.stderr,
        )
        return 2

    report_path = (
        Path(args.report_out) if str(args.report_out or "").strip() else None
    )

    def write_progress(progress: dict[str, Any]) -> None:
        if report_path is not None:
            _atomic_write_json(report_path, progress)

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
            host_request_budgets=host_request_budgets,
            require_explicit_host_budget=bool(args.require_explicit_host_budget),
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
            progress_callback=write_progress if report_path is not None else None,
            progress_min_interval_seconds=max(
                0.0, float(args.progress_min_interval_seconds)
            ),
        )
    finally:
        conn.close()

    if report_path is not None:
        _atomic_write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
