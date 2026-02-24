#!/usr/bin/env python3
"""Windowed trend report for liberty identity actionable review queue heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.jsonl"
)
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS = 0
DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS_RATE_PCT = 0.0


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Liberty person identity actionable heartbeat window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing rows to inspect (default: {DEFAULT_LAST})")
    p.add_argument("--max-failed", type=int, default=DEFAULT_MAX_FAILED)
    p.add_argument("--max-failed-rate-pct", type=float, default=DEFAULT_MAX_FAILED_RATE_PCT)
    p.add_argument("--max-actionable-nonempty-runs", type=int, default=DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS)
    p.add_argument(
        "--max-actionable-nonempty-runs-rate-pct",
        type=float,
        default=DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS_RATE_PCT,
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
            "actionable_rows_total": 0,
            "actionable_queue_empty": False,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "actionable_rows_total": _to_int(entry.get("actionable_rows_total"), 0),
        "actionable_queue_empty": bool(entry.get("actionable_queue_empty")),
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
    max_actionable_nonempty_runs: int = DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS,
    max_actionable_nonempty_runs_rate_pct: float = DEFAULT_MAX_ACTIONABLE_NONEMPTY_RUNS_RATE_PCT,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_actionable_nonempty_runs_n = _parse_non_negative_int(
        max_actionable_nonempty_runs,
        arg_name="max_actionable_nonempty_runs",
    )
    max_actionable_nonempty_runs_rate = _parse_non_negative_float(
        max_actionable_nonempty_runs_rate_pct,
        arg_name="max_actionable_nonempty_runs_rate_pct",
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
            "max_actionable_nonempty_runs": int(max_actionable_nonempty_runs_n),
            "max_actionable_nonempty_runs_rate_pct": float(max_actionable_nonempty_runs_rate),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "actionable_nonempty_runs_in_window": 0,
        "actionable_nonempty_runs_rate_pct": 0.0,
        "first_failed_run_at": "",
        "last_failed_run_at": "",
        "first_actionable_nonempty_run_at": "",
        "last_actionable_nonempty_run_at": "",
        "latest": {},
        "failed_streak_latest": 0,
        "checks": {
            "window_nonempty_ok": False,
            "malformed_entries_ok": False,
            "max_failed_ok": False,
            "max_failed_rate_ok": False,
            "max_actionable_nonempty_runs_ok": False,
            "max_actionable_nonempty_runs_rate_ok": False,
            "latest_not_failed_ok": False,
            "latest_actionable_queue_empty_ok": False,
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
        actionable_rows_total = _to_int(entry.get("actionable_rows_total"), 0)

        report["status_counts"][status] = int(report["status_counts"].get(status, 0)) + 1
        if status == "failed":
            if not report["first_failed_run_at"]:
                report["first_failed_run_at"] = run_at
            report["last_failed_run_at"] = run_at
        if actionable_rows_total > 0:
            report["actionable_nonempty_runs_in_window"] = int(report["actionable_nonempty_runs_in_window"]) + 1
            if not report["first_actionable_nonempty_run_at"]:
                report["first_actionable_nonempty_run_at"] = run_at
            report["last_actionable_nonempty_run_at"] = run_at

    report["failed_in_window"] = int(report["status_counts"]["failed"])
    report["failed_rate_pct"] = _rate_pct(int(report["failed_in_window"]), int(report["entries_in_window"]))
    report["actionable_nonempty_runs_rate_pct"] = _rate_pct(
        int(report["actionable_nonempty_runs_in_window"]),
        int(report["entries_in_window"]),
    )
    report["latest"] = _latest_summary(window_rows[-1] if window_rows else None)
    report["failed_streak_latest"] = _latest_streak(window_rows, status="failed")

    checks = report["checks"]
    checks["window_nonempty_ok"] = int(report["entries_in_window"]) > 0
    checks["malformed_entries_ok"] = int(report["malformed_entries_in_window"]) == 0
    checks["max_failed_ok"] = int(report["failed_in_window"]) <= int(max_failed_n)
    checks["max_failed_rate_ok"] = float(report["failed_rate_pct"]) <= float(max_failed_rate)
    checks["max_actionable_nonempty_runs_ok"] = int(report["actionable_nonempty_runs_in_window"]) <= int(
        max_actionable_nonempty_runs_n
    )
    checks["max_actionable_nonempty_runs_rate_ok"] = float(report["actionable_nonempty_runs_rate_pct"]) <= float(
        max_actionable_nonempty_runs_rate
    )
    checks["latest_not_failed_ok"] = _normalize_status(report["latest"].get("status")) != "failed"
    checks["latest_actionable_queue_empty_ok"] = bool(report["latest"].get("actionable_queue_empty"))

    strict_fail_reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        strict_fail_reasons.append("window_empty")
    if not checks["malformed_entries_ok"]:
        strict_fail_reasons.append("malformed_entries_present")
    if not checks["max_failed_ok"]:
        strict_fail_reasons.append("max_failed_exceeded")
    if not checks["max_failed_rate_ok"]:
        strict_fail_reasons.append("max_failed_rate_exceeded")
    if not checks["max_actionable_nonempty_runs_ok"]:
        strict_fail_reasons.append("max_actionable_nonempty_runs_exceeded")
    if not checks["max_actionable_nonempty_runs_rate_ok"]:
        strict_fail_reasons.append("max_actionable_nonempty_runs_rate_exceeded")
    if not checks["latest_not_failed_ok"]:
        strict_fail_reasons.append("latest_failed")
    if not checks["latest_actionable_queue_empty_ok"]:
        strict_fail_reasons.append("latest_actionable_queue_not_empty")
    report["strict_fail_reasons"] = strict_fail_reasons

    if strict_fail_reasons:
        report["status"] = "failed"
    elif int(report["failed_in_window"]) > 0 or int(report["actionable_nonempty_runs_in_window"]) > 0:
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    heartbeat_path = Path(str(args.heartbeat_jsonl))
    rows = read_heartbeat_rows(heartbeat_path)
    try:
        report = build_window_report(
            rows,
            window_last=int(args.last),
            max_failed=int(args.max_failed),
            max_failed_rate_pct=float(args.max_failed_rate_pct),
            max_actionable_nonempty_runs=int(args.max_actionable_nonempty_runs),
            max_actionable_nonempty_runs_rate_pct=float(args.max_actionable_nonempty_runs_rate_pct),
            strict=bool(args.strict),
            heartbeat_path=str(heartbeat_path),
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "generated_at": now_utc_iso(),
            "strict": bool(args.strict),
            "heartbeat_path": str(heartbeat_path),
            "status": "failed",
            "strict_fail_reasons": [f"runtime_error:{type(exc).__name__}:{exc}"],
        }
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        print(payload)
        out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(report.get("strict_fail_reasons") or []) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
