#!/usr/bin/env python3
"""Compact digest for initdoc heartbeat raw-vs-compacted parity."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initdoc actionable-tail compaction-window digest report")
    p.add_argument(
        "--compaction-window-json",
        required=True,
        help=(
            "Path to JSON emitted by "
            "scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py"
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when digest status is failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value: Any) -> bool:
    return bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(v) for v in value if _safe_text(v)]


def _round4(value: float) -> float:
    return round(float(value), 4)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = _safe_text(value)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _determine_status(*, missing_any: bool, strict_fail_reasons: list[str], risk_reasons: list[str]) -> str:
    if len(strict_fail_reasons) > 0:
        return "failed"
    if missing_any or len(risk_reasons) > 0:
        return "degraded"
    return "ok"


def _risk_level_for_status(status: str) -> str:
    token = _safe_text(status).lower()
    if token == "ok":
        return "green"
    if token == "degraded":
        return "amber"
    return "red"


def _validate_digest(digest: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    input_obj = _safe_obj(digest.get("input"))
    if not _safe_text(input_obj.get("compaction_window_generated_at")):
        reasons.append("missing_compaction_window_generated_at")

    status = _safe_text(digest.get("status")).lower()
    if status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    risk_level = _safe_text(digest.get("risk_level")).lower()
    if risk_level not in {"green", "amber", "red"}:
        reasons.append("invalid_risk_level")

    metrics = _safe_obj(digest.get("key_metrics"))
    if _to_int(metrics.get("entries_total_raw"), -1) < 0:
        reasons.append("invalid_entries_total_raw")
    if _to_int(metrics.get("entries_total_compacted"), -1) < 0:
        reasons.append("invalid_entries_total_compacted")
    if _to_int(metrics.get("window_raw_entries"), -1) < 0:
        reasons.append("invalid_window_raw_entries")
    if _to_int(metrics.get("raw_window_incidents"), -1) < 0:
        reasons.append("invalid_raw_window_incidents")
    if _to_int(metrics.get("present_in_compacted_in_window"), -1) < 0:
        reasons.append("invalid_present_in_compacted_in_window")
    if _to_int(metrics.get("missing_in_compacted_in_window"), -1) < 0:
        reasons.append("invalid_missing_in_compacted_in_window")
    if _to_int(metrics.get("incident_missing_in_compacted"), -1) < 0:
        reasons.append("invalid_incident_missing_in_compacted")
    if _to_float(metrics.get("raw_window_coverage_pct"), -1.0) < 0:
        reasons.append("invalid_raw_window_coverage_pct")
    if _to_float(metrics.get("incident_coverage_pct"), -1.0) < 0:
        reasons.append("invalid_incident_coverage_pct")

    window_raw_entries = _to_int(metrics.get("window_raw_entries"), 0)
    present_count = _to_int(metrics.get("present_in_compacted_in_window"), 0)
    missing_count = _to_int(metrics.get("missing_in_compacted_in_window"), 0)
    if window_raw_entries != present_count + missing_count:
        reasons.append("window_presence_count_mismatch")

    strict_fail_count = _to_int(digest.get("strict_fail_count"), 0)
    strict_fail_len = len(_safe_list_str(digest.get("strict_fail_reasons")))
    if strict_fail_count != strict_fail_len:
        reasons.append("strict_fail_count_mismatch")

    risk_reason_count = _to_int(digest.get("risk_reason_count"), 0)
    risk_reason_len = len(_safe_list_str(digest.get("risk_reasons")))
    if risk_reason_count != risk_reason_len:
        reasons.append("risk_reason_count_mismatch")

    return reasons


def build_compaction_window_digest(
    parity_report: dict[str, Any],
    *,
    compaction_window_json_path: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    parity = _safe_obj(parity_report)
    checks = _safe_obj(parity.get("checks"))
    strict_fail_reasons = _safe_list_str(parity.get("strict_fail_reasons"))

    missing_any = _to_int(parity.get("missing_in_compacted_in_window"), 0) > 0
    missing_incident = _to_int(parity.get("incident_missing_in_compacted"), 0) > 0
    coverage_pct = _round4(_to_float(parity.get("raw_window_coverage_pct"), 0.0))
    incident_coverage_pct = _round4(_to_float(parity.get("incident_coverage_pct"), 0.0))
    raw_window_incidents = _to_int(parity.get("raw_window_incidents"), 0)

    risk_reasons: list[str] = []
    if (not missing_incident) and missing_any:
        risk_reasons.append("non_incident_rows_missing_in_compacted_window")
    if (not missing_incident) and missing_any and coverage_pct < 100.0:
        risk_reasons.append("raw_window_coverage_below_100")
    if raw_window_incidents > 0 and incident_coverage_pct < 100.0:
        risk_reasons.append("incident_coverage_below_100")

    status = _determine_status(
        missing_any=missing_any,
        strict_fail_reasons=strict_fail_reasons,
        risk_reasons=risk_reasons,
    )
    risk_level = _risk_level_for_status(status)

    digest: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "input": {
            "compaction_window_json_path": _safe_text(compaction_window_json_path),
            "compaction_window_generated_at": _safe_text(parity.get("generated_at")),
            "heartbeat_path": _safe_text(parity.get("heartbeat_path")),
            "compacted_path": _safe_text(parity.get("compacted_path")),
        },
        "status": status,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "strict_fail_reasons": strict_fail_reasons,
        "strict_fail_count": len(strict_fail_reasons),
        "risk_reason_count": len(risk_reasons),
        "key_metrics": {
            "entries_total_raw": _to_int(parity.get("entries_total_raw"), 0),
            "entries_total_compacted": _to_int(parity.get("entries_total_compacted"), 0),
            "window_raw_entries": _to_int(parity.get("window_raw_entries"), 0),
            "raw_window_incidents": raw_window_incidents,
            "present_in_compacted_in_window": _to_int(parity.get("present_in_compacted_in_window"), 0),
            "missing_in_compacted_in_window": _to_int(parity.get("missing_in_compacted_in_window"), 0),
            "incident_missing_in_compacted": _to_int(parity.get("incident_missing_in_compacted"), 0),
            "raw_window_coverage_pct": coverage_pct,
            "incident_coverage_pct": incident_coverage_pct,
        },
        "key_checks": {
            "window_nonempty_ok": _to_bool(checks.get("window_nonempty_ok")),
            "raw_window_malformed_ok": _to_bool(checks.get("raw_window_malformed_ok")),
            "compacted_malformed_ok": _to_bool(checks.get("compacted_malformed_ok")),
            "latest_present_ok": _to_bool(checks.get("latest_present_ok")),
            "incident_parity_ok": _to_bool(checks.get("incident_parity_ok")),
            "failed_parity_ok": _to_bool(checks.get("failed_parity_ok")),
            "degraded_parity_ok": _to_bool(checks.get("degraded_parity_ok")),
            "strict_rows_parity_ok": _to_bool(checks.get("strict_rows_parity_ok")),
            "malformed_parity_ok": _to_bool(checks.get("malformed_parity_ok")),
        },
        "thresholds": {
            "max_missing_in_compacted_window_for_ok": 0,
            "min_raw_window_coverage_pct_for_ok": 100.0,
            "min_incident_coverage_pct_for_ok": 100.0,
        },
        "validation_errors": [],
    }

    validation_errors = _validate_digest(digest)
    if validation_errors:
        digest["validation_errors"] = validation_errors
        merged_strict_reasons = _dedupe(
            list(digest.get("strict_fail_reasons") or [])
            + [f"validation:{reason}" for reason in validation_errors]
        )
        digest["strict_fail_reasons"] = merged_strict_reasons
        digest["strict_fail_count"] = len(merged_strict_reasons)
        digest["status"] = "failed"
        digest["risk_level"] = "red"
    return digest


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    parity_path = Path(str(args.compaction_window_json))
    if not parity_path.exists():
        print(json.dumps({"error": f"compaction-window json not found: {parity_path}"}, ensure_ascii=False))
        return 2

    try:
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid compaction-window json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(parity, dict):
        print(json.dumps({"error": "invalid compaction-window json: root must be object"}, ensure_ascii=False))
        return 3

    digest = build_compaction_window_digest(
        parity,
        compaction_window_json_path=str(parity_path),
        strict=bool(args.strict),
    )
    payload = json.dumps(digest, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out or "").strip()) if str(args.out or "").strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and _safe_text(digest.get("status")).lower() == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
