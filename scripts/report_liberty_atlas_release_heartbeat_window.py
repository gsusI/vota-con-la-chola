#!/usr/bin/env python3
"""Window report for liberty atlas release heartbeat."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/liberty_atlas_release_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_DEGRADED = 20
DEFAULT_MAX_STALE_ALERTS = 0
DEFAULT_MAX_DRIFT_ALERTS = 0
DEFAULT_MAX_HF_UNAVAILABLE = 20


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Liberty atlas release heartbeat window report")
    p.add_argument("--heartbeat-jsonl", default=str(DEFAULT_HEARTBEAT_JSONL))
    p.add_argument("--last", type=int, default=DEFAULT_LAST)
    p.add_argument("--max-failed", type=int, default=DEFAULT_MAX_FAILED)
    p.add_argument("--max-degraded", type=int, default=DEFAULT_MAX_DEGRADED)
    p.add_argument("--max-stale-alerts", type=int, default=DEFAULT_MAX_STALE_ALERTS)
    p.add_argument("--max-drift-alerts", type=int, default=DEFAULT_MAX_DRIFT_ALERTS)
    p.add_argument("--max-hf-unavailable", type=int, default=DEFAULT_MAX_HF_UNAVAILABLE)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--out", default="")
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
            "snapshot_date_expected": "",
            "stale_alerts_count": 0,
            "drift_alerts_count": 0,
            "hf_unavailable": True,
            "checks": {},
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "snapshot_date_expected": _safe_text(entry.get("snapshot_date_expected")),
        "stale_alerts_count": _to_int(entry.get("stale_alerts_count"), 0),
        "drift_alerts_count": _to_int(entry.get("drift_alerts_count"), 0),
        "hf_unavailable": bool(entry.get("hf_unavailable")),
        "checks": _safe_obj(entry.get("checks")),
    }


def build_window_report(
    rows: list[dict[str, Any]],
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_degraded: int = DEFAULT_MAX_DEGRADED,
    max_stale_alerts: int = DEFAULT_MAX_STALE_ALERTS,
    max_drift_alerts: int = DEFAULT_MAX_DRIFT_ALERTS,
    max_hf_unavailable: int = DEFAULT_MAX_HF_UNAVAILABLE,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_degraded_n = _parse_non_negative_int(max_degraded, arg_name="max_degraded")
    max_stale_alerts_n = _parse_non_negative_int(max_stale_alerts, arg_name="max_stale_alerts")
    max_drift_alerts_n = _parse_non_negative_int(max_drift_alerts, arg_name="max_drift_alerts")
    max_hf_unavailable_n = _parse_non_negative_int(max_hf_unavailable, arg_name="max_hf_unavailable")

    window_rows = rows[max(0, len(rows) - window_size) :]
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "window_last": int(window_size),
        "thresholds": {
            "max_failed": int(max_failed_n),
            "max_degraded": int(max_degraded_n),
            "max_stale_alerts": int(max_stale_alerts_n),
            "max_drift_alerts": int(max_drift_alerts_n),
            "max_hf_unavailable": int(max_hf_unavailable_n),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "degraded_in_window": 0,
        "degraded_rate_pct": 0.0,
        "stale_alerts_in_window": 0,
        "drift_alerts_in_window": 0,
        "hf_unavailable_in_window": 0,
        "latest": {},
        "checks": {
            "window_nonempty_ok": False,
            "malformed_entries_ok": False,
            "max_failed_ok": False,
            "max_degraded_ok": False,
            "max_stale_alerts_ok": False,
            "max_drift_alerts_ok": False,
            "max_hf_unavailable_ok": False,
            "latest_not_failed_ok": False,
            "latest_no_stale_alerts_ok": False,
            "latest_no_drift_alerts_ok": False,
            "latest_continuity_ok": False,
            "latest_published_gh_parity_ok": False,
            "latest_expected_snapshot_match_ok": False,
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
        report["status_counts"][status] = int(report["status_counts"].get(status, 0)) + 1
        report["stale_alerts_in_window"] = int(report["stale_alerts_in_window"]) + _to_int(
            entry.get("stale_alerts_count"), 0
        )
        report["drift_alerts_in_window"] = int(report["drift_alerts_in_window"]) + _to_int(
            entry.get("drift_alerts_count"), 0
        )
        if bool(entry.get("hf_unavailable")):
            report["hf_unavailable_in_window"] = int(report["hf_unavailable_in_window"]) + 1

    report["failed_in_window"] = int(report["status_counts"]["failed"])
    report["degraded_in_window"] = int(report["status_counts"]["degraded"])

    if report["entries_in_window"] > 0:
        denom = int(report["entries_in_window"])
        report["failed_rate_pct"] = _rate_pct(int(report["failed_in_window"]), denom)
        report["degraded_rate_pct"] = _rate_pct(int(report["degraded_in_window"]), denom)
        report["latest"] = _latest_summary(window_rows[-1])
    else:
        report["latest"] = _latest_summary(None)

    latest = _safe_obj(report.get("latest"))
    latest_checks = _safe_obj(latest.get("checks"))
    checks = _safe_obj(report.get("checks"))
    checks["window_nonempty_ok"] = report["entries_in_window"] > 0
    checks["malformed_entries_ok"] = report["malformed_entries_in_window"] == 0
    checks["max_failed_ok"] = report["failed_in_window"] <= max_failed_n
    checks["max_degraded_ok"] = report["degraded_in_window"] <= max_degraded_n
    checks["max_stale_alerts_ok"] = report["stale_alerts_in_window"] <= max_stale_alerts_n
    checks["max_drift_alerts_ok"] = report["drift_alerts_in_window"] <= max_drift_alerts_n
    checks["max_hf_unavailable_ok"] = report["hf_unavailable_in_window"] <= max_hf_unavailable_n
    checks["latest_not_failed_ok"] = (
        report["entries_in_window"] > 0
        and not bool(latest.get("malformed_line"))
        and _normalize_status(latest.get("status")) != "failed"
    )
    checks["latest_no_stale_alerts_ok"] = report["entries_in_window"] > 0 and _to_int(
        latest.get("stale_alerts_count"), 0
    ) == 0
    checks["latest_no_drift_alerts_ok"] = report["entries_in_window"] > 0 and _to_int(
        latest.get("drift_alerts_count"), 0
    ) == 0
    checks["latest_continuity_ok"] = report["entries_in_window"] > 0 and bool(latest_checks.get("continuity_ok"))
    checks["latest_published_gh_parity_ok"] = report["entries_in_window"] > 0 and bool(
        latest_checks.get("published_gh_parity_ok")
    )
    checks["latest_expected_snapshot_match_ok"] = report["entries_in_window"] > 0 and bool(
        latest_checks.get("expected_snapshot_match_ok")
    )
    report["checks"] = checks

    reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        reasons.append("empty_window")
    if not checks["malformed_entries_ok"]:
        reasons.append("malformed_entries_present")
    if not checks["max_failed_ok"]:
        reasons.append("max_failed_exceeded")
    if not checks["max_degraded_ok"]:
        reasons.append("max_degraded_exceeded")
    if not checks["max_stale_alerts_ok"]:
        reasons.append("max_stale_alerts_exceeded")
    if not checks["max_drift_alerts_ok"]:
        reasons.append("max_drift_alerts_exceeded")
    if not checks["max_hf_unavailable_ok"]:
        reasons.append("max_hf_unavailable_exceeded")
    if not checks["latest_not_failed_ok"]:
        reasons.append("latest_status_failed")
    if not checks["latest_no_stale_alerts_ok"]:
        reasons.append("latest_stale_alert_present")
    if not checks["latest_no_drift_alerts_ok"]:
        reasons.append("latest_drift_alert_present")
    if not checks["latest_continuity_ok"]:
        reasons.append("latest_continuity_not_ok")
    if not checks["latest_published_gh_parity_ok"]:
        reasons.append("latest_published_gh_parity_not_ok")
    if not checks["latest_expected_snapshot_match_ok"]:
        reasons.append("latest_expected_snapshot_mismatch")

    report["strict_fail_reasons"] = reasons

    if report["entries_in_window"] == 0:
        report["status"] = "degraded"
    elif report["malformed_entries_in_window"] > 0:
        report["status"] = "failed"
    elif reasons:
        report["status"] = "failed"
    elif report["degraded_in_window"] > 0 or report["hf_unavailable_in_window"] > 0:
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report


def build_window_report_from_path(
    heartbeat_path: Path,
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_degraded: int = DEFAULT_MAX_DEGRADED,
    max_stale_alerts: int = DEFAULT_MAX_STALE_ALERTS,
    max_drift_alerts: int = DEFAULT_MAX_DRIFT_ALERTS,
    max_hf_unavailable: int = DEFAULT_MAX_HF_UNAVAILABLE,
    strict: bool = False,
) -> dict[str, Any]:
    rows = read_heartbeat_rows(heartbeat_path)
    return build_window_report(
        rows,
        window_last=window_last,
        max_failed=max_failed,
        max_degraded=max_degraded,
        max_stale_alerts=max_stale_alerts,
        max_drift_alerts=max_drift_alerts,
        max_hf_unavailable=max_hf_unavailable,
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
            max_degraded=int(args.max_degraded),
            max_stale_alerts=int(args.max_stale_alerts),
            max_drift_alerts=int(args.max_drift_alerts),
            max_hf_unavailable=int(args.max_hf_unavailable),
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

    out_path_token = _safe_text(args.out)
    if out_path_token:
        out_path = Path(out_path_token)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
