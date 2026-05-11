from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from publicdata_core.util import normalize_ws, now_utc_iso, sha256_bytes


def seed_sources_from_config(
    conn: sqlite3.Connection,
    source_config: Mapping[str, Mapping[str, Any]],
    *,
    now_iso: str | None = None,
) -> None:
    ts = now_iso or now_utc_iso()
    for source_id, cfg in source_config.items():
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


def upsert_source_record(
    conn: sqlite3.Connection,
    source_id: str,
    source_record_id: str,
    snapshot_date: str | None,
    raw_payload: str,
    content_sha256: str,
    now_iso: str,
) -> int:
    row = conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, source_records.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        RETURNING source_record_pk
        """,
        (source_id, source_record_id, snapshot_date, raw_payload, content_sha256, now_iso, now_iso),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver source_record_pk")
    return int(row["source_record_pk"])


def upsert_source_record_for_event(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    source_record_id: str,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> int:
    return upsert_source_record(
        conn,
        source_id,
        source_record_id,
        snapshot_date,
        raw_payload,
        sha256_bytes(raw_payload.encode("utf-8")),
        now_iso,
    )


def upsert_source_records(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, Any]],
    snapshot_date: str | None,
    now_iso: str,
) -> dict[str, int]:
    if not rows:
        return {}

    params: list[tuple[Any, ...]] = []
    record_ids: list[str] = []
    for row in rows:
        record_id = str(row["source_record_id"])
        payload = str(row["raw_payload"])
        record_ids.append(record_id)
        params.append(
            (
                source_id,
                record_id,
                snapshot_date,
                payload,
                sha256_bytes(payload.encode("utf-8")),
                now_iso,
                now_iso,
            )
        )

    _execute_source_record_batch(conn, params)
    return _resolve_source_record_pks(conn, source_id, record_ids)


def upsert_source_records_with_content_sha256(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    rows: list[dict[str, Any]],
    snapshot_date: str | None,
    now_iso: str,
) -> dict[str, int]:
    if not rows:
        return {}

    params: list[tuple[Any, ...]] = []
    record_ids: list[str] = []
    for row in rows:
        record_id = str(row["source_record_id"])
        payload = str(row["raw_payload"])
        content_sha = normalize_ws(str(row.get("content_sha256") or ""))
        if not content_sha:
            content_sha = sha256_bytes(payload.encode("utf-8"))
        record_ids.append(record_id)
        params.append((source_id, record_id, snapshot_date, payload, content_sha, now_iso, now_iso))

    _execute_source_record_batch(conn, params)
    return _resolve_source_record_pks(conn, source_id, record_ids)


def _execute_source_record_batch(conn: sqlite3.Connection, params: list[tuple[Any, ...]]) -> None:
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


def _resolve_source_record_pks(conn: sqlite3.Connection, source_id: str, record_ids: list[str]) -> dict[str, int]:
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
