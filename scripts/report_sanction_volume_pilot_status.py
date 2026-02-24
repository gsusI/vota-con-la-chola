#!/usr/bin/env python3
"""Report status for sanction volume pilot lane (ranking + dossiers + municipal progress)."""

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


def _top_norms(
    conn: sqlite3.Connection,
    *,
    top_n: int,
    total_norm_expedientes: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          o.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          SUM(COALESCE(o.expediente_count, 0)) AS expediente_count,
          SUM(COALESCE(o.importe_total_eur, 0.0)) AS importe_total_eur,
          CASE
            WHEN SUM(COALESCE(o.expediente_count, 0)) > 0
            THEN (SUM(COALESCE(o.importe_total_eur, 0.0)) / SUM(COALESCE(o.expediente_count, 0)))
            ELSE NULL
          END AS importe_medio_eur,
          COUNT(*) AS observation_rows,
          COUNT(DISTINCT o.sanction_source_id) AS source_count
        FROM sanction_volume_observations o
        LEFT JOIN legal_norms n ON n.norm_id = o.norm_id
        WHERE o.norm_id IS NOT NULL AND TRIM(o.norm_id) <> ''
        GROUP BY o.norm_id
        ORDER BY expediente_count DESC, importe_total_eur DESC, o.norm_id ASC
        LIMIT ?
        """,
        (max(0, int(top_n)),),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        expedientes = int(row["expediente_count"] or 0)
        importe_total = float(row["importe_total_eur"] or 0.0)
        out.append(
            {
                "norm_id": _norm(row["norm_id"]),
                "boe_id": _norm(row["boe_id"]),
                "norm_title": _norm(row["norm_title"]),
                "expediente_count": expedientes,
                "importe_total_eur": round(importe_total, 2),
                "importe_medio_eur": (
                    round(float(row["importe_medio_eur"]), 2)
                    if row["importe_medio_eur"] is not None
                    else None
                ),
                "observation_rows": int(row["observation_rows"] or 0),
                "source_count": int(row["source_count"] or 0),
                # Proxy only over observed sanction universe; population denominator remains pending.
                "incidence_per_1000_observed_cases": round(
                    ((expedientes / total_norm_expedientes) * 1000.0) if total_norm_expedientes > 0 else 0.0,
                    6,
                ),
                "incidence_per_1000_population": None,
            }
        )
    return out


def _norm_dossier(
    conn: sqlite3.Connection,
    *,
    norm_id: str,
    fragment_sample_limit: int,
    infraction_sample_limit: int,
) -> dict[str, Any]:
    totals_row = conn.execute(
        """
        SELECT
          SUM(COALESCE(expediente_count, 0)) AS expediente_count,
          SUM(COALESCE(importe_total_eur, 0.0)) AS importe_total_eur,
          SUM(COALESCE(recurso_presentado_count, 0)) AS recurso_presentado_count,
          SUM(COALESCE(recurso_estimado_count, 0)) AS recurso_estimado_count,
          SUM(COALESCE(recurso_desestimado_count, 0)) AS recurso_desestimado_count,
          COUNT(*) AS observation_rows
        FROM sanction_volume_observations
        WHERE norm_id = ?
        """,
        (norm_id,),
    ).fetchone()

    meta_row = conn.execute(
        """
        SELECT
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(c.scope, '') AS scope,
          COALESCE(c.organismo_competente, '') AS organismo_competente,
          COALESCE(c.incidence_hypothesis, '') AS incidence_hypothesis
        FROM legal_norms n
        LEFT JOIN sanction_norm_catalog c ON c.norm_id = n.norm_id
        WHERE n.norm_id = ?
        """,
        (norm_id,),
    ).fetchone()

    infraction_rows = conn.execute(
        """
        SELECT
          o.infraction_type_id,
          COALESCE(t.label, '') AS infraction_label,
          SUM(COALESCE(o.expediente_count, 0)) AS expediente_count,
          SUM(COALESCE(o.importe_total_eur, 0.0)) AS importe_total_eur
        FROM sanction_volume_observations o
        LEFT JOIN sanction_infraction_types t ON t.infraction_type_id = o.infraction_type_id
        WHERE o.norm_id = ? AND o.infraction_type_id IS NOT NULL AND TRIM(o.infraction_type_id) <> ''
        GROUP BY o.infraction_type_id, t.label
        ORDER BY expediente_count DESC, importe_total_eur DESC, o.infraction_type_id ASC
        LIMIT ?
        """,
        (norm_id, max(0, int(infraction_sample_limit))),
    ).fetchall()

    fragment_rows = conn.execute(
        """
        SELECT
          f.fragment_id,
          COALESCE(f.fragment_type, '') AS fragment_type,
          COALESCE(f.fragment_label, '') AS fragment_label,
          COALESCE(f.competent_body, '') AS competent_body
        FROM legal_norm_fragments f
        WHERE f.norm_id = ?
        ORDER BY f.fragment_order ASC, f.fragment_id ASC
        LIMIT ?
        """,
        (norm_id, max(0, int(fragment_sample_limit))),
    ).fetchall()

    source_rows = conn.execute(
        """
        SELECT
          o.sanction_source_id,
          COALESCE(s.label, '') AS source_label,
          SUM(COALESCE(o.expediente_count, 0)) AS expediente_count
        FROM sanction_volume_observations o
        LEFT JOIN sanction_volume_sources s ON s.sanction_source_id = o.sanction_source_id
        WHERE o.norm_id = ?
        GROUP BY o.sanction_source_id, s.label
        ORDER BY expediente_count DESC, o.sanction_source_id ASC
        """,
        (norm_id,),
    ).fetchall()

    municipal_row = conn.execute(
        """
        SELECT
          COUNT(*) AS ordinance_fragment_links_total,
          COUNT(DISTINCT ordinance_id) AS municipal_ordinances_total
        FROM sanction_municipal_ordinance_fragments
        WHERE mapped_norm_id = ?
        """,
        (norm_id,),
    ).fetchone()

    recurso_presentado = int(totals_row["recurso_presentado_count"] or 0)
    recurso_estimado = int(totals_row["recurso_estimado_count"] or 0)
    recurso_desestimado = int(totals_row["recurso_desestimado_count"] or 0)

    return {
        "norm_id": norm_id,
        "boe_id": _norm(meta_row["boe_id"]) if meta_row else "",
        "norm_title": _norm(meta_row["norm_title"]) if meta_row else "",
        "scope": _norm(meta_row["scope"]) if meta_row else "",
        "organismo_competente": _norm(meta_row["organismo_competente"]) if meta_row else "",
        "incidence_hypothesis": _norm(meta_row["incidence_hypothesis"]) if meta_row else "",
        "volumen": {
            "expediente_count": int(totals_row["expediente_count"] or 0),
            "importe_total_eur": round(float(totals_row["importe_total_eur"] or 0.0), 2),
            "observation_rows": int(totals_row["observation_rows"] or 0),
        },
        "procedural": {
            "recurso_presentado_count": recurso_presentado,
            "recurso_estimado_count": recurso_estimado,
            "recurso_desestimado_count": recurso_desestimado,
            "recurso_estimation_rate": round((recurso_estimado / recurso_presentado), 6)
            if recurso_presentado > 0
            else None,
        },
        "top_infraction_types": [
            {
                "infraction_type_id": _norm(row["infraction_type_id"]),
                "infraction_label": _norm(row["infraction_label"]),
                "expediente_count": int(row["expediente_count"] or 0),
                "importe_total_eur": round(float(row["importe_total_eur"] or 0.0), 2),
            }
            for row in infraction_rows
        ],
        "legal_drilldown_fragments": [
            {
                "fragment_id": _norm(row["fragment_id"]),
                "fragment_type": _norm(row["fragment_type"]),
                "fragment_label": _norm(row["fragment_label"]),
                "competent_body": _norm(row["competent_body"]),
            }
            for row in fragment_rows
        ],
        "source_lanes": [
            {
                "sanction_source_id": _norm(row["sanction_source_id"]),
                "source_label": _norm(row["source_label"]),
                "expediente_count": int(row["expediente_count"] or 0),
            }
            for row in source_rows
        ],
        "municipal_links": {
            "ordinance_fragment_links_total": int(municipal_row["ordinance_fragment_links_total"] or 0),
            "municipal_ordinances_total": int(municipal_row["municipal_ordinances_total"] or 0),
        },
    }


def _municipal_progress(conn: sqlite3.Connection, *, sample_limit: int) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_municipal_ordinances) AS ordinances_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinances WHERE ordinance_status = 'normalized') AS normalized_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinances WHERE ordinance_status = 'identified') AS identified_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinances WHERE ordinance_status = 'blocked') AS blocked_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinance_fragments) AS ordinance_fragments_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinance_fragments WHERE mapped_norm_id IS NOT NULL) AS mapped_norm_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinance_fragments WHERE mapped_fragment_id IS NOT NULL) AS mapped_fragment_total
        """
    ).fetchone()

    normalized_rows = conn.execute(
        """
        SELECT ordinance_id, city_name, ordinance_label
        FROM sanction_municipal_ordinances
        WHERE ordinance_status = 'normalized'
        ORDER BY city_name ASC, ordinance_id ASC
        LIMIT ?
        """,
        (max(0, int(sample_limit)),),
    ).fetchall()

    backlog_rows = conn.execute(
        """
        SELECT ordinance_id, city_name, ordinance_label
        FROM sanction_municipal_ordinances
        WHERE ordinance_status = 'identified'
        ORDER BY city_name ASC, ordinance_id ASC
        LIMIT ?
        """,
        (max(0, int(sample_limit)),),
    ).fetchall()

    ordinances_total = int(totals["ordinances_total"] or 0)
    normalized_total = int(totals["normalized_total"] or 0)
    ordinance_fragments_total = int(totals["ordinance_fragments_total"] or 0)
    mapped_norm_total = int(totals["mapped_norm_total"] or 0)
    mapped_fragment_total = int(totals["mapped_fragment_total"] or 0)

    return {
        "target_pilot_cities": 20,
        "totals": {
            "ordinances_total": ordinances_total,
            "normalized_total": normalized_total,
            "identified_total": int(totals["identified_total"] or 0),
            "blocked_total": int(totals["blocked_total"] or 0),
            "ordinance_fragments_total": ordinance_fragments_total,
            "mapped_norm_total": mapped_norm_total,
            "mapped_fragment_total": mapped_fragment_total,
        },
        "coverage": {
            "pilot_catalog_coverage_pct": round((ordinances_total / 20.0), 6) if ordinances_total else 0.0,
            "normalized_coverage_pct": round((normalized_total / ordinances_total), 6) if ordinances_total else 0.0,
            "fragment_norm_mapping_pct": round((mapped_norm_total / ordinance_fragments_total), 6)
            if ordinance_fragments_total
            else 0.0,
            "fragment_fragment_mapping_pct": round((mapped_fragment_total / ordinance_fragments_total), 6)
            if ordinance_fragments_total
            else 0.0,
        },
        "normalized_sample": [
            {
                "ordinance_id": _norm(row["ordinance_id"]),
                "city_name": _norm(row["city_name"]),
                "ordinance_label": _norm(row["ordinance_label"]),
            }
            for row in normalized_rows
        ],
        "normalization_backlog_sample": [
            {
                "ordinance_id": _norm(row["ordinance_id"]),
                "city_name": _norm(row["city_name"]),
                "ordinance_label": _norm(row["ordinance_label"]),
            }
            for row in backlog_rows
        ],
    }


