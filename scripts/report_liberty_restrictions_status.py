#!/usr/bin/env python3
"""Report status for liberty restrictions lanes (IRLC + map + coverage + focus gate)."""

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
    top_n: int = 20,
    norms_classified_min: float = 0.8,
    fragments_irlc_min: float = 0.6,
    fragments_accountability_min: float = 0.6,
    rights_with_data_min: float = 1.0,
    sources_with_assessments_min_pct: float = 1.0,
    scopes_with_assessments_min_pct: float = 1.0,
    min_assessment_sources: int = 1,
    min_assessment_scopes: int = 1,
    sources_with_dual_coverage_min_pct: float = 1.0,
    scopes_with_dual_coverage_min_pct: float = 1.0,
    min_dual_coverage_sources: int = 1,
    min_dual_coverage_scopes: int = 1,
    accountability_primary_evidence_min_pct: float = 1.0,
    min_accountability_primary_evidence_edges: int = 1,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(DISTINCT norm_id) FROM legal_norm_fragments) AS norms_total,
          (SELECT COUNT(*) FROM legal_norm_fragments) AS fragments_total,
          (SELECT COUNT(*) FROM liberty_irlc_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_right_categories) AS right_categories_total,
          (SELECT COUNT(DISTINCT right_category_id) FROM liberty_restriction_assessments) AS right_categories_with_data_total,
          (SELECT COUNT(*) FROM liberty_restriction_assessments) AS assessments_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS fragments_with_irlc_total,
          (SELECT COUNT(DISTINCT f.norm_id)
             FROM legal_norm_fragments f
             JOIN liberty_restriction_assessments a ON a.fragment_id = f.fragment_id) AS norms_with_irlc_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM legal_fragment_responsibilities) AS fragments_with_accountability_total,
          (SELECT COUNT(DISTINCT a.fragment_id)
             FROM liberty_restriction_assessments a
             JOIN legal_fragment_responsibilities r ON r.fragment_id = a.fragment_id) AS fragments_with_dual_coverage_total,
          (SELECT COUNT(*) FROM legal_fragment_responsibilities) AS accountability_edges_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities
            WHERE COALESCE(TRIM(source_url), '') <> ''
              AND COALESCE(TRIM(evidence_date), '') <> ''
              AND COALESCE(TRIM(evidence_quote), '') <> '') AS accountability_edges_with_primary_evidence_total
        """
    ).fetchone()

    norms_total = int(totals["norms_total"] or 0)
    fragments_total = int(totals["fragments_total"] or 0)
    right_categories_total = int(totals["right_categories_total"] or 0)
    right_categories_with_data_total = int(totals["right_categories_with_data_total"] or 0)
    fragments_with_irlc_total = int(totals["fragments_with_irlc_total"] or 0)
    norms_with_irlc_total = int(totals["norms_with_irlc_total"] or 0)
    fragments_with_accountability_total = int(totals["fragments_with_accountability_total"] or 0)
    fragments_with_dual_coverage_total = int(totals["fragments_with_dual_coverage_total"] or 0)
    assessments_total = int(totals["assessments_total"] or 0)
    accountability_edges_total = int(totals["accountability_edges_total"] or 0)
    accountability_edges_with_primary_evidence_total = int(
        totals["accountability_edges_with_primary_evidence_total"] or 0
    )

    by_right_rows = conn.execute(
        """
        SELECT
          a.right_category_id,
          COALESCE(c.label, '') AS right_label,
          COUNT(*) AS assessments_total,
          COUNT(DISTINCT a.fragment_id) AS fragments_total,
          AVG(a.irlc_score) AS irlc_avg,
          MIN(a.irlc_score) AS irlc_min,
          MAX(a.irlc_score) AS irlc_max
        FROM liberty_restriction_assessments a
        LEFT JOIN liberty_right_categories c ON c.right_category_id = a.right_category_id
        GROUP BY a.right_category_id, c.label
        ORDER BY fragments_total DESC, a.right_category_id ASC
        """
    ).fetchall()
    by_right = [
        {
            "right_category_id": _norm(row["right_category_id"]),
            "right_label": _norm(row["right_label"]),
            "assessments_total": int(row["assessments_total"] or 0),
            "fragments_total": int(row["fragments_total"] or 0),
            "irlc_avg": round(float(row["irlc_avg"] or 0.0), 6),
            "irlc_min": round(float(row["irlc_min"] or 0.0), 6),
            "irlc_max": round(float(row["irlc_max"] or 0.0), 6),
        }
        for row in by_right_rows
    ]

    source_rows = conn.execute(
        """
        SELECT
          COALESCE(NULLIF(TRIM(n.source_id), ''), 'unknown') AS source_key,
          COUNT(DISTINCT n.norm_id) AS norms_total,
          COUNT(DISTINCT f.fragment_id) AS fragments_total,
          COUNT(DISTINCT CASE WHEN a.fragment_id IS NOT NULL THEN n.norm_id END) AS norms_with_irlc_total,
          COUNT(DISTINCT a.fragment_id) AS fragments_with_irlc_total,
          COUNT(DISTINCT CASE WHEN r.fragment_id IS NOT NULL THEN f.fragment_id END) AS fragments_with_accountability_total,
          COUNT(DISTINCT CASE WHEN a.fragment_id IS NOT NULL AND r.fragment_id IS NOT NULL THEN f.fragment_id END) AS fragments_with_dual_coverage_total,
          COUNT(DISTINCT CASE
            WHEN COALESCE(TRIM(r.source_url), '') <> ''
             AND COALESCE(TRIM(r.evidence_date), '') <> ''
             AND COALESCE(TRIM(r.evidence_quote), '') <> ''
            THEN f.fragment_id
          END) AS fragments_with_accountability_primary_evidence_total
        FROM legal_norm_fragments f
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_restriction_assessments a ON a.fragment_id = f.fragment_id
        LEFT JOIN legal_fragment_responsibilities r ON r.fragment_id = f.fragment_id
        GROUP BY source_key
        ORDER BY fragments_total DESC, source_key ASC
        """
    ).fetchall()
    coverage_by_source = [
        {
            "source_key": _norm(row["source_key"]) or "unknown",
            "norms_total": int(row["norms_total"] or 0),
            "norms_with_irlc_total": int(row["norms_with_irlc_total"] or 0),
            "norms_with_irlc_pct": (
                round(float(row["norms_with_irlc_total"] or 0) / float(row["norms_total"]), 6)
                if int(row["norms_total"] or 0) > 0
                else 0.0
            ),
            "fragments_total": int(row["fragments_total"] or 0),
            "fragments_with_irlc_total": int(row["fragments_with_irlc_total"] or 0),
            "fragments_with_irlc_pct": (
                round(float(row["fragments_with_irlc_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_accountability_total": int(row["fragments_with_accountability_total"] or 0),
            "fragments_with_accountability_pct": (
                round(float(row["fragments_with_accountability_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_accountability_primary_evidence_total": int(
                row["fragments_with_accountability_primary_evidence_total"] or 0
            ),
            "fragments_with_accountability_primary_evidence_pct": (
                round(
                    float(row["fragments_with_accountability_primary_evidence_total"] or 0)
                    / float(row["fragments_total"]),
                    6,
                )
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_dual_coverage_total": int(row["fragments_with_dual_coverage_total"] or 0),
            "fragments_with_dual_coverage_pct": (
                round(float(row["fragments_with_dual_coverage_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
        }
        for row in source_rows
    ]

    scope_rows = conn.execute(
        """
        SELECT
          COALESCE(NULLIF(TRIM(n.scope), ''), 'unknown') AS scope_key,
          COUNT(DISTINCT n.norm_id) AS norms_total,
          COUNT(DISTINCT f.fragment_id) AS fragments_total,
          COUNT(DISTINCT CASE WHEN a.fragment_id IS NOT NULL THEN n.norm_id END) AS norms_with_irlc_total,
          COUNT(DISTINCT a.fragment_id) AS fragments_with_irlc_total,
          COUNT(DISTINCT CASE WHEN r.fragment_id IS NOT NULL THEN f.fragment_id END) AS fragments_with_accountability_total,
          COUNT(DISTINCT CASE WHEN a.fragment_id IS NOT NULL AND r.fragment_id IS NOT NULL THEN f.fragment_id END) AS fragments_with_dual_coverage_total,
          COUNT(DISTINCT CASE
            WHEN COALESCE(TRIM(r.source_url), '') <> ''
             AND COALESCE(TRIM(r.evidence_date), '') <> ''
             AND COALESCE(TRIM(r.evidence_quote), '') <> ''
            THEN f.fragment_id
          END) AS fragments_with_accountability_primary_evidence_total
        FROM legal_norm_fragments f
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_restriction_assessments a ON a.fragment_id = f.fragment_id
        LEFT JOIN legal_fragment_responsibilities r ON r.fragment_id = f.fragment_id
        GROUP BY scope_key
        ORDER BY fragments_total DESC, scope_key ASC
        """
    ).fetchall()
    coverage_by_scope = [
        {
            "scope_key": _norm(row["scope_key"]) or "unknown",
            "norms_total": int(row["norms_total"] or 0),
            "norms_with_irlc_total": int(row["norms_with_irlc_total"] or 0),
            "norms_with_irlc_pct": (
                round(float(row["norms_with_irlc_total"] or 0) / float(row["norms_total"]), 6)
                if int(row["norms_total"] or 0) > 0
                else 0.0
            ),
            "fragments_total": int(row["fragments_total"] or 0),
            "fragments_with_irlc_total": int(row["fragments_with_irlc_total"] or 0),
            "fragments_with_irlc_pct": (
                round(float(row["fragments_with_irlc_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_accountability_total": int(row["fragments_with_accountability_total"] or 0),
            "fragments_with_accountability_pct": (
                round(float(row["fragments_with_accountability_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_accountability_primary_evidence_total": int(
                row["fragments_with_accountability_primary_evidence_total"] or 0
            ),
            "fragments_with_accountability_primary_evidence_pct": (
                round(
                    float(row["fragments_with_accountability_primary_evidence_total"] or 0)
                    / float(row["fragments_total"]),
                    6,
                )
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
            "fragments_with_dual_coverage_total": int(row["fragments_with_dual_coverage_total"] or 0),
            "fragments_with_dual_coverage_pct": (
                round(float(row["fragments_with_dual_coverage_total"] or 0) / float(row["fragments_total"]), 6)
                if int(row["fragments_total"] or 0) > 0
                else 0.0
            ),
        }
        for row in scope_rows
    ]

    sources_total = len(coverage_by_source)
    sources_with_assessments_total = sum(1 for row in coverage_by_source if int(row["fragments_with_irlc_total"]) > 0)
    scopes_total = len(coverage_by_scope)
    scopes_with_assessments_total = sum(1 for row in coverage_by_scope if int(row["fragments_with_irlc_total"]) > 0)
    sources_with_dual_coverage_total = sum(1 for row in coverage_by_source if int(row["fragments_with_dual_coverage_total"]) > 0)
    scopes_with_dual_coverage_total = sum(1 for row in coverage_by_scope if int(row["fragments_with_dual_coverage_total"]) > 0)

    top_rows = conn.execute(
        """
        SELECT
          a.assessment_key,
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          a.right_category_id,
          COALESCE(c.label, '') AS right_label,
          a.irlc_score,
          a.confidence
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_right_categories c ON c.right_category_id = a.right_category_id
        ORDER BY a.irlc_score DESC, a.confidence DESC, a.fragment_id ASC
        LIMIT ?
        """,
        (max(0, int(top_n)),),
    ).fetchall()
    top_restrictions = [
        {
            "assessment_key": _norm(row["assessment_key"]),
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_label": _norm(row["fragment_label"]),
            "right_category_id": _norm(row["right_category_id"]),
            "right_label": _norm(row["right_label"]),
            "irlc_score": round(float(row["irlc_score"] or 0.0), 6),
            "confidence": round(float(row["confidence"] or 0.0), 6) if row["confidence"] is not None else None,
        }
        for row in top_rows
    ]

    coverage = {
        "norms_classified_pct": round((norms_with_irlc_total / norms_total), 6) if norms_total else 0.0,
        "fragments_with_irlc_pct": round((fragments_with_irlc_total / fragments_total), 6) if fragments_total else 0.0,
        "fragments_with_accountability_pct": round((fragments_with_accountability_total / fragments_total), 6) if fragments_total else 0.0,
        "fragments_with_dual_coverage_pct": round((fragments_with_dual_coverage_total / fragments_total), 6) if fragments_total else 0.0,
        "accountability_edges_with_primary_evidence_pct": (
            round((accountability_edges_with_primary_evidence_total / accountability_edges_total), 6)
            if accountability_edges_total
            else 0.0
        ),
        "right_categories_with_data_pct": (
            round((right_categories_with_data_total / right_categories_total), 6) if right_categories_total else 0.0
        ),
        "sources_with_assessments_pct": round((sources_with_assessments_total / sources_total), 6) if sources_total else 0.0,
        "scopes_with_assessments_pct": round((scopes_with_assessments_total / scopes_total), 6) if scopes_total else 0.0,
        "sources_with_dual_coverage_pct": round((sources_with_dual_coverage_total / sources_total), 6) if sources_total else 0.0,
        "scopes_with_dual_coverage_pct": round((scopes_with_dual_coverage_total / scopes_total), 6) if scopes_total else 0.0,
    }

    checks = {
        "irlc_started": assessments_total > 0,
        "restriction_map_started": len(by_right) > 0,
        "norms_classified_gate": coverage["norms_classified_pct"] >= float(norms_classified_min),
        "fragments_irlc_gate": coverage["fragments_with_irlc_pct"] >= float(fragments_irlc_min),
        "fragments_accountability_gate": coverage["fragments_with_accountability_pct"] >= float(fragments_accountability_min),
        "rights_with_data_gate": coverage["right_categories_with_data_pct"] >= float(rights_with_data_min),
        "source_representativity_gate": (
            coverage["sources_with_assessments_pct"] >= float(sources_with_assessments_min_pct)
            and sources_with_assessments_total >= int(min_assessment_sources)
        ),
        "scope_representativity_gate": (
            coverage["scopes_with_assessments_pct"] >= float(scopes_with_assessments_min_pct)
            and scopes_with_assessments_total >= int(min_assessment_scopes)
        ),
        "source_dual_coverage_gate": (
            coverage["sources_with_dual_coverage_pct"] >= float(sources_with_dual_coverage_min_pct)
            and sources_with_dual_coverage_total >= int(min_dual_coverage_sources)
        ),
        "scope_dual_coverage_gate": (
            coverage["scopes_with_dual_coverage_pct"] >= float(scopes_with_dual_coverage_min_pct)
            and scopes_with_dual_coverage_total >= int(min_dual_coverage_scopes)
        ),
        "accountability_primary_evidence_gate": (
            coverage["accountability_edges_with_primary_evidence_pct"] >= float(accountability_primary_evidence_min_pct)
            and accountability_edges_with_primary_evidence_total >= int(min_accountability_primary_evidence_edges)
        ),
    }
    gate_passed = all(
        checks[k]
        for k in (
            "norms_classified_gate",
            "fragments_irlc_gate",
            "fragments_accountability_gate",
            "rights_with_data_gate",
            "source_representativity_gate",
            "scope_representativity_gate",
            "source_dual_coverage_gate",
            "scope_dual_coverage_gate",
            "accountability_primary_evidence_gate",
        )
    )

    if assessments_total == 0:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "norms_total": norms_total,
            "fragments_total": fragments_total,
            "methodologies_total": int(totals["methodologies_total"] or 0),
            "right_categories_total": right_categories_total,
            "right_categories_with_data_total": right_categories_with_data_total,
            "assessments_total": assessments_total,
            "norms_with_irlc_total": norms_with_irlc_total,
            "fragments_with_irlc_total": fragments_with_irlc_total,
            "fragments_with_accountability_total": fragments_with_accountability_total,
            "fragments_with_dual_coverage_total": fragments_with_dual_coverage_total,
            "accountability_edges_total": accountability_edges_total,
            "accountability_edges_with_primary_evidence_total": accountability_edges_with_primary_evidence_total,
            "sources_total": sources_total,
            "sources_with_assessments_total": sources_with_assessments_total,
            "scopes_total": scopes_total,
            "scopes_with_assessments_total": scopes_with_assessments_total,
            "sources_with_dual_coverage_total": sources_with_dual_coverage_total,
            "scopes_with_dual_coverage_total": scopes_with_dual_coverage_total,
        },
        "coverage": coverage,
        "checks": checks,
        "focus_gate": {
            "passed": gate_passed,
            "thresholds": {
                "norms_classified_min": float(norms_classified_min),
                "fragments_irlc_min": float(fragments_irlc_min),
                "fragments_accountability_min": float(fragments_accountability_min),
                "rights_with_data_min": float(rights_with_data_min),
                "sources_with_assessments_min_pct": float(sources_with_assessments_min_pct),
                "scopes_with_assessments_min_pct": float(scopes_with_assessments_min_pct),
                "min_assessment_sources": int(min_assessment_sources),
                "min_assessment_scopes": int(min_assessment_scopes),
                "sources_with_dual_coverage_min_pct": float(sources_with_dual_coverage_min_pct),
                "scopes_with_dual_coverage_min_pct": float(scopes_with_dual_coverage_min_pct),
                "min_dual_coverage_sources": int(min_dual_coverage_sources),
                "min_dual_coverage_scopes": int(min_dual_coverage_scopes),
                "accountability_primary_evidence_min_pct": float(accountability_primary_evidence_min_pct),
                "min_accountability_primary_evidence_edges": int(min_accountability_primary_evidence_edges),
            },
        },
        "coverage_by_source": coverage_by_source,
        "coverage_by_scope": coverage_by_scope,
        "restriction_map_by_right": by_right,
        "top_restrictions": top_restrictions,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report status for liberty restrictions lanes")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--norms-classified-min", type=float, default=0.8)
    ap.add_argument("--fragments-irlc-min", type=float, default=0.6)
    ap.add_argument("--fragments-accountability-min", type=float, default=0.6)
    ap.add_argument("--rights-with-data-min", type=float, default=1.0)
    ap.add_argument("--sources-with-assessments-min-pct", type=float, default=1.0)
    ap.add_argument("--scopes-with-assessments-min-pct", type=float, default=1.0)
    ap.add_argument("--min-assessment-sources", type=int, default=1)
    ap.add_argument("--min-assessment-scopes", type=int, default=1)
    ap.add_argument("--sources-with-dual-coverage-min-pct", type=float, default=1.0)
    ap.add_argument("--scopes-with-dual-coverage-min-pct", type=float, default=1.0)
    ap.add_argument("--min-dual-coverage-sources", type=int, default=1)
    ap.add_argument("--min-dual-coverage-scopes", type=int, default=1)
    ap.add_argument("--accountability-primary-evidence-min-pct", type=float, default=1.0)
    ap.add_argument("--min-accountability-primary-evidence-edges", type=int, default=1)
    ap.add_argument("--enforce-gate", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_status_report(
            conn,
            top_n=int(args.top_n),
            norms_classified_min=float(args.norms_classified_min),
            fragments_irlc_min=float(args.fragments_irlc_min),
            fragments_accountability_min=float(args.fragments_accountability_min),
            rights_with_data_min=float(args.rights_with_data_min),
            sources_with_assessments_min_pct=float(args.sources_with_assessments_min_pct),
            scopes_with_assessments_min_pct=float(args.scopes_with_assessments_min_pct),
            min_assessment_sources=int(args.min_assessment_sources),
            min_assessment_scopes=int(args.min_assessment_scopes),
            sources_with_dual_coverage_min_pct=float(args.sources_with_dual_coverage_min_pct),
            scopes_with_dual_coverage_min_pct=float(args.scopes_with_dual_coverage_min_pct),
            min_dual_coverage_sources=int(args.min_dual_coverage_sources),
            min_dual_coverage_scopes=int(args.min_dual_coverage_scopes),
            accountability_primary_evidence_min_pct=float(args.accountability_primary_evidence_min_pct),
            min_accountability_primary_evidence_edges=int(args.min_accountability_primary_evidence_edges),
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
    if bool(args.enforce_gate) and not bool(report.get("focus_gate", {}).get("passed")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
