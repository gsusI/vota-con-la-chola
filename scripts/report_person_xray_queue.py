#!/usr/bin/env python3
"""Build person xray diagnostics and maintain a public-data gap queue."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_DB, DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db

PUBLIC_SCOPE_SET = ("nacional", "europeo", "autonomico")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_queue_schema_only(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS person_public_data_queue (
          person_public_data_queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
          queue_key TEXT NOT NULL UNIQUE,
          person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
          person_name TEXT NOT NULL,
          gap_code TEXT NOT NULL,
          scope_key TEXT NOT NULL DEFAULT '',
          priority INTEGER NOT NULL DEFAULT 50,
          is_publicly_available INTEGER NOT NULL DEFAULT 1 CHECK (is_publicly_available IN (0, 1)),
          status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'resolved', 'ignored')) DEFAULT 'pending',
          rationale TEXT NOT NULL,
          next_action TEXT NOT NULL,
          suggested_source_id TEXT REFERENCES sources(source_id),
          suggested_source_url TEXT,
          detection_payload_json TEXT NOT NULL DEFAULT '{}',
          first_detected_at TEXT NOT NULL,
          last_detected_at TEXT NOT NULL,
          resolved_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (person_id, gap_code, scope_key)
        );
        CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_person_id ON person_public_data_queue(person_id);
        CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_status ON person_public_data_queue(status);
        CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_priority ON person_public_data_queue(priority);
        CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_gap_code ON person_public_data_queue(gap_code);
        CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_source_id ON person_public_data_queue(suggested_source_id);
        """
    )
    conn.commit()


def _apply_schema_with_lock_fallback(conn: sqlite3.Connection, schema_path: Path) -> None:
    try:
        apply_schema(conn, schema_path)
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        # On heavily used DBs, full schema re-apply can fail under lock contention.
        # Keep report operable by ensuring only the queue table/indexes required here.
        _ensure_queue_schema_only(conn)


