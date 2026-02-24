#!/usr/bin/env python3
"""Machine-readable concern-pack outcome telemetry digest for /citizen."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_JSONL = Path("tests/fixtures/citizen_concern_pack_outcome_events_sample.jsonl")
DEFAULT_PACK_QUALITY_JSON = Path("tests/fixtures/citizen_concern_pack_quality_sample.json")
DEFAULT_MIN_PACK_SELECT_EVENTS = 20
DEFAULT_MIN_WEAK_PACK_SELECT_SESSIONS = 5
DEFAULT_MIN_WEAK_PACK_FOLLOWTHROUGH_RATE = 0.30
DEFAULT_MAX_UNKNOWN_PACK_SELECT_SHARE = 0.20

_EVENT_PACK_SELECTED = "pack_selected"
_EVENT_TOPIC_OPEN_WITH_PACK = "topic_open_with_pack"
_EVENT_NAMES = {_EVENT_PACK_SELECTED, _EVENT_TOPIC_OPEN_WITH_PACK, "pack_cleared"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen concern-pack outcomes report")
    ap.add_argument("--events-jsonl", default=str(DEFAULT_EVENTS_JSONL))
    ap.add_argument("--concern-pack-quality-json", default=str(DEFAULT_PACK_QUALITY_JSON))
    ap.add_argument("--min-pack-select-events", type=int, default=DEFAULT_MIN_PACK_SELECT_EVENTS)
    ap.add_argument("--min-weak-pack-select-sessions", type=int, default=DEFAULT_MIN_WEAK_PACK_SELECT_SESSIONS)
    ap.add_argument("--min-weak-pack-followthrough-rate", type=float, default=DEFAULT_MIN_WEAK_PACK_FOLLOWTHROUGH_RATE)
    ap.add_argument("--max-unknown-pack-select-share", type=float, default=DEFAULT_MAX_UNKNOWN_PACK_SELECT_SHARE)
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


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_token(v: Any) -> str:
    return str(v or "").strip().lower().replace("-", "_").replace(" ", "_")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    return obj


def _norm_pack_id(v: Any) -> str:
    return _norm_token(v).strip("_")


def _load_weak_pack_map(path: Path | None) -> dict[str, bool]:
    if path is None or not path.exists():
        return {}
    obj = _load_json(path)
    rows = obj.get("packs")
    out: dict[str, bool] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            pack_id = _norm_pack_id(row.get("pack_id"))
            if not pack_id:
                continue
            weak_raw = row.get("weak")
            if isinstance(weak_raw, bool):
                out[pack_id] = bool(weak_raw)
    return out


def _resolve_pack_weak(row: dict[str, Any], weak_pack_map: dict[str, bool], pack_id: str) -> bool | None:
    raw = row.get("pack_weak")
    if isinstance(raw, bool):
        return bool(raw)
    if pack_id and pack_id in weak_pack_map:
        return bool(weak_pack_map[pack_id])
    return None


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


def _read_events(events_path: Path, weak_pack_map: dict[str, bool]) -> dict[str, Any]:
    parse_errors = 0
    events_total = 0
    recognized_events_total = 0
    ignored_events_total = 0

    pack_selected_events = 0
    weak_pack_selected_events = 0
    unknown_pack_selected_events = 0
    weak_pack_followthrough_events = 0
    topic_open_with_pack_events = 0

    by_pack: dict[str, dict[str, int]] = {}
    sessions: dict[str, dict[str, bool]] = {}

    def _ensure_pack(pack_id: str) -> dict[str, int]:
        row = by_pack.get(pack_id)
        if row is None:
            row = {
                "pack_selected_events": 0,
                "topic_open_with_pack_events": 0,
                "weak_pack_selected_events": 0,
                "weak_pack_followthrough_events": 0,
            }
            by_pack[pack_id] = row
        return row

    def _ensure_session(sid: str) -> dict[str, bool]:
        st = sessions.get(sid)
        if st is None:
            st = {
                "pack_selected": False,
                "weak_selected": False,
                "weak_followthrough": False,
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

        pack_id = _norm_pack_id(row.get("pack_id"))
        pack_weak = _resolve_pack_weak(row, weak_pack_map, pack_id)

        if event_name == _EVENT_PACK_SELECTED:
            pack_selected_events += 1
            st["pack_selected"] = True
            if pack_weak is True:
                weak_pack_selected_events += 1
                st["weak_selected"] = True
            elif pack_weak is None:
                unknown_pack_selected_events += 1

            if pack_id:
                prow = _ensure_pack(pack_id)
                prow["pack_selected_events"] += 1
                if pack_weak is True:
                    prow["weak_pack_selected_events"] += 1
            continue

        if event_name == _EVENT_TOPIC_OPEN_WITH_PACK:
            topic_open_with_pack_events += 1
            if pack_weak is True:
                weak_pack_followthrough_events += 1
                st["weak_followthrough"] = True
            if pack_id:
                prow = _ensure_pack(pack_id)
                prow["topic_open_with_pack_events"] += 1
                if pack_weak is True:
                    prow["weak_pack_followthrough_events"] += 1
            continue

    pack_selected_sessions = sum(1 for st in sessions.values() if bool(st.get("pack_selected")))
    weak_pack_selected_sessions = sum(1 for st in sessions.values() if bool(st.get("weak_selected")))
    weak_pack_followthrough_sessions = sum(1 for st in sessions.values() if bool(st.get("weak_followthrough")))

    weak_followthrough_rate = _ratio(weak_pack_followthrough_sessions, weak_pack_selected_sessions)
    unknown_pack_select_share = _ratio(unknown_pack_selected_events, pack_selected_events)

    by_pack_rows = []
    for pack_id in sorted(by_pack.keys()):
        prow = by_pack[pack_id]
        by_pack_rows.append(
            {
                "pack_id": pack_id,
                **prow,
            }
        )

    return {
        "events_total": events_total,
        "recognized_events_total": recognized_events_total,
        "ignored_events_total": ignored_events_total,
        "parse_errors": parse_errors,
        "pack_selected_events_total": pack_selected_events,
        "topic_open_with_pack_events_total": topic_open_with_pack_events,
        "weak_pack_selected_events_total": weak_pack_selected_events,
        "weak_pack_followthrough_events_total": weak_pack_followthrough_events,
        "unknown_pack_selected_events_total": unknown_pack_selected_events,
        "sessions_total": len(sessions),
        "pack_selected_sessions_total": pack_selected_sessions,
        "weak_pack_selected_sessions_total": weak_pack_selected_sessions,
        "weak_pack_followthrough_sessions_total": weak_pack_followthrough_sessions,
        "weak_pack_followthrough_rate": round(_clamp01(weak_followthrough_rate), 6) if weak_followthrough_rate is not None else None,
        "unknown_pack_select_share": round(_clamp01(unknown_pack_select_share), 6) if unknown_pack_select_share is not None else None,
        "selected_pack_ids_total": len(by_pack_rows),
        "by_pack": by_pack_rows,
    }


def build_report(
    *,
    events_path: Path,
    concern_pack_quality_path: Path | None,
    min_pack_select_events: int,
    min_weak_pack_select_sessions: int,
    min_weak_pack_followthrough_rate: float,
    max_unknown_pack_select_share: float,
) -> dict[str, Any]:
    weak_pack_map = _load_weak_pack_map(concern_pack_quality_path)
    telemetry = _read_events(events_path, weak_pack_map)

    pack_selected_events_total = int(telemetry.get("pack_selected_events_total") or 0)
    weak_pack_selected_sessions_total = int(telemetry.get("weak_pack_selected_sessions_total") or 0)
    weak_pack_followthrough_rate = _safe_float(telemetry.get("weak_pack_followthrough_rate"))
    unknown_pack_select_share = _safe_float(telemetry.get("unknown_pack_select_share"))

    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if int(telemetry.get("recognized_events_total") or 0) <= 0:
        degraded_reasons.append("telemetry_missing")
    if pack_selected_events_total < int(min_pack_select_events):
        degraded_reasons.append("pack_select_events_below_minimum")
    if weak_pack_selected_sessions_total < int(min_weak_pack_select_sessions):
        degraded_reasons.append("weak_pack_select_sessions_below_minimum")

    unknown_share_ok: bool | None = None
    if unknown_pack_select_share is not None:
        unknown_share_ok = float(unknown_pack_select_share) <= float(max_unknown_pack_select_share)
        if not unknown_share_ok:
            failure_reasons.append("unknown_pack_select_share_above_threshold")

    weak_followthrough_ok: bool | None = None
    if weak_pack_followthrough_rate is not None and weak_pack_selected_sessions_total >= int(min_weak_pack_select_sessions):
        weak_followthrough_ok = float(weak_pack_followthrough_rate) >= float(min_weak_pack_followthrough_rate)
        if not weak_followthrough_ok:
            failure_reasons.append("weak_pack_followthrough_below_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif degraded_reasons:
        status = "degraded"

    checks = {
        "telemetry_available": bool(int(telemetry.get("recognized_events_total") or 0) > 0),
        "pack_select_events_meet_minimum": bool(pack_selected_events_total >= int(min_pack_select_events)),
        "weak_pack_select_sessions_meet_minimum": bool(weak_pack_selected_sessions_total >= int(min_weak_pack_select_sessions)),
        "weak_pack_followthrough_rate_meets_minimum": weak_followthrough_ok,
        "unknown_pack_select_share_within_threshold": unknown_share_ok,
        "contract_complete": bool(
            status == "ok"
            and weak_pack_selected_sessions_total >= int(min_weak_pack_select_sessions)
            and pack_selected_events_total >= int(min_pack_select_events)
            and weak_pack_followthrough_rate is not None
            and unknown_pack_select_share is not None
        ),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "events_jsonl": str(events_path),
            "concern_pack_quality_json": str(concern_pack_quality_path) if concern_pack_quality_path else None,
        },
        "telemetry": {
            k: telemetry.get(k)
            for k in (
                "events_total",
                "recognized_events_total",
                "ignored_events_total",
                "parse_errors",
                "sessions_total",
                "selected_pack_ids_total",
            )
        },
        "metrics": {
            k: telemetry.get(k)
            for k in (
                "pack_selected_events_total",
                "topic_open_with_pack_events_total",
                "weak_pack_selected_events_total",
                "weak_pack_followthrough_events_total",
                "unknown_pack_selected_events_total",
                "pack_selected_sessions_total",
                "weak_pack_selected_sessions_total",
                "weak_pack_followthrough_sessions_total",
                "weak_pack_followthrough_rate",
                "unknown_pack_select_share",
            )
        },
        "thresholds": {
            "min_pack_select_events": int(min_pack_select_events),
            "min_weak_pack_select_sessions": int(min_weak_pack_select_sessions),
            "min_weak_pack_followthrough_rate": round(_clamp01(float(min_weak_pack_followthrough_rate)), 6),
            "max_unknown_pack_select_share": round(_clamp01(float(max_unknown_pack_select_share)), 6),
        },
        "checks": checks,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "by_pack": telemetry.get("by_pack") or [],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    events_path = Path(str(args.events_jsonl).strip())
    if not events_path.exists():
        print(json.dumps({"error": f"events-jsonl not found: {events_path}"}, ensure_ascii=False))
        return 2

    quality_raw = str(args.concern_pack_quality_json).strip()
    concern_pack_quality_path = Path(quality_raw) if quality_raw else None
    if concern_pack_quality_path is not None and not concern_pack_quality_path.exists():
        print(json.dumps({"error": f"concern-pack-quality-json not found: {concern_pack_quality_path}"}, ensure_ascii=False))
        return 2

    try:
        report = build_report(
            events_path=events_path,
            concern_pack_quality_path=concern_pack_quality_path,
            min_pack_select_events=int(args.min_pack_select_events),
            min_weak_pack_select_sessions=int(args.min_weak_pack_select_sessions),
            min_weak_pack_followthrough_rate=float(args.min_weak_pack_followthrough_rate),
            max_unknown_pack_select_share=float(args.max_unknown_pack_select_share),
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
