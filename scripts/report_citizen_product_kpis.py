#!/usr/bin/env python3
"""Machine-readable KPI contract for the citizen product lane.

KPI v1:
- unknown_rate (from citizen snapshot quality contract)
- time_to_first_answer_seconds (from optional telemetry artifacts)
- drilldown_click_rate (from optional telemetry artifacts)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_SNAPSHOT = Path("docs/gh-pages/citizen/data/citizen.json")
DEFAULT_MAX_UNKNOWN_RATE = 0.45
DEFAULT_MAX_TIME_TO_FIRST_ANSWER_SECONDS = 120.0
DEFAULT_MIN_DRILLDOWN_CLICK_RATE = 0.20

_EVENT_NAMES_SESSION_START = {
    "session_start",
    "page_load",
    "view_loaded",
    "app_loaded",
    "onboarding_start",
}
_EVENT_NAMES_FIRST_ANSWER = {
    "first_answer",
    "answer_ready",
    "alignment_result",
    "onboarding_answer",
}
_EVENT_NAMES_DRILLDOWN = {
    "drilldown_click",
    "open_drilldown",
    "open_evidence",
    "evidence_link_click",
    "open_explorer",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen product KPI contract report")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT), help="Path to citizen snapshot JSON")
    ap.add_argument(
        "--telemetry-json",
        default="",
        help="Optional telemetry summary JSON path (if it already contains pre-aggregated KPIs)",
    )
    ap.add_argument(
        "--telemetry-events-jsonl",
        default="",
        help="Optional telemetry events JSONL path (session/event rows)",
    )
    ap.add_argument("--max-unknown-rate", type=float, default=DEFAULT_MAX_UNKNOWN_RATE)
    ap.add_argument(
        "--max-time-to-first-answer-seconds",
        type=float,
        default=DEFAULT_MAX_TIME_TO_FIRST_ANSWER_SECONDS,
    )
    ap.add_argument("--min-drilldown-click-rate", type=float, default=DEFAULT_MIN_DRILLDOWN_CLICK_RATE)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when KPI status is failed")
    ap.add_argument(
        "--strict-require-complete",
        action="store_true",
        help="With --strict, also fail when status is degraded (missing metrics).",
    )
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args(argv)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _norm_token(v: Any) -> str:
    return str(v or "").strip().lower().replace("-", "_").replace(" ", "_")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    return obj


def _extract_unknown_rate(snapshot: dict[str, Any]) -> tuple[float | None, str]:
    meta = snapshot.get("meta")
    if isinstance(meta, dict):
        quality = meta.get("quality")
        if isinstance(quality, dict):
            unknown_pct = _safe_float(quality.get("unknown_pct"))
            if unknown_pct is not None:
                return round(_clamp01(float(unknown_pct)), 6), "meta.quality.unknown_pct"

    rows = snapshot.get("party_topic_positions")
    if isinstance(rows, list) and rows:
        unknown_n = 0
        for row in rows:
            stance = ""
            if isinstance(row, dict):
                stance = _norm_token(row.get("stance"))
            if stance in {"no_signal", "unclear"}:
                unknown_n += 1
        return round(float(unknown_n) / float(len(rows)), 6), "party_topic_positions.stance"

    return None, ""


def _parse_iso_ts(v: Any) -> datetime | None:
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        as_num = _safe_float(s)
        if as_num is None:
            return None
        return _parse_iso_ts(as_num)


def _extract_metric_from_summary(obj: dict[str, Any], paths: list[tuple[str, ...]]) -> float | None:
    for p in paths:
        cur: Any = obj
        ok = True
        for key in p:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if not ok:
            continue
        fv = _safe_float(cur)
        if fv is not None:
            return fv
    return None


def _extract_count_from_summary(obj: dict[str, Any], paths: list[tuple[str, ...]]) -> int | None:
    for p in paths:
        cur: Any = obj
        ok = True
        for key in p:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if not ok:
            continue
        iv = _safe_int(cur)
        if iv is not None:
            return iv
    return None


def _read_telemetry_summary(path: Path) -> dict[str, Any]:
    obj = _load_json(path)
    tfa = _extract_metric_from_summary(
        obj,
        [
            ("time_to_first_answer_seconds",),
            ("metrics", "time_to_first_answer_seconds"),
            ("kpis", "time_to_first_answer_seconds"),
        ],
    )
    drill = _extract_metric_from_summary(
        obj,
        [
            ("drilldown_click_rate",),
            ("metrics", "drilldown_click_rate"),
            ("kpis", "drilldown_click_rate"),
        ],
    )
    sessions_total = _extract_count_from_summary(
        obj,
        [
            ("sessions_total",),
            ("telemetry", "sessions_total"),
            ("counts", "sessions_total"),
        ],
    )
    sessions_first = _extract_count_from_summary(
        obj,
        [
            ("sessions_with_first_answer",),
            ("telemetry", "sessions_with_first_answer"),
            ("counts", "sessions_with_first_answer"),
        ],
    )
    sessions_drill = _extract_count_from_summary(
        obj,
        [
            ("sessions_with_drilldown_click",),
            ("telemetry", "sessions_with_drilldown_click"),
            ("counts", "sessions_with_drilldown_click"),
        ],
    )
    return {
        "time_to_first_answer_seconds": round(float(tfa), 6) if tfa is not None else None,
        "drilldown_click_rate": round(_clamp01(float(drill)), 6) if drill is not None else None,
        "sessions_total": sessions_total,
        "sessions_with_first_answer": sessions_first,
        "sessions_with_drilldown_click": sessions_drill,
        "events_total": None,
        "parse_errors": None,
        "source": "telemetry_json",
    }


def _read_telemetry_events_jsonl(path: Path) -> dict[str, Any]:
    sessions: dict[str, dict[str, Any]] = {}
    parse_errors = 0
    events_total = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        ln = line.strip()
        if not ln:
            continue
        events_total += 1
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(row, dict):
            parse_errors += 1
            continue

        sid = ""
        for k in ("session_id", "sessionId", "session", "sid", "user_session_id"):
            v = str(row.get(k) or "").strip()
            if v:
                sid = v
                break
        if not sid:
            parse_errors += 1
            continue

        state = sessions.setdefault(
            sid,
            {
                "start_ts": None,
                "first_answer_ts": None,
                "first_answer_elapsed_ms": None,
                "drilldown_clicks": 0,
            },
        )
        event_name = ""
        for k in ("event", "event_name", "name", "type", "action"):
            token = _norm_token(row.get(k))
            if token:
                event_name = token
                break

        ts = None
        for k in ("timestamp", "ts", "at", "time"):
            parsed = _parse_iso_ts(row.get(k))
            if parsed is not None:
                ts = parsed
                break

        if event_name in _EVENT_NAMES_SESSION_START and ts is not None:
            prev = state.get("start_ts")
            if prev is None or ts < prev:
                state["start_ts"] = ts

        if event_name in _EVENT_NAMES_FIRST_ANSWER:
            for k in ("elapsed_ms", "duration_ms", "time_to_first_answer_ms", "tfa_ms"):
                ms = _safe_float(row.get(k))
                if ms is not None and ms >= 0.0:
                    prev_ms = _safe_float(state.get("first_answer_elapsed_ms"))
                    if prev_ms is None or ms < prev_ms:
                        state["first_answer_elapsed_ms"] = float(ms)
                    break
            if ts is not None:
                prev = state.get("first_answer_ts")
                if prev is None or ts < prev:
                    state["first_answer_ts"] = ts

        if event_name in _EVENT_NAMES_DRILLDOWN:
            state["drilldown_clicks"] = int(state.get("drilldown_clicks") or 0) + 1

    sessions_total = len(sessions)
    sessions_with_drilldown_click = sum(
        1 for state in sessions.values() if int(state.get("drilldown_clicks") or 0) > 0
    )

    tfa_values: list[float] = []
    for state in sessions.values():
        elapsed_ms = _safe_float(state.get("first_answer_elapsed_ms"))
        if elapsed_ms is not None and elapsed_ms >= 0.0:
            tfa_values.append(float(elapsed_ms) / 1000.0)
            continue

        start_ts = state.get("start_ts")
        first_ts = state.get("first_answer_ts")
        if isinstance(start_ts, datetime) and isinstance(first_ts, datetime) and first_ts >= start_ts:
            tfa_values.append((first_ts - start_ts).total_seconds())

    sessions_with_first_answer = len(tfa_values)
    tfa_seconds = round(float(median(tfa_values)), 6) if tfa_values else None
    drill_rate = (
        round(_clamp01(float(sessions_with_drilldown_click) / float(sessions_total)), 6)
        if sessions_total > 0
        else None
    )

    return {
        "time_to_first_answer_seconds": tfa_seconds,
        "drilldown_click_rate": drill_rate,
        "sessions_total": sessions_total,
        "sessions_with_first_answer": sessions_with_first_answer,
        "sessions_with_drilldown_click": sessions_with_drilldown_click,
        "events_total": events_total,
        "parse_errors": parse_errors,
        "source": "telemetry_events_jsonl",
    }


def _merge_telemetry(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    out = dict(primary)
    for key in (
        "time_to_first_answer_seconds",
        "drilldown_click_rate",
        "sessions_total",
        "sessions_with_first_answer",
        "sessions_with_drilldown_click",
        "events_total",
        "parse_errors",
    ):
        if out.get(key) is None and secondary.get(key) is not None:
            out[key] = secondary.get(key)
    return out


def build_report(
    *,
    snapshot: dict[str, Any],
    telemetry_summary: dict[str, Any] | None,
    telemetry_events: dict[str, Any] | None,
    snapshot_path: Path,
    telemetry_json_path: Path | None,
    telemetry_events_path: Path | None,
    max_unknown_rate: float,
    max_time_to_first_answer_seconds: float,
    min_drilldown_click_rate: float,
) -> dict[str, Any]:
    unknown_rate, unknown_source = _extract_unknown_rate(snapshot)

    telemetry_merged: dict[str, Any] = {
        "time_to_first_answer_seconds": None,
        "drilldown_click_rate": None,
        "sessions_total": None,
        "sessions_with_first_answer": None,
        "sessions_with_drilldown_click": None,
        "events_total": None,
        "parse_errors": None,
    }
    telemetry_sources: list[str] = []
    if telemetry_summary is not None:
        telemetry_merged = _merge_telemetry(telemetry_merged, telemetry_summary)
        telemetry_sources.append(str(telemetry_summary.get("source") or "telemetry_json"))
    if telemetry_events is not None:
        telemetry_merged = _merge_telemetry(telemetry_merged, telemetry_events)
        telemetry_sources.append(str(telemetry_events.get("source") or "telemetry_events_jsonl"))

    tfa_seconds = _safe_float(telemetry_merged.get("time_to_first_answer_seconds"))
    drill_rate = _safe_float(telemetry_merged.get("drilldown_click_rate"))

    missing_metrics: list[str] = []
    failure_reasons: list[str] = []

    unknown_ok = False
    if unknown_rate is None:
        missing_metrics.append("unknown_rate")
        failure_reasons.append("unknown_rate_missing")
    else:
        unknown_ok = float(unknown_rate) <= float(max_unknown_rate)
        if not unknown_ok:
            failure_reasons.append("unknown_rate_above_threshold")

    tfa_ok: bool | None = None
    if tfa_seconds is None:
        missing_metrics.append("time_to_first_answer_seconds")
    else:
        tfa_ok = float(tfa_seconds) <= float(max_time_to_first_answer_seconds)
        if not tfa_ok:
            failure_reasons.append("time_to_first_answer_above_threshold")

    drill_ok: bool | None = None
    if drill_rate is None:
        missing_metrics.append("drilldown_click_rate")
    else:
        drill_ok = float(drill_rate) >= float(min_drilldown_click_rate)
        if not drill_ok:
            failure_reasons.append("drilldown_click_rate_below_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif missing_metrics:
        status = "degraded"

    checks: dict[str, Any] = {
        "unknown_rate_within_threshold": bool(unknown_ok),
        "time_to_first_answer_within_threshold": tfa_ok,
        "drilldown_click_rate_within_threshold": drill_ok,
        "telemetry_available": bool(tfa_seconds is not None or drill_rate is not None),
        "contract_complete": bool(
            unknown_rate is not None and tfa_seconds is not None and drill_rate is not None and status == "ok"
        ),
    }

    report = {
        "generated_at": now_utc_iso(),
        "snapshot_path": str(snapshot_path),
        "telemetry_json_path": str(telemetry_json_path) if telemetry_json_path else None,
        "telemetry_events_jsonl_path": str(telemetry_events_path) if telemetry_events_path else None,
        "telemetry_sources": sorted(set(telemetry_sources)),
        "telemetry": {
            "sessions_total": _safe_int(telemetry_merged.get("sessions_total")),
            "sessions_with_first_answer": _safe_int(telemetry_merged.get("sessions_with_first_answer")),
            "sessions_with_drilldown_click": _safe_int(telemetry_merged.get("sessions_with_drilldown_click")),
            "events_total": _safe_int(telemetry_merged.get("events_total")),
            "parse_errors": _safe_int(telemetry_merged.get("parse_errors")),
        },
        "metrics": {
            "unknown_rate": round(float(unknown_rate), 6) if unknown_rate is not None else None,
            "unknown_rate_source": unknown_source or None,
            "time_to_first_answer_seconds": round(float(tfa_seconds), 6) if tfa_seconds is not None else None,
            "drilldown_click_rate": round(_clamp01(float(drill_rate)), 6) if drill_rate is not None else None,
        },
        "thresholds": {
            "max_unknown_rate": round(_clamp01(float(max_unknown_rate)), 6),
            "max_time_to_first_answer_seconds": round(float(max_time_to_first_answer_seconds), 6),
            "min_drilldown_click_rate": round(_clamp01(float(min_drilldown_click_rate)), 6),
        },
        "checks": checks,
        "missing_metrics": sorted(set(missing_metrics)),
        "failure_reasons": sorted(set(failure_reasons)),
        "status": status,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        print(json.dumps({"error": f"snapshot not found: {snapshot_path}"}, ensure_ascii=False))
        return 2

    telemetry_json_path = Path(str(args.telemetry_json).strip()) if str(args.telemetry_json).strip() else None
    if telemetry_json_path is not None and not telemetry_json_path.exists():
        print(json.dumps({"error": f"telemetry-json not found: {telemetry_json_path}"}, ensure_ascii=False))
        return 2

    telemetry_events_path = (
        Path(str(args.telemetry_events_jsonl).strip()) if str(args.telemetry_events_jsonl).strip() else None
    )
    if telemetry_events_path is not None and not telemetry_events_path.exists():
        print(json.dumps({"error": f"telemetry-events-jsonl not found: {telemetry_events_path}"}, ensure_ascii=False))
        return 2

    try:
        snapshot = _load_json(snapshot_path)
        telemetry_summary = _read_telemetry_summary(telemetry_json_path) if telemetry_json_path is not None else None
        telemetry_events = (
            _read_telemetry_events_jsonl(telemetry_events_path) if telemetry_events_path is not None else None
        )
        report = build_report(
            snapshot=snapshot,
            telemetry_summary=telemetry_summary,
            telemetry_events=telemetry_events,
            snapshot_path=snapshot_path,
            telemetry_json_path=telemetry_json_path,
            telemetry_events_path=telemetry_events_path,
            max_unknown_rate=float(args.max_unknown_rate),
            max_time_to_first_answer_seconds=float(args.max_time_to_first_answer_seconds),
            min_drilldown_click_rate=float(args.min_drilldown_click_rate),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    status = str(report.get("status") or "")
    if bool(args.strict):
        if status == "failed":
            return 4
        if bool(args.strict_require_complete) and status != "ok":
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
