#!/usr/bin/env python3
"""Report delegated enforcement chain status for restrictions."""

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
    target_fragment_coverage_min: float = 0.6,
    designated_actor_coverage_min: float = 0.5,
    enforcement_evidence_coverage_min: float = 0.7,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_delegated_enforcement_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_delegated_enforcement_links) AS links_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_delegated_enforcement_links) AS fragments_with_links_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS target_fragments_total,
          (SELECT COUNT(DISTINCT fragment_id)
             FROM liberty_delegated_enforcement_links
            WHERE COALESCE(TRIM(designated_actor_label), '') <> '') AS fragments_with_designated_actor_total,
          (SELECT COUNT(*)
             FROM liberty_delegated_enforcement_links
            WHERE COALESCE(TRIM(enforcement_evidence_date), '') <> '') AS links_with_enforcement_evidence_total
        """
    ).fetchone()

    links_rows = conn.execute(
        """
        SELECT
          l.link_key,
          l.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          l.delegating_actor_label,
          l.delegated_institution_label,
          COALESCE(l.designated_role_title, '') AS designated_role_title,
          COALESCE(l.designated_actor_label, '') AS designated_actor_label,
          COALESCE(l.appointment_start_date, '') AS appointment_start_date,
          COALESCE(l.appointment_end_date, '') AS appointment_end_date,
          COALESCE(l.enforcement_action_label, '') AS enforcement_action_label,
          COALESCE(l.enforcement_evidence_date, '') AS enforcement_evidence_date,
          l.chain_confidence,
          COALESCE(l.source_url, '') AS source_url
        FROM liberty_delegated_enforcement_links l
        JOIN legal_norm_fragments f ON f.fragment_id = l.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY l.chain_confidence DESC, l.fragment_id ASC
        LIMIT ?
        """,
        (max(0, int(top_n)),),
    ).fetchall()
    link_sample = [
        {
            "link_key": _norm(r["link_key"]),
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "norm_title": _norm(r["norm_title"]),
            "fragment_label": _norm(r["fragment_label"]),
            "delegating_actor_label": _norm(r["delegating_actor_label"]),
            "delegated_institution_label": _norm(r["delegated_institution_label"]),
            "designated_role_title": _norm(r["designated_role_title"]),
            "designated_actor_label": _norm(r["designated_actor_label"]),
            "appointment_start_date": _norm(r["appointment_start_date"]),
            "appointment_end_date": _norm(r["appointment_end_date"]),
            "enforcement_action_label": _norm(r["enforcement_action_label"]),
            "enforcement_evidence_date": _norm(r["enforcement_evidence_date"]),
            "chain_confidence": float(r["chain_confidence"] or 0.0),
            "source_url": _norm(r["source_url"]),
        }
        for r in links_rows
    ]

    by_institution_rows = conn.execute(
        """
        SELECT
          delegated_institution_label,
          COUNT(*) AS links_total,
          COUNT(DISTINCT fragment_id) AS fragments_total,
          AVG(chain_confidence) AS avg_confidence
        FROM liberty_delegated_enforcement_links
        GROUP BY delegated_institution_label
        ORDER BY links_total DESC, delegated_institution_label ASC
        """
    ).fetchall()
    by_institution = [
        {
            "delegated_institution_label": _norm(r["delegated_institution_label"]),
            "links_total": int(r["links_total"] or 0),
            "fragments_total": int(r["fragments_total"] or 0),
            "avg_confidence": round(float(r["avg_confidence"] or 0.0), 6),
        }
        for r in by_institution_rows
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
        LEFT JOIN liberty_delegated_enforcement_links l ON l.fragment_id = a.fragment_id
        WHERE l.fragment_id IS NULL
        ORDER BY f.norm_id ASC, a.fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    missing_fragment_sample = [
        {
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "fragment_label": _norm(r["fragment_label"]),
        }
        for r in missing_rows
    ]

    weak_rows = conn.execute(
        """
        SELECT
          link_key,
          fragment_id,
          delegating_actor_label,
          delegated_institution_label,
          COALESCE(designated_actor_label, '') AS designated_actor_label,
          COALESCE(enforcement_evidence_date, '') AS enforcement_evidence_date,
          chain_confidence
        FROM liberty_delegated_enforcement_links
        WHERE COALESCE(TRIM(designated_actor_label), '') = ''
           OR COALESCE(TRIM(enforcement_evidence_date), '') = ''
        ORDER BY chain_confidence ASC, fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    weak_link_sample = [
        {
            "link_key": _norm(r["link_key"]),
            "fragment_id": _norm(r["fragment_id"]),
            "delegating_actor_label": _norm(r["delegating_actor_label"]),
            "delegated_institution_label": _norm(r["delegated_institution_label"]),
            "designated_actor_label": _norm(r["designated_actor_label"]),
            "enforcement_evidence_date": _norm(r["enforcement_evidence_date"]),
            "chain_confidence": float(r["chain_confidence"] or 0.0),
        }
        for r in weak_rows
    ]

    links_total = int(totals["links_total"] or 0)
    target_fragments_total = int(totals["target_fragments_total"] or 0)

    coverage = {
        "target_fragment_coverage_pct": round(
            (int(totals["fragments_with_links_total"] or 0) / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "designated_actor_coverage_pct": round(
            (int(totals["fragments_with_designated_actor_total"] or 0) / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "enforcement_evidence_coverage_pct": round(
            (int(totals["links_with_enforcement_evidence_total"] or 0) / links_total) if links_total else 0.0,
            6,
        ),
    }

    checks = {
        "delegated_chain_started": links_total > 0,
        "target_coverage_gate": coverage["target_fragment_coverage_pct"] >= float(target_fragment_coverage_min),
        "designated_actor_gate": coverage["designated_actor_coverage_pct"] >= float(designated_actor_coverage_min),
        "enforcement_evidence_gate": coverage["enforcement_evidence_coverage_pct"] >= float(enforcement_evidence_coverage_min),
    }
    gate_passed = (
        checks["target_coverage_gate"]
        and checks["designated_actor_gate"]
        and checks["enforcement_evidence_gate"]
    )

    if links_total == 0:
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
            "links_total": links_total,
            "fragments_with_links_total": int(totals["fragments_with_links_total"] or 0),
            "target_fragments_total": target_fragments_total,
            "fragments_with_designated_actor_total": int(totals["fragments_with_designated_actor_total"] or 0),
            "links_with_enforcement_evidence_total": int(totals["links_with_enforcement_evidence_total"] or 0),
            "weak_links_total": len(weak_link_sample),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "target_fragment_coverage_min": float(target_fragment_coverage_min),
                "designated_actor_coverage_min": float(designated_actor_coverage_min),
                "enforcement_evidence_coverage_min": float(enforcement_evidence_coverage_min),
            },
        },
        "by_delegated_institution": by_institution,
        "delegated_links_sample": link_sample,
        "weak_links_sample": weak_link_sample,
        "missing_fragment_sample": missing_fragment_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report delegated enforcement chain status")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--target-fragment-coverage-min", type=float, default=0.6)
    ap.add_argument("--designated-actor-coverage-min", type=float, default=0.5)
    ap.add_argument("--enforcement-evidence-coverage-min", type=float, default=0.7)
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
            target_fragment_coverage_min=float(args.target_fragment_coverage_min),
            designated_actor_coverage_min=float(args.designated_actor_coverage_min),
            enforcement_evidence_coverage_min=float(args.enforcement_evidence_coverage_min),
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