def build_status_report(
    conn: sqlite3.Connection,
    *,
    top_n: int = 10,
    dossier_limit: int = 5,
    sample_limit: int = 20,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_volume_observations) AS observations_total,
          (SELECT COUNT(*) FROM sanction_volume_observations WHERE norm_id IS NOT NULL AND TRIM(norm_id) <> '') AS observations_with_norm_total,
          (SELECT COUNT(*) FROM sanction_volume_observations WHERE norm_id IS NULL OR TRIM(norm_id) = '') AS observations_without_norm_total,
          (SELECT SUM(COALESCE(expediente_count, 0))
             FROM sanction_volume_observations
             WHERE norm_id IS NOT NULL AND TRIM(norm_id) <> '') AS observations_with_norm_expediente_total,
          (SELECT COUNT(*) FROM sanction_procedural_metrics) AS procedural_metrics_total
        """
    ).fetchone()

    observations_total = int(totals["observations_total"] or 0)
    observations_with_norm_total = int(totals["observations_with_norm_total"] or 0)
    observations_without_norm_total = int(totals["observations_without_norm_total"] or 0)
    observations_with_norm_expediente_total = int(totals["observations_with_norm_expediente_total"] or 0)

    top_normas = _top_norms(
        conn,
        top_n=max(0, int(top_n)),
        total_norm_expedientes=observations_with_norm_expediente_total,
    )
    norm_dossiers = [
        _norm_dossier(
            conn,
            norm_id=_norm(row["norm_id"]),
            fragment_sample_limit=max(1, min(int(sample_limit), 20)),
            infraction_sample_limit=max(1, min(int(sample_limit), 10)),
        )
        for row in top_normas[: max(0, int(dossier_limit))]
    ]
    municipal = _municipal_progress(conn, sample_limit=max(0, int(sample_limit)))

    checks = {
        "observations_loaded": observations_total > 0,
        "ranking_top_norms_ready": len(top_normas) > 0,
        "dossiers_top_norms_ready": len(norm_dossiers) > 0,
        "dossiers_with_legal_drilldown": all(bool(d["legal_drilldown_fragments"]) for d in norm_dossiers) if norm_dossiers else False,
        "municipal_pilot_catalog_seeded": int(municipal["totals"]["ordinances_total"]) >= int(municipal["target_pilot_cities"]),
        "municipal_normalization_started": int(municipal["totals"]["normalized_total"]) > 0,
        "municipal_fragment_rows_loaded": int(municipal["totals"]["ordinance_fragments_total"]) > 0,
    }

    if observations_total == 0 and int(municipal["totals"]["ordinances_total"]) == 0:
        status = "failed"
    elif all(
        checks[k]
        for k in (
            "observations_loaded",
            "ranking_top_norms_ready",
            "dossiers_top_norms_ready",
            "dossiers_with_legal_drilldown",
            "municipal_pilot_catalog_seeded",
            "municipal_normalization_started",
            "municipal_fragment_rows_loaded",
        )
    ):
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "methodology": {
            "ranking": {
                "primary_metric": "expediente_count",
                "secondary_metric": "importe_total_eur",
                "incidence_proxy": "incidence_per_1000_observed_cases",
                "population_incidence": "pending_population_denominator",
            },
            "dossier_fields": [
                "conducta_sancionada (tipologias)",
                "volumen",
                "importe",
                "base_legal (norma+fragmentos)",
                "drilldown_sources",
            ],
        },
        "totals": {
            "observations_total": observations_total,
            "observations_with_norm_total": observations_with_norm_total,
            "observations_without_norm_total": observations_without_norm_total,
            "observations_with_norm_expediente_total": observations_with_norm_expediente_total,
            "procedural_metrics_total": int(totals["procedural_metrics_total"] or 0),
            "top_norms_total": len(top_normas),
            "norm_dossiers_total": len(norm_dossiers),
        },
        "coverage": {
            "observations_with_norm_pct": round(
                (observations_with_norm_total / observations_total) if observations_total else 0.0,
                6,
            ),
            "municipal_normalized_pct": municipal["coverage"]["normalized_coverage_pct"],
        },
        "checks": checks,
        "top_normas_sancion_ciudadana": top_normas,
        "norm_dossiers": norm_dossiers,
        "municipal_normalization_progress": municipal,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report status for sanction volume pilot lane")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--dossier-limit", type=int, default=5)
    ap.add_argument("--sample-limit", type=int, default=20)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_status_report(
            conn,
            top_n=int(args.top_n),
            dossier_limit=int(args.dossier_limit),
            sample_limit=int(args.sample_limit),
        )
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
