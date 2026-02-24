#!/usr/bin/env python3
"""Report/export unresolved personal identity resolution queue for liberty edges."""

from __future__ import annotations

import argparse
import csv
import hashlib
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


def _stable_queue_key(actor_person_name: str) -> str:
    token = _norm(actor_person_name).lower()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"actor_name:{digest[:16]}"


def _stable_upgrade_queue_key(actor_person_name: str) -> str:
    token = _norm(actor_person_name).lower()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"alias_upgrade:{digest[:16]}"


def _stable_official_evidence_gap_queue_key(actor_person_name: str) -> str:
    token = _norm(actor_person_name).lower()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"official_evidence:{digest[:16]}"


def _stable_official_source_record_gap_queue_key(actor_person_name: str) -> str:
    token = _norm(actor_person_name).lower()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"official_source_record:{digest[:16]}"


def _split_csv_tokens(value: Any) -> list[str]:
    raw = _norm(value)
    if not raw:
        return []
    return sorted({_norm(t) for t in raw.split(",") if _norm(t)})


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(_norm(r["name"]) == column for r in rows)


def _base_identity_scope_sql() -> str:
    return """
        FROM liberty_indirect_responsibility_edges e
        WHERE e.edge_confidence >= :confidence_min
          AND e.causal_distance <= :max_distance
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
    """


def _identity_resolved_exact_name_sql(alias: str = "e") -> str:
    actor = f"LOWER(TRIM({alias}.actor_person_name))"
    return f"""
      EXISTS (
        SELECT 1
        FROM persons p
        WHERE LOWER(TRIM(p.full_name)) = {actor}
      )
    """


def _identity_resolved_alias_sql(alias: str = "e") -> str:
    actor = f"LOWER(TRIM({alias}.actor_person_name))"
    return f"""
      EXISTS (
        SELECT 1
        FROM person_name_aliases pna
        WHERE pna.canonical_alias = {actor}
      )
    """


def _identity_resolved_sql(alias: str = "e") -> str:
    return f"(({_identity_resolved_exact_name_sql(alias)}) OR ({_identity_resolved_alias_sql(alias)}))"


