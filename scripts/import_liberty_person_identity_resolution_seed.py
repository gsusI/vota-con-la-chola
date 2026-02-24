#!/usr/bin/env python3
"""Import liberty_person_identity_resolution_seed_v1 into person_name_aliases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_liberty_person_identity_resolution_seed import SOURCE_KIND_MANUAL, validate_seed


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return normalize_ws(str(v))


def _canonical_alias(actor_person_name: Any) -> str:
    return _norm(actor_person_name).lower()


def _to_float_or_none(v: Any) -> float | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return float(token)
    except Exception:
        return None


def _to_int_or_none(v: Any) -> int | None:
    token = _norm(v)
    if not token:
        return None
    try:
        got = int(float(token))
    except Exception:
        return None
    return got if got >= 1 else None


def _source_kind(v: Any) -> str:
    token = _norm(v).lower()
    return token or SOURCE_KIND_MANUAL


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _source_record_pk_exists(conn: sqlite3.Connection, source_record_pk: int, source_id: str = "") -> bool:
    if int(source_record_pk) < 1:
        return False
    sid = _norm(source_id)
    if sid:
        row = conn.execute(
            "SELECT 1 FROM source_records WHERE source_record_pk = ? AND source_id = ?",
            (int(source_record_pk), sid),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM source_records WHERE source_record_pk = ?",
            (int(source_record_pk),),
        ).fetchone()
    return row is not None


def _find_source_record_pk(conn: sqlite3.Connection, source_id: str, source_record_id: str) -> int | None:
    sid = _norm(source_id)
    srid = _norm(source_record_id)
    if not sid or not srid:
        return None
    row = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        LIMIT 1
        """,
        (sid, srid),
    ).fetchone()
    return int(row["source_record_pk"]) if row is not None else None


