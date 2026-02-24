#!/usr/bin/env python3
"""Parity report for raw vs compacted product KPI heartbeat (last-N window)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_product_kpis_heartbeat.jsonl")
DEFAULT_COMPACTED_JSONL = Path("docs/etl/runs/citizen_product_kpis_heartbeat.compacted.jsonl")
DEFAULT_LAST = 20


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


def _to_bool(value: Any) -> bool:
    return bool(value)


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


def _round4(value: float) -> float:
    return round(float(value), 4)


def _parse_positive_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 1:
        raise ValueError(f"{arg_name} must be >= 1")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citizen product KPI heartbeat compaction-window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Raw heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--compacted-jsonl",
        default=str(DEFAULT_COMPACTED_JSONL),
        help=f"Compacted heartbeat JSONL path (default: {DEFAULT_COMPACTED_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing raw rows to compare (default: {DEFAULT_LAST})")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when strict checks fail.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def read_heartbeat_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def _is_threshold_violation(entry: dict[str, Any], *, key_ok: str) -> bool:
    raw = entry.get(key_ok)
    if isinstance(raw, bool):
        return not raw
    return True


def _to_ref(row: dict[str, Any]) -> dict[str, Any]:
    entry = _safe_obj(row.get("entry"))
    heartbeat_id = _safe_text(entry.get("heartbeat_id"))
    run_at = _safe_text(entry.get("run_at"))
    status = _normalize_status(entry.get("status"))
    strict_fail_count = _to_int(entry.get("strict_fail_count"), 0)
    strict_fail_reasons = _safe_list_str(entry.get("strict_fail_reasons"))
    line_no = _to_int(row.get("line_no"), 0)
    return {
        "line_no": line_no,
        "malformed_line": _to_bool(row.get("malformed_line")),
        "heartbeat_id": heartbeat_id,
        "run_at": run_at,
        "status": status,
        "strict_fail_count": strict_fail_count,
        "strict_fail_reasons": strict_fail_reasons,
        "contract_complete": bool(entry.get("contract_complete")),
        "unknown_rate_violation": _is_threshold_violation(entry, key_ok="unknown_rate_within_threshold"),
        "tfa_violation": _is_threshold_violation(entry, key_ok="time_to_first_answer_within_threshold"),
        "drilldown_violation": _is_threshold_violation(entry, key_ok="drilldown_click_rate_within_threshold"),
        "id": heartbeat_id or run_at or f"line:{line_no}",
    }


def _has_incident(ref: dict[str, Any]) -> bool:
    if _to_bool(ref.get("malformed_line")):
        return True
    if _normalize_status(ref.get("status")) in {"failed", "degraded"}:
        return True
    if _to_int(ref.get("strict_fail_count"), 0) > 0:
        return True
    if len(_safe_list_str(ref.get("strict_fail_reasons"))) > 0:
        return True
    if not bool(ref.get("contract_complete")):
        return True
    if bool(ref.get("unknown_rate_violation")):
        return True
    if bool(ref.get("tfa_violation")):
        return True
    if bool(ref.get("drilldown_violation")):
        return True
    return False


def _build_compacted_index(refs: list[dict[str, Any]]) -> dict[str, set[str]]:
    heartbeat_ids: set[str] = set()
    run_ats: set[str] = set()
    line_ids: set[str] = set()
    for ref in refs:
        hb = _safe_text(ref.get("heartbeat_id"))
        ra = _safe_text(ref.get("run_at"))
        if hb:
            heartbeat_ids.add(hb)
        if ra:
            run_ats.add(ra)
        line_ids.add(_safe_text(ref.get("id")))
    return {"heartbeat_ids": heartbeat_ids, "run_ats": run_ats, "line_ids": line_ids}


def _present_in_compacted(ref: dict[str, Any], idx: dict[str, set[str]]) -> bool:
    hb = _safe_text(ref.get("heartbeat_id"))
    ra = _safe_text(ref.get("run_at"))
    line_id = _safe_text(ref.get("id"))
    if hb:
        return hb in idx["heartbeat_ids"]
    if ra:
        return ra in idx["run_ats"]
    return line_id in idx["line_ids"]


def _sample_ref(ref: dict[str, Any], *, present: bool) -> dict[str, Any]:
    return {
        "id": _safe_text(ref.get("id")),
        "heartbeat_id": _safe_text(ref.get("heartbeat_id")),
        "run_at": _safe_text(ref.get("run_at")),
        "line_no": _to_int(ref.get("line_no"), 0),
        "status": _normalize_status(ref.get("status")),
        "malformed_line": _to_bool(ref.get("malformed_line")),
        "contract_complete": bool(ref.get("contract_complete")),
        "unknown_rate_violation": bool(ref.get("unknown_rate_violation")),
        "tfa_violation": bool(ref.get("tfa_violation")),
        "drilldown_violation": bool(ref.get("drilldown_violation")),
        "present_in_compacted": bool(present),
    }


def build_compaction_window_report(
    raw_rows: list[dict[str, Any]],
    compacted_rows: list[dict[str, Any]],
    *,
    heartbeat_path: str = "",
    compacted_path: str = "",
    window_last: int = DEFAULT_LAST,
    strict: bool = False,
) -> dict[str, Any]:
    last_n = _parse_positive_int(window_last, arg_name="window_last")
    raw_window_rows = raw_rows[max(0, len(raw_rows) - last_n) :]
    raw_window_refs = [_to_ref(r) for r in raw_window_rows]
    compacted_refs = [_to_ref(r) for r in compacted_rows]
    compacted_idx = _build_compacted_index(compacted_refs)

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "compacted_path": compacted_path,
        "window_last": int(last_n),
        "entries_total_raw": len(raw_rows),
        "entries_total_compacted": len(compacted_rows),
        "window_raw_entries": len(raw_window_refs),
        "window_raw_malformed_entries": sum(1 for r in raw_window_refs if _to_bool(r.get("malformed_line"))),
        "compacted_malformed_entries": sum(1 for r in compacted_refs if _to_bool(r.get("malformed_line"))),
        "raw_window_status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "raw_window_incidents": 0,
        "raw_window_failed": 0,
        "raw_window_degraded": 0,
        "raw_window_strict_rows": 0,
        "raw_window_contract_incomplete_rows": 0,
        "raw_window_unknown_rate_violations": 0,
        "raw_window_tfa_violations": 0,
        "raw_window_drilldown_violations": 0,
        "present_in_compacted_in_window": 0,
        "missing_in_compacted_in_window": 0,
        "incident_present_in_compacted": 0,
        "incident_missing_in_compacted": 0,
        "failed_present_in_compacted": 0,
        "degraded_present_in_compacted": 0,
        "strict_rows_present_in_compacted": 0,
        "contract_incomplete_present_in_compacted": 0,
        "contract_incomplete_missing_in_compacted": 0,
        "unknown_rate_violations_present_in_compacted": 0,
        "unknown_rate_violations_missing_in_compacted": 0,
        "tfa_violations_present_in_compacted": 0,
        "tfa_violations_missing_in_compacted": 0,
        "drilldown_violations_present_in_compacted": 0,
        "drilldown_violations_missing_in_compacted": 0,
        "malformed_present_in_compacted": 0,
        "raw_window_coverage_pct": 0.0,
        "incident_coverage_pct": 0.0,
        "latest_raw": {},
        "missing_raw_ids_sample": [],
        "missing_incident_ids_sample": [],
        "checks": {
            "window_nonempty_ok": False,
            "raw_window_malformed_ok": False,
            "compacted_malformed_ok": False,
            "latest_present_ok": False,
            "incident_parity_ok": False,
            "failed_parity_ok": False,
            "degraded_parity_ok": False,
            "strict_rows_parity_ok": False,
            "contract_incomplete_parity_ok": False,
            "unknown_rate_violations_parity_ok": False,
            "tfa_violations_parity_ok": False,
            "drilldown_violations_parity_ok": False,
            "malformed_parity_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "degraded",
    }

    for ref in raw_window_refs:
        status = _normalize_status(ref.get("status"))
        present = _present_in_compacted(ref, compacted_idx)
        incident = _has_incident(ref)
        is_strict = _to_int(ref.get("strict_fail_count"), 0) > 0 or len(_safe_list_str(ref.get("strict_fail_reasons"))) > 0
        is_malformed = _to_bool(ref.get("malformed_line"))
        is_contract_incomplete = not bool(ref.get("contract_complete"))
        is_unknown_rate_violation = bool(ref.get("unknown_rate_violation"))
        is_tfa_violation = bool(ref.get("tfa_violation"))
        is_drilldown_violation = bool(ref.get("drilldown_violation"))

        report["raw_window_status_counts"][status] += 1
        if incident:
            report["raw_window_incidents"] += 1
        if status == "failed":
            report["raw_window_failed"] += 1
        if status == "degraded":
            report["raw_window_degraded"] += 1
        if is_strict:
            report["raw_window_strict_rows"] += 1
        if is_contract_incomplete:
            report["raw_window_contract_incomplete_rows"] += 1
        if is_unknown_rate_violation:
            report["raw_window_unknown_rate_violations"] += 1
        if is_tfa_violation:
            report["raw_window_tfa_violations"] += 1
        if is_drilldown_violation:
            report["raw_window_drilldown_violations"] += 1

        if present:
            report["present_in_compacted_in_window"] += 1
            if incident:
                report["incident_present_in_compacted"] += 1
            if status == "failed":
                report["failed_present_in_compacted"] += 1
            if status == "degraded":
                report["degraded_present_in_compacted"] += 1
            if is_strict:
                report["strict_rows_present_in_compacted"] += 1
            if is_malformed:
                report["malformed_present_in_compacted"] += 1
            if is_contract_incomplete:
                report["contract_incomplete_present_in_compacted"] += 1
            if is_unknown_rate_violation:
                report["unknown_rate_violations_present_in_compacted"] += 1
            if is_tfa_violation:
                report["tfa_violations_present_in_compacted"] += 1
            if is_drilldown_violation:
                report["drilldown_violations_present_in_compacted"] += 1
        else:
            report["missing_in_compacted_in_window"] += 1
            if len(report["missing_raw_ids_sample"]) < 20:
                report["missing_raw_ids_sample"].append(_sample_ref(ref, present=False))
            if incident:
                report["incident_missing_in_compacted"] += 1
                if len(report["missing_incident_ids_sample"]) < 20:
                    report["missing_incident_ids_sample"].append(_sample_ref(ref, present=False))
            if is_contract_incomplete:
                report["contract_incomplete_missing_in_compacted"] += 1
            if is_unknown_rate_violation:
                report["unknown_rate_violations_missing_in_compacted"] += 1
            if is_tfa_violation:
                report["tfa_violations_missing_in_compacted"] += 1
            if is_drilldown_violation:
                report["drilldown_violations_missing_in_compacted"] += 1

    if report["window_raw_entries"] > 0:
        report["raw_window_coverage_pct"] = _round4(
            float(report["present_in_compacted_in_window"]) / float(report["window_raw_entries"]) * 100.0
        )
    if report["raw_window_incidents"] > 0:
        report["incident_coverage_pct"] = _round4(
            float(report["incident_present_in_compacted"]) / float(report["raw_window_incidents"]) * 100.0
        )

    latest_raw = raw_window_refs[-1] if raw_window_refs else None
    report["latest_raw"] = _sample_ref(latest_raw, present=_present_in_compacted(latest_raw, compacted_idx)) if latest_raw else {}

    checks = report["checks"]
    checks["window_nonempty_ok"] = report["window_raw_entries"] > 0
    checks["raw_window_malformed_ok"] = report["window_raw_malformed_entries"] == 0
    checks["compacted_malformed_ok"] = report["compacted_malformed_entries"] == 0
    checks["latest_present_ok"] = bool(latest_raw) and _present_in_compacted(latest_raw, compacted_idx)
    checks["incident_parity_ok"] = report["incident_missing_in_compacted"] == 0
    checks["failed_parity_ok"] = report["failed_present_in_compacted"] >= report["raw_window_failed"]
    checks["degraded_parity_ok"] = report["degraded_present_in_compacted"] >= report["raw_window_degraded"]
    checks["strict_rows_parity_ok"] = report["strict_rows_present_in_compacted"] >= report["raw_window_strict_rows"]
    checks["contract_incomplete_parity_ok"] = (
        report["contract_incomplete_present_in_compacted"] >= report["raw_window_contract_incomplete_rows"]
    )
    checks["unknown_rate_violations_parity_ok"] = (
        report["unknown_rate_violations_present_in_compacted"] >= report["raw_window_unknown_rate_violations"]
    )
    checks["tfa_violations_parity_ok"] = report["tfa_violations_present_in_compacted"] >= report["raw_window_tfa_violations"]
    checks["drilldown_violations_parity_ok"] = (
        report["drilldown_violations_present_in_compacted"] >= report["raw_window_drilldown_violations"]
    )
    checks["malformed_parity_ok"] = report["malformed_present_in_compacted"] >= report["window_raw_malformed_entries"]

    reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        reasons.append("empty_raw_window")
    if not checks["raw_window_malformed_ok"]:
        reasons.append("raw_window_malformed_entries_present")
    if not checks["compacted_malformed_ok"]:
        reasons.append("compacted_malformed_entries_present")
    if not checks["latest_present_ok"]:
        reasons.append("latest_raw_missing_in_compacted")
    if not checks["incident_parity_ok"]:
        reasons.append("incident_missing_in_compacted")
    if not checks["failed_parity_ok"]:
        reasons.append("failed_underreported_in_compacted")
    if not checks["degraded_parity_ok"]:
        reasons.append("degraded_underreported_in_compacted")
    if not checks["strict_rows_parity_ok"]:
        reasons.append("strict_rows_underreported_in_compacted")
    if not checks["contract_incomplete_parity_ok"]:
        reasons.append("contract_incomplete_underreported_in_compacted")
    if not checks["unknown_rate_violations_parity_ok"]:
        reasons.append("unknown_rate_violations_underreported_in_compacted")
    if not checks["tfa_violations_parity_ok"]:
        reasons.append("tfa_violations_underreported_in_compacted")
    if not checks["drilldown_violations_parity_ok"]:
        reasons.append("drilldown_violations_underreported_in_compacted")
    if not checks["malformed_parity_ok"]:
        reasons.append("malformed_rows_underreported_in_compacted")
    report["strict_fail_reasons"] = reasons

    if report["window_raw_entries"] == 0:
        report["status"] = "degraded"
    elif reasons:
        report["status"] = "failed"
    elif report["missing_in_compacted_in_window"] > 0:
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report


def build_compaction_window_report_from_paths(
    heartbeat_path: Path,
    compacted_path: Path,
    *,
    window_last: int = DEFAULT_LAST,
    strict: bool = False,
) -> dict[str, Any]:
    raw_rows = read_heartbeat_rows(heartbeat_path)
    compacted_rows = read_heartbeat_rows(compacted_path)
    return build_compaction_window_report(
        raw_rows,
        compacted_rows,
        heartbeat_path=str(heartbeat_path),
        compacted_path=str(compacted_path),
        window_last=window_last,
        strict=strict,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        report = build_compaction_window_report_from_paths(
            Path(str(args.heartbeat_jsonl)),
            Path(str(args.compacted_jsonl)),
            window_last=int(args.last),
            strict=bool(args.strict),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
