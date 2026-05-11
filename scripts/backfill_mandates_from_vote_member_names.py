#!/usr/bin/env python3
"""Create observed parliamentary mandates from official roll-call participation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import (
    apply_schema,
    open_db,
    upsert_admin_level,
    upsert_institution,
    upsert_role,
)
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso
from publicdata_sqlite import table_exists


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_SOURCE_IDS = ("congreso_votaciones", "senado_votaciones")

CHAMBERS = {
    "congreso_votaciones": {
        "institution": "Congreso de los Diputados",
        "role": "Diputado/a",
    },
    "senado_votaciones": {
        "institution": "Senado de Espana",
        "role": "Senador/a",
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill observed mandates from official roll-call names")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-ids", nargs="*", default=list(DEFAULT_SOURCE_IDS), help="Vote source_ids to scan")
    p.add_argument("--limit", type=int, default=0, help="Max observed mandate groups to process; 0 means all")
    p.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _source_exists(conn: Any, source_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return row is not None


def _observed_rows(conn: Any, *, source_ids: tuple[str, ...], limit: int) -> list[Any]:
    placeholders = ",".join(["?"] * len(source_ids))
    limit_sql = "LIMIT ?" if limit > 0 else ""
    params: list[Any] = list(source_ids)
    if limit > 0:
        params.append(int(limit))
    return conn.execute(
        f"""
        WITH base AS (
          SELECT
            mv.source_id,
            e.legislature,
            mv.person_id,
            mv.member_name,
            COALESCE(NULLIF(TRIM(mv.member_name_normalized), ''), lower(trim(mv.member_name))) AS name_key_raw,
            e.vote_date,
            mv.vote_event_id,
            mv.group_code,
            mv.source_snapshot_date,
            mv.source_url
          FROM parl_vote_member_votes mv
          JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
          WHERE mv.source_id IN ({placeholders})
            AND mv.person_id IS NOT NULL
            AND TRIM(COALESCE(mv.member_name, '')) <> ''
        ),
        known_legislatures AS (
          SELECT
            source_id,
            person_id,
            name_key_raw,
            COUNT(DISTINCT NULLIF(TRIM(legislature), '')) AS known_legs,
            MIN(NULLIF(TRIM(legislature), '')) AS known_leg
          FROM base
          GROUP BY source_id, person_id, name_key_raw
        ),
        resolved AS (
          SELECT
            b.*,
            COALESCE(
              NULLIF(TRIM(b.legislature), ''),
              CASE WHEN k.known_legs = 1 THEN k.known_leg END,
              ''
            ) AS effective_legislature
          FROM base b
          LEFT JOIN known_legislatures k
            ON k.source_id = b.source_id
           AND k.person_id = b.person_id
           AND k.name_key_raw = b.name_key_raw
        )
        SELECT
          source_id,
          effective_legislature AS legislature,
          person_id,
          MIN(member_name) AS member_name,
          name_key_raw,
          MIN(vote_date) AS first_vote_date,
          MAX(vote_date) AS last_vote_date,
          COUNT(*) AS vote_rows,
          COUNT(DISTINCT vote_event_id) AS vote_events,
          COUNT(DISTINCT NULLIF(TRIM(group_code), '')) AS group_codes_total,
          MIN(NULLIF(TRIM(group_code), '')) AS first_group_code,
          MAX(NULLIF(TRIM(group_code), '')) AS last_group_code,
          MIN(source_snapshot_date) AS first_snapshot_date,
          MAX(source_snapshot_date) AS last_snapshot_date,
          MIN(source_url) AS source_url
        FROM resolved
        GROUP BY source_id, effective_legislature, person_id, name_key_raw
        ORDER BY source_id, effective_legislature, member_name
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()


def _ensure_chamber_refs(conn: Any, *, source_id: str, now_iso: str) -> dict[str, int | str]:
    chamber = CHAMBERS.get(source_id)
    if chamber is None:
        raise ValueError(f"unsupported vote source_id: {source_id}")
    admin_level_id = upsert_admin_level(conn, "nacional", now_iso)
    institution_id = upsert_institution(
        conn,
        chamber["institution"],
        "nacional",
        "",
        admin_level_id,
        None,
        now_iso,
    )
    role_id = upsert_role(conn, chamber["role"], now_iso)
    return {
        "institution_id": int(institution_id),
        "role_id": int(role_id) if role_id is not None else None,
        "admin_level_id": int(admin_level_id) if admin_level_id is not None else None,
        "role_title": chamber["role"],
    }


def _source_record_id(row: Any) -> str:
    name_key = normalize_key_part(_norm(row["name_key_raw"]) or _norm(row["member_name"]))
    legislature = _norm(row["legislature"]) or "unknown"
    return f"observed-rollcall-mandate:leg{legislature}:{name_key}"


