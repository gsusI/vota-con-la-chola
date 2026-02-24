#!/usr/bin/env python3
"""Append-only heartbeat lane for citizen release-trace digest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DIGEST_JSON = Path("docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_release_trace_digest_heartbeat.jsonl")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        token = _safe_text(item)
        if token:
            out.append(token)
    return out


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _fmt_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _dedupe_ordered(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _safe_text(value)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for citizen release-trace digest")
    p.add_argument(
        "--digest-json",
        default=str(DEFAULT_DIGEST_JSON),
        help=f"Input release-trace digest JSON (default: {DEFAULT_DIGEST_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when heartbeat is invalid or status=failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def _stale_detected(*, freshness_within_sla: bool | None, degraded_reasons: list[str]) -> bool:
    if freshness_within_sla is False:
        return True
    return "release_trace_stale" in {_safe_text(x) for x in degraded_reasons}


def build_heartbeat(
    digest_payload: dict[str, Any],
    *,
    digest_path: str,
) -> dict[str, Any]:
    digest = _safe_obj(digest_payload)
    if "status" not in digest and isinstance(digest.get("digest"), dict):
        digest = _safe_obj(digest.get("digest"))

    checks = _safe_obj(digest.get("checks"))
    release_trace = _safe_obj(digest.get("release_trace"))
    thresholds = _safe_obj(digest.get("thresholds"))

    status = _normalize_status(digest.get("status"))
    run_at = _safe_text(digest.get("generated_at")) or now_utc_iso()
    digest_generated_at = _safe_text(digest.get("generated_at"))
    release_generated_at = _safe_text(release_trace.get("release_generated_at"))

    release_age_minutes = _safe_float(release_trace.get("release_age_minutes"))
    max_age_minutes = _safe_float(thresholds.get("max_age_minutes"))
    release_ready = bool(release_trace.get("release_ready"))
    release_total_fail = _to_int(release_trace.get("release_total_fail"), 0)
    release_failed_ids_total = _to_int(release_trace.get("release_failed_ids_total"), 0)
    parity_ok_assets = _to_int(release_trace.get("parity_ok_assets"), 0)
    parity_total_assets = _to_int(release_trace.get("parity_total_assets"), 0)

    freshness_within_sla: bool | None
    if "freshness_within_sla" in checks:
        freshness_within_sla = bool(checks.get("freshness_within_sla"))
    elif release_age_minutes is not None and max_age_minutes is not None:
        freshness_within_sla = bool(release_age_minutes <= max_age_minutes)
    else:
        freshness_within_sla = None

    contract_complete = bool(checks.get("contract_complete"))
    degraded_reasons = _safe_list_str(digest.get("degraded_reasons"))
    failure_reasons = _safe_list_str(digest.get("failure_reasons"))

    stale_detected = _stale_detected(freshness_within_sla=freshness_within_sla, degraded_reasons=degraded_reasons)

    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.extend(failure_reasons)
        if not failure_reasons:
            strict_fail_reasons.append("release_trace_failed_without_reason")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            release_generated_at,
            _fmt_float(release_age_minutes),
            _fmt_float(max_age_minutes),
            "1" if freshness_within_sla is True else ("0" if freshness_within_sla is False else ""),
            "1" if release_ready else "0",
            str(release_total_fail),
            "1" if stale_detected else "0",
            ",".join(failure_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "digest_path": _safe_text(digest_path),
        "digest_generated_at": digest_generated_at,
        "release_generated_at": release_generated_at,
        "status": status,
        "release_age_minutes": round(float(release_age_minutes), 6) if release_age_minutes is not None else None,
        "max_age_minutes": round(float(max_age_minutes), 6) if max_age_minutes is not None else None,
        "freshness_within_sla": freshness_within_sla,
        "stale_detected": bool(stale_detected),
        "release_ready": release_ready,
        "release_total_fail": release_total_fail,
        "release_failed_ids_total": release_failed_ids_total,
        "parity_ok_assets": parity_ok_assets,
        "parity_total_assets": parity_total_assets,
        "contract_complete": contract_complete,
        "degraded_reasons": degraded_reasons,
        "failure_reasons": failure_reasons,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }


def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")

    raw_status = _safe_text(heartbeat.get("status")).lower()
    if raw_status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    release_age_minutes = _safe_float(heartbeat.get("release_age_minutes"))
    if release_age_minutes is not None and release_age_minutes < 0:
        reasons.append("negative_release_age_minutes")

    max_age_minutes = _safe_float(heartbeat.get("max_age_minutes"))
    if max_age_minutes is not None and max_age_minutes <= 0:
        reasons.append("invalid_max_age_minutes")

    freshness_raw = heartbeat.get("freshness_within_sla")
    if freshness_raw is not None and not isinstance(freshness_raw, bool):
        reasons.append("invalid_freshness_within_sla")
    if release_age_minutes is not None and max_age_minutes is not None and isinstance(freshness_raw, bool):
        expected = bool(release_age_minutes <= max_age_minutes)
        if bool(freshness_raw) != expected:
            reasons.append("freshness_consistency_mismatch")

    stale_detected = bool(heartbeat.get("stale_detected"))
    degraded_reasons = _safe_list_str(heartbeat.get("degraded_reasons"))
    expected_stale = _stale_detected(
        freshness_within_sla=freshness_raw if isinstance(freshness_raw, bool) else None,
        degraded_reasons=degraded_reasons,
    )
    if stale_detected != expected_stale:
        reasons.append("stale_detected_mismatch")

    for key in ("release_total_fail", "release_failed_ids_total", "parity_ok_assets", "parity_total_assets"):
        value = _to_int(heartbeat.get(key), -1)
        if value < 0:
            reasons.append(f"invalid_{key}")

    if bool(heartbeat.get("contract_complete")) and raw_status != "ok":
        reasons.append("contract_complete_status_mismatch")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    return _dedupe_ordered(reasons)


def read_history_entries(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    raw = history_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def history_has_heartbeat(rows: list[dict[str, Any]], heartbeat_id: str) -> bool:
    needle = _safe_text(heartbeat_id)
    if not needle:
        return False
    for row in rows:
        if bool(row.get("malformed_line")):
            continue
        entry = _safe_obj(row.get("entry"))
        if _safe_text(entry.get("heartbeat_id")) == needle:
            return True
    return False


def append_heartbeat(history_path: Path, heartbeat: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(heartbeat, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    digest_path = Path(str(args.digest_json))
    if not digest_path.exists():
        print(json.dumps({"error": f"digest json not found: {digest_path}"}, ensure_ascii=False))
        return 2

    try:
        digest_payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid digest json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(digest_payload, dict):
        print(json.dumps({"error": "invalid digest json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(digest_path),
        "heartbeat_path": str(heartbeat_path),
        "history_size_before": 0,
        "history_size_after": 0,
        "history_malformed_lines_before": 0,
        "appended": False,
        "duplicate_detected": False,
        "validation_errors": [],
        "strict_fail_reasons": [],
        "heartbeat": {},
        "status": "failed",
    }

    try:
        heartbeat = build_heartbeat(digest_payload, digest_path=str(digest_path))
        report["heartbeat"] = heartbeat
        report["validation_errors"] = validate_heartbeat(heartbeat)

        history_before = read_history_entries(heartbeat_path)
        report["history_size_before"] = len(history_before)
        report["history_malformed_lines_before"] = sum(1 for row in history_before if bool(row.get("malformed_line")))

        if not report["validation_errors"]:
            report["duplicate_detected"] = history_has_heartbeat(history_before, _safe_text(heartbeat.get("heartbeat_id")))
            if not report["duplicate_detected"]:
                append_heartbeat(heartbeat_path, heartbeat)
                report["appended"] = True

        report["history_size_after"] = int(report["history_size_before"]) + (1 if report["appended"] else 0)
    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["strict_fail_reasons"] = [f"runtime_error:{type(exc).__name__}"]
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        print(payload)
        out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        return 3

    strict_fail_reasons: list[str] = []
    for reason in _safe_list_str(report.get("validation_errors")):
        strict_fail_reasons.append(f"validation:{reason}")

    heartbeat_status = _normalize_status(_safe_obj(report.get("heartbeat")).get("status"))
    if heartbeat_status == "failed":
        strict_fail_reasons.append("heartbeat_status_failed")
        strict_fail_reasons.extend(_safe_list_str(_safe_obj(report.get("heartbeat")).get("strict_fail_reasons")))
    report["strict_fail_reasons"] = _dedupe_ordered(strict_fail_reasons)

    if report["validation_errors"]:
        report["status"] = "failed"
    elif heartbeat_status == "failed":
        report["status"] = "failed"
    elif heartbeat_status == "degraded":
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(_safe_list_str(report.get("strict_fail_reasons"))) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
