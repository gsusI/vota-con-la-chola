#!/usr/bin/env python3
"""Report observed precision from manual QA decisions on delegated auto-review rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

STRICT_FAIL_EXIT = 4
ALLOWED_DECISIONS = {"", "confirm", "reject", "skip", "pending"}
ALLOWED_DECISION_SCOPE = {"all", "approved"}


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


def _pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return round((float(numer) / float(denom)) * 100.0, 4)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _decision(value: Any) -> str:
    return _norm(value).lower()


def _institution(value: Any) -> str:
    token = _norm(value)
    return token if token else "(sin_institucion)"


def build_precision_report(
    *,
    qa_rows: list[dict[str, str]],
    min_reviewed_rows: int,
    min_precision_pct: float,
    decision_scope: str,
    strict: bool,
) -> dict[str, Any]:
    if int(min_reviewed_rows) < 0:
        raise ValueError("min_reviewed_rows must be >= 0")
    if float(min_precision_pct) < 0.0:
        raise ValueError("min_precision_pct must be >= 0")
    scope = _decision(decision_scope) or "approved"
    if scope not in ALLOWED_DECISION_SCOPE:
        raise ValueError(f"decision_scope must be one of: {sorted(ALLOWED_DECISION_SCOPE)}")

    by_institution: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "rows_total": 0,
            "reviewed_rows_total": 0,
            "confirm_total": 0,
            "reject_total": 0,
            "skip_or_pending_total": 0,
            "invalid_decision_total": 0,
        }
    )

    confirm_total = 0
    reject_total = 0
    reviewed_total = 0
    skip_or_pending_total = 0
    invalid_decision_total = 0
    invalid_decision_samples: list[dict[str, str]] = []
    rows_excluded_by_scope_total = 0
    rows_in_scope_total = 0

    for row in qa_rows:
        auto_decision = _decision(row.get("auto_decision") or "approved")
        in_scope = bool(scope == "all" or auto_decision == "approved")
        if not in_scope:
            rows_excluded_by_scope_total += 1
            continue
        rows_in_scope_total += 1

        inst = _institution(row.get("delegated_institution_label") or row.get("qa_stratum_institution"))
        stats = by_institution[inst]
        stats["rows_total"] += 1

        decision = _decision(row.get("qa_decision"))
        if decision not in ALLOWED_DECISIONS:
            invalid_decision_total += 1
            stats["invalid_decision_total"] += 1
            if len(invalid_decision_samples) < 5:
                invalid_decision_samples.append(
                    {
                        "link_key": _norm(row.get("link_key")),
                        "qa_decision": _norm(row.get("qa_decision")),
                    }
                )
            continue

        if decision in {"confirm", "reject"}:
            reviewed_total += 1
            stats["reviewed_rows_total"] += 1
            if decision == "confirm":
                confirm_total += 1
                stats["confirm_total"] += 1
            else:
                reject_total += 1
                stats["reject_total"] += 1
        else:
            skip_or_pending_total += 1
            stats["skip_or_pending_total"] += 1

    observed_precision_pct = _pct(confirm_total, reviewed_total)

    institution_breakdown: list[dict[str, Any]] = []
    for key in sorted(by_institution.keys()):
        stats = by_institution[key]
        inst_reviewed = int(stats["reviewed_rows_total"])
        inst_confirm = int(stats["confirm_total"])
        institution_breakdown.append(
            {
                "institution": key,
                "rows_total": int(stats["rows_total"]),
                "reviewed_rows_total": inst_reviewed,
                "confirm_total": inst_confirm,
                "reject_total": int(stats["reject_total"]),
                "skip_or_pending_total": int(stats["skip_or_pending_total"]),
                "invalid_decision_total": int(stats["invalid_decision_total"]),
                "observed_precision_pct": _pct(inst_confirm, inst_reviewed),
            }
        )

    strict_fail_reasons: list[str] = []
    if reviewed_total < int(min_reviewed_rows):
        strict_fail_reasons.append("reviewed_rows_below_min")
    if observed_precision_pct < float(min_precision_pct):
        strict_fail_reasons.append("precision_below_min")
    if invalid_decision_total > 0:
        strict_fail_reasons.append("invalid_qa_decisions")

    status = "ok" if not strict_fail_reasons else "degraded"
    report: dict[str, Any] = {
        "status": status,
        "strict": bool(strict),
        "decision_scope": scope,
        "thresholds": {
            "min_reviewed_rows": int(min_reviewed_rows),
            "min_precision_pct": float(min_precision_pct),
        },
        "rows_total": len(qa_rows),
        "rows_in_scope_total": rows_in_scope_total,
        "rows_excluded_by_scope_total": rows_excluded_by_scope_total,
        "reviewed_rows_total": reviewed_total,
        "confirm_total": confirm_total,
        "reject_total": reject_total,
        "skip_or_pending_total": skip_or_pending_total,
        "invalid_decision_total": invalid_decision_total,
        "observed_precision_pct": observed_precision_pct,
        "institution_breakdown": institution_breakdown,
        "invalid_decision_samples": invalid_decision_samples,
        "strict_fail_reasons": strict_fail_reasons,
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--qa-csv",
        default="docs/etl/sprints/AI-OPS-284/exports/liberty_delegated_person_window_auto_review_qa_sample_latest.csv",
    )
    ap.add_argument("--min-reviewed-rows", type=int, default=8)
    ap.add_argument("--min-precision-pct", type=float, default=0.0)
    ap.add_argument("--decision-scope", choices=sorted(ALLOWED_DECISION_SCOPE), default="approved")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    qa_rows = _read_csv(Path(args.qa_csv))
    report = build_precision_report(
        qa_rows=qa_rows,
        min_reviewed_rows=_to_int(args.min_reviewed_rows),
        min_precision_pct=_to_float(args.min_precision_pct),
        decision_scope=_norm(args.decision_scope),
        strict=bool(args.strict),
    )

    payload = {
        "qa_csv": _norm(args.qa_csv),
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
