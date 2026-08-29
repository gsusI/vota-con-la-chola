#!/usr/bin/env python3
"""Publish bounded document-fetch operations from the real official queue."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PIPELINE_ID = "document_fetch"
QUEUE_STATES = ("pending", "leased", "succeeded", "dead")


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


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def fetch_failure_class(http_status: int | None, error: str | None) -> str:
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


def zero_states() -> dict[str, int]:
    return {state: 0 for state in QUEUE_STATES}


def build_payload(
    *,
    db_path: Path,
    raw_root: Path,
    generated_at: str,
    global_workers: int,
    per_host_workers: int,
    per_host_min_interval_ms: int,
    max_document_bytes: int,
) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        queue_rows = connection.execute(
            """
            SELECT item_key, state, attempts, max_attempts, payload_json,
                   created_at, updated_at, lease_expires_at
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

    queue_counts = zero_states()
    hosts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "official_urls_total": 0,
            "queue_state_counts": zero_states(),
            "attempts_total": 0,
            "max_attempts_observed": 0,
            "fetched_succeeded_total": 0,
            "fetched_failed_total": 0,
            "bytes_received": 0,
            "http_status_counts": Counter(),
            "failure_class_counts": Counter(),
        }
    )
    queue_urls: dict[str, str] = {}
    schemes = Counter()
    attempts_total = 0
    retry_attempts_total = 0
    max_attempts_observed = 0
    oldest_created_at: str | None = None
    latest_updated_at: str | None = None
    overdue_leases_total = 0
    now_iso = generated_at
    for row in queue_rows:
        payload = json.loads(str(row["payload_json"] or "{}"))
        url = str(payload.get("doc_url") or row["item_key"] or "").strip()
        parsed = urlparse(url)
        host = str(parsed.hostname or "missing-host").lower()
        schemes[str(parsed.scheme or "missing-scheme").lower()] += 1
        queue_urls[str(row["item_key"])] = host
        state = str(row["state"])
        queue_counts[state] = queue_counts.get(state, 0) + 1
        host_row = hosts[host]
        host_row["official_urls_total"] += 1
        host_row["queue_state_counts"][state] += 1
        attempts = int(row["attempts"] or 0)
        attempts_total += attempts
        retry_attempts_total += max(0, attempts - 1)
        max_attempts_observed = max(max_attempts_observed, attempts)
        host_row["attempts_total"] += attempts
        host_row["max_attempts_observed"] = max(
            host_row["max_attempts_observed"], attempts
        )
        created_at = str(row["created_at"] or "")
        updated_at = str(row["updated_at"] or "")
        oldest_created_at = min(
            value for value in (oldest_created_at, created_at) if value
        )
        latest_updated_at = max(
            value for value in (latest_updated_at, updated_at) if value
        )
        if state == "leased" and str(row["lease_expires_at"] or "") <= now_iso:
            overdue_leases_total += 1

    fetch_status_counts = Counter()
    failure_class_counts = Counter()
    fetched_succeeded_total = 0
    fetched_failed_total = 0
    bytes_received = 0
    missing_fetch_rows_total = 0
    for row in fetch_rows:
        host = queue_urls.get(str(row["item_key"]), "missing-host")
        host_row = hosts[host]
        if row["fetched_ok"] is None:
            missing_fetch_rows_total += 1
            continue
        fetched_ok = int(row["fetched_ok"] or 0) == 1
        status_key = str(
            row["last_http_status"] if row["last_http_status"] is not None else "none"
        )
        fetch_status_counts[status_key] += 1
        host_row["http_status_counts"][status_key] += 1
        if fetched_ok:
            fetched_succeeded_total += 1
            received = int(row["bytes"] or 0)
            bytes_received += received
            host_row["fetched_succeeded_total"] += 1
            host_row["bytes_received"] += received
        else:
            fetched_failed_total += 1
            failure_class = fetch_failure_class(
                row["last_http_status"], row["last_error"]
            )
            failure_class_counts[failure_class] += 1
            host_row["fetched_failed_total"] += 1
            host_row["failure_class_counts"][failure_class] += 1

    terminal_total = queue_counts["succeeded"] + queue_counts["dead"]
    unfinished_total = queue_counts["pending"] + queue_counts["leased"]
    partial_files_total = (
        sum(1 for path in (raw_root / ".partial").rglob("*") if path.is_file())
        if (raw_root / ".partial").is_dir()
        else 0
    )
    linked_urls = int(document_row["linked_urls"] or 0)
    unique_urls = int(document_row["unique_urls"] or 0)
    host_rows = []
    for host, values in sorted(hosts.items()):
        host_rows.append(
            {
                **{
                    key: values[key]
                    for key in (
                        "official_urls_total",
                        "queue_state_counts",
                        "attempts_total",
                        "max_attempts_observed",
                        "fetched_succeeded_total",
                        "fetched_failed_total",
                        "bytes_received",
                    )
                },
                "host": host,
                "http_status_counts": dict(
                    sorted(values["http_status_counts"].items())
                ),
                "failure_class_counts": dict(
                    sorted(values["failure_class_counts"].items())
                ),
            }
        )
    host_rows.sort(key=lambda item: item["host"])

    return {
        "meta": {
            "schema_version": "document_fetch_operations_v1",
            "generated_at": generated_at,
            "pipeline_id": PIPELINE_ID,
            "source_db": repo_path(db_path),
            "network_run_performed": False,
        },
        "policy": {
            "data_origin": "official_public_documents_only",
            "synthetic_or_mock_records": "forbidden",
            "public_domain_personal_information": "retained",
            "raw_urls_or_error_samples_published": False,
            "worker_policy_scope": "configured_guardrail_for_subsequent_runs",
        },
        "worker_policy": {
            "global_workers": int(global_workers),
            "per_host_workers": int(per_host_workers),
            "per_host_min_interval_ms": int(per_host_min_interval_ms),
            "max_document_bytes": int(max_document_bytes),
            "streaming_content_addressed_storage": True,
            "atomic_leases": True,
            "heartbeat_and_reclaim": True,
            "retry_and_dead_letter_states": True,
            "cohort_circuit_breakers": True,
            "per_host_slo_report_on_worker_runs": True,
        },
        "queue": {
            "items_total": len(queue_rows),
            "state_counts": queue_counts,
            "unfinished_total": unfinished_total,
            "terminal_total": terminal_total,
            "attempts_total": attempts_total,
            "retry_attempts_total": retry_attempts_total,
            "max_attempts_observed": max_attempts_observed,
            "attempt_status_counts": {
                str(row["status"]): int(row["total"]) for row in attempt_rows
            },
            "overdue_leases_total": overdue_leases_total,
            "oldest_created_at": oldest_created_at,
            "latest_updated_at": latest_updated_at,
        },
        "documents": {
            "official_url_sightings_total": int(document_row["sightings"] or 0),
            "official_urls_total": unique_urls,
            "source_record_linked_urls_total": linked_urls,
            "source_record_missing_urls_total": unique_urls - linked_urls,
            "fetched_succeeded_total": fetched_succeeded_total,
            "fetched_failed_total": fetched_failed_total,
            "missing_fetch_rows_total": missing_fetch_rows_total,
            "bytes_received": bytes_received,
            "url_scheme_counts": dict(sorted(schemes.items())),
            "http_status_counts": dict(sorted(fetch_status_counts.items())),
            "failure_class_counts": dict(sorted(failure_class_counts.items())),
        },
        "hosts": host_rows,
        "integrity": {
            "queue_balance_passed": len(queue_rows)
            == terminal_total + unfinished_total,
            "document_queue_parity_passed": unique_urls == len(queue_rows),
            "succeeded_fetch_parity_passed": queue_counts["succeeded"]
            == fetched_succeeded_total,
            "fetch_rows_parity_passed": len(queue_rows)
            == fetched_succeeded_total
            + fetched_failed_total
            + missing_fetch_rows_total,
            "orphan_partial_files_total": partial_files_total,
            "official_host_allowlist_passed": set(hosts) == {"www.senado.es"},
            "official_https_only": dict(schemes) == {"https": len(queue_rows)},
            "plaintext_http_urls_total": int(schemes.get("http", 0)),
        },
        "scale_claim": {
            "operational_contract_status": "partial",
            "one_million_documents_processed": terminal_total >= 1_000_000,
            "promoted_for_unbounded_operation": False,
            "next_gate": "complete_measured_real_cohorts_100_1000_10000_100000_before_one_million",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--global-workers", type=int, default=8)
    parser.add_argument("--per-host-workers", type=int, default=2)
    parser.add_argument("--per-host-min-interval-ms", type=int, default=500)
    parser.add_argument("--max-document-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence-out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR missing DB: {repo_path(db_path)}")
        return 2
    generated_at = (
        str(args.generated_at or "").strip()
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        payload = build_payload(
            db_path=db_path,
            raw_root=Path(args.raw_root),
            generated_at=generated_at,
            global_workers=int(args.global_workers),
            per_host_workers=int(args.per_host_workers),
            per_host_min_interval_ms=int(args.per_host_min_interval_ms),
            max_document_bytes=int(args.max_document_bytes),
        )
        atomic_write_json(Path(args.out), payload)
        if str(args.evidence_out or "").strip():
            atomic_write_json(Path(args.evidence_out), payload)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR document-fetch operations export: {exc}")
        return 2
    print(
        "OK document-fetch operations -> "
        f"{args.out} (official_urls={payload['documents']['official_urls_total']} "
        f"terminal={payload['queue']['terminal_total']} "
        f"pending={payload['queue']['unfinished_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
