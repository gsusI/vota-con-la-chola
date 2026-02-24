#!/usr/bin/env python3
"""Append-only heartbeat lane for liberty identity actionable upgrade review queue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SUMMARY_JSON = Path(
    "docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_latest.json"
)
DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.jsonl"
)


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Append heartbeat JSONL for liberty person identity official upgrade actionable queue"
    )
    p.add_argument(
        "--summary-json",
        default=str(DEFAULT_SUMMARY_JSON),
        help=f"Input summary JSON path (default: {DEFAULT_SUMMARY_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict_fail_reasons is not empty.")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def build_heartbeat(summary_payload: dict[str, Any], *, summary_path: str) -> dict[str, Any]:
    payload = _safe_obj(summary_payload)
    summary = _safe_obj(payload.get("summary"))

    rows_total = _to_int(summary.get("rows_total"), 0)
    actionable_rows_total = _to_int(summary.get("actionable_rows_total"), 0)
    likely_not_actionable_rows_total = _to_int(summary.get("likely_not_actionable_rows_total"), 0)
    manual_upgrade_rows_total = _to_int(summary.get("manual_upgrade_rows_total"), 0)
    official_evidence_gap_rows_total = _to_int(summary.get("official_evidence_gap_rows_total"), 0)
    official_source_record_gap_rows_total = _to_int(summary.get("official_source_record_gap_rows_total"), 0)
    rows_exported_total = _to_int(payload.get("rows_exported_total"), 0)
    source_record_lookup_rows_total = _to_int(payload.get("source_record_lookup_rows_total"), 0)
    missing_seed_mapping_total = _to_int(summary.get("missing_seed_mapping_total"), 0)
    source_record_pk_lookup_keys_total = _to_int(summary.get("source_record_pk_lookup_keys_total"), 0)
    source_record_pk_lookup_prefilled_total = _to_int(summary.get("source_record_pk_lookup_prefilled_total"), 0)
    source_record_pk_lookup_miss_total = _to_int(summary.get("source_record_pk_lookup_miss_total"), 0)
    only_actionable = bool(payload.get("only_actionable"))
    strict_empty_actionable = bool(payload.get("strict_empty_actionable"))
    actionable_queue_empty = actionable_rows_total == 0

    strict_fail_reasons: list[str] = []
    if not only_actionable:
        strict_fail_reasons.append("only_actionable_false")
    if actionable_rows_total > 0:
        strict_fail_reasons.append("actionable_rows_nonzero")
    if rows_total < actionable_rows_total + likely_not_actionable_rows_total:
        strict_fail_reasons.append("rows_total_less_than_actionability_split")
    if rows_exported_total != actionable_rows_total:
        strict_fail_reasons.append("rows_exported_total_mismatch_actionable_rows_total")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    status = "failed" if strict_fail_reasons else "ok"
    run_at = now_utc_iso()
    heartbeat_id = "|".join(
        [
            status,
            str(rows_total),
            str(actionable_rows_total),
            str(likely_not_actionable_rows_total),
            str(manual_upgrade_rows_total),
            str(official_evidence_gap_rows_total),
            str(official_source_record_gap_rows_total),
            str(rows_exported_total),
            "1" if actionable_queue_empty else "0",
            ",".join(strict_fail_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "summary_path": _safe_text(summary_path),
        "status": status,
        "rows_total": int(rows_total),
        "rows_exported_total": int(rows_exported_total),
        "actionable_rows_total": int(actionable_rows_total),
        "likely_not_actionable_rows_total": int(likely_not_actionable_rows_total),
        "manual_upgrade_rows_total": int(manual_upgrade_rows_total),
        "official_evidence_gap_rows_total": int(official_evidence_gap_rows_total),
        "official_source_record_gap_rows_total": int(official_source_record_gap_rows_total),
        "missing_seed_mapping_total": int(missing_seed_mapping_total),
        "source_record_lookup_rows_total": int(source_record_lookup_rows_total),
        "source_record_pk_lookup_keys_total": int(source_record_pk_lookup_keys_total),
        "source_record_pk_lookup_prefilled_total": int(source_record_pk_lookup_prefilled_total),
        "source_record_pk_lookup_miss_total": int(source_record_pk_lookup_miss_total),
        "only_actionable": bool(only_actionable),
        "strict_empty_actionable": bool(strict_empty_actionable),
        "actionable_queue_empty": bool(actionable_queue_empty),
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
    if status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    for key in (
        "rows_total",
        "rows_exported_total",
        "actionable_rows_total",
        "likely_not_actionable_rows_total",
        "manual_upgrade_rows_total",
        "official_evidence_gap_rows_total",
        "official_source_record_gap_rows_total",
        "missing_seed_mapping_total",
        "source_record_lookup_rows_total",
        "source_record_pk_lookup_keys_total",
        "source_record_pk_lookup_prefilled_total",
        "source_record_pk_lookup_miss_total",
    ):
        value = _to_int(heartbeat.get(key), -1)
        if value < 0:
            reasons.append(f"invalid_{key}")

    rows_total = _to_int(heartbeat.get("rows_total"), 0)
    actionable_rows_total = _to_int(heartbeat.get("actionable_rows_total"), 0)
    likely_not_actionable_rows_total = _to_int(heartbeat.get("likely_not_actionable_rows_total"), 0)
    rows_exported_total = _to_int(heartbeat.get("rows_exported_total"), 0)
    actionable_queue_empty = bool(heartbeat.get("actionable_queue_empty"))
    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)

    if rows_total < actionable_rows_total + likely_not_actionable_rows_total:
        reasons.append("rows_total_less_than_actionability_split")
    if actionable_queue_empty != (actionable_rows_total == 0):
        reasons.append("actionable_queue_empty_mismatch")
    if rows_exported_total != actionable_rows_total:
        reasons.append("rows_exported_total_mismatch_actionable_rows_total")
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")
    if status == "ok" and len(strict_fail_reasons) > 0:
        reasons.append("status_ok_with_strict_fail_reasons")
    if status == "failed" and len(strict_fail_reasons) == 0:
        reasons.append("status_failed_without_strict_fail_reasons")

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
    summary_path = Path(str(args.summary_json))
    heartbeat_path = Path(str(args.heartbeat_jsonl))

    if not summary_path.exists():
        print(json.dumps({"error": f"summary json not found: {summary_path}"}, ensure_ascii=False))
        return 2

    try:
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid summary json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(summary_payload, dict):
        print(json.dumps({"error": "invalid summary json: root must be object"}, ensure_ascii=False))
        return 3

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(summary_path),
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
        heartbeat = build_heartbeat(summary_payload, summary_path=str(summary_path))
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

    if report["validation_errors"] or heartbeat_status == "failed":
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
