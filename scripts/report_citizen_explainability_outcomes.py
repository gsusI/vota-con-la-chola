#!/usr/bin/env python3
"""Machine-readable explainability outcomes telemetry digest for /citizen."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_JSONL = Path("tests/fixtures/citizen_explainability_outcome_events_sample.jsonl")
DEFAULT_MIN_GLOSSARY_INTERACTION_EVENTS = 8
DEFAULT_MIN_HELP_COPY_INTERACTION_EVENTS = 5
DEFAULT_MIN_ADOPTION_SESSIONS = 5
DEFAULT_MIN_ADOPTION_COMPLETENESS_RATE = 0.60

_EVENT_GLOSSARY_OPENED = "explainability_glossary_opened"
_EVENT_GLOSSARY_TERM_INTERACTED = "explainability_glossary_term_interacted"
_EVENT_HELP_COPY_INTERACTED = "explainability_help_copy_interacted"
_EVENT_NAMES = {
    _EVENT_GLOSSARY_OPENED,
    _EVENT_GLOSSARY_TERM_INTERACTED,
    _EVENT_HELP_COPY_INTERACTED,
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen explainability outcomes report")
    ap.add_argument("--events-jsonl", default=str(DEFAULT_EVENTS_JSONL))
    ap.add_argument("--min-glossary-interaction-events", type=int, default=DEFAULT_MIN_GLOSSARY_INTERACTION_EVENTS)
    ap.add_argument("--min-help-copy-interaction-events", type=int, default=DEFAULT_MIN_HELP_COPY_INTERACTION_EVENTS)
    ap.add_argument("--min-adoption-sessions", type=int, default=DEFAULT_MIN_ADOPTION_SESSIONS)
    ap.add_argument("--min-adoption-completeness-rate", type=float, default=DEFAULT_MIN_ADOPTION_COMPLETENESS_RATE)
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

    glossary_opened_events = 0
    glossary_term_events = 0
    help_copy_events = 0

    sessions: dict[str, dict[str, bool]] = {}
    by_term: dict[str, int] = {}

    def _ensure_session(sid: str) -> dict[str, bool]:
        st = sessions.get(sid)
        if st is None:
            st = {"glossary": False, "help_copy": False}
            sessions[sid] = st
        return st

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

        if event_name == _EVENT_GLOSSARY_OPENED:
            glossary_opened_events += 1
            st["glossary"] = True
            continue

        if event_name == _EVENT_GLOSSARY_TERM_INTERACTED:
            glossary_term_events += 1
            st["glossary"] = True
            term = _norm_token(row.get("term"))
            if term:
                by_term[term] = int(by_term.get(term) or 0) + 1
            continue

        if event_name == _EVENT_HELP_COPY_INTERACTED:
            help_copy_events += 1
            st["help_copy"] = True
            continue

    adoption_sessions = sum(1 for st in sessions.values() if bool(st.get("glossary") or st.get("help_copy")))
    complete_adoption_sessions = sum(1 for st in sessions.values() if bool(st.get("glossary") and st.get("help_copy")))

    adoption_completeness_rate = _ratio(complete_adoption_sessions, adoption_sessions)

    by_term_rows = []
    for term in sorted(by_term.keys()):
        by_term_rows.append({"term": term, "events_total": int(by_term.get(term) or 0)})

    return {
        "events_total": events_total,
        "recognized_events_total": recognized_events_total,
        "ignored_events_total": ignored_events_total,
        "parse_errors": parse_errors,
        "sessions_total": len(sessions),
        "glossary_opened_events_total": glossary_opened_events,
        "glossary_term_interaction_events_total": glossary_term_events,
        "glossary_interaction_events_total": glossary_opened_events + glossary_term_events,
        "help_copy_interaction_events_total": help_copy_events,
        "adoption_sessions_total": adoption_sessions,
        "complete_adoption_sessions_total": complete_adoption_sessions,
        "adoption_completeness_rate": round(_clamp01(adoption_completeness_rate), 6)
        if adoption_completeness_rate is not None
        else None,
        "interacted_terms_total": len(by_term_rows),
        "by_term": by_term_rows,
    }


def build_report(
    *,
    events_path: Path,
    min_glossary_interaction_events: int,
    min_help_copy_interaction_events: int,
    min_adoption_sessions: int,
    min_adoption_completeness_rate: float,
) -> dict[str, Any]:
    telemetry = _read_events(events_path)

    glossary_interaction_events_total = int(telemetry.get("glossary_interaction_events_total") or 0)
    help_copy_interaction_events_total = int(telemetry.get("help_copy_interaction_events_total") or 0)
    adoption_sessions_total = int(telemetry.get("adoption_sessions_total") or 0)
    adoption_completeness_rate = _safe_float(telemetry.get("adoption_completeness_rate"))

    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if int(telemetry.get("recognized_events_total") or 0) <= 0:
        degraded_reasons.append("telemetry_missing")
    if glossary_interaction_events_total < int(min_glossary_interaction_events):
        degraded_reasons.append("glossary_interactions_below_minimum")
    if help_copy_interaction_events_total < int(min_help_copy_interaction_events):
        degraded_reasons.append("help_copy_interactions_below_minimum")
    if adoption_sessions_total < int(min_adoption_sessions):
        degraded_reasons.append("adoption_sessions_below_minimum")

    adoption_completeness_ok: bool | None = None
    if adoption_completeness_rate is not None and adoption_sessions_total >= int(min_adoption_sessions):
        adoption_completeness_ok = float(adoption_completeness_rate) >= float(min_adoption_completeness_rate)
        if not adoption_completeness_ok:
            failure_reasons.append("adoption_completeness_below_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif degraded_reasons:
        status = "degraded"

    checks = {
        "telemetry_available": bool(int(telemetry.get("recognized_events_total") or 0) > 0),
        "glossary_interactions_meet_minimum": bool(
            glossary_interaction_events_total >= int(min_glossary_interaction_events)
        ),
        "help_copy_interactions_meet_minimum": bool(
            help_copy_interaction_events_total >= int(min_help_copy_interaction_events)
        ),
        "adoption_sessions_meet_minimum": bool(adoption_sessions_total >= int(min_adoption_sessions)),
        "adoption_completeness_meets_minimum": adoption_completeness_ok,
        "contract_complete": bool(
            status == "ok"
            and glossary_interaction_events_total >= int(min_glossary_interaction_events)
            and help_copy_interaction_events_total >= int(min_help_copy_interaction_events)
            and adoption_sessions_total >= int(min_adoption_sessions)
            and adoption_completeness_rate is not None
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
                "glossary_opened_events_total",
                "glossary_term_interaction_events_total",
                "glossary_interaction_events_total",
                "help_copy_interaction_events_total",
                "adoption_sessions_total",
                "complete_adoption_sessions_total",
                "adoption_completeness_rate",
                "interacted_terms_total",
            )
        },
        "thresholds": {
            "min_glossary_interaction_events": int(min_glossary_interaction_events),
            "min_help_copy_interaction_events": int(min_help_copy_interaction_events),
            "min_adoption_sessions": int(min_adoption_sessions),
            "min_adoption_completeness_rate": round(_clamp01(float(min_adoption_completeness_rate)), 6),
        },
        "checks": checks,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "by_term": telemetry.get("by_term") or [],
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
            min_glossary_interaction_events=int(args.min_glossary_interaction_events),
            min_help_copy_interaction_events=int(args.min_help_copy_interaction_events),
            min_adoption_sessions=int(args.min_adoption_sessions),
            min_adoption_completeness_rate=float(args.min_adoption_completeness_rate),
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