def _superseded_unknown_source_record_ids(rows: list[Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in rows:
        legislature = _norm(row["legislature"]) or "unknown"
        if legislature == "unknown":
            continue
        name_key = normalize_key_part(_norm(row["name_key_raw"]) or _norm(row["member_name"]))
        if not name_key:
            continue
        out.append((_norm(row["source_id"]), f"observed-rollcall-mandate:legunknown:{name_key}"))
    return out


def backfill_mandates_from_vote_member_names(
    conn: Any,
    *,
    source_ids: tuple[str, ...] = DEFAULT_SOURCE_IDS,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not table_exists(conn, "parl_vote_member_votes") or not table_exists(conn, "parl_vote_events"):
        return {
            "source_rows_seen": 0,
            "observed_mandates_seen": 0,
            "mandates_upserted": 0,
            "dry_run": bool(dry_run),
        }

    effective_source_ids = tuple(sid for sid in source_ids if sid in CHAMBERS and _source_exists(conn, sid))
    if not effective_source_ids:
        return {
            "source_rows_seen": 0,
            "observed_mandates_seen": 0,
            "mandates_upserted": 0,
            "missing_or_unsupported_source_ids": list(source_ids),
            "dry_run": bool(dry_run),
        }

    rows = _observed_rows(conn, source_ids=effective_source_ids, limit=limit)
    stats: dict[str, Any] = {
        "source_rows_seen": sum(int(row["vote_rows"] or 0) for row in rows),
        "observed_mandates_seen": len(rows),
        "mandates_upserted": 0,
        "stale_unknown_mandates_deleted": 0,
        "mandates_by_source": {},
        "source_ids": list(effective_source_ids),
        "dry_run": bool(dry_run),
    }
    if dry_run:
        stats["mandates_by_source"] = dict(Counter(_norm(row["source_id"]) for row in rows))
        return stats

    now_iso = now_utc_iso()
    by_source: Counter[str] = Counter()
    refs_by_source: dict[str, dict[str, int | str]] = {}
    with conn:
        superseded = _superseded_unknown_source_record_ids(rows)
        for source_id, source_record_id in superseded:
            cur = conn.execute(
                """
                DELETE FROM mandates
                WHERE source_id = ?
                  AND source_record_id = ?
                  AND source_record_id LIKE 'observed-rollcall-mandate:legunknown:%'
                """,
                (source_id, source_record_id),
            )
            stats["stale_unknown_mandates_deleted"] += int(cur.rowcount if cur.rowcount is not None else 0)
        for row in rows:
            source_id = _norm(row["source_id"])
            refs = refs_by_source.get(source_id)
            if refs is None:
                refs = _ensure_chamber_refs(conn, source_id=source_id, now_iso=now_iso)
                refs_by_source[source_id] = refs
            source_record_id = _source_record_id(row)
            payload = {
                "source": "parl_vote_member_votes",
                "method": "observed_roll_call_participation",
                "caveat": "Observed voting range only; verify full mandate dates against official member registry.",
                "source_id": source_id,
                "legislature": _norm(row["legislature"]),
                "member_name": _norm(row["member_name"]),
                "name_key": normalize_key_part(_norm(row["name_key_raw"]) or _norm(row["member_name"])),
                "first_vote_date": _norm(row["first_vote_date"]),
                "last_vote_date": _norm(row["last_vote_date"]),
                "vote_rows": int(row["vote_rows"] or 0),
                "vote_events": int(row["vote_events"] or 0),
                "group_codes_total": int(row["group_codes_total"] or 0),
                "first_group_code": _norm(row["first_group_code"]),
                "last_group_code": _norm(row["last_group_code"]),
            }
            conn.execute(
                """
                INSERT INTO mandates (
                  person_id, institution_id, party_id, role_title, role_id,
                  level, admin_level_id, territory_code, territory_id,
                  start_date, end_date, is_active, source_id, source_record_id,
                  source_record_pk, source_snapshot_date, first_seen_at, last_seen_at, raw_payload
                ) VALUES (?, ?, NULL, ?, ?, 'nacional', ?, '', NULL, ?, ?, 1, ?, ?, NULL, ?, ?, ?, ?)
                ON CONFLICT(source_id, source_record_id) DO UPDATE SET
                  person_id = excluded.person_id,
                  institution_id = excluded.institution_id,
                  role_title = excluded.role_title,
                  role_id = excluded.role_id,
                  level = excluded.level,
                  admin_level_id = excluded.admin_level_id,
                  start_date = excluded.start_date,
                  end_date = excluded.end_date,
                  is_active = excluded.is_active,
                  source_snapshot_date = COALESCE(excluded.source_snapshot_date, mandates.source_snapshot_date),
                  last_seen_at = excluded.last_seen_at,
                  raw_payload = excluded.raw_payload
                """,
                (
                    int(row["person_id"]),
                    int(refs["institution_id"]),
                    str(refs["role_title"]),
                    refs["role_id"],
                    refs["admin_level_id"],
                    _norm(row["first_vote_date"]) or None,
                    _norm(row["last_vote_date"]) or None,
                    source_id,
                    source_record_id,
                    _norm(row["last_snapshot_date"]) or _norm(row["first_snapshot_date"]) or None,
                    now_iso,
                    now_iso,
                    json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
                ),
            )
            stats["mandates_upserted"] += 1
            by_source[source_id] += 1
    stats["mandates_by_source"] = dict(sorted(by_source.items()))
    return stats


def main() -> int:
    args = parse_args()
    with closing(open_db(Path(args.db))) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_mandates_from_vote_member_names(
            conn,
            source_ids=tuple(str(item) for item in args.source_ids),
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK vote-member mandate backfill "
        + f"(observed={summary['observed_mandates_seen']} upserted={summary['mandates_upserted']} "
        + f"dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
