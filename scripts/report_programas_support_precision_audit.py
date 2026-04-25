#!/usr/bin/env python3
"""Build precision audit summary from a labeled programas support sample CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4
DEFAULT_REQUIRED_PARTIES = "BNG,VOX,FORO Asturias,PP"
TRUE_POSITIVE = "true_positive"
FALSE_POSITIVE = "false_positive"
VALID_LABELS = {TRUE_POSITIVE, FALSE_POSITIVE}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="sample_in", required=True, help="Input labeled sample CSV")
    parser.add_argument("--min-precision", type=float, default=0.90, help="Minimum precision threshold")
    parser.add_argument("--min-reviewed", type=int, default=30, help="Minimum labeled rows required")
    parser.add_argument(
        "--min-party-precision",
        type=float,
        default=0.0,
        help="Minimum precision per required party (0 disables this check)",
    )
    parser.add_argument(
        "--required-parties",
        default=DEFAULT_REQUIRED_PARTIES,
        help=f"CSV parties that must have at least one reviewed row (default: {DEFAULT_REQUIRED_PARTIES})",
    )
    parser.add_argument("--out", required=True, help="Output JSON summary path")
    parser.add_argument("--breakdown-out", default="", help="Optional party breakdown CSV output path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless status=ok")
    return parser.parse_args(argv)


def _parse_csv_list(raw: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = token.strip()
        if not item or item in seen:
            continue
        values.append(item)
        seen.add(item)
    return values


def _norm_label(raw: Any) -> str:
    return str(raw or "").strip().lower()


def _as_int(raw: Any) -> int | None:
    txt = str(raw or "").strip()
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def _write_breakdown_csv(path: Path, *, by_party: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["party_name", "sample_total", "true_positive", "false_positive", "precision"])
        for party in sorted(by_party.keys()):
            row = by_party[party]
            writer.writerow(
                [
                    party,
                    int(row["total"]),
                    int(row["tp"]),
                    int(row["fp"]),
                    f"{float(row['precision']):.4f}",
                ]
            )


def build_report(
    *,
    sample_path: Path,
    min_precision: float,
    min_reviewed: int,
    min_party_precision: float,
    required_parties: list[str],
) -> dict[str, Any]:
    with sample_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    reviewed = 0
    tp_total = 0
    fp_total = 0
    unlabeled = 0
    invalid_label_rows = 0
    false_positive_ids: list[int] = []
    by_party: dict[str, dict[str, Any]] = {}

    for row in rows:
        party = str(row.get("party_name") or "").strip()
        if not party:
            party = "unknown"
        if party not in by_party:
            by_party[party] = {"total": 0, "tp": 0, "fp": 0, "precision": 0.0}

        label = _norm_label(row.get("manual_label"))
        if not label:
            unlabeled += 1
            continue
        if label not in VALID_LABELS:
            invalid_label_rows += 1
            continue

        reviewed += 1
        by_party[party]["total"] = int(by_party[party]["total"]) + 1
        if label == TRUE_POSITIVE:
            tp_total += 1
            by_party[party]["tp"] = int(by_party[party]["tp"]) + 1
        else:
            fp_total += 1
            by_party[party]["fp"] = int(by_party[party]["fp"]) + 1
            maybe_id = _as_int(row.get("evidence_id"))
            if maybe_id is not None:
                false_positive_ids.append(maybe_id)

    for party in by_party:
        party_total = int(by_party[party]["total"])
        if party_total > 0:
            by_party[party]["precision"] = float(by_party[party]["tp"]) / float(party_total)
        else:
            by_party[party]["precision"] = 0.0

    precision = float(tp_total) / float(reviewed) if reviewed > 0 else 0.0
    reviewed_by_required = {party: int(by_party.get(party, {}).get("total", 0)) for party in required_parties}
    precision_by_required = {party: float(by_party.get(party, {}).get("precision", 0.0)) for party in required_parties}
    missing_required_parties = [party for party, c in reviewed_by_required.items() if int(c) <= 0]
    below_min_party_precision: list[dict[str, Any]] = []
    if float(min_party_precision) > 0.0:
        for party in required_parties:
            reviewed_party = int(reviewed_by_required.get(party, 0))
            if reviewed_party <= 0:
                continue
            precision_party = float(precision_by_required.get(party, 0.0))
            if precision_party < float(min_party_precision):
                below_min_party_precision.append(
                    {
                        "party_name": party,
                        "precision": precision_party,
                        "reviewed_total": reviewed_party,
                    }
                )
    checks = {
        "meets_min_reviewed": int(reviewed) >= int(max(0, min_reviewed)),
        "meets_precision_threshold": float(precision) >= float(min_precision),
        "required_parties_covered": len(missing_required_parties) == 0,
        "required_parties_min_precision": len(below_min_party_precision) == 0,
        "no_invalid_labels": int(invalid_label_rows) == 0,
    }
    status = "ok" if all(bool(v) for v in checks.values()) else "degraded"
    reasons: list[str] = []
    if not checks["meets_min_reviewed"]:
        reasons.append("min_reviewed_not_met")
    if not checks["meets_precision_threshold"]:
        reasons.append("precision_below_threshold")
    if not checks["required_parties_covered"]:
        reasons.append("missing_required_parties")
    if not checks["required_parties_min_precision"]:
        reasons.append("required_party_precision_below_threshold")
    if not checks["no_invalid_labels"]:
        reasons.append("invalid_manual_labels")

    return {
        "sample_file": str(sample_path),
        "sample_total": total,
        "reviewed_total": reviewed,
        "unlabeled_rows": unlabeled,
        "invalid_label_rows": invalid_label_rows,
        "true_positive": tp_total,
        "false_positive": fp_total,
        "precision": precision,
        "threshold": float(min_precision),
        "min_reviewed": int(min_reviewed),
        "min_party_precision": float(min_party_precision),
        "required_parties": required_parties,
        "reviewed_by_required_party": reviewed_by_required,
        "precision_by_required_party": precision_by_required,
        "missing_required_parties": missing_required_parties,
        "below_min_party_precision": below_min_party_precision,
        "false_positive_evidence_ids": sorted(set(false_positive_ids)),
        "by_party": by_party,
        "checks": checks,
        "status": status,
        "passed": status == "ok",
        "strict_fail_reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sample_path = Path(args.sample_in)
    out_path = Path(args.out)
    breakdown_out = Path(args.breakdown_out) if str(args.breakdown_out or "").strip() else None
    required_parties = _parse_csv_list(str(args.required_parties or ""))

    if not sample_path.exists():
        print(f"ERROR: sample CSV not found: {sample_path}")
        return 2

    report = build_report(
        sample_path=sample_path,
        min_precision=float(args.min_precision),
        min_reviewed=int(args.min_reviewed),
        min_party_precision=float(args.min_party_precision),
        required_parties=required_parties,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    if breakdown_out is not None:
        _write_breakdown_csv(breakdown_out, by_party=dict(report.get("by_party") or {}))
    print(json.dumps(report, ensure_ascii=True, indent=2))

    if bool(args.strict) and str(report.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
