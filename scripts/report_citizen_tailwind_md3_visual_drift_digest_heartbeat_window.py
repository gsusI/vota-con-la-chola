#!/usr/bin/env python3
"""Windowed trend report for Tailwind+MD3 visual drift heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_tailwind_md3_visual_drift_digest_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_DEGRADED = 0
DEFAULT_MAX_DEGRADED_RATE_PCT = 0.0
DEFAULT_MAX_PARITY_MISMATCH = 0
DEFAULT_MAX_PARITY_MISMATCH_RATE_PCT = 0.0
DEFAULT_MAX_TOKENS_PARITY_MISMATCH = 0
DEFAULT_MAX_TOKENS_DATA_PARITY_MISMATCH = 0
DEFAULT_MAX_CSS_PARITY_MISMATCH = 0
DEFAULT_MAX_UI_HTML_PARITY_MISMATCH = 0
DEFAULT_MAX_MARKER_MISMATCH = 0


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


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        token = _safe_text(item)
        if token:
            out.append(token)
    return out


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


def _entry_bool(entry: dict[str, Any], key: str) -> bool:
    return bool(entry.get(key)) if isinstance(entry.get(key), bool) else False


def _row_parity_mismatch(entry: dict[str, Any]) -> bool:
    return (not _entry_bool(entry, "source_published_parity_ok")) or (not _entry_bool(entry, "marker_parity_ok"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tailwind+MD3 visual drift heartbeat window report")
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
        "--max-parity-mismatch",
        type=int,
        default=DEFAULT_MAX_PARITY_MISMATCH,
        help=f"Max allowed parity mismatch rows in window (default: {DEFAULT_MAX_PARITY_MISMATCH})",
    )
    p.add_argument(
        "--max-parity-mismatch-rate-pct",
        type=float,
        default=DEFAULT_MAX_PARITY_MISMATCH_RATE_PCT,
        help=f"Max allowed parity mismatch rate pct in window (default: {DEFAULT_MAX_PARITY_MISMATCH_RATE_PCT})",
    )
    p.add_argument(
        "--max-tokens-parity-mismatch",
        type=int,
        default=DEFAULT_MAX_TOKENS_PARITY_MISMATCH,
        help=f"Max allowed tokens parity mismatches in window (default: {DEFAULT_MAX_TOKENS_PARITY_MISMATCH})",
    )
    p.add_argument(
        "--max-tokens-data-parity-mismatch",
        type=int,
        default=DEFAULT_MAX_TOKENS_DATA_PARITY_MISMATCH,
        help=f"Max allowed published-data tokens parity mismatches in window (default: {DEFAULT_MAX_TOKENS_DATA_PARITY_MISMATCH})",
    )
    p.add_argument(
        "--max-css-parity-mismatch",
        type=int,
        default=DEFAULT_MAX_CSS_PARITY_MISMATCH,
        help=f"Max allowed CSS parity mismatches in window (default: {DEFAULT_MAX_CSS_PARITY_MISMATCH})",
    )
    p.add_argument(
        "--max-ui-html-parity-mismatch",
        type=int,
        default=DEFAULT_MAX_UI_HTML_PARITY_MISMATCH,
        help=f"Max allowed UI HTML parity mismatches in window (default: {DEFAULT_MAX_UI_HTML_PARITY_MISMATCH})",
    )
    p.add_argument(
        "--max-marker-mismatch",
        type=int,
        default=DEFAULT_MAX_MARKER_MISMATCH,
        help=f"Max allowed marker parity mismatches in window (default: {DEFAULT_MAX_MARKER_MISMATCH})",
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
            "source_published_parity_ok": False,
            "marker_parity_ok": False,
            "tokens_parity_ok": False,
            "tokens_data_parity_ok": False,
            "css_parity_ok": False,
            "ui_html_parity_ok": False,
            "parity_fail_count": 0,
            "strict_fail_count": 0,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "source_published_parity_ok": False if malformed else _entry_bool(entry, "source_published_parity_ok"),
        "marker_parity_ok": False if malformed else _entry_bool(entry, "marker_parity_ok"),
        "tokens_parity_ok": False if malformed else _entry_bool(entry, "tokens_parity_ok"),
        "tokens_data_parity_ok": False if malformed else _entry_bool(entry, "tokens_data_parity_ok"),
        "css_parity_ok": False if malformed else _entry_bool(entry, "css_parity_ok"),
        "ui_html_parity_ok": False if malformed else _entry_bool(entry, "ui_html_parity_ok"),
        "parity_fail_count": 0 if malformed else _to_int(entry.get("parity_fail_count"), 0),
        "strict_fail_count": 0 if malformed else _to_int(entry.get("strict_fail_count"), 0),
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
    max_parity_mismatch: int = DEFAULT_MAX_PARITY_MISMATCH,
    max_parity_mismatch_rate_pct: float = DEFAULT_MAX_PARITY_MISMATCH_RATE_PCT,
    max_tokens_parity_mismatch: int = DEFAULT_MAX_TOKENS_PARITY_MISMATCH,
    max_tokens_data_parity_mismatch: int = DEFAULT_MAX_TOKENS_DATA_PARITY_MISMATCH,
    max_css_parity_mismatch: int = DEFAULT_MAX_CSS_PARITY_MISMATCH,
    max_ui_html_parity_mismatch: int = DEFAULT_MAX_UI_HTML_PARITY_MISMATCH,
    max_marker_mismatch: int = DEFAULT_MAX_MARKER_MISMATCH,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_degraded_n = _parse_non_negative_int(max_degraded, arg_name="max_degraded")
    max_degraded_rate = _parse_non_negative_float(max_degraded_rate_pct, arg_name="max_degraded_rate_pct")
    max_parity_mismatch_n = _parse_non_negative_int(max_parity_mismatch, arg_name="max_parity_mismatch")
    max_parity_mismatch_rate = _parse_non_negative_float(max_parity_mismatch_rate_pct, arg_name="max_parity_mismatch_rate_pct")
    max_tokens_parity_mismatch_n = _parse_non_negative_int(max_tokens_parity_mismatch, arg_name="max_tokens_parity_mismatch")
    max_tokens_data_parity_mismatch_n = _parse_non_negative_int(
        max_tokens_data_parity_mismatch,
        arg_name="max_tokens_data_parity_mismatch",
    )
    max_css_parity_mismatch_n = _parse_non_negative_int(max_css_parity_mismatch, arg_name="max_css_parity_mismatch")
    max_ui_html_parity_mismatch_n = _parse_non_negative_int(max_ui_html_parity_mismatch, arg_name="max_ui_html_parity_mismatch")
    max_marker_mismatch_n = _parse_non_negative_int(max_marker_mismatch, arg_name="max_marker_mismatch")

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
            "max_parity_mismatch": int(max_parity_mismatch_n),
            "max_parity_mismatch_rate_pct": float(max_parity_mismatch_rate),
            "max_tokens_parity_mismatch": int(max_tokens_parity_mismatch_n),
            "max_tokens_data_parity_mismatch": int(max_tokens_data_parity_mismatch_n),
            "max_css_parity_mismatch": int(max_css_parity_mismatch_n),
            "max_ui_html_parity_mismatch": int(max_ui_html_parity_mismatch_n),
            "max_marker_mismatch": int(max_marker_mismatch_n),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "degraded_in_window": 0,
        "degraded_rate_pct": 0.0,
        "parity_mismatch_in_window": 0,
        "parity_mismatch_rate_pct": 0.0,
        "tokens_parity_mismatch_in_window": 0,
        "tokens_data_parity_mismatch_in_window": 0,
        "css_parity_mismatch_in_window": 0,
        "ui_html_parity_mismatch_in_window": 0,
        "marker_mismatch_in_window": 0,
        "first_parity_mismatch_run_at": "",
        "last_parity_mismatch_run_at": "",
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
            "max_parity_mismatch_ok": False,
            "max_parity_mismatch_rate_ok": False,
            "max_tokens_parity_mismatch_ok": False,
            "max_tokens_data_parity_mismatch_ok": False,
            "max_css_parity_mismatch_ok": False,
            "max_ui_html_parity_mismatch_ok": False,
            "max_marker_mismatch_ok": False,
            "latest_not_failed_ok": False,
            "latest_source_published_parity_ok": False,
            "latest_marker_parity_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "degraded",
    }

    if not window_rows:
        report["strict_fail_reasons"] = ["window_empty"]
        report["latest"] = _latest_summary(None)
        report["status"] = "failed"
        return report

    first_parity_mismatch = ""
    last_parity_mismatch = ""
    for row in window_rows:
        malformed = bool(row.get("malformed_line"))
        if malformed:
            report["malformed_entries_in_window"] += 1
            report["status_counts"]["failed"] += 1
            continue

        entry = _safe_obj(row.get("entry"))
        status = _normalize_status(entry.get("status"))
        report["status_counts"][status] += 1

        if status == "failed":
            report["failed_in_window"] += 1
        elif status == "degraded":
            report["degraded_in_window"] += 1

        tokens_mismatch = not _entry_bool(entry, "tokens_parity_ok")
        tokens_data_mismatch = not _entry_bool(entry, "tokens_data_parity_ok")
        css_mismatch = not _entry_bool(entry, "css_parity_ok")
        ui_html_mismatch = not _entry_bool(entry, "ui_html_parity_ok")
        marker_mismatch = not _entry_bool(entry, "marker_parity_ok")
        parity_mismatch = _row_parity_mismatch(entry)

        if tokens_mismatch:
            report["tokens_parity_mismatch_in_window"] += 1
        if tokens_data_mismatch:
            report["tokens_data_parity_mismatch_in_window"] += 1
        if css_mismatch:
            report["css_parity_mismatch_in_window"] += 1
        if ui_html_mismatch:
            report["ui_html_parity_mismatch_in_window"] += 1
        if marker_mismatch:
            report["marker_mismatch_in_window"] += 1
        if parity_mismatch:
            report["parity_mismatch_in_window"] += 1
            run_at = _safe_text(entry.get("run_at"))
            if run_at:
                if not first_parity_mismatch:
                    first_parity_mismatch = run_at
                last_parity_mismatch = run_at

    entries_in_window = int(report["entries_in_window"])
    if entries_in_window > 0:
        report["failed_rate_pct"] = _round4((float(report["failed_in_window"]) * 100.0) / entries_in_window)
        report["degraded_rate_pct"] = _round4((float(report["degraded_in_window"]) * 100.0) / entries_in_window)
        report["parity_mismatch_rate_pct"] = _round4((float(report["parity_mismatch_in_window"]) * 100.0) / entries_in_window)

    report["first_parity_mismatch_run_at"] = first_parity_mismatch
    report["last_parity_mismatch_run_at"] = last_parity_mismatch
    report["failed_streak_latest"] = _latest_streak(window_rows, status="failed")
    report["degraded_streak_latest"] = _latest_streak(window_rows, status="degraded")
    report["latest"] = _latest_summary(window_rows[-1] if window_rows else None)

    latest = _safe_obj(report.get("latest"))
    checks = _safe_obj(report.get("checks"))
    checks["window_nonempty_ok"] = entries_in_window > 0
    checks["malformed_entries_ok"] = int(report["malformed_entries_in_window"]) == 0
    checks["max_failed_ok"] = int(report["failed_in_window"]) <= max_failed_n
    checks["max_failed_rate_ok"] = float(report["failed_rate_pct"]) <= max_failed_rate
    checks["max_degraded_ok"] = int(report["degraded_in_window"]) <= max_degraded_n
    checks["max_degraded_rate_ok"] = float(report["degraded_rate_pct"]) <= max_degraded_rate
    checks["max_parity_mismatch_ok"] = int(report["parity_mismatch_in_window"]) <= max_parity_mismatch_n
    checks["max_parity_mismatch_rate_ok"] = float(report["parity_mismatch_rate_pct"]) <= max_parity_mismatch_rate
    checks["max_tokens_parity_mismatch_ok"] = int(report["tokens_parity_mismatch_in_window"]) <= max_tokens_parity_mismatch_n
    checks["max_tokens_data_parity_mismatch_ok"] = int(report["tokens_data_parity_mismatch_in_window"]) <= max_tokens_data_parity_mismatch_n
    checks["max_css_parity_mismatch_ok"] = int(report["css_parity_mismatch_in_window"]) <= max_css_parity_mismatch_n
    checks["max_ui_html_parity_mismatch_ok"] = int(report["ui_html_parity_mismatch_in_window"]) <= max_ui_html_parity_mismatch_n
    checks["max_marker_mismatch_ok"] = int(report["marker_mismatch_in_window"]) <= max_marker_mismatch_n
    checks["latest_not_failed_ok"] = _normalize_status(latest.get("status")) != "failed"
    checks["latest_source_published_parity_ok"] = bool(latest.get("source_published_parity_ok"))
    checks["latest_marker_parity_ok"] = bool(latest.get("marker_parity_ok"))
    report["checks"] = checks

    strict_fail_reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        strict_fail_reasons.append("window_empty")
    if not checks["malformed_entries_ok"]:
        strict_fail_reasons.append("malformed_entries_present")
    if not checks["max_failed_ok"]:
        strict_fail_reasons.append("max_failed_exceeded")
    if not checks["max_failed_rate_ok"]:
        strict_fail_reasons.append("max_failed_rate_exceeded")
    if not checks["max_degraded_ok"]:
        strict_fail_reasons.append("max_degraded_exceeded")
    if not checks["max_degraded_rate_ok"]:
        strict_fail_reasons.append("max_degraded_rate_exceeded")
    if not checks["max_parity_mismatch_ok"]:
        strict_fail_reasons.append("max_parity_mismatch_exceeded")
    if not checks["max_parity_mismatch_rate_ok"]:
        strict_fail_reasons.append("max_parity_mismatch_rate_exceeded")
    if not checks["max_tokens_parity_mismatch_ok"]:
        strict_fail_reasons.append("max_tokens_parity_mismatch_exceeded")
    if not checks["max_tokens_data_parity_mismatch_ok"]:
        strict_fail_reasons.append("max_tokens_data_parity_mismatch_exceeded")
    if not checks["max_css_parity_mismatch_ok"]:
        strict_fail_reasons.append("max_css_parity_mismatch_exceeded")
    if not checks["max_ui_html_parity_mismatch_ok"]:
        strict_fail_reasons.append("max_ui_html_parity_mismatch_exceeded")
    if not checks["max_marker_mismatch_ok"]:
        strict_fail_reasons.append("max_marker_mismatch_exceeded")
    if not checks["latest_not_failed_ok"]:
        strict_fail_reasons.append("latest_failed")
    if not checks["latest_source_published_parity_ok"]:
        strict_fail_reasons.append("latest_source_published_parity_mismatch")
    if not checks["latest_marker_parity_ok"]:
        strict_fail_reasons.append("latest_marker_parity_mismatch")

    report["strict_fail_reasons"] = sorted(set(strict_fail_reasons))
    if report["strict_fail_reasons"]:
        report["status"] = "failed"
    elif int(report["failed_in_window"]) > 0 or int(report["degraded_in_window"]) > 0 or int(report["parity_mismatch_in_window"]) > 0:
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
            window_last=args.last,
            max_failed=args.max_failed,
            max_failed_rate_pct=args.max_failed_rate_pct,
            max_degraded=args.max_degraded,
            max_degraded_rate_pct=args.max_degraded_rate_pct,
            max_parity_mismatch=args.max_parity_mismatch,
            max_parity_mismatch_rate_pct=args.max_parity_mismatch_rate_pct,
            max_tokens_parity_mismatch=args.max_tokens_parity_mismatch,
            max_tokens_data_parity_mismatch=args.max_tokens_data_parity_mismatch,
            max_css_parity_mismatch=args.max_css_parity_mismatch,
            max_ui_html_parity_mismatch=args.max_ui_html_parity_mismatch,
            max_marker_mismatch=args.max_marker_mismatch,
            strict=bool(args.strict),
            heartbeat_path=str(heartbeat_path),
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

    if bool(args.strict) and len(_safe_list_str(report.get("strict_fail_reasons"))) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
