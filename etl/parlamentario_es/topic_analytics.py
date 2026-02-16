from __future__ import annotations

import json
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any

from etl.politicos_es.util import now_utc_iso, normalize_ws, sha256_bytes

from .config import SOURCE_CONFIG

DEFAULT_TAXONOMY_SEED_PATH = Path("etl/data/seeds/topic_taxonomy_es.json")


def _load_taxonomy_seed(seed_path: Path | None) -> dict[str, Any] | None:
    if seed_path is None:
        return None
    try:
        if not seed_path.exists():
            return None
        raw = seed_path.read_bytes()
    except OSError:
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise ValueError(f"taxonomy seed JSON invalido: {seed_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"taxonomy seed debe ser objeto JSON: {seed_path}")

    data["_seed_path"] = str(seed_path)
    data["_seed_sha256"] = sha256_bytes(raw)
    return data


def _seed_int(value: Any, default: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return int(default)
    return out if out > 0 else int(default)


def _seed_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = normalize_ws(str(item or ""))
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _parse_iso_date(value: str) -> str:
    text = normalize_ws(str(value or ""))
    if not text:
        raise ValueError("fecha vacia")
    return dt.date.fromisoformat(text).isoformat()


def _resolve_territory_id(conn: sqlite3.Connection, *, code: str) -> int | None:
    row = conn.execute(
        """
        SELECT territory_id
        FROM territories
        WHERE code = ?
        """,
        (code,),
    ).fetchone()
    if not row:
        return None
    return int(row["territory_id"])


def _resolve_or_create_admin_level_id(conn: sqlite3.Connection, *, code: str, now_iso: str) -> int | None:
    code_norm = normalize_ws(str(code or ""))
    if not code_norm:
        return None
    row = conn.execute(
        """
        SELECT admin_level_id
        FROM admin_levels
        WHERE code = ?
        """,
        (code_norm,),
    ).fetchone()
    if row:
        return int(row["admin_level_id"])

    label = code_norm.capitalize()
    conn.execute(
        """
        INSERT INTO admin_levels (code, label, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          label=excluded.label,
          updated_at=excluded.updated_at
        """,
        (code_norm, label, now_iso, now_iso),
    )
    row = conn.execute(
        "SELECT admin_level_id FROM admin_levels WHERE code = ?",
        (code_norm,),
    ).fetchone()
    return int(row["admin_level_id"]) if row else None


def _resolve_or_create_territory_id(conn: sqlite3.Connection, *, code: str, now_iso: str) -> int | None:
    code_norm = normalize_ws(str(code or ""))
    if not code_norm:
        return None
    existing = _resolve_territory_id(conn, code=code_norm)
    if existing is not None:
        return existing

    conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=COALESCE(excluded.name, territories.name),
          updated_at=excluded.updated_at
        """,
        (code_norm, code_norm, now_iso, now_iso),
    )
    return _resolve_territory_id(conn, code=code_norm)


def _resolve_institution(conn: sqlite3.Connection, *, name: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT institution_id, admin_level_id, territory_id, territory_code, level
        FROM institutions
        WHERE name = ?
        ORDER BY
          CASE WHEN territory_code IS NULL OR TRIM(territory_code) = '' THEN 0 ELSE 1 END,
          institution_id
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"No se encontro institution para name={name!r}")
    return {
        "institution_id": int(row["institution_id"]),
        "admin_level_id": int(row["admin_level_id"]) if row["admin_level_id"] is not None else None,
        "territory_id": int(row["territory_id"]) if row["territory_id"] is not None else None,
        "territory_code": str(row["territory_code"] or ""),
        "level": str(row["level"] or ""),
    }


def _resolve_or_create_institution(
    conn: sqlite3.Connection,
    *,
    name: str,
    level: str,
    admin_level_id: int | None,
    territory_id: int | None,
    now_iso: str,
) -> dict[str, Any]:
    try:
        return _resolve_institution(conn, name=name)
    except RuntimeError:
        pass

    conn.execute(
        """
        INSERT INTO institutions (name, level, admin_level_id, territory_code, territory_id, created_at, updated_at)
        VALUES (?, ?, ?, '', ?, ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET
          admin_level_id=COALESCE(excluded.admin_level_id, institutions.admin_level_id),
          territory_id=COALESCE(excluded.territory_id, institutions.territory_id),
          updated_at=excluded.updated_at
        """,
        (name, level, admin_level_id, territory_id, now_iso, now_iso),
    )
    return _resolve_institution(conn, name=name)


def _resolve_latest_legislature(conn: sqlite3.Connection, *, vote_source_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT MAX(CAST(legislature AS INTEGER)) AS leg
        FROM parl_vote_events
        WHERE source_id = ? AND legislature IS NOT NULL AND TRIM(legislature) <> ''
        """,
        (vote_source_id,),
    ).fetchone()
    if not row or row["leg"] is None:
        return None
    return str(int(row["leg"]))


def _upsert_topic_set(
    conn: sqlite3.Connection,
    *,
    name: str,
    description: str,
    institution_id: int | None,
    admin_level_id: int | None,
    territory_id: int | None,
    legislature: str | None,
    valid_from: str | None,
    valid_to: str | None,
    is_active: int,
    now_iso: str,
) -> int:
    conn.execute(
        """
        INSERT INTO topic_sets (
          name, description,
          institution_id, admin_level_id, territory_id,
          legislature, valid_from, valid_to,
          is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, institution_id, admin_level_id, territory_id, legislature) DO UPDATE SET
          description=excluded.description,
          valid_from=excluded.valid_from,
          valid_to=excluded.valid_to,
          is_active=excluded.is_active,
          updated_at=excluded.updated_at
        """,
        (
            name,
            description,
            institution_id,
            admin_level_id,
            territory_id,
            legislature,
            valid_from,
            valid_to,
            int(is_active),
            now_iso,
            now_iso,
        ),
    )
    row = conn.execute(
        """
        SELECT topic_set_id
        FROM topic_sets
        WHERE name = ?
          AND institution_id IS ?
          AND admin_level_id IS ?
          AND territory_id IS ?
          AND legislature IS ?
        ORDER BY topic_set_id DESC
        LIMIT 1
        """,
        (name, institution_id, admin_level_id, territory_id, legislature),
    ).fetchone()
    if not row:
        raise RuntimeError("No se pudo resolver topic_set_id tras upsert")
    return int(row["topic_set_id"])


def _drop_temp(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(f'DROP TABLE IF EXISTS "{name}"')


def _compute_topic_set_window(
    conn: sqlite3.Connection,
    *,
    vote_source_id: str,
    legislature: str,
) -> tuple[str | None, str | None]:
    row = conn.execute(
        """
        SELECT MIN(vote_date) AS dmin, MAX(vote_date) AS dmax
        FROM parl_vote_events
        WHERE source_id = ? AND legislature = ?
        """,
        (vote_source_id, legislature),
    ).fetchone()
    if not row:
        return None, None
    return (str(row["dmin"]) if row["dmin"] else None, str(row["dmax"]) if row["dmax"] else None)


def _build_selected_topics_temp(
    conn: sqlite3.Connection,
    *,
    vote_source_id: str,
    legislature: str,
    max_topics: int,
    exclude_canonical_keys: list[str] | None = None,
    pin_canonical_keys: list[str] | None = None,
) -> None:
    _drop_temp(conn, "tmp_best_link")
    _drop_temp(conn, "tmp_event_topic")
    _drop_temp(conn, "tmp_topic_scores")
    _drop_temp(conn, "tmp_selected_topics")
    _drop_temp(conn, "tmp_selected_topics_base")
    _drop_temp(conn, "tmp_selected_topics_union")
    _drop_temp(conn, "tmp_exclude_keys")
    _drop_temp(conn, "tmp_pin_keys")

    conn.execute("CREATE TEMP TABLE tmp_exclude_keys (canonical_key TEXT PRIMARY KEY)")
    conn.execute("CREATE TEMP TABLE tmp_pin_keys (canonical_key TEXT PRIMARY KEY)")
    if exclude_canonical_keys:
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_exclude_keys (canonical_key) VALUES (?)",
            [(str(k),) for k in exclude_canonical_keys if normalize_ws(str(k or ""))],
        )
    if pin_canonical_keys:
        conn.executemany(
            "INSERT OR IGNORE INTO tmp_pin_keys (canonical_key) VALUES (?)",
            [(str(k),) for k in pin_canonical_keys if normalize_ws(str(k or ""))],
        )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_best_link AS
        SELECT vote_event_id, initiative_id, link_method, confidence
        FROM (
          SELECT
            l.vote_event_id,
            l.initiative_id,
            l.link_method,
            l.confidence,
            ROW_NUMBER() OVER (
              PARTITION BY l.vote_event_id
              ORDER BY COALESCE(l.confidence, 0.0) DESC, l.link_method ASC, l.initiative_id ASC
            ) AS rn
          FROM parl_vote_event_initiatives l
          JOIN parl_vote_events e ON e.vote_event_id = l.vote_event_id
          WHERE e.source_id = ? AND e.legislature = ?
        ) ranked
        WHERE rn = 1
        """,
        (vote_source_id, legislature),
    )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_event_topic AS
        SELECT
          e.vote_event_id,
          e.vote_date,
          e.title,
          e.totals_present,
          e.totals_yes,
          e.totals_no,
          e.totals_abstain,
          e.totals_no_vote,
          bl.initiative_id,
          bl.link_method,
          COALESCE(bl.initiative_id, 'vote_event:' || e.vote_event_id) AS canonical_key
        FROM parl_vote_events e
        LEFT JOIN tmp_best_link bl ON bl.vote_event_id = e.vote_event_id
        WHERE e.source_id = ? AND e.legislature = ?
        """,
        (vote_source_id, legislature),
    )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_topic_scores AS
        WITH event_scores AS (
          SELECT
            canonical_key,
            initiative_id,
            link_method,
            vote_event_id,
            vote_date,
            title,
            COALESCE(
              totals_present,
              COALESCE(totals_yes, 0) + COALESCE(totals_no, 0) + COALESCE(totals_abstain, 0) + COALESCE(totals_no_vote, 0),
              0
            ) AS present,
            COALESCE(totals_yes, 0) AS yes,
            COALESCE(totals_no, 0) AS no
          FROM tmp_event_topic
        )
        SELECT
          canonical_key,
          MAX(initiative_id) AS initiative_id,
          MAX(link_method) AS link_method,
          COUNT(DISTINCT vote_event_id) AS vote_event_count,
          SUM(
            present * (
              CASE
                WHEN (yes + no) > 0 THEN 1.0 - (ABS(yes - no) * 1.0 / (yes + no))
                ELSE 0.0
              END
            )
          ) AS stakes_score,
          MAX(title) AS sample_title,
          MAX(vote_date) AS last_vote_date
        FROM event_scores
        GROUP BY canonical_key
        """,
    )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_selected_topics_base AS
        SELECT
          canonical_key,
          initiative_id,
          link_method,
          vote_event_count,
          stakes_score,
          sample_title,
          last_vote_date,
          NULL AS stakes_rank
        FROM tmp_topic_scores
        WHERE canonical_key NOT IN (SELECT canonical_key FROM tmp_exclude_keys)
        ORDER BY stakes_score DESC, vote_event_count DESC, canonical_key ASC
        LIMIT ?
        """,
        (int(max(1, max_topics)),),
    )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_selected_topics_union AS
        SELECT canonical_key, initiative_id, link_method, vote_event_count, stakes_score, sample_title, last_vote_date
        FROM tmp_selected_topics_base
        UNION
        SELECT canonical_key, initiative_id, link_method, vote_event_count, stakes_score, sample_title, last_vote_date
        FROM tmp_topic_scores
        WHERE canonical_key IN (SELECT canonical_key FROM tmp_pin_keys)
        """
    )

    conn.execute(
        """
        CREATE TEMP TABLE tmp_selected_topics AS
        SELECT
          canonical_key,
          initiative_id,
          link_method,
          vote_event_count,
          stakes_score,
          sample_title,
          last_vote_date,
          ROW_NUMBER() OVER (ORDER BY stakes_score DESC, vote_event_count DESC, canonical_key ASC) AS stakes_rank
        FROM tmp_selected_topics_union
        ORDER BY stakes_score DESC, vote_event_count DESC, canonical_key ASC
        """
    )


def backfill_topic_set_from_votes(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    vote_source_id: str,
    legislature: str,
    institution_id: int | None,
    admin_level_id: int | None,
    territory_id: int | None,
    as_of_date: str,
    max_topics: int = 200,
    high_stakes_top: int = 60,
    exclude_canonical_keys: list[str] | None = None,
    pin_canonical_keys: list[str] | None = None,
    dry_run: bool = False,
    computed_method: str = "votes",
    computed_version: str = "v1",
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    as_of_date = _parse_iso_date(as_of_date)

    if max_topics <= 0:
        raise ValueError("max_topics debe ser > 0")
    if high_stakes_top < 0:
        raise ValueError("high_stakes_top debe ser >= 0")

    _build_selected_topics_temp(
        conn,
        vote_source_id=vote_source_id,
        legislature=legislature,
        max_topics=max_topics,
        exclude_canonical_keys=exclude_canonical_keys,
        pin_canonical_keys=pin_canonical_keys,
    )

    selected_topics = int(
        (conn.execute("SELECT COUNT(*) AS c FROM tmp_selected_topics").fetchone() or {"c": 0})["c"]
    )

    # Estimate how many evidence rows we would produce (keeps dry-run useful for big DBs).
    evidence_would = int(
        (
            conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM parl_vote_member_votes mv
                JOIN tmp_event_topic et ON et.vote_event_id = mv.vote_event_id
                JOIN tmp_selected_topics st ON st.canonical_key = et.canonical_key
                WHERE mv.person_id IS NOT NULL
                  AND (
                    mv.vote_choice IN ('SÍ','Sí','SI','Si','NO','No','ABSTENCIÓN','Abstención','ABSTENCION','Abstencion')
                  )
                """
            ).fetchone()
            or {"c": 0}
        )["c"]
    )

    if dry_run:
        return {
            "topic_set_id": int(topic_set_id),
            "vote_source_id": vote_source_id,
            "legislature": legislature,
            "as_of_date": as_of_date,
            "max_topics": int(max_topics),
            "high_stakes_top": int(high_stakes_top),
            "selected_topics": selected_topics,
            "evidence_would_insert": evidence_would,
            "dry_run": True,
        }

    with conn:
        # Upsert topics for initiatives in selection.
        conn.execute(
            """
            INSERT INTO topics (
              canonical_key, label, description, parent_topic_id, created_at, updated_at
            )
            SELECT
              i.initiative_id AS canonical_key,
              COALESCE(NULLIF(TRIM(i.title), ''), NULLIF(TRIM(i.expediente), ''), i.initiative_id) AS label,
              NULL AS description,
              NULL AS parent_topic_id,
              ? AS created_at,
              ? AS updated_at
            FROM parl_initiatives i
            JOIN tmp_selected_topics st ON st.canonical_key = i.initiative_id
            ON CONFLICT(canonical_key) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            """,
            (now_iso, now_iso),
        )

        # Upsert topics for vote_event fallbacks.
        conn.execute(
            """
            INSERT INTO topics (
              canonical_key, label, description, parent_topic_id, created_at, updated_at
            )
            SELECT
              st.canonical_key AS canonical_key,
              COALESCE(NULLIF(TRIM(st.sample_title), ''), st.canonical_key) AS label,
              NULL AS description,
              NULL AS parent_topic_id,
              ? AS created_at,
              ? AS updated_at
            FROM tmp_selected_topics st
            WHERE st.initiative_id IS NULL
            ON CONFLICT(canonical_key) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            """,
            (now_iso, now_iso),
        )

        conn.execute("DELETE FROM topic_set_topics WHERE topic_set_id = ?", (int(topic_set_id),))
        conn.execute(
            """
            INSERT INTO topic_set_topics (
              topic_set_id, topic_id,
              stakes_score, stakes_rank, is_high_stakes, notes,
              created_at, updated_at
            )
            SELECT
              ? AS topic_set_id,
              t.topic_id,
              st.stakes_score,
              st.stakes_rank,
              CASE WHEN st.stakes_rank <= ? THEN 1 ELSE 0 END AS is_high_stakes,
              CASE
                WHEN st.initiative_id IS NOT NULL THEN 'initiative:' || COALESCE(st.link_method, 'linked')
                ELSE 'vote_event'
              END AS notes,
              ? AS created_at,
              ? AS updated_at
            FROM tmp_selected_topics st
            JOIN topics t ON t.canonical_key = st.canonical_key
            """,
            (int(topic_set_id), int(high_stakes_top), now_iso, now_iso),
        )

        conn.execute(
            "DELETE FROM topic_evidence WHERE topic_set_id = ? AND evidence_type = 'revealed:vote'",
            (int(topic_set_id),),
        )
        conn.execute(
            """
            INSERT INTO topic_evidence (
              topic_id, topic_set_id,
              person_id, mandate_id,
              institution_id, admin_level_id, territory_id,
              evidence_type, evidence_date, title, excerpt,
              stance, polarity, weight, confidence,
              topic_method, stance_method,
              vote_event_id, initiative_id,
              source_id, source_url, source_record_pk, source_snapshot_date,
              raw_payload, created_at, updated_at
            )
            SELECT
              t.topic_id AS topic_id,
              ? AS topic_set_id,
              mv.person_id AS person_id,
              NULL AS mandate_id,
              ? AS institution_id,
              ? AS admin_level_id,
              ? AS territory_id,
              'revealed:vote' AS evidence_type,
              e.vote_date AS evidence_date,
              e.title AS title,
              mv.vote_choice AS excerpt,
              CASE
                WHEN mv.vote_choice IN ('SÍ','Sí','SI','Si') THEN 'support'
                WHEN mv.vote_choice IN ('NO','No') THEN 'oppose'
                WHEN mv.vote_choice IN ('ABSTENCIÓN','Abstención','ABSTENCION','Abstencion') THEN 'unclear'
                ELSE 'no_signal'
              END AS stance,
              CASE
                WHEN mv.vote_choice IN ('SÍ','Sí','SI','Si') THEN 1
                WHEN mv.vote_choice IN ('NO','No') THEN -1
                WHEN mv.vote_choice IN ('ABSTENCIÓN','Abstención','ABSTENCION','Abstencion') THEN 0
                ELSE NULL
              END AS polarity,
              1.0 AS weight,
              1.0 AS confidence,
              CASE
                WHEN et.initiative_id IS NOT NULL THEN 'initiative:' || COALESCE(et.link_method, 'linked')
                ELSE 'vote_event_fallback'
              END AS topic_method,
              'rollcall' AS stance_method,
              e.vote_event_id AS vote_event_id,
              et.initiative_id AS initiative_id,
              mv.source_id AS source_id,
              mv.source_url AS source_url,
              e.source_record_pk AS source_record_pk,
              mv.source_snapshot_date AS source_snapshot_date,
              json_object(
                'member_vote_id', mv.member_vote_id,
                'vote_choice', mv.vote_choice,
                'seat', mv.seat,
                'group_code', mv.group_code,
                'vote_event_id', mv.vote_event_id,
                'initiative_id', et.initiative_id,
                'person_id', mv.person_id
              ) AS raw_payload,
              ? AS created_at,
              ? AS updated_at
            FROM parl_vote_member_votes mv
            JOIN tmp_event_topic et ON et.vote_event_id = mv.vote_event_id
            JOIN tmp_selected_topics st ON st.canonical_key = et.canonical_key
            JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
            JOIN topics t ON t.canonical_key = et.canonical_key
            WHERE mv.person_id IS NOT NULL
              AND (
                mv.vote_choice IN ('SÍ','Sí','SI','Si','NO','No','ABSTENCIÓN','Abstención','ABSTENCION','Abstencion')
              )
              AND (
                CASE
                  WHEN mv.vote_choice IN ('SÍ','Sí','SI','Si') THEN 1
                  WHEN mv.vote_choice IN ('NO','No') THEN -1
                  WHEN mv.vote_choice IN ('ABSTENCIÓN','Abstención','ABSTENCION','Abstencion') THEN 0
                  ELSE NULL
                END
              ) IS NOT NULL
            """,
            (int(topic_set_id), institution_id, admin_level_id, territory_id, now_iso, now_iso),
        )

        conn.execute(
            """
            DELETE FROM topic_positions
            WHERE topic_set_id = ?
              AND computed_method = ?
              AND computed_version = ?
              AND as_of_date = ?
            """,
            (int(topic_set_id), str(computed_method), str(computed_version), as_of_date),
        )

        conn.execute(
            """
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
                WHEN agg.denom <= 0 THEN 'unclear'
                WHEN (agg.numer / agg.denom) > 0.2 THEN 'support'
                WHEN (agg.numer / agg.denom) < -0.2 THEN 'oppose'
                ELSE 'unclear'
              END AS stance,
              CASE WHEN agg.denom <= 0 THEN 0.0 ELSE (agg.numer / agg.denom) END AS score,
              CASE WHEN agg.evidence_count >= 5 THEN 1.0 ELSE (agg.evidence_count * 1.0 / 5.0) END AS confidence,
              agg.evidence_count AS evidence_count,
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
                COUNT(*) AS evidence_count,
                MAX(evidence_date) AS last_evidence_date,
                SUM(COALESCE(polarity, 0) * COALESCE(weight, 1) * COALESCE(confidence, 1)) AS numer,
                SUM(
                  CASE
                    WHEN polarity IS NULL OR polarity = 0 THEN 0
                    ELSE COALESCE(weight, 1) * COALESCE(confidence, 1)
                  END
                ) AS denom
              FROM topic_evidence
              WHERE topic_set_id = ?
                AND evidence_type = 'revealed:vote'
              GROUP BY topic_id, topic_set_id, person_id
            ) agg
            """,
            (
                institution_id,
                admin_level_id,
                territory_id,
                as_of_date,
                str(computed_method),
                str(computed_version),
                now_iso,
                now_iso,
                now_iso,
                int(topic_set_id),
            ),
        )

    topics_in_set = int(
        (conn.execute("SELECT COUNT(*) AS c FROM topic_set_topics WHERE topic_set_id = ?", (int(topic_set_id),)).fetchone() or {"c": 0})[
            "c"
        ]
    )
    evidence_inserted = int(
        (
            conn.execute(
                "SELECT COUNT(*) AS c FROM topic_evidence WHERE topic_set_id = ? AND evidence_type = 'revealed:vote'",
                (int(topic_set_id),),
            ).fetchone()
            or {"c": 0}
        )["c"]
    )
    positions_inserted = int(
        (
            conn.execute(
                "SELECT COUNT(*) AS c FROM topic_positions WHERE topic_set_id = ? AND computed_method = ? AND computed_version = ? AND as_of_date = ?",
                (int(topic_set_id), str(computed_method), str(computed_version), as_of_date),
            ).fetchone()
            or {"c": 0}
        )["c"]
    )

    return {
        "topic_set_id": int(topic_set_id),
        "vote_source_id": vote_source_id,
        "legislature": legislature,
        "as_of_date": as_of_date,
        "max_topics": int(max_topics),
        "high_stakes_top": int(high_stakes_top),
        "selected_topics": selected_topics,
        "topics_in_set": topics_in_set,
        "evidence_inserted": evidence_inserted,
        "positions_inserted": positions_inserted,
        "dry_run": False,
    }


