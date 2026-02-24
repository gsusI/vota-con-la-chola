#!/usr/bin/env python3
"""Append-only heartbeat lane for liberty restrictions status."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATUS_JSON = Path("docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_status_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/liberty_restrictions_status_heartbeat.jsonl")


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


def _as_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


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
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for liberty restrictions status")
    p.add_argument(
        "--status-json",
        default=str(DEFAULT_STATUS_JSON),
        help=f"Input liberty restrictions status JSON (default: {DEFAULT_STATUS_JSON})",
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
    status_payload: dict[str, Any],
    *,
    status_path: str,
) -> dict[str, Any]:
    status_doc = _safe_obj(status_payload)
    coverage = _safe_obj(status_doc.get("coverage"))
    checks = _safe_obj(status_doc.get("checks"))
    focus_gate = _safe_obj(status_doc.get("focus_gate"))
    totals = _safe_obj(status_doc.get("totals"))

    status = _normalize_status(status_doc.get("status"))
    source_generated_at = _safe_text(status_doc.get("generated_at"))
    run_at = source_generated_at or now_utc_iso()

    norms_classified_pct = _safe_float(coverage.get("norms_classified_pct"))
    fragments_with_irlc_pct = _safe_float(coverage.get("fragments_with_irlc_pct"))
    fragments_with_accountability_pct = _safe_float(coverage.get("fragments_with_accountability_pct"))
    fragments_with_dual_coverage_pct = _safe_float(coverage.get("fragments_with_dual_coverage_pct"))
    accountability_edges_with_primary_evidence_pct = _safe_float(
        coverage.get("accountability_edges_with_primary_evidence_pct")
    )
    right_categories_with_data_pct = _safe_float(coverage.get("right_categories_with_data_pct"))
    sources_with_assessments_pct = _safe_float(coverage.get("sources_with_assessments_pct"))
    scopes_with_assessments_pct = _safe_float(coverage.get("scopes_with_assessments_pct"))
    sources_with_dual_coverage_pct = _safe_float(coverage.get("sources_with_dual_coverage_pct"))
    scopes_with_dual_coverage_pct = _safe_float(coverage.get("scopes_with_dual_coverage_pct"))

    focus_gate_passed = _as_bool_or_none(focus_gate.get("passed"))
    norms_classified_gate_passed = _as_bool_or_none(checks.get("norms_classified_gate"))
    fragments_irlc_gate_passed = _as_bool_or_none(checks.get("fragments_irlc_gate"))
    fragments_accountability_gate_passed = _as_bool_or_none(checks.get("fragments_accountability_gate"))
    rights_with_data_gate_passed = _as_bool_or_none(checks.get("rights_with_data_gate"))
    source_representativity_gate_passed = _as_bool_or_none(checks.get("source_representativity_gate"))
    scope_representativity_gate_passed = _as_bool_or_none(checks.get("scope_representativity_gate"))
    source_dual_coverage_gate_passed = _as_bool_or_none(checks.get("source_dual_coverage_gate"))
    scope_dual_coverage_gate_passed = _as_bool_or_none(checks.get("scope_dual_coverage_gate"))
    accountability_primary_evidence_gate_passed = _as_bool_or_none(checks.get("accountability_primary_evidence_gate"))

    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.append("liberty_status_failed")

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            _fmt_float(norms_classified_pct),
            _fmt_float(fragments_with_irlc_pct),
            _fmt_float(fragments_with_accountability_pct),
            _fmt_float(fragments_with_dual_coverage_pct),
            _fmt_float(accountability_edges_with_primary_evidence_pct),
            _fmt_float(right_categories_with_data_pct),
            _fmt_float(sources_with_assessments_pct),
            _fmt_float(scopes_with_assessments_pct),
            _fmt_float(sources_with_dual_coverage_pct),
            _fmt_float(scopes_with_dual_coverage_pct),
            "" if focus_gate_passed is None else ("1" if focus_gate_passed else "0"),
            str(_to_int(totals.get("norms_total"), 0)),
            str(_to_int(totals.get("fragments_total"), 0)),
            str(_to_int(totals.get("sources_with_assessments_total"), 0)),
            str(_to_int(totals.get("scopes_with_assessments_total"), 0)),
            str(_to_int(totals.get("sources_with_dual_coverage_total"), 0)),
            str(_to_int(totals.get("scopes_with_dual_coverage_total"), 0)),
            ",".join(strict_fail_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "status_path": _safe_text(status_path),
        "status_generated_at": source_generated_at,
        "status": status,
        "norms_total": _to_int(totals.get("norms_total"), 0),
        "fragments_total": _to_int(totals.get("fragments_total"), 0),
        "assessments_total": _to_int(totals.get("assessments_total"), 0),
        "sources_total": _to_int(totals.get("sources_total"), 0),
        "sources_with_assessments_total": _to_int(totals.get("sources_with_assessments_total"), 0),
        "scopes_total": _to_int(totals.get("scopes_total"), 0),
        "scopes_with_assessments_total": _to_int(totals.get("scopes_with_assessments_total"), 0),
        "sources_with_dual_coverage_total": _to_int(totals.get("sources_with_dual_coverage_total"), 0),
        "scopes_with_dual_coverage_total": _to_int(totals.get("scopes_with_dual_coverage_total"), 0),
        "accountability_edges_total": _to_int(totals.get("accountability_edges_total"), 0),
        "accountability_edges_with_primary_evidence_total": _to_int(
            totals.get("accountability_edges_with_primary_evidence_total"),
            0,
        ),
        "norms_classified_pct": round(float(norms_classified_pct), 6) if norms_classified_pct is not None else None,
        "fragments_with_irlc_pct": round(float(fragments_with_irlc_pct), 6)
        if fragments_with_irlc_pct is not None
        else None,
        "fragments_with_accountability_pct": round(float(fragments_with_accountability_pct), 6)
        if fragments_with_accountability_pct is not None
        else None,
        "fragments_with_dual_coverage_pct": round(float(fragments_with_dual_coverage_pct), 6)
        if fragments_with_dual_coverage_pct is not None
        else None,
        "accountability_edges_with_primary_evidence_pct": (
            round(float(accountability_edges_with_primary_evidence_pct), 6)
            if accountability_edges_with_primary_evidence_pct is not None
            else None
        ),
        "right_categories_with_data_pct": round(float(right_categories_with_data_pct), 6)
        if right_categories_with_data_pct is not None
        else None,
        "sources_with_assessments_pct": round(float(sources_with_assessments_pct), 6)
        if sources_with_assessments_pct is not None
        else None,
        "scopes_with_assessments_pct": round(float(scopes_with_assessments_pct), 6)
        if scopes_with_assessments_pct is not None
        else None,
        "sources_with_dual_coverage_pct": round(float(sources_with_dual_coverage_pct), 6)
        if sources_with_dual_coverage_pct is not None
        else None,
        "scopes_with_dual_coverage_pct": round(float(scopes_with_dual_coverage_pct), 6)
        if scopes_with_dual_coverage_pct is not None
        else None,
        "focus_gate_passed": focus_gate_passed,
        "norms_classified_gate_passed": norms_classified_gate_passed,
        "fragments_irlc_gate_passed": fragments_irlc_gate_passed,
        "fragments_accountability_gate_passed": fragments_accountability_gate_passed,
        "rights_with_data_gate_passed": rights_with_data_gate_passed,
        "source_representativity_gate_passed": source_representativity_gate_passed,
        "scope_representativity_gate_passed": scope_representativity_gate_passed,
        "source_dual_coverage_gate_passed": source_dual_coverage_gate_passed,
        "scope_dual_coverage_gate_passed": scope_dual_coverage_gate_passed,
        "accountability_primary_evidence_gate_passed": accountability_primary_evidence_gate_passed,
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
        "norms_classified_pct",
        "fragments_with_irlc_pct",
        "fragments_with_accountability_pct",
        "fragments_with_dual_coverage_pct",
        "accountability_edges_with_primary_evidence_pct",
        "right_categories_with_data_pct",
        "sources_with_assessments_pct",
        "scopes_with_assessments_pct",
        "sources_with_dual_coverage_pct",
        "scopes_with_dual_coverage_pct",
    ):
        value = _safe_float(heartbeat.get(key))
        if value is None:
            continue
        if value < 0.0 or value > 1.0:
            reasons.append(f"invalid_{key}")

    for key in (
        "norms_total",
        "fragments_total",
        "assessments_total",
        "sources_total",
        "sources_with_assessments_total",
        "scopes_total",
        "scopes_with_assessments_total",
        "sources_with_dual_coverage_total",
        "scopes_with_dual_coverage_total",
        "accountability_edges_total",
        "accountability_edges_with_primary_evidence_total",
    ):
        value = _to_int(heartbeat.get(key), -1)
        if value < 0:
            reasons.append(f"invalid_{key}")

    focus_gate_passed = _as_bool_or_none(heartbeat.get("focus_gate_passed"))
    if raw_status == "ok" and focus_gate_passed is False:
        reasons.append("focus_gate_status_mismatch")
    rights_with_data_gate_passed = _as_bool_or_none(heartbeat.get("rights_with_data_gate_passed"))
    if raw_status == "ok" and rights_with_data_gate_passed is False:
        reasons.append("rights_with_data_gate_status_mismatch")
    source_representativity_gate_passed = _as_bool_or_none(heartbeat.get("source_representativity_gate_passed"))
    if raw_status == "ok" and source_representativity_gate_passed is False:
        reasons.append("source_representativity_gate_status_mismatch")
    scope_representativity_gate_passed = _as_bool_or_none(heartbeat.get("scope_representativity_gate_passed"))
    if raw_status == "ok" and scope_representativity_gate_passed is False:
        reasons.append("scope_representativity_gate_status_mismatch")
    source_dual_coverage_gate_passed = _as_bool_or_none(heartbeat.get("source_dual_coverage_gate_passed"))
    if raw_status == "ok" and source_dual_coverage_gate_passed is False:
        reasons.append("source_dual_coverage_gate_status_mismatch")
    scope_dual_coverage_gate_passed = _as_bool_or_none(heartbeat.get("scope_dual_coverage_gate_passed"))
    if raw_status == "ok" and scope_dual_coverage_gate_passed is False:
        reasons.append("scope_dual_coverage_gate_status_mismatch")
    accountability_primary_evidence_gate_passed = _as_bool_or_none(
        heartbeat.get("accountability_primary_evidence_gate_passed")
    )
    if raw_status == "ok" and accountability_primary_evidence_gate_passed is False:
        reasons.append("accountability_primary_evidence_gate_status_mismatch")

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

    status_path = Path(str(args.status_json))
    if not status_path.exists():
        print(json.dumps({"error": f"status json not found: {status_path}"}, ensure_ascii=False))
        return 2

    try:
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid status json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(status_payload, dict):
        print(json.dumps({"error": "invalid status json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(status_path),
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
        heartbeat = build_heartbeat(status_payload, status_path=str(status_path))
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
