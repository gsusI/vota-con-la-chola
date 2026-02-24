#!/usr/bin/env python3
"""Windowed trend report for citizen mobile observability heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_mobile_observability_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_DEGRADED = 0
DEFAULT_MAX_DEGRADED_RATE_PCT = 0.0
DEFAULT_MAX_P90_THRESHOLD_VIOLATIONS = 0
DEFAULT_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT = 0.0


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


def _p90_within_threshold(entry: dict[str, Any]) -> bool | None:
    raw = entry.get("input_to_render_p90_within_threshold")
    if isinstance(raw, bool):
        return raw
    p90 = _safe_float(entry.get("input_to_render_p90_ms"))
    max_p90 = _safe_float(entry.get("max_input_to_render_p90_ms"))
    if p90 is None or max_p90 is None:
        return None
    return bool(p90 <= max_p90)


def _p90_margin_ms(entry: dict[str, Any]) -> float | None:
    p90 = _safe_float(entry.get("input_to_render_p90_ms"))
    max_p90 = _safe_float(entry.get("max_input_to_render_p90_ms"))
    if p90 is None or max_p90 is None:
        return None
    return float(max_p90) - float(p90)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citizen mobile observability heartbeat window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing rows to inspect (default: {DEFAULT_LAST})")
    p.add_argument(
        "--max-failed",
        type=int,
        default=DEFAULT_MAX_FAILED,
        help=f"Max allowed failed rows in window (default: {DEFAULT_MAX_FAILED})",
    )
    p.add_argument(
        "--max-failed-rate-pct",
        type=float,
        default=DEFAULT_MAX_FAILED_RATE_PCT,
        help=f"Max allowed failed rate pct in window (default: {DEFAULT_MAX_FAILED_RATE_PCT})",
    )
    p.add_argument(
        "--max-degraded",
        type=int,
        default=DEFAULT_MAX_DEGRADED,
        help=f"Max allowed degraded rows in window (default: {DEFAULT_MAX_DEGRADED})",
    )
    p.add_argument(
        "--max-degraded-rate-pct",
        type=float,
        default=DEFAULT_MAX_DEGRADED_RATE_PCT,
        help=f"Max allowed degraded rate pct in window (default: {DEFAULT_MAX_DEGRADED_RATE_PCT})",
    )
    p.add_argument(
        "--max-p90-threshold-violations",
        type=int,
        default=DEFAULT_MAX_P90_THRESHOLD_VIOLATIONS,
        help=f"Max allowed p90-threshold violations in window (default: {DEFAULT_MAX_P90_THRESHOLD_VIOLATIONS})",
    )
    p.add_argument(
        "--max-p90-threshold-violation-rate-pct",
        type=float,
        default=DEFAULT_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT,
        help=(
            "Max allowed p90-threshold violation rate pct in window "
            f"(default: {DEFAULT_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT})"
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when strict_fail_reasons is not empty.",
    )
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
            "input_to_render_p90_ms": None,
            "max_input_to_render_p90_ms": None,
            "input_to_render_p90_within_threshold": None,
            "input_to_render_p90_margin_ms": None,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "input_to_render_p90_ms": _safe_float(entry.get("input_to_render_p90_ms")),
        "max_input_to_render_p90_ms": _safe_float(entry.get("max_input_to_render_p90_ms")),
        "input_to_render_p90_within_threshold": _p90_within_threshold(entry),
        "input_to_render_p90_margin_ms": _p90_margin_ms(entry),
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
    max_p90_threshold_violations: int = DEFAULT_MAX_P90_THRESHOLD_VIOLATIONS,
    max_p90_threshold_violation_rate_pct: float = DEFAULT_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_degraded_n = _parse_non_negative_int(max_degraded, arg_name="max_degraded")
    max_degraded_rate = _parse_non_negative_float(max_degraded_rate_pct, arg_name="max_degraded_rate_pct")
    max_p90_violations_n = _parse_non_negative_int(
        max_p90_threshold_violations, arg_name="max_p90_threshold_violations"
    )
    max_p90_violations_rate = _parse_non_negative_float(
        max_p90_threshold_violation_rate_pct, arg_name="max_p90_threshold_violation_rate_pct"
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
            "max_p90_threshold_violations": int(max_p90_violations_n),
            "max_p90_threshold_violation_rate_pct": float(max_p90_violations_rate),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "degraded_in_window": 0,
        "degraded_rate_pct": 0.0,
        "p90_threshold_violations_in_window": 0,
        "p90_threshold_violation_rate_pct": 0.0,
        "first_failed_run_at": "",
        "last_failed_run_at": "",
        "first_degraded_run_at": "",
        "last_degraded_run_at": "",
        "first_p90_threshold_violation_run_at": "",
        "last_p90_threshold_violation_run_at": "",
        "latest": {},
        "failed_streak_latest": 0,
        "degraded_streak_latest": 0,
        "p90_margin_min_ms": None,
        "p90_margin_max_ms": None,
        "latest_p90_margin_ms": None,
        "checks": {
            "window_nonempty_ok": False,
            "malformed_entries_ok": False,
            "max_failed_ok": False,
            "max_failed_rate_ok": False,
            "max_degraded_ok": False,
            "max_degraded_rate_ok": False,
            "max_p90_threshold_violations_ok": False,
            "max_p90_threshold_violation_rate_ok": False,
            "latest_not_failed_ok": False,
            "latest_p90_within_threshold_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "degraded",
    }

    p90_margins: list[float] = []
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

        p90_within_threshold = _p90_within_threshold(entry)
        if p90_within_threshold is False:
            report["p90_threshold_violations_in_window"] = int(report["p90_threshold_violations_in_window"]) + 1
            if not report["first_p90_threshold_violation_run_at"]:
                report["first_p90_threshold_violation_run_at"] = run_at
            report["last_p90_threshold_violation_run_at"] = run_at

        p90_margin = _p90_margin_ms(entry)
        if p90_margin is not None:
            p90_margins.append(float(p90_margin))

    report["failed_in_window"] = int(report["status_counts"]["failed"])
    report["degraded_in_window"] = int(report["status_counts"]["degraded"])

    if report["entries_in_window"] > 0:
        denom = float(report["entries_in_window"])
        report["failed_rate_pct"] = _round4((float(report["failed_in_window"]) / denom) * 100.0)
        report["degraded_rate_pct"] = _round4((float(report["degraded_in_window"]) / denom) * 100.0)
        report["p90_threshold_violation_rate_pct"] = _round4(
            (float(report["p90_threshold_violations_in_window"]) / denom) * 100.0
        )
        report["latest"] = _latest_summary(window_rows[-1])
        report["failed_streak_latest"] = _latest_streak(window_rows, status="failed")
        report["degraded_streak_latest"] = _latest_streak(window_rows, status="degraded")
        report["latest_p90_margin_ms"] = _safe_float(_safe_obj(report["latest"]).get("input_to_render_p90_margin_ms"))
    else:
        report["latest"] = _latest_summary(None)

    if p90_margins:
        report["p90_margin_min_ms"] = round(min(p90_margins), 6)
        report["p90_margin_max_ms"] = round(max(p90_margins), 6)

    checks = report["checks"]
    checks["window_nonempty_ok"] = report["entries_in_window"] > 0
    checks["malformed_entries_ok"] = report["malformed_entries_in_window"] == 0
    checks["max_failed_ok"] = report["failed_in_window"] <= max_failed_n
    checks["max_failed_rate_ok"] = float(report["failed_rate_pct"]) <= max_failed_rate
    checks["max_degraded_ok"] = report["degraded_in_window"] <= max_degraded_n
    checks["max_degraded_rate_ok"] = float(report["degraded_rate_pct"]) <= max_degraded_rate
    checks["max_p90_threshold_violations_ok"] = report["p90_threshold_violations_in_window"] <= max_p90_violations_n
    checks["max_p90_threshold_violation_rate_ok"] = (
        float(report["p90_threshold_violation_rate_pct"]) <= max_p90_violations_rate
    )
    checks["latest_not_failed_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _normalize_status(_safe_obj(report["latest"]).get("status")) != "failed"
    )
    latest_p90_within = _safe_obj(report["latest"]).get("input_to_render_p90_within_threshold")
    checks["latest_p90_within_threshold_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_p90_within is not False
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
    if not checks["max_p90_threshold_violations_ok"]:
        reasons.append("max_p90_threshold_violations_exceeded")
    if not checks["max_p90_threshold_violation_rate_ok"]:
        reasons.append("max_p90_threshold_violation_rate_exceeded")
    if not checks["latest_not_failed_ok"]:
        reasons.append("latest_status_failed")
    if not checks["latest_p90_within_threshold_ok"]:
        reasons.append("latest_p90_threshold_violation")
    report["strict_fail_reasons"] = reasons

    if report["entries_in_window"] == 0:
        report["status"] = "degraded"
    elif report["malformed_entries_in_window"] > 0:
        report["status"] = "failed"
    elif (
        not checks["max_failed_ok"]
        or not checks["max_failed_rate_ok"]
        or not checks["max_p90_threshold_violations_ok"]
        or not checks["max_p90_threshold_violation_rate_ok"]
        or not checks["latest_not_failed_ok"]
        or not checks["latest_p90_within_threshold_ok"]
    ):
        report["status"] = "failed"
    elif not checks["max_degraded_ok"] or not checks["max_degraded_rate_ok"]:
        report["status"] = "failed"
    elif report["degraded_in_window"] > 0 or report["p90_threshold_violations_in_window"] > 0:
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
    max_p90_threshold_violations: int = DEFAULT_MAX_P90_THRESHOLD_VIOLATIONS,
    max_p90_threshold_violation_rate_pct: float = DEFAULT_MAX_P90_THRESHOLD_VIOLATION_RATE_PCT,
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
        max_p90_threshold_violations=max_p90_threshold_violations,
        max_p90_threshold_violation_rate_pct=max_p90_threshold_violation_rate_pct,
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
            max_p90_threshold_violations=int(args.max_p90_threshold_violations),
            max_p90_threshold_violation_rate_pct=float(args.max_p90_threshold_violation_rate_pct),
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
