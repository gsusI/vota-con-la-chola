#!/usr/bin/env python3
"""Append-only heartbeat lane for sanction procedural packet-fix queue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_FIX_QUEUE_JSON = Path(
    "docs/etl/sprints/AI-OPS-193/evidence/"
    "sanction_procedural_official_review_packet_fix_ready_cycle_fix_queue_latest.json"
)
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat.jsonl")


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


def _normalize_fix_payload(root_payload: dict[str, Any]) -> dict[str, Any]:
    root = _safe_obj(root_payload)
    nested = root.get("fix_queue")
    if isinstance(nested, dict):
        return _safe_obj(nested)
    return root


def _status_digest(by_status: dict[str, int]) -> str:
    parts: list[str] = []
    for status in sorted(by_status):
        parts.append(f"{status}:{int(by_status[status])}")
    return ",".join(parts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for sanction procedural packet-fix queue")
    p.add_argument(
        "--fix-queue-json",
        default=str(DEFAULT_FIX_QUEUE_JSON),
        help=f"Input packet-fix queue JSON (default: {DEFAULT_FIX_QUEUE_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict checks fail")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def build_heartbeat(
    fix_payload: dict[str, Any],
    *,
    fix_queue_path: str,
) -> dict[str, Any]:
    payload = _normalize_fix_payload(fix_payload)
    totals = _safe_obj(payload.get("totals"))
    checks = _safe_obj(payload.get("checks"))
    by_status_raw = totals.get("queue_rows_by_packet_status")

    by_status: dict[str, int] = {}
    if isinstance(by_status_raw, dict):
        for key, raw_value in by_status_raw.items():
            status_key = _safe_text(key)
            if not status_key:
                continue
            by_status[status_key] = max(0, _to_int(raw_value, 0))

    status = _normalize_status(payload.get("status"))
    run_at = _safe_text(payload.get("generated_at")) or now_utc_iso()
    queue_rows_total = max(0, _to_int(totals.get("queue_rows_total"), 0))
    packets_expected_total = max(0, _to_int(totals.get("packets_expected_total"), 0))
    packets_ready_total = max(0, _to_int(totals.get("packets_ready_total"), 0))
    packets_not_ready_total = max(0, _to_int(totals.get("packets_not_ready_total"), 0))
    fix_queue_empty = bool(checks.get("fix_queue_empty"))
    progress_report_not_failed = bool(checks.get("progress_report_not_failed"))

    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.append("fix_queue_status_failed")
    if not progress_report_not_failed:
        strict_fail_reasons.append("progress_report_failed")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            str(queue_rows_total),
            str(packets_expected_total),
            str(packets_ready_total),
            str(packets_not_ready_total),
            _status_digest(by_status),
            "1" if fix_queue_empty else "0",
            "1" if progress_report_not_failed else "0",
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "fix_queue_path": _safe_text(fix_queue_path),
        "fix_queue_generated_at": _safe_text(payload.get("generated_at")),
        "status": status,
        "queue_rows_total": queue_rows_total,
        "packets_expected_total": packets_expected_total,
        "packets_ready_total": packets_ready_total,
        "packets_not_ready_total": packets_not_ready_total,
        "queue_rows_by_packet_status": by_status,
        "fix_queue_empty": fix_queue_empty,
        "progress_report_not_failed": progress_report_not_failed,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }


def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")

    status = _normalize_status(heartbeat.get("status"))
    if status == "failed" and _safe_text(heartbeat.get("status")).lower() not in {"failed"}:
        reasons.append("invalid_status")

    queue_rows_total = _to_int(heartbeat.get("queue_rows_total"), -1)
    packets_expected_total = _to_int(heartbeat.get("packets_expected_total"), -1)
    packets_ready_total = _to_int(heartbeat.get("packets_ready_total"), -1)
    packets_not_ready_total = _to_int(heartbeat.get("packets_not_ready_total"), -1)
    if queue_rows_total < 0:
        reasons.append("invalid_queue_rows_total")
    if packets_expected_total < 0:
        reasons.append("invalid_packets_expected_total")
    if packets_ready_total < 0:
        reasons.append("invalid_packets_ready_total")
    if packets_not_ready_total < 0:
        reasons.append("invalid_packets_not_ready_total")
    if packets_expected_total >= 0 and packets_ready_total >= 0 and packets_not_ready_total >= 0:
        if packets_ready_total + packets_not_ready_total != packets_expected_total:
            reasons.append("packet_totals_mismatch")

    by_status = heartbeat.get("queue_rows_by_packet_status")
    if not isinstance(by_status, dict):
        reasons.append("invalid_queue_rows_by_packet_status")
    else:
        for key, raw_value in by_status.items():
            if not _safe_text(key):
                reasons.append("empty_packet_status_key")
                continue
            if _to_int(raw_value, -1) < 0:
                reasons.append("invalid_packet_status_count")

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


def append_history_line(history_path: Path, heartbeat: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(heartbeat, ensure_ascii=False) + "\n")


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _safe_text(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fix_queue_path = Path(args.fix_queue_json)
    heartbeat_path = Path(args.heartbeat_jsonl)

    if not fix_queue_path.exists():
        payload = {
            "generated_at": now_utc_iso(),
            "status": "failed",
            "error": f"fix_queue_json_not_found: {fix_queue_path}",
        }
        _write_json(args.out, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    fix_payload = json.loads(fix_queue_path.read_text(encoding="utf-8"))
    heartbeat = build_heartbeat(fix_payload, fix_queue_path=str(fix_queue_path))
    validation_errors = validate_heartbeat(heartbeat)

    history_rows = read_history_entries(heartbeat_path)
    malformed_history_rows = sum(1 for row in history_rows if bool(row.get("malformed_line")))
    history_rows_before = len(history_rows)
    already_present = history_has_heartbeat(history_rows, _safe_text(heartbeat.get("heartbeat_id")))
    appended = False
    if not already_present:
        append_history_line(heartbeat_path, heartbeat)
        appended = True
    history_rows_after = history_rows_before + (1 if appended else 0)

    strict_fail_reasons = _dedupe_ordered(validation_errors + _safe_list_str(heartbeat.get("strict_fail_reasons")))
    status = _normalize_status(heartbeat.get("status"))
    if validation_errors:
        status = "failed"

    payload = {
        "generated_at": now_utc_iso(),
        "status": status,
        "strict": bool(args.strict),
        "fix_queue_json": str(fix_queue_path),
        "heartbeat_jsonl": str(heartbeat_path),
        "heartbeat": heartbeat,
        "validation_errors": validation_errors,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
        "history_rows_before": history_rows_before,
        "history_rows_after": history_rows_after,
        "malformed_history_rows": malformed_history_rows,
        "already_present": already_present,
        "appended": appended,
        "checks": {
            "heartbeat_valid": len(validation_errors) == 0,
            "history_append_succeeded": bool(already_present or appended),
        },
    }
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if bool(args.strict) and strict_fail_reasons:
        return 4
    if status == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