def _find_person_by_id(conn: sqlite3.Connection, person_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT person_id, full_name, canonical_key
        FROM persons
        WHERE person_id = ?
        """,
        (int(person_id),),
    ).fetchone()


def _find_person_by_canonical_key(conn: sqlite3.Connection, canonical_key: str) -> sqlite3.Row | None:
    key = _norm(canonical_key)
    if not key:
        return None
    return conn.execute(
        """
        SELECT person_id, full_name, canonical_key
        FROM persons
        WHERE canonical_key = ?
        """,
        (key,),
    ).fetchone()


def _find_person_by_full_name(conn: sqlite3.Connection, full_name: str) -> sqlite3.Row | None:
    name = _norm(full_name)
    if not name:
        return None
    return conn.execute(
        """
        SELECT person_id, full_name, canonical_key
        FROM persons
        WHERE LOWER(TRIM(full_name)) = LOWER(TRIM(?))
        ORDER BY person_id ASC
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def _manual_person_canonical_key(full_name: str) -> str:
    token = _norm(full_name).lower()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"manual::liberty_identity::{digest[:24]}"


def _ensure_person(
    conn: sqlite3.Connection,
    *,
    person_id_hint: int | None,
    person_canonical_key_hint: str,
    person_full_name: str,
    ts: str,
    counts: dict[str, int],
) -> tuple[int, str]:
    row: sqlite3.Row | None = None
    if person_id_hint is not None:
        row = _find_person_by_id(conn, person_id_hint)
    if row is None and person_canonical_key_hint:
        row = _find_person_by_canonical_key(conn, person_canonical_key_hint)
    if row is None and person_full_name:
        row = _find_person_by_full_name(conn, person_full_name)
    if row is not None:
        counts["persons_reused"] += 1
        return int(row["person_id"]), _norm(row["full_name"])

    full_name = _norm(person_full_name)
    if not full_name:
        raise ValueError("person_full_name is required to create person")
    canonical_key = _norm(person_canonical_key_hint) or _manual_person_canonical_key(full_name)
    existing = _find_person_by_canonical_key(conn, canonical_key)
    if existing is not None:
        counts["persons_reused"] += 1
        return int(existing["person_id"]), _norm(existing["full_name"])

    conn.execute(
        """
        INSERT INTO persons (
          full_name, territory_code, canonical_key, created_at, updated_at
        ) VALUES (?, '', ?, ?, ?)
        """,
        (full_name, canonical_key, ts, ts),
    )
    person_row = _find_person_by_canonical_key(conn, canonical_key)
    if person_row is None:
        raise RuntimeError(f"failed to create person for canonical_key={canonical_key!r}")
    counts["persons_created"] += 1
    return int(person_row["person_id"]), _norm(person_row["full_name"])


def import_seed(
    conn: sqlite3.Connection,
    *,
    seed_doc: dict[str, Any],
    source_id: str,
    snapshot_date: str,
) -> dict[str, Any]:
    ts = now_utc_iso()
    sid = _norm(source_id)
    if sid and not _source_exists(conn, sid):
        sid = ""

    mappings = seed_doc.get("mappings") if isinstance(seed_doc.get("mappings"), list) else []
    counts: dict[str, int] = {
        "mappings_total": len(mappings),
        "persons_created": 0,
        "persons_reused": 0,
        "aliases_inserted": 0,
        "aliases_updated": 0,
        "aliases_retargeted": 0,
        "aliases_retarget_downgrade_prevented": 0,
        "aliases_source_kind_downgrade_prevented": 0,
        "manual_mappings_total": 0,
        "official_mappings_total": 0,
        "official_mappings_with_source_record_total": 0,
        "official_mappings_missing_source_record_total": 0,
        "source_record_pk_resolved_total": 0,
        "source_record_pk_unresolved_total": 0,
    }

    for row in mappings:
        if not isinstance(row, dict):
            continue
        actor_person_name = _norm(row.get("actor_person_name"))
        canonical_alias = _canonical_alias(actor_person_name)
        if not canonical_alias:
            continue
        person_id_hint = _to_int_or_none(row.get("person_id"))
        person_canonical_key_hint = _norm(row.get("person_canonical_key"))
        person_full_name = _norm(row.get("person_full_name"))
        person_id, resolved_full_name = _ensure_person(
            conn,
            person_id_hint=person_id_hint,
            person_canonical_key_hint=person_canonical_key_hint,
            person_full_name=person_full_name,
            ts=ts,
            counts=counts,
        )

        source_kind = _source_kind(row.get("source_kind"))
        if source_kind == SOURCE_KIND_MANUAL:
            counts["manual_mappings_total"] += 1
        else:
            counts["official_mappings_total"] += 1

        row_source_id = _norm(row.get("source_id"))
        if row_source_id and not _source_exists(conn, row_source_id):
            row_source_id = ""
        if source_kind == SOURCE_KIND_MANUAL and not row_source_id:
            source_id_effective = None
        elif row_source_id:
            source_id_effective = row_source_id
        elif sid:
            source_id_effective = sid
        else:
            source_id_effective = None

        row_source_record_pk = _to_int_or_none(row.get("source_record_pk"))
        row_source_record_id = _norm(row.get("source_record_id"))
        source_record_pk_effective: int | None = None
        if row_source_record_pk is not None:
            if _source_record_pk_exists(conn, row_source_record_pk, _norm(source_id_effective)):
                source_record_pk_effective = int(row_source_record_pk)
                counts["source_record_pk_resolved_total"] += 1
            else:
                counts["source_record_pk_unresolved_total"] += 1
        elif row_source_record_id and source_id_effective:
            source_record_pk_effective = _find_source_record_pk(
                conn,
                _norm(source_id_effective),
                row_source_record_id,
            )
            if source_record_pk_effective is not None:
                counts["source_record_pk_resolved_total"] += 1
            else:
                counts["source_record_pk_unresolved_total"] += 1
        elif row_source_record_id:
            counts["source_record_pk_unresolved_total"] += 1

        if source_kind != SOURCE_KIND_MANUAL:
            if source_record_pk_effective is None:
                counts["official_mappings_missing_source_record_total"] += 1
            else:
                counts["official_mappings_with_source_record_total"] += 1

        previous = conn.execute(
            """
            SELECT person_name_alias_id, person_id, source_kind
            FROM person_name_aliases
            WHERE canonical_alias = ?
            """,
            (canonical_alias,),
        ).fetchone()
        if previous is None:
            counts["aliases_inserted"] += 1
        else:
            counts["aliases_updated"] += 1
            previous_person_id = int(previous["person_id"])
            prev_source_kind = _source_kind(previous["source_kind"])
            is_manual_downgrade_attempt = prev_source_kind != SOURCE_KIND_MANUAL and source_kind == SOURCE_KIND_MANUAL
            if is_manual_downgrade_attempt:
                counts["aliases_source_kind_downgrade_prevented"] += 1
                if previous_person_id != int(person_id):
                    counts["aliases_retarget_downgrade_prevented"] += 1
            elif previous_person_id != int(person_id):
                counts["aliases_retargeted"] += 1

        payload_note = _norm(row.get("note"))
        confidence = _to_float_or_none(row.get("confidence"))
        source_url = _norm(row.get("source_url"))
        if not source_url:
            source_url = None
        evidence_date = _norm(row.get("evidence_date"))
        if not evidence_date:
            evidence_date = None
        evidence_quote = _norm(row.get("evidence_quote"))
        if not evidence_quote:
            evidence_quote = None
        conn.execute(
            """
            INSERT INTO person_name_aliases (
              person_id, alias, canonical_alias, source_id, source_record_pk, source_kind, source_url, evidence_date, evidence_quote, confidence, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_alias) DO UPDATE SET
              person_id=(
                CASE
                  WHEN COALESCE(LOWER(TRIM(person_name_aliases.source_kind)), 'manual_seed') <> 'manual_seed'
                   AND COALESCE(LOWER(TRIM(excluded.source_kind)), 'manual_seed') = 'manual_seed'
                  THEN person_name_aliases.person_id
                  ELSE excluded.person_id
                END
              ),
              alias=(
                CASE
                  WHEN COALESCE(LOWER(TRIM(person_name_aliases.source_kind)), 'manual_seed') <> 'manual_seed'
                   AND COALESCE(LOWER(TRIM(excluded.source_kind)), 'manual_seed') = 'manual_seed'
                  THEN person_name_aliases.alias
                  ELSE excluded.alias
                END
              ),
              source_id=COALESCE(excluded.source_id, person_name_aliases.source_id),
              source_record_pk=COALESCE(excluded.source_record_pk, person_name_aliases.source_record_pk),
              source_kind=(
                CASE
                  WHEN COALESCE(LOWER(TRIM(person_name_aliases.source_kind)), 'manual_seed') <> 'manual_seed'
                   AND COALESCE(LOWER(TRIM(excluded.source_kind)), 'manual_seed') = 'manual_seed'
                  THEN person_name_aliases.source_kind
                  ELSE COALESCE(excluded.source_kind, person_name_aliases.source_kind)
                END
              ),
              source_url=COALESCE(excluded.source_url, person_name_aliases.source_url),
              evidence_date=COALESCE(excluded.evidence_date, person_name_aliases.evidence_date),
              evidence_quote=COALESCE(excluded.evidence_quote, person_name_aliases.evidence_quote),
              confidence=COALESCE(excluded.confidence, person_name_aliases.confidence),
              note=COALESCE(excluded.note, person_name_aliases.note),
              updated_at=excluded.updated_at
            """,
            (
                person_id,
                actor_person_name or resolved_full_name,
                canonical_alias,
                source_id_effective,
                source_record_pk_effective,
                source_kind,
                source_url,
                evidence_date,
                evidence_quote,
                confidence,
                payload_note or None,
                ts,
                ts,
            ),
        )

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM person_name_aliases) AS aliases_total,
          (SELECT COUNT(DISTINCT person_id) FROM person_name_aliases) AS persons_with_aliases_total,
          (SELECT COUNT(*) FROM person_name_aliases WHERE COALESCE(source_kind, 'manual_seed') = 'manual_seed') AS manual_aliases_total,
          (SELECT COUNT(*) FROM person_name_aliases WHERE COALESCE(source_kind, 'manual_seed') <> 'manual_seed') AS official_aliases_total,
          (
            SELECT COUNT(*)
            FROM person_name_aliases
            WHERE COALESCE(source_kind, 'manual_seed') <> 'manual_seed'
              AND source_record_pk IS NOT NULL
          ) AS official_aliases_with_source_record_total
        """
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "counts": counts,
        "totals": {
            "aliases_total": int(totals["aliases_total"]),
            "persons_with_aliases_total": int(totals["persons_with_aliases_total"]),
            "manual_aliases_total": int(totals["manual_aliases_total"]),
            "official_aliases_total": int(totals["official_aliases_total"]),
            "official_aliases_with_source_record_total": int(totals["official_aliases_with_source_record_total"]),
            "official_aliases_missing_source_record_total": max(
                0,
                int(totals["official_aliases_total"]) - int(totals["official_aliases_with_source_record_total"]),
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import liberty_person_identity_resolution_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_person_identity_resolution_seed_v1.json")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--source-id", default="boe_api_legal")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    validation = validate_seed(seed_path)
    if not bool(validation.get("valid")):
        payload = {"status": "invalid_seed", "validation": validation}
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        if _norm(args.out):
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 1

    seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
    db_path = Path(args.db)
    schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            seed_doc=seed_doc,
            source_id=str(args.source_id or ""),
            snapshot_date=str(args.snapshot_date or ""),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "seed_path": str(seed_path),
        "validation": {
            "valid": bool(validation.get("valid")),
            "method_version": _norm(validation.get("method_version")),
            "mappings_total": int(validation.get("mappings_total") or 0),
        },
        "import": report,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