def build_report(
    conn: sqlite3.Connection,
    *,
    personal_confidence_min: float = 0.55,
    personal_max_causal_distance: int = 2,
    identity_resolution_min_pct: float = 0.0,
    min_indirect_person_edges: int = 1,
    non_manual_alias_resolution_min_pct: float = 0.0,
    min_non_manual_alias_resolution_edges: int = 1,
    manual_alias_share_max: float = 1.0,
    min_alias_rows_for_manual_share_gate: int = 1,
    official_alias_share_min_pct: float = 0.0,
    min_alias_rows_for_official_share_gate: int = 1,
    official_alias_evidence_min_pct: float = 1.0,
    min_official_alias_rows_for_evidence_gate: int = 1,
    official_alias_source_record_min_pct: float = 1.0,
    min_official_alias_rows_for_source_record_gate: int = 1,
    limit: int = 0,
) -> dict[str, Any]:
    scope_sql = _base_identity_scope_sql()
    resolved_sql = _identity_resolved_sql("e")
    resolved_exact_sql = _identity_resolved_exact_name_sql("e")
    resolved_alias_sql = _identity_resolved_alias_sql("e")
    has_alias_source_kind = _has_column(conn, "person_name_aliases", "source_kind")
    has_alias_source_url = _has_column(conn, "person_name_aliases", "source_url")
    has_alias_evidence_date = _has_column(conn, "person_name_aliases", "evidence_date")
    has_alias_evidence_quote = _has_column(conn, "person_name_aliases", "evidence_quote")
    has_alias_source_record_pk = _has_column(conn, "person_name_aliases", "source_record_pk")
    alias_source_kind_select_expr = (
        "COALESCE(TRIM(pna.source_kind), 'manual_seed')" if has_alias_source_kind else "'manual_seed'"
    )
    alias_source_url_select_expr = "TRIM(COALESCE(pna.source_url, ''))" if has_alias_source_url else "''"
    alias_evidence_date_select_expr = (
        "TRIM(COALESCE(pna.evidence_date, ''))" if has_alias_evidence_date else "''"
    )
    alias_evidence_quote_select_expr = (
        "TRIM(COALESCE(pna.evidence_quote, ''))" if has_alias_evidence_quote else "''"
    )
    alias_source_record_pk_select_expr = (
        "COALESCE(pna.source_record_pk, 0)" if has_alias_source_record_pk else "0"
    )
    alias_non_manual_predicate = (
        "COALESCE(LOWER(TRIM(pna.source_kind)), 'manual_seed') <> 'manual_seed'" if has_alias_source_kind else "0"
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
    params = {
        "confidence_min": float(personal_confidence_min),
        "max_distance": int(personal_max_causal_distance),
    }

    totals = conn.execute(
        f"""
        SELECT
          (SELECT COUNT(*) {scope_sql}) AS indirect_person_edges_valid_window_total,
          (SELECT COUNT(*)
             {scope_sql}
              AND {resolved_sql}
          ) AS indirect_person_edges_identity_resolved_total,
          (SELECT COUNT(*)
             {scope_sql}
              AND {resolved_exact_sql}
          ) AS indirect_person_edges_identity_resolved_exact_name_total,
          (SELECT COUNT(*)
             {scope_sql}
              AND (NOT ({resolved_exact_sql}))
              AND {resolved_alias_sql}
          ) AS indirect_person_edges_identity_resolved_alias_total,
          (SELECT COUNT(*)
             {scope_sql}
              AND NOT ({resolved_exact_sql})
              AND EXISTS (
                SELECT 1
                FROM person_name_aliases pna
                WHERE pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
                  AND {alias_non_manual_predicate}
              )
          ) AS indirect_person_edges_identity_resolved_alias_non_manual_total,
          (SELECT COUNT(DISTINCT TRIM(e.actor_person_name))
             {scope_sql}
              AND NOT ({resolved_sql})
          ) AS unresolved_actor_names_total
        """,
        params,
    ).fetchone()

    unresolved_sql = f"""
        SELECT
          TRIM(e.actor_person_name) AS actor_person_name,
          GROUP_CONCAT(DISTINCT TRIM(e.actor_role_title)) AS actor_role_titles_csv,
          COUNT(*) AS edges_total,
          COUNT(DISTINCT e.fragment_id) AS fragments_total,
          COALESCE(MIN(NULLIF(TRIM(e.evidence_date), '')), '') AS first_evidence_date,
          COALESCE(MAX(NULLIF(TRIM(e.evidence_date), '')), '') AS last_evidence_date
          {scope_sql}
          AND NOT ({resolved_sql})
        GROUP BY TRIM(e.actor_person_name)
        ORDER BY COUNT(*) DESC, TRIM(e.actor_person_name) ASC
    """
    if int(limit) > 0:
        unresolved_sql = unresolved_sql + "\nLIMIT :limit"
        unresolved_params = dict(params)
        unresolved_params["limit"] = int(limit)
    else:
        unresolved_params = params

    unresolved_rows = conn.execute(unresolved_sql, unresolved_params).fetchall()
    queue_rows = []
    for rank, r in enumerate(unresolved_rows, start=1):
        actor_person_name = _norm(r["actor_person_name"])
        role_titles = _split_csv_tokens(r["actor_role_titles_csv"])
        queue_rows.append(
            {
                "queue_rank": rank,
                "queue_key": _stable_queue_key(actor_person_name),
                "actor_person_name": actor_person_name,
                "actor_role_titles": role_titles,
                "actor_role_titles_csv": ", ".join(role_titles),
                "edges_total": int(r["edges_total"] or 0),
                "fragments_total": int(r["fragments_total"] or 0),
                "first_evidence_date": _norm(r["first_evidence_date"]),
                "last_evidence_date": _norm(r["last_evidence_date"]),
            }
        )

    manual_alias_predicate = (
        "COALESCE(LOWER(TRIM(pna.source_kind)), 'manual_seed') = 'manual_seed'" if has_alias_source_kind else "1=1"
    )
    manual_alias_rows = conn.execute(
        f"""
        SELECT
          TRIM(pna.alias) AS actor_person_name,
          TRIM(COALESCE(p.full_name, '')) AS person_name,
          {alias_source_kind_select_expr} AS source_kind,
          COUNT(e.edge_id) AS edges_total,
          COUNT(DISTINCT e.fragment_id) AS fragments_total,
          COALESCE(MIN(NULLIF(TRIM(e.evidence_date), '')), '') AS first_evidence_date,
          COALESCE(MAX(NULLIF(TRIM(e.evidence_date), '')), '') AS last_evidence_date
        FROM person_name_aliases pna
        JOIN persons p ON p.person_id = pna.person_id
        LEFT JOIN liberty_indirect_responsibility_edges e
          ON pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
         AND e.edge_confidence >= :confidence_min
         AND e.causal_distance <= :max_distance
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
        WHERE {manual_alias_predicate}
        GROUP BY pna.person_name_alias_id, TRIM(pna.alias), TRIM(COALESCE(p.full_name, '')), {alias_source_kind_select_expr}
        ORDER BY COUNT(e.edge_id) DESC, TRIM(pna.alias) ASC
        """,
        params,
    ).fetchall()
    manual_alias_upgrade_queue_rows = []
    for rank, r in enumerate(manual_alias_rows, start=1):
        actor_person_name = _norm(r["actor_person_name"])
        manual_alias_upgrade_queue_rows.append(
            {
                "queue_rank": rank,
                "queue_key": _stable_upgrade_queue_key(actor_person_name),
                "actor_person_name": actor_person_name,
                "person_name": _norm(r["person_name"]),
                "source_kind": _norm(r["source_kind"]) or "manual_seed",
                "edges_total": int(r["edges_total"] or 0),
                "fragments_total": int(r["fragments_total"] or 0),
                "first_evidence_date": _norm(r["first_evidence_date"]),
                "last_evidence_date": _norm(r["last_evidence_date"]),
                "next_action": "replace_manual_alias_with_official_evidence",
            }
        )

    official_alias_evidence_gap_rows = conn.execute(
        f"""
        SELECT
          TRIM(pna.alias) AS actor_person_name,
          TRIM(COALESCE(p.full_name, '')) AS person_name,
          {alias_source_kind_select_expr} AS source_kind,
          {alias_source_url_select_expr} AS source_url,
          {alias_evidence_date_select_expr} AS source_date,
          {alias_evidence_quote_select_expr} AS evidence_quote,
          {alias_source_record_pk_select_expr} AS source_record_pk,
          COUNT(e.edge_id) AS edges_total,
          COUNT(DISTINCT e.fragment_id) AS fragments_total,
          COALESCE(MIN(NULLIF(TRIM(e.evidence_date), '')), '') AS first_evidence_date,
          COALESCE(MAX(NULLIF(TRIM(e.evidence_date), '')), '') AS last_evidence_date
        FROM person_name_aliases pna
        JOIN persons p ON p.person_id = pna.person_id
        LEFT JOIN liberty_indirect_responsibility_edges e
          ON pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
         AND e.edge_confidence >= :confidence_min
         AND e.causal_distance <= :max_distance
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
        WHERE ({alias_non_manual_predicate})
          AND NOT ({alias_official_with_evidence_predicate})
        GROUP BY
          pna.person_name_alias_id,
          TRIM(pna.alias),
          TRIM(COALESCE(p.full_name, '')),
          {alias_source_kind_select_expr},
          {alias_source_url_select_expr},
          {alias_evidence_date_select_expr},
          {alias_evidence_quote_select_expr},
          {alias_source_record_pk_select_expr}
        ORDER BY COUNT(e.edge_id) DESC, TRIM(pna.alias) ASC
        """,
        params,
    ).fetchall()
    official_alias_evidence_upgrade_queue_rows = []
    for rank, r in enumerate(official_alias_evidence_gap_rows, start=1):
        actor_person_name = _norm(r["actor_person_name"])
        missing_fields = []
        if not _norm(r["source_url"]):
            missing_fields.append("source_url")
        if not _norm(r["source_date"]):
            missing_fields.append("evidence_date")
        if not _norm(r["evidence_quote"]):
            missing_fields.append("evidence_quote")
        official_alias_evidence_upgrade_queue_rows.append(
            {
                "queue_rank": rank,
                "queue_key": _stable_official_evidence_gap_queue_key(actor_person_name),
                "actor_person_name": actor_person_name,
                "person_name": _norm(r["person_name"]),
                "source_kind": _norm(r["source_kind"]) or "manual_seed",
                "source_record_pk": int(r["source_record_pk"] or 0),
                "missing_fields": missing_fields,
                "missing_fields_csv": ", ".join(missing_fields),
                "edges_total": int(r["edges_total"] or 0),
                "fragments_total": int(r["fragments_total"] or 0),
                "first_evidence_date": _norm(r["first_evidence_date"]),
                "last_evidence_date": _norm(r["last_evidence_date"]),
                "next_action": "fill_official_alias_evidence_fields",
            }
        )

    official_alias_source_record_gap_rows = conn.execute(
        f"""
        SELECT
          TRIM(pna.alias) AS actor_person_name,
          TRIM(COALESCE(p.full_name, '')) AS person_name,
          {alias_source_kind_select_expr} AS source_kind,
          {alias_source_url_select_expr} AS source_url,
          {alias_evidence_date_select_expr} AS source_date,
          {alias_evidence_quote_select_expr} AS evidence_quote,
          {alias_source_record_pk_select_expr} AS source_record_pk,
          COUNT(e.edge_id) AS edges_total,
          COUNT(DISTINCT e.fragment_id) AS fragments_total,
          COALESCE(MIN(NULLIF(TRIM(e.evidence_date), '')), '') AS first_evidence_date,
          COALESCE(MAX(NULLIF(TRIM(e.evidence_date), '')), '') AS last_evidence_date
        FROM person_name_aliases pna
        JOIN persons p ON p.person_id = pna.person_id
        LEFT JOIN liberty_indirect_responsibility_edges e
          ON pna.canonical_alias = LOWER(TRIM(e.actor_person_name))
         AND e.edge_confidence >= :confidence_min
         AND e.causal_distance <= :max_distance
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
        WHERE ({alias_non_manual_predicate})
          AND NOT ({alias_official_with_source_record_predicate})
        GROUP BY
          pna.person_name_alias_id,
          TRIM(pna.alias),
          TRIM(COALESCE(p.full_name, '')),
          {alias_source_kind_select_expr},
          {alias_source_url_select_expr},
          {alias_evidence_date_select_expr},
          {alias_evidence_quote_select_expr},
          {alias_source_record_pk_select_expr}
        ORDER BY COUNT(e.edge_id) DESC, TRIM(pna.alias) ASC
        """,
        params,
    ).fetchall()
    official_alias_source_record_upgrade_queue_rows = []
    for rank, r in enumerate(official_alias_source_record_gap_rows, start=1):
        actor_person_name = _norm(r["actor_person_name"])
        official_alias_source_record_upgrade_queue_rows.append(
            {
                "queue_rank": rank,
                "queue_key": _stable_official_source_record_gap_queue_key(actor_person_name),
                "actor_person_name": actor_person_name,
                "person_name": _norm(r["person_name"]),
                "source_kind": _norm(r["source_kind"]) or "manual_seed",
                "source_url": _norm(r["source_url"]),
                "source_date": _norm(r["source_date"]),
                "evidence_quote": _norm(r["evidence_quote"]),
                "source_record_pk": int(r["source_record_pk"] or 0),
                "edges_total": int(r["edges_total"] or 0),
                "fragments_total": int(r["fragments_total"] or 0),
                "first_evidence_date": _norm(r["first_evidence_date"]),
                "last_evidence_date": _norm(r["last_evidence_date"]),
                "next_action": "attach_official_alias_source_record",
            }
        )

    valid_window_total = int(totals["indirect_person_edges_valid_window_total"] or 0)
    resolved_total = int(totals["indirect_person_edges_identity_resolved_total"] or 0)
    resolved_alias_total = int(totals["indirect_person_edges_identity_resolved_alias_total"] or 0)
    resolved_alias_non_manual_total = int(totals["indirect_person_edges_identity_resolved_alias_non_manual_total"] or 0)
    resolved_alias_manual_total = max(0, resolved_alias_total - resolved_alias_non_manual_total)
    unresolved_edges_total = max(0, valid_window_total - resolved_total)
    unresolved_actor_names_total = int(totals["unresolved_actor_names_total"] or 0)
    aliases_total_row = conn.execute("SELECT COUNT(*) AS n FROM person_name_aliases").fetchone()
    aliases_total = int((aliases_total_row["n"] if aliases_total_row is not None else 0) or 0)
    manual_alias_rows_total = len(manual_alias_upgrade_queue_rows)
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
    manual_alias_rows_with_edge_impact_total = sum(
        1 for r in manual_alias_upgrade_queue_rows if int(r["edges_total"] or 0) > 0
    )
    manual_alias_edges_with_impact_total = sum(int(r["edges_total"] or 0) for r in manual_alias_upgrade_queue_rows)

    coverage = {
        "indirect_identity_resolution_pct": round((resolved_total / valid_window_total) if valid_window_total else 0.0, 6),
        "indirect_identity_unresolved_pct": round((unresolved_edges_total / valid_window_total) if valid_window_total else 0.0, 6),
        "indirect_non_manual_alias_resolution_pct": round(
            (resolved_alias_non_manual_total / resolved_alias_total) if resolved_alias_total else 1.0,
            6,
        ),
        "manual_alias_share_pct": round((manual_alias_rows_total / aliases_total) if aliases_total else 0.0, 6),
        "manual_alias_upgrade_edge_impact_pct": round(
            (manual_alias_edges_with_impact_total / resolved_alias_total) if resolved_alias_total else 0.0,
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
        "queue_generated": True,
        "unresolved_backlog_visible": unresolved_edges_total == 0 or len(queue_rows) > 0,
        "manual_alias_upgrade_backlog_visible": (
            manual_alias_rows_with_edge_impact_total == 0 or manual_alias_rows_total > 0
        ),
        "official_alias_evidence_backlog_visible": (
            official_alias_rows_missing_evidence_total == 0
            or len(official_alias_evidence_upgrade_queue_rows) > 0
        ),
        "official_alias_source_record_backlog_visible": (
            official_alias_rows_missing_source_record_total == 0
            or len(official_alias_source_record_upgrade_queue_rows) > 0
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
        "identity_resolution_gate": (
            coverage["indirect_identity_resolution_pct"] >= float(identity_resolution_min_pct)
            and valid_window_total >= int(min_indirect_person_edges)
        ),
        "identity_non_manual_alias_resolution_gate": (
            resolved_alias_total == 0
            or (
                coverage["indirect_non_manual_alias_resolution_pct"] >= float(non_manual_alias_resolution_min_pct)
                and resolved_alias_total >= int(min_non_manual_alias_resolution_edges)
            )
        ),
    }
    gate_passed = all(bool(v) for v in checks.values())

    if valid_window_total == 0:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "indirect_person_edges_valid_window_total": valid_window_total,
            "indirect_person_edges_identity_resolved_total": resolved_total,
            "indirect_person_edges_identity_resolved_exact_name_total": int(
                totals["indirect_person_edges_identity_resolved_exact_name_total"] or 0
            ),
            "indirect_person_edges_identity_resolved_alias_total": resolved_alias_total,
            "indirect_person_edges_identity_resolved_alias_non_manual_total": resolved_alias_non_manual_total,
            "indirect_person_edges_identity_resolved_alias_manual_total": resolved_alias_manual_total,
            "indirect_person_edges_unresolved_total": unresolved_edges_total,
            "unresolved_actor_names_total": unresolved_actor_names_total,
            "queue_rows_total": len(queue_rows),
            "queue_truncated": bool(int(limit) > 0 and unresolved_actor_names_total > len(queue_rows)),
            "aliases_total": aliases_total,
            "manual_alias_rows_total": manual_alias_rows_total,
            "manual_alias_rows_with_edge_impact_total": manual_alias_rows_with_edge_impact_total,
            "manual_alias_edges_with_impact_total": manual_alias_edges_with_impact_total,
            "official_alias_rows_total": official_alias_rows_total,
            "official_alias_rows_with_evidence_total": official_alias_rows_with_evidence_total,
            "official_alias_rows_missing_evidence_total": official_alias_rows_missing_evidence_total,
            "official_alias_rows_with_source_record_total": official_alias_rows_with_source_record_total,
            "official_alias_rows_missing_source_record_total": official_alias_rows_missing_source_record_total,
            "manual_alias_upgrade_queue_rows_total": manual_alias_rows_total,
            "official_alias_evidence_upgrade_queue_rows_total": len(official_alias_evidence_upgrade_queue_rows),
            "official_alias_source_record_upgrade_queue_rows_total": len(
                official_alias_source_record_upgrade_queue_rows
            ),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "personal_confidence_min": float(personal_confidence_min),
                "personal_max_causal_distance": int(personal_max_causal_distance),
                "identity_resolution_min_pct": float(identity_resolution_min_pct),
                "min_indirect_person_edges": int(min_indirect_person_edges),
                "non_manual_alias_resolution_min_pct": float(non_manual_alias_resolution_min_pct),
                "min_non_manual_alias_resolution_edges": int(min_non_manual_alias_resolution_edges),
                "manual_alias_share_max": float(manual_alias_share_max),
                "min_alias_rows_for_manual_share_gate": int(min_alias_rows_for_manual_share_gate),
                "official_alias_share_min_pct": float(official_alias_share_min_pct),
                "min_alias_rows_for_official_share_gate": int(min_alias_rows_for_official_share_gate),
                "official_alias_evidence_min_pct": float(official_alias_evidence_min_pct),
                "min_official_alias_rows_for_evidence_gate": int(min_official_alias_rows_for_evidence_gate),
                "official_alias_source_record_min_pct": float(official_alias_source_record_min_pct),
                "min_official_alias_rows_for_source_record_gate": int(min_official_alias_rows_for_source_record_gate),
            },
        },
        "queue_preview": queue_rows[:20],
        "queue_rows": queue_rows,
        "manual_alias_upgrade_queue_preview": manual_alias_upgrade_queue_rows[:20],
        "manual_alias_upgrade_queue_rows": manual_alias_upgrade_queue_rows,
        "official_alias_evidence_upgrade_queue_preview": official_alias_evidence_upgrade_queue_rows[:20],
        "official_alias_evidence_upgrade_queue_rows": official_alias_evidence_upgrade_queue_rows,
        "official_alias_source_record_upgrade_queue_preview": official_alias_source_record_upgrade_queue_rows[:20],
        "official_alias_source_record_upgrade_queue_rows": official_alias_source_record_upgrade_queue_rows,
    }


