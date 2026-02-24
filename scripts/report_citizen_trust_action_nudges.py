#!/usr/bin/env python3
"""Machine-readable trust-action nudge KPI digest for /citizen."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_JSONL = Path("tests/fixtures/citizen_trust_action_nudge_events_sample.jsonl")
DEFAULT_MIN_NUDGE_SHOWN_EVENTS = 8
DEFAULT_MIN_NUDGE_SHOWN_SESSIONS = 5
DEFAULT_MIN_NUDGE_CLICKTHROUGH_RATE = 0.40

_EVENT_SHOWN = "trust_action_nudge_shown"
_EVENT_CLICKED = "trust_action_nudge_clicked"
_EVENT_NAMES = {_EVENT_SHOWN, _EVENT_CLICKED}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen trust-action nudge report")
    ap.add_argument("--events-jsonl", default=str(DEFAULT_EVENTS_JSONL))
    ap.add_argument("--min-nudge-shown-events", type=int, default=DEFAULT_MIN_NUDGE_SHOWN_EVENTS)
    ap.add_argument("--min-nudge-shown-sessions", type=int, default=DEFAULT_MIN_NUDGE_SHOWN_SESSIONS)
    ap.add_argument("--min-nudge-clickthrough-rate", type=float, default=DEFAULT_MIN_NUDGE_CLICKTHROUGH_RATE)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when status is failed")
    ap.add_argument(
        "--strict-require-complete",
        action="store_true",
        help="With --strict, also fail when status is degraded (missing/insufficient telemetry).",
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


def _norm_token(v: Any) -> str:
    return str(v or "").strip().lower().replace("-", "_").replace(" ", "_")


def _session_id(row: dict[str, Any]) -> str:
    for key in ("session_id", "sessionId", "session", "sid"):
        token = str(row.get(key) or "").strip()
        if token:
            return token
    return "global"


def _ratio(numer: int, denom: int) -> float | None:
    if denom <= 0:
        return None
    return float(numer) / float(denom)


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _read_events(events_path: Path) -> dict[str, Any]:
    parse_errors = 0
    events_total = 0
    recognized_events_total = 0
    ignored_events_total = 0

    shown_events = 0
    clicked_events = 0

    sessions: dict[str, dict[str, bool]] = {}
    by_view: dict[str, dict[str, int]] = {}

    def _ensure_session(sid: str) -> dict[str, bool]:
        st = sessions.get(sid)
        if st is None:
            st = {"shown": False, "clicked": False}
            sessions[sid] = st
        return st

    def _ensure_view(view: str) -> dict[str, int]:
        row = by_view.get(view)
        if row is None:
            row = {"nudge_shown_events": 0, "nudge_clicked_events": 0}
            by_view[view] = row
        return row

    for line in events_path.read_text(encoding="utf-8").splitlines():
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

        event_name = _norm_token(row.get("event_type") or row.get("event") or row.get("name") or row.get("type"))
        if not event_name:
            parse_errors += 1
            continue
        if event_name not in _EVENT_NAMES:
            ignored_events_total += 1
            continue

        recognized_events_total += 1
        sid = _session_id(row)
        st = _ensure_session(sid)
        view = _norm_token(row.get("source_view") or row.get("view_mode") or "unknown") or "unknown"
        vrow = _ensure_view(view)

        if event_name == _EVENT_SHOWN:
            shown_events += 1
            st["shown"] = True
            vrow["nudge_shown_events"] += 1
            continue

        if event_name == _EVENT_CLICKED:
            clicked_events += 1
            st["clicked"] = True
            vrow["nudge_clicked_events"] += 1
            continue

    shown_sessions = sum(1 for st in sessions.values() if bool(st.get("shown")))
    clicked_sessions = sum(1 for st in sessions.values() if bool(st.get("clicked")))

    clickthrough_session_rate = _ratio(clicked_sessions, shown_sessions)
    clickthrough_event_rate = _ratio(clicked_events, shown_events)

    by_view_rows = []
    for view in sorted(by_view.keys()):
        row = by_view[view]
        shown_n = int(row.get("nudge_shown_events") or 0)
        clicked_n = int(row.get("nudge_clicked_events") or 0)
        by_view_rows.append(
            {
                "source_view": view,
                "nudge_shown_events": shown_n,
                "nudge_clicked_events": clicked_n,
                "nudge_clickthrough_event_rate": round(_clamp01(float(clicked_n) / float(shown_n)), 6) if shown_n > 0 else None,
            }
        )

    return {
        "events_total": events_total,
        "recognized_events_total": recognized_events_total,
        "ignored_events_total": ignored_events_total,
        "parse_errors": parse_errors,
        "sessions_total": len(sessions),
        "nudge_shown_events_total": shown_events,
        "nudge_clicked_events_total": clicked_events,
        "nudge_shown_sessions_total": shown_sessions,
        "nudge_clicked_sessions_total": clicked_sessions,
        "nudge_clickthrough_session_rate": round(_clamp01(clickthrough_session_rate), 6)
        if clickthrough_session_rate is not None
        else None,
        "nudge_clickthrough_event_rate": round(_clamp01(clickthrough_event_rate), 6) if clickthrough_event_rate is not None else None,
        "by_source_view": by_view_rows,
    }


def build_report(
    *,
    events_path: Path,
    min_nudge_shown_events: int,
    min_nudge_shown_sessions: int,
    min_nudge_clickthrough_rate: float,
) -> dict[str, Any]:
    telemetry = _read_events(events_path)

    shown_events_total = int(telemetry.get("nudge_shown_events_total") or 0)
    shown_sessions_total = int(telemetry.get("nudge_shown_sessions_total") or 0)
    ctr = _safe_float(telemetry.get("nudge_clickthrough_session_rate"))

    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if int(telemetry.get("recognized_events_total") or 0) <= 0:
        degraded_reasons.append("telemetry_missing")
    if shown_events_total < int(min_nudge_shown_events):
        degraded_reasons.append("nudge_shown_events_below_minimum")
    if shown_sessions_total < int(min_nudge_shown_sessions):
        degraded_reasons.append("nudge_shown_sessions_below_minimum")

    clickthrough_ok: bool | None = None
    if ctr is not None and shown_sessions_total >= int(min_nudge_shown_sessions):
        clickthrough_ok = float(ctr) >= float(min_nudge_clickthrough_rate)
        if not clickthrough_ok:
            failure_reasons.append("nudge_clickthrough_below_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif degraded_reasons:
        status = "degraded"

    checks = {
        "telemetry_available": bool(int(telemetry.get("recognized_events_total") or 0) > 0),
        "nudge_shown_events_meet_minimum": bool(shown_events_total >= int(min_nudge_shown_events)),
        "nudge_shown_sessions_meet_minimum": bool(shown_sessions_total >= int(min_nudge_shown_sessions)),
        "nudge_clickthrough_meets_minimum": clickthrough_ok,
        "contract_complete": bool(
            status == "ok"
            and shown_events_total >= int(min_nudge_shown_events)
            and shown_sessions_total >= int(min_nudge_shown_sessions)
            and ctr is not None
        ),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "events_jsonl": str(events_path),
        },
        "telemetry": {
            k: telemetry.get(k)
            for k in (
                "events_total",
                "recognized_events_total",
                "ignored_events_total",
                "parse_errors",
                "sessions_total",
            )
        },
        "metrics": {
            k: telemetry.get(k)
            for k in (
                "nudge_shown_events_total",
                "nudge_clicked_events_total",
                "nudge_shown_sessions_total",
                "nudge_clicked_sessions_total",
                "nudge_clickthrough_session_rate",
                "nudge_clickthrough_event_rate",
            )
        },
        "thresholds": {
            "min_nudge_shown_events": int(min_nudge_shown_events),
            "min_nudge_shown_sessions": int(min_nudge_shown_sessions),
            "min_nudge_clickthrough_rate": round(_clamp01(float(min_nudge_clickthrough_rate)), 6),
        },
        "checks": checks,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "by_source_view": telemetry.get("by_source_view") or [],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    events_path = Path(str(args.events_jsonl).strip())
    if not events_path.exists():
        print(json.dumps({"error": f"events-jsonl not found: {events_path}"}, ensure_ascii=False))
        return 2

    try:
        report = build_report(
            events_path=events_path,
            min_nudge_shown_events=int(args.min_nudge_shown_events),
            min_nudge_shown_sessions=int(args.min_nudge_shown_sessions),
            min_nudge_clickthrough_rate=float(args.min_nudge_clickthrough_rate),
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
