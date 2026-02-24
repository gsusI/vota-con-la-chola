#!/usr/bin/env python3
"""Windowed trend report for citizen product KPI heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_product_kpis_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_DEGRADED = 0
DEFAULT_MAX_DEGRADED_RATE_PCT = 0.0
DEFAULT_MAX_CONTRACT_INCOMPLETE = 0
DEFAULT_MAX_CONTRACT_INCOMPLETE_RATE_PCT = 0.0
DEFAULT_MAX_UNKNOWN_RATE_VIOLATIONS = 0
DEFAULT_MAX_UNKNOWN_RATE_VIOLATION_RATE_PCT = 0.0
DEFAULT_MAX_TFA_VIOLATIONS = 0
DEFAULT_MAX_TFA_VIOLATION_RATE_PCT = 0.0
DEFAULT_MAX_DRILLDOWN_VIOLATIONS = 0
DEFAULT_MAX_DRILLDOWN_VIOLATION_RATE_PCT = 0.0


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _round4(value: float) -> float:
    return round(float(value), 4)


def _parse_positive_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 1:
        raise ValueError(f"{arg_name} must be >= 1")
    return value


def _parse_non_negative_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def _parse_non_negative_float(raw: Any, *, arg_name: str) -> float:
    value = _to_float(raw, -1.0)
    if value < 0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def _rate_pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return _round4((float(numer) / float(denom)) * 100.0)


def _is_threshold_violation(entry: dict[str, Any], *, key_ok: str) -> bool:
    raw = entry.get(key_ok)
    if isinstance(raw, bool):
        return not raw
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citizen product KPI heartbeat window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing rows to inspect (default: {DEFAULT_LAST})")
    p.add_argument("--max-failed", type=int, default=DEFAULT_MAX_FAILED)
    p.add_argument("--max-failed-rate-pct", type=float, default=DEFAULT_MAX_FAILED_RATE_PCT)
    p.add_argument("--max-degraded", type=int, default=DEFAULT_MAX_DEGRADED)
    p.add_argument("--max-degraded-rate-pct", type=float, default=DEFAULT_MAX_DEGRADED_RATE_PCT)
    p.add_argument("--max-contract-incomplete", type=int, default=DEFAULT_MAX_CONTRACT_INCOMPLETE)
    p.add_argument(
        "--max-contract-incomplete-rate-pct",
        type=float,
        default=DEFAULT_MAX_CONTRACT_INCOMPLETE_RATE_PCT,
    )
    p.add_argument("--max-unknown-rate-violations", type=int, default=DEFAULT_MAX_UNKNOWN_RATE_VIOLATIONS)
    p.add_argument(
        "--max-unknown-rate-violation-rate-pct",
        type=float,
        default=DEFAULT_MAX_UNKNOWN_RATE_VIOLATION_RATE_PCT,
    )
    p.add_argument("--max-tfa-violations", type=int, default=DEFAULT_MAX_TFA_VIOLATIONS)
    p.add_argument("--max-tfa-violation-rate-pct", type=float, default=DEFAULT_MAX_TFA_VIOLATION_RATE_PCT)
    p.add_argument("--max-drilldown-violations", type=int, default=DEFAULT_MAX_DRILLDOWN_VIOLATIONS)
    p.add_argument(
        "--max-drilldown-violation-rate-pct",
        type=float,
        default=DEFAULT_MAX_DRILLDOWN_VIOLATION_RATE_PCT,
    )
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict_fail_reasons is not empty.")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def read_heartbeat_rows(heartbeat_path: Path) -> list[dict[str, Any]]:
    if not heartbeat_path.exists():
        return []
    raw = heartbeat_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def _latest_summary(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "run_at": "",
            "heartbeat_id": "",
            "status": "failed",
            "line_no": 0,
            "malformed_line": True,
            "digest_generated_at": "",
            "unknown_rate": None,
            "time_to_first_answer_seconds": None,
            "drilldown_click_rate": None,
            "contract_complete": None,
            "unknown_rate_within_threshold": None,
            "time_to_first_answer_within_threshold": None,
            "drilldown_click_rate_within_threshold": None,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "digest_generated_at": _safe_text(entry.get("digest_generated_at")),
        "unknown_rate": _safe_float(entry.get("unknown_rate")),
        "time_to_first_answer_seconds": _safe_float(entry.get("time_to_first_answer_seconds")),
        "drilldown_click_rate": _safe_float(entry.get("drilldown_click_rate")),
        "contract_complete": bool(entry.get("contract_complete")) if "contract_complete" in entry else None,
        "unknown_rate_within_threshold": entry.get("unknown_rate_within_threshold")
        if isinstance(entry.get("unknown_rate_within_threshold"), bool)
        else None,
        "time_to_first_answer_within_threshold": entry.get("time_to_first_answer_within_threshold")
        if isinstance(entry.get("time_to_first_answer_within_threshold"), bool)
        else None,
        "drilldown_click_rate_within_threshold": entry.get("drilldown_click_rate_within_threshold")
        if isinstance(entry.get("drilldown_click_rate_within_threshold"), bool)
        else None,
    }


def _latest_streak(window_rows: list[dict[str, Any]], *, status: str) -> int:
    streak = 0
    target = _normalize_status(status)
    for row in reversed(window_rows):
        if bool(row.get("malformed_line")):
            break
        entry = _safe_obj(row.get("entry"))
        current = _normalize_status(entry.get("status"))
        if current != target:
            break
        streak += 1
    return streak


def build_window_report(
    rows: list[dict[str, Any]],
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_failed_rate_pct: float = DEFAULT_MAX_FAILED_RATE_PCT,
    max_degraded: int = DEFAULT_MAX_DEGRADED,
    max_degraded_rate_pct: float = DEFAULT_MAX_DEGRADED_RATE_PCT,
    max_contract_incomplete: int = DEFAULT_MAX_CONTRACT_INCOMPLETE,
    max_contract_incomplete_rate_pct: float = DEFAULT_MAX_CONTRACT_INCOMPLETE_RATE_PCT,
    max_unknown_rate_violations: int = DEFAULT_MAX_UNKNOWN_RATE_VIOLATIONS,
    max_unknown_rate_violation_rate_pct: float = DEFAULT_MAX_UNKNOWN_RATE_VIOLATION_RATE_PCT,
    max_tfa_violations: int = DEFAULT_MAX_TFA_VIOLATIONS,
    max_tfa_violation_rate_pct: float = DEFAULT_MAX_TFA_VIOLATION_RATE_PCT,
    max_drilldown_violations: int = DEFAULT_MAX_DRILLDOWN_VIOLATIONS,
    max_drilldown_violation_rate_pct: float = DEFAULT_MAX_DRILLDOWN_VIOLATION_RATE_PCT,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_degraded_n = _parse_non_negative_int(max_degraded, arg_name="max_degraded")
    max_degraded_rate = _parse_non_negative_float(max_degraded_rate_pct, arg_name="max_degraded_rate_pct")
    max_contract_incomplete_n = _parse_non_negative_int(max_contract_incomplete, arg_name="max_contract_incomplete")
    max_contract_incomplete_rate = _parse_non_negative_float(
        max_contract_incomplete_rate_pct,
        arg_name="max_contract_incomplete_rate_pct",
    )
    max_unknown_viol_n = _parse_non_negative_int(max_unknown_rate_violations, arg_name="max_unknown_rate_violations")
    max_unknown_viol_rate = _parse_non_negative_float(
        max_unknown_rate_violation_rate_pct,
        arg_name="max_unknown_rate_violation_rate_pct",
    )
    max_tfa_viol_n = _parse_non_negative_int(max_tfa_violations, arg_name="max_tfa_violations")
    max_tfa_viol_rate = _parse_non_negative_float(max_tfa_violation_rate_pct, arg_name="max_tfa_violation_rate_pct")
    max_drill_viol_n = _parse_non_negative_int(max_drilldown_violations, arg_name="max_drilldown_violations")
    max_drill_viol_rate = _parse_non_negative_float(
        max_drilldown_violation_rate_pct,
        arg_name="max_drilldown_violation_rate_pct",
    )

    window_rows = rows[max(0, len(rows) - window_size) :]
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "window_last": int(window_size),
        "thresholds": {
            "max_failed": int(max_failed_n),
            "max_failed_rate_pct": float(max_failed_rate),
            "max_degraded": int(max_degraded_n),
            "max_degraded_rate_pct": float(max_degraded_rate),
            "max_contract_incomplete": int(max_contract_incomplete_n),
            "max_contract_incomplete_rate_pct": float(max_contract_incomplete_rate),
            "max_unknown_rate_violations": int(max_unknown_viol_n),
            "max_unknown_rate_violation_rate_pct": float(max_unknown_viol_rate),
            "max_tfa_violations": int(max_tfa_viol_n),
            "max_tfa_violation_rate_pct": float(max_tfa_viol_rate),
            "max_drilldown_violations": int(max_drill_viol_n),
            "max_drilldown_violation_rate_pct": float(max_drill_viol_rate),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "degraded_in_window": 0,
        "degraded_rate_pct": 0.0,
        "contract_incomplete_in_window": 0,
        "contract_incomplete_rate_pct": 0.0,
        "unknown_rate_violations_in_window": 0,
        "unknown_rate_violation_rate_pct": 0.0,
        "tfa_violations_in_window": 0,
        "tfa_violation_rate_pct": 0.0,
        "drilldown_violations_in_window": 0,
        "drilldown_violation_rate_pct": 0.0,
        "first_failed_run_at": "",
        "last_failed_run_at": "",
        "first_degraded_run_at": "",
        "last_degraded_run_at": "",
        "first_contract_incomplete_run_at": "",
        "last_contract_incomplete_run_at": "",
        "latest": {},
        "failed_streak_latest": 0,
        "degraded_streak_latest": 0,
        "checks": {
            "window_nonempty_ok": False,
            "malformed_entries_ok": False,
            "max_failed_ok": False,
            "max_failed_rate_ok": False,
            "max_degraded_ok": False,
            "max_degraded_rate_ok": False,
            "max_contract_incomplete_ok": False,
            "max_contract_incomplete_rate_ok": False,
            "max_unknown_rate_violations_ok": False,
            "max_unknown_rate_violation_rate_ok": False,
            "max_tfa_violations_ok": False,
            "max_tfa_violation_rate_ok": False,
            "max_drilldown_violations_ok": False,
            "max_drilldown_violation_rate_ok": False,
            "latest_not_failed_ok": False,
            "latest_contract_complete_ok": False,
            "latest_thresholds_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "degraded",
    }

    for row in window_rows:
        if bool(row.get("malformed_line")):
            report["malformed_entries_in_window"] = int(report["malformed_entries_in_window"]) + 1
            continue

        entry = _safe_obj(row.get("entry"))
        status = _normalize_status(entry.get("status"))
        run_at = _safe_text(entry.get("run_at"))
        report["status_counts"][status] = int(report["status_counts"].get(status, 0)) + 1

        if status == "failed":
            if not report["first_failed_run_at"]:
                report["first_failed_run_at"] = run_at
            report["last_failed_run_at"] = run_at
        if status == "degraded":
            if not report["first_degraded_run_at"]:
                report["first_degraded_run_at"] = run_at
            report["last_degraded_run_at"] = run_at

        contract_complete = bool(entry.get("contract_complete"))
        if not contract_complete:
            report["contract_incomplete_in_window"] = int(report["contract_incomplete_in_window"]) + 1
            if not report["first_contract_incomplete_run_at"]:
                report["first_contract_incomplete_run_at"] = run_at
            report["last_contract_incomplete_run_at"] = run_at

        if _is_threshold_violation(entry, key_ok="unknown_rate_within_threshold"):
            report["unknown_rate_violations_in_window"] = int(report["unknown_rate_violations_in_window"]) + 1
        if _is_threshold_violation(entry, key_ok="time_to_first_answer_within_threshold"):
            report["tfa_violations_in_window"] = int(report["tfa_violations_in_window"]) + 1
        if _is_threshold_violation(entry, key_ok="drilldown_click_rate_within_threshold"):
            report["drilldown_violations_in_window"] = int(report["drilldown_violations_in_window"]) + 1

    report["failed_in_window"] = int(report["status_counts"]["failed"])
    report["degraded_in_window"] = int(report["status_counts"]["degraded"])

    if report["entries_in_window"] > 0:
        denom = int(report["entries_in_window"])
        report["failed_rate_pct"] = _rate_pct(int(report["failed_in_window"]), denom)
        report["degraded_rate_pct"] = _rate_pct(int(report["degraded_in_window"]), denom)
        report["contract_incomplete_rate_pct"] = _rate_pct(int(report["contract_incomplete_in_window"]), denom)
        report["unknown_rate_violation_rate_pct"] = _rate_pct(int(report["unknown_rate_violations_in_window"]), denom)
        report["tfa_violation_rate_pct"] = _rate_pct(int(report["tfa_violations_in_window"]), denom)
        report["drilldown_violation_rate_pct"] = _rate_pct(int(report["drilldown_violations_in_window"]), denom)
        report["latest"] = _latest_summary(window_rows[-1])
        report["failed_streak_latest"] = _latest_streak(window_rows, status="failed")
        report["degraded_streak_latest"] = _latest_streak(window_rows, status="degraded")
    else:
        report["latest"] = _latest_summary(None)

    checks = report["checks"]
    checks["window_nonempty_ok"] = report["entries_in_window"] > 0
    checks["malformed_entries_ok"] = report["malformed_entries_in_window"] == 0
    checks["max_failed_ok"] = report["failed_in_window"] <= max_failed_n
    checks["max_failed_rate_ok"] = float(report["failed_rate_pct"]) <= max_failed_rate
    checks["max_degraded_ok"] = report["degraded_in_window"] <= max_degraded_n
    checks["max_degraded_rate_ok"] = float(report["degraded_rate_pct"]) <= max_degraded_rate
    checks["max_contract_incomplete_ok"] = report["contract_incomplete_in_window"] <= max_contract_incomplete_n
    checks["max_contract_incomplete_rate_ok"] = float(report["contract_incomplete_rate_pct"]) <= max_contract_incomplete_rate
    checks["max_unknown_rate_violations_ok"] = report["unknown_rate_violations_in_window"] <= max_unknown_viol_n
    checks["max_unknown_rate_violation_rate_ok"] = float(report["unknown_rate_violation_rate_pct"]) <= max_unknown_viol_rate
    checks["max_tfa_violations_ok"] = report["tfa_violations_in_window"] <= max_tfa_viol_n
    checks["max_tfa_violation_rate_ok"] = float(report["tfa_violation_rate_pct"]) <= max_tfa_viol_rate
    checks["max_drilldown_violations_ok"] = report["drilldown_violations_in_window"] <= max_drill_viol_n
    checks["max_drilldown_violation_rate_ok"] = float(report["drilldown_violation_rate_pct"]) <= max_drill_viol_rate
    checks["latest_not_failed_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _normalize_status(_safe_obj(report["latest"]).get("status")) != "failed"
    )
    checks["latest_contract_complete_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and bool(_safe_obj(report["latest"]).get("contract_complete"))
    )
    checks["latest_thresholds_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and bool(_safe_obj(report["latest"]).get("unknown_rate_within_threshold"))
        and bool(_safe_obj(report["latest"]).get("time_to_first_answer_within_threshold"))
        and bool(_safe_obj(report["latest"]).get("drilldown_click_rate_within_threshold"))
    )

    reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        reasons.append("empty_window")
    if not checks["malformed_entries_ok"]:
        reasons.append("malformed_entries_present")
    if not checks["max_failed_ok"]:
        reasons.append("max_failed_exceeded")
    if not checks["max_failed_rate_ok"]:
        reasons.append("max_failed_rate_exceeded")
    if not checks["max_degraded_ok"]:
        reasons.append("max_degraded_exceeded")
    if not checks["max_degraded_rate_ok"]:
        reasons.append("max_degraded_rate_exceeded")
    if not checks["max_contract_incomplete_ok"]:
        reasons.append("max_contract_incomplete_exceeded")
    if not checks["max_contract_incomplete_rate_ok"]:
        reasons.append("max_contract_incomplete_rate_exceeded")
    if not checks["max_unknown_rate_violations_ok"]:
        reasons.append("max_unknown_rate_violations_exceeded")
    if not checks["max_unknown_rate_violation_rate_ok"]:
        reasons.append("max_unknown_rate_violation_rate_exceeded")
    if not checks["max_tfa_violations_ok"]:
        reasons.append("max_tfa_violations_exceeded")
    if not checks["max_tfa_violation_rate_ok"]:
        reasons.append("max_tfa_violation_rate_exceeded")
    if not checks["max_drilldown_violations_ok"]:
        reasons.append("max_drilldown_violations_exceeded")
    if not checks["max_drilldown_violation_rate_ok"]:
        reasons.append("max_drilldown_violation_rate_exceeded")
    if not checks["latest_not_failed_ok"]:
        reasons.append("latest_status_failed")
    if not checks["latest_contract_complete_ok"]:
        reasons.append("latest_contract_incomplete")
    if not checks["latest_thresholds_ok"]:
        reasons.append("latest_threshold_violation")
    report["strict_fail_reasons"] = reasons

    if report["entries_in_window"] == 0:
        report["status"] = "degraded"
    elif report["malformed_entries_in_window"] > 0:
        report["status"] = "failed"
    elif reasons:
        report["status"] = "failed"
    elif (
        report["degraded_in_window"] > 0
        or report["contract_incomplete_in_window"] > 0
        or report["unknown_rate_violations_in_window"] > 0
        or report["tfa_violations_in_window"] > 0
        or report["drilldown_violations_in_window"] > 0
    ):
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report


def build_window_report_from_path(
    heartbeat_path: Path,
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_failed_rate_pct: float = DEFAULT_MAX_FAILED_RATE_PCT,
    max_degraded: int = DEFAULT_MAX_DEGRADED,
    max_degraded_rate_pct: float = DEFAULT_MAX_DEGRADED_RATE_PCT,
    max_contract_incomplete: int = DEFAULT_MAX_CONTRACT_INCOMPLETE,
    max_contract_incomplete_rate_pct: float = DEFAULT_MAX_CONTRACT_INCOMPLETE_RATE_PCT,
    max_unknown_rate_violations: int = DEFAULT_MAX_UNKNOWN_RATE_VIOLATIONS,
    max_unknown_rate_violation_rate_pct: float = DEFAULT_MAX_UNKNOWN_RATE_VIOLATION_RATE_PCT,
    max_tfa_violations: int = DEFAULT_MAX_TFA_VIOLATIONS,
    max_tfa_violation_rate_pct: float = DEFAULT_MAX_TFA_VIOLATION_RATE_PCT,
    max_drilldown_violations: int = DEFAULT_MAX_DRILLDOWN_VIOLATIONS,
    max_drilldown_violation_rate_pct: float = DEFAULT_MAX_DRILLDOWN_VIOLATION_RATE_PCT,
    strict: bool = False,
) -> dict[str, Any]:
    rows = read_heartbeat_rows(heartbeat_path)
    return build_window_report(
        rows,
        window_last=window_last,
        max_failed=max_failed,
        max_failed_rate_pct=max_failed_rate_pct,
        max_degraded=max_degraded,
        max_degraded_rate_pct=max_degraded_rate_pct,
        max_contract_incomplete=max_contract_incomplete,
        max_contract_incomplete_rate_pct=max_contract_incomplete_rate_pct,
        max_unknown_rate_violations=max_unknown_rate_violations,
        max_unknown_rate_violation_rate_pct=max_unknown_rate_violation_rate_pct,
        max_tfa_violations=max_tfa_violations,
        max_tfa_violation_rate_pct=max_tfa_violation_rate_pct,
        max_drilldown_violations=max_drilldown_violations,
        max_drilldown_violation_rate_pct=max_drilldown_violation_rate_pct,
        strict=strict,
        heartbeat_path=str(heartbeat_path),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        report = build_window_report_from_path(
            Path(str(args.heartbeat_jsonl)),
            window_last=int(args.last),
            max_failed=int(args.max_failed),
            max_failed_rate_pct=float(args.max_failed_rate_pct),
            max_degraded=int(args.max_degraded),
            max_degraded_rate_pct=float(args.max_degraded_rate_pct),
            max_contract_incomplete=int(args.max_contract_incomplete),
            max_contract_incomplete_rate_pct=float(args.max_contract_incomplete_rate_pct),
            max_unknown_rate_violations=int(args.max_unknown_rate_violations),
            max_unknown_rate_violation_rate_pct=float(args.max_unknown_rate_violation_rate_pct),
            max_tfa_violations=int(args.max_tfa_violations),
            max_tfa_violation_rate_pct=float(args.max_tfa_violation_rate_pct),
            max_drilldown_violations=int(args.max_drilldown_violations),
            max_drilldown_violation_rate_pct=float(args.max_drilldown_violation_rate_pct),
            strict=bool(args.strict),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
