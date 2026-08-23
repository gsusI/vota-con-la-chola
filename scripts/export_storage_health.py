#!/usr/bin/env python3
"""Export public-safe storage capacity status from real acquisition preflights."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LANE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
FORBIDDEN_PUBLIC_MARKERS = ("/Users/", "/home/", "file:///", "Bearer ", "cookie")
ALLOWED_EVIDENCE_SCHEMAS = {
    "bdns_worker_storage_preflight_v1",
    "placsp_archive_worker_v2",
}


class StorageHealthError(RuntimeError):
    """Raised when source evidence cannot produce a trustworthy public status."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise StorageHealthError("storage evidence paths must be repository-relative")
    resolved = (REPO_ROOT / path).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise StorageHealthError("storage evidence path escapes repository") from exc
    if not resolved.is_file():
        raise StorageHealthError(f"missing storage evidence: {raw_path}")
    return resolved


def parse_lane_spec(spec: str) -> tuple[str, str]:
    lane_id, separator, raw_path = spec.partition("=")
    if not separator or not LANE_ID_RE.fullmatch(lane_id) or not raw_path:
        raise StorageHealthError(f"invalid lane specification: {spec!r}")
    return lane_id, raw_path


def nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise StorageHealthError(f"{field} must be a nonnegative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise StorageHealthError(f"{field} must be a nonnegative integer") from exc
    if result < 0:
        raise StorageHealthError(f"{field} must be a nonnegative integer")
    return result


def signed_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise StorageHealthError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StorageHealthError(f"{field} must be an integer") from exc


def extract_preflight(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("storage_preflight"), dict):
        return payload["storage_preflight"]
    checks = payload.get("checks")
    if isinstance(checks, list) and len(checks) == 1 and isinstance(checks[0], dict):
        return checks[0]
    raise StorageHealthError("storage evidence has no unambiguous preflight contract")


def audit_lane(lane_id: str, raw_path: str) -> dict[str, Any]:
    path = repo_path(raw_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageHealthError(f"invalid storage evidence: {raw_path}") from exc
    if not isinstance(payload, dict):
        raise StorageHealthError(f"storage evidence must be a JSON object: {raw_path}")
    schema_version = payload.get("schema_version")
    if schema_version not in ALLOWED_EVIDENCE_SCHEMAS:
        raise StorageHealthError(f"unsupported storage evidence schema for {lane_id}")

    preflight = extract_preflight(payload)
    free_bytes = nonnegative_int(preflight.get("free_bytes"), "free_bytes")
    minimum_free_bytes = nonnegative_int(
        preflight.get("min_free_bytes"), "min_free_bytes"
    )
    reserve_bytes = nonnegative_int(preflight.get("reserve_bytes"), "reserve_bytes")
    required_free_bytes = nonnegative_int(
        preflight.get("required_free_bytes"), "required_free_bytes"
    )
    headroom_bytes = signed_int(preflight.get("headroom_bytes"), "headroom_bytes")
    if required_free_bytes != minimum_free_bytes + reserve_bytes:
        raise StorageHealthError(f"required storage arithmetic mismatch for {lane_id}")
    if headroom_bytes != free_bytes - required_free_bytes:
        raise StorageHealthError(f"storage headroom arithmetic mismatch for {lane_id}")

    ready = preflight.get("ready")
    if not isinstance(ready, bool):
        raise StorageHealthError(f"storage ready flag missing for {lane_id}")
    if ready != (headroom_bytes >= 0):
        raise StorageHealthError(
            f"storage ready flag contradicts headroom for {lane_id}"
        )
    expected_status = "ok" if ready else "blocked_storage"
    if payload.get("status") != expected_status:
        raise StorageHealthError(f"storage status contradicts preflight for {lane_id}")

    relative_path = path.relative_to(REPO_ROOT).as_posix()
    return {
        "id": lane_id,
        "status": "ready" if ready else "blocked_storage",
        "free_bytes": free_bytes,
        "minimum_free_after_work_bytes": minimum_free_bytes,
        "work_reserve_bytes": reserve_bytes,
        "required_free_bytes": required_free_bytes,
        "headroom_bytes": headroom_bytes,
        "additional_bytes_required": max(0, -headroom_bytes),
        "evidence": {
            "path": relative_path,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "schema_version": schema_version,
        },
    }


def build_report(lane_specs: list[str]) -> dict[str, Any]:
    parsed = [parse_lane_spec(spec) for spec in lane_specs]
    lane_ids = [lane_id for lane_id, _ in parsed]
    if len(lane_ids) != len(set(lane_ids)):
        raise StorageHealthError("storage lane IDs must be unique")
    lanes = sorted(
        (audit_lane(lane_id, raw_path) for lane_id, raw_path in parsed),
        key=lambda lane: lane["id"],
    )
    if not lanes:
        raise StorageHealthError("at least one storage lane is required")

    blocked = [lane for lane in lanes if lane["status"] == "blocked_storage"]
    report = {
        "schema_version": "public_storage_health_v1",
        "generated_at": utc_now(),
        "status": "blocked_storage" if blocked else "ready",
        "policy": {
            "real_preflight_evidence_only": True,
            "workstation_paths_forbidden": True,
            "credentials_and_session_state_forbidden": True,
            "official_public_domain_personal_information_unchanged": True,
        },
        "summary": {
            "lanes_total": len(lanes),
            "lanes_ready": len(lanes) - len(blocked),
            "lanes_blocked_storage": len(blocked),
            "largest_additional_bytes_required": max(
                lane["additional_bytes_required"] for lane in lanes
            ),
        },
        "lanes": lanes,
        "checks": {
            "source_contracts_valid": True,
            "storage_arithmetic_reconciled": True,
            "public_output_contains_no_workstation_paths_or_secrets": True,
        },
        "next_action": (
            "Restore the declared headroom for every blocked lane, rerun each real "
            "preflight before claim or network work, then regenerate this artifact."
        ),
    }
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if any(marker.lower() in serialized.lower() for marker in FORBIDDEN_PUBLIC_MARKERS):
        raise StorageHealthError("public storage report contains a forbidden marker")
    return report


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lane",
        action="append",
        required=True,
        help="Lane and repository-relative evidence path as lane_id=path.json",
    )
    parser.add_argument("--out", required=True, help="Repository-relative output JSON")
    parser.add_argument("--enforce-ready", action="store_true")
    args = parser.parse_args()
    output = Path(args.out)
    if output.is_absolute():
        raise StorageHealthError("output path must be repository-relative")
    output = (REPO_ROOT / output).resolve()
    try:
        output.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise StorageHealthError("output path escapes repository") from exc
    report = build_report(args.lane)
    write_json_atomic(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if args.enforce_ready and report["status"] != "ready" else 0


if __name__ == "__main__":
    raise SystemExit(main())
