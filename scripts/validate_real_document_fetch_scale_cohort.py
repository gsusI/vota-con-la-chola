#!/usr/bin/env python3
"""Independently validate the fresh 1,000-object real document acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


EXPECTED_HOST_ROWS = {
    "www.boe.es": 914,
    "www.parlamentodeandalucia.es": 86,
}
EXPECTED_MODES = {
    "boe_document_identifier": 800,
    "boe_summary_structure": 114,
    "parliament_html_semantic": 51,
    "parliament_pdf_signature": 35,
}


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


def safe_repo_file(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {value}")
    resolved = (Path.cwd() / path).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError(f"repository path escapes root: {value}") from exc
    return resolved


def safe_fresh_path(raw_root: Path, stored_path: str) -> Path:
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve()
    try:
        resolved.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError(f"stored raw path escapes cohort root: {stored_path}") from exc
    return resolved


def semantic_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "source_pipeline_id",
        "source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
    )
    return [{field: row.get(field) for field in fields} for row in rows]


def semantic_sha256(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        semantic_projection(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_fresh_contract(
    *, row: dict[str, Any], content_type: str, fresh_path: Path
) -> list[str]:
    errors: list[str] = []
    source_url = str(row.get("source_url") or "")
    payload = row.get("payload") or {}
    contract = payload.get("validation_contract") or {}
    parsed = urlparse(source_url)
    if not isinstance(contract, dict):
        return [f"validation contract is not an object: {source_url}"]
    if contract.get("require_https") is True and parsed.scheme != "https":
        errors.append(f"validation contract HTTPS mismatch: {source_url}")
    expected_host = str(contract.get("expected_host") or "").lower()
    if expected_host and (parsed.hostname or "").lower() != expected_host:
        errors.append(f"validation contract host mismatch: {source_url}")
    minimum_bytes = int(contract.get("minimum_bytes") or 0)
    if fresh_path.stat().st_size < minimum_bytes:
        errors.append(f"validation contract minimum bytes mismatch: {source_url}")
    allowed_types = contract.get("allowed_content_types")
    if allowed_types is not None:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        normalized_allowed = {
            str(value).strip().lower() for value in allowed_types if str(value).strip()
        }
        if normalized_type not in normalized_allowed:
            errors.append(f"validation contract content type mismatch: {source_url}")
    required = contract.get("required_ascii_casefolded") or []
    forbidden = contract.get("forbidden_ascii_casefolded") or []
    if required or forbidden:
        with fresh_path.open("rb") as handle:
            body = handle.read(1024 * 1024).lower()
        for marker in required:
            try:
                marker_bytes = str(marker).encode("ascii").lower()
            except UnicodeEncodeError:
                errors.append(f"validation contract marker is not ASCII: {source_url}")
                continue
            if marker_bytes not in body:
                errors.append(f"required semantic marker missing: {source_url}")
        for marker in forbidden:
            try:
                marker_bytes = str(marker).encode("ascii").lower()
            except UnicodeEncodeError:
                errors.append(f"validation contract marker is not ASCII: {source_url}")
                continue
            if marker_bytes in body:
                errors.append(f"forbidden block marker present: {source_url}")
    return errors


def validate_boe_structure(*, row: dict[str, Any], fresh_path: Path) -> list[str]:
    errors: list[str] = []
    source_url = str(row.get("source_url") or "")
    mode = str(row.get("validation_mode") or "")
    parsed = urlparse(source_url)
    with fresh_path.open("rb") as handle:
        prefix = handle.read(128 * 1024).lstrip()
    if mode == "boe_summary_structure":
        if not re.fullmatch(r"/datosabiertos/api/boe/sumario/\d{8}", parsed.path):
            errors.append(f"BOE summary URL contract mismatch: {source_url}")
        is_json = prefix.startswith(b"{") and b'"sumario"' in prefix
        is_xml = (
            prefix.startswith(b"<?xml")
            and b"<response" in prefix
            and b"<sumario" in prefix
        )
        if not is_json and not is_xml:
            errors.append(f"BOE summary payload contract mismatch: {source_url}")
        return errors
    if mode != "boe_document_identifier":
        return errors
    expected_ids = parse_qs(parsed.query).get("id") or []
    if (
        parsed.path != "/diario_boe/xml.php"
        or len(expected_ids) != 1
        or not re.fullmatch(
            r"BOE-[A-Z]-\d{4}-\d+", expected_ids[0], flags=re.IGNORECASE
        )
    ):
        errors.append(f"BOE document URL contract mismatch: {source_url}")
        return errors
    identifier_match = re.search(
        rb"<identificador>\s*(BOE-[A-Z]-\d{4}-\d+)\s*</identificador>",
        prefix,
        flags=re.IGNORECASE,
    )
    if not prefix.startswith(b"<?xml") or identifier_match is None:
        errors.append(f"BOE document XML contract mismatch: {source_url}")
    elif identifier_match.group(1).decode("ascii").upper() != expected_ids[0].upper():
        errors.append(f"BOE document identifier mismatch: {source_url}")
    return errors


def validate(
    *, manifest_path: Path, run_report_path: Path, db_path: Path, raw_root: Path
) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read_json(manifest_path)
    run_report = read_json(run_report_path)
    if manifest.get("schema_version") != "real_document_fetch_scale_cohort_v2":
        errors.append("manifest schema mismatch")
    if run_report.get("schema_version") != "document_fetch_queue_run_v3":
        errors.append("run report schema mismatch")
    if run_report.get("status") != "ok":
        errors.append("run status is not ok")
    expected_policy = {
        "official_real_documents_only": True,
        "synthetic_or_mock_records_counted": False,
        "official_public_domain_personal_information_retained": True,
        "known_blocked_rows_selected": 0,
        "dynamic_official_html_requires_semantic_contract": True,
        "official_content_revisions_preserved_and_measured": True,
    }
    policy = manifest.get("policy") or {}
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} mismatch")

    rows = manifest.get("rows") or []
    if len(rows) != 1000:
        errors.append(f"manifest row count mismatch: {len(rows)}")
    expected_by_url = {str(row.get("source_url") or ""): row for row in rows}
    if len(expected_by_url) != len(rows) or "" in expected_by_url:
        errors.append("manifest URLs are empty or duplicated")
    cohort_semantic_sha256 = semantic_sha256(rows)
    if manifest.get("cohort_semantic_sha256") != cohort_semantic_sha256:
        errors.append("cohort semantic hash mismatch")
    selection = manifest.get("selection") or {}
    if selection.get("hosts") != EXPECTED_HOST_ROWS:
        errors.append("manifest host allocation mismatch")
    if selection.get("validation_modes") != EXPECTED_MODES:
        errors.append("manifest validation-mode allocation mismatch")

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
                   content_type, content_sha256, bytes, raw_path
            FROM document_fetches
            ORDER BY doc_url
            """
        ).fetchall()
        document_rows = conn.execute(
            """
            SELECT source_url, source_id, content_type, content_sha256, bytes, raw_path
            FROM text_documents
            ORDER BY source_url
            """
        ).fetchall()
    finally:
        conn.close()

    queue_by_url = {str(row["item_key"]): row for row in queue_rows}
    fetch_by_url = {str(row["doc_url"]): row for row in fetch_rows}
    document_by_url = {str(row["source_url"]): row for row in document_rows}
    prior_files_rehashed = 0
    fresh_files_rehashed = 0
    fresh_bytes = 0
    exact_matches = 0
    drifted_rows = 0
    source_contract_rows = 0
    source_contract_parity = True
    host_actual_rows: dict[str, int] = {}
    host_actual_bytes: dict[str, int] = {}
    drift_by_kind: dict[str, int] = {}
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
        if (
            int(fetch["fetched_ok"] or 0) != 1
            or int(fetch["last_http_status"] or 0) != 200
        ):
            errors.append(f"fetch terminal status mismatch: {source_url}")
        for label, db_row in (("fetch", fetch), ("document", document)):
            if str(db_row["source_id"] or "") != str(expected.get("source_id") or ""):
                errors.append(f"{label} source mismatch: {source_url}")
            if str(db_row["content_sha256"] or "") != str(fetch["content_sha256"] or ""):
                errors.append(f"{label} fresh hash inconsistency: {source_url}")
            if int(db_row["bytes"] or 0) != int(fetch["bytes"] or 0):
                errors.append(f"{label} fresh byte inconsistency: {source_url}")
        try:
            prior_path = safe_repo_file(str(expected.get("captured_raw_path") or ""))
            fresh_path = safe_fresh_path(raw_root, str(fetch["raw_path"] or ""))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        expected_bytes = int(expected.get("expected_bytes") or 0)
        expected_sha256 = str(expected.get("expected_content_sha256") or "")
        if not prior_path.is_file():
            errors.append(f"prior captured file missing: {source_url}")
            continue
        prior_files_rehashed += 1
        if prior_path.stat().st_size != expected_bytes or sha256_path(prior_path) != expected_sha256:
            errors.append(f"prior captured file drift: {source_url}")
        if not fresh_path.is_file():
            errors.append(f"fresh raw file missing: {source_url}")
            continue
        actual_bytes = fresh_path.stat().st_size
        actual_sha256 = sha256_path(fresh_path)
        fresh_files_rehashed += 1
        fresh_bytes += actual_bytes
        host = str(expected.get("source_host") or "")
        host_actual_rows[host] = host_actual_rows.get(host, 0) + 1
        host_actual_bytes[host] = host_actual_bytes.get(host, 0) + actual_bytes
        if actual_sha256 != str(fetch["content_sha256"] or ""):
            errors.append(f"fresh raw hash differs from database: {source_url}")
        if actual_bytes != int(fetch["bytes"] or 0):
            errors.append(f"fresh raw bytes differ from database: {source_url}")
        if actual_sha256 == expected_sha256 and actual_bytes == expected_bytes:
            exact_matches += 1
        else:
            drifted_rows += 1
            kind = str(expected.get("document_kind") or "unknown")
            drift_by_kind[kind] = drift_by_kind.get(kind, 0) + 1
        mode = str(expected.get("validation_mode") or "")
        if mode not in EXPECTED_MODES:
            errors.append(f"unknown validation mode: {source_url}")
            continue
        source_contract_rows += 1
        contract_errors = validate_fresh_contract(
            row=expected,
            content_type=str(fetch["content_type"] or ""),
            fresh_path=fresh_path,
        )
        if mode.startswith("boe_"):
            contract_errors.extend(
                validate_boe_structure(row=expected, fresh_path=fresh_path)
            )
        if contract_errors:
            source_contract_parity = False
            errors.extend(contract_errors)

    totals = run_report.get("totals") or {}
    performance = run_report.get("performance") or {}
    host_slos = run_report.get("host_slos") or []
    requests_started = sum(int(row.get("requests_started") or 0) for row in host_slos)
    host_successes = sum(int(row.get("successes") or 0) for row in host_slos)
    host_failures = sum(int(row.get("failures") or 0) for row in host_slos)
    host_bytes = sum(int(row.get("bytes_received") or 0) for row in host_slos)
    host_request_counts = {
        str(row.get("host") or ""): int(row.get("requests_started") or 0)
        for row in host_slos
    }
    host_success_counts = {
        str(row.get("host") or ""): int(row.get("successes") or 0)
        for row in host_slos
    }
    succeeded = int(totals.get("succeeded") or 0)
    if int(totals.get("claimed") or 0) != len(rows) or succeeded != len(rows):
        errors.append("run claimed/succeeded totals do not match cohort")
    if int(totals.get("retried") or 0) != 0 or int(totals.get("dead") or 0) != 0:
        errors.append("fresh cohort has retries or dead rows")
    if int(totals.get("bytes_received") or 0) != fresh_bytes:
        errors.append("run bytes do not match fresh files")
    if requests_started != int(performance.get("network_requests_started") or 0):
        errors.append("network request telemetry does not reconcile")
    network_request_upper_bound = int(
        performance.get("network_request_upper_bound") or 0
    )
    if (
        requests_started < len(rows)
        or requests_started > network_request_upper_bound
        or host_successes != len(rows)
        or host_failures != requests_started - host_successes
    ):
        errors.append("host request outcomes exceed the bounded retry envelope")
    if host_failures > max(1, len(rows) // 50):
        errors.append("network-attempt failure rate exceeds two percent")
    if host_bytes != fresh_bytes:
        errors.append("host bytes do not reconcile with fresh files")
    if host_success_counts != EXPECTED_HOST_ROWS:
        errors.append("host success allocation mismatch")
    if host_actual_rows != EXPECTED_HOST_ROWS:
        errors.append("fresh-file host allocation mismatch")
    host_policy = run_report.get("host_policy") or {}
    if int(host_policy.get("per_host_min_interval_ms") or 0) < 500:
        errors.append("per-host minimum interval is below 500ms")
    for row in host_slos:
        if int(row.get("peak_inflight") or 0) > int(
            host_policy.get("per_host_workers") or 0
        ):
            errors.append(f"host peak inflight exceeds limit: {row.get('host')}")
    for key in ("elapsed_seconds", "cpu_seconds", "peak_rss_bytes"):
        if float(performance.get(key) or 0) <= 0:
            errors.append(f"performance.{key} is not positive")
    if integrity != "ok" or foreign_keys:
        errors.append("cohort database integrity or foreign keys failed")
    if (
        len(queue_rows) != len(rows)
        or len(fetch_rows) != len(rows)
        or len(document_rows) != len(rows)
    ):
        errors.append("cohort database row totals do not reconcile")
    if source_contract_rows != len(rows):
        errors.append("source-contract validation row count mismatch")

    denominator = succeeded or 1
    return {
        "schema_version": "real_document_fetch_scale_cohort_validation_v2",
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
            "prior_files_rehashed": prior_files_rehashed,
            "fresh_files_rehashed": fresh_files_rehashed,
            "fresh_bytes_reconciled": fresh_bytes,
            "network_requests_started": requests_started,
            "network_retry_attempts": max(0, requests_started - len(rows)),
            "network_request_upper_bound": network_request_upper_bound,
            "host_successes": host_successes,
            "host_failures": host_failures,
            "database_integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "prior_capture_byte_hash_integrity": not any(
                "prior captured file" in error for error in errors
            ),
            "source_contract_rows": source_contract_rows,
            "fresh_source_contract_parity": source_contract_parity,
            "fresh_content_hash_self_consistency": not any(
                "fresh raw" in error or "fresh hash inconsistency" in error
                for error in errors
            ),
        },
        "content_drift": {
            "exact_matches": exact_matches,
            "drifted_rows": drifted_rows,
            "drift_by_document_kind": dict(sorted(drift_by_kind.items())),
            "drift_is_allowed_when_fresh_source_contract_passes": True,
        },
        "hosts": {
            host: {
                "rows": host_actual_rows.get(host, 0),
                "bytes": host_actual_bytes.get(host, 0),
                "network_requests": host_request_counts.get(host, 0),
                "network_successes": host_success_counts.get(host, 0),
            }
            for host in sorted(EXPECTED_HOST_ROWS)
        },
        "per_1000_succeeded": {
            "network_requests_started": round(requests_started * 1000 / denominator, 6),
            "bytes_received": round(fresh_bytes * 1000 / denominator, 6),
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
        print(f"ERROR real document fetch scale cohort validation: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
