#!/usr/bin/env python3
"""Report indirect accountability chain status for liberty restrictions."""

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
    attributable_confidence_min: float = 0.55,
    attributable_max_causal_distance: int = 2,
    attributable_fragment_coverage_min: float = 0.5,
    attributable_person_window_min: float = 1.0,
    min_attributable_edges_for_person_window: int = 1,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_indirect_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_indirect_responsibility_edges) AS edges_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_indirect_responsibility_edges) AS fragments_with_edges_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS target_fragments_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges
            WHERE edge_confidence >= ?
              AND causal_distance <= ?) AS attributable_edges_total,
          (SELECT COUNT(DISTINCT fragment_id)
             FROM liberty_indirect_responsibility_edges
            WHERE edge_confidence >= ?
              AND causal_distance <= ?) AS fragments_with_attributable_edges_total,
          (SELECT COUNT(DISTINCT r.fragment_id)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
            WHERE r.role IN ('propose','approve','enforce')) AS direct_fragments_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges
            WHERE edge_confidence >= ?
              AND causal_distance > ?) AS high_confidence_far_edges_total
          ,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges
            WHERE edge_confidence >= ?
              AND causal_distance <= ?
              AND TRIM(COALESCE(actor_person_name, '')) <> ''
              AND TRIM(COALESCE(actor_role_title, '')) <> ''
              AND TRIM(COALESCE(appointment_start_date, '')) <> '') AS attributable_edges_with_actor_person_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges
            WHERE edge_confidence >= ?
              AND causal_distance <= ?
              AND TRIM(COALESCE(actor_person_name, '')) <> ''
              AND TRIM(COALESCE(actor_role_title, '')) <> ''
              AND TRIM(COALESCE(appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(appointment_end_date, '')) = ''
                    OR date(appointment_end_date) >= date(appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(evidence_date, '')) = ''
                    OR date(evidence_date) >= date(appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(evidence_date, '')) = ''
                    OR date(evidence_date) <= date(appointment_end_date)
              )) AS attributable_edges_with_valid_person_window_total
        """,
        (
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
        ),
    ).fetchone()

    attributable_rows = conn.execute(
        """
        SELECT
          e.edge_key,
          e.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          e.actor_label,
          COALESCE(e.actor_person_name, '') AS actor_person_name,
          COALESCE(e.actor_role_title, '') AS actor_role_title,
          e.role,
          COALESCE(e.direct_actor_label, '') AS direct_actor_label,
          COALESCE(e.appointment_start_date, '') AS appointment_start_date,
          COALESCE(e.appointment_end_date, '') AS appointment_end_date,
          e.causal_distance,
          e.edge_confidence,
          COALESCE(e.evidence_date, '') AS evidence_date,
          COALESCE(e.source_url, '') AS source_url
        FROM liberty_indirect_responsibility_edges e
        JOIN legal_norm_fragments f ON f.fragment_id = e.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        WHERE e.edge_confidence >= ?
          AND e.causal_distance <= ?
        ORDER BY e.edge_confidence DESC, e.causal_distance ASC, e.fragment_id ASC
        LIMIT ?
        """,
        (
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            max(0, int(top_n)),
        ),
    ).fetchall()

    attributable_sample = [
        {
            "edge_key": _norm(r["edge_key"]),
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "norm_title": _norm(r["norm_title"]),
            "fragment_label": _norm(r["fragment_label"]),
            "actor_label": _norm(r["actor_label"]),
            "actor_person_name": _norm(r["actor_person_name"]),
            "actor_role_title": _norm(r["actor_role_title"]),
            "role": _norm(r["role"]),
            "direct_actor_label": _norm(r["direct_actor_label"]),
            "appointment_start_date": _norm(r["appointment_start_date"]),
            "appointment_end_date": _norm(r["appointment_end_date"]),
            "causal_distance": int(r["causal_distance"] or 0),
            "edge_confidence": float(r["edge_confidence"] or 0.0),
            "evidence_date": _norm(r["evidence_date"]),
            "source_url": _norm(r["source_url"]),
        }
        for r in attributable_rows
    ]

    excluded_rows = conn.execute(
        """
        SELECT
          e.edge_key,
          e.fragment_id,
          e.actor_label,
          COALESCE(e.actor_person_name, '') AS actor_person_name,
          COALESCE(e.actor_role_title, '') AS actor_role_title,
          e.role,
          COALESCE(e.direct_actor_label, '') AS direct_actor_label,
          COALESCE(e.appointment_start_date, '') AS appointment_start_date,
          COALESCE(e.appointment_end_date, '') AS appointment_end_date,
          e.causal_distance,
          e.edge_confidence,
          CASE
            WHEN e.edge_confidence < ? THEN 'low_confidence'
            WHEN e.causal_distance > ? THEN 'causal_distance_exceeds_max'
            ELSE 'excluded'
          END AS exclusion_reason
        FROM liberty_indirect_responsibility_edges e
        WHERE e.edge_confidence < ?
           OR e.causal_distance > ?
        ORDER BY e.edge_confidence ASC, e.causal_distance DESC, e.edge_key ASC
        LIMIT ?
        """,
        (
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            float(attributable_confidence_min),
            int(attributable_max_causal_distance),
            max(0, int(top_n)),
        ),
    ).fetchall()
    excluded_sample = [
        {
            "edge_key": _norm(r["edge_key"]),
            "fragment_id": _norm(r["fragment_id"]),
            "actor_label": _norm(r["actor_label"]),
            "actor_person_name": _norm(r["actor_person_name"]),
            "actor_role_title": _norm(r["actor_role_title"]),
            "role": _norm(r["role"]),
            "direct_actor_label": _norm(r["direct_actor_label"]),
            "appointment_start_date": _norm(r["appointment_start_date"]),
            "appointment_end_date": _norm(r["appointment_end_date"]),
            "causal_distance": int(r["causal_distance"] or 0),
            "edge_confidence": float(r["edge_confidence"] or 0.0),
            "exclusion_reason": _norm(r["exclusion_reason"]),
        }
        for r in excluded_rows
    ]

    missing_rows = conn.execute(
        """
        SELECT
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(f.fragment_label, '') AS fragment_label
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_indirect_responsibility_edges e ON e.fragment_id = a.fragment_id
        WHERE e.fragment_id IS NULL
        ORDER BY f.norm_id ASC, a.fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    missing_sample = [
        {
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "fragment_label": _norm(r["fragment_label"]),
        }
        for r in missing_rows
    ]

    target_fragments_total = int(totals["target_fragments_total"] or 0)
    fragments_with_attributable_edges_total = int(totals["fragments_with_attributable_edges_total"] or 0)
    direct_fragments_total = int(totals["direct_fragments_total"] or 0)

    coverage = {
        "target_fragment_coverage_pct": round(
            (int(totals["fragments_with_edges_total"] or 0) / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "attributable_fragment_coverage_pct": round(
            (fragments_with_attributable_edges_total / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "attributable_edges_pct": round(
            (int(totals["attributable_edges_total"] or 0) / int(totals["edges_total"] or 1)) if int(totals["edges_total"] or 0) > 0 else 0.0,
            6,
        ),
        "attributable_edges_with_actor_person_pct": round(
            (int(totals["attributable_edges_with_actor_person_total"] or 0) / int(totals["attributable_edges_total"] or 1))
            if int(totals["attributable_edges_total"] or 0) > 0
            else 0.0,
            6,
        ),
        "attributable_edges_with_valid_person_window_pct": round(
            (int(totals["attributable_edges_with_valid_person_window_total"] or 0) / int(totals["attributable_edges_total"] or 1))
            if int(totals["attributable_edges_total"] or 0) > 0
            else 0.0,
            6,
        ),
        "direct_and_indirect_overlap_pct": round(
            (fragments_with_attributable_edges_total / direct_fragments_total) if direct_fragments_total else 0.0,
            6,
        ),
    }

    checks = {
        "indirect_chain_started": int(totals["edges_total"] or 0) > 0,
        "attributable_filter_applied": True,
        "attributable_fragment_gate": coverage["attributable_fragment_coverage_pct"] >= float(attributable_fragment_coverage_min),
        "anti_overattribution_guard": int(totals["high_confidence_far_edges_total"] or 0) == 0,
        "indirect_person_window_gate": (
            int(totals["attributable_edges_total"] or 0) >= int(min_attributable_edges_for_person_window)
            and coverage["attributable_edges_with_valid_person_window_pct"] >= float(attributable_person_window_min)
        ),
    }
    gate_passed = checks["attributable_fragment_gate"] and checks["anti_overattribution_guard"] and checks["indirect_person_window_gate"]

    if int(totals["edges_total"] or 0) == 0:
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
            "edges_total": int(totals["edges_total"] or 0),
            "fragments_with_edges_total": int(totals["fragments_with_edges_total"] or 0),
            "target_fragments_total": target_fragments_total,
            "attributable_edges_total": int(totals["attributable_edges_total"] or 0),
            "fragments_with_attributable_edges_total": fragments_with_attributable_edges_total,
            "direct_fragments_total": direct_fragments_total,
            "high_confidence_far_edges_total": int(totals["high_confidence_far_edges_total"] or 0),
            "attributable_edges_with_actor_person_total": int(totals["attributable_edges_with_actor_person_total"] or 0),
            "attributable_edges_with_valid_person_window_total": int(totals["attributable_edges_with_valid_person_window_total"] or 0),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "attributable_confidence_min": float(attributable_confidence_min),
                "attributable_max_causal_distance": int(attributable_max_causal_distance),
                "attributable_fragment_coverage_min": float(attributable_fragment_coverage_min),
                "attributable_person_window_min": float(attributable_person_window_min),
                "min_attributable_edges_for_person_window": int(min_attributable_edges_for_person_window),
            },
        },
        "attributable_edges_sample": attributable_sample,
        "excluded_edges_sample": excluded_sample,
        "missing_fragment_sample": missing_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report indirect accountability chain status")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--attributable-confidence-min", type=float, default=0.55)
    ap.add_argument("--attributable-max-causal-distance", type=int, default=2)
    ap.add_argument("--attributable-fragment-coverage-min", type=float, default=0.5)
    ap.add_argument("--attributable-person-window-min", type=float, default=1.0)
    ap.add_argument("--min-attributable-edges-for-person-window", type=int, default=1)
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
            attributable_confidence_min=float(args.attributable_confidence_min),
            attributable_max_causal_distance=int(args.attributable_max_causal_distance),
            attributable_fragment_coverage_min=float(args.attributable_fragment_coverage_min),
            attributable_person_window_min=float(args.attributable_person_window_min),
            min_attributable_edges_for_person_window=int(args.min_attributable_edges_for_person_window),
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
