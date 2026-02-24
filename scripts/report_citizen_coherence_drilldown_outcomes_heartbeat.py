#!/usr/bin/env python3
"""Append-only heartbeat lane for citizen coherence drilldown outcomes digest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DIGEST_JSON = Path("docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_coherence_drilldown_outcomes_heartbeat.jsonl")



def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()



def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()



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



def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)



def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None



def _fmt_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"



def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"



def _dedupe_ordered(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _safe_text(value)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for citizen coherence drilldown outcomes digest")
    p.add_argument(
        "--digest-json",
        default=str(DEFAULT_DIGEST_JSON),
        help=f"Input coherence drilldown outcomes digest JSON (default: {DEFAULT_DIGEST_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when heartbeat is invalid or status=failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)



def build_heartbeat(
    digest_payload: dict[str, Any],
    *,
    digest_path: str,
) -> dict[str, Any]:
    digest = _safe_obj(digest_payload)
    if "status" not in digest and isinstance(digest.get("digest"), dict):
        digest = _safe_obj(digest.get("digest"))

    metrics = _safe_obj(digest.get("metrics"))
    thresholds = _safe_obj(digest.get("thresholds"))
    checks = _safe_obj(digest.get("checks"))

    status = _normalize_status(digest.get("status"))
    run_at = _safe_text(digest.get("generated_at")) or now_utc_iso()
    digest_generated_at = _safe_text(digest.get("generated_at"))

    drilldown_click_events_total = _to_int(metrics.get("drilldown_click_events_total"), 0)
    replay_attempt_events_total = _to_int(metrics.get("replay_attempt_events_total"), 0)
    replay_success_events_total = _to_int(metrics.get("replay_success_events_total"), 0)
    replay_failure_events_total = _to_int(metrics.get("replay_failure_events_total"), 0)
    contract_complete_click_events_total = _to_int(metrics.get("contract_complete_click_events_total"), 0)

    replay_success_rate = _safe_float(metrics.get("replay_success_rate"))
    replay_failure_rate = _safe_float(metrics.get("replay_failure_rate"))
    contract_complete_click_rate = _safe_float(metrics.get("contract_complete_click_rate"))

    min_drilldown_click_events = _to_int(thresholds.get("min_drilldown_click_events"), 0)
    min_replay_attempt_events = _to_int(thresholds.get("min_replay_attempt_events"), 0)
    min_replay_success_rate = _safe_float(thresholds.get("min_replay_success_rate"))
    min_contract_complete_click_rate = _safe_float(thresholds.get("min_contract_complete_click_rate"))
    max_replay_failure_rate = _safe_float(thresholds.get("max_replay_failure_rate"))

    replay_success_ok_raw = checks.get("replay_success_rate_meets_minimum")
    contract_click_rate_ok_raw = checks.get("contract_complete_click_rate_meets_minimum")
    replay_failure_ok_raw = checks.get("replay_failure_rate_within_threshold")

    replay_success_ok = bool(replay_success_ok_raw) if isinstance(replay_success_ok_raw, bool) else None
    contract_click_rate_ok = bool(contract_click_rate_ok_raw) if isinstance(contract_click_rate_ok_raw, bool) else None
    replay_failure_ok = bool(replay_failure_ok_raw) if isinstance(replay_failure_ok_raw, bool) else None

    telemetry_available = bool(checks.get("telemetry_available"))
    contract_complete = bool(checks.get("contract_complete"))

    degraded_reasons = _safe_list_str(digest.get("degraded_reasons"))
    failure_reasons = _safe_list_str(digest.get("failure_reasons"))

    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.extend(failure_reasons)
        if not failure_reasons:
            strict_fail_reasons.append("coherence_drilldown_outcomes_failed_without_reason")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            digest_generated_at,
            str(drilldown_click_events_total),
            str(replay_attempt_events_total),
            str(replay_success_events_total),
            str(replay_failure_events_total),
            str(contract_complete_click_events_total),
            _fmt_float(replay_success_rate),
            _fmt_float(replay_failure_rate),
            _fmt_float(contract_complete_click_rate),
            _fmt_float(min_replay_success_rate),
            _fmt_float(min_contract_complete_click_rate),
            _fmt_float(max_replay_failure_rate),
            "1" if contract_complete else "0",
            ",".join(failure_reasons),
            ",".join(degraded_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "digest_path": _safe_text(digest_path),
        "digest_generated_at": digest_generated_at,
        "status": status,
        "drilldown_click_events_total": drilldown_click_events_total,
        "replay_attempt_events_total": replay_attempt_events_total,
        "replay_success_events_total": replay_success_events_total,
        "replay_failure_events_total": replay_failure_events_total,
        "contract_complete_click_events_total": contract_complete_click_events_total,
        "replay_success_rate": round(float(replay_success_rate), 6) if replay_success_rate is not None else None,
        "replay_failure_rate": round(float(replay_failure_rate), 6) if replay_failure_rate is not None else None,
        "contract_complete_click_rate": round(float(contract_complete_click_rate), 6)
        if contract_complete_click_rate is not None
        else None,
        "min_drilldown_click_events": min_drilldown_click_events,
        "min_replay_attempt_events": min_replay_attempt_events,
        "min_replay_success_rate": round(float(min_replay_success_rate), 6) if min_replay_success_rate is not None else None,
        "min_contract_complete_click_rate": round(float(min_contract_complete_click_rate), 6)
        if min_contract_complete_click_rate is not None
        else None,
        "max_replay_failure_rate": round(float(max_replay_failure_rate), 6) if max_replay_failure_rate is not None else None,
        "replay_success_rate_meets_minimum": replay_success_ok,
        "contract_complete_click_rate_meets_minimum": contract_click_rate_ok,
        "replay_failure_rate_within_threshold": replay_failure_ok,
        "telemetry_available": telemetry_available,
        "contract_complete": contract_complete,
        "degraded_reasons": degraded_reasons,
        "failure_reasons": failure_reasons,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }



def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")

    raw_status = _safe_text(heartbeat.get("status")).lower()
    if raw_status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    for key in (
        "drilldown_click_events_total",
        "replay_attempt_events_total",
        "replay_success_events_total",
        "replay_failure_events_total",
        "contract_complete_click_events_total",
        "min_drilldown_click_events",
        "min_replay_attempt_events",
    ):
        value = _to_int(heartbeat.get(key), -1)
        if value < 0:
            reasons.append(f"invalid_{key}")

    replay_attempt_events_total = _to_int(heartbeat.get("replay_attempt_events_total"), -1)
    replay_success_events_total = _to_int(heartbeat.get("replay_success_events_total"), -1)
    replay_failure_events_total = _to_int(heartbeat.get("replay_failure_events_total"), -1)
    if replay_success_events_total + replay_failure_events_total != replay_attempt_events_total:
        reasons.append("replay_attempt_totals_mismatch")

    drilldown_click_events_total = _to_int(heartbeat.get("drilldown_click_events_total"), -1)
    contract_complete_click_events_total = _to_int(heartbeat.get("contract_complete_click_events_total"), -1)
    if contract_complete_click_events_total > drilldown_click_events_total >= 0:
        reasons.append("contract_complete_click_events_exceeds_drilldown_click_events")

    for key in (
        "replay_success_rate",
        "replay_failure_rate",
        "contract_complete_click_rate",
        "min_replay_success_rate",
        "min_contract_complete_click_rate",
        "max_replay_failure_rate",
    ):
        value = _safe_float(heartbeat.get(key))
        if value is not None and not (0.0 <= float(value) <= 1.0):
            reasons.append(f"invalid_{key}")

    if bool(heartbeat.get("contract_complete")) and raw_status != "ok":
        reasons.append("contract_complete_status_mismatch")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    return _dedupe_ordered(reasons)



def read_history_entries(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    raw = history_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows



def history_has_heartbeat(rows: list[dict[str, Any]], heartbeat_id: str) -> bool:
    needle = _safe_text(heartbeat_id)
    if not needle:
        return False
    for row in rows:
        if bool(row.get("malformed_line")):
            continue
        entry = _safe_obj(row.get("entry"))
        if _safe_text(entry.get("heartbeat_id")) == needle:
            return True
    return False



def append_heartbeat(history_path: Path, heartbeat: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(heartbeat, ensure_ascii=False) + "\n")



def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    digest_path = Path(str(args.digest_json))
    if not digest_path.exists():
        print(json.dumps({"error": f"digest json not found: {digest_path}"}, ensure_ascii=False))
        return 2

    try:
        digest_payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid digest json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(digest_payload, dict):
        print(json.dumps({"error": "invalid digest json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(digest_path),
        "heartbeat_path": str(heartbeat_path),
        "history_size_before": 0,
        "history_size_after": 0,
        "history_malformed_lines_before": 0,
        "appended": False,
        "duplicate_detected": False,
        "validation_errors": [],
        "strict_fail_reasons": [],
        "heartbeat": {},
        "status": "failed",
    }

    try:
        heartbeat = build_heartbeat(digest_payload, digest_path=str(digest_path))
        report["heartbeat"] = heartbeat
        report["validation_errors"] = validate_heartbeat(heartbeat)

        history_before = read_history_entries(heartbeat_path)
        report["history_size_before"] = len(history_before)
        report["history_malformed_lines_before"] = sum(1 for row in history_before if bool(row.get("malformed_line")))

        if not report["validation_errors"]:
            report["duplicate_detected"] = history_has_heartbeat(history_before, _safe_text(heartbeat.get("heartbeat_id")))
            if not report["duplicate_detected"]:
                append_heartbeat(heartbeat_path, heartbeat)
                report["appended"] = True

        report["history_size_after"] = int(report["history_size_before"]) + (1 if report["appended"] else 0)
    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["strict_fail_reasons"] = [f"runtime_error:{type(exc).__name__}"]
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        print(payload)
        out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        return 3

    strict_fail_reasons: list[str] = []
    for reason in _safe_list_str(report.get("validation_errors")):
        strict_fail_reasons.append(f"validation:{reason}")

    heartbeat_status = _normalize_status(_safe_obj(report.get("heartbeat")).get("status"))
    if heartbeat_status == "failed":
        strict_fail_reasons.append("heartbeat_status_failed")
        strict_fail_reasons.extend(_safe_list_str(_safe_obj(report.get("heartbeat")).get("strict_fail_reasons")))
    report["strict_fail_reasons"] = _dedupe_ordered(strict_fail_reasons)

    if report["validation_errors"]:
        report["status"] = "failed"
    elif heartbeat_status == "failed":
        report["status"] = "failed"
    elif heartbeat_status == "degraded":
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

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
