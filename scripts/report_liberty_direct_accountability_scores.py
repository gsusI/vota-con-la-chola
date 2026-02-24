#!/usr/bin/env python3
"""Report direct accountability coverage and responsibility_score for restrictions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db


DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "propose": 0.25,
    "approve": 0.30,
    "delegate": 0.15,
    "enforce": 0.25,
    "audit": 0.05,
}
DIRECT_ROLES = ("propose", "approve", "enforce")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _role_weights_json(weights: dict[str, float]) -> str:
    return json.dumps(weights, ensure_ascii=False, sort_keys=True)


def build_status_report(
    conn: sqlite3.Connection,
    *,
    top_n: int = 20,
    direct_coverage_min: float = 0.6,
    direct_primary_evidence_min_pct: float = 1.0,
    min_direct_primary_evidence_edges: int = 1,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS fragments_with_irlc_total,
          (SELECT COUNT(DISTINCT r.fragment_id)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id) AS fragments_with_any_accountability_total,
          (SELECT COUNT(DISTINCT r.fragment_id)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
            WHERE r.role IN ('propose','approve','enforce')) AS fragments_with_direct_chain_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id) AS accountability_edges_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
            WHERE r.role IN ('propose','approve','enforce')) AS direct_edges_total
          ,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
            WHERE r.role IN ('propose','approve','enforce')
              AND COALESCE(TRIM(r.source_url), '') <> ''
              AND COALESCE(TRIM(r.evidence_date), '') <> ''
              AND COALESCE(TRIM(r.evidence_quote), '') <> '') AS direct_edges_with_primary_evidence_total
        """
    ).fetchone()

    fragments_with_irlc_total = int(totals["fragments_with_irlc_total"] or 0)
    fragments_with_direct_chain_total = int(totals["fragments_with_direct_chain_total"] or 0)
    accountability_edges_total = int(totals["accountability_edges_total"] or 0)
    direct_edges_total = int(totals["direct_edges_total"] or 0)
    direct_edges_with_primary_evidence_total = int(totals["direct_edges_with_primary_evidence_total"] or 0)

    weights = DEFAULT_ROLE_WEIGHTS.copy()
    role_case = "CASE r.role " + " ".join(
        [f"WHEN '{role}' THEN {weight}" for role, weight in sorted(weights.items())]
    ) + " ELSE 0.0 END"

    actor_rows = conn.execute(
        f"""
        WITH edges AS (
          SELECT
            COALESCE(NULLIF(TRIM(r.actor_label), ''), 'unknown_actor') AS actor_label,
            r.role AS role,
            r.fragment_id AS fragment_id,
            a.irlc_score AS irlc_score,
            {role_case} AS role_weight,
            CASE WHEN r.role IN ('propose','approve','enforce') THEN 1 ELSE 0 END AS is_direct
          FROM legal_fragment_responsibilities r
          JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
        )
        SELECT
          actor_label,
          COUNT(*) AS edges_total,
          COUNT(DISTINCT fragment_id) AS fragments_total,
          SUM(CASE WHEN is_direct = 1 THEN 1 ELSE 0 END) AS direct_edges_total,
          SUM(CASE WHEN is_direct = 1 THEN irlc_score * role_weight ELSE 0 END) AS direct_weighted_score,
          SUM(CASE WHEN is_direct = 0 THEN irlc_score * role_weight ELSE 0 END) AS indirect_weighted_score,
          SUM(irlc_score * role_weight) AS total_weighted_score
        FROM edges
        GROUP BY actor_label
        ORDER BY total_weighted_score DESC, edges_total DESC, actor_label ASC
        LIMIT ?
        """,
        (max(0, int(top_n)),),
    ).fetchall()

    max_total = 0.0
    for r in actor_rows:
        max_total = max(max_total, float(r["total_weighted_score"] or 0.0))

    actor_scores: list[dict[str, Any]] = []
    for r in actor_rows:
        total_weighted = float(r["total_weighted_score"] or 0.0)
        actor_scores.append(
            {
                "actor_label": _norm(r["actor_label"]),
                "edges_total": int(r["edges_total"] or 0),
                "fragments_total": int(r["fragments_total"] or 0),
                "direct_edges_total": int(r["direct_edges_total"] or 0),
                "direct_weighted_score": round(float(r["direct_weighted_score"] or 0.0), 6),
                "indirect_weighted_score": round(float(r["indirect_weighted_score"] or 0.0), 6),
                "total_weighted_score": round(total_weighted, 6),
                "responsibility_score": round((total_weighted / max_total) * 100.0, 6) if max_total > 0 else 0.0,
            }
        )

    low_coverage_rows = conn.execute(
        """
        SELECT
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(f.fragment_label, '') AS fragment_label
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN legal_fragment_responsibilities r
          ON r.fragment_id = a.fragment_id
         AND r.role IN ('propose','approve','enforce')
        WHERE r.fragment_id IS NULL
        ORDER BY f.norm_id ASC, a.fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    direct_missing_sample = [
        {
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "fragment_label": _norm(r["fragment_label"]),
        }
        for r in low_coverage_rows
    ]

    coverage = {
        "fragments_with_any_accountability_pct": round(
            (int(totals["fragments_with_any_accountability_total"] or 0) / fragments_with_irlc_total) if fragments_with_irlc_total else 0.0,
            6,
        ),
        "fragments_with_direct_chain_pct": round(
            (fragments_with_direct_chain_total / fragments_with_irlc_total) if fragments_with_irlc_total else 0.0,
            6,
        ),
        "direct_edges_with_primary_evidence_pct": round(
            (direct_edges_with_primary_evidence_total / direct_edges_total) if direct_edges_total else 0.0,
            6,
        ),
    }

    checks = {
        "direct_chain_started": direct_edges_total > 0,
        "responsibility_score_available": len(actor_scores) > 0,
        "direct_coverage_gate": coverage["fragments_with_direct_chain_pct"] >= float(direct_coverage_min),
        "direct_primary_evidence_gate": (
            coverage["direct_edges_with_primary_evidence_pct"] >= float(direct_primary_evidence_min_pct)
            and direct_edges_with_primary_evidence_total >= int(min_direct_primary_evidence_edges)
        ),
    }
    gate_passed = checks["direct_coverage_gate"] and checks["direct_primary_evidence_gate"]

    if accountability_edges_total == 0:
        status = "failed"
    elif all(checks.values()):
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "fragments_with_irlc_total": fragments_with_irlc_total,
            "fragments_with_any_accountability_total": int(totals["fragments_with_any_accountability_total"] or 0),
            "fragments_with_direct_chain_total": fragments_with_direct_chain_total,
            "accountability_edges_total": accountability_edges_total,
            "direct_edges_total": direct_edges_total,
            "direct_edges_with_primary_evidence_total": direct_edges_with_primary_evidence_total,
            "actors_scored_total": len(actor_scores),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "direct_coverage_min": float(direct_coverage_min),
                "direct_primary_evidence_min_pct": float(direct_primary_evidence_min_pct),
                "min_direct_primary_evidence_edges": int(min_direct_primary_evidence_edges),
            },
        },
        "methodology": {
            "role_weights": weights,
            "direct_roles": list(DIRECT_ROLES),
            "score_formula": "responsibility_score = actor_total_weighted_score / max_actor_total_weighted_score * 100",
            "role_weights_json": _role_weights_json(weights),
        },
        "top_actor_scores": actor_scores,
        "direct_chain_missing_sample": direct_missing_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report direct accountability + responsibility_score")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--direct-coverage-min", type=float, default=0.6)
    ap.add_argument("--direct-primary-evidence-min-pct", type=float, default=1.0)
    ap.add_argument("--min-direct-primary-evidence-edges", type=int, default=1)
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
            direct_coverage_min=float(args.direct_coverage_min),
            direct_primary_evidence_min_pct=float(args.direct_primary_evidence_min_pct),
            min_direct_primary_evidence_edges=int(args.min_direct_primary_evidence_edges),
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
