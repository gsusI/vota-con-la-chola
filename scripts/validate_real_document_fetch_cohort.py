#!/usr/bin/env python3
"""Validate a fresh real BOE acquisition cohort against prior official bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
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


def safe_raw_path(raw_root: Path, stored_path: str) -> Path:
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve()
    try:
        resolved.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError(f"stored raw path escapes cohort root: {stored_path}") from exc
    return resolved


def validate(
    *,
    manifest_path: Path,
    run_report_path: Path,
    db_path: Path,
    raw_root: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read_json(manifest_path)
    run_report = read_json(run_report_path)
    if manifest.get("schema_version") != "real_document_fetch_cohort_v1":
        errors.append("manifest schema mismatch")
    if run_report.get("schema_version") != "document_fetch_queue_run_v3":
        errors.append("run report schema mismatch")
    if run_report.get("status") != "ok":
        errors.append("run status is not ok")
    policy = manifest.get("policy") or {}
    expected_policy = {
        "official_real_documents_only": True,
        "synthetic_or_mock_records_counted": False,
        "official_public_domain_personal_information_retained": True,
        "known_blocked_rows_selected": 0,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} mismatch")

    rows = manifest.get("rows") or []
    if len(rows) != 100:
        errors.append(f"manifest row count mismatch: {len(rows)}")
    expected_by_url = {str(row.get("source_url") or ""): row for row in rows}
    if len(expected_by_url) != len(rows) or "" in expected_by_url:
        errors.append("manifest URLs are empty or duplicated")
    semantic_projection = [
        {
            "source_pipeline_id": row.get("source_pipeline_id"),
            "source_id": row.get("source_id"),
            "source_url": row.get("source_url"),
            "size_decile": row.get("size_decile"),
            "expected_bytes": row.get("expected_bytes"),
            "expected_content_sha256": row.get("expected_content_sha256"),
        }
        for row in rows
    ]
    semantic_bytes = json.dumps(
        semantic_projection,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    cohort_semantic_sha256 = hashlib.sha256(semantic_bytes).hexdigest()
    if manifest.get("cohort_semantic_sha256") != cohort_semantic_sha256:
        errors.append("cohort semantic hash mismatch")
    expected_bytes = sum(int(row.get("expected_bytes") or 0) for row in rows)

    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        queue_rows = conn.execute(
            """
            SELECT item_key, state, attempts, last_error
            FROM pipeline_work_items
            WHERE pipeline_id = ?
            ORDER BY item_key
            """,
            (str(manifest.get("pipeline_id") or ""),),
        ).fetchall()
        fetch_rows = conn.execute(
            """
            SELECT doc_url, source_id, fetched_ok, last_http_status,
                   content_sha256, bytes, raw_path
            FROM document_fetches
            ORDER BY doc_url
            """
        ).fetchall()
        document_rows = conn.execute(
            """
            SELECT source_url, source_id, content_sha256, bytes, raw_path
            FROM text_documents
            ORDER BY source_url
            """
        ).fetchall()
    finally:
        conn.close()

    queue_by_url = {str(row["item_key"]): row for row in queue_rows}
    fetch_by_url = {str(row["doc_url"]): row for row in fetch_rows}
    document_by_url = {str(row["source_url"]): row for row in document_rows}
    rehashed_files = 0
    actual_bytes = 0
    for source_url, expected in expected_by_url.items():
        queue = queue_by_url.get(source_url)
        fetch = fetch_by_url.get(source_url)
        document = document_by_url.get(source_url)
        if queue is None or str(queue["state"]) != "succeeded":
            errors.append(f"queue row not succeeded: {source_url}")
            continue
        if fetch is None or document is None:
            errors.append(f"fetch or text document row missing: {source_url}")
            continue
        expected_sha256 = str(expected.get("expected_content_sha256") or "")
        expected_row_bytes = int(expected.get("expected_bytes") or 0)
        for label, row in (("fetch", fetch), ("document", document)):
            if str(row["content_sha256"] or "") != expected_sha256:
                errors.append(f"{label} hash drift: {source_url}")
            if int(row["bytes"] or 0) != expected_row_bytes:
                errors.append(f"{label} byte drift: {source_url}")
        if (
            int(fetch["fetched_ok"] or 0) != 1
            or int(fetch["last_http_status"] or 0) != 200
        ):
            errors.append(f"fetch terminal status mismatch: {source_url}")
        try:
            raw_path = safe_raw_path(raw_root, str(fetch["raw_path"] or ""))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not raw_path.is_file():
            errors.append(f"fresh raw file missing: {source_url}")
            continue
        actual_size = raw_path.stat().st_size
        actual_bytes += actual_size
        rehashed_files += 1
        if actual_size != expected_row_bytes:
            errors.append(f"fresh raw size drift: {source_url}")
        if sha256_path(raw_path) != expected_sha256:
            errors.append(f"fresh raw hash drift: {source_url}")

    totals = run_report.get("totals") or {}
    performance = run_report.get("performance") or {}
    host_slos = run_report.get("host_slos") or []
    requests_started = sum(int(row.get("requests_started") or 0) for row in host_slos)
    host_successes = sum(int(row.get("successes") or 0) for row in host_slos)
    host_failures = sum(int(row.get("failures") or 0) for row in host_slos)
    host_bytes = sum(int(row.get("bytes_received") or 0) for row in host_slos)
    succeeded = int(totals.get("succeeded") or 0)
    claimed = int(totals.get("claimed") or 0)
    if claimed != len(rows) or succeeded != len(rows):
        errors.append("run claimed/succeeded totals do not match cohort")
    if int(totals.get("retried") or 0) != 0 or int(totals.get("dead") or 0) != 0:
        errors.append("fresh cohort has retries or dead rows")
    if int(totals.get("bytes_received") or 0) != expected_bytes:
        errors.append("run bytes do not match expected immutable bytes")
    if requests_started != int(performance.get("network_requests_started") or 0):
        errors.append("network request telemetry does not reconcile")
    if requests_started != len(rows) or host_successes != len(rows) or host_failures:
        errors.append("host request outcomes do not match clean one-request cohort")
    if host_bytes != expected_bytes or actual_bytes != expected_bytes:
        errors.append("host or fresh-object bytes do not reconcile")
    if len(host_slos) != 1 or str(host_slos[0].get("host") or "") != "www.boe.es":
        errors.append("unexpected fresh acquisition host set")
    host_policy = run_report.get("host_policy") or {}
    if int(host_policy.get("per_host_min_interval_ms") or 0) < 500:
        errors.append("per-host minimum interval is below 500ms")
    if host_slos and int(host_slos[0].get("peak_inflight") or 0) > int(
        host_policy.get("per_host_workers") or 0
    ):
        errors.append("host peak inflight exceeds configured limit")
    for key in ("elapsed_seconds", "cpu_seconds", "peak_rss_bytes"):
        if float(performance.get(key) or 0) <= 0:
            errors.append(f"performance.{key} is not positive")
    if integrity != "ok" or foreign_keys:
        errors.append("cohort database integrity or foreign keys failed")
    if len(queue_rows) != len(rows) or len(fetch_rows) != len(rows):
        errors.append("cohort database row totals do not reconcile")

    denominator = succeeded or 1
    return {
        "schema_version": "real_document_fetch_cohort_validation_v1",
        "status": "ok" if not errors else "error",
        "cohort_id": str(manifest.get("cohort_id") or ""),
        "cohort_semantic_sha256": cohort_semantic_sha256,
        "policy": expected_policy,
        "inputs": {
            "manifest": {
                "path": repo_path(manifest_path),
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256_path(manifest_path),
            },
            "run_report": {
                "path": repo_path(run_report_path),
                "bytes": run_report_path.stat().st_size,
                "sha256": sha256_path(run_report_path),
            },
            "database": {
                "path": repo_path(db_path),
                "bytes": db_path.stat().st_size,
                "sha256": sha256_path(db_path),
            },
        },
        "checks": {
            "cohort_rows": len(rows),
            "fresh_files_rehashed": rehashed_files,
            "fresh_bytes_reconciled": actual_bytes,
            "network_requests_started": requests_started,
            "host_successes": host_successes,
            "host_failures": host_failures,
            "database_integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "immutable_byte_hash_parity": not any("drift" in error for error in errors),
        },
        "per_1000_succeeded": {
            "network_requests_started": round(requests_started * 1000 / denominator, 6),
            "bytes_received": round(actual_bytes * 1000 / denominator, 6),
            "elapsed_seconds": round(
                float(performance.get("elapsed_seconds") or 0) * 1000 / denominator,
                6,
            ),
            "cpu_seconds": round(
                float(performance.get("cpu_seconds") or 0) * 1000 / denominator,
                6,
            ),
            "failures": round(host_failures * 1000 / denominator, 6),
        },
        "performance": {
            "elapsed_seconds": float(performance.get("elapsed_seconds") or 0),
            "cpu_seconds": float(performance.get("cpu_seconds") or 0),
            "peak_rss_bytes": int(performance.get("peak_rss_bytes") or 0),
            "workers": int(run_report.get("workers") or 0),
            "per_host_workers": int(run_report.get("per_host_workers") or 0),
            "per_host_min_interval_ms": int(
                host_policy.get("per_host_min_interval_ms") or 0
            ),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run-report", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = validate(
            manifest_path=Path(args.manifest),
            run_report_path=Path(args.run_report),
            db_path=Path(args.db),
            raw_root=Path(args.raw_root),
        )
        write_json_atomic(Path(args.out), report)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR real document fetch cohort validation: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
