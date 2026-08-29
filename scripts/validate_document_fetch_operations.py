#!/usr/bin/env python3
"""Independently reconcile the public document-fetch operations snapshot."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PIPELINE_ID = "document_fetch"
QUEUE_STATES = ("pending", "leased", "succeeded", "dead")
PRIVATE_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"file:///", re.IGNORECASE),
    re.compile(
        r"(?:bearer|authorization|cookie|api[_-]?key|token)\s*[:=]", re.IGNORECASE
    ),
)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def failure_class(http_status: int | None, error: str | None) -> str:
    normalized = str(error or "").lower()
    if "host_circuit_open" in normalized:
        return "host_circuit_open"
    if http_status in {400, 404, 410, 413, 414, 415, 422}:
        return "not_fetchable"
    if http_status in {401, 403}:
        return "access_blocked"
    if http_status == 429:
        return "rate_limited"
    if http_status is not None and 500 <= http_status <= 599:
        return "upstream_server_error"
    if "timeout" in normalized:
        return "timeout"
    if "urlerror" in normalized or "connection" in normalized:
        return "network"
    return "download_error"


def validate(
    *,
    path: Path,
    evidence_path: Path | None,
    db_path: Path,
    raw_root: Path,
    max_bytes: int,
) -> dict[str, Any]:
    errors: list[str] = []
    if not path.is_file():
        return {
            "status": "error",
            "checks": {},
            "errors": [f"missing snapshot: {path}"],
        }
    size = path.stat().st_size
    if size > int(max_bytes):
        errors.append(f"snapshot exceeds max bytes: {size} > {int(max_bytes)}")
    body = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "checks": {"file_size_bytes": size},
            "errors": [str(exc)],
        }
    if evidence_path is not None:
        if not evidence_path.is_file():
            errors.append(f"missing evidence copy: {evidence_path}")
        elif evidence_path.read_bytes() != path.read_bytes():
            errors.append("public snapshot and evidence copy differ")
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(body):
            errors.append(
                f"public artifact contains forbidden pattern: {pattern.pattern}"
            )

    meta = payload.get("meta") or {}
    policy = payload.get("policy") or {}
    worker_policy = payload.get("worker_policy") or {}
    queue = payload.get("queue") or {}
    documents = payload.get("documents") or {}
    integrity = payload.get("integrity") or {}
    scale_claim = payload.get("scale_claim") or {}
    if meta.get("schema_version") != "document_fetch_operations_v1":
        errors.append("schema_version must be document_fetch_operations_v1")
    try:
        generated_at = datetime.fromisoformat(
            str(meta.get("generated_at") or "").replace("Z", "+00:00")
        )
        if generated_at.tzinfo is None:
            raise ValueError("timezone missing")
    except ValueError:
        generated_at = datetime.now(timezone.utc)
        errors.append("meta.generated_at must be timezone-aware ISO-8601")
    if meta.get("pipeline_id") != PIPELINE_ID:
        errors.append(f"meta.pipeline_id must be {PIPELINE_ID}")
    if meta.get("network_run_performed") is not False:
        errors.append("snapshot generation must not claim a network run")
    expected_policy = {
        "data_origin": "official_public_documents_only",
        "synthetic_or_mock_records": "forbidden",
        "public_domain_personal_information": "retained",
        "raw_urls_or_error_samples_published": False,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} must be {expected!r}")
    for key in ("global_workers", "per_host_workers", "max_document_bytes"):
        if (
            not isinstance(worker_policy.get(key), int)
            or int(worker_policy.get(key) or 0) < 1
        ):
            errors.append(f"worker_policy.{key} must be a positive integer")
    if (
        not isinstance(worker_policy.get("per_host_min_interval_ms"), int)
        or int(worker_policy.get("per_host_min_interval_ms") or 0) < 0
    ):
        errors.append("worker_policy.per_host_min_interval_ms must be non-negative")
    for key in (
        "streaming_content_addressed_storage",
        "atomic_leases",
        "heartbeat_and_reclaim",
        "retry_and_dead_letter_states",
        "cohort_circuit_breakers",
        "per_host_slo_report_on_worker_runs",
    ):
        if worker_policy.get(key) is not True:
            errors.append(f"worker_policy.{key} must be true")

    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        queue_rows = connection.execute(
            """
            SELECT item_key, state, attempts, payload_json, lease_expires_at
            FROM pipeline_work_items
            WHERE pipeline_id = ?
            ORDER BY work_item_id
            """,
            (PIPELINE_ID,),
        ).fetchall()
        attempt_rows = connection.execute(
            """
            SELECT a.status, COUNT(*) AS total
            FROM pipeline_work_attempts a
            JOIN pipeline_work_items i ON i.work_item_id = a.work_item_id
            WHERE i.pipeline_id = ?
            GROUP BY a.status
            ORDER BY a.status
            """,
            (PIPELINE_ID,),
        ).fetchall()
        fetch_rows = connection.execute(
            """
            SELECT i.item_key, f.fetched_ok, f.last_http_status, f.last_error,
                   COALESCE(f.bytes, 0) AS bytes
            FROM pipeline_work_items i
            LEFT JOIN document_fetches f ON f.doc_url = i.item_key
            WHERE i.pipeline_id = ?
            ORDER BY i.work_item_id
            """,
            (PIPELINE_ID,),
        ).fetchall()
        document_row = connection.execute(
            """
            SELECT COUNT(*) AS sightings,
                   COUNT(DISTINCT doc_url) AS unique_urls,
                   COUNT(DISTINCT CASE WHEN source_record_pk IS NOT NULL THEN doc_url END)
                     AS linked_urls
            FROM parl_initiative_documents
            """
        ).fetchone()
    finally:
        connection.close()

    state_counts = {state: 0 for state in QUEUE_STATES}
    schemes = Counter()
    host_queue: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "official_urls_total": 0,
            "queue_state_counts": {state: 0 for state in QUEUE_STATES},
            "attempts_total": 0,
            "max_attempts_observed": 0,
            "fetched_succeeded_total": 0,
            "fetched_failed_total": 0,
            "bytes_received": 0,
            "http_status_counts": Counter(),
            "failure_class_counts": Counter(),
        }
    )
    item_hosts: dict[str, str] = {}
    attempts_total = 0
    retry_attempts_total = 0
    max_attempts_observed = 0
    overdue_leases_total = 0
    generated_iso = generated_at.astimezone(timezone.utc).isoformat()
    for row in queue_rows:
        record = json.loads(str(row["payload_json"] or "{}"))
        url = str(record.get("doc_url") or row["item_key"] or "")
        parsed = urlparse(url)
        host = str(parsed.hostname or "missing-host").lower()
        item_hosts[str(row["item_key"])] = host
        schemes[str(parsed.scheme or "missing-scheme").lower()] += 1
        state = str(row["state"])
        state_counts[state] = state_counts.get(state, 0) + 1
        host_queue[host]["official_urls_total"] += 1
        host_queue[host]["queue_state_counts"][state] += 1
        attempts = int(row["attempts"] or 0)
        attempts_total += attempts
        retry_attempts_total += max(0, attempts - 1)
        max_attempts_observed = max(max_attempts_observed, attempts)
        host_queue[host]["attempts_total"] += attempts
        host_queue[host]["max_attempts_observed"] = max(
            host_queue[host]["max_attempts_observed"], attempts
        )
        if state == "leased" and str(row["lease_expires_at"] or "") <= generated_iso:
            overdue_leases_total += 1

    fetched_succeeded = 0
    fetched_failed = 0
    missing_fetch = 0
    bytes_received = 0
    statuses = Counter()
    failures = Counter()
    for row in fetch_rows:
        host_values = host_queue[item_hosts.get(str(row["item_key"]), "missing-host")]
        if row["fetched_ok"] is None:
            missing_fetch += 1
            continue
        status_key = str(
            row["last_http_status"] if row["last_http_status"] is not None else "none"
        )
        statuses[status_key] += 1
        host_values["http_status_counts"][status_key] += 1
        if int(row["fetched_ok"] or 0) == 1:
            fetched_succeeded += 1
            received = int(row["bytes"] or 0)
            bytes_received += received
            host_values["fetched_succeeded_total"] += 1
            host_values["bytes_received"] += received
        else:
            fetched_failed += 1
            classification = failure_class(row["last_http_status"], row["last_error"])
            failures[classification] += 1
            host_values["fetched_failed_total"] += 1
            host_values["failure_class_counts"][classification] += 1

    terminal = state_counts["succeeded"] + state_counts["dead"]
    unfinished = state_counts["pending"] + state_counts["leased"]
    expected_queue = {
        "items_total": len(queue_rows),
        "state_counts": state_counts,
        "unfinished_total": unfinished,
        "terminal_total": terminal,
        "attempts_total": attempts_total,
        "retry_attempts_total": retry_attempts_total,
        "max_attempts_observed": max_attempts_observed,
        "attempt_status_counts": {
            str(row["status"]): int(row["total"]) for row in attempt_rows
        },
        "overdue_leases_total": overdue_leases_total,
    }
    for key, expected in expected_queue.items():
        if queue.get(key) != expected:
            errors.append(f"queue.{key} does not reconcile to the real DB")

    linked_urls = int(document_row["linked_urls"] or 0)
    unique_urls = int(document_row["unique_urls"] or 0)
    expected_documents = {
        "official_url_sightings_total": int(document_row["sightings"] or 0),
        "official_urls_total": unique_urls,
        "source_record_linked_urls_total": linked_urls,
        "source_record_missing_urls_total": unique_urls - linked_urls,
        "fetched_succeeded_total": fetched_succeeded,
        "fetched_failed_total": fetched_failed,
        "missing_fetch_rows_total": missing_fetch,
        "bytes_received": bytes_received,
        "url_scheme_counts": dict(sorted(schemes.items())),
        "http_status_counts": dict(sorted(statuses.items())),
        "failure_class_counts": dict(sorted(failures.items())),
    }
    for key, expected in expected_documents.items():
        if documents.get(key) != expected:
            errors.append(f"documents.{key} does not reconcile to the real DB")

    expected_hosts = []
    for host, values in sorted(host_queue.items()):
        expected_hosts.append(
            {
                "official_urls_total": values["official_urls_total"],
                "queue_state_counts": values["queue_state_counts"],
                "attempts_total": values["attempts_total"],
                "max_attempts_observed": values["max_attempts_observed"],
                "fetched_succeeded_total": values["fetched_succeeded_total"],
                "fetched_failed_total": values["fetched_failed_total"],
                "bytes_received": values["bytes_received"],
                "host": host,
                "http_status_counts": dict(
                    sorted(values["http_status_counts"].items())
                ),
                "failure_class_counts": dict(
                    sorted(values["failure_class_counts"].items())
                ),
            }
        )
    if payload.get("hosts") != expected_hosts:
        errors.append("hosts do not reconcile to real queue URLs and outcomes")

    partial_files = (
        sum(
            1 for candidate in (raw_root / ".partial").rglob("*") if candidate.is_file()
        )
        if (raw_root / ".partial").is_dir()
        else 0
    )
    expected_integrity = {
        "queue_balance_passed": len(queue_rows) == terminal + unfinished,
        "document_queue_parity_passed": unique_urls == len(queue_rows),
        "succeeded_fetch_parity_passed": state_counts["succeeded"] == fetched_succeeded,
        "fetch_rows_parity_passed": len(queue_rows)
        == fetched_succeeded + fetched_failed + missing_fetch,
        "orphan_partial_files_total": partial_files,
        "official_host_allowlist_passed": set(host_queue) == {"www.senado.es"},
        "official_https_only": dict(schemes) == {"https": len(queue_rows)},
        "plaintext_http_urls_total": int(schemes.get("http", 0)),
    }
    if integrity != expected_integrity:
        errors.append("integrity section does not reconcile independently")
    if partial_files != 0:
        errors.append("orphan partial files must be zero")
    if not expected_integrity["official_host_allowlist_passed"]:
        errors.append(
            "document queue contains a URL outside the official host allowlist"
        )
    if scale_claim.get("one_million_documents_processed") != (terminal >= 1_000_000):
        errors.append("one-million processing claim is not evidence-backed")
    if scale_claim.get("promoted_for_unbounded_operation") is not False:
        errors.append("unbounded promotion is unsupported")

    return {
        "status": "ok" if not errors else "error",
        "checks": {
            "schema_version": meta.get("schema_version"),
            "file_size_bytes": size,
            "max_bytes": int(max_bytes),
            "official_urls_total": unique_urls,
            "terminal_total": terminal,
            "unfinished_total": unfinished,
            "fetched_succeeded_total": fetched_succeeded,
            "fetched_failed_total": fetched_failed,
            "orphan_partial_files_total": partial_files,
            "hosts_total": len(expected_hosts),
            "public_evidence_byte_equal": evidence_path is not None
            and evidence_path.is_file()
            and evidence_path.read_bytes() == path.read_bytes(),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--evidence-path", default="")
    parser.add_argument("--db", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--max-bytes", type=int, default=500_000)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = validate(
            path=Path(args.path),
            evidence_path=Path(args.evidence_path) if args.evidence_path else None,
            db_path=Path(args.db),
            raw_root=Path(args.raw_root),
            max_bytes=int(args.max_bytes),
        )
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        report = {"status": "error", "checks": {}, "errors": [str(exc)]}
    if args.out:
        atomic_write_json(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
