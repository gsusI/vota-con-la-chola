from __future__ import annotations

import re
import sqlite3
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def backfill_topic_positions_combined(
    conn: sqlite3.Connection,
    *,
    as_of_date: str,
    combined_method: str = "combined",
    combined_version: str = "v1",
    votes_method: str = "votes",
    declared_method: str = "declared",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build a deterministic 'best available' position per (topic_set, topic, person) for an as_of_date.

    Rule (KISS):
    - If a votes position exists, use it.
    - Else, if a declared position exists, use it.

    This avoids inventing weights between "says" and "does"; it is a selector, not a mixer.
    """

    now_iso = now_utc_iso()
    as_of = normalize_ws(as_of_date)
    if not as_of or not _ISO_DATE_RE.match(as_of):
        raise ValueError("as_of_date debe ser YYYY-MM-DD")

    # We pick the latest row per key by (computed_at, position_id) in case multiple versions exist.
    try:
        row = conn.execute(
            """
            WITH votes AS (
              SELECT
                *,
                ROW_NUMBER() OVER (
                  PARTITION BY topic_set_id, topic_id, person_id, COALESCE(mandate_id, -1), as_of_date
                  ORDER BY computed_at DESC, position_id DESC
                ) AS rn
              FROM topic_positions
              WHERE computed_method = ? AND as_of_date = ?
            ),
            decl AS (
              SELECT
                *,
                ROW_NUMBER() OVER (
                  PARTITION BY topic_set_id, topic_id, person_id, COALESCE(mandate_id, -1), as_of_date
                  ORDER BY computed_at DESC, position_id DESC
                ) AS rn
              FROM topic_positions
              WHERE computed_method = ? AND as_of_date = ?
            ),
            best_votes AS (
              SELECT * FROM votes WHERE rn = 1
            ),
            best_decl AS (
              SELECT * FROM decl WHERE rn = 1
            ),
            selected AS (
              SELECT * FROM best_votes
              UNION ALL
              SELECT d.*
              FROM best_decl d
              WHERE NOT EXISTS (
                SELECT 1
                FROM best_votes v
                WHERE v.topic_set_id = d.topic_set_id
                  AND v.topic_id = d.topic_id
                  AND v.person_id = d.person_id
                  AND COALESCE(v.mandate_id, -1) = COALESCE(d.mandate_id, -1)
                  AND v.as_of_date = d.as_of_date
              )
            )
            SELECT COUNT(*) AS c FROM selected
            """,
            (votes_method, as_of, declared_method, as_of),
        ).fetchone()
        would_insert = int(row["c"] or 0) if row else 0
    except sqlite3.Error:
        would_insert = 0

    if dry_run:
        return {
            "as_of_date": as_of,
            "dry_run": True,
            "combined_method": combined_method,
            "combined_version": combined_version,
            "would_insert": would_insert,
        }

    with conn:
        conn.execute(
            """
            DELETE FROM topic_positions
            WHERE computed_method = ?
              AND computed_version = ?
              AND as_of_date = ?
            """,
            (str(combined_method), str(combined_version), as_of),
        )

        conn.execute(
            """
            WITH votes AS (
              SELECT
                *,
                ROW_NUMBER() OVER (
                  PARTITION BY topic_set_id, topic_id, person_id, COALESCE(mandate_id, -1), as_of_date
                  ORDER BY computed_at DESC, position_id DESC
                ) AS rn
              FROM topic_positions
              WHERE computed_method = ? AND as_of_date = ?
            ),
            decl AS (
              SELECT
                *,
                ROW_NUMBER() OVER (
                  PARTITION BY topic_set_id, topic_id, person_id, COALESCE(mandate_id, -1), as_of_date
                  ORDER BY computed_at DESC, position_id DESC
                ) AS rn
              FROM topic_positions
              WHERE computed_method = ? AND as_of_date = ?
            ),
            best_votes AS (
              SELECT * FROM votes WHERE rn = 1
            ),
            best_decl AS (
              SELECT * FROM decl WHERE rn = 1
            ),
            selected AS (
              SELECT * FROM best_votes
              UNION ALL
              SELECT d.*
              FROM best_decl d
              WHERE NOT EXISTS (
                SELECT 1
                FROM best_votes v
                WHERE v.topic_set_id = d.topic_set_id
                  AND v.topic_id = d.topic_id
                  AND v.person_id = d.person_id
                  AND COALESCE(v.mandate_id, -1) = COALESCE(d.mandate_id, -1)
                  AND v.as_of_date = d.as_of_date
              )
            )
            INSERT INTO topic_positions (
              topic_id, topic_set_id,
              person_id, mandate_id,
              institution_id, admin_level_id, territory_id,
              as_of_date, window_days,
              stance, score, confidence, evidence_count, last_evidence_date,
              computed_method, computed_version, computed_at,
              created_at, updated_at
            )
            SELECT
              topic_id, topic_set_id,
              person_id, mandate_id,
              institution_id, admin_level_id, territory_id,
              as_of_date, window_days,
              stance, score, confidence, evidence_count, last_evidence_date,
              ? AS computed_method,
              ? AS computed_version,
              ? AS computed_at,
              ? AS created_at,
              ? AS updated_at
            FROM selected
            """,
            (
                votes_method,
                as_of,
                declared_method,
                as_of,
                str(combined_method),
                str(combined_version),
                now_iso,
                now_iso,
                now_iso,
            ),
        )

        inserted = int(
            (
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM topic_positions
                    WHERE computed_method = ?
                      AND computed_version = ?
                      AND as_of_date = ?
                    """,
                    (str(combined_method), str(combined_version), as_of),
                ).fetchone()
                or {"c": 0}
            )["c"]
        )

    return {
        "as_of_date": as_of,
        "dry_run": False,
        "combined_method": combined_method,
        "combined_version": combined_version,
        "inserted": inserted,
        "would_insert": would_insert,
    }
