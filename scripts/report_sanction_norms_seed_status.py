#!/usr/bin/env python3
"""Report operational status for sanction norms seed lane."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def build_status_report(conn: sqlite3.Connection, *, sample_limit: int = 20) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_norm_catalog) AS norms_total,
          (SELECT COUNT(*) FROM sanction_norm_fragment_links) AS fragments_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id) AS responsibilities_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE COALESCE(TRIM(r.source_url), '') <> ''
              AND COALESCE(TRIM(r.evidence_date), '') <> ''
              AND COALESCE(TRIM(r.evidence_quote), '') <> '') AS responsibilities_with_primary_evidence_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id) AS responsibility_evidence_items_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE COALESCE(TRIM(e.source_url), '') <> ''
              AND COALESCE(TRIM(e.evidence_date), '') <> ''
              AND COALESCE(TRIM(e.evidence_quote), '') <> '') AS responsibility_evidence_items_with_primary_fields_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.source_record_pk IS NOT NULL) AS responsibility_evidence_items_with_source_record_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type IN ('congreso_diario', 'senado_diario', 'congreso_vote', 'senado_vote')
          ) AS responsibility_evidence_items_parliamentary_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type = 'other'
              AND COALESCE(json_extract(e.raw_payload, '$.record_kind'), '') IN (
                'sanction_norm_execution_evidence_backfill',
                'sanction_norm_execution_lineage_bridge_backfill',
                'sanction_norm_procedural_metric_evidence_backfill'
              )
          ) AS responsibility_evidence_items_execution_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type IN ('congreso_vote', 'senado_vote')
          ) AS responsibility_evidence_items_parliamentary_vote_total,
          (SELECT COUNT(DISTINCT r.responsibility_id)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type IN ('congreso_diario', 'senado_diario', 'congreso_vote', 'senado_vote')
          ) AS responsibilities_with_parliamentary_evidence_total,
          (SELECT COUNT(DISTINCT r.responsibility_id)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type = 'other'
              AND COALESCE(json_extract(e.raw_payload, '$.record_kind'), '') IN (
                'sanction_norm_execution_evidence_backfill',
                'sanction_norm_execution_lineage_bridge_backfill',
                'sanction_norm_procedural_metric_evidence_backfill'
              )
          ) AS responsibilities_with_execution_evidence_total,
          (SELECT COUNT(DISTINCT r.responsibility_id)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
            WHERE e.evidence_type IN ('congreso_vote', 'senado_vote')
          ) AS responsibilities_with_parliamentary_vote_evidence_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibility_evidence e
             JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
             JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
            WHERE COALESCE(sr.raw_payload, '') LIKE '%\"seed_schema_version\": \"sanction_norms_seed_v1\"%') AS responsibility_evidence_items_with_seed_source_record_total,
          (SELECT COUNT(*)
             FROM legal_norm_lineage_edges e
             JOIN sanction_norm_catalog c ON c.norm_id = e.norm_id) AS lineage_edges_total,
          (SELECT COUNT(*)
             FROM legal_norm_lineage_edges e
             JOIN sanction_norm_catalog c ON c.norm_id = e.norm_id
            WHERE COALESCE(TRIM(e.source_url), '') <> ''
              AND COALESCE(TRIM(e.evidence_date), '') <> ''
              AND COALESCE(TRIM(e.evidence_quote), '') <> '') AS lineage_edges_with_primary_evidence_total,
          (SELECT COUNT(DISTINCT l.fragment_id)
             FROM sanction_norm_fragment_links l
             JOIN legal_fragment_responsibilities r ON r.fragment_id = l.fragment_id) AS fragments_with_responsibility,
          (SELECT COUNT(DISTINCT l.fragment_id)
             FROM sanction_norm_fragment_links l
             JOIN legal_fragment_responsibilities r ON r.fragment_id = l.fragment_id
            WHERE COALESCE(TRIM(r.source_url), '') <> ''
              AND COALESCE(TRIM(r.evidence_date), '') <> ''
              AND COALESCE(TRIM(r.evidence_quote), '') <> '') AS fragments_with_responsibility_primary_evidence,
          (SELECT COUNT(DISTINCT r.responsibility_id)
             FROM legal_fragment_responsibilities r
             JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
             JOIN legal_fragment_responsibility_evidence e ON e.responsibility_id = r.responsibility_id) AS responsibilities_with_evidence_items_total,
          (SELECT COUNT(DISTINCT e.norm_id)
             FROM legal_norm_lineage_edges e
             JOIN sanction_norm_catalog c ON c.norm_id = e.norm_id) AS norms_with_lineage
        """
    ).fetchone()

    norms_total = int(totals["norms_total"])
    fragments_total = int(totals["fragments_total"])
    responsibilities_total = int(totals["responsibilities_total"])
    responsibilities_with_primary_evidence_total = int(totals["responsibilities_with_primary_evidence_total"])
    responsibility_evidence_items_total = int(totals["responsibility_evidence_items_total"])
    responsibility_evidence_items_with_primary_fields_total = int(
        totals["responsibility_evidence_items_with_primary_fields_total"]
    )
    responsibility_evidence_items_with_source_record_total = int(
        totals["responsibility_evidence_items_with_source_record_total"]
    )
    responsibility_evidence_items_parliamentary_total = int(
        totals["responsibility_evidence_items_parliamentary_total"]
    )
    responsibility_evidence_items_execution_total = int(
        totals["responsibility_evidence_items_execution_total"]
    )
    responsibility_evidence_items_parliamentary_vote_total = int(
        totals["responsibility_evidence_items_parliamentary_vote_total"]
    )
    responsibilities_with_parliamentary_evidence_total = int(
        totals["responsibilities_with_parliamentary_evidence_total"]
    )
    responsibilities_with_execution_evidence_total = int(
        totals["responsibilities_with_execution_evidence_total"]
    )
    responsibilities_with_parliamentary_vote_evidence_total = int(
        totals["responsibilities_with_parliamentary_vote_evidence_total"]
    )
    responsibility_evidence_items_with_seed_source_record_total = int(
        totals["responsibility_evidence_items_with_seed_source_record_total"]
    )
    lineage_edges_total = int(totals["lineage_edges_total"])
    lineage_edges_with_primary_evidence_total = int(totals["lineage_edges_with_primary_evidence_total"])
    fragments_with_responsibility = int(totals["fragments_with_responsibility"])
    fragments_with_responsibility_primary_evidence = int(totals["fragments_with_responsibility_primary_evidence"])
    responsibilities_with_evidence_items_total = int(totals["responsibilities_with_evidence_items_total"])
    norms_with_lineage = int(totals["norms_with_lineage"])
    fragments_missing_responsibility = max(0, fragments_total - fragments_with_responsibility)
    norms_missing_lineage = max(0, norms_total - norms_with_lineage)
    responsibilities_missing_primary_evidence = max(
        0, responsibilities_total - responsibilities_with_primary_evidence_total
    )
    responsibilities_missing_evidence_items = max(
        0, responsibilities_total - responsibilities_with_evidence_items_total
    )
    responsibility_evidence_items_missing_primary_fields = max(
        0, responsibility_evidence_items_total - responsibility_evidence_items_with_primary_fields_total
    )
    responsibility_evidence_items_missing_source_record = max(
        0, responsibility_evidence_items_total - responsibility_evidence_items_with_source_record_total
    )
    responsibilities_missing_parliamentary_evidence = max(
        0, responsibilities_total - responsibilities_with_parliamentary_evidence_total
    )
    responsibilities_missing_execution_evidence = max(
        0, responsibilities_total - responsibilities_with_execution_evidence_total
    )
    responsibilities_missing_parliamentary_vote_evidence = max(
        0, responsibilities_total - responsibilities_with_parliamentary_vote_evidence_total
    )
    responsibility_evidence_items_with_non_seed_source_record_total = max(
        0,
        responsibility_evidence_items_with_source_record_total
        - responsibility_evidence_items_with_seed_source_record_total,
    )
    lineage_missing_primary_evidence = max(
        0, lineage_edges_total - lineage_edges_with_primary_evidence_total
    )
    fragments_missing_primary_evidence = max(
        0, fragments_with_responsibility - fragments_with_responsibility_primary_evidence
    )

    by_role_rows = conn.execute(
        """
        SELECT r.role AS role, COUNT(*) AS n
        FROM legal_fragment_responsibilities r
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        GROUP BY r.role
        ORDER BY n DESC, role ASC
        """
    ).fetchall()
    by_role = {str(r["role"]): int(r["n"]) for r in by_role_rows}

    by_relation_rows = conn.execute(
        """
        SELECT e.relation_type AS relation_type, COUNT(*) AS n
        FROM legal_norm_lineage_edges e
        JOIN sanction_norm_catalog c ON c.norm_id = e.norm_id
        GROUP BY e.relation_type
        ORDER BY n DESC, relation_type ASC
        """
    ).fetchall()
    by_relation_type = {str(r["relation_type"]): int(r["n"]) for r in by_relation_rows}

    missing_rows = conn.execute(
        """
        SELECT
          f.fragment_id,
          f.norm_id,
          n.boe_id,
          f.fragment_type,
          f.fragment_label,
          f.competent_body
        FROM sanction_norm_fragment_links l
        JOIN legal_norm_fragments f ON f.fragment_id = l.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN legal_fragment_responsibilities r ON r.fragment_id = f.fragment_id
        WHERE r.fragment_id IS NULL
        ORDER BY f.norm_id, f.fragment_order, f.fragment_label
        LIMIT ?
        """,
        (max(0, int(sample_limit)),),
    ).fetchall()

    missing_sample: list[dict[str, Any]] = []
    for row in missing_rows:
        missing_sample.append(
            {
                "fragment_id": str(row["fragment_id"]),
                "norm_id": str(row["norm_id"]),
                "boe_id": _norm(row["boe_id"]),
                "fragment_type": _norm(row["fragment_type"]),
                "fragment_label": _norm(row["fragment_label"]),
                "competent_body": _norm(row["competent_body"]),
            }
        )

    missing_lineage_rows = conn.execute(
        """
        SELECT n.norm_id, n.boe_id, n.title, n.scope
        FROM sanction_norm_catalog c
        JOIN legal_norms n ON n.norm_id = c.norm_id
        LEFT JOIN (
          SELECT DISTINCT norm_id
          FROM legal_norm_lineage_edges
        ) e ON e.norm_id = n.norm_id
        WHERE e.norm_id IS NULL
        ORDER BY n.norm_id
        LIMIT ?
        """,
        (max(0, int(sample_limit)),),
    ).fetchall()

    missing_lineage_sample: list[dict[str, Any]] = []
    for row in missing_lineage_rows:
        missing_lineage_sample.append(
            {
                "norm_id": str(row["norm_id"]),
                "boe_id": _norm(row["boe_id"]),
                "title": _norm(row["title"]),
                "scope": _norm(row["scope"]),
            }
        )

    coverage_pct = (fragments_with_responsibility / fragments_total) if fragments_total > 0 else 0.0
    primary_evidence_coverage_pct = (
        (responsibilities_with_primary_evidence_total / responsibilities_total)
        if responsibilities_total > 0
        else 0.0
    )
    responsibility_evidence_item_coverage_pct = (
        (responsibilities_with_evidence_items_total / responsibilities_total)
        if responsibilities_total > 0
        else 0.0
    )
    responsibility_evidence_item_primary_fields_coverage_pct = (
        (responsibility_evidence_items_with_primary_fields_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_evidence_item_source_record_coverage_pct = (
        (responsibility_evidence_items_with_source_record_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_evidence_item_non_seed_source_record_coverage_pct = (
        (responsibility_evidence_items_with_non_seed_source_record_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_evidence_item_parliamentary_share_pct = (
        (responsibility_evidence_items_parliamentary_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_evidence_item_execution_share_pct = (
        (responsibility_evidence_items_execution_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_evidence_item_parliamentary_vote_share_pct = (
        (responsibility_evidence_items_parliamentary_vote_total / responsibility_evidence_items_total)
        if responsibility_evidence_items_total > 0
        else 0.0
    )
    responsibility_parliamentary_coverage_pct = (
        (responsibilities_with_parliamentary_evidence_total / responsibilities_total)
        if responsibilities_total > 0
        else 0.0
    )
    responsibility_execution_coverage_pct = (
        (responsibilities_with_execution_evidence_total / responsibilities_total)
        if responsibilities_total > 0
        else 0.0
    )
    responsibility_parliamentary_vote_coverage_pct = (
        (responsibilities_with_parliamentary_vote_evidence_total / responsibilities_total)
        if responsibilities_total > 0
        else 0.0
    )
    lineage_coverage_pct = (norms_with_lineage / norms_total) if norms_total > 0 else 0.0
    lineage_primary_evidence_coverage_pct = (
        (lineage_edges_with_primary_evidence_total / lineage_edges_total)
        if lineage_edges_total > 0
        else 0.0
    )

    status = "failed"
    if norms_total > 0 and fragments_total > 0:
        status = (
            "ok"
            if (
                fragments_missing_responsibility == 0
                and responsibilities_missing_primary_evidence == 0
                and responsibilities_missing_evidence_items == 0
                and responsibility_evidence_items_missing_primary_fields == 0
                and norms_missing_lineage == 0
                and lineage_missing_primary_evidence == 0
            )
            else "degraded"
        )

    checks = {
        "seed_loaded": norms_total > 0,
        "fragment_catalog_loaded": fragments_total > 0,
        "responsibility_chain_started": responsibilities_total > 0,
        "all_fragments_with_responsibility": fragments_total > 0 and fragments_missing_responsibility == 0,
        "primary_evidence_chain_started": responsibilities_with_primary_evidence_total > 0,
        "all_responsibilities_with_primary_evidence": (
            responsibilities_total > 0 and responsibilities_missing_primary_evidence == 0
        ),
        "responsibility_evidence_chain_started": responsibility_evidence_items_total > 0,
        "responsibility_evidence_parliamentary_chain_started": responsibility_evidence_items_parliamentary_total > 0,
        "responsibility_evidence_execution_chain_started": responsibility_evidence_items_execution_total > 0,
        "responsibility_evidence_vote_chain_started": responsibility_evidence_items_parliamentary_vote_total > 0,
        "responsibility_evidence_source_record_chain_started": responsibility_evidence_items_with_source_record_total > 0,
        "responsibility_evidence_non_seed_source_record_chain_started": (
            responsibility_evidence_items_with_non_seed_source_record_total > 0
        ),
        "all_responsibilities_with_evidence_items": (
            responsibilities_total > 0 and responsibilities_missing_evidence_items == 0
        ),
        "all_responsibility_evidence_items_with_primary_fields": (
            responsibility_evidence_items_total > 0 and responsibility_evidence_items_missing_primary_fields == 0
        ),
        "lineage_chain_started": lineage_edges_total > 0,
        "all_norms_with_lineage": norms_total > 0 and norms_missing_lineage == 0,
        "lineage_primary_evidence_chain_started": lineage_edges_with_primary_evidence_total > 0,
        "all_lineage_edges_with_primary_evidence": (
            lineage_edges_total > 0 and lineage_missing_primary_evidence == 0
        ),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "norms_total": norms_total,
            "fragments_total": fragments_total,
            "responsibilities_total": responsibilities_total,
            "responsibilities_with_primary_evidence_total": responsibilities_with_primary_evidence_total,
            "responsibilities_missing_primary_evidence": responsibilities_missing_primary_evidence,
            "responsibilities_with_evidence_items_total": responsibilities_with_evidence_items_total,
            "responsibilities_missing_evidence_items": responsibilities_missing_evidence_items,
            "responsibility_evidence_items_total": responsibility_evidence_items_total,
            "responsibility_evidence_items_with_primary_fields_total": (
                responsibility_evidence_items_with_primary_fields_total
            ),
            "responsibility_evidence_items_missing_primary_fields": (
                responsibility_evidence_items_missing_primary_fields
            ),
            "responsibility_evidence_items_with_source_record_total": (
                responsibility_evidence_items_with_source_record_total
            ),
            "responsibility_evidence_items_parliamentary_total": (
                responsibility_evidence_items_parliamentary_total
            ),
            "responsibility_evidence_items_execution_total": (
                responsibility_evidence_items_execution_total
            ),
            "responsibility_evidence_items_parliamentary_vote_total": (
                responsibility_evidence_items_parliamentary_vote_total
            ),
            "responsibilities_with_parliamentary_evidence_total": (
                responsibilities_with_parliamentary_evidence_total
            ),
            "responsibilities_with_execution_evidence_total": (
                responsibilities_with_execution_evidence_total
            ),
            "responsibilities_with_parliamentary_vote_evidence_total": (
                responsibilities_with_parliamentary_vote_evidence_total
            ),
            "responsibilities_missing_parliamentary_evidence": (
                responsibilities_missing_parliamentary_evidence
            ),
            "responsibilities_missing_execution_evidence": (
                responsibilities_missing_execution_evidence
            ),
            "responsibilities_missing_parliamentary_vote_evidence": (
                responsibilities_missing_parliamentary_vote_evidence
            ),
            "responsibility_evidence_items_with_seed_source_record_total": (
                responsibility_evidence_items_with_seed_source_record_total
            ),
            "responsibility_evidence_items_with_non_seed_source_record_total": (
                responsibility_evidence_items_with_non_seed_source_record_total
            ),
            "responsibility_evidence_items_missing_source_record": (
                responsibility_evidence_items_missing_source_record
            ),
            "lineage_edges_total": lineage_edges_total,
            "lineage_edges_with_primary_evidence_total": lineage_edges_with_primary_evidence_total,
            "lineage_edges_missing_primary_evidence": lineage_missing_primary_evidence,
            "fragments_with_responsibility": fragments_with_responsibility,
            "fragments_with_responsibility_primary_evidence": fragments_with_responsibility_primary_evidence,
            "fragments_missing_primary_evidence": fragments_missing_primary_evidence,
            "fragments_missing_responsibility": fragments_missing_responsibility,
            "norms_with_lineage": norms_with_lineage,
            "norms_missing_lineage": norms_missing_lineage,
        },
        "coverage": {
            "responsibility_coverage_pct": round(coverage_pct, 6),
            "responsibility_primary_evidence_coverage_pct": round(primary_evidence_coverage_pct, 6),
            "responsibility_evidence_item_coverage_pct": round(responsibility_evidence_item_coverage_pct, 6),
            "responsibility_evidence_item_primary_fields_coverage_pct": round(
                responsibility_evidence_item_primary_fields_coverage_pct, 6
            ),
            "responsibility_evidence_item_source_record_coverage_pct": round(
                responsibility_evidence_item_source_record_coverage_pct, 6
            ),
            "responsibility_evidence_item_non_seed_source_record_coverage_pct": round(
                responsibility_evidence_item_non_seed_source_record_coverage_pct, 6
            ),
            "responsibility_evidence_item_parliamentary_share_pct": round(
                responsibility_evidence_item_parliamentary_share_pct, 6
            ),
            "responsibility_evidence_item_execution_share_pct": round(
                responsibility_evidence_item_execution_share_pct, 6
            ),
            "responsibility_evidence_item_parliamentary_vote_share_pct": round(
                responsibility_evidence_item_parliamentary_vote_share_pct, 6
            ),
            "responsibility_parliamentary_coverage_pct": round(
                responsibility_parliamentary_coverage_pct, 6
            ),
            "responsibility_execution_coverage_pct": round(
                responsibility_execution_coverage_pct, 6
            ),
            "responsibility_parliamentary_vote_coverage_pct": round(
                responsibility_parliamentary_vote_coverage_pct, 6
            ),
            "lineage_coverage_pct": round(lineage_coverage_pct, 6),
            "lineage_primary_evidence_coverage_pct": round(lineage_primary_evidence_coverage_pct, 6),
        },
        "by_role": by_role,
        "by_relation_type": by_relation_type,
        "checks": checks,
        "missing_responsibility_sample": missing_sample,
        "missing_lineage_sample": missing_lineage_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report status for sanction norms seed lane")
    ap.add_argument("--db", required=True)
    ap.add_argument("--sample-limit", type=int, default=20)
    ap.add_argument("--out", default="", help="optional output JSON path")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    conn = open_db(db_path)
    try:
        report = build_status_report(conn, sample_limit=int(args.sample_limit))
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if str(report.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
