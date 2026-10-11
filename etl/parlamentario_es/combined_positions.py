from __future__ import annotations

import re
import sqlite3
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Each method contributes its own latest snapshot (per topic_set) on or before the target date.
# Votes and declared positions are computed on different days; requiring the same as_of_date
# silently dropped every votes row whenever the dates differed, turning "combined" into "declared".
_SELECTED_CTE = """
WITH snap AS (
  SELECT computed_method, topic_set_id, MAX(as_of_date) AS d
  FROM topic_positions
  WHERE computed_method IN (:votes_method, :declared_method)
    AND as_of_date IS NOT NULL
    AND as_of_date <= :as_of
  GROUP BY computed_method, topic_set_id
),
ranked AS (
  SELECT
    tp.*,
    ROW_NUMBER() OVER (
      PARTITION BY tp.computed_method, tp.topic_set_id, tp.topic_id, tp.person_id, COALESCE(tp.mandate_id, -1)
      ORDER BY tp.computed_at DESC, tp.position_id DESC
    ) AS rn
  FROM topic_positions tp
  JOIN snap s
    ON s.computed_method = tp.computed_method
   AND s.topic_set_id = tp.topic_set_id
   AND s.d = tp.as_of_date
),
best_votes AS (
  SELECT * FROM ranked WHERE rn = 1 AND computed_method = :votes_method
),
best_decl AS (
  SELECT * FROM ranked WHERE rn = 1 AND computed_method = :declared_method
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
  )
)
"""


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

    Each method is read from its latest snapshot on or before as_of_date; the combined
    rows are stamped with as_of_date. This avoids inventing weights between "says" and
    "does"; it is a selector, not a mixer.
    """

    now_iso = now_utc_iso()
    as_of = normalize_ws(as_of_date)
    if not as_of or not _ISO_DATE_RE.match(as_of):
        raise ValueError("as_of_date debe ser YYYY-MM-DD")

    params: dict[str, Any] = {
        "votes_method": votes_method,
        "declared_method": declared_method,
        "as_of": as_of,
    }

    try:
        rows = conn.execute(
            _SELECTED_CTE
            + """
            SELECT computed_method AS m, as_of_date AS d, COUNT(*) AS c
            FROM selected
            GROUP BY computed_method, as_of_date
            ORDER BY computed_method, as_of_date
            """,
            params,
        ).fetchall()
    except sqlite3.Error:
        rows = []
    selected_by_method: dict[str, int] = {}
    source_as_of_dates: dict[str, list[str]] = {}
    for r in rows:
        method = str(r["m"])
        selected_by_method[method] = selected_by_method.get(method, 0) + int(r["c"] or 0)
        source_as_of_dates.setdefault(method, []).append(str(r["d"]))
    would_insert = sum(selected_by_method.values())
    trace = {
        "selected_from_votes": selected_by_method.get(votes_method, 0),
        "selected_from_declared": selected_by_method.get(declared_method, 0),
        "source_as_of_dates": source_as_of_dates,
    }

    if dry_run:
        return {
            "as_of_date": as_of,
            "dry_run": True,
            "combined_method": combined_method,
            "combined_version": combined_version,
            "would_insert": would_insert,
            **trace,
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
            _SELECTED_CTE
            + """
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
              :as_of AS as_of_date, window_days,
              stance, score, confidence, evidence_count, last_evidence_date,
              :combined_method AS computed_method,
              :combined_version AS computed_version,
              :now AS computed_at,
              :now AS created_at,
              :now AS updated_at
            FROM selected
            """,
            {
                **params,
                "combined_method": str(combined_method),
                "combined_version": str(combined_version),
                "now": now_iso,
            },
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
        **trace,
    }
