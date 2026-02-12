from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from etl.politicos_es.db import apply_schema as _apply_schema
from etl.politicos_es.db import open_db as _open_db
from etl.politicos_es.util import now_utc_iso, sha256_bytes

from .config import SOURCE_CONFIG


def open_db(path: Path) -> sqlite3.Connection:
    return _open_db(path)


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    _apply_schema(conn, schema_path)


def seed_sources(conn: sqlite3.Connection) -> None:
    ts = now_utc_iso()
    for source_id, cfg in SOURCE_CONFIG.items():
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
              name=excluded.name,
              scope=excluded.scope,
              default_url=excluded.default_url,
              data_format=excluded.data_format,
              is_active=1,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                cfg["name"],
                cfg["scope"],
                cfg["default_url"],
                cfg.get("format") or "",
                ts,
                ts,
            ),
        )
    conn.commit()


def upsert_source_record_for_event(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    source_record_id: str,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> int:
    # Reuse the generic table but keep the sha stable from the payload itself.
    content_sha256 = sha256_bytes(raw_payload.encode("utf-8"))
    conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, source_records.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        """,
        (source_id, source_record_id, snapshot_date, raw_payload, content_sha256, now_iso, now_iso),
    )
    row = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (source_id, source_record_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver source_record_pk")
    return int(row["source_record_pk"])


def upsert_source_records(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, Any]],
    snapshot_date: str | None,
    now_iso: str,
) -> dict[str, int]:
    """Batch upsert into source_records; return mapping source_record_id -> pk.

    Keeps ingestion fast for list-style sources (e.g. initiatives exports).
    """
    if not rows:
        return {}

    params: list[tuple[Any, ...]] = []
    record_ids: list[str] = []
    for r in rows:
        sid = str(r["source_record_id"])
        payload = str(r["raw_payload"])
        record_ids.append(sid)
        params.append(
            (
                source_id,
                sid,
                snapshot_date,
                payload,
                sha256_bytes(payload.encode("utf-8")),
                now_iso,
                now_iso,
            )
        )

    conn.executemany(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, source_records.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        """,
        params,
    )

    # Resolve PKs in chunks to avoid hitting SQLite variable limits.
    out: dict[str, int] = {}
    chunk = 400
    for i in range(0, len(record_ids), chunk):
        batch = record_ids[i : i + chunk]
        qmarks = ",".join("?" for _ in batch)
        fetched = conn.execute(
            f"""
            SELECT source_record_id, source_record_pk
            FROM source_records
            WHERE source_id = ? AND source_record_id IN ({qmarks})
            """,
            (source_id, *batch),
        ).fetchall()
        for row in fetched:
            out[str(row["source_record_id"])] = int(row["source_record_pk"])
    return out