def write_queue_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_rank",
        "queue_key",
        "actor_person_name",
        "actor_role_titles_csv",
        "edges_total",
        "fragments_total",
        "first_evidence_date",
        "last_evidence_date",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def write_manual_alias_upgrade_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_rank",
        "queue_key",
        "actor_person_name",
        "person_name",
        "source_kind",
        "edges_total",
        "fragments_total",
        "first_evidence_date",
        "last_evidence_date",
        "next_action",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def write_official_alias_evidence_upgrade_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_rank",
        "queue_key",
        "actor_person_name",
        "person_name",
        "source_kind",
        "source_record_pk",
        "missing_fields_csv",
        "edges_total",
        "fragments_total",
        "first_evidence_date",
        "last_evidence_date",
        "next_action",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def write_official_alias_source_record_upgrade_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_rank",
        "queue_key",
        "actor_person_name",
        "person_name",
        "source_kind",
        "source_url",
        "source_date",
        "source_record_pk",
        "edges_total",
        "fragments_total",
        "first_evidence_date",
        "last_evidence_date",
        "next_action",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report/export unresolved identity resolution queue for liberty personal scoring")
    ap.add_argument("--db", required=True)
    ap.add_argument("--personal-confidence-min", type=float, default=0.55)
    ap.add_argument("--personal-max-causal-distance", type=int, default=2)
    ap.add_argument("--identity-resolution-min-pct", type=float, default=0.0)
    ap.add_argument("--min-indirect-person-edges", type=int, default=1)
    ap.add_argument("--non-manual-alias-resolution-min-pct", type=float, default=0.0)
    ap.add_argument("--min-non-manual-alias-resolution-edges", type=int, default=1)
    ap.add_argument("--manual-alias-share-max", type=float, default=1.0)
    ap.add_argument("--min-alias-rows-for-manual-share-gate", type=int, default=1)
    ap.add_argument("--official-alias-share-min-pct", type=float, default=0.0)
    ap.add_argument("--min-alias-rows-for-official-share-gate", type=int, default=1)
    ap.add_argument("--official-alias-evidence-min-pct", type=float, default=1.0)
    ap.add_argument("--min-official-alias-rows-for-evidence-gate", type=int, default=1)
    ap.add_argument("--official-alias-source-record-min-pct", type=float, default=1.0)
    ap.add_argument("--min-official-alias-rows-for-source-record-gate", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--queue-csv-out", default="")
    ap.add_argument("--manual-alias-upgrade-csv-out", default="")
    ap.add_argument("--official-alias-evidence-upgrade-csv-out", default="")
    ap.add_argument("--official-alias-source-record-upgrade-csv-out", default="")
    ap.add_argument("--enforce-gate", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_report(
            conn,
            personal_confidence_min=float(args.personal_confidence_min),
            personal_max_causal_distance=int(args.personal_max_causal_distance),
            identity_resolution_min_pct=float(args.identity_resolution_min_pct),
            min_indirect_person_edges=int(args.min_indirect_person_edges),
            non_manual_alias_resolution_min_pct=float(args.non_manual_alias_resolution_min_pct),
            min_non_manual_alias_resolution_edges=int(args.min_non_manual_alias_resolution_edges),
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
            limit=int(args.limit),
        )
    finally:
        conn.close()

    if _norm(args.queue_csv_out):
        write_queue_csv(report.get("queue_rows", []), Path(args.queue_csv_out))
    if _norm(args.manual_alias_upgrade_csv_out):
        write_manual_alias_upgrade_csv(
            report.get("manual_alias_upgrade_queue_rows", []),
            Path(args.manual_alias_upgrade_csv_out),
        )
    if _norm(args.official_alias_evidence_upgrade_csv_out):
        write_official_alias_evidence_upgrade_csv(
            report.get("official_alias_evidence_upgrade_queue_rows", []),
            Path(args.official_alias_evidence_upgrade_csv_out),
        )
    if _norm(args.official_alias_source_record_upgrade_csv_out):
        write_official_alias_source_record_upgrade_csv(
            report.get("official_alias_source_record_upgrade_queue_rows", []),
            Path(args.official_alias_source_record_upgrade_csv_out),
        )
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