def _load_source_lookup(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    rows = conn.execute(
        """
        SELECT source_id, default_url, name, scope
        FROM sources
        """
    ).fetchall()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        sid = _norm(row["source_id"])
        if not sid:
            continue
        out[sid] = {
            "default_url": _norm(row["default_url"]),
            "name": _norm(row["name"]),
            "scope": _norm(row["scope"]),
        }
    return out


def _queue_key(person_id: int, gap_code: str, scope_key: str) -> str:
    return f"person:{person_id}|{gap_code}|{scope_key or 'global'}"


def _add_gap_row(
    *,
    rows: list[dict[str, Any]],
    source_lookup: dict[str, dict[str, str]],
    person_id: int,
    person_name: str,
    gap_code: str,
    scope_key: str,
    priority: int,
    rationale: str,
    next_action: str,
    suggested_source_id: str,
    payload: dict[str, Any],
) -> None:
    suggested_source_id_norm = _norm(suggested_source_id)
    source_meta = source_lookup.get(suggested_source_id_norm, {})
    suggested_source_url = _norm(source_meta.get("default_url"))
    rows.append(
        {
            "queue_key": _queue_key(person_id, gap_code, scope_key),
            "person_id": int(person_id),
            "person_name": _norm(person_name),
            "gap_code": gap_code,
            "scope_key": _norm(scope_key),
            "priority": int(priority),
            "is_publicly_available": 1,
            "rationale": rationale,
            "next_action": next_action,
            "suggested_source_id": suggested_source_id_norm,
            "suggested_source_url": suggested_source_url,
            "detection_payload_json": _json_dumps(payload),
        }
    )


def detect_public_data_gaps(
    conn: sqlite3.Connection,
    *,
    source_lookup: dict[str, dict[str, str]],
    person_id: int | None = None,
    include_party_proxies: bool = False,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    person_filter_sql = ""
    if person_id is not None:
        person_filter_sql = "AND p.person_id = :person_id"
        params["person_id"] = int(person_id)
    exclude_party_sql = "" if include_party_proxies else "AND p.canonical_key NOT LIKE 'party:%'"

    out: list[dict[str, Any]] = []

    public_scope_csv = ", ".join(f"'{v}'" for v in PUBLIC_SCOPE_SET)

    birth_rows = conn.execute(
        f"""
        WITH public_mandate_source AS (
          SELECT
            m.person_id,
            m.source_id,
            COUNT(*) AS rows_n,
            ROW_NUMBER() OVER (
              PARTITION BY m.person_id
              ORDER BY COUNT(*) DESC, m.source_id ASC
            ) AS rn
          FROM mandates m
          JOIN sources s ON s.source_id = m.source_id
          WHERE s.scope IN ({public_scope_csv})
          GROUP BY m.person_id, m.source_id
        )
        SELECT
          p.person_id,
          p.full_name,
          pms.source_id,
          pms.rows_n
        FROM persons p
        JOIN public_mandate_source pms
          ON pms.person_id = p.person_id
         AND pms.rn = 1
        WHERE TRIM(COALESCE(p.birth_date, '')) = ''
          {exclude_party_sql}
          {person_filter_sql}
        ORDER BY p.person_id
        """,
        params,
    ).fetchall()
    for row in birth_rows:
        _add_gap_row(
            rows=out,
            source_lookup=source_lookup,
            person_id=int(row["person_id"]),
            person_name=_norm(row["full_name"]),
            gap_code="missing_birth_date_public_profile",
            scope_key="identity",
            priority=80,
            rationale="Missing birth_date while holding public mandates with official profile sources.",
            next_action="backfill_birth_date_from_official_profile",
            suggested_source_id=_norm(row["source_id"]),
            payload={
                "public_mandate_rows": int(row["rows_n"] or 0),
                "suggested_source_id": _norm(row["source_id"]),
            },
        )

    gender_rows = conn.execute(
        f"""
        WITH public_mandate_source AS (
          SELECT
            m.person_id,
            m.source_id,
            COUNT(*) AS rows_n,
            ROW_NUMBER() OVER (
              PARTITION BY m.person_id
              ORDER BY COUNT(*) DESC, m.source_id ASC
            ) AS rn
          FROM mandates m
          JOIN sources s ON s.source_id = m.source_id
          WHERE s.scope IN ({public_scope_csv})
          GROUP BY m.person_id, m.source_id
        )
        SELECT
          p.person_id,
          p.full_name,
          pms.source_id,
          pms.rows_n
        FROM persons p
        LEFT JOIN genders g ON g.gender_id = p.gender_id
        JOIN public_mandate_source pms
          ON pms.person_id = p.person_id
         AND pms.rn = 1
        WHERE (
            p.gender_id IS NULL
            OR LOWER(TRIM(COALESCE(g.code, ''))) = 'u'
            OR LOWER(TRIM(COALESCE(g.label, ''))) IN ('desconocido', 'unknown')
          )
          AND LOWER(TRIM(COALESCE(p.gender, ''))) IN ('', 'u', 'desconocido', 'unknown')
          {exclude_party_sql}
          {person_filter_sql}
        ORDER BY p.person_id
        """,
        params,
    ).fetchall()
    for row in gender_rows:
        _add_gap_row(
            rows=out,
            source_lookup=source_lookup,
            person_id=int(row["person_id"]),
            person_name=_norm(row["full_name"]),
            gap_code="missing_gender_public_profile",
            scope_key="identity",
            priority=60,
            rationale="Missing gender normalization while official public profile data likely contains this field.",
            next_action="backfill_gender_from_official_profile",
            suggested_source_id=_norm(row["source_id"]),
            payload={
                "public_mandate_rows": int(row["rows_n"] or 0),
                "suggested_source_id": _norm(row["source_id"]),
            },
        )

    territory_rows = conn.execute(
        f"""
        WITH public_mandate_source AS (
          SELECT
            m.person_id,
            m.source_id,
            COUNT(*) AS rows_n,
            ROW_NUMBER() OVER (
              PARTITION BY m.person_id
              ORDER BY COUNT(*) DESC, m.source_id ASC
            ) AS rn
          FROM mandates m
          JOIN sources s ON s.source_id = m.source_id
          WHERE s.scope IN ({public_scope_csv})
          GROUP BY m.person_id, m.source_id
        )
        SELECT
          p.person_id,
          p.full_name,
          pms.source_id,
          pms.rows_n
        FROM persons p
        JOIN public_mandate_source pms
          ON pms.person_id = p.person_id
         AND pms.rn = 1
        WHERE p.territory_id IS NULL
          AND TRIM(COALESCE(p.territory_code, '')) = ''
          {exclude_party_sql}
          {person_filter_sql}
        ORDER BY p.person_id
        """,
        params,
    ).fetchall()
    for row in territory_rows:
        _add_gap_row(
            rows=out,
            source_lookup=source_lookup,
            person_id=int(row["person_id"]),
            person_name=_norm(row["full_name"]),
            gap_code="missing_territory_public_profile",
            scope_key="identity",
            priority=55,
            rationale="Missing person territory for a public-mandate profile where territory is usually published.",
            next_action="backfill_person_territory_from_official_profile",
            suggested_source_id=_norm(row["source_id"]),
            payload={
                "public_mandate_rows": int(row["rows_n"] or 0),
                "suggested_source_id": _norm(row["source_id"]),
            },
        )

    declared_rows = conn.execute(
        f"""
        WITH vote_totals AS (
          SELECT person_id, COUNT(*) AS votes_total
          FROM parl_vote_member_votes
          WHERE person_id IS NOT NULL
          GROUP BY person_id
        ),
        vote_source_top AS (
          SELECT
            person_id,
            source_id,
            COUNT(*) AS rows_n,
            ROW_NUMBER() OVER (
              PARTITION BY person_id
              ORDER BY COUNT(*) DESC, source_id ASC
            ) AS rn
          FROM parl_vote_member_votes
          WHERE person_id IS NOT NULL
          GROUP BY person_id, source_id
        ),
        declared_totals AS (
          SELECT person_id, COUNT(*) AS declared_total
          FROM topic_evidence
          WHERE evidence_type LIKE 'declared:%'
          GROUP BY person_id
        )
        SELECT
          p.person_id,
          p.full_name,
          vt.votes_total,
          COALESCE(dt.declared_total, 0) AS declared_total,
          vst.source_id,
          vst.rows_n
        FROM persons p
        JOIN vote_totals vt ON vt.person_id = p.person_id
        JOIN vote_source_top vst
          ON vst.person_id = p.person_id
         AND vst.rn = 1
        LEFT JOIN declared_totals dt ON dt.person_id = p.person_id
        WHERE COALESCE(dt.declared_total, 0) = 0
          {exclude_party_sql}
          {person_filter_sql}
        ORDER BY p.person_id
        """,
        params,
    ).fetchall()
    for row in declared_rows:
        _add_gap_row(
            rows=out,
            source_lookup=source_lookup,
            person_id=int(row["person_id"]),
            person_name=_norm(row["full_name"]),
            gap_code="missing_declared_evidence",
            scope_key="declared",
            priority=70,
            rationale="Person has vote activity but no declared evidence rows (interventions/programs).",
            next_action="backfill_declared_sources_for_person",
            suggested_source_id=_norm(row["source_id"]),
            payload={
                "votes_total": int(row["votes_total"] or 0),
                "declared_total": int(row["declared_total"] or 0),
                "top_vote_source_rows": int(row["rows_n"] or 0),
                "suggested_source_id": _norm(row["source_id"]),
            },
        )

    alias_rows = conn.execute(
        f"""
        WITH vote_name_variants AS (
          SELECT
            person_id,
            COUNT(
              DISTINCT LOWER(TRIM(COALESCE(NULLIF(member_name_normalized, ''), member_name, '')))
            ) AS variants_total
          FROM parl_vote_member_votes
          WHERE person_id IS NOT NULL
          GROUP BY person_id
          HAVING COUNT(
              DISTINCT LOWER(TRIM(COALESCE(NULLIF(member_name_normalized, ''), member_name, '')))
            ) > 1
        ),
        vote_source_top AS (
          SELECT
            person_id,
            source_id,
            COUNT(*) AS rows_n,
            ROW_NUMBER() OVER (
              PARTITION BY person_id
              ORDER BY COUNT(*) DESC, source_id ASC
            ) AS rn
          FROM parl_vote_member_votes
          WHERE person_id IS NOT NULL
          GROUP BY person_id, source_id
        ),
        alias_totals AS (
          SELECT person_id, COUNT(*) AS aliases_total
          FROM person_name_aliases
          GROUP BY person_id
        )
        SELECT
          p.person_id,
          p.full_name,
          vnv.variants_total,
          COALESCE(at.aliases_total, 0) AS aliases_total,
          vst.source_id,
          vst.rows_n
        FROM persons p
        JOIN vote_name_variants vnv ON vnv.person_id = p.person_id
        JOIN vote_source_top vst
          ON vst.person_id = p.person_id
         AND vst.rn = 1
        LEFT JOIN alias_totals at ON at.person_id = p.person_id
        WHERE COALESCE(at.aliases_total, 0) = 0
          {exclude_party_sql}
          {person_filter_sql}
        ORDER BY p.person_id
        """,
        params,
    ).fetchall()
    for row in alias_rows:
        _add_gap_row(
            rows=out,
            source_lookup=source_lookup,
            person_id=int(row["person_id"]),
            person_name=_norm(row["full_name"]),
            gap_code="missing_name_aliases_for_vote_variants",
            scope_key="alias",
            priority=75,
            rationale="Multiple vote-name variants detected but no person_name_aliases rows exist.",
            next_action="seed_person_name_aliases_from_official_vote_variants",
            suggested_source_id=_norm(row["source_id"]),
            payload={
                "variants_total": int(row["variants_total"] or 0),
                "aliases_total": int(row["aliases_total"] or 0),
                "top_vote_source_rows": int(row["rows_n"] or 0),
                "suggested_source_id": _norm(row["source_id"]),
            },
        )

    out.sort(key=lambda row: (-int(row["priority"]), int(row["person_id"]), _norm(row["gap_code"]), _norm(row["scope_key"])))
    return out


def enqueue_gaps(
    conn: sqlite3.Connection,
    *,
    gap_rows: list[dict[str, Any]],
    person_id: int | None,
    reconcile_resolved: bool = True,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    conn.execute("DROP TABLE IF EXISTS tmp_person_public_data_queue_keys")
    conn.execute("CREATE TEMP TABLE tmp_person_public_data_queue_keys(queue_key TEXT PRIMARY KEY)")
    if gap_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_person_public_data_queue_keys(queue_key) VALUES (?)",
            [(str(row["queue_key"]),) for row in gap_rows],
        )

    conn.executemany(
        """
        INSERT INTO person_public_data_queue (
          queue_key,
          person_id,
          person_name,
          gap_code,
          scope_key,
          priority,
          is_publicly_available,
          status,
          rationale,
          next_action,
          suggested_source_id,
          suggested_source_url,
          detection_payload_json,
          first_detected_at,
          last_detected_at,
          resolved_at,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        ON CONFLICT(queue_key) DO UPDATE SET
          person_name=excluded.person_name,
          priority=excluded.priority,
          rationale=excluded.rationale,
          next_action=excluded.next_action,
          suggested_source_id=excluded.suggested_source_id,
          suggested_source_url=excluded.suggested_source_url,
          detection_payload_json=excluded.detection_payload_json,
          last_detected_at=excluded.last_detected_at,
          updated_at=excluded.updated_at,
          status=CASE
            WHEN person_public_data_queue.status = 'resolved' THEN 'pending'
            ELSE person_public_data_queue.status
          END,
          resolved_at=CASE
            WHEN person_public_data_queue.status = 'resolved' THEN NULL
            ELSE person_public_data_queue.resolved_at
          END
        """,
        [
            (
                _norm(row["queue_key"]),
                int(row["person_id"]),
                _norm(row["person_name"]),
                _norm(row["gap_code"]),
                _norm(row["scope_key"]),
                int(row["priority"]),
                int(row["is_publicly_available"]),
                _norm(row["rationale"]),
                _norm(row["next_action"]),
                _norm(row["suggested_source_id"]),
                _norm(row["suggested_source_url"]),
                _norm(row["detection_payload_json"]),
                now_iso,
                now_iso,
                now_iso,
                now_iso,
            )
            for row in gap_rows
        ],
    )

    resolved_rows = 0
    if reconcile_resolved:
        if person_id is not None:
            resolved_rows = int(
                conn.execute(
                    """
                    UPDATE person_public_data_queue
                    SET
                      status='resolved',
                      resolved_at=?,
                      updated_at=?
                    WHERE person_id = ?
                      AND status IN ('pending', 'in_progress')
                      AND queue_key NOT IN (
                        SELECT queue_key
                        FROM tmp_person_public_data_queue_keys
                      )
                    """,
                    (now_iso, now_iso, int(person_id)),
                ).rowcount
                or 0
            )
        else:
            resolved_rows = int(
                conn.execute(
                    """
                    UPDATE person_public_data_queue
                    SET
                      status='resolved',
                      resolved_at=?,
                      updated_at=?
                    WHERE status IN ('pending', 'in_progress')
                      AND queue_key NOT IN (
                        SELECT queue_key
                        FROM tmp_person_public_data_queue_keys
                      )
                    """,
                    (now_iso, now_iso),
                ).rowcount
                or 0
            )

    conn.commit()
    return {
        "detected_rows_total": len(gap_rows),
        "auto_resolved_rows_total": int(resolved_rows),
    }


def _fetch_queue_rows(
    conn: sqlite3.Connection,
    *,
    person_id: int | None,
    queue_limit: int,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if person_id is not None:
        where = "WHERE person_id = ?"
        params.append(int(person_id))
    sql = f"""
        SELECT
          queue_key,
          person_id,
          person_name,
          gap_code,
          scope_key,
          priority,
          status,
          rationale,
          next_action,
          suggested_source_id,
          suggested_source_url,
          detection_payload_json,
          first_detected_at,
          last_detected_at,
          resolved_at
        FROM person_public_data_queue
        {where}
        ORDER BY
          CASE status
            WHEN 'pending' THEN 0
            WHEN 'in_progress' THEN 1
            WHEN 'resolved' THEN 2
            ELSE 3
          END ASC,
          priority DESC,
          last_detected_at DESC,
          person_id ASC,
          gap_code ASC
    """
    if int(queue_limit) > 0:
        sql += "\nLIMIT ?"
        params.append(int(queue_limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def _fetch_queue_totals(conn: sqlite3.Connection, *, person_id: int | None) -> dict[str, Any]:
    params: list[Any] = []
    where = ""
    if person_id is not None:
        where = "WHERE person_id = ?"
        params.append(int(person_id))
    totals_row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS queue_rows_total,
          SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS queue_pending_total,
          SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS queue_in_progress_total,
          SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS queue_resolved_total,
          SUM(CASE WHEN status = 'ignored' THEN 1 ELSE 0 END) AS queue_ignored_total
        FROM person_public_data_queue
        {where}
        """,
        tuple(params),
    ).fetchone()
    by_gap_rows = conn.execute(
        f"""
        SELECT gap_code, COUNT(*) AS n
        FROM person_public_data_queue
        {where}
        GROUP BY gap_code
        ORDER BY n DESC, gap_code ASC
        """,
        tuple(params),
    ).fetchall()
    return {
        "queue_rows_total": int((totals_row["queue_rows_total"] if totals_row else 0) or 0),
        "queue_pending_total": int((totals_row["queue_pending_total"] if totals_row else 0) or 0),
        "queue_in_progress_total": int((totals_row["queue_in_progress_total"] if totals_row else 0) or 0),
        "queue_resolved_total": int((totals_row["queue_resolved_total"] if totals_row else 0) or 0),
        "queue_ignored_total": int((totals_row["queue_ignored_total"] if totals_row else 0) or 0),
        "queue_by_gap_code": [
            {"gap_code": _norm(row["gap_code"]), "rows_total": int(row["n"] or 0)} for row in by_gap_rows
        ],
    }


def _fetch_person_xray(conn: sqlite3.Connection, *, person_id: int) -> dict[str, Any] | None:
    person = conn.execute(
        """
        SELECT
          p.person_id,
          p.full_name,
          p.given_name,
          p.family_name,
          p.canonical_key,
          p.birth_date,
          p.gender,
          p.gender_id,
          g.label AS gender_label,
          p.territory_code,
          p.territory_id,
          t.name AS territory_name,
          p.created_at,
          p.updated_at
        FROM persons p
        LEFT JOIN genders g ON g.gender_id = p.gender_id
        LEFT JOIN territories t ON t.territory_id = p.territory_id
        WHERE p.person_id = ?
        """,
        (int(person_id),),
    ).fetchone()
    if person is None:
        return None

    summary = conn.execute(
        """
        WITH mandate_agg AS (
          SELECT
            m.person_id,
            COUNT(*) AS mandates_total,
            SUM(CASE WHEN m.is_active = 1 THEN 1 ELSE 0 END) AS active_mandates,
            COUNT(DISTINCT m.institution_id) AS institutions_total,
            COUNT(DISTINCT m.party_id) AS parties_total,
            MIN(CASE WHEN m.start_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN m.start_date END) AS first_mandate_start,
            MAX(CASE WHEN COALESCE(m.end_date, m.start_date) GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN COALESCE(m.end_date, m.start_date) END) AS last_mandate_date
          FROM mandates m
          WHERE m.person_id = ?
          GROUP BY m.person_id
        ),
        vote_agg AS (
          SELECT
            mv.person_id,
            COUNT(*) AS votes_total,
            COUNT(DISTINCT mv.vote_event_id) AS vote_events_total,
            MIN(CASE WHEN e.vote_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN e.vote_date END) AS first_vote_date,
            MAX(CASE WHEN e.vote_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN e.vote_date END) AS last_vote_date
          FROM parl_vote_member_votes mv
          LEFT JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
          WHERE mv.person_id = ?
          GROUP BY mv.person_id
        ),
        evidence_agg AS (
          SELECT
            te.person_id,
            COUNT(*) AS evidence_total,
            SUM(CASE WHEN te.evidence_type LIKE 'declared:%' THEN 1 ELSE 0 END) AS declared_evidence_total,
            SUM(CASE WHEN te.evidence_type = 'revealed:vote' THEN 1 ELSE 0 END) AS revealed_vote_evidence_total
          FROM topic_evidence te
          WHERE te.person_id = ?
          GROUP BY te.person_id
        ),
        position_agg AS (
          SELECT
            tp.person_id,
            COUNT(*) AS topic_positions_total,
            SUM(CASE WHEN tp.computed_method = 'combined' THEN 1 ELSE 0 END) AS topic_positions_combined_total
          FROM topic_positions tp
          WHERE tp.person_id = ?
          GROUP BY tp.person_id
        ),
        ids AS (
          SELECT person_id, COUNT(*) AS identifiers_total
          FROM person_identifiers
          WHERE person_id = ?
          GROUP BY person_id
        ),
        aliases AS (
          SELECT person_id, COUNT(*) AS aliases_total
          FROM person_name_aliases
          WHERE person_id = ?
          GROUP BY person_id
        )
        SELECT
          COALESCE(ma.mandates_total, 0) AS mandates_total,
          COALESCE(ma.active_mandates, 0) AS active_mandates,
          COALESCE(ma.institutions_total, 0) AS institutions_total,
          COALESCE(ma.parties_total, 0) AS parties_total,
          ma.first_mandate_start,
          ma.last_mandate_date,
          COALESCE(va.votes_total, 0) AS votes_total,
          COALESCE(va.vote_events_total, 0) AS vote_events_total,
          va.first_vote_date,
          va.last_vote_date,
          COALESCE(ea.evidence_total, 0) AS evidence_total,
          COALESCE(ea.declared_evidence_total, 0) AS declared_evidence_total,
          COALESCE(ea.revealed_vote_evidence_total, 0) AS revealed_vote_evidence_total,
          COALESCE(pa.topic_positions_total, 0) AS topic_positions_total,
          COALESCE(pa.topic_positions_combined_total, 0) AS topic_positions_combined_total,
          COALESCE(ids.identifiers_total, 0) AS identifiers_total,
          COALESCE(als.aliases_total, 0) AS aliases_total
        FROM (SELECT ? AS person_id) x
        LEFT JOIN mandate_agg ma ON ma.person_id = x.person_id
        LEFT JOIN vote_agg va ON va.person_id = x.person_id
        LEFT JOIN evidence_agg ea ON ea.person_id = x.person_id
        LEFT JOIN position_agg pa ON pa.person_id = x.person_id
        LEFT JOIN ids ON ids.person_id = x.person_id
        LEFT JOIN aliases als ON als.person_id = x.person_id
        """,
        (int(person_id), int(person_id), int(person_id), int(person_id), int(person_id), int(person_id), int(person_id)),
    ).fetchone()

    mandates_history = conn.execute(
        """
        SELECT
          COALESCE(r.title, m.role_title) AS role_title,
          i.name AS institution_name,
          COALESCE(pa.acronym, pa.name, '') AS party,
          al.label AS admin_level,
          te.name AS territory_name,
          MIN(m.start_date) AS first_start_date,
          MAX(COALESCE(m.end_date, m.start_date)) AS last_end_date,
          MAX(m.is_active) AS currently_active,
          COUNT(*) AS source_rows
        FROM mandates m
        LEFT JOIN roles r ON r.role_id = m.role_id
        LEFT JOIN institutions i ON i.institution_id = m.institution_id
        LEFT JOIN parties pa ON pa.party_id = m.party_id
        LEFT JOIN admin_levels al ON al.admin_level_id = m.admin_level_id
        LEFT JOIN territories te ON te.territory_id = m.territory_id
        WHERE m.person_id = ?
        GROUP BY
          COALESCE(r.title, m.role_title),
          i.name,
          COALESCE(pa.acronym, pa.name, ''),
          al.label,
          te.name
        ORDER BY first_start_date ASC, role_title ASC
        """,
        (int(person_id),),
    ).fetchall()

    recent_actions = conn.execute(
        """
        WITH vote_actions AS (
          SELECT
            mv.person_id,
            e.vote_date AS action_date,
            'vote' AS action_type,
            mv.vote_event_id AS action_key,
            e.title AS action_title,
            mv.vote_choice AS action_value,
            mv.source_id AS source_id,
            CASE
              WHEN mv.source_url LIKE 'file:///%' THEN ''
              ELSE COALESCE(mv.source_url, '')
            END AS source_url
          FROM parl_vote_member_votes mv
          JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
          WHERE mv.person_id = ?
        ),
        declared_actions AS (
          SELECT
            te.person_id,
            te.evidence_date AS action_date,
            te.evidence_type AS action_type,
            CAST(te.evidence_id AS TEXT) AS action_key,
            te.title AS action_title,
            te.stance AS action_value,
            te.source_id AS source_id,
            CASE
              WHEN te.source_url LIKE 'file:///%' THEN ''
              ELSE COALESCE(te.source_url, '')
            END AS source_url
          FROM topic_evidence te
          WHERE te.person_id = ?
            AND te.evidence_type LIKE 'declared:%'
        )
        SELECT *
        FROM (
          SELECT * FROM vote_actions
          UNION ALL
          SELECT * FROM declared_actions
        )
        ORDER BY action_date DESC, action_type ASC, action_key DESC
        LIMIT 25
        """,
        (int(person_id), int(person_id)),
    ).fetchall()

    return {
        "person": dict(person),
        "summary": dict(summary) if summary is not None else {},
        "mandates_history": [dict(row) for row in mandates_history],
        "recent_actions": [dict(row) for row in recent_actions],
    }


def build_report(
    conn: sqlite3.Connection,
    *,
    person_id: int | None = None,
    include_party_proxies: bool = False,
    enqueue: bool = True,
    reconcile_resolved: bool = True,
    queue_limit: int = 200,
) -> dict[str, Any]:
    source_lookup = _load_source_lookup(conn)
    detected_rows = detect_public_data_gaps(
        conn,
        source_lookup=source_lookup,
        person_id=person_id,
        include_party_proxies=include_party_proxies,
    )

    enqueue_summary: dict[str, Any] = {
        "detected_rows_total": len(detected_rows),
        "auto_resolved_rows_total": 0,
    }
    if enqueue:
        enqueue_summary = enqueue_gaps(
            conn,
            gap_rows=detected_rows,
            person_id=person_id,
            reconcile_resolved=reconcile_resolved,
        )

    queue_totals = _fetch_queue_totals(conn, person_id=person_id)
    queue_rows = _fetch_queue_rows(conn, person_id=person_id, queue_limit=queue_limit)

    xray = None
    if person_id is not None:
        xray = _fetch_person_xray(conn, person_id=int(person_id))
        if xray is not None:
            xray["detected_gaps"] = [row for row in detected_rows if int(row["person_id"]) == int(person_id)]

    pending_total = int(queue_totals["queue_pending_total"])
    in_progress_total = int(queue_totals["queue_in_progress_total"])
    status = "degraded" if (pending_total + in_progress_total) > 0 else "ok"
    if person_id is not None and xray is None:
        status = "failed"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "scope": {
            "person_id": int(person_id) if person_id is not None else None,
            "include_party_proxies": bool(include_party_proxies),
        },
        "enqueue": {
            "enabled": bool(enqueue),
            **enqueue_summary,
        },
        "queue_totals": queue_totals,
        "queue_rows": queue_rows,
        "xray": xray,
    }


def _write_queue_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    _ensure_parent(out_path)
    fieldnames = [
        "queue_key",
        "person_id",
        "person_name",
        "gap_code",
        "scope_key",
        "priority",
        "status",
        "rationale",
        "next_action",
        "suggested_source_id",
        "suggested_source_url",
        "detection_payload_json",
        "first_detected_at",
        "last_detected_at",
        "resolved_at",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Person xray + public data gap queue")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Schema SQL path")
    ap.add_argument("--person-id", type=int, default=0, help="Optional person_id scope (0=all)")
    ap.add_argument("--queue-limit", type=int, default=200, help="Queue rows returned in JSON output")
    ap.add_argument("--out", default="", help="Write full JSON report to this path")
    ap.add_argument("--csv-out", default="", help="Write queue rows CSV to this path")
    ap.add_argument(
        "--include-party-proxies",
        action="store_true",
        help="Include canonical_key like party:* in gap detection",
    )
    ap.add_argument(
        "--enqueue",
        dest="enqueue",
        action="store_true",
        default=True,
        help="Upsert detected gaps into person_public_data_queue (default: true)",
    )
    ap.add_argument(
        "--no-enqueue",
        dest="enqueue",
        action="store_false",
        help="Do not upsert; compute report only",
    )
    ap.add_argument(
        "--no-reconcile-resolved",
        action="store_true",
        help="Do not auto-resolve pending/in_progress rows that are no longer detected",
    )
    ap.add_argument(
        "--strict-empty-queue",
        action="store_true",
        help="Exit with code 4 when queue has pending/in_progress rows in selected scope",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    schema_path = Path(args.schema)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}")
        return 2
    if not schema_path.exists():
        print(f"Schema no encontrado: {schema_path}")
        return 2

    person_id = int(args.person_id) if int(args.person_id or 0) > 0 else None
    conn = open_db(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 120000")
        _apply_schema_with_lock_fallback(conn, schema_path)
        report = build_report(
            conn,
            person_id=person_id,
            include_party_proxies=bool(args.include_party_proxies),
            enqueue=bool(args.enqueue),
            reconcile_resolved=not bool(args.no_reconcile_resolved),
            queue_limit=int(args.queue_limit),
        )
    finally:
        conn.close()

    out_path = _norm(args.out)
    if out_path:
        target = Path(out_path)
        _ensure_parent(target)
        target.write_text(_json_dumps(report), encoding="utf-8")

    csv_out = _norm(args.csv_out)
    if csv_out:
        _write_queue_csv(report.get("queue_rows") or [], Path(csv_out))

    print(_json_dumps(report))

    pending_total = int((report.get("queue_totals") or {}).get("queue_pending_total") or 0)
    in_progress_total = int((report.get("queue_totals") or {}).get("queue_in_progress_total") or 0)
    if bool(args.strict_empty_queue) and (pending_total + in_progress_total) > 0:
        return 4
    if report.get("status") == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
