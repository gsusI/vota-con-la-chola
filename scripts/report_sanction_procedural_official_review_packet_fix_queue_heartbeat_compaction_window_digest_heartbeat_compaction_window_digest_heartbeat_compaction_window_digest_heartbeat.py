#!/usr/bin/env python3
"""Append-only heartbeat lane for packet-fix compact-window digest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DIGEST_JSON = Path(
    "docs/etl/sprints/AI-OPS-203/evidence/"
    "sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json"
)
DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/"
    "sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl"
)


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
    return [_safe_text(v) for v in value if _safe_text(v)]


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _normalize_risk_level(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"green", "amber", "red"}:
        return token
    return "red"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for packet-fix compaction-window digest")
    p.add_argument(
        "--digest-json",
        default=str(DEFAULT_DIGEST_JSON),
        help=f"Input digest JSON path (default: {DEFAULT_DIGEST_JSON})",
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


def build_heartbeat(digest_payload: dict[str, Any], *, digest_path: str) -> dict[str, Any]:
    digest = _safe_obj(digest_payload)
    input_obj = _safe_obj(digest.get("input"))
    key_metrics = _safe_obj(digest.get("key_metrics"))

    run_at = _safe_text(digest.get("generated_at")) or now_utc_iso()
    digest_generated_at = _safe_text(digest.get("generated_at"))
    compaction_window_generated_at = _safe_text(input_obj.get("compaction_window_generated_at"))
    status = _normalize_status(digest.get("status"))
    risk_level = _normalize_risk_level(digest.get("risk_level"))

    window_raw_entries = _to_int(key_metrics.get("window_raw_entries"), 0)
    missing_in_compacted = _to_int(key_metrics.get("missing_in_compacted_in_window"), 0)
    heartbeat_id = "|".join(
        [
            compaction_window_generated_at,
            run_at,
            status,
            risk_level,
            str(missing_in_compacted),
            str(window_raw_entries),
        ]
    )

    strict_fail_reasons = _safe_list_str(digest.get("strict_fail_reasons"))
    risk_reasons = _safe_list_str(digest.get("risk_reasons"))

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "digest_path": _safe_text(digest_path),
        "digest_generated_at": digest_generated_at,
        "compaction_window_generated_at": compaction_window_generated_at,
        "status": status,
        "risk_level": risk_level,
        "window_raw_entries": window_raw_entries,
        "raw_window_incidents": _to_int(key_metrics.get("raw_window_incidents"), 0),
        "missing_in_compacted_in_window": missing_in_compacted,
        "incident_missing_in_compacted": _to_int(key_metrics.get("incident_missing_in_compacted"), 0),
        "raw_window_coverage_pct": _to_float(key_metrics.get("raw_window_coverage_pct"), 0.0),
        "incident_coverage_pct": _to_float(key_metrics.get("incident_coverage_pct"), 0.0),
        "strict_fail_count": len(strict_fail_reasons),
        "risk_reason_count": len(risk_reasons),
        "strict_fail_reasons": strict_fail_reasons,
        "risk_reasons": risk_reasons,
    }


def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")
    if not _safe_text(heartbeat.get("compaction_window_generated_at")):
        reasons.append("missing_compaction_window_generated_at")

    status = _normalize_status(heartbeat.get("status"))
    if status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    risk_level = _normalize_risk_level(heartbeat.get("risk_level"))
    if risk_level not in {"green", "amber", "red"}:
        reasons.append("invalid_risk_level")

    if _to_int(heartbeat.get("window_raw_entries"), -1) < 0:
        reasons.append("invalid_window_raw_entries")
    if _to_int(heartbeat.get("raw_window_incidents"), -1) < 0:
        reasons.append("invalid_raw_window_incidents")
    if _to_int(heartbeat.get("missing_in_compacted_in_window"), -1) < 0:
        reasons.append("invalid_missing_in_compacted_in_window")
    if _to_int(heartbeat.get("incident_missing_in_compacted"), -1) < 0:
        reasons.append("invalid_incident_missing_in_compacted")
    if _to_float(heartbeat.get("raw_window_coverage_pct"), -1.0) < 0:
        reasons.append("invalid_raw_window_coverage_pct")
    if _to_float(heartbeat.get("incident_coverage_pct"), -1.0) < 0:
        reasons.append("invalid_incident_coverage_pct")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    risk_reasons = _safe_list_str(heartbeat.get("risk_reasons"))
    risk_reason_count = _to_int(heartbeat.get("risk_reason_count"), -1)
    if risk_reason_count != len(risk_reasons):
        reasons.append("risk_reason_count_mismatch")

    return reasons


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
        "heartbeat": {},
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
        report["validation_errors"] = [f"runtime_error:{type(exc).__name__}:{exc}"]
        report["history_size_after"] = int(report["history_size_before"])

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    status = _normalize_status(_safe_obj(report.get("heartbeat")).get("status"))
    if bool(args.strict) and (len(list(report.get("validation_errors") or [])) > 0 or status == "failed"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
