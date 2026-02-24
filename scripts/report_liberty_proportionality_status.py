#!/usr/bin/env python3
"""Report status for liberty proportionality/necessity lane."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def build_status_report(
    conn: sqlite3.Connection,
    *,
    low_score_threshold: float = 50.0,
    target_coverage_min: float = 0.6,
    objective_defined_min: float = 0.8,
    indicator_defined_min: float = 0.6,
    alternatives_considered_min: float = 0.4,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_proportionality_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_proportionality_reviews) AS reviews_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_proportionality_reviews) AS fragments_with_reviews_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS target_fragments_total,
          (SELECT AVG(proportionality_score) FROM liberty_proportionality_reviews) AS proportionality_avg,
          (SELECT MIN(proportionality_score) FROM liberty_proportionality_reviews) AS proportionality_min,
          (SELECT MAX(proportionality_score) FROM liberty_proportionality_reviews) AS proportionality_max,
          (SELECT AVG(objective_defined) FROM liberty_proportionality_reviews) AS objective_defined_avg,
          (SELECT AVG(indicator_defined) FROM liberty_proportionality_reviews) AS indicator_defined_avg,
          (SELECT AVG(alternatives_less_restrictive_considered) FROM liberty_proportionality_reviews) AS alternatives_considered_avg,
          (SELECT AVG(sunset_review_present) FROM liberty_proportionality_reviews) AS sunset_present_avg
        """
    ).fetchone()

    reviews_total = int(totals["reviews_total"] or 0)
    fragments_with_reviews_total = int(totals["fragments_with_reviews_total"] or 0)
    target_fragments_total = int(totals["target_fragments_total"] or 0)

    by_label_rows = conn.execute(
        """
        SELECT assessment_label, COUNT(*) AS n
        FROM liberty_proportionality_reviews
        GROUP BY assessment_label
        ORDER BY n DESC, assessment_label ASC
        """
    ).fetchall()
    by_label = {_norm(r["assessment_label"]): int(r["n"]) for r in by_label_rows}

    low_score_rows = conn.execute(
        """
        SELECT
          p.review_key,
          p.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          p.proportionality_score,
          p.assessment_label
        FROM liberty_proportionality_reviews p
        JOIN legal_norm_fragments f ON f.fragment_id = p.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        WHERE p.proportionality_score < ?
        ORDER BY p.proportionality_score ASC, p.fragment_id ASC
        LIMIT 20
        """,
        (float(low_score_threshold),),
    ).fetchall()
    low_score_sample = [
        {
            "review_key": _norm(r["review_key"]),
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "norm_title": _norm(r["norm_title"]),
            "fragment_label": _norm(r["fragment_label"]),
            "proportionality_score": round(float(r["proportionality_score"] or 0.0), 6),
            "assessment_label": _norm(r["assessment_label"]),
        }
        for r in low_score_rows
    ]

    target_missing_rows = conn.execute(
        """
        SELECT
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(f.fragment_label, '') AS fragment_label
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_proportionality_reviews p ON p.fragment_id = a.fragment_id
        WHERE p.fragment_id IS NULL
        ORDER BY f.norm_id ASC, f.fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    target_missing_sample = [
        {
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "fragment_label": _norm(r["fragment_label"]),
        }
        for r in target_missing_rows
    ]

    coverage = {
        "target_fragments_coverage_pct": round((fragments_with_reviews_total / target_fragments_total), 6) if target_fragments_total else 0.0,
        "objective_defined_pct": round(float(totals["objective_defined_avg"] or 0.0), 6),
        "indicator_defined_pct": round(float(totals["indicator_defined_avg"] or 0.0), 6),
        "alternatives_considered_pct": round(float(totals["alternatives_considered_avg"] or 0.0), 6),
        "sunset_present_pct": round(float(totals["sunset_present_avg"] or 0.0), 6),
        "proportionality_score_avg": round(float(totals["proportionality_avg"] or 0.0), 6),
        "proportionality_score_min": round(float(totals["proportionality_min"] or 0.0), 6),
        "proportionality_score_max": round(float(totals["proportionality_max"] or 0.0), 6),
    }

    checks = {
        "proportionality_started": reviews_total > 0,
        "target_coverage_gate": coverage["target_fragments_coverage_pct"] >= float(target_coverage_min),
        "objective_defined_gate": coverage["objective_defined_pct"] >= float(objective_defined_min),
        "indicator_defined_gate": coverage["indicator_defined_pct"] >= float(indicator_defined_min),
        "alternatives_considered_gate": coverage["alternatives_considered_pct"] >= float(alternatives_considered_min),
    }
    gate_passed = all(
        checks[k]
        for k in (
            "target_coverage_gate",
            "objective_defined_gate",
            "indicator_defined_gate",
            "alternatives_considered_gate",
        )
    )

    if reviews_total == 0:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "methodologies_total": int(totals["methodologies_total"] or 0),
            "reviews_total": reviews_total,
            "fragments_with_reviews_total": fragments_with_reviews_total,
            "target_fragments_total": target_fragments_total,
            "reviews_below_threshold_total": len(low_score_sample),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "target_coverage_min": float(target_coverage_min),
                "objective_defined_min": float(objective_defined_min),
                "indicator_defined_min": float(indicator_defined_min),
                "alternatives_considered_min": float(alternatives_considered_min),
                "low_score_threshold": float(low_score_threshold),
            },
        },
        "by_assessment_label": by_label,
        "low_score_sample": low_score_sample,
        "target_missing_sample": target_missing_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report status for liberty proportionality lane")
    ap.add_argument("--db", required=True)
    ap.add_argument("--low-score-threshold", type=float, default=50.0)
    ap.add_argument("--target-coverage-min", type=float, default=0.6)
    ap.add_argument("--objective-defined-min", type=float, default=0.8)
    ap.add_argument("--indicator-defined-min", type=float, default=0.6)
    ap.add_argument("--alternatives-considered-min", type=float, default=0.4)
    ap.add_argument("--enforce-gate", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_status_report(
            conn,
            low_score_threshold=float(args.low_score_threshold),
            target_coverage_min=float(args.target_coverage_min),
            objective_defined_min=float(args.objective_defined_min),
            indicator_defined_min=float(args.indicator_defined_min),
            alternatives_considered_min=float(args.alternatives_considered_min),
        )
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if str(report.get("status")) == "failed":
        return 1
    if bool(args.enforce_gate) and not bool(report.get("gate", {}).get("passed")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