def backfill_topic_analytics_from_votes(
    conn: sqlite3.Connection,
    *,
    vote_source_ids: tuple[str, ...] = ("congreso_votaciones", "senado_votaciones"),
    legislature: str = "latest",
    as_of_date: str | None = None,
    max_topics: int = 200,
    high_stakes_top: int = 60,
    taxonomy_seed_path: Path | None = DEFAULT_TAXONOMY_SEED_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    as_of = _parse_iso_date(as_of_date) if as_of_date else None
    seed = _load_taxonomy_seed(taxonomy_seed_path)
    seed_id = normalize_ws(str(seed.get("taxonomy_id") or "")) if seed else ""
    seed_version = normalize_ws(str(seed.get("taxonomy_version") or "")) if seed else ""
    seed_sha = normalize_ws(str(seed.get("_seed_sha256") or "")) if seed else ""

    es_territory_id = _resolve_or_create_territory_id(conn, code="ES", now_iso=now_iso)
    results: list[dict[str, Any]] = []

    for vote_source_id in vote_source_ids:
        seed_vote_cfg = {}
        if seed:
            vote_sets = seed.get("vote_sets") or {}
            if isinstance(vote_sets, dict):
                seed_vote_cfg = vote_sets.get(vote_source_id) or {}
        if not isinstance(seed_vote_cfg, dict):
            seed_vote_cfg = {}

        eff_max_topics = _seed_int(seed_vote_cfg.get("max_topics"), int(max_topics))
        eff_high_stakes_top = _seed_int(seed_vote_cfg.get("high_stakes_top"), int(high_stakes_top))
        pin_keys = _seed_str_list(seed_vote_cfg.get("pin_canonical_keys"))
        exclude_keys = _seed_str_list(seed_vote_cfg.get("exclude_canonical_keys"))

        cfg = SOURCE_CONFIG.get(vote_source_id)
        if not cfg:
            raise ValueError(f"vote_source_id desconocido: {vote_source_id}")
        institution_name = str(cfg.get("institution_name") or "")
        if not institution_name:
            raise RuntimeError(f"SOURCE_CONFIG[{vote_source_id!r}] sin institution_name")

        level_code = normalize_ws(str(cfg.get("level") or "")) or "nacional"
        admin_level_id = _resolve_or_create_admin_level_id(conn, code=level_code, now_iso=now_iso)
        inst = _resolve_or_create_institution(
            conn,
            name=institution_name,
            level=level_code,
            admin_level_id=admin_level_id,
            territory_id=es_territory_id,
            now_iso=now_iso,
        )
        institution_id = int(inst["institution_id"])

        if legislature.strip().lower() == "latest":
            leg = _resolve_latest_legislature(conn, vote_source_id=vote_source_id)
            if not leg:
                results.append(
                    {
                        "vote_source_id": vote_source_id,
                        "skipped": True,
                        "reason": "no_legislature_found",
                    }
                )
                continue
            legislature_value = leg
            is_active = 1
        else:
            legislature_value = normalize_ws(legislature)
            if not legislature_value:
                raise ValueError("legislature vacia")
            is_active = 0
            latest = _resolve_latest_legislature(conn, vote_source_id=vote_source_id)
            if latest and latest == legislature_value:
                is_active = 1

        valid_from, valid_to = _compute_topic_set_window(conn, vote_source_id=vote_source_id, legislature=legislature_value)

        set_name = f"{institution_name} / leg {legislature_value} / votaciones (auto)"
        seed_tag = ""
        if seed_id or seed_version or seed_sha:
            sha_short = seed_sha[:12] if seed_sha else ""
            seed_tag = f" seed={seed_id or 'seed'}:{seed_version or 'v?'}:{sha_short or 'sha?'}"
        set_desc = (
            "Auto(votes:v1):"
            f"{seed_tag}"
            f" max_topics={eff_max_topics}"
            f" high_stakes_top={eff_high_stakes_top}"
            f" pin={len(pin_keys)}"
            f" exclude={len(exclude_keys)}"
            " derived_from=parl_vote_member_votes+parl_vote_event_initiatives"
        )

        topic_set_id = _upsert_topic_set(
            conn,
            name=set_name,
            description=set_desc,
            institution_id=institution_id,
            admin_level_id=admin_level_id,
            territory_id=es_territory_id,
            legislature=legislature_value,
            valid_from=valid_from,
            valid_to=valid_to,
            is_active=is_active,
            now_iso=now_iso,
        )

        # Default as_of_date to the end of the window if not explicitly passed.
        effective_as_of = as_of or valid_to
        if not effective_as_of:
            # Fallback: use today's UTC date to keep schema happy.
            effective_as_of = dt.datetime.now(dt.timezone.utc).date().isoformat()

        result = backfill_topic_set_from_votes(
            conn,
            topic_set_id=topic_set_id,
            vote_source_id=vote_source_id,
            legislature=legislature_value,
            institution_id=institution_id,
            admin_level_id=admin_level_id,
            territory_id=es_territory_id,
            as_of_date=effective_as_of,
            max_topics=eff_max_topics,
            high_stakes_top=eff_high_stakes_top,
            pin_canonical_keys=pin_keys,
            exclude_canonical_keys=exclude_keys,
            dry_run=dry_run,
        )
        results.append(result)

    return {
        "dry_run": bool(dry_run),
        "generated_at": now_iso,
        "territory_id_es": es_territory_id,
        "vote_source_ids": list(vote_source_ids),
        "legislature": legislature,
        "as_of_date": as_of_date,
        "max_topics": int(max_topics),
        "high_stakes_top": int(high_stakes_top),
        "results": results,
    }
