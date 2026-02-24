#!/usr/bin/env python3
"""Windowed trend report for liberty restrictions status heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/liberty_restrictions_status_heartbeat.jsonl")
DEFAULT_LAST = 20
DEFAULT_MAX_FAILED = 0
DEFAULT_MAX_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_FOCUS_GATE_FAILED = 0
DEFAULT_MAX_FOCUS_GATE_FAILED_RATE_PCT = 0.0
DEFAULT_MAX_NORMS_CLASSIFIED_GATE_FAILED = 0
DEFAULT_MAX_FRAGMENTS_IRLC_GATE_FAILED = 0
DEFAULT_MAX_FRAGMENTS_ACCOUNTABILITY_GATE_FAILED = 0
DEFAULT_MAX_RIGHTS_WITH_DATA_GATE_FAILED = 0
DEFAULT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED = 0
DEFAULT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED = 0
DEFAULT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED = 0
DEFAULT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED = 0
DEFAULT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED = 0


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


def _parse_non_negative_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def _parse_non_negative_float(raw: Any, *, arg_name: str) -> float:
    value = _to_float(raw, -1.0)
    if value < 0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def _rate_pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return _round4((float(numer) / float(denom)) * 100.0)


def _as_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Liberty restrictions heartbeat window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing rows to inspect (default: {DEFAULT_LAST})")
    p.add_argument("--max-failed", type=int, default=DEFAULT_MAX_FAILED)
    p.add_argument("--max-failed-rate-pct", type=float, default=DEFAULT_MAX_FAILED_RATE_PCT)
    p.add_argument("--max-focus-gate-failed", type=int, default=DEFAULT_MAX_FOCUS_GATE_FAILED)
    p.add_argument("--max-focus-gate-failed-rate-pct", type=float, default=DEFAULT_MAX_FOCUS_GATE_FAILED_RATE_PCT)
    p.add_argument("--max-norms-classified-gate-failed", type=int, default=DEFAULT_MAX_NORMS_CLASSIFIED_GATE_FAILED)
    p.add_argument("--max-fragments-irlc-gate-failed", type=int, default=DEFAULT_MAX_FRAGMENTS_IRLC_GATE_FAILED)
    p.add_argument(
        "--max-fragments-accountability-gate-failed",
        type=int,
        default=DEFAULT_MAX_FRAGMENTS_ACCOUNTABILITY_GATE_FAILED,
    )
    p.add_argument("--max-rights-with-data-gate-failed", type=int, default=DEFAULT_MAX_RIGHTS_WITH_DATA_GATE_FAILED)
    p.add_argument(
        "--max-source-representativity-gate-failed",
        type=int,
        default=DEFAULT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED,
    )
    p.add_argument(
        "--max-scope-representativity-gate-failed",
        type=int,
        default=DEFAULT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED,
    )
    p.add_argument(
        "--max-source-dual-coverage-gate-failed",
        type=int,
        default=DEFAULT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED,
    )
    p.add_argument(
        "--max-scope-dual-coverage-gate-failed",
        type=int,
        default=DEFAULT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED,
    )
    p.add_argument(
        "--max-accountability-primary-evidence-gate-failed",
        type=int,
        default=DEFAULT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED,
    )
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict_fail_reasons is not empty.")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def read_heartbeat_rows(heartbeat_path: Path) -> list[dict[str, Any]]:
    if not heartbeat_path.exists():
        return []
    raw = heartbeat_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def _latest_summary(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "run_at": "",
            "heartbeat_id": "",
            "status": "failed",
            "line_no": 0,
            "malformed_line": True,
            "status_generated_at": "",
            "focus_gate_passed": None,
            "norms_classified_gate_passed": None,
            "fragments_irlc_gate_passed": None,
            "fragments_accountability_gate_passed": None,
            "rights_with_data_gate_passed": None,
            "source_representativity_gate_passed": None,
            "scope_representativity_gate_passed": None,
            "source_dual_coverage_gate_passed": None,
            "scope_dual_coverage_gate_passed": None,
            "accountability_primary_evidence_gate_passed": None,
        }
    malformed = bool(row.get("malformed_line"))
    entry = _safe_obj(row.get("entry"))
    return {
        "run_at": _safe_text(entry.get("run_at")),
        "heartbeat_id": _safe_text(entry.get("heartbeat_id")),
        "status": "failed" if malformed else _normalize_status(entry.get("status")),
        "line_no": _to_int(row.get("line_no"), 0),
        "malformed_line": malformed,
        "status_generated_at": _safe_text(entry.get("status_generated_at")),
        "focus_gate_passed": _as_bool_or_none(entry.get("focus_gate_passed")),
        "norms_classified_gate_passed": _as_bool_or_none(entry.get("norms_classified_gate_passed")),
        "fragments_irlc_gate_passed": _as_bool_or_none(entry.get("fragments_irlc_gate_passed")),
        "fragments_accountability_gate_passed": _as_bool_or_none(entry.get("fragments_accountability_gate_passed")),
        "rights_with_data_gate_passed": _as_bool_or_none(entry.get("rights_with_data_gate_passed")),
        "source_representativity_gate_passed": _as_bool_or_none(entry.get("source_representativity_gate_passed")),
        "scope_representativity_gate_passed": _as_bool_or_none(entry.get("scope_representativity_gate_passed")),
        "source_dual_coverage_gate_passed": _as_bool_or_none(entry.get("source_dual_coverage_gate_passed")),
        "scope_dual_coverage_gate_passed": _as_bool_or_none(entry.get("scope_dual_coverage_gate_passed")),
        "accountability_primary_evidence_gate_passed": _as_bool_or_none(
            entry.get("accountability_primary_evidence_gate_passed")
        ),
    }


def _latest_streak(window_rows: list[dict[str, Any]], *, status: str) -> int:
    streak = 0
    target = _normalize_status(status)
    for row in reversed(window_rows):
        if bool(row.get("malformed_line")):
            break
        entry = _safe_obj(row.get("entry"))
        current = _normalize_status(entry.get("status"))
        if current != target:
            break
        streak += 1
    return streak


def _is_gate_failed(entry: dict[str, Any], *, key: str) -> bool:
    value = _as_bool_or_none(entry.get(key))
    return value is not True


def _is_optional_gate_failed(entry: dict[str, Any], *, key: str) -> bool:
    value = _as_bool_or_none(entry.get(key))
    return value is False


def build_window_report(
    rows: list[dict[str, Any]],
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_failed_rate_pct: float = DEFAULT_MAX_FAILED_RATE_PCT,
    max_focus_gate_failed: int = DEFAULT_MAX_FOCUS_GATE_FAILED,
    max_focus_gate_failed_rate_pct: float = DEFAULT_MAX_FOCUS_GATE_FAILED_RATE_PCT,
    max_norms_classified_gate_failed: int = DEFAULT_MAX_NORMS_CLASSIFIED_GATE_FAILED,
    max_fragments_irlc_gate_failed: int = DEFAULT_MAX_FRAGMENTS_IRLC_GATE_FAILED,
    max_fragments_accountability_gate_failed: int = DEFAULT_MAX_FRAGMENTS_ACCOUNTABILITY_GATE_FAILED,
    max_rights_with_data_gate_failed: int = DEFAULT_MAX_RIGHTS_WITH_DATA_GATE_FAILED,
    max_source_representativity_gate_failed: int = DEFAULT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED,
    max_scope_representativity_gate_failed: int = DEFAULT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED,
    max_source_dual_coverage_gate_failed: int = DEFAULT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED,
    max_scope_dual_coverage_gate_failed: int = DEFAULT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED,
    max_accountability_primary_evidence_gate_failed: int = DEFAULT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED,
    strict: bool = False,
    heartbeat_path: str = "",
) -> dict[str, Any]:
    window_size = _parse_positive_int(window_last, arg_name="window_last")
    max_failed_n = _parse_non_negative_int(max_failed, arg_name="max_failed")
    max_failed_rate = _parse_non_negative_float(max_failed_rate_pct, arg_name="max_failed_rate_pct")
    max_focus_failed_n = _parse_non_negative_int(max_focus_gate_failed, arg_name="max_focus_gate_failed")
    max_focus_failed_rate = _parse_non_negative_float(
        max_focus_gate_failed_rate_pct,
        arg_name="max_focus_gate_failed_rate_pct",
    )
    max_norms_gate_failed_n = _parse_non_negative_int(
        max_norms_classified_gate_failed,
        arg_name="max_norms_classified_gate_failed",
    )
    max_fragments_irlc_gate_failed_n = _parse_non_negative_int(
        max_fragments_irlc_gate_failed,
        arg_name="max_fragments_irlc_gate_failed",
    )
    max_fragments_accountability_gate_failed_n = _parse_non_negative_int(
        max_fragments_accountability_gate_failed,
        arg_name="max_fragments_accountability_gate_failed",
    )
    max_rights_with_data_gate_failed_n = _parse_non_negative_int(
        max_rights_with_data_gate_failed,
        arg_name="max_rights_with_data_gate_failed",
    )
    max_source_representativity_gate_failed_n = _parse_non_negative_int(
        max_source_representativity_gate_failed,
        arg_name="max_source_representativity_gate_failed",
    )
    max_scope_representativity_gate_failed_n = _parse_non_negative_int(
        max_scope_representativity_gate_failed,
        arg_name="max_scope_representativity_gate_failed",
    )
    max_source_dual_coverage_gate_failed_n = _parse_non_negative_int(
        max_source_dual_coverage_gate_failed,
        arg_name="max_source_dual_coverage_gate_failed",
    )
    max_scope_dual_coverage_gate_failed_n = _parse_non_negative_int(
        max_scope_dual_coverage_gate_failed,
        arg_name="max_scope_dual_coverage_gate_failed",
    )
    max_accountability_primary_evidence_gate_failed_n = _parse_non_negative_int(
        max_accountability_primary_evidence_gate_failed,
        arg_name="max_accountability_primary_evidence_gate_failed",
    )

    window_rows = rows[max(0, len(rows) - window_size) :]
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "window_last": int(window_size),
        "thresholds": {
            "max_failed": int(max_failed_n),
            "max_failed_rate_pct": float(max_failed_rate),
            "max_focus_gate_failed": int(max_focus_failed_n),
            "max_focus_gate_failed_rate_pct": float(max_focus_failed_rate),
            "max_norms_classified_gate_failed": int(max_norms_gate_failed_n),
            "max_fragments_irlc_gate_failed": int(max_fragments_irlc_gate_failed_n),
            "max_fragments_accountability_gate_failed": int(max_fragments_accountability_gate_failed_n),
            "max_rights_with_data_gate_failed": int(max_rights_with_data_gate_failed_n),
            "max_source_representativity_gate_failed": int(max_source_representativity_gate_failed_n),
            "max_scope_representativity_gate_failed": int(max_scope_representativity_gate_failed_n),
            "max_source_dual_coverage_gate_failed": int(max_source_dual_coverage_gate_failed_n),
            "max_scope_dual_coverage_gate_failed": int(max_scope_dual_coverage_gate_failed_n),
            "max_accountability_primary_evidence_gate_failed": int(
                max_accountability_primary_evidence_gate_failed_n
            ),
        },
        "entries_total": len(rows),
        "entries_in_window": len(window_rows),
        "malformed_entries_in_window": 0,
        "status_counts": {"ok": 0, "degraded": 0, "failed": 0},
        "failed_in_window": 0,
        "failed_rate_pct": 0.0,
        "degraded_in_window": 0,
        "degraded_rate_pct": 0.0,
        "focus_gate_failed_in_window": 0,
        "focus_gate_failed_rate_pct": 0.0,
        "norms_classified_gate_failed_in_window": 0,
        "fragments_irlc_gate_failed_in_window": 0,
        "fragments_accountability_gate_failed_in_window": 0,
        "rights_with_data_gate_failed_in_window": 0,
        "source_representativity_gate_failed_in_window": 0,
        "scope_representativity_gate_failed_in_window": 0,
        "source_dual_coverage_gate_failed_in_window": 0,
        "scope_dual_coverage_gate_failed_in_window": 0,
        "accountability_primary_evidence_gate_failed_in_window": 0,
        "first_failed_run_at": "",
        "last_failed_run_at": "",
        "first_focus_gate_failed_run_at": "",
        "last_focus_gate_failed_run_at": "",
        "latest": {},
        "failed_streak_latest": 0,
        "degraded_streak_latest": 0,
        "checks": {
            "window_nonempty_ok": False,
            "malformed_entries_ok": False,
            "max_failed_ok": False,
            "max_failed_rate_ok": False,
            "max_focus_gate_failed_ok": False,
            "max_focus_gate_failed_rate_ok": False,
            "max_norms_classified_gate_failed_ok": False,
            "max_fragments_irlc_gate_failed_ok": False,
            "max_fragments_accountability_gate_failed_ok": False,
            "max_rights_with_data_gate_failed_ok": False,
            "max_source_representativity_gate_failed_ok": False,
            "max_scope_representativity_gate_failed_ok": False,
            "max_source_dual_coverage_gate_failed_ok": False,
            "max_scope_dual_coverage_gate_failed_ok": False,
            "max_accountability_primary_evidence_gate_failed_ok": False,
            "latest_not_failed_ok": False,
            "latest_focus_gate_passed_ok": False,
            "latest_norms_classified_gate_ok": False,
            "latest_fragments_irlc_gate_ok": False,
            "latest_fragments_accountability_gate_ok": False,
            "latest_rights_with_data_gate_ok": False,
            "latest_source_representativity_gate_ok": False,
            "latest_scope_representativity_gate_ok": False,
            "latest_source_dual_coverage_gate_ok": False,
            "latest_scope_dual_coverage_gate_ok": False,
            "latest_accountability_primary_evidence_gate_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "degraded",
    }

    for row in window_rows:
        if bool(row.get("malformed_line")):
            report["malformed_entries_in_window"] = int(report["malformed_entries_in_window"]) + 1
            continue

        entry = _safe_obj(row.get("entry"))
        status = _normalize_status(entry.get("status"))
        run_at = _safe_text(entry.get("run_at"))
        report["status_counts"][status] = int(report["status_counts"].get(status, 0)) + 1

        if status == "failed":
            if not report["first_failed_run_at"]:
                report["first_failed_run_at"] = run_at
            report["last_failed_run_at"] = run_at

        if _is_gate_failed(entry, key="focus_gate_passed"):
            report["focus_gate_failed_in_window"] = int(report["focus_gate_failed_in_window"]) + 1
            if not report["first_focus_gate_failed_run_at"]:
                report["first_focus_gate_failed_run_at"] = run_at
            report["last_focus_gate_failed_run_at"] = run_at

        if _is_gate_failed(entry, key="norms_classified_gate_passed"):
            report["norms_classified_gate_failed_in_window"] = int(report["norms_classified_gate_failed_in_window"]) + 1
        if _is_gate_failed(entry, key="fragments_irlc_gate_passed"):
            report["fragments_irlc_gate_failed_in_window"] = int(report["fragments_irlc_gate_failed_in_window"]) + 1
        if _is_gate_failed(entry, key="fragments_accountability_gate_passed"):
            report["fragments_accountability_gate_failed_in_window"] = int(
                report["fragments_accountability_gate_failed_in_window"]
            ) + 1
        if _is_optional_gate_failed(entry, key="rights_with_data_gate_passed"):
            report["rights_with_data_gate_failed_in_window"] = int(report["rights_with_data_gate_failed_in_window"]) + 1
        if _is_optional_gate_failed(entry, key="source_representativity_gate_passed"):
            report["source_representativity_gate_failed_in_window"] = (
                int(report["source_representativity_gate_failed_in_window"]) + 1
            )
        if _is_optional_gate_failed(entry, key="scope_representativity_gate_passed"):
            report["scope_representativity_gate_failed_in_window"] = (
                int(report["scope_representativity_gate_failed_in_window"]) + 1
            )
        if _is_optional_gate_failed(entry, key="source_dual_coverage_gate_passed"):
            report["source_dual_coverage_gate_failed_in_window"] = (
                int(report["source_dual_coverage_gate_failed_in_window"]) + 1
            )
        if _is_optional_gate_failed(entry, key="scope_dual_coverage_gate_passed"):
            report["scope_dual_coverage_gate_failed_in_window"] = (
                int(report["scope_dual_coverage_gate_failed_in_window"]) + 1
            )
        if _is_optional_gate_failed(entry, key="accountability_primary_evidence_gate_passed"):
            report["accountability_primary_evidence_gate_failed_in_window"] = (
                int(report["accountability_primary_evidence_gate_failed_in_window"]) + 1
            )

    report["failed_in_window"] = int(report["status_counts"]["failed"])
    report["degraded_in_window"] = int(report["status_counts"]["degraded"])

    if report["entries_in_window"] > 0:
        denom = int(report["entries_in_window"])
        report["failed_rate_pct"] = _rate_pct(int(report["failed_in_window"]), denom)
        report["degraded_rate_pct"] = _rate_pct(int(report["degraded_in_window"]), denom)
        report["focus_gate_failed_rate_pct"] = _rate_pct(int(report["focus_gate_failed_in_window"]), denom)
        report["latest"] = _latest_summary(window_rows[-1])
        report["failed_streak_latest"] = _latest_streak(window_rows, status="failed")
        report["degraded_streak_latest"] = _latest_streak(window_rows, status="degraded")
    else:
        report["latest"] = _latest_summary(None)

    checks = report["checks"]
    checks["window_nonempty_ok"] = report["entries_in_window"] > 0
    checks["malformed_entries_ok"] = report["malformed_entries_in_window"] == 0
    checks["max_failed_ok"] = report["failed_in_window"] <= max_failed_n
    checks["max_failed_rate_ok"] = float(report["failed_rate_pct"]) <= max_failed_rate
    checks["max_focus_gate_failed_ok"] = report["focus_gate_failed_in_window"] <= max_focus_failed_n
    checks["max_focus_gate_failed_rate_ok"] = float(report["focus_gate_failed_rate_pct"]) <= max_focus_failed_rate
    checks["max_norms_classified_gate_failed_ok"] = (
        report["norms_classified_gate_failed_in_window"] <= max_norms_gate_failed_n
    )
    checks["max_fragments_irlc_gate_failed_ok"] = (
        report["fragments_irlc_gate_failed_in_window"] <= max_fragments_irlc_gate_failed_n
    )
    checks["max_fragments_accountability_gate_failed_ok"] = (
        report["fragments_accountability_gate_failed_in_window"] <= max_fragments_accountability_gate_failed_n
    )
    checks["max_rights_with_data_gate_failed_ok"] = (
        report["rights_with_data_gate_failed_in_window"] <= max_rights_with_data_gate_failed_n
    )
    checks["max_source_representativity_gate_failed_ok"] = (
        report["source_representativity_gate_failed_in_window"] <= max_source_representativity_gate_failed_n
    )
    checks["max_scope_representativity_gate_failed_ok"] = (
        report["scope_representativity_gate_failed_in_window"] <= max_scope_representativity_gate_failed_n
    )
    checks["max_source_dual_coverage_gate_failed_ok"] = (
        report["source_dual_coverage_gate_failed_in_window"] <= max_source_dual_coverage_gate_failed_n
    )
    checks["max_scope_dual_coverage_gate_failed_ok"] = (
        report["scope_dual_coverage_gate_failed_in_window"] <= max_scope_dual_coverage_gate_failed_n
    )
    checks["max_accountability_primary_evidence_gate_failed_ok"] = (
        report["accountability_primary_evidence_gate_failed_in_window"]
        <= max_accountability_primary_evidence_gate_failed_n
    )
    checks["latest_not_failed_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _normalize_status(_safe_obj(report["latest"]).get("status")) != "failed"
    )
    checks["latest_focus_gate_passed_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _as_bool_or_none(_safe_obj(report["latest"]).get("focus_gate_passed")) is True
    )
    checks["latest_norms_classified_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _as_bool_or_none(_safe_obj(report["latest"]).get("norms_classified_gate_passed")) is True
    )
    checks["latest_fragments_irlc_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _as_bool_or_none(_safe_obj(report["latest"]).get("fragments_irlc_gate_passed")) is True
    )
    checks["latest_fragments_accountability_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and _as_bool_or_none(_safe_obj(report["latest"]).get("fragments_accountability_gate_passed")) is True
    )
    latest_rights_with_data = _as_bool_or_none(_safe_obj(report["latest"]).get("rights_with_data_gate_passed"))
    checks["latest_rights_with_data_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_rights_with_data is not False
    )
    latest_source_representativity = _as_bool_or_none(
        _safe_obj(report["latest"]).get("source_representativity_gate_passed")
    )
    checks["latest_source_representativity_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_source_representativity is not False
    )
    latest_scope_representativity = _as_bool_or_none(_safe_obj(report["latest"]).get("scope_representativity_gate_passed"))
    checks["latest_scope_representativity_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_scope_representativity is not False
    )
    latest_source_dual_coverage = _as_bool_or_none(_safe_obj(report["latest"]).get("source_dual_coverage_gate_passed"))
    checks["latest_source_dual_coverage_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_source_dual_coverage is not False
    )
    latest_scope_dual_coverage = _as_bool_or_none(_safe_obj(report["latest"]).get("scope_dual_coverage_gate_passed"))
    checks["latest_scope_dual_coverage_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_scope_dual_coverage is not False
    )
    latest_accountability_primary_evidence = _as_bool_or_none(
        _safe_obj(report["latest"]).get("accountability_primary_evidence_gate_passed")
    )
    checks["latest_accountability_primary_evidence_gate_ok"] = (
        report["entries_in_window"] > 0
        and not bool(_safe_obj(report["latest"]).get("malformed_line"))
        and latest_accountability_primary_evidence is not False
    )

    reasons: list[str] = []
    if not checks["window_nonempty_ok"]:
        reasons.append("empty_window")
    if not checks["malformed_entries_ok"]:
        reasons.append("malformed_entries_present")
    if not checks["max_failed_ok"]:
        reasons.append("max_failed_exceeded")
    if not checks["max_failed_rate_ok"]:
        reasons.append("max_failed_rate_exceeded")
    if not checks["max_focus_gate_failed_ok"]:
        reasons.append("max_focus_gate_failed_exceeded")
    if not checks["max_focus_gate_failed_rate_ok"]:
        reasons.append("max_focus_gate_failed_rate_exceeded")
    if not checks["max_norms_classified_gate_failed_ok"]:
        reasons.append("max_norms_classified_gate_failed_exceeded")
    if not checks["max_fragments_irlc_gate_failed_ok"]:
        reasons.append("max_fragments_irlc_gate_failed_exceeded")
    if not checks["max_fragments_accountability_gate_failed_ok"]:
        reasons.append("max_fragments_accountability_gate_failed_exceeded")
    if not checks["max_rights_with_data_gate_failed_ok"]:
        reasons.append("max_rights_with_data_gate_failed_exceeded")
    if not checks["max_source_representativity_gate_failed_ok"]:
        reasons.append("max_source_representativity_gate_failed_exceeded")
    if not checks["max_scope_representativity_gate_failed_ok"]:
        reasons.append("max_scope_representativity_gate_failed_exceeded")
    if not checks["max_source_dual_coverage_gate_failed_ok"]:
        reasons.append("max_source_dual_coverage_gate_failed_exceeded")
    if not checks["max_scope_dual_coverage_gate_failed_ok"]:
        reasons.append("max_scope_dual_coverage_gate_failed_exceeded")
    if not checks["max_accountability_primary_evidence_gate_failed_ok"]:
        reasons.append("max_accountability_primary_evidence_gate_failed_exceeded")
    if not checks["latest_not_failed_ok"]:
        reasons.append("latest_status_failed")
    if not checks["latest_focus_gate_passed_ok"]:
        reasons.append("latest_focus_gate_failed")
    if not checks["latest_norms_classified_gate_ok"]:
        reasons.append("latest_norms_classified_gate_failed")
    if not checks["latest_fragments_irlc_gate_ok"]:
        reasons.append("latest_fragments_irlc_gate_failed")
    if not checks["latest_fragments_accountability_gate_ok"]:
        reasons.append("latest_fragments_accountability_gate_failed")
    if not checks["latest_rights_with_data_gate_ok"]:
        reasons.append("latest_rights_with_data_gate_failed")
    if not checks["latest_source_representativity_gate_ok"]:
        reasons.append("latest_source_representativity_gate_failed")
    if not checks["latest_scope_representativity_gate_ok"]:
        reasons.append("latest_scope_representativity_gate_failed")
    if not checks["latest_source_dual_coverage_gate_ok"]:
        reasons.append("latest_source_dual_coverage_gate_failed")
    if not checks["latest_scope_dual_coverage_gate_ok"]:
        reasons.append("latest_scope_dual_coverage_gate_failed")
    if not checks["latest_accountability_primary_evidence_gate_ok"]:
        reasons.append("latest_accountability_primary_evidence_gate_failed")
    report["strict_fail_reasons"] = reasons

    if report["entries_in_window"] == 0:
        report["status"] = "degraded"
    elif report["malformed_entries_in_window"] > 0:
        report["status"] = "failed"
    elif reasons:
        report["status"] = "failed"
    elif (
        report["degraded_in_window"] > 0
        or report["focus_gate_failed_in_window"] > 0
        or report["norms_classified_gate_failed_in_window"] > 0
        or report["fragments_irlc_gate_failed_in_window"] > 0
        or report["fragments_accountability_gate_failed_in_window"] > 0
        or report["rights_with_data_gate_failed_in_window"] > 0
        or report["source_representativity_gate_failed_in_window"] > 0
        or report["scope_representativity_gate_failed_in_window"] > 0
        or report["source_dual_coverage_gate_failed_in_window"] > 0
        or report["scope_dual_coverage_gate_failed_in_window"] > 0
        or report["accountability_primary_evidence_gate_failed_in_window"] > 0
    ):
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report


def build_window_report_from_path(
    heartbeat_path: Path,
    *,
    window_last: int = DEFAULT_LAST,
    max_failed: int = DEFAULT_MAX_FAILED,
    max_failed_rate_pct: float = DEFAULT_MAX_FAILED_RATE_PCT,
    max_focus_gate_failed: int = DEFAULT_MAX_FOCUS_GATE_FAILED,
    max_focus_gate_failed_rate_pct: float = DEFAULT_MAX_FOCUS_GATE_FAILED_RATE_PCT,
    max_norms_classified_gate_failed: int = DEFAULT_MAX_NORMS_CLASSIFIED_GATE_FAILED,
    max_fragments_irlc_gate_failed: int = DEFAULT_MAX_FRAGMENTS_IRLC_GATE_FAILED,
    max_fragments_accountability_gate_failed: int = DEFAULT_MAX_FRAGMENTS_ACCOUNTABILITY_GATE_FAILED,
    max_rights_with_data_gate_failed: int = DEFAULT_MAX_RIGHTS_WITH_DATA_GATE_FAILED,
    max_source_representativity_gate_failed: int = DEFAULT_MAX_SOURCE_REPRESENTATIVITY_GATE_FAILED,
    max_scope_representativity_gate_failed: int = DEFAULT_MAX_SCOPE_REPRESENTATIVITY_GATE_FAILED,
    max_source_dual_coverage_gate_failed: int = DEFAULT_MAX_SOURCE_DUAL_COVERAGE_GATE_FAILED,
    max_scope_dual_coverage_gate_failed: int = DEFAULT_MAX_SCOPE_DUAL_COVERAGE_GATE_FAILED,
    max_accountability_primary_evidence_gate_failed: int = DEFAULT_MAX_ACCOUNTABILITY_PRIMARY_EVIDENCE_GATE_FAILED,
    strict: bool = False,
) -> dict[str, Any]:
    rows = read_heartbeat_rows(heartbeat_path)
    return build_window_report(
        rows,
        window_last=window_last,
        max_failed=max_failed,
        max_failed_rate_pct=max_failed_rate_pct,
        max_focus_gate_failed=max_focus_gate_failed,
        max_focus_gate_failed_rate_pct=max_focus_gate_failed_rate_pct,
        max_norms_classified_gate_failed=max_norms_classified_gate_failed,
        max_fragments_irlc_gate_failed=max_fragments_irlc_gate_failed,
        max_fragments_accountability_gate_failed=max_fragments_accountability_gate_failed,
        max_rights_with_data_gate_failed=max_rights_with_data_gate_failed,
        max_source_representativity_gate_failed=max_source_representativity_gate_failed,
        max_scope_representativity_gate_failed=max_scope_representativity_gate_failed,
        max_source_dual_coverage_gate_failed=max_source_dual_coverage_gate_failed,
        max_scope_dual_coverage_gate_failed=max_scope_dual_coverage_gate_failed,
        max_accountability_primary_evidence_gate_failed=max_accountability_primary_evidence_gate_failed,
        strict=strict,
        heartbeat_path=str(heartbeat_path),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        report = build_window_report_from_path(
            Path(str(args.heartbeat_jsonl)),
            window_last=int(args.last),
            max_failed=int(args.max_failed),
            max_failed_rate_pct=float(args.max_failed_rate_pct),
            max_focus_gate_failed=int(args.max_focus_gate_failed),
            max_focus_gate_failed_rate_pct=float(args.max_focus_gate_failed_rate_pct),
            max_norms_classified_gate_failed=int(args.max_norms_classified_gate_failed),
            max_fragments_irlc_gate_failed=int(args.max_fragments_irlc_gate_failed),
            max_fragments_accountability_gate_failed=int(args.max_fragments_accountability_gate_failed),
            max_rights_with_data_gate_failed=int(args.max_rights_with_data_gate_failed),
            max_source_representativity_gate_failed=int(args.max_source_representativity_gate_failed),
            max_scope_representativity_gate_failed=int(args.max_scope_representativity_gate_failed),
            max_source_dual_coverage_gate_failed=int(args.max_source_dual_coverage_gate_failed),
            max_scope_dual_coverage_gate_failed=int(args.max_scope_dual_coverage_gate_failed),
            max_accountability_primary_evidence_gate_failed=int(
                args.max_accountability_primary_evidence_gate_failed
            ),
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

    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
