#!/usr/bin/env python3
"""Report personal accountability scoring for liberty restrictions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
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
    "appoint": 0.15,
    "instruct": 0.15,
    "design": 0.10,
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _parse_iso_date(v: Any) -> datetime | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return datetime.strptime(token, "%Y-%m-%d")
    except ValueError:
        return None


def _min_date_token(existing: str, candidate: str) -> str:
    if not candidate:
        return existing
    if not existing:
        return candidate
    ex = _parse_iso_date(existing)
    ca = _parse_iso_date(candidate)
    if ex is None:
        return candidate
    if ca is None:
        return existing
    return candidate if ca < ex else existing


def _max_date_token(existing: str, candidate: str) -> str:
    if not candidate:
        return existing
    if not existing:
        return candidate
    ex = _parse_iso_date(existing)
    ca = _parse_iso_date(candidate)
    if ex is None:
        return candidate
    if ca is None:
        return existing
    return candidate if ca > ex else existing


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(_norm(r["name"]) == column for r in rows)


def build_status_report(
    conn: sqlite3.Connection,
    *,
    top_n: int = 20,
    personal_confidence_min: float = 0.55,
    personal_max_causal_distance: int = 2,
    personal_fragment_coverage_min: float = 0.5,
    personal_primary_evidence_min_pct: float = 1.0,
    min_personal_primary_evidence_edges: int = 1,
    indirect_person_window_min_pct: float = 1.0,
    min_indirect_person_window_edges: int = 1,
    indirect_identity_resolution_min_pct: float = 0.0,
    min_indirect_identity_resolution_edges: int = 1,
    indirect_non_manual_alias_resolution_min_pct: float = 0.0,
    min_indirect_non_manual_alias_resolution_edges: int = 1,
    manual_alias_share_max: float = 1.0,
    min_alias_rows_for_manual_share_gate: int = 1,
    official_alias_evidence_min_pct: float = 1.0,
    min_official_alias_rows_for_evidence_gate: int = 1,
    official_alias_source_record_min_pct: float = 1.0,
    min_official_alias_rows_for_source_record_gate: int = 1,
    official_alias_share_min_pct: float = 0.0,
    min_alias_rows_for_official_share_gate: int = 1,
    min_persons_scored: int = 1,
) -> dict[str, Any]:
    has_alias_source_kind = _has_column(conn, "person_name_aliases", "source_kind")
    has_alias_source_url = _has_column(conn, "person_name_aliases", "source_url")
    has_alias_evidence_date = _has_column(conn, "person_name_aliases", "evidence_date")
    has_alias_evidence_quote = _has_column(conn, "person_name_aliases", "evidence_quote")
    has_alias_source_record_pk = _has_column(conn, "person_name_aliases", "source_record_pk")
    alias_non_manual_predicate = (
        "COALESCE(LOWER(TRIM(pna.source_kind)), 'manual_seed') <> 'manual_seed'" if has_alias_source_kind else "0"
    )
    alias_manual_predicate = (
        "COALESCE(LOWER(TRIM(pna.source_kind)), 'manual_seed') = 'manual_seed'" if has_alias_source_kind else "1=1"
    )
    alias_official_with_evidence_predicate = (
        f"({alias_non_manual_predicate})"
        + (
            " AND TRIM(COALESCE(pna.source_url, '')) <> ''"
            if has_alias_source_url
            else " AND 0"
        )
        + (
            " AND TRIM(COALESCE(pna.evidence_date, '')) <> ''"
            if has_alias_evidence_date
            else " AND 0"
        )
        + (
            " AND TRIM(COALESCE(pna.evidence_quote, '')) <> ''"
            if has_alias_evidence_quote
            else " AND 0"
        )
    )
    alias_official_with_source_record_predicate = (
        f"({alias_non_manual_predicate})"
        + (
            " AND COALESCE(pna.source_record_pk, 0) >= 1"
            if has_alias_source_record_pk
            else " AND 0"
        )
    )

    totals_row = conn.execute(
        f"""
        SELECT
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS target_fragments_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?) AS indirect_attributable_edges_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> '') AS indirect_person_edges_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
              )) AS indirect_person_edges_valid_window_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
              )
              AND (
                    EXISTS (
                      SELECT 1
                      FROM persons p
                      WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM person_name_aliases pna
                      WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
                    )
              )) AS indirect_person_edges_identity_resolved_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
              )
              AND EXISTS (
                SELECT 1
                FROM persons p
                WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
              )) AS indirect_person_edges_identity_resolved_exact_name_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
              )
              AND NOT EXISTS (
                SELECT 1
                FROM persons p
                WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
              )
              AND EXISTS (
                SELECT 1
                FROM person_name_aliases pna
                WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
              )) AS indirect_person_edges_identity_resolved_alias_total,
          (SELECT COUNT(*)
             FROM liberty_indirect_responsibility_edges e
            WHERE e.edge_confidence >= ?
              AND e.causal_distance <= ?
              AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
              AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
              AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
              )
              AND (
                    TRIM(COALESCE(e.appointment_end_date, '')) = ''
                    OR TRIM(COALESCE(e.evidence_date, '')) = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
              )
              AND NOT EXISTS (
                SELECT 1
                FROM persons p
                WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
              )
              AND EXISTS (
                SELECT 1
                FROM person_name_aliases pna
                WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
                  AND {alias_non_manual_predicate}
              )) AS indirect_person_edges_identity_resolved_alias_non_manual_total,
          (SELECT COUNT(*)
             FROM legal_fragment_responsibilities r
             JOIN persons p ON p.person_id = r.person_id
             JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
            WHERE r.person_id IS NOT NULL
              AND TRIM(COALESCE(p.full_name, '')) <> '') AS direct_person_edges_total
        """,
        (
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
            float(personal_confidence_min),
            int(personal_max_causal_distance),
        ),
    ).fetchone()

    edge_rows = conn.execute(
        """
        WITH direct_person_edges AS (
          SELECT
            COALESCE(NULLIF(TRIM(p.full_name), ''), NULLIF(TRIM(r.actor_label), ''), 'unknown_person') AS person_name,
            COALESCE(NULLIF(TRIM(r.actor_label), ''), NULLIF(TRIM(p.full_name), ''), 'unknown_actor') AS actor_label,
            COALESCE(NULLIF(TRIM(r.role), ''), 'unknown_role') AS role,
            COALESCE(NULLIF(TRIM(r.role), ''), 'unknown_role') AS actor_role_title,
            r.fragment_id AS fragment_id,
            a.irlc_score AS irlc_score,
            1.0 AS edge_confidence,
            CASE
              WHEN COALESCE(TRIM(r.source_url), '') <> ''
               AND COALESCE(TRIM(r.evidence_date), '') <> ''
               AND COALESCE(TRIM(r.evidence_quote), '') <> '' THEN 1
              ELSE 0
            END AS has_primary_evidence,
            COALESCE(TRIM(r.evidence_date), '') AS evidence_date,
            COALESCE(TRIM(r.evidence_date), '') AS period_start_date,
            COALESCE(TRIM(r.evidence_date), '') AS period_end_date,
            1 AS window_valid,
            'direct' AS source_lane
          FROM legal_fragment_responsibilities r
          JOIN persons p ON p.person_id = r.person_id
          JOIN liberty_restriction_assessments a ON a.fragment_id = r.fragment_id
          WHERE r.person_id IS NOT NULL
            AND TRIM(COALESCE(p.full_name, '')) <> ''
        ),
        indirect_person_edges AS (
          SELECT
            COALESCE(
              (
                SELECT p.full_name
                FROM persons p
                WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
                ORDER BY p.person_id ASC
                LIMIT 1
              ),
              (
                SELECT p.full_name
                FROM person_name_aliases pna
                JOIN persons p ON p.person_id = pna.person_id
                WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
                ORDER BY pna.person_name_alias_id DESC
                LIMIT 1
              ),
              TRIM(e.actor_person_name)
            ) AS person_name,
            COALESCE(NULLIF(TRIM(e.actor_label), ''), TRIM(e.actor_person_name), 'unknown_actor') AS actor_label,
            TRIM(e.role) AS role,
            TRIM(e.actor_role_title) AS actor_role_title,
            e.fragment_id AS fragment_id,
            a.irlc_score AS irlc_score,
            e.edge_confidence AS edge_confidence,
            CASE
              WHEN COALESCE(TRIM(e.source_url), '') <> ''
               AND COALESCE(TRIM(e.evidence_date), '') <> ''
               AND COALESCE(TRIM(e.evidence_quote), '') <> '' THEN 1
              ELSE 0
            END AS has_primary_evidence,
            COALESCE(TRIM(e.evidence_date), '') AS evidence_date,
            TRIM(e.appointment_start_date) AS period_start_date,
            CASE
              WHEN COALESCE(TRIM(e.appointment_end_date), '') <> '' THEN TRIM(e.appointment_end_date)
              WHEN COALESCE(TRIM(e.evidence_date), '') <> '' THEN TRIM(e.evidence_date)
              ELSE TRIM(e.appointment_start_date)
            END AS period_end_date,
            CASE
              WHEN (
                    COALESCE(TRIM(e.appointment_end_date), '') = ''
                    OR date(e.appointment_end_date) >= date(e.appointment_start_date)
              )
               AND (
                    COALESCE(TRIM(e.evidence_date), '') = ''
                    OR date(e.evidence_date) >= date(e.appointment_start_date)
               )
               AND (
                    COALESCE(TRIM(e.appointment_end_date), '') = ''
                    OR COALESCE(TRIM(e.evidence_date), '') = ''
                    OR date(e.evidence_date) <= date(e.appointment_end_date)
               ) THEN 1
              ELSE 0
            END AS window_valid,
            'indirect' AS source_lane
          FROM liberty_indirect_responsibility_edges e
          JOIN liberty_restriction_assessments a ON a.fragment_id = e.fragment_id
          WHERE e.edge_confidence >= ?
            AND e.causal_distance <= ?
            AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
            AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
            AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
        )
        SELECT *
        FROM direct_person_edges
        UNION ALL
        SELECT *
        FROM indirect_person_edges
        WHERE window_valid = 1
        """,
        (float(personal_confidence_min), int(personal_max_causal_distance)),
    ).fetchall()

    person_map: dict[str, dict[str, Any]] = {}
    fragments_with_personal_edges: set[str] = set()
    personal_edges_with_primary_evidence_total = 0
    personal_edges_total = 0

    for r in edge_rows:
        person_name = _norm(r["person_name"]) or "unknown_person"
        role = _norm(r["role"]) or "unknown_role"
        role_weight = float(DEFAULT_ROLE_WEIGHTS.get(role, 0.0))
        if role_weight <= 0.0:
            continue
        irlc_score = float(r["irlc_score"] or 0.0)
        edge_confidence = float(r["edge_confidence"] or 0.0)
        has_primary_evidence = int(r["has_primary_evidence"] or 0) == 1
        primary_factor = 1.0 if has_primary_evidence else 0.5
        weighted_score = irlc_score * role_weight * edge_confidence * primary_factor
        probative_strength = edge_confidence * primary_factor

        personal_edges_total += 1
        if has_primary_evidence:
            personal_edges_with_primary_evidence_total += 1

        fragment_id = _norm(r["fragment_id"])
        if fragment_id:
            fragments_with_personal_edges.add(fragment_id)

        rec = person_map.setdefault(
            person_name,
            {
                "person_name": person_name,
                "actor_labels": set(),
                "role_titles": set(),
                "edges_total": 0,
                "direct_edges_total": 0,
                "indirect_edges_total": 0,
                "fragments": set(),
                "primary_evidence_edges_total": 0,
                "edge_confidence_sum": 0.0,
                "probative_strength_sum": 0.0,
                "weighted_score_raw": 0.0,
                "period_start_date": "",
                "period_end_date": "",
                "role_breakdown": defaultdict(
                    lambda: {
                        "role": "",
                        "edges_total": 0,
                        "weighted_score_raw": 0.0,
                        "primary_evidence_edges_total": 0,
                    }
                ),
            },
        )
        rec["actor_labels"].add(_norm(r["actor_label"]))
        rec["role_titles"].add(_norm(r["actor_role_title"]))
        rec["edges_total"] += 1
        rec["direct_edges_total"] += 1 if _norm(r["source_lane"]) == "direct" else 0
        rec["indirect_edges_total"] += 1 if _norm(r["source_lane"]) == "indirect" else 0
        rec["fragments"].add(fragment_id)
        rec["primary_evidence_edges_total"] += 1 if has_primary_evidence else 0
        rec["edge_confidence_sum"] += edge_confidence
        rec["probative_strength_sum"] += probative_strength
        rec["weighted_score_raw"] += weighted_score

        evidence_date = _norm(r["evidence_date"])
        period_start = _norm(r["period_start_date"]) or evidence_date
        period_end = _norm(r["period_end_date"]) or evidence_date
        rec["period_start_date"] = _min_date_token(rec["period_start_date"], period_start)
        rec["period_end_date"] = _max_date_token(rec["period_end_date"], period_end)

        rb = rec["role_breakdown"][role]
        rb["role"] = role
        rb["edges_total"] += 1
        rb["weighted_score_raw"] += weighted_score
        rb["primary_evidence_edges_total"] += 1 if has_primary_evidence else 0

    max_weighted = 0.0
    for rec in person_map.values():
        max_weighted = max(max_weighted, float(rec["weighted_score_raw"]))

    all_person_scores: list[dict[str, Any]] = []
    for rec in person_map.values():
        edges_total = int(rec["edges_total"])
        role_breakdown = []
        for rb in rec["role_breakdown"].values():
            rb_edges = int(rb["edges_total"])
            role_breakdown.append(
                {
                    "role": _norm(rb["role"]),
                    "edges_total": rb_edges,
                    "weighted_score_raw": round(float(rb["weighted_score_raw"]), 6),
                    "primary_evidence_edges_total": int(rb["primary_evidence_edges_total"]),
                    "primary_evidence_pct": round(
                        (int(rb["primary_evidence_edges_total"]) / rb_edges) if rb_edges else 0.0,
                        6,
                    ),
                }
            )
        role_breakdown.sort(key=lambda x: (float(x["weighted_score_raw"]), int(x["edges_total"]), _norm(x["role"])), reverse=True)

        primary_evidence_edges_total = int(rec["primary_evidence_edges_total"])
        weighted_score_raw = float(rec["weighted_score_raw"])
        all_person_scores.append(
            {
                "person_name": _norm(rec["person_name"]),
                "actor_labels": sorted([a for a in rec["actor_labels"] if _norm(a)]),
                "role_titles": sorted([t for t in rec["role_titles"] if _norm(t)]),
                "period_start_date": _norm(rec["period_start_date"]),
                "period_end_date": _norm(rec["period_end_date"]),
                "edges_total": edges_total,
                "direct_edges_total": int(rec["direct_edges_total"]),
                "indirect_edges_total": int(rec["indirect_edges_total"]),
                "fragments_total": len(rec["fragments"]),
                "primary_evidence_edges_total": primary_evidence_edges_total,
                "primary_evidence_pct": round((primary_evidence_edges_total / edges_total) if edges_total else 0.0, 6),
                "mean_edge_confidence": round((float(rec["edge_confidence_sum"]) / edges_total) if edges_total else 0.0, 6),
                "mean_probative_strength": round((float(rec["probative_strength_sum"]) / edges_total) if edges_total else 0.0, 6),
                "weighted_score_raw": round(weighted_score_raw, 6),
                "responsibility_score_personal": round((weighted_score_raw / max_weighted) * 100.0, 6) if max_weighted > 0 else 0.0,
                "role_breakdown": role_breakdown,
            }
        )

    all_person_scores.sort(
        key=lambda x: (
            float(x["responsibility_score_personal"]),
            int(x["edges_total"]),
            _norm(x["person_name"]),
        ),
        reverse=True,
    )
    persons_scored_total = len(all_person_scores)
    top_person_scores = all_person_scores[: max(0, int(top_n))]

    target_fragments_total = int(totals_row["target_fragments_total"] or 0)
    indirect_person_edges_total = int(totals_row["indirect_person_edges_total"] or 0)
    indirect_person_edges_valid_window_total = int(totals_row["indirect_person_edges_valid_window_total"] or 0)
    indirect_person_edges_identity_resolved_total = int(totals_row["indirect_person_edges_identity_resolved_total"] or 0)
    indirect_person_edges_identity_resolved_exact_name_total = int(
        totals_row["indirect_person_edges_identity_resolved_exact_name_total"] or 0
    )
    indirect_person_edges_identity_resolved_alias_total = int(
        totals_row["indirect_person_edges_identity_resolved_alias_total"] or 0
    )
    indirect_person_edges_identity_resolved_alias_non_manual_total = int(
        totals_row["indirect_person_edges_identity_resolved_alias_non_manual_total"] or 0
    )
    indirect_person_edges_identity_resolved_alias_manual_total = max(
        0,
        indirect_person_edges_identity_resolved_alias_total - indirect_person_edges_identity_resolved_alias_non_manual_total,
    )
    manual_alias_rows = conn.execute(
        f"""
        SELECT
          TRIM(pna.alias) AS actor_person_name,
          COUNT(e.edge_id) AS edges_total
        FROM person_name_aliases pna
        LEFT JOIN liberty_indirect_responsibility_edges e
          ON pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
         AND e.edge_confidence >= ?
         AND e.causal_distance <= ?
         AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
         AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
         AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
         AND (
              TRIM(COALESCE(e.appointment_end_date, '')) = ''
              OR date(e.appointment_end_date) >= date(e.appointment_start_date)
         )
         AND (
              TRIM(COALESCE(e.evidence_date, '')) = ''
              OR date(e.evidence_date) >= date(e.appointment_start_date)
         )
         AND (
              TRIM(COALESCE(e.appointment_end_date, '')) = ''
              OR TRIM(COALESCE(e.evidence_date, '')) = ''
              OR date(e.evidence_date) <= date(e.appointment_end_date)
         )
        WHERE {alias_manual_predicate}
        GROUP BY pna.person_name_alias_id, TRIM(pna.alias)
        ORDER BY COUNT(e.edge_id) DESC, TRIM(pna.alias) ASC
        """,
        (
            float(personal_confidence_min),
            int(personal_max_causal_distance),
        ),
    ).fetchall()
    aliases_total_row = conn.execute("SELECT COUNT(*) AS n FROM person_name_aliases").fetchone()
    aliases_total = int((aliases_total_row["n"] if aliases_total_row is not None else 0) or 0)
    manual_alias_rows_total = len(manual_alias_rows)
    official_alias_rows_total = max(0, aliases_total - manual_alias_rows_total)
    official_alias_rows_with_evidence_row = conn.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM person_name_aliases pna
        WHERE {alias_official_with_evidence_predicate}
        """
    ).fetchone()
    official_alias_rows_with_evidence_total = int(
        (
            official_alias_rows_with_evidence_row["n"]
            if official_alias_rows_with_evidence_row is not None
            else 0
        )
        or 0
    )
    official_alias_rows_missing_evidence_total = max(
        0,
        official_alias_rows_total - official_alias_rows_with_evidence_total,
    )
    official_alias_rows_with_source_record_row = conn.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM person_name_aliases pna
        WHERE {alias_official_with_source_record_predicate}
        """
    ).fetchone()
    official_alias_rows_with_source_record_total = int(
        (
            official_alias_rows_with_source_record_row["n"]
            if official_alias_rows_with_source_record_row is not None
            else 0
        )
        or 0
    )
    official_alias_rows_missing_source_record_total = max(
        0,
        official_alias_rows_total - official_alias_rows_with_source_record_total,
    )
    manual_alias_rows_with_edge_impact_total = sum(1 for r in manual_alias_rows if int(r["edges_total"] or 0) > 0)
    manual_alias_edges_with_impact_total = sum(int(r["edges_total"] or 0) for r in manual_alias_rows)

    unresolved_indirect_identity_rows = conn.execute(
        """
        SELECT
          TRIM(e.actor_person_name) AS actor_person_name,
          COUNT(*) AS edges_total
        FROM liberty_indirect_responsibility_edges e
        WHERE e.edge_confidence >= ?
          AND e.causal_distance <= ?
          AND TRIM(COALESCE(e.actor_person_name, '')) <> ''
          AND TRIM(COALESCE(e.actor_role_title, '')) <> ''
          AND TRIM(COALESCE(e.appointment_start_date, '')) <> ''
          AND (
                TRIM(COALESCE(e.appointment_end_date, '')) = ''
                OR date(e.appointment_end_date) >= date(e.appointment_start_date)
          )
          AND (
                TRIM(COALESCE(e.evidence_date, '')) = ''
                OR date(e.evidence_date) >= date(e.appointment_start_date)
          )
          AND (
                TRIM(COALESCE(e.appointment_end_date, '')) = ''
                OR TRIM(COALESCE(e.evidence_date, '')) = ''
                OR date(e.evidence_date) <= date(e.appointment_end_date)
          )
          AND NOT EXISTS (
            SELECT 1
            FROM persons p
            WHERE LOWER(TRIM(p.full_name)) = LOWER(TRIM(e.actor_person_name))
          )
          AND NOT EXISTS (
            SELECT 1
            FROM person_name_aliases pna
            WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
          )
        GROUP BY TRIM(e.actor_person_name)
        ORDER BY COUNT(*) DESC, TRIM(e.actor_person_name) ASC
        LIMIT 20
        """,
        (float(personal_confidence_min), int(personal_max_causal_distance)),
    ).fetchall()
    unresolved_indirect_identity_sample = [
        {
            "actor_person_name": _norm(r["actor_person_name"]),
            "edges_total": int(r["edges_total"] or 0),
        }
        for r in unresolved_indirect_identity_rows
    ]

    coverage = {
        "fragments_with_personal_accountability_pct": round(
            (len(fragments_with_personal_edges) / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "personal_edges_with_primary_evidence_pct": round(
            (personal_edges_with_primary_evidence_total / personal_edges_total) if personal_edges_total else 0.0,
            6,
        ),
        "indirect_person_edges_with_valid_window_pct": round(
            (indirect_person_edges_valid_window_total / indirect_person_edges_total) if indirect_person_edges_total else 0.0,
            6,
        ),
        "indirect_identity_resolution_pct": round(
            (
                indirect_person_edges_identity_resolved_total
                / indirect_person_edges_valid_window_total
            )
            if indirect_person_edges_valid_window_total
            else 0.0,
            6,
        ),
        "indirect_non_manual_alias_resolution_pct": round(
            (
                indirect_person_edges_identity_resolved_alias_non_manual_total
                / indirect_person_edges_identity_resolved_alias_total
            )
            if indirect_person_edges_identity_resolved_alias_total
            else 1.0,
            6,
        ),
        "manual_alias_share_pct": round((manual_alias_rows_total / aliases_total) if aliases_total else 0.0, 6),
        "manual_alias_upgrade_edge_impact_pct": round(
            (manual_alias_edges_with_impact_total / indirect_person_edges_identity_resolved_alias_total)
            if indirect_person_edges_identity_resolved_alias_total
            else 0.0,
            6,
        ),
        "official_alias_share_pct": round((official_alias_rows_total / aliases_total) if aliases_total else 1.0, 6),
        "official_alias_evidence_coverage_pct": round(
            (
                official_alias_rows_with_evidence_total
                / official_alias_rows_total
            )
            if official_alias_rows_total
            else 1.0,
            6,
        ),
        "official_alias_source_record_coverage_pct": round(
            (
                official_alias_rows_with_source_record_total
                / official_alias_rows_total
            )
            if official_alias_rows_total
            else 1.0,
            6,
        ),
    }

    checks = {
        "personal_scores_available": persons_scored_total > 0,
        "min_persons_scored_gate": persons_scored_total >= int(min_persons_scored),
        "personal_fragment_coverage_gate": coverage["fragments_with_personal_accountability_pct"] >= float(personal_fragment_coverage_min),
        "personal_primary_evidence_gate": (
            coverage["personal_edges_with_primary_evidence_pct"] >= float(personal_primary_evidence_min_pct)
            and personal_edges_with_primary_evidence_total >= int(min_personal_primary_evidence_edges)
        ),
        "indirect_person_window_gate": (
            coverage["indirect_person_edges_with_valid_window_pct"] >= float(indirect_person_window_min_pct)
            and indirect_person_edges_total >= int(min_indirect_person_window_edges)
        ),
        "indirect_identity_resolution_gate": (
            coverage["indirect_identity_resolution_pct"] >= float(indirect_identity_resolution_min_pct)
            and indirect_person_edges_valid_window_total >= int(min_indirect_identity_resolution_edges)
        ),
        "indirect_non_manual_alias_resolution_gate": (
            indirect_person_edges_identity_resolved_alias_total == 0
            or (
                coverage["indirect_non_manual_alias_resolution_pct"] >= float(indirect_non_manual_alias_resolution_min_pct)
                and indirect_person_edges_identity_resolved_alias_total
                >= int(min_indirect_non_manual_alias_resolution_edges)
            )
        ),
        "manual_alias_share_gate": (
            aliases_total < int(min_alias_rows_for_manual_share_gate)
            or coverage["manual_alias_share_pct"] <= float(manual_alias_share_max)
        ),
        "official_alias_share_gate": (
            aliases_total < int(min_alias_rows_for_official_share_gate)
            or coverage["official_alias_share_pct"] >= float(official_alias_share_min_pct)
        ),
        "official_alias_evidence_gate": (
            official_alias_rows_total < int(min_official_alias_rows_for_evidence_gate)
            or coverage["official_alias_evidence_coverage_pct"] >= float(official_alias_evidence_min_pct)
        ),
        "official_alias_source_record_gate": (
            official_alias_rows_total < int(min_official_alias_rows_for_source_record_gate)
            or coverage["official_alias_source_record_coverage_pct"] >= float(official_alias_source_record_min_pct)
        ),
    }
    gate_passed = all(bool(v) for v in checks.values())

    if personal_edges_total == 0:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "target_fragments_total": target_fragments_total,
            "fragments_with_personal_accountability_total": len(fragments_with_personal_edges),
            "personal_edges_total": personal_edges_total,
            "personal_edges_with_primary_evidence_total": personal_edges_with_primary_evidence_total,
            "direct_person_edges_total": int(totals_row["direct_person_edges_total"] or 0),
            "indirect_attributable_edges_total": int(totals_row["indirect_attributable_edges_total"] or 0),
            "indirect_person_edges_total": indirect_person_edges_total,
            "indirect_person_edges_valid_window_total": indirect_person_edges_valid_window_total,
            "indirect_person_edges_identity_resolved_total": indirect_person_edges_identity_resolved_total,
            "indirect_person_edges_identity_resolved_exact_name_total": indirect_person_edges_identity_resolved_exact_name_total,
            "indirect_person_edges_identity_resolved_alias_total": indirect_person_edges_identity_resolved_alias_total,
            "indirect_person_edges_identity_resolved_alias_non_manual_total": indirect_person_edges_identity_resolved_alias_non_manual_total,
            "indirect_person_edges_identity_resolved_alias_manual_total": indirect_person_edges_identity_resolved_alias_manual_total,
            "aliases_total": aliases_total,
            "manual_alias_rows_total": manual_alias_rows_total,
            "manual_alias_rows_with_edge_impact_total": manual_alias_rows_with_edge_impact_total,
            "manual_alias_edges_with_impact_total": manual_alias_edges_with_impact_total,
            "official_alias_rows_total": official_alias_rows_total,
            "official_alias_rows_with_evidence_total": official_alias_rows_with_evidence_total,
            "official_alias_rows_missing_evidence_total": official_alias_rows_missing_evidence_total,
            "official_alias_rows_with_source_record_total": official_alias_rows_with_source_record_total,
            "official_alias_rows_missing_source_record_total": official_alias_rows_missing_source_record_total,
            "persons_scored_total": persons_scored_total,
            "top_person_scores_total": len(top_person_scores),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "personal_confidence_min": float(personal_confidence_min),
                "personal_max_causal_distance": int(personal_max_causal_distance),
                "personal_fragment_coverage_min": float(personal_fragment_coverage_min),
                "personal_primary_evidence_min_pct": float(personal_primary_evidence_min_pct),
                "min_personal_primary_evidence_edges": int(min_personal_primary_evidence_edges),
                "indirect_person_window_min_pct": float(indirect_person_window_min_pct),
                "min_indirect_person_window_edges": int(min_indirect_person_window_edges),
                "indirect_identity_resolution_min_pct": float(indirect_identity_resolution_min_pct),
                "min_indirect_identity_resolution_edges": int(min_indirect_identity_resolution_edges),
                "indirect_non_manual_alias_resolution_min_pct": float(indirect_non_manual_alias_resolution_min_pct),
                "min_indirect_non_manual_alias_resolution_edges": int(
                    min_indirect_non_manual_alias_resolution_edges
                ),
                "manual_alias_share_max": float(manual_alias_share_max),
                "min_alias_rows_for_manual_share_gate": int(min_alias_rows_for_manual_share_gate),
                "official_alias_share_min_pct": float(official_alias_share_min_pct),
                "min_alias_rows_for_official_share_gate": int(min_alias_rows_for_official_share_gate),
                "official_alias_evidence_min_pct": float(official_alias_evidence_min_pct),
                "min_official_alias_rows_for_evidence_gate": int(min_official_alias_rows_for_evidence_gate),
                "official_alias_source_record_min_pct": float(official_alias_source_record_min_pct),
                "min_official_alias_rows_for_source_record_gate": int(min_official_alias_rows_for_source_record_gate),
                "min_persons_scored": int(min_persons_scored),
            },
        },
        "methodology": {
            "score_formula": "sum(irlc_score * role_weight * edge_confidence * primary_evidence_factor), normalized 0-100 by max person",
            "ranking_note": "top_person_scores is a display cap (top_n); gate checks always use full persons_scored_total",
            "identity_resolution_method": "exact normalized full_name match OR alias match on person_name_aliases.canonical_alias",
            "identity_provenance_note": "alias source quality is tracked via source_kind (manual_seed vs official_*) and source_record_pk coverage for official aliases.",
            "primary_evidence_factor": {
                "with_primary_evidence": 1.0,
                "without_primary_evidence": 0.5,
            },
            "role_weights": DEFAULT_ROLE_WEIGHTS,
        },
        "top_person_scores": top_person_scores,
        "indirect_identity_unresolved_sample": unresolved_indirect_identity_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report personal accountability scoring for liberty restrictions")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--personal-confidence-min", type=float, default=0.55)
    ap.add_argument("--personal-max-causal-distance", type=int, default=2)
    ap.add_argument("--personal-fragment-coverage-min", type=float, default=0.5)
    ap.add_argument("--personal-primary-evidence-min-pct", type=float, default=1.0)
    ap.add_argument("--min-personal-primary-evidence-edges", type=int, default=1)
    ap.add_argument("--indirect-person-window-min-pct", type=float, default=1.0)
    ap.add_argument("--min-indirect-person-window-edges", type=int, default=1)
    ap.add_argument("--indirect-identity-resolution-min-pct", type=float, default=0.0)
    ap.add_argument("--min-indirect-identity-resolution-edges", type=int, default=1)
    ap.add_argument("--indirect-non-manual-alias-resolution-min-pct", type=float, default=0.0)
    ap.add_argument("--min-indirect-non-manual-alias-resolution-edges", type=int, default=1)
    ap.add_argument("--manual-alias-share-max", type=float, default=1.0)
    ap.add_argument("--min-alias-rows-for-manual-share-gate", type=int, default=1)
    ap.add_argument("--official-alias-share-min-pct", type=float, default=0.0)
    ap.add_argument("--min-alias-rows-for-official-share-gate", type=int, default=1)
    ap.add_argument("--official-alias-evidence-min-pct", type=float, default=1.0)
    ap.add_argument("--min-official-alias-rows-for-evidence-gate", type=int, default=1)
    ap.add_argument("--official-alias-source-record-min-pct", type=float, default=1.0)
    ap.add_argument("--min-official-alias-rows-for-source-record-gate", type=int, default=1)
    ap.add_argument("--min-persons-scored", type=int, default=1)
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
            personal_confidence_min=float(args.personal_confidence_min),
            personal_max_causal_distance=int(args.personal_max_causal_distance),
            personal_fragment_coverage_min=float(args.personal_fragment_coverage_min),
            personal_primary_evidence_min_pct=float(args.personal_primary_evidence_min_pct),
            min_personal_primary_evidence_edges=int(args.min_personal_primary_evidence_edges),
            indirect_person_window_min_pct=float(args.indirect_person_window_min_pct),
            min_indirect_person_window_edges=int(args.min_indirect_person_window_edges),
            indirect_identity_resolution_min_pct=float(args.indirect_identity_resolution_min_pct),
            min_indirect_identity_resolution_edges=int(args.min_indirect_identity_resolution_edges),
            indirect_non_manual_alias_resolution_min_pct=float(args.indirect_non_manual_alias_resolution_min_pct),
            min_indirect_non_manual_alias_resolution_edges=int(args.min_indirect_non_manual_alias_resolution_edges),
            manual_alias_share_max=float(args.manual_alias_share_max),
            min_alias_rows_for_manual_share_gate=int(args.min_alias_rows_for_manual_share_gate),
            official_alias_share_min_pct=float(args.official_alias_share_min_pct),
            min_alias_rows_for_official_share_gate=int(args.min_alias_rows_for_official_share_gate),
            official_alias_evidence_min_pct=float(args.official_alias_evidence_min_pct),
            min_official_alias_rows_for_evidence_gate=int(args.min_official_alias_rows_for_evidence_gate),
            official_alias_source_record_min_pct=float(args.official_alias_source_record_min_pct),
            min_official_alias_rows_for_source_record_gate=int(
                args.min_official_alias_rows_for_source_record_gate
            ),
            min_persons_scored=int(args.min_persons_scored),
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
