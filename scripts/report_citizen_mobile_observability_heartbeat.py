#!/usr/bin/env python3
"""Append-only heartbeat lane for citizen mobile observability digest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OBSERVABILITY_JSON = Path("docs/etl/sprints/AI-OPS-83/evidence/citizen_mobile_observability_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_mobile_observability_heartbeat.jsonl")


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
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for citizen mobile observability digest")
    p.add_argument(
        "--observability-json",
        default=str(DEFAULT_OBSERVABILITY_JSON),
        help=f"Input observability JSON (default: {DEFAULT_OBSERVABILITY_JSON})",
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
    observability_payload: dict[str, Any],
    *,
    observability_path: str,
) -> dict[str, Any]:
    obs = _safe_obj(observability_payload)
    if "status" not in obs and isinstance(obs.get("digest"), dict):
        obs = _safe_obj(obs.get("digest"))

    checks = _safe_obj(obs.get("checks"))
    telemetry = _safe_obj(obs.get("telemetry"))
    metrics = _safe_obj(obs.get("metrics"))
    thresholds = _safe_obj(obs.get("thresholds"))

    status = _normalize_status(obs.get("status"))
    run_at = _safe_text(obs.get("generated_at")) or now_utc_iso()

    sample_count = _to_int(telemetry.get("sample_count"), 0)
    p50 = _safe_float(metrics.get("input_to_render_p50_ms"))
    p90 = _safe_float(metrics.get("input_to_render_p90_ms"))
    p95 = _safe_float(metrics.get("input_to_render_p95_ms"))
    max_p90 = _safe_float(thresholds.get("max_input_to_render_p90_ms"))
    min_samples = _to_int(thresholds.get("min_samples"), 0)

    p90_within_threshold: bool | None
    if p90 is not None and max_p90 is not None:
        p90_within_threshold = bool(p90 <= max_p90)
    elif "input_to_render_p90_within_threshold" in checks:
        p90_within_threshold = bool(checks.get("input_to_render_p90_within_threshold"))
    else:
        p90_within_threshold = None

    contract_complete = bool(checks.get("contract_complete"))
    telemetry_available = bool(checks.get("telemetry_available")) if "telemetry_available" in checks else (
        sample_count > 0
    )
    missing_metrics = _safe_list_str(obs.get("missing_metrics"))
    degraded_reasons = _safe_list_str(obs.get("degraded_reasons"))
    failure_reasons = _safe_list_str(obs.get("failure_reasons"))

    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.extend(failure_reasons)
        if not failure_reasons:
            strict_fail_reasons.append("observability_failed_without_reason")
    if p90_within_threshold is False:
        strict_fail_reasons.append("input_to_render_p90_above_threshold")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    p90_margin_ms: float | None = None
    if p90 is not None and max_p90 is not None:
        p90_margin_ms = round(float(max_p90) - float(p90), 6)

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            str(sample_count),
            _fmt_float(p90),
            _fmt_float(max_p90),
            "1" if contract_complete else "0",
            ",".join(failure_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "observability_path": _safe_text(observability_path),
        "observability_generated_at": _safe_text(obs.get("generated_at")),
        "status": status,
        "sample_count": sample_count,
        "min_samples": min_samples,
        "input_to_render_p50_ms": round(float(p50), 6) if p50 is not None else None,
        "input_to_render_p90_ms": round(float(p90), 6) if p90 is not None else None,
        "input_to_render_p95_ms": round(float(p95), 6) if p95 is not None else None,
        "max_input_to_render_p90_ms": round(float(max_p90), 6) if max_p90 is not None else None,
        "input_to_render_p90_within_threshold": p90_within_threshold,
        "input_to_render_p90_margin_ms": p90_margin_ms,
        "contract_complete": contract_complete,
        "telemetry_available": telemetry_available,
        "missing_metrics": missing_metrics,
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

    sample_count = _to_int(heartbeat.get("sample_count"), -1)
    if sample_count < 0:
        reasons.append("invalid_sample_count")

    min_samples = _to_int(heartbeat.get("min_samples"), -1)
    if min_samples < 0:
        reasons.append("invalid_min_samples")

    for key in ("input_to_render_p50_ms", "input_to_render_p90_ms", "input_to_render_p95_ms", "max_input_to_render_p90_ms"):
        raw = heartbeat.get(key)
        fv = _safe_float(raw)
        if raw is None:
            continue
        if fv is None:
            reasons.append(f"invalid_{key}")
            continue
        if fv < 0:
            reasons.append(f"negative_{key}")

    p90 = _safe_float(heartbeat.get("input_to_render_p90_ms"))
    max_p90 = _safe_float(heartbeat.get("max_input_to_render_p90_ms"))
    p90_within_raw = heartbeat.get("input_to_render_p90_within_threshold")
    if p90_within_raw is not None and not isinstance(p90_within_raw, bool):
        reasons.append("invalid_input_to_render_p90_within_threshold")
    if p90 is not None and max_p90 is not None and isinstance(p90_within_raw, bool):
        expected = bool(p90 <= max_p90)
        if bool(p90_within_raw) != expected:
            reasons.append("p90_threshold_consistency_mismatch")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    contract_complete = bool(heartbeat.get("contract_complete"))
    if contract_complete and raw_status != "ok":
        reasons.append("contract_complete_status_mismatch")

    telemetry_available = bool(heartbeat.get("telemetry_available"))
    if telemetry_available != (sample_count > 0):
        reasons.append("telemetry_available_mismatch")

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

    observability_path = Path(str(args.observability_json))
    if not observability_path.exists():
        print(json.dumps({"error": f"observability json not found: {observability_path}"}, ensure_ascii=False))
        return 2

    try:
        observability_payload = json.loads(observability_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid observability json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(observability_payload, dict):
        print(json.dumps({"error": "invalid observability json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(observability_path),
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
        heartbeat = build_heartbeat(observability_payload, observability_path=str(observability_path))
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
