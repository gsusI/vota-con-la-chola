#!/usr/bin/env python3
"""Export snapshot artifact for liberty restrictions atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.report_liberty_delegated_enforcement_status import build_status_report as build_delegated_status
from scripts.report_liberty_direct_accountability_scores import build_status_report as build_accountability_status
from scripts.report_liberty_enforcement_variation_status import build_status_report as build_enforcement_status
from scripts.report_liberty_indirect_accountability_status import build_status_report as build_indirect_status
from scripts.report_liberty_personal_accountability_scores import (
    build_status_report as build_personal_accountability_status,
)

IRLC_PARQUET_FIELDS: tuple[tuple[str, str], ...] = (
    ("assessment_key", "string"),
    ("fragment_id", "string"),
    ("norm_id", "string"),
    ("boe_id", "string"),
    ("norm_title", "string"),
    ("fragment_type", "string"),
    ("fragment_label", "string"),
    ("competent_body", "string"),
    ("appeal_path", "string"),
    ("right_category_id", "string"),
    ("right_label", "string"),
    ("method_version", "string"),
    ("reach_score", "float"),
    ("intensity_score", "float"),
    ("due_process_risk_score", "float"),
    ("reversibility_risk_score", "float"),
    ("discretionality_score", "float"),
    ("compliance_cost_score", "float"),
    ("irlc_score", "float"),
    ("confidence", "float"),
    ("source_url", "string"),
)

ACCOUNTABILITY_PARQUET_FIELDS: tuple[tuple[str, str], ...] = (
    ("fragment_id", "string"),
    ("norm_id", "string"),
    ("boe_id", "string"),
    ("norm_title", "string"),
    ("role", "string"),
    ("actor_label", "string"),
    ("evidence_date", "string"),
    ("source_url", "string"),
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def build_snapshot(conn: sqlite3.Connection, *, snapshot_date: str) -> dict[str, Any]:
    restrictions_rows = conn.execute(
        """
        SELECT
          a.assessment_key,
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_type, '') AS fragment_type,
          COALESCE(f.fragment_label, '') AS fragment_label,
          COALESCE(f.competent_body, '') AS competent_body,
          COALESCE(f.appeal_path, '') AS appeal_path,
          a.right_category_id,
          COALESCE(c.label, '') AS right_label,
          a.method_version,
          a.reach_score,
          a.intensity_score,
          a.due_process_risk_score,
          a.reversibility_risk_score,
          a.discretionality_score,
          a.compliance_cost_score,
          a.irlc_score,
          a.confidence,
          COALESCE(a.source_url, '') AS source_url
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_right_categories c ON c.right_category_id = a.right_category_id
        ORDER BY a.irlc_score DESC, a.fragment_id ASC
        """
    ).fetchall()

    restrictions = [
        {
            "assessment_key": _norm(row["assessment_key"]),
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_type": _norm(row["fragment_type"]),
            "fragment_label": _norm(row["fragment_label"]),
            "competent_body": _norm(row["competent_body"]),
            "appeal_path": _norm(row["appeal_path"]),
            "right_category_id": _norm(row["right_category_id"]),
            "right_label": _norm(row["right_label"]),
            "method_version": _norm(row["method_version"]),
            "scores": {
                "reach_score": float(row["reach_score"] or 0.0),
                "intensity_score": float(row["intensity_score"] or 0.0),
                "due_process_risk_score": float(row["due_process_risk_score"] or 0.0),
                "reversibility_risk_score": float(row["reversibility_risk_score"] or 0.0),
                "discretionality_score": float(row["discretionality_score"] or 0.0),
                "compliance_cost_score": float(row["compliance_cost_score"] or 0.0),
                "irlc_score": float(row["irlc_score"] or 0.0),
            },
            "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            "source_url": _norm(row["source_url"]),
        }
        for row in restrictions_rows
    ]

    accountability_rows = conn.execute(
        """
        SELECT
          r.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          r.role,
          COALESCE(r.actor_label, '') AS actor_label,
          COALESCE(r.evidence_date, '') AS evidence_date,
          COALESCE(r.source_url, '') AS source_url
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY r.fragment_id ASC, r.role ASC, r.actor_label ASC
        """
    ).fetchall()

    accountability_edges = [
        {
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "role": _norm(row["role"]),
            "actor_label": _norm(row["actor_label"]),
            "evidence_date": _norm(row["evidence_date"]),
            "source_url": _norm(row["source_url"]),
        }
        for row in accountability_rows
    ]

    proportionality_rows = conn.execute(
        """
        SELECT
          p.review_key,
          p.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          p.method_version,
          p.objective_defined,
          p.indicator_defined,
          p.alternatives_less_restrictive_considered,
          p.sunset_review_present,
          p.observed_effectiveness_score,
          p.necessity_score,
          p.proportionality_score,
          p.assessment_label,
          p.confidence,
          COALESCE(p.source_url, '') AS source_url
        FROM liberty_proportionality_reviews p
        JOIN legal_norm_fragments f ON f.fragment_id = p.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY p.proportionality_score ASC, p.fragment_id ASC
        """
    ).fetchall()
    proportionality_reviews = [
        {
            "review_key": _norm(row["review_key"]),
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_label": _norm(row["fragment_label"]),
            "method_version": _norm(row["method_version"]),
            "objective_defined": int(row["objective_defined"] or 0),
            "indicator_defined": int(row["indicator_defined"] or 0),
            "alternatives_less_restrictive_considered": int(row["alternatives_less_restrictive_considered"] or 0),
            "sunset_review_present": int(row["sunset_review_present"] or 0),
            "observed_effectiveness_score": float(row["observed_effectiveness_score"] or 0.0),
            "necessity_score": float(row["necessity_score"] or 0.0),
            "proportionality_score": float(row["proportionality_score"] or 0.0),
            "assessment_label": _norm(row["assessment_label"]),
            "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            "source_url": _norm(row["source_url"]),
        }
        for row in proportionality_rows
    ]

    accountability_report = build_accountability_status(conn, top_n=200, direct_coverage_min=0.6)
    enforcement_report = build_enforcement_status(
        conn,
        top_n=200,
        sanction_rate_spread_pct_min=0.35,
        annulment_rate_spread_pp_min=0.08,
        delay_spread_days_min=45.0,
        target_coverage_min=0.6,
        multi_territory_coverage_min=0.6,
    )
    indirect_report = build_indirect_status(
        conn,
        top_n=200,
        attributable_confidence_min=0.55,
        attributable_max_causal_distance=2,
        attributable_fragment_coverage_min=0.5,
    )
    personal_accountability_report = build_personal_accountability_status(
        conn,
        top_n=200,
        personal_confidence_min=0.55,
        personal_max_causal_distance=2,
        personal_fragment_coverage_min=0.5,
        personal_primary_evidence_min_pct=1.0,
        min_personal_primary_evidence_edges=1,
        indirect_person_window_min_pct=1.0,
        min_indirect_person_window_edges=1,
        min_persons_scored=1,
    )
    indirect_rows = conn.execute(
        """
        SELECT
          e.edge_key,
          e.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          e.method_version,
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
        ORDER BY e.edge_confidence DESC, e.causal_distance ASC, e.fragment_id ASC
        """
    ).fetchall()
    indirect_accountability_edges = [
        {
            "edge_key": _norm(row["edge_key"]),
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_label": _norm(row["fragment_label"]),
            "method_version": _norm(row["method_version"]),
            "actor_label": _norm(row["actor_label"]),
            "actor_person_name": _norm(row["actor_person_name"]),
            "actor_role_title": _norm(row["actor_role_title"]),
            "role": _norm(row["role"]),
            "direct_actor_label": _norm(row["direct_actor_label"]),
            "appointment_start_date": _norm(row["appointment_start_date"]),
            "appointment_end_date": _norm(row["appointment_end_date"]),
            "causal_distance": int(row["causal_distance"] or 0),
            "edge_confidence": float(row["edge_confidence"] or 0.0),
            "evidence_date": _norm(row["evidence_date"]),
            "source_url": _norm(row["source_url"]),
        }
        for row in indirect_rows
    ]
    delegated_report = build_delegated_status(
        conn,
        top_n=200,
        target_fragment_coverage_min=0.6,
        designated_actor_coverage_min=0.5,
        enforcement_evidence_coverage_min=0.7,
    )
    delegated_rows = conn.execute(
        """
        SELECT
          l.link_key,
          l.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          l.method_version,
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
        """
    ).fetchall()
    delegated_enforcement_links = [
        {
            "link_key": _norm(row["link_key"]),
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_label": _norm(row["fragment_label"]),
            "method_version": _norm(row["method_version"]),
            "delegating_actor_label": _norm(row["delegating_actor_label"]),
            "delegated_institution_label": _norm(row["delegated_institution_label"]),
            "designated_role_title": _norm(row["designated_role_title"]),
            "designated_actor_label": _norm(row["designated_actor_label"]),
            "appointment_start_date": _norm(row["appointment_start_date"]),
            "appointment_end_date": _norm(row["appointment_end_date"]),
            "enforcement_action_label": _norm(row["enforcement_action_label"]),
            "enforcement_evidence_date": _norm(row["enforcement_evidence_date"]),
            "chain_confidence": float(row["chain_confidence"] or 0.0),
            "source_url": _norm(row["source_url"]),
        }
        for row in delegated_rows
    ]

    return {
        "generated_at": now_utc_iso(),
        "snapshot_date": snapshot_date,
        "schema_version": "liberty_restrictions_snapshot_v1",
        "totals": {
            "restrictions_total": len(restrictions),
            "accountability_edges_total": len(accountability_edges),
            "proportionality_reviews_total": len(proportionality_reviews),
            "actors_scored_total": int(accountability_report.get("totals", {}).get("actors_scored_total", 0)),
            "persons_scored_total": int(personal_accountability_report.get("totals", {}).get("persons_scored_total", 0)),
            "enforcement_observations_total": int(enforcement_report.get("totals", {}).get("observations_total", 0)),
            "indirect_edges_total": int(indirect_report.get("totals", {}).get("edges_total", 0)),
            "indirect_attributable_edges_total": int(indirect_report.get("totals", {}).get("attributable_edges_total", 0)),
            "delegated_links_total": int(delegated_report.get("totals", {}).get("links_total", 0)),
            "fragments_with_delegated_chain_total": int(
                delegated_report.get("totals", {}).get("fragments_with_links_total", 0)
            ),
        },
        "restrictions": restrictions,
        "accountability_edges": accountability_edges,
        "proportionality_reviews": proportionality_reviews,
        "accountability_scores": accountability_report.get("top_actor_scores", []),
        "accountability_methodology": accountability_report.get("methodology", {}),
        "personal_accountability_scores": personal_accountability_report.get("top_person_scores", []),
        "personal_accountability_methodology": personal_accountability_report.get("methodology", {}),
        "personal_accountability_summary": personal_accountability_report,
        "enforcement_variation": enforcement_report,
        "indirect_accountability_edges": indirect_accountability_edges,
        "indirect_accountability_summary": indirect_report,
        "delegated_enforcement_links": delegated_enforcement_links,
        "delegated_enforcement_summary": delegated_report,
    }


def build_irlc_parquet_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _safe_list(snapshot.get("restrictions")):
        row = _safe_obj(item)
        scores = _safe_obj(row.get("scores"))
        rows.append(
            {
                "assessment_key": _norm(row.get("assessment_key")),
                "fragment_id": _norm(row.get("fragment_id")),
                "norm_id": _norm(row.get("norm_id")),
                "boe_id": _norm(row.get("boe_id")),
                "norm_title": _norm(row.get("norm_title")),
                "fragment_type": _norm(row.get("fragment_type")),
                "fragment_label": _norm(row.get("fragment_label")),
                "competent_body": _norm(row.get("competent_body")),
                "appeal_path": _norm(row.get("appeal_path")),
                "right_category_id": _norm(row.get("right_category_id")),
                "right_label": _norm(row.get("right_label")),
                "method_version": _norm(row.get("method_version")),
                "reach_score": scores.get("reach_score"),
                "intensity_score": scores.get("intensity_score"),
                "due_process_risk_score": scores.get("due_process_risk_score"),
                "reversibility_risk_score": scores.get("reversibility_risk_score"),
                "discretionality_score": scores.get("discretionality_score"),
                "compliance_cost_score": scores.get("compliance_cost_score"),
                "irlc_score": scores.get("irlc_score"),
                "confidence": row.get("confidence"),
                "source_url": _norm(row.get("source_url")),
            }
        )
    return rows


def build_accountability_parquet_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _safe_list(snapshot.get("accountability_edges")):
        row = _safe_obj(item)
        rows.append(
            {
                "fragment_id": _norm(row.get("fragment_id")),
                "norm_id": _norm(row.get("norm_id")),
                "boe_id": _norm(row.get("boe_id")),
                "norm_title": _norm(row.get("norm_title")),
                "role": _norm(row.get("role")),
                "actor_label": _norm(row.get("actor_label")),
                "evidence_date": _norm(row.get("evidence_date")),
                "source_url": _norm(row.get("source_url")),
            }
        )
    return rows


def _coerce_field(value: Any, kind: str) -> Any:
    if kind == "string":
        return _norm(value)
    if value is None or _norm(value) == "":
        return None
    if kind == "float":
        try:
            return float(value)
        except Exception:  # noqa: BLE001
            return None
    if kind == "int":
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return None
    return value


def _pyarrow_type(pa_mod: Any, kind: str) -> Any:
    if kind == "string":
        return pa_mod.string()
    if kind == "float":
        return pa_mod.float64()
    if kind == "int":
        return pa_mod.int64()
    return pa_mod.string()


def write_parquet_table(
    rows: list[dict[str, Any]],
    *,
    out_path: Path,
    fields: tuple[tuple[str, str], ...],
    compression: str = "zstd",
) -> dict[str, Any]:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pyarrow no esta instalado; no se puede exportar parquet") from exc

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        rec: dict[str, Any] = {}
        for name, kind in fields:
            rec[name] = _coerce_field(row.get(name), kind)
        normalized_rows.append(rec)

    schema = pa.schema([pa.field(name, _pyarrow_type(pa, kind)) for name, kind in fields])
    if normalized_rows:
        table = pa.Table.from_pylist(normalized_rows, schema=schema)
    else:
        arrays = [pa.array([], type=field.type) for field in schema]
        table = pa.Table.from_arrays(arrays, schema=schema)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, compression=compression)
    return {
        "path": str(out_path),
        "rows": int(table.num_rows),
        "columns": [name for name, _ in fields],
        "compression": compression,
    }


def _stable_row_hash(row: Any) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ids_for_section(snapshot: dict[str, Any], section: str) -> set[str]:
    values = _safe_list(snapshot.get(section))
    ids: set[str] = set()
    if section == "restrictions":
        for row_any in values:
            row = _safe_obj(row_any)
            token = _norm(row.get("assessment_key"))
            if token:
                ids.add(token)
        return ids
    if section == "accountability_edges":
        for row_any in values:
            row = _safe_obj(row_any)
            token = "|".join(
                [
                    _norm(row.get("fragment_id")),
                    _norm(row.get("role")),
                    _norm(row.get("actor_label")),
                    _norm(row.get("evidence_date")),
                    _norm(row.get("source_url")),
                ]
            )
            if token:
                ids.add(token)
        return ids
    if section == "proportionality_reviews":
        for row_any in values:
            row = _safe_obj(row_any)
            token = _norm(row.get("review_key"))
            if token:
                ids.add(token)
        return ids
    if section == "indirect_accountability_edges":
        for row_any in values:
            row = _safe_obj(row_any)
            token = _norm(row.get("edge_key"))
            if token:
                ids.add(token)
        return ids
    if section == "delegated_enforcement_links":
        for row_any in values:
            row = _safe_obj(row_any)
            token = _norm(row.get("link_key"))
            if token:
                ids.add(token)
        return ids
    if section == "accountability_scores":
        for row_any in values:
            row = _safe_obj(row_any)
            if row:
                ids.add(_stable_row_hash(row))
        return ids
    if section == "personal_accountability_scores":
        for row_any in values:
            row = _safe_obj(row_any)
            if row:
                ids.add(_stable_row_hash(row))
        return ids
    for row_any in values:
        row = _safe_obj(row_any)
        if row:
            ids.add(_stable_row_hash(row))
    return ids


def _snapshot_contract_sections(snapshot: dict[str, Any]) -> dict[str, set[str]]:
    sections = (
        "restrictions",
        "accountability_edges",
        "proportionality_reviews",
        "accountability_scores",
        "personal_accountability_scores",
        "indirect_accountability_edges",
        "delegated_enforcement_links",
    )
    out: dict[str, set[str]] = {}
    for section in sections:
        out[section] = _ids_for_section(snapshot, section)
    return out


def _snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    sections = _snapshot_contract_sections(snapshot)
    canonical = {
        "schema_version": _norm(snapshot.get("schema_version")),
        "snapshot_date": _norm(snapshot.get("snapshot_date")),
        "totals": _safe_obj(snapshot.get("totals")),
        "sections": {name: sorted(values) for name, values in sections.items()},
    }
    return _stable_row_hash(canonical)


def build_snapshot_diff(
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None = None,
    *,
    previous_snapshot_path: str = "",
) -> dict[str, Any]:
    current = _safe_obj(current_snapshot)
    previous = _safe_obj(previous_snapshot)
    current_sections = _snapshot_contract_sections(current)
    previous_sections = _snapshot_contract_sections(previous)

    all_section_names = sorted(set(current_sections.keys()) | set(previous_sections.keys()))
    sections: dict[str, Any] = {}
    changed_sections: list[str] = []
    added_total = 0
    removed_total = 0
    for section_name in all_section_names:
        current_ids = current_sections.get(section_name, set())
        previous_ids = previous_sections.get(section_name, set())
        added_ids = sorted(current_ids - previous_ids)
        removed_ids = sorted(previous_ids - current_ids)
        unchanged_total = len(current_ids & previous_ids)
        added_total += len(added_ids)
        removed_total += len(removed_ids)
        if added_ids or removed_ids:
            changed_sections.append(section_name)
        sections[section_name] = {
            "current_total": len(current_ids),
            "previous_total": len(previous_ids),
            "added_total": len(added_ids),
            "removed_total": len(removed_ids),
            "unchanged_total": unchanged_total,
            "added_ids_sample": added_ids[:20],
            "removed_ids_sample": removed_ids[:20],
        }

    current_totals = _safe_obj(current.get("totals"))
    previous_totals = _safe_obj(previous.get("totals"))
    total_keys = sorted(set(current_totals.keys()) | set(previous_totals.keys()))
    totals_delta: dict[str, int] = {}
    totals_changed: list[str] = []
    for key in total_keys:
        delta = _to_int(current_totals.get(key), 0) - _to_int(previous_totals.get(key), 0)
        totals_delta[key] = int(delta)
        if delta != 0:
            totals_changed.append(key)

    status = "baseline"
    if previous:
        status = "changed" if changed_sections or totals_changed else "unchanged"

    return {
        "generated_at": now_utc_iso(),
        "snapshot_date": _norm(current.get("snapshot_date")),
        "previous_snapshot_date": _norm(previous.get("snapshot_date")),
        "schema_version": _norm(current.get("schema_version")),
        "previous_snapshot_path": _norm(previous_snapshot_path),
        "status": status,
        "sections": sections,
        "changed_sections": changed_sections,
        "changed_sections_total": len(changed_sections),
        "items_added_total": added_total,
        "items_removed_total": removed_total,
        "totals_current": current_totals,
        "totals_previous": previous_totals,
        "totals_delta": totals_delta,
        "totals_changed": totals_changed,
    }


def build_snapshot_changelog_entry(
    snapshot: dict[str, Any],
    diff: dict[str, Any],
    *,
    snapshot_path: str,
    previous_snapshot_path: str,
    diff_path: str,
) -> dict[str, Any]:
    snapshot_date = _norm(snapshot.get("snapshot_date"))
    previous_snapshot_date = _norm(diff.get("previous_snapshot_date"))
    fingerprint = _snapshot_fingerprint(snapshot)
    entry_id = "|".join([snapshot_date, previous_snapshot_date, fingerprint])
    changed_sections = [str(v) for v in _safe_list(diff.get("changed_sections")) if _norm(v)]
    return {
        "run_at": now_utc_iso(),
        "entry_id": entry_id,
        "snapshot_date": snapshot_date,
        "previous_snapshot_date": previous_snapshot_date,
        "schema_version": _norm(snapshot.get("schema_version")),
        "snapshot_path": _norm(snapshot_path),
        "previous_snapshot_path": _norm(previous_snapshot_path),
        "diff_path": _norm(diff_path),
        "fingerprint": fingerprint,
        "totals": _safe_obj(snapshot.get("totals")),
        "change_summary": {
            "status": _norm(diff.get("status")),
            "changed_sections_total": len(changed_sections),
            "changed_sections": changed_sections,
            "items_added_total": _to_int(diff.get("items_added_total"), 0),
            "items_removed_total": _to_int(diff.get("items_removed_total"), 0),
            "totals_changed": [str(v) for v in _safe_list(diff.get("totals_changed")) if _norm(v)],
        },
    }


def read_jsonl_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = _norm(raw_line)
        if not line:
            continue
        try:
            payload = json.loads(line)
            rows.append({"line_no": line_no, "malformed_line": False, "entry": _safe_obj(payload)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": line_no, "malformed_line": True, "entry": {}})
    return rows


def history_has_entry(rows: list[dict[str, Any]], entry_id: str) -> bool:
    needle = _norm(entry_id)
    if not needle:
        return False
    for row in rows:
        if bool(row.get("malformed_line")):
            continue
        entry = _safe_obj(row.get("entry"))
        if _norm(entry.get("entry_id")) == needle:
            return True
    return False


def append_jsonl_entry(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export liberty restrictions snapshot")
    ap.add_argument("--db", required=True)
    ap.add_argument("--snapshot-date", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--irlc-parquet-out", default="")
    ap.add_argument("--accountability-parquet-out", default="")
    ap.add_argument("--parquet-compression", default="zstd")
    ap.add_argument("--prev-snapshot", default="")
    ap.add_argument("--diff-out", default="")
    ap.add_argument("--changelog-jsonl", default="")
    ap.add_argument("--changelog-out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        payload = build_snapshot(conn, snapshot_date=str(args.snapshot_date or ""))
    finally:
        conn.close()

    out_path = Path(args.out)
    write_json(out_path, payload)

    operation_payload: dict[str, Any] = {
        "status": "ok",
        "snapshot_path": str(out_path),
        "snapshot_schema_version": _norm(payload.get("schema_version")),
        "snapshot_totals": _safe_obj(payload.get("totals")),
    }

    if _norm(args.irlc_parquet_out):
        irlc_rows = build_irlc_parquet_rows(payload)
        operation_payload["irlc_by_fragment_parquet"] = write_parquet_table(
            irlc_rows,
            out_path=Path(str(args.irlc_parquet_out)),
            fields=IRLC_PARQUET_FIELDS,
            compression=_norm(args.parquet_compression) or "zstd",
        )

    if _norm(args.accountability_parquet_out):
        accountability_rows = build_accountability_parquet_rows(payload)
        operation_payload["accountability_edges_parquet"] = write_parquet_table(
            accountability_rows,
            out_path=Path(str(args.accountability_parquet_out)),
            fields=ACCOUNTABILITY_PARQUET_FIELDS,
            compression=_norm(args.parquet_compression) or "zstd",
        )

    previous_snapshot_path = _norm(args.prev_snapshot)
    previous_snapshot_doc: dict[str, Any] | None = None
    if previous_snapshot_path:
        prev_path_obj = Path(previous_snapshot_path)
        if prev_path_obj.exists():
            loaded_prev = json.loads(prev_path_obj.read_text(encoding="utf-8"))
            previous_snapshot_doc = _safe_obj(loaded_prev)
        else:
            operation_payload["previous_snapshot_missing"] = True

    should_emit_diff = bool(_norm(args.diff_out) or _norm(args.changelog_jsonl) or _norm(args.changelog_out))
    diff_payload: dict[str, Any] = {}
    if should_emit_diff:
        diff_payload = build_snapshot_diff(
            payload,
            previous_snapshot_doc,
            previous_snapshot_path=previous_snapshot_path,
        )
        if _norm(args.diff_out):
            write_json(Path(str(args.diff_out)), diff_payload)
        operation_payload["snapshot_diff"] = {
            "status": _norm(diff_payload.get("status")),
            "changed_sections_total": _to_int(diff_payload.get("changed_sections_total"), 0),
            "items_added_total": _to_int(diff_payload.get("items_added_total"), 0),
            "items_removed_total": _to_int(diff_payload.get("items_removed_total"), 0),
            "diff_path": _norm(args.diff_out),
        }

    if _norm(args.changelog_jsonl):
        if not diff_payload:
            diff_payload = build_snapshot_diff(
                payload,
                previous_snapshot_doc,
                previous_snapshot_path=previous_snapshot_path,
            )
        changelog_path = Path(str(args.changelog_jsonl))
        history_rows = read_jsonl_entries(changelog_path)
        changelog_entry = build_snapshot_changelog_entry(
            payload,
            diff_payload,
            snapshot_path=str(out_path),
            previous_snapshot_path=previous_snapshot_path,
            diff_path=_norm(args.diff_out),
        )
        entry_id = _norm(changelog_entry.get("entry_id"))
        appended = False
        if entry_id and not history_has_entry(history_rows, entry_id):
            append_jsonl_entry(changelog_path, changelog_entry)
            appended = True
        history_entries_total = sum(1 for row in history_rows if not bool(row.get("malformed_line"))) + (1 if appended else 0)
        history_malformed_total = sum(1 for row in history_rows if bool(row.get("malformed_line")))
        changelog_out_payload = {
            "status": "ok",
            "changelog_path": str(changelog_path),
            "entry_id": entry_id,
            "appended": appended,
            "history_entries_total": history_entries_total,
            "history_malformed_lines_total": history_malformed_total,
            "entry": changelog_entry,
        }
        operation_payload["snapshot_changelog"] = {
            "changelog_path": str(changelog_path),
            "entry_id": entry_id,
            "appended": appended,
        }
        if _norm(args.changelog_out):
            write_json(Path(str(args.changelog_out)), changelog_out_payload)
    elif _norm(args.changelog_out):
        write_json(
            Path(str(args.changelog_out)),
            {
                "status": "skipped",
                "reason": "changelog_jsonl_not_provided",
                "changelog_path": "",
                "entry_id": "",
                "appended": False,
            },
        )

    print(json.dumps(operation_payload, ensure_ascii=False, indent=2))
    return 0 if int(payload.get("totals", {}).get("restrictions_total", 0)) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
