#!/usr/bin/env python3
"""Machine-readable coherence drilldown telemetry digest for /citizen -> explorer-temas."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_JSONL = Path("tests/fixtures/citizen_coherence_drilldown_events_sample.jsonl")
DEFAULT_MIN_DRILLDOWN_CLICK_EVENTS = 8
DEFAULT_MIN_REPLAY_ATTEMPT_EVENTS = 8
DEFAULT_MIN_REPLAY_SUCCESS_RATE = 0.85
DEFAULT_MIN_CONTRACT_COMPLETE_CLICK_RATE = 0.90
DEFAULT_MAX_REPLAY_FAILURE_RATE = 0.15

_EVENT_COHERENCE_DRILLDOWN_CLICKED = "coherence_drilldown_link_clicked"
_EVENT_COHERENCE_REPLAY_SUCCEEDED = "coherence_drilldown_url_replayed"
_EVENT_COHERENCE_REPLAY_FAILED = "coherence_drilldown_url_replay_failed"
_EVENT_NAMES = {
    _EVENT_COHERENCE_DRILLDOWN_CLICKED,
    _EVENT_COHERENCE_REPLAY_SUCCEEDED,
    _EVENT_COHERENCE_REPLAY_FAILED,
}



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen coherence drilldown outcomes report")
    ap.add_argument("--events-jsonl", default=str(DEFAULT_EVENTS_JSONL))
    ap.add_argument("--min-drilldown-click-events", type=int, default=DEFAULT_MIN_DRILLDOWN_CLICK_EVENTS)
    ap.add_argument("--min-replay-attempt-events", type=int, default=DEFAULT_MIN_REPLAY_ATTEMPT_EVENTS)
    ap.add_argument("--min-replay-success-rate", type=float, default=DEFAULT_MIN_REPLAY_SUCCESS_RATE)
    ap.add_argument(
        "--min-contract-complete-click-rate",
        type=float,
        default=DEFAULT_MIN_CONTRACT_COMPLETE_CLICK_RATE,
    )
    ap.add_argument("--max-replay-failure-rate", type=float, default=DEFAULT_MAX_REPLAY_FAILURE_RATE)
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



def _contract_complete_click(row: dict[str, Any]) -> bool:
    source = _norm_token(row.get("source"))
    view = _norm_token(row.get("view"))
    bucket = _norm_token(row.get("bucket"))

    party_id = str(row.get("party_id") or row.get("party") or row.get("partyId") or "").strip()
    topic_id = str(row.get("topic_id") or row.get("topic") or row.get("topicId") or "").strip()
    concern = str(row.get("concern") or row.get("concern_id") or row.get("concernId") or "").strip()

    return bool(
        source == "citizen_coherence"
        and view == "coherence"
        and bucket
        and party_id
        and topic_id
        and concern
    )



def _read_events(events_path: Path) -> dict[str, Any]:
    parse_errors = 0
    events_total = 0
    recognized_events_total = 0
    ignored_events_total = 0

    drilldown_click_events_total = 0
    replay_success_events_total = 0
    replay_failure_events_total = 0
    contract_complete_click_events_total = 0

    by_bucket: dict[str, int] = {}
    sessions: dict[str, dict[str, bool]] = {}

    def _ensure_session(sid: str) -> dict[str, bool]:
        st = sessions.get(sid)
        if st is None:
            st = {
                "click": False,
                "replay_success": False,
                "replay_failure": False,
            }
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

        if event_name == _EVENT_COHERENCE_DRILLDOWN_CLICKED:
            drilldown_click_events_total += 1
            st["click"] = True
            bucket = _norm_token(row.get("bucket"))
            if bucket:
                by_bucket[bucket] = int(by_bucket.get(bucket) or 0) + 1
            if _contract_complete_click(row):
                contract_complete_click_events_total += 1
            continue

        if event_name == _EVENT_COHERENCE_REPLAY_SUCCEEDED:
            replay_success_events_total += 1
            st["replay_success"] = True
            continue

        if event_name == _EVENT_COHERENCE_REPLAY_FAILED:
            replay_failure_events_total += 1
            st["replay_failure"] = True
            continue

    replay_attempt_events_total = replay_success_events_total + replay_failure_events_total
    replay_success_rate = _ratio(replay_success_events_total, replay_attempt_events_total)
    replay_failure_rate = _ratio(replay_failure_events_total, replay_attempt_events_total)
    contract_complete_click_rate = _ratio(contract_complete_click_events_total, drilldown_click_events_total)

    click_sessions_total = sum(1 for st in sessions.values() if bool(st.get("click")))
    replay_success_sessions_total = sum(1 for st in sessions.values() if bool(st.get("replay_success")))
    replay_failure_sessions_total = sum(1 for st in sessions.values() if bool(st.get("replay_failure")))

    by_bucket_rows = []
    for bucket in sorted(by_bucket.keys()):
        by_bucket_rows.append({"bucket": bucket, "click_events_total": int(by_bucket.get(bucket) or 0)})

    return {
        "events_total": events_total,
        "recognized_events_total": recognized_events_total,
        "ignored_events_total": ignored_events_total,
        "parse_errors": parse_errors,
        "sessions_total": len(sessions),
        "click_sessions_total": click_sessions_total,
        "replay_success_sessions_total": replay_success_sessions_total,
        "replay_failure_sessions_total": replay_failure_sessions_total,
        "drilldown_click_events_total": drilldown_click_events_total,
        "replay_attempt_events_total": replay_attempt_events_total,
        "replay_success_events_total": replay_success_events_total,
        "replay_failure_events_total": replay_failure_events_total,
        "contract_complete_click_events_total": contract_complete_click_events_total,
        "replay_success_rate": round(_clamp01(replay_success_rate), 6) if replay_success_rate is not None else None,
        "replay_failure_rate": round(_clamp01(replay_failure_rate), 6) if replay_failure_rate is not None else None,
        "contract_complete_click_rate": round(_clamp01(contract_complete_click_rate), 6)
        if contract_complete_click_rate is not None
        else None,
        "by_bucket": by_bucket_rows,
    }



def build_report(
    *,
    events_path: Path,
    min_drilldown_click_events: int,
    min_replay_attempt_events: int,
    min_replay_success_rate: float,
    min_contract_complete_click_rate: float,
    max_replay_failure_rate: float,
) -> dict[str, Any]:
    telemetry = _read_events(events_path)

    drilldown_click_events_total = int(telemetry.get("drilldown_click_events_total") or 0)
    replay_attempt_events_total = int(telemetry.get("replay_attempt_events_total") or 0)
    replay_success_rate = _safe_float(telemetry.get("replay_success_rate"))
    replay_failure_rate = _safe_float(telemetry.get("replay_failure_rate"))
    contract_complete_click_rate = _safe_float(telemetry.get("contract_complete_click_rate"))

    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if int(telemetry.get("recognized_events_total") or 0) <= 0:
        degraded_reasons.append("telemetry_missing")
    if drilldown_click_events_total < int(min_drilldown_click_events):
        degraded_reasons.append("drilldown_click_events_below_minimum")
    if replay_attempt_events_total < int(min_replay_attempt_events):
        degraded_reasons.append("replay_attempt_events_below_minimum")

    replay_success_ok: bool | None = None
    if replay_success_rate is not None:
        replay_success_ok = float(replay_success_rate) >= float(min_replay_success_rate)
        if not replay_success_ok:
            failure_reasons.append("replay_success_rate_below_threshold")

    contract_complete_click_ok: bool | None = None
    if contract_complete_click_rate is not None:
        contract_complete_click_ok = float(contract_complete_click_rate) >= float(min_contract_complete_click_rate)
        if not contract_complete_click_ok:
            failure_reasons.append("contract_complete_click_rate_below_threshold")

    replay_failure_ok: bool | None = None
    if replay_failure_rate is not None:
        replay_failure_ok = float(replay_failure_rate) <= float(max_replay_failure_rate)
        if not replay_failure_ok:
            failure_reasons.append("replay_failure_rate_above_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif degraded_reasons:
        status = "degraded"

    checks = {
        "telemetry_available": bool(int(telemetry.get("recognized_events_total") or 0) > 0),
        "drilldown_click_events_meet_minimum": bool(drilldown_click_events_total >= int(min_drilldown_click_events)),
        "replay_attempt_events_meet_minimum": bool(replay_attempt_events_total >= int(min_replay_attempt_events)),
        "replay_success_rate_meets_minimum": replay_success_ok,
        "contract_complete_click_rate_meets_minimum": contract_complete_click_ok,
        "replay_failure_rate_within_threshold": replay_failure_ok,
        "contract_complete": bool(
            status == "ok"
            and drilldown_click_events_total >= int(min_drilldown_click_events)
            and replay_attempt_events_total >= int(min_replay_attempt_events)
            and replay_success_rate is not None
            and contract_complete_click_rate is not None
            and replay_failure_rate is not None
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
                "click_sessions_total",
                "replay_success_sessions_total",
                "replay_failure_sessions_total",
            )
        },
        "metrics": {
            k: telemetry.get(k)
            for k in (
                "drilldown_click_events_total",
                "replay_attempt_events_total",
                "replay_success_events_total",
                "replay_failure_events_total",
                "contract_complete_click_events_total",
                "replay_success_rate",
                "replay_failure_rate",
                "contract_complete_click_rate",
            )
        },
        "thresholds": {
            "min_drilldown_click_events": int(min_drilldown_click_events),
            "min_replay_attempt_events": int(min_replay_attempt_events),
            "min_replay_success_rate": round(_clamp01(float(min_replay_success_rate)), 6),
            "min_contract_complete_click_rate": round(_clamp01(float(min_contract_complete_click_rate)), 6),
            "max_replay_failure_rate": round(_clamp01(float(max_replay_failure_rate)), 6),
        },
        "checks": checks,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "by_bucket": telemetry.get("by_bucket") or [],
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
            min_drilldown_click_events=int(args.min_drilldown_click_events),
            min_replay_attempt_events=int(args.min_replay_attempt_events),
            min_replay_success_rate=float(args.min_replay_success_rate),
            min_contract_complete_click_rate=float(args.min_contract_complete_click_rate),
            max_replay_failure_rate=float(args.max_replay_failure_rate),
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
