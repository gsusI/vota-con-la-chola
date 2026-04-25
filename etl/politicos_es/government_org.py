from __future__ import annotations

import json
import sqlite3
from typing import Any

from .util import normalize_key_part, normalize_ws, now_utc_iso, stable_json


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _load_payload(raw_payload: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _unit_id_by_code(conn: sqlite3.Connection, source_id: str, code: str) -> int | None:
    row = conn.execute(
        """
        SELECT org_unit_id
        FROM government_org_units
        WHERE source_id = ? AND org_unit_code = ?
        """,
        (source_id, code),
    ).fetchone()
    return int(row["org_unit_id"]) if row else None


def backfill_government_org_units(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = ("dir3_unidades_age",),
) -> dict[str, Any]:
    if not source_ids:
        raise ValueError("Debe indicar al menos un source_id")

    now_iso = now_utc_iso()
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          source_record_pk,
          source_id,
          source_record_id,
          source_snapshot_date,
          raw_payload
        FROM source_records
        WHERE source_id IN ({placeholders})
        ORDER BY source_id, source_record_id
        """,
        source_ids,
    ).fetchall()

    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_records_seen": len(rows),
        "org_units_upserted": 0,
        "relationships_upserted": 0,
        "records_skipped": 0,
        "relationships_missing_parent": 0,
    }

    records: list[dict[str, Any]] = []
    for row in rows:
        payload = _load_payload(str(row["raw_payload"] or ""))
        if not payload:
            stats["records_skipped"] += 1
            continue
        code = _text(payload.get("org_unit_code")).upper()
        name = _text(payload.get("org_unit_name") or payload.get("name"))
        if not code or not name:
            stats["records_skipped"] += 1
            continue

        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        source_url = _text(payload.get("source_url") or payload.get("feed_url"))
        raw_payload = stable_json(payload)

        conn.execute(
            """
            INSERT INTO government_org_units (
              source_id,
              source_record_pk,
              source_record_id,
              org_unit_code,
              org_unit_version,
              name,
              normalized_name,
              administration_level,
              administration_name,
              ministry_name,
              entity_type_code,
              entity_type_label,
              unit_type_code,
              unit_type_label,
              organic_level,
              status,
              valid_from,
              valid_to,
              source_url,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, org_unit_code) DO UPDATE SET
              source_record_pk=excluded.source_record_pk,
              source_record_id=excluded.source_record_id,
              org_unit_version=excluded.org_unit_version,
              name=excluded.name,
              normalized_name=excluded.normalized_name,
              administration_level=excluded.administration_level,
              administration_name=excluded.administration_name,
              ministry_name=excluded.ministry_name,
              entity_type_code=excluded.entity_type_code,
              entity_type_label=excluded.entity_type_label,
              unit_type_code=excluded.unit_type_code,
              unit_type_label=excluded.unit_type_label,
              organic_level=excluded.organic_level,
              status=excluded.status,
              valid_from=excluded.valid_from,
              valid_to=excluded.valid_to,
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                source_record_pk,
                source_record_id,
                code,
                _text(payload.get("org_unit_version")) or None,
                name,
                _text(payload.get("normalized_name")) or normalize_key_part(name),
                _text(payload.get("administration_level")) or None,
                _text(payload.get("administration_name")) or None,
                _text(payload.get("ministry_name")) or None,
                _text(payload.get("entity_type_code")) or None,
                _text(payload.get("entity_type_label")) or None,
                _text(payload.get("unit_type_code")) or None,
                _text(payload.get("unit_type_label")) or None,
                _as_int(payload.get("organic_level")),
                _text(payload.get("status")) or None,
                _text(payload.get("valid_from")) or None,
                _text(payload.get("valid_to")) or None,
                source_url or None,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["org_units_upserted"] += 1
        records.append(
            {
                "source_id": source_id,
                "source_record_pk": source_record_pk,
                "source_record_id": source_record_id,
                "org_unit_code": code,
                "parent_org_unit_code": _text(payload.get("parent_org_unit_code")).upper(),
                "source_snapshot_date": str(row["source_snapshot_date"] or ""),
                "source_url": source_url,
                "raw_payload": raw_payload,
            }
        )

    for record in records:
        parent_code = record["parent_org_unit_code"]
        subject_code = record["org_unit_code"]
        if not parent_code or parent_code == subject_code:
            continue

        source_id = record["source_id"]
        subject_id = _unit_id_by_code(conn, source_id, subject_code)
        object_id = _unit_id_by_code(conn, source_id, parent_code)
        if object_id is None:
            stats["relationships_missing_parent"] += 1

        conn.execute(
            """
            INSERT INTO government_org_relationships (
              source_id,
              source_record_pk,
              relationship_type,
              subject_org_unit_id,
              object_org_unit_id,
              subject_org_unit_code,
              object_org_unit_code,
              evidence_date,
              source_url,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, 'depends_on', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, subject_org_unit_code, relationship_type, object_org_unit_code)
            DO UPDATE SET
              source_record_pk=excluded.source_record_pk,
              subject_org_unit_id=excluded.subject_org_unit_id,
              object_org_unit_id=excluded.object_org_unit_id,
              evidence_date=excluded.evidence_date,
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                record["source_record_pk"],
                subject_id,
                object_id,
                subject_code,
                parent_code,
                record["source_snapshot_date"] or None,
                record["source_url"] or None,
                record["raw_payload"],
                now_iso,
                now_iso,
            ),
        )
        stats["relationships_upserted"] += 1

    conn.commit()
    return stats
