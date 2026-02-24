#!/usr/bin/env python3
"""Report status for sanction data catalog lane."""

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


def build_status_report(conn: sqlite3.Connection, *, sample_limit: int = 20) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_volume_sources) AS volume_sources_total,
          (SELECT COUNT(*) FROM sanction_infraction_types) AS infraction_types_total,
          (SELECT COUNT(*) FROM sanction_infraction_type_mappings) AS infraction_mappings_total,
          (SELECT COUNT(*) FROM sanction_infraction_type_mappings WHERE norm_id IS NOT NULL) AS mappings_with_norm_total,
          (SELECT COUNT(*) FROM sanction_infraction_type_mappings WHERE fragment_id IS NOT NULL) AS mappings_with_fragment_total,
          (SELECT COUNT(*) FROM sanction_procedural_kpi_definitions) AS procedural_kpis_total,
          (SELECT COUNT(*) FROM sanction_procedural_metrics) AS procedural_metric_rows_total,
          (SELECT COUNT(*) FROM sanction_volume_observations) AS volume_observations_total
        """
    ).fetchone()

    by_domain_rows = conn.execute(
        """
        SELECT domain, COUNT(*) AS n
        FROM sanction_infraction_types
        GROUP BY domain
        ORDER BY n DESC, domain ASC
        """
    ).fetchall()
    by_domain = {_norm(r["domain"]): int(r["n"]) for r in by_domain_rows}

    by_scope_rows = conn.execute(
        """
        SELECT admin_scope, COUNT(*) AS n
        FROM sanction_volume_sources
        GROUP BY admin_scope
        ORDER BY n DESC, admin_scope ASC
        """
    ).fetchall()
    by_scope = {_norm(r["admin_scope"]): int(r["n"]) for r in by_scope_rows}

    missing_fragment_rows = conn.execute(
        """
        SELECT
          m.mapping_key,
          m.infraction_type_id,
          m.source_system,
          m.source_code,
          m.source_label
        FROM sanction_infraction_type_mappings m
        WHERE m.fragment_id IS NULL
        ORDER BY m.infraction_type_id, m.source_system, m.source_code
        LIMIT ?
        """,
        (max(0, int(sample_limit)),),
    ).fetchall()
    missing_fragment_sample = [
        {
            "mapping_key": _norm(row["mapping_key"]),
            "infraction_type_id": _norm(row["infraction_type_id"]),
            "source_system": _norm(row["source_system"]),
            "source_code": _norm(row["source_code"]),
            "source_label": _norm(row["source_label"]),
        }
        for row in missing_fragment_rows
    ]

    volume_sources_total = int(totals["volume_sources_total"])
    infraction_types_total = int(totals["infraction_types_total"])
    infraction_mappings_total = int(totals["infraction_mappings_total"])
    mappings_with_norm_total = int(totals["mappings_with_norm_total"])
    mappings_with_fragment_total = int(totals["mappings_with_fragment_total"])
    procedural_kpis_total = int(totals["procedural_kpis_total"])
    procedural_metric_rows_total = int(totals["procedural_metric_rows_total"])
    volume_observations_total = int(totals["volume_observations_total"])

    checks = {
        "volume_sources_seeded": volume_sources_total >= 5,
        "infraction_types_seeded": infraction_types_total >= 8,
        "infraction_mappings_seeded": infraction_mappings_total >= 8,
        "mappings_with_fragment_seeded": mappings_with_fragment_total >= 6,
        "procedural_kpis_seeded": procedural_kpis_total >= 3,
        "volume_observations_started": volume_observations_total > 0,
        "procedural_metrics_started": procedural_metric_rows_total > 0,
    }

    if volume_sources_total == 0 or infraction_types_total == 0:
        status = "failed"
    elif all(
        checks[k]
        for k in (
            "volume_sources_seeded",
            "infraction_types_seeded",
            "infraction_mappings_seeded",
            "mappings_with_fragment_seeded",
            "procedural_kpis_seeded",
        )
    ):
        # data rows are optional in this slice; they become mandatory in later ingestion lanes.
        status = "ok"
    else:
        status = "degraded"

    coverage = {
        "mapping_fragment_coverage_pct": round(
            (mappings_with_fragment_total / infraction_mappings_total) if infraction_mappings_total else 0.0,
            6,
        ),
        "mapping_norm_coverage_pct": round((mappings_with_norm_total / infraction_mappings_total) if infraction_mappings_total else 0.0, 6),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "volume_sources_total": volume_sources_total,
            "infraction_types_total": infraction_types_total,
            "infraction_mappings_total": infraction_mappings_total,
            "mappings_with_norm_total": mappings_with_norm_total,
            "mappings_with_fragment_total": mappings_with_fragment_total,
            "procedural_kpis_total": procedural_kpis_total,
            "volume_observations_total": volume_observations_total,
            "procedural_metric_rows_total": procedural_metric_rows_total,
        },
        "coverage": coverage,
        "checks": checks,
        "by_domain": by_domain,
        "by_scope": by_scope,
        "missing_fragment_sample": missing_fragment_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report status for sanction data catalog lane")
    ap.add_argument("--db", required=True)
    ap.add_argument("--sample-limit", type=int, default=20)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
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
