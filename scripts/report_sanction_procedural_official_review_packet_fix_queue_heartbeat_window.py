#!/usr/bin/env python3
"""Window report for sanction procedural packet-fix queue heartbeat."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_DEGRADED = 1000000
DEFAULT_MAX_DEGRADED_RATE_PCT = 100.0
DEFAULT_MAX_NONEMPTY_QUEUE_RUNS = 1000000
DEFAULT_MAX_NONEMPTY_QUEUE_RATE_PCT = 100.0
DEFAULT_MAX_MALFORMED = 0


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _rate_pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return round((float(numer) / float(denom)) * 100.0, 4)


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
    if value < 0.0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Window report for packet-fix queue heartbeat")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST)
    p.add_argument("--max-failed", type=int, default=DEFAULT_MAX_FAILED)
    p.add_argument("--max-failed-rate-pct", type=float, default=DEFAULT_MAX_FAILED_RATE_PCT)
    p.add_argument("--max-degraded", type=int, default=DEFAULT_MAX_DEGRADED)
    p.add_argument("--max-degraded-rate-pct", type=float, default=DEFAULT_MAX_DEGRADED_RATE_PCT)
    p.add_argument("--max-nonempty-queue-runs", type=int, default=DEFAULT_MAX_NONEMPTY_QUEUE_RUNS)
    p.add_argument("--max-nonempty-queue-rate-pct", type=float, default=DEFAULT_MAX_NONEMPTY_QUEUE_RATE_PCT)
    p.add_argument("--max-malformed", type=int, default=DEFAULT_MAX_MALFORMED)
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict checks fail")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def read_heartbeat_rows(heartbeat_path: Path) -> list[dict[str, Any]]:
    if not heartbeat_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    raw = heartbeat_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
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
            "line_no": 0,
            "malformed_line": True,
            "run_at": "",
            "heartbeat_id": "",
            "status": "failed",
            "queue_rows_total": None,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "queue_rows_total": None if malformed else _to_int(entry.get("queue_rows_total"), 0),
    }


def build_window_report(
    rows: list[dict[str, Any]],
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_failed_rate_pct: float = DEFAULT_MAX_FAILED_RATE_PCT,
    max_degraded: int = DEFAULT_MAX_DEGRADED,
    max_degraded_rate_pct: float = DEFAULT_MAX_DEGRADED_RATE_PCT,
    max_nonempty_queue_runs: int = DEFAULT_MAX_NONEMPTY_QUEUE_RUNS,
    max_nonempty_queue_rate_pct: float = DEFAULT_MAX_NONEMPTY_QUEUE_RATE_PCT,
    max_malformed: int = DEFAULT_MAX_MALFORMED,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_degraded_n = _parse_non_negative_int(max_degraded, arg_name="max_degraded")
    max_degraded_rate = _parse_non_negative_float(max_degraded_rate_pct, arg_name="max_degraded_rate_pct")
    max_nonempty_n = _parse_non_negative_int(max_nonempty_queue_runs, arg_name="max_nonempty_queue_runs")
    max_nonempty_rate = _parse_non_negative_float(
        max_nonempty_queue_rate_pct,
        arg_name="max_nonempty_queue_rate_pct",
    )
    max_malformed_n = _parse_non_negative_int(max_malformed, arg_name="max_malformed")

    window_rows = rows[max(0, len(rows) - window_size) :]
    entries_in_window = len(window_rows)

    status_counts = {"ok": 0, "degraded": 0, "failed": 0}
    malformed_entries_in_window = 0
    failed_in_window = 0
    degraded_in_window = 0
    nonempty_queue_runs_in_window = 0
    first_failed_run_at = ""
    last_failed_run_at = ""
    first_degraded_run_at = ""
    last_degraded_run_at = ""

    for row in window_rows:
        malformed = bool(row.get("malformed_line"))
        entry = _safe_obj(row.get("entry"))
        run_at = _safe_text(entry.get("run_at"))
        if malformed:
            malformed_entries_in_window += 1
            failed_in_window += 1
            status_counts["failed"] += 1
            if not first_failed_run_at:
                first_failed_run_at = run_at
            last_failed_run_at = run_at
            continue

        status = _normalize_status(entry.get("status"))
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        if status == "failed":
            failed_in_window += 1
            if not first_failed_run_at:
                first_failed_run_at = run_at
            last_failed_run_at = run_at
        if status == "degraded":
            degraded_in_window += 1
            if not first_degraded_run_at:
                first_degraded_run_at = run_at
            last_degraded_run_at = run_at

        queue_rows_total = _to_int(entry.get("queue_rows_total"), 0)
        if queue_rows_total > 0:
            nonempty_queue_runs_in_window += 1

    failed_rate_pct = _rate_pct(failed_in_window, entries_in_window)
    degraded_rate_pct = _rate_pct(degraded_in_window, entries_in_window)
    nonempty_queue_rate_pct = _rate_pct(nonempty_queue_runs_in_window, entries_in_window)

    checks = {
        "max_failed_ok": failed_in_window <= max_failed_n,
        "max_failed_rate_ok": failed_rate_pct <= float(max_failed_rate),
        "max_degraded_ok": degraded_in_window <= max_degraded_n,
        "max_degraded_rate_ok": degraded_rate_pct <= float(max_degraded_rate),
        "max_nonempty_queue_runs_ok": nonempty_queue_runs_in_window <= max_nonempty_n,
        "max_nonempty_queue_rate_ok": nonempty_queue_rate_pct <= float(max_nonempty_rate),
        "max_malformed_ok": malformed_entries_in_window <= max_malformed_n,
    }

    strict_fail_reasons: list[str] = []
    for key, ok in checks.items():
        if not bool(ok):
            strict_fail_reasons.append(f"{key}_exceeded")

    status = "ok" if all(bool(v) for v in checks.values()) else "failed"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "window_last": int(window_size),
        "thresholds": {
            "max_failed": int(max_failed_n),
            "max_failed_rate_pct": float(max_failed_rate),
            "max_degraded": int(max_degraded_n),
            "max_degraded_rate_pct": float(max_degraded_rate),
            "max_nonempty_queue_runs": int(max_nonempty_n),
            "max_nonempty_queue_rate_pct": float(max_nonempty_rate),
            "max_malformed": int(max_malformed_n),
        },
        "entries_total": len(rows),
        "entries_in_window": entries_in_window,
        "malformed_entries_in_window": malformed_entries_in_window,
        "status_counts": status_counts,
        "failed_in_window": failed_in_window,
        "failed_rate_pct": failed_rate_pct,
        "degraded_in_window": degraded_in_window,
        "degraded_rate_pct": degraded_rate_pct,
        "nonempty_queue_runs_in_window": nonempty_queue_runs_in_window,
        "nonempty_queue_rate_pct": nonempty_queue_rate_pct,
        "first_failed_run_at": first_failed_run_at,
        "last_failed_run_at": last_failed_run_at,
        "first_degraded_run_at": first_degraded_run_at,
        "last_degraded_run_at": last_degraded_run_at,
        "latest": _latest_summary(window_rows[-1] if window_rows else None),
        "checks": checks,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _safe_text(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    heartbeat_path = Path(args.heartbeat_jsonl)
    rows = read_heartbeat_rows(heartbeat_path)
    report = build_window_report(
        rows,
        window_last=args.last,
        max_failed=args.max_failed,
        max_failed_rate_pct=args.max_failed_rate_pct,
        max_degraded=args.max_degraded,
        max_degraded_rate_pct=args.max_degraded_rate_pct,
        max_nonempty_queue_runs=args.max_nonempty_queue_runs,
        max_nonempty_queue_rate_pct=args.max_nonempty_queue_rate_pct,
        max_malformed=args.max_malformed,
        strict=bool(args.strict),
        heartbeat_path=str(heartbeat_path),
    )
    _write_json(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    strict_fail_reasons = report.get("strict_fail_reasons")
    if bool(args.strict) and isinstance(strict_fail_reasons, list) and len(strict_fail_reasons) > 0:
        return 4
    if _normalize_status(report.get("status")) == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
