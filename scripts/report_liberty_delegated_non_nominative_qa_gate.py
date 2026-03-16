#!/usr/bin/env python3
"""Gate non-nominative delegated fallback approvals on focused manual QA evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value or "").strip())
    except Exception:
        return float(default)


def _load_json(path: Path | None) -> Any:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_metric(payload: Any, key: str, default: Any) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload.get(key)
        for container in ("summary", "report"):
            nested = payload.get(container)
            if isinstance(nested, dict) and key in nested:
                return nested.get(key)
    return default


def _contains_casefold(value: str, needle: str) -> bool:
    left = _norm(value).casefold()
    right = _norm(needle).casefold()
    if not right:
        return True
    return right in left


def _csv_matches_or_review_variant(*, expected_csv: str, actual_csv: str) -> bool:
    expected = _norm(expected_csv)
    actual = _norm(actual_csv)
    if not expected or not actual:
        return False
    if actual == expected:
        return True
    expected_name = Path(expected).name
    actual_name = Path(actual).name
    if actual_name.replace("_reviewed", "") == expected_name:
        return True
    return False


def build_report(
    *,
    auto_review_payload: Any,
    qa_sample_summary_payload: Any,
    qa_precision_payload: Any,
    review_note_contains: str,
    min_reviewed_rows: int,
    min_precision_pct: float,
) -> dict[str, Any]:
    if int(min_reviewed_rows) < 0:
        raise ValueError("min_reviewed_rows must be >= 0")
    if float(min_precision_pct) < 0:
        raise ValueError("min_precision_pct must be >= 0")

    approved_fallback_total = _to_int(
        _extract_metric(auto_review_payload, "approved_with_non_nominative_actor_fallback_total", 0),
        default=0,
    )
    qa_required = approved_fallback_total > 0

    sample_present = bool(qa_sample_summary_payload)
    precision_present = bool(qa_precision_payload)

    sample_rows_total = _to_int(_extract_metric(qa_sample_summary_payload, "sample_rows_total", 0), default=0)
    sample_review_note_contains = _norm(_extract_metric(qa_sample_summary_payload, "review_note_contains", ""))
    sample_auto_review_csv = _norm(_extract_metric(qa_sample_summary_payload, "auto_review_csv", ""))
    sample_out_csv = _norm(_extract_metric(qa_sample_summary_payload, "out_csv", ""))
    reviewed_rows_total = _to_int(_extract_metric(qa_precision_payload, "reviewed_rows_total", 0), default=0)
    observed_precision_pct = _to_float(_extract_metric(qa_precision_payload, "observed_precision_pct", 0.0), default=0.0)
    precision_status = _norm(_extract_metric(qa_precision_payload, "status", ""))
    precision_strict_fail_reasons = _extract_metric(qa_precision_payload, "strict_fail_reasons", [])
    precision_qa_csv = _norm(_extract_metric(qa_precision_payload, "qa_csv", ""))
    auto_review_out_csv = _norm(_extract_metric(auto_review_payload, "out_csv", ""))
    if not isinstance(precision_strict_fail_reasons, list):
        precision_strict_fail_reasons = []

    checks = {
        "qa_required": qa_required,
        "qa_sample_summary_present": (not qa_required) or sample_present,
        "qa_precision_report_present": (not qa_required) or precision_present,
        "qa_sample_has_rows": (not qa_required) or (sample_rows_total > 0),
        "qa_sample_review_note_filter_matches": (not qa_required)
        or _contains_casefold(sample_review_note_contains, review_note_contains),
        "qa_sample_matches_auto_review_csv": (not qa_required)
        or (not auto_review_out_csv)
        or bool(sample_auto_review_csv == auto_review_out_csv),
        "qa_precision_matches_sample_csv": (not qa_required)
        or (not sample_out_csv)
        or _csv_matches_or_review_variant(expected_csv=sample_out_csv, actual_csv=precision_qa_csv),
        "qa_reviewed_rows_meet_min": (not qa_required) or (reviewed_rows_total >= int(min_reviewed_rows)),
        "qa_precision_meets_min": (not qa_required) or (observed_precision_pct >= float(min_precision_pct)),
        "qa_precision_report_status_ok": (not qa_required) or (precision_status == "ok"),
    }

    strict_fail_reasons: list[str] = []
    if qa_required:
        if not checks["qa_sample_summary_present"]:
            strict_fail_reasons.append("missing_qa_sample_summary")
        if not checks["qa_precision_report_present"]:
            strict_fail_reasons.append("missing_qa_precision_report")
        if checks["qa_sample_summary_present"] and not checks["qa_sample_has_rows"]:
            strict_fail_reasons.append("qa_sample_empty")
        if checks["qa_sample_summary_present"] and not checks["qa_sample_review_note_filter_matches"]:
            strict_fail_reasons.append("qa_sample_review_note_filter_mismatch")
        if checks["qa_sample_summary_present"] and not checks["qa_sample_matches_auto_review_csv"]:
            strict_fail_reasons.append("qa_sample_not_linked_to_auto_review")
        if checks["qa_precision_report_present"] and not checks["qa_precision_matches_sample_csv"]:
            strict_fail_reasons.append("qa_precision_not_linked_to_sample")
        if checks["qa_precision_report_present"] and not checks["qa_reviewed_rows_meet_min"]:
            strict_fail_reasons.append("qa_reviewed_rows_below_min")
        if checks["qa_precision_report_present"] and not checks["qa_precision_meets_min"]:
            strict_fail_reasons.append("qa_precision_below_min")
        if checks["qa_precision_report_present"] and not checks["qa_precision_report_status_ok"]:
            strict_fail_reasons.append("qa_precision_report_not_ok")

    status = "ok" if not strict_fail_reasons else "degraded"
    return {
        "status": status,
        "approved_with_non_nominative_actor_fallback_total": approved_fallback_total,
        "qa_required": qa_required,
        "thresholds": {
            "review_note_contains": _norm(review_note_contains),
            "min_reviewed_rows": int(min_reviewed_rows),
            "min_precision_pct": float(min_precision_pct),
        },
        "qa_sample": {
            "present": sample_present,
            "sample_rows_total": sample_rows_total,
            "review_note_contains": sample_review_note_contains,
            "auto_review_csv": sample_auto_review_csv,
            "out_csv": sample_out_csv,
        },
        "qa_precision": {
            "present": precision_present,
            "status": precision_status,
            "qa_csv": precision_qa_csv,
            "reviewed_rows_total": reviewed_rows_total,
            "observed_precision_pct": observed_precision_pct,
            "strict_fail_reasons": precision_strict_fail_reasons,
        },
        "auto_review_out_csv": auto_review_out_csv,
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--auto-review-summary",
        default="docs/etl/sprints/AI-OPS-293/evidence/liberty_delegated_person_window_auto_review_decisions_alternative_latest.json",
    )
    ap.add_argument(
        "--qa-sample-summary",
        default="",
        help="Optional JSON output from export_liberty_delegated_person_window_auto_review_qa_sample.py",
    )
    ap.add_argument(
        "--qa-precision-report",
        default="",
        help="Optional JSON output from report_liberty_delegated_person_window_auto_review_qa_precision.py",
    )
    ap.add_argument("--review-note-contains", default="approved_non_nominative_unit")
    ap.add_argument("--min-reviewed-rows", type=int, default=1)
    ap.add_argument("--min-precision-pct", type=float, default=100.0)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    auto_review_summary = Path(args.auto_review_summary)
    qa_sample_summary = Path(args.qa_sample_summary) if _norm(args.qa_sample_summary) else None
    qa_precision_report = Path(args.qa_precision_report) if _norm(args.qa_precision_report) else None

    auto_payload = _load_json(auto_review_summary)
    sample_payload = _load_json(qa_sample_summary) if qa_sample_summary and qa_sample_summary.exists() else {}
    precision_payload = _load_json(qa_precision_report) if qa_precision_report and qa_precision_report.exists() else {}

    report = build_report(
        auto_review_payload=auto_payload,
        qa_sample_summary_payload=sample_payload,
        qa_precision_payload=precision_payload,
        review_note_contains=_norm(args.review_note_contains),
        min_reviewed_rows=_to_int(args.min_reviewed_rows),
        min_precision_pct=_to_float(args.min_precision_pct),
    )
    payload = {
        "auto_review_summary": _norm(args.auto_review_summary),
        "qa_sample_summary": _norm(args.qa_sample_summary),
        "qa_precision_report": _norm(args.qa_precision_report),
        "report": report,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if bool(args.strict) and report.get("strict_fail_reasons"):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