def upsert_parl_vote_event(
    conn: sqlite3.Connection,
    *,
    vote_event_id: str,
    row: dict[str, Any],
    source_id: str,
    source_url: str | None,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO parl_vote_events (
          vote_event_id,
          legislature, session_number, vote_number, vote_date,
          title, expediente_text, subgroup_title, subgroup_text,
          assentimiento,
          totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote,
          source_id, source_url, source_record_pk, source_snapshot_date,
          raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vote_event_id) DO UPDATE SET
          legislature=excluded.legislature,
          session_number=excluded.session_number,
          vote_number=excluded.vote_number,
          vote_date=excluded.vote_date,
          title=excluded.title,
          expediente_text=excluded.expediente_text,
          subgroup_title=excluded.subgroup_title,
          subgroup_text=excluded.subgroup_text,
          assentimiento=excluded.assentimiento,
          totals_present=excluded.totals_present,
          totals_yes=excluded.totals_yes,
          totals_no=excluded.totals_no,
          totals_abstain=excluded.totals_abstain,
          totals_no_vote=excluded.totals_no_vote,
          source_url=COALESCE(excluded.source_url, parl_vote_events.source_url),
          source_record_pk=COALESCE(excluded.source_record_pk, parl_vote_events.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, parl_vote_events.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            vote_event_id,
            row.get("legislature"),
            row.get("session_number"),
            row.get("vote_number"),
            row.get("vote_date"),
            row.get("title"),
            row.get("expediente_text"),
            row.get("subgroup_title"),
            row.get("subgroup_text"),
            row.get("assentimiento"),
            row.get("totals_present"),
            row.get("totals_yes"),
            row.get("totals_no"),
            row.get("totals_abstain"),
            row.get("totals_no_vote"),
            source_id,
            source_url,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )


def upsert_parl_member_vote(
    conn: sqlite3.Connection,
    *,
    vote_event_id: str,
    seat: str | None,
    member_name: str | None,
    member_name_normalized: str | None,
    person_id: int | None,
    group_code: str | None,
    vote_choice: str,
    source_id: str,
    source_url: str | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    if not seat or seat == "-1":
        seat = f"name:{member_name_normalized or sha256_bytes((member_name or '').encode('utf-8'))[:16]}"
    conn.execute(
        """
        INSERT INTO parl_vote_member_votes (
          vote_event_id,
          seat, member_name, member_name_normalized, person_id,
          group_code, vote_choice,
          source_id, source_url, source_snapshot_date,
          raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vote_event_id, seat) DO UPDATE SET
          member_name=excluded.member_name,
          member_name_normalized=excluded.member_name_normalized,
          person_id=COALESCE(excluded.person_id, parl_vote_member_votes.person_id),
          group_code=excluded.group_code,
          vote_choice=excluded.vote_choice,
          source_url=COALESCE(excluded.source_url, parl_vote_member_votes.source_url),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, parl_vote_member_votes.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            vote_event_id,
            seat,
            member_name,
            member_name_normalized,
            person_id,
            group_code,
            vote_choice,
            source_id,
            source_url,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )


def upsert_parl_initiatives(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return

    conn.executemany(
        """
        INSERT INTO parl_initiatives (
          initiative_id,
          legislature, expediente,
          supertype, grouping, type, title,
          presented_date, qualified_date,
          author_text, procedure_type, result_text, current_status,
          competent_committee,
          deadlines_text, rapporteurs_text, processing_text, related_initiatives_text,
          links_bocg_json, links_ds_json,
          source_id, source_url, source_record_pk, source_snapshot_date,
          raw_payload, created_at, updated_at
        ) VALUES (
          :initiative_id,
          :legislature, :expediente,
          :supertype, :grouping, :type, :title,
          :presented_date, :qualified_date,
          :author_text, :procedure_type, :result_text, :current_status,
          :competent_committee,
          :deadlines_text, :rapporteurs_text, :processing_text, :related_initiatives_text,
          :links_bocg_json, :links_ds_json,
          :source_id, :source_url, :source_record_pk, :source_snapshot_date,
          :raw_payload, :created_at, :updated_at
        )
        ON CONFLICT(initiative_id) DO UPDATE SET
          legislature=excluded.legislature,
          expediente=excluded.expediente,
          supertype=excluded.supertype,
          grouping=excluded.grouping,
          type=excluded.type,
          title=excluded.title,
          presented_date=excluded.presented_date,
          qualified_date=excluded.qualified_date,
          author_text=excluded.author_text,
          procedure_type=excluded.procedure_type,
          result_text=excluded.result_text,
          current_status=excluded.current_status,
          competent_committee=excluded.competent_committee,
          deadlines_text=excluded.deadlines_text,
          rapporteurs_text=excluded.rapporteurs_text,
          processing_text=excluded.processing_text,
          related_initiatives_text=excluded.related_initiatives_text,
          links_bocg_json=excluded.links_bocg_json,
          links_ds_json=excluded.links_ds_json,
          source_url=COALESCE(excluded.source_url, parl_initiatives.source_url),
          source_record_pk=COALESCE(excluded.source_record_pk, parl_initiatives.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, parl_initiatives.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        rows,
    )
