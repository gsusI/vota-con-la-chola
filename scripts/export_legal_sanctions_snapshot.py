#!/usr/bin/env python3
"""Exporta una instantánea estática para /legal-sanctions en GH Pages.

Objetivos:
- Grafo jurídico normalizado (norma -> norma relacionada con relación tipo).
- Trazabilidad de responsabilidad en fragmentos sancionadores.
- Mapeo tipología de infracción -> norma/base legal.
- Monitoreo de volumen de sanciones (cambios por periodo).
- Drift de KPIs procedimentales.
- Monitoreo de ordenanzas municipales (estado + cobertura mapeo).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from etl.parlamentario_es.db import open_db

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/legal-sanctions/data/legal-sanctions.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot de legal + sanciones para GH Pages")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta SQLite")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta JSON salida")
    p.add_argument("--max-norms", type=int, default=240, help="Máximo de normas incluidas")
    p.add_argument("--max-fragments-per-norm", type=int, default=6, help="Máximo fragmentos por norma en el grafo")
    p.add_argument("--max-lineage-edges", type=int, default=500, help="Máximo de aristas de linaje")
    p.add_argument("--max-infraction-mappings", type=int, default=320, help="Máximo mapeos por tipo de infracción")
    p.add_argument("--max-volume-rows", type=int, default=350, help="Máximo filas de volumen/sanitario")
    p.add_argument("--max-kpi-rows", type=int, default=320, help="Máximo filas de drift de KPI")
    p.add_argument("--max-municipal-rows", type=int, default=220, help="Máximo filas de régimen municipal")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm(value: Any) -> str:
    return str(value or "").strip()


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return default


def to_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def round_float(value: Any, digits: int = 2) -> float | None:
    number = to_float(value, default=None)
    if number is None:
        return None
    return round(number, digits)


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def infer_snapshot_date(conn: sqlite3.Connection) -> str:
    rows = [
        "SELECT MAX(source_snapshot_date) FROM legal_norms",
        "SELECT MAX(source_snapshot_date) FROM sanction_volume_observations",
        "SELECT MAX(source_snapshot_date) FROM sanction_procedural_metrics",
        "SELECT MAX(created_at) FROM sanctions",
    ]

    for sql in rows:
        try:
            row = conn.execute(sql).fetchone()
        except sqlite3.DatabaseError:
            continue
        value = row[0] if row else None
        if value:
            return norm(value)[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_legal_graph(conn: sqlite3.Connection, *, max_norms: int, max_fragments_per_norm: int, max_edges: int) -> dict[str, Any]:
    norms = []
    relation_rows = []
    relation_types: list[str] = []
    node_count = 0
    nodes: list[dict[str, Any]] = []
    relation_type_seen: set[str] = set()

    norm_rows = conn.execute(
        """
        SELECT
          n.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS title,
          COALESCE(n.scope, '') AS scope,
          COALESCE(n.topic_hint, '') AS topic_hint,
          COALESCE(n.effective_date, '') AS effective_date,
          COALESCE(n.published_date, '') AS published_date,
          COALESCE(n.source_url, '') AS source_url,
          COALESCE(n.source_snapshot_date, '') AS source_snapshot_date
        FROM legal_norms n
        ORDER BY
          CASE WHEN TRIM(COALESCE(n.title, '')) <> '' THEN n.title ELSE n.boe_id END ASC,
          n.norm_id ASC
        """
    ).fetchall()

    if max_norms > 0:
        norm_rows = norm_rows[: max_norms]

    if norm_rows:
        norm_ids = [norm(r["norm_id"]) for r in norm_rows]
        id_map = {norm_id: True for norm_id in norm_ids}
        norm_id_params = tuple(norm_ids)

        if norm_id_params:
            fragment_placeholders = ", ".join(["?"] * len(norm_id_params))
            fragment_rows = conn.execute(
                f"""
                SELECT
                  f.norm_id,
                  f.fragment_id,
                  COALESCE(f.fragment_type, '') AS fragment_type,
                  COALESCE(f.fragment_label, '') AS fragment_label,
                  COALESCE(f.fragment_title, '') AS fragment_title,
                  f.fragment_order,
                  f.sanction_amount_min_eur,
                  f.sanction_amount_max_eur,
                  COALESCE(f.competent_body, '') AS competent_body,
                  COALESCE(f.appeal_path, '') AS appeal_path
                FROM legal_norm_fragments f
                WHERE f.norm_id IN ({fragment_placeholders})
                ORDER BY f.norm_id ASC, CAST(f.fragment_order AS INTEGER) ASC, f.fragment_id ASC
                """,
                norm_id_params,
            ).fetchall()
        else:
            fragment_rows = []

        fragments_by_norm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in fragment_rows:
            fragments_by_norm[norm(row["norm_id"])].append(
                {
                    "fragment_id": norm(row["fragment_id"]),
                    "fragment_type": norm(row["fragment_type"]),
                    "fragment_label": norm(row["fragment_label"]),
                    "fragment_title": norm(row["fragment_title"]),
                    "fragment_order": to_int(row["fragment_order"]),
                    "sanction_amount_min_eur": to_float(row["sanction_amount_min_eur"]),
                    "sanction_amount_max_eur": to_float(row["sanction_amount_max_eur"]),
                    "competent_body": norm(row["competent_body"]),
                    "appeal_path": norm(row["appeal_path"]),
                }
            )

        for row in norm_rows:
            norm_id = norm(row["norm_id"])
            norm_fragments = fragments_by_norm.get(norm_id, [])
            if max_fragments_per_norm > 0:
                norm_fragments = norm_fragments[: max_fragments_per_norm]

            if norm_id and id_map.get(norm_id):
                nodes.append(
                    {
                        "norm_id": norm_id,
                        "boe_id": norm(row["boe_id"]),
                        "title": norm(row["title"]),
                        "scope": norm(row["scope"]),
                        "topic_hint": norm(row["topic_hint"]),
                        "effective_date": norm(row["effective_date"]),
                        "published_date": norm(row["published_date"]),
                        "source_snapshot_date": norm(row["source_snapshot_date"]),
                        "source_url": norm(row["source_url"]),
                        "fragments_total": len(norm_fragments),
                        "fragments": norm_fragments,
                    }
                )

        node_count = len(nodes)

        if table_exists(conn, "legal_norm_lineage_edges"):
            if norm_id_params:
                relation_rows = conn.execute(
                    f"""
                    SELECT
                      e.lineage_edge_id,
                      e.norm_id,
                      COALESCE(e.related_norm_id, '') AS related_norm_id,
                      COALESCE(e.relation_type, '') AS relation_type,
                      COALESCE(e.relation_scope, '') AS relation_scope,
                      COALESCE(e.evidence_date, '') AS evidence_date,
                      COALESCE(e.evidence_quote, '') AS evidence_quote,
                      COALESCE(e.source_url, '') AS source_url,
                      COALESCE(n1.boe_id, '') AS source_boe_id,
                      COALESCE(n1.title, '') AS source_title,
                      COALESCE(n2.boe_id, '') AS related_boe_id,
                      COALESCE(n2.title, '') AS related_title
                    FROM legal_norm_lineage_edges e
                    LEFT JOIN legal_norms n1 ON n1.norm_id = e.norm_id
                    LEFT JOIN legal_norms n2 ON n2.norm_id = e.related_norm_id
                    WHERE e.norm_id IN ({fragment_placeholders})
                    ORDER BY e.norm_id ASC, e.related_norm_id ASC, e.lineage_edge_id ASC
                    """,
                    norm_id_params,
                ).fetchall()  # type: ignore[call-overload]
            else:
                relation_rows = []

    if max_edges > 0:
        relation_rows = relation_rows[: max_edges]

    edges = []
    for row in relation_rows:
        rel_type = norm(row["relation_type"])
        if rel_type:
            relation_type_seen.add(rel_type)
        edges.append(
            {
                "lineage_edge_id": to_int(row["lineage_edge_id"]),
                "source_norm_id": norm(row["norm_id"]),
                "source_norm_boe_id": norm(row["source_boe_id"]),
                "source_norm_title": norm(row["source_title"]),
                "related_norm_id": norm(row["related_norm_id"]),
                "related_norm_boe_id": norm(row["related_boe_id"]),
                "related_norm_title": norm(row["related_title"]),
                "relation_type": rel_type,
                "relation_scope": norm(row["relation_scope"]),
                "evidence_date": norm(row["evidence_date"]),
                "source_url": norm(row["source_url"]),
                "evidence_quote": norm(row["evidence_quote"]),
            }
        )

    relation_types = sorted(relation_type_seen)
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": node_count,
        "edge_count": len(edges),
        "relation_types": relation_types,
        "nodes_with_fragments": len([n for n in nodes if n.get("fragments_total") > 0]),
    }

def build_infraction_network(
    conn: sqlite3.Connection,
    *,
    max_mappings_per_infraction: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not table_exists(conn, "sanction_infraction_type_mappings"):
        return [], []

    mapping_rows = conn.execute(
        """
        SELECT
          m.mapping_id,
          m.mapping_key,
          m.infraction_type_id,
          COALESCE(it.label, '') AS infraction_label,
          COALESCE(it.domain, '') AS infraction_domain,
          COALESCE(it.description, '') AS infraction_description,
          COALESCE(it.canonical_unit, '') AS canonical_unit,
          COALESCE(m.norm_id, '') AS norm_id,
          COALESCE(m.fragment_id, '') AS fragment_id,
          COALESCE(m.source_system, '') AS source_system,
          COALESCE(m.source_code, '') AS source_code,
          COALESCE(m.source_label, '') AS source_label,
          COALESCE(m.confidence, 0.0) AS confidence,
          COALESCE(m.source_url, '') AS source_url
        FROM sanction_infraction_type_mappings m
        LEFT JOIN sanction_infraction_types it ON it.infraction_type_id = m.infraction_type_id
        ORDER BY COALESCE(it.label, m.infraction_type_id), COALESCE(m.confidence, 0) DESC, m.mapping_id ASC
        """
    ).fetchall()

    map_totals = conn.execute(
        """
        SELECT
          m.infraction_type_id,
          COALESCE(it.label, '') AS infraction_label,
          COUNT(*) AS mapping_rows,
          COUNT(DISTINCT m.norm_id) AS norms_covered,
          COUNT(DISTINCT m.fragment_id) AS fragments_covered
        FROM sanction_infraction_type_mappings m
        LEFT JOIN sanction_infraction_types it ON it.infraction_type_id = m.infraction_type_id
        GROUP BY m.infraction_type_id, COALESCE(it.label, '')
        ORDER BY mapping_rows DESC, m.infraction_type_id ASC
        """
    ).fetchall()

    totals_by_id: dict[str, dict[str, Any]] = {}
    for row in map_totals:
        inf_id = norm(row["infraction_type_id"])
        if not inf_id:
            continue
        totals_by_id[inf_id] = {
            "infraction_type_id": inf_id,
            "infraction_label": norm(row["infraction_label"]) or inf_id,
            "mapping_rows": to_int(row["mapping_rows"]),
            "norms_covered": to_int(row["norms_covered"]),
            "fragments_covered": to_int(row["fragments_covered"]),
            "obs_expediente_total": 0,
            "obs_importe_total_eur": 0.0,
        }

    if table_exists(conn, "sanction_volume_observations"):
        obs_rows = conn.execute(
            """
            SELECT
              COALESCE(infraction_type_id, '') AS infraction_type_id,
              SUM(COALESCE(expediente_count, 0)) AS expediente_count,
              SUM(COALESCE(importe_total_eur, 0.0)) AS importe_total_eur
            FROM sanction_volume_observations
            GROUP BY infraction_type_id
            """,
        ).fetchall()
        for row in obs_rows:
            inf_id = norm(row["infraction_type_id"])
            if inf_id and inf_id in totals_by_id:
                totals_by_id[inf_id]["obs_expediente_total"] = to_int(row["expediente_count"])
                totals_by_id[inf_id]["obs_importe_total_eur"] = round_float(row["importe_total_eur"], 2) or 0.0

    by_infraction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mapping_rows:
        inf_id = norm(row["infraction_type_id"])
        if not inf_id:
            continue
        by_infraction[inf_id].append(
            {
                "mapping_id": to_int(row["mapping_id"]),
                "mapping_key": norm(row["mapping_key"]),
                "norm_id": norm(row["norm_id"]),
                "fragment_id": norm(row["fragment_id"]),
                "source_system": norm(row["source_system"]),
                "source_code": norm(row["source_code"]),
                "source_label": norm(row["source_label"]),
                "confidence": round_float(row["confidence"], 4),
                "source_url": norm(row["source_url"]),
            }
        )

    infraction_types: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    for inf_id, payload in totals_by_id.items():
        sample = by_infraction.get(inf_id, [])
        if max_mappings_per_infraction > 0:
            sample = sample[:max_mappings_per_infraction]

        infraction_types.append(
            {
                "infraction_type_id": inf_id,
                "infraction_label": payload["infraction_label"],
                "infraction_domain": conn.execute(
                    "SELECT COALESCE(domain, '') FROM sanction_infraction_types WHERE infraction_type_id = ?",
                    (inf_id,),
                ).fetchone()[0]
                if table_exists(conn, "sanction_infraction_types")
                else "",
                "canonical_unit": conn.execute(
                    "SELECT COALESCE(canonical_unit, '') FROM sanction_infraction_types WHERE infraction_type_id = ?",
                    (inf_id,),
                ).fetchone()[0]
                if table_exists(conn, "sanction_infraction_types")
                else "",
                "mapping_rows": to_int(payload["mapping_rows"]),
                "norms_covered": to_int(payload["norms_covered"]),
                "fragments_covered": to_int(payload["fragments_covered"]),
                "obs_expediente_total": to_int(payload["obs_expediente_total"]),
                "obs_importe_total_eur": round_float(payload["obs_importe_total_eur"], 2) or 0.0,
            }
        )

        for mapping in sample:
            row = dict(mapping)
            row["infraction_type_id"] = inf_id
            row["infraction_label"] = payload["infraction_label"]
            mappings.append(row)

    infraction_types.sort(key=lambda item: (-(to_int(item["mapping_rows"])), item["infraction_label"]))
    mappings.sort(key=lambda row: (row["infraction_label"], to_float(row.get("confidence"), 0.0) or 0), reverse=True)

    return infraction_types, mappings


def build_volume_monitoring(
    conn: sqlite3.Connection,
    *,
    max_rows: int,
) -> dict[str, Any]:
    if not table_exists(conn, "sanction_volume_observations"):
        return {
            "series": [],
            "source_totals": [],
            "sources": [],
            "periods": [],
        }

    rows = conn.execute(
        """
        SELECT
          o.sanction_source_id,
          COALESCE(s.label, '') AS source_label,
          COALESCE(s.admin_scope, '') AS admin_scope,
          COALESCE(s.territory_scope, '') AS territory_scope,
          o.period_granularity,
          o.period_date,
          o.territory_id,
          COALESCE(t.name, '') AS territory_name,
          SUM(COALESCE(o.expediente_count, 0)) AS expediente_count,
          SUM(COALESCE(o.importe_total_eur, 0.0)) AS importe_total_eur,
          SUM(COALESCE(o.importe_medio_eur, 0.0)) AS importe_medio_eur,
          SUM(COALESCE(o.recurso_presentado_count, 0)) AS recurso_presentado_count,
          SUM(COALESCE(o.recurso_estimado_count, 0)) AS recurso_estimado_count,
          SUM(COALESCE(o.recurso_desestimado_count, 0)) AS recurso_desestimado_count
        FROM sanction_volume_observations o
        LEFT JOIN sanction_volume_sources s ON s.sanction_source_id = o.sanction_source_id
        LEFT JOIN territories t ON t.territory_id = o.territory_id
        GROUP BY
          o.sanction_source_id,
          source_label,
          admin_scope,
          territory_scope,
          o.period_granularity,
          o.period_date,
          o.territory_id,
          territory_name
        ORDER BY o.sanction_source_id ASC, o.period_granularity ASC, o.period_date ASC, COALESCE(territory_name, '')
        """
    ).fetchall()

    source_map: dict[str, Any] = {}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        source_id = norm(row["sanction_source_id"])
        if not source_id:
            continue
        period_key = (source_id, norm(row["period_granularity"]), norm(row["territory_id"] or ""))
        item = {
            "sanction_source_id": source_id,
            "source_label": norm(row["source_label"]),
            "admin_scope": norm(row["admin_scope"]),
            "territory_scope": norm(row["territory_scope"]),
            "period_granularity": norm(row["period_granularity"]),
            "period_date": norm(row["period_date"]),
            "territory_id": to_int(row["territory_id"]),
            "territory_name": norm(row["territory_name"]),
            "expediente_count": to_int(row["expediente_count"]),
            "importe_total_eur": round_float(row["importe_total_eur"], 2) or 0.0,
            "importe_medio_eur": round_float(row["importe_medio_eur"], 2) or 0.0,
            "recurso_presentado_count": to_int(row["recurso_presentado_count"]),
            "recurso_estimado_count": to_int(row["recurso_estimado_count"]),
            "recurso_desestimado_count": to_int(row["recurso_desestimado_count"]),
        }
        grouped[period_key].append(item)

        if source_id not in source_map:
            source_map[source_id] = {
                "source_id": source_id,
                "label": norm(row["source_label"]),
                "admin_scope": norm(row["admin_scope"]),
                "territory_scope": norm(row["territory_scope"]),
            }

    series: list[dict[str, Any]] = []
    for point_key, samples in grouped.items():
        if max_rows > 0 and len(series) >= max_rows:
            break
        samples.sort(key=lambda item: item["period_date"])
        prev_item: dict[str, Any] | None = None
        for item in samples:
            if max_rows > 0 and len(series) >= max_rows:
                break
            if prev_item:
                prev_exp = to_int(prev_item["expediente_count"])
                prev_imp = to_float(prev_item["importe_total_eur"]) or 0.0
                cur_exp = to_int(item["expediente_count"])
                cur_imp = to_float(item["importe_total_eur"]) or 0.0
                delta_exp = cur_exp - prev_exp
                delta_imp = round_float(cur_imp - prev_imp, 2) or 0.0
                delta_exp_pct = None if prev_exp == 0 else round((delta_exp / prev_exp) * 100.0, 2)
                delta_imp_pct = None if prev_imp == 0 else round((delta_imp / prev_imp) * 100.0, 2)
                item["delta_expediente_count"] = delta_exp
                item["delta_expediente_pct"] = delta_exp_pct
                item["delta_importe_total_eur"] = delta_imp
                item["delta_importe_total_pct"] = delta_imp_pct
            else:
                item["delta_expediente_count"] = 0
                item["delta_expediente_pct"] = 0.0
                item["delta_importe_total_eur"] = 0.0
                item["delta_importe_total_pct"] = 0.0

            series.append(item)
            prev_item = item

    source_totals = conn.execute(
        """
        SELECT
          o.sanction_source_id,
          COALESCE(s.label, '') AS source_label,
          COALESCE(s.admin_scope, '') AS admin_scope,
          SUM(COALESCE(o.expediente_count, 0)) AS expediente_count,
          SUM(COALESCE(o.importe_total_eur, 0.0)) AS importe_total_eur,
          SUM(COALESCE(o.recurso_presentado_count, 0)) AS recurso_presentado_count,
          SUM(COALESCE(o.recurso_estimado_count, 0)) AS recurso_estimado_count,
          SUM(COALESCE(o.recurso_desestimado_count, 0)) AS recurso_desestimado_count
        FROM sanction_volume_observations o
        LEFT JOIN sanction_volume_sources s ON s.sanction_source_id = o.sanction_source_id
        GROUP BY o.sanction_source_id, source_label, admin_scope
        ORDER BY expediente_count DESC, source_label ASC
        """
    ).fetchall()

    periods_rows = conn.execute(
        """
        SELECT DISTINCT period_granularity, period_date
        FROM sanction_volume_observations
        ORDER BY period_granularity ASC, period_date ASC
        """
    ).fetchall()

    return {
        "series": series,
        "source_totals": [
            {
                "source_id": norm(row["sanction_source_id"]),
                "label": norm(row["source_label"]),
                "admin_scope": norm(row["admin_scope"]),
                "expediente_count": to_int(row["expediente_count"]),
                "importe_total_eur": round_float(row["importe_total_eur"], 2) or 0.0,
                "recurso_presentado_count": to_int(row["recurso_presentado_count"]),
                "recurso_estimado_count": to_int(row["recurso_estimado_count"]),
                "recurso_desestimado_count": to_int(row["recurso_desestimado_count"]),
            }
            for row in source_totals
        ],
        "sources": sorted(
            [
                {
                    "source_id": norm(item["source_id"]),
                    "label": norm(item["label"]),
                    "admin_scope": norm(item["admin_scope"]),
                    "territory_scope": norm(item["territory_scope"]),
                }
                for item in source_map.values()
            ],
            key=lambda item: item["source_id"],
        ),
        "periods": [
            {"period_granularity": norm(r["period_granularity"]), "period_date": norm(r["period_date"])}
            for r in periods_rows
        ],
    }


def build_kpi_drift(conn: sqlite3.Connection, *, max_rows: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "sanction_procedural_metrics"):
        return []

    rows = conn.execute(
        """
        SELECT
          m.kpi_id,
          COALESCE(k.label, '') AS kpi_label,
          COALESCE(k.target_direction, '') AS target_direction,
          COALESCE(m.sanction_source_id, '') AS sanction_source_id,
          COALESCE(s.label, '') AS source_label,
          COALESCE(m.period_granularity, '') AS period_granularity,
          COALESCE(m.period_date, '') AS period_date,
          COALESCE(m.territory_id, '') AS territory_id,
          COALESCE(t.name, '') AS territory_name,
          m.value,
          m.numerator,
          m.denominator,
          COALESCE(m.source_url, '') AS source_url,
          COALESCE(m.evidence_date, '') AS evidence_date
        FROM sanction_procedural_metrics m
        LEFT JOIN sanction_procedural_kpi_definitions k ON k.kpi_id = m.kpi_id
        LEFT JOIN sanction_volume_sources s ON s.sanction_source_id = m.sanction_source_id
        LEFT JOIN territories t ON t.territory_id = m.territory_id
        ORDER BY m.kpi_id ASC, m.sanction_source_id ASC, m.period_granularity ASC, m.period_date ASC, COALESCE(territory_name, '')
        """
    ).fetchall()

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    out: list[dict[str, Any]] = []

    for row in rows:
        kpi_id = norm(row["kpi_id"])
        source_id = norm(row["sanction_source_id"])
        if not kpi_id or not source_id:
            continue
        key = (kpi_id, source_id, norm(row["period_granularity"]), norm(row["territory_id"]))
        value = {
            "kpi_id": kpi_id,
            "kpi_label": norm(row["kpi_label"]),
            "target_direction": norm(row["target_direction"]),
            "sanction_source_id": source_id,
            "source_label": norm(row["source_label"]),
            "period_granularity": norm(row["period_granularity"]),
            "period_date": norm(row["period_date"]),
            "territory_id": to_int(row["territory_id"]),
            "territory_name": norm(row["territory_name"]),
            "value": round_float(row["value"], 6),
            "numerator": to_float(row["numerator"], 0.0),
            "denominator": to_float(row["denominator"], 0.0),
            "source_url": norm(row["source_url"]),
            "evidence_date": norm(row["evidence_date"]),
        }
        grouped[key].append(value)

    for key, point_rows in grouped.items():
        if len(out) >= max_rows:
            break
        point_rows.sort(key=lambda item: item["period_date"])
        prev: dict[str, Any] | None = None
        for item in point_rows:
            if len(out) >= max_rows:
                break
            current = to_float(item["value"]) or 0.0
            if prev:
                prev_value = to_float(prev["value"]) or 0.0
                delta = current - prev_value
                delta_pct = None if prev_value == 0 else round((delta / prev_value) * 100.0, 2)
                item["delta_value"] = round(delta, 6)
                item["delta_value_pct"] = delta_pct
            else:
                item["delta_value"] = 0.0
                item["delta_value_pct"] = 0.0
            out.append(item)
            prev = item

    return out


def build_responsibility_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    if not table_exists(conn, "legal_fragment_responsibilities"):
        return {"roles": [], "top_actors": [], "rows_with_primary_evidence": 0, "rows_total": 0}

    roles_rows = conn.execute(
        """
        SELECT COALESCE(r.role, '') AS role, COUNT(*) AS n
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        GROUP BY COALESCE(r.role, '')
        ORDER BY n DESC, role ASC
        """
    ).fetchall()

    actor_rows = conn.execute(
        """
        SELECT COALESCE(r.actor_label, '') AS actor_label, COUNT(*) AS n
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        WHERE COALESCE(r.actor_label, '') <> ''
        GROUP BY COALESCE(r.actor_label, '')
        ORDER BY n DESC, actor_label ASC
        LIMIT 10
        """
    ).fetchall()

    evidence_with_text = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        WHERE COALESCE(TRIM(r.source_url), '') <> ''
          AND COALESCE(TRIM(r.actor_label), '') <> ''
          AND COALESCE(TRIM(r.evidence_date), '') <> ''
          AND COALESCE(TRIM(r.evidence_quote), '') <> ''
        """
    ).fetchone()

    total = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        """
    ).fetchone()

    return {
        "roles": [{"role": norm(row["role"]) or "sin-rol", "rows": to_int(row["n"])} for row in roles_rows],
        "top_actors": [{"actor_label": norm(row["actor_label"]), "rows": to_int(row["n"])} for row in actor_rows],
        "rows_with_primary_evidence": to_int(evidence_with_text["n"] if evidence_with_text else 0),
        "rows_total": to_int(total["n"] if total else 0),
    }


def build_municipal_monitoring(conn: sqlite3.Connection, *, max_rows: int) -> dict[str, Any]:
    if not table_exists(conn, "sanction_municipal_ordinances"):
        return {"summary": {}, "city_summary": [], "ordinance_rows": []}

    totals = conn.execute(
        """
        SELECT
          COUNT(*) AS total_ordinances,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'normalized' THEN 1 ELSE 0 END) AS normalized_ordinances,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'identified' THEN 1 ELSE 0 END) AS identified_ordinances,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'blocked' THEN 1 ELSE 0 END) AS blocked_ordinances
        FROM sanction_municipal_ordinances
        """
    ).fetchone()

    city_rows = conn.execute(
        """
        SELECT
          COALESCE(city_name, '') AS city_name,
          COALESCE(province_name, '') AS province_name,
          COUNT(*) AS ordinances_total,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'normalized' THEN 1 ELSE 0 END) AS normalized_total,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'identified' THEN 1 ELSE 0 END) AS identified_total,
          SUM(CASE WHEN COALESCE(ordinance_status, '') = 'blocked' THEN 1 ELSE 0 END) AS blocked_total
        FROM sanction_municipal_ordinances
        GROUP BY COALESCE(city_name, ''), COALESCE(province_name, '')
        ORDER BY ordinances_total DESC, city_name ASC
        LIMIT 30
        """
    ).fetchall()

    ordinances = conn.execute(
        """
        SELECT
          o.ordinance_id,
          COALESCE(o.city_name, '') AS city_name,
          COALESCE(o.province_name, '') AS province_name,
          COALESCE(o.ordinance_label, '') AS ordinance_label,
          COALESCE(o.ordinance_status, '') AS ordinance_status,
          COALESCE(o.publication_date, '') AS publication_date,
          COALESCE(o.ordinance_url, '') AS ordinance_url,
          COUNT(f.ordinance_fragment_id) AS fragments_total,
          SUM(CASE WHEN COALESCE(f.mapped_norm_id, '') <> '' THEN 1 ELSE 0 END) AS mapped_norm_fragments,
          SUM(CASE WHEN COALESCE(f.mapped_fragment_id, '') <> '' THEN 1 ELSE 0 END) AS mapped_fragment_rows
        FROM sanction_municipal_ordinances o
        LEFT JOIN sanction_municipal_ordinance_fragments f ON f.ordinance_id = o.ordinance_id
        GROUP BY
          o.ordinance_id,
          o.city_name,
          o.province_name,
          o.ordinance_label,
          o.ordinance_status,
          o.publication_date,
          o.ordinance_url
        ORDER BY o.ordinance_status ASC, o.city_name ASC, o.ordinance_label ASC
        """
    ).fetchall()

    if max_rows > 0:
        ordinances = ordinances[:max_rows]

    status_counts = []
    for row in conn.execute(
        """
        SELECT COALESCE(ordinance_status, '') AS status, COUNT(*) AS total
        FROM sanction_municipal_ordinances
        GROUP BY COALESCE(ordinance_status, '')
        ORDER BY total DESC
        """
    ).fetchall():
        status_counts.append(
            {
                "status": norm(row["status"]) or "sin-estado",
                "total": to_int(row["total"]),
            }
        )

    return {
        "summary": {
            "total_ordinances": to_int(totals["total_ordinances"] if totals else 0),
            "normalized_ordinances": to_int(totals["normalized_ordinances"] if totals else 0),
            "identified_ordinances": to_int(totals["identified_ordinances"] if totals else 0),
            "blocked_ordinances": to_int(totals["blocked_ordinances"] if totals else 0),
            "status_counts": status_counts,
        },
        "city_summary": [
            {
                "city_name": norm(row["city_name"]),
                "province_name": norm(row["province_name"]),
                "ordinances_total": to_int(row["ordinances_total"]),
                "normalized_total": to_int(row["normalized_total"]),
                "identified_total": to_int(row["identified_total"]),
                "blocked_total": to_int(row["blocked_total"]),
            }
            for row in city_rows
        ],
        "ordinance_rows": [
            {
                "ordinance_id": norm(row["ordinance_id"]),
                "city_name": norm(row["city_name"]),
                "province_name": norm(row["province_name"]),
                "ordinance_label": norm(row["ordinance_label"]),
                "ordinance_status": norm(row["ordinance_status"]) or "sin-estado",
                "publication_date": norm(row["publication_date"]),
                "ordinance_url": norm(row["ordinance_url"]),
                "fragments_total": to_int(row["fragments_total"]),
                "mapped_norm_fragments": to_int(row["mapped_norm_fragments"]),
                "mapped_fragment_rows": to_int(row["mapped_fragment_rows"]),
            }
            for row in ordinances
        ],
    }


def build_liberty_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    if not table_exists(conn, "liberty_restriction_assessments"):
        return {"enabled": False, "rows": 0}

    totals = conn.execute(
        """
        SELECT
          COUNT(*) AS rows,
          MIN(assessment_key) AS first_key,
          MAX(assessment_key) AS last_key,
          AVG(COALESCE(irlc_score, 0.0)) AS avg_irlc_score,
          AVG(COALESCE(confidence, 0.0)) AS avg_confidence
        FROM liberty_restriction_assessments
        """
    ).fetchone()

    methods = conn.execute(
        """
        SELECT COALESCE(method_version, '') AS method_version, COUNT(*) AS total
        FROM liberty_restriction_assessments
        GROUP BY COALESCE(method_version, '')
        ORDER BY total DESC, method_version ASC
        """
    ).fetchall()

    return {
        "enabled": True,
        "rows": to_int(totals["rows"] if totals else 0),
        "sample_first_key": norm(totals["first_key"]),
        "sample_last_key": norm(totals["last_key"]),
        "avg_irlc_score": round_float(totals["avg_irlc_score"], 4) if totals else None,
        "avg_confidence": round_float(totals["avg_confidence"], 4) if totals else None,
        "method_distribution": [{"method_version": norm(row["method_version"]) or "unknown", "total": to_int(row["total"])} for row in methods],
    }


def build_snapshot(conn: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    legal_graph = build_legal_graph(
        conn,
        max_norms=max(0, int(args.max_norms)),
        max_fragments_per_norm=max(0, int(args.max_fragments_per_norm)),
        max_edges=max(0, int(args.max_lineage_edges)),
    )
    infraction_types, infraction_mappings = build_infraction_network(
        conn,
        max_mappings_per_infraction=max(0, int(args.max_infraction_mappings)),
    )
    volume_monitoring = build_volume_monitoring(
        conn,
        max_rows=max(0, int(args.max_volume_rows)),
    )
    kpi_drift = build_kpi_drift(
        conn,
        max_rows=max(0, int(args.max_kpi_rows)),
    )
    municipal = build_municipal_monitoring(
        conn,
        max_rows=max(0, int(args.max_municipal_rows)),
    )

    source_ids = set()
    relation_types = set(legal_graph.get("relation_types", []))
    for row in infraction_mappings:
        if row.get("source_system"):
            source_ids.add(norm(row["source_system"]))
    for row in volume_monitoring.get("source_totals", []):
        source_ids.add(norm(row["source_id"]))

    return {
        "generated_at": now_utc_iso(),
        "snapshot_date": infer_snapshot_date(conn),
        "schema_version": "legal_sanctions_snapshot_v1",
        "meta": {
            "norm_nodes": legal_graph["node_count"],
            "lineage_edges": legal_graph["edge_count"],
            "infraction_type_count": len(infraction_types),
            "infraction_mappings": len(infraction_mappings),
            "volume_rows": len(volume_monitoring.get("series", [])),
            "kpi_rows": len(kpi_drift),
            "municipal_rows": len(municipal.get("ordinance_rows", [])),
        },
        "filters": {
            "source_ids": sorted(source_ids),
            "relation_types": sorted(relation_types),
            "infraction_type_ids": sorted([row["infraction_type_id"] for row in infraction_types]),
            "kpi_ids": sorted({row["kpi_id"] for row in kpi_drift}),
            "periods": sorted(volume_monitoring.get("periods", []), key=lambda item: (item["period_granularity"], item["period_date"])),
        },
        "legal_graph": legal_graph,
        "infraction_network": {
            "infraction_types": infraction_types,
            "mappings": infraction_mappings,
        },
        "sanction_volume_monitoring": volume_monitoring,
        "procedural_kpi_drift": kpi_drift,
        "municipal_monitoring": municipal,
        "responsibility_summary": build_responsibility_summary(conn),
        "liberty_restriction_monitoring": build_liberty_snapshot(conn),
    }


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    conn = open_db(Path(args.db))
    try:
        snapshot = build_snapshot(conn, args)
    finally:
        conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
