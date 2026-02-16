from __future__ import annotations

import re
import sqlite3
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def backfill_topic_positions_from_declared_evidence(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    as_of_date: str,
    computed_method: str = "declared",
    computed_version: str = "v1",
    stance_methods: tuple[str, ...] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Compute topic_positions from declared evidence with stance signals.

    This is a deterministic aggregation over `topic_evidence` (declared:*) filtered
    to one or more `stance_method` values that produce polarity (+1/-1/0).
    """

    now_iso = now_utc_iso()
    as_of = normalize_ws(as_of_date)
    if not as_of or not _ISO_DATE_RE.match(as_of):
        raise ValueError("as_of_date debe ser YYYY-MM-DD")
    resolved_stance_methods = tuple(
        normalize_ws(m)
        for m in (
            stance_methods
            if stance_methods is not None
            else ("declared:regex_v2", "declared:regex_v1")
        )
        if normalize_ws(m)
    )
    if not resolved_stance_methods:
        raise ValueError("stance_methods vacio")
    stance_ph = ",".join("?" for _ in resolved_stance_methods)

    topic_set_ids = [
        int(r["topic_set_id"])
        for r in conn.execute(
            """
            SELECT DISTINCT topic_set_id
            FROM topic_evidence
            WHERE source_id = ?
              AND evidence_type LIKE 'declared:%'
              AND topic_set_id IS NOT NULL
            ORDER BY topic_set_id ASC
            """,
            (source_id,),
        ).fetchall()
        if r["topic_set_id"] is not None
    ]

    per_set: list[dict[str, Any]] = []
    total_positions = 0

    for topic_set_id in topic_set_ids:
        set_row = conn.execute(
            "SELECT institution_id, admin_level_id, territory_id FROM topic_sets WHERE topic_set_id = ?",
            (int(topic_set_id),),
        ).fetchone()
        institution_id = set_row["institution_id"] if set_row is not None else None
        admin_level_id = set_row["admin_level_id"] if set_row is not None else None
        territory_id = set_row["territory_id"] if set_row is not None else None

        would_insert = int(
            (
                conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM (
                      SELECT topic_id, person_id
                      FROM topic_evidence
                      WHERE topic_set_id = ?
                        AND evidence_type LIKE 'declared:%'
                        AND stance_method IN ({stance_ph})
                        AND stance IN ('support', 'oppose', 'mixed')
                      GROUP BY topic_id, person_id
                    ) t
                    """,
                    (int(topic_set_id), *resolved_stance_methods),
                ).fetchone()
                or {"c": 0}
            )["c"]
        )

        if dry_run:
            per_set.append(
                {
                    "topic_set_id": int(topic_set_id),
                    "would_insert": would_insert,
                }
            )
            total_positions += would_insert
            continue

        with conn:
            conn.execute(
                """
                DELETE FROM topic_positions
                WHERE topic_set_id = ?
                  AND computed_method = ?
                  AND computed_version = ?
                  AND as_of_date = ?
                """,
                (int(topic_set_id), str(computed_method), str(computed_version), as_of),
            )

            conn.execute(
                f"""
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
                  agg.topic_id AS topic_id,
                  agg.topic_set_id AS topic_set_id,
                  agg.person_id AS person_id,
                  NULL AS mandate_id,
                  ? AS institution_id,
                  ? AS admin_level_id,
                  ? AS territory_id,
                  ? AS as_of_date,
                  NULL AS window_days,
                  CASE
                    WHEN agg.signal_count <= 0 THEN 'no_signal'
                    WHEN agg.denom <= 0 AND agg.mixed_count > 0 THEN 'mixed'
                    WHEN agg.denom <= 0 THEN 'unclear'
                    WHEN (agg.numer / agg.denom) > 0.2 THEN 'support'
                    WHEN (agg.numer / agg.denom) < -0.2 THEN 'oppose'
                    WHEN agg.support_count > 0 AND agg.oppose_count > 0 THEN 'mixed'
                    ELSE 'unclear'
                  END AS stance,
                  CASE WHEN agg.denom <= 0 THEN 0.0 ELSE (agg.numer / agg.denom) END AS score,
                  CASE WHEN agg.signal_count >= 3 THEN 1.0 ELSE (agg.signal_count * 1.0 / 3.0) END AS confidence,
                  agg.signal_count AS evidence_count,
                  agg.last_evidence_date AS last_evidence_date,
                  ? AS computed_method,
                  ? AS computed_version,
                  ? AS computed_at,
                  ? AS created_at,
                  ? AS updated_at
                FROM (
                  SELECT
                    topic_id,
                    topic_set_id,
                    person_id,
                    COUNT(*) AS signal_count,
                    MAX(evidence_date) AS last_evidence_date,
                    SUM(CASE WHEN stance = 'mixed' THEN 1 ELSE 0 END) AS mixed_count,
                    SUM(CASE WHEN polarity = 1 THEN 1 ELSE 0 END) AS support_count,
                    SUM(CASE WHEN polarity = -1 THEN 1 ELSE 0 END) AS oppose_count,
                    SUM(COALESCE(polarity, 0) * COALESCE(weight, 1) * COALESCE(confidence, 1)) AS numer,
                    SUM(
                      CASE
                        WHEN polarity IS NULL OR polarity = 0 THEN 0
                        ELSE COALESCE(weight, 1) * COALESCE(confidence, 1)
                      END
                    ) AS denom
                  FROM topic_evidence
                  WHERE topic_set_id = ?
                    AND evidence_type LIKE 'declared:%'
                    AND stance_method IN ({stance_ph})
                    AND stance IN ('support', 'oppose', 'mixed')
                  GROUP BY topic_id, topic_set_id, person_id
                ) agg
                """,
                (
                    institution_id,
                    admin_level_id,
                    territory_id,
                    as_of,
                    str(computed_method),
                    str(computed_version),
                    now_iso,
                    now_iso,
                    now_iso,
                    int(topic_set_id),
                    *resolved_stance_methods,
                ),
            )

        inserted = int(
            (
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM topic_positions
                    WHERE topic_set_id = ?
                      AND computed_method = ?
                      AND computed_version = ?
                      AND as_of_date = ?
                    """,
                    (int(topic_set_id), str(computed_method), str(computed_version), as_of),
                ).fetchone()
                or {"c": 0}
            )["c"]
        )
        per_set.append(
            {
                "topic_set_id": int(topic_set_id),
                "inserted": inserted,
            }
        )
        total_positions += inserted

    return {
        "source_id": source_id,
        "as_of_date": as_of,
        "computed_method": computed_method,
        "computed_version": computed_version,
        "stance_methods": list(resolved_stance_methods),
        "dry_run": bool(dry_run),
        "topic_sets": per_set,
        "positions_total": total_positions,
    }
