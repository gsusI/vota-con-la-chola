#!/usr/bin/env python3
"""Materialize parliamentary groups and observed memberships from roll-call votes."""

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
from etl.politicos_es.db import apply_schema, open_db, upsert_admin_level, upsert_institution
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso
from publicdata_publish.sanitize import sanitize_url_for_public
from publicdata_sqlite import table_exists


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_SOURCE_IDS = ("congreso_votaciones", "senado_votaciones")

CHAMBERS = {
    "congreso_votaciones": "Congreso de los Diputados",
    "senado_votaciones": "Senado de Espana",
}

GROUP_LABELS = {
    "GP": "Grupo Parlamentario Popular en el Congreso",
    "GS": "Grupo Parlamentario Socialista",
    "GVOX": "Grupo Parlamentario VOX",
    "GSUMAR": "Grupo Parlamentario Plurinacional SUMAR",
    "GMx": "Grupo Parlamentario Mixto",
    "GR": "Grupo Parlamentario Republicano",
    "GJxCAT": "Grupo Parlamentario Junts per Catalunya",
    "GEH Bildu": "Grupo Parlamentario Euskal Herria Bildu",
    "GV (EAJ-PNV)": "Grupo Parlamentario Vasco (EAJ-PNV)",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill parliamentary groups from vote member group_code values")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-ids", nargs="*", default=list(DEFAULT_SOURCE_IDS), help="Vote source_ids to scan")
    p.add_argument("--limit", type=int, default=0, help="Max group rows to process; 0 means all")
    p.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _source_exists(conn: Any, source_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return row is not None


def _group_label(group_code: str) -> str:
    code = _norm(group_code)
    return GROUP_LABELS.get(code, f"Grupo parlamentario {code}")


def _ensure_institution(conn: Any, *, source_id: str, now_iso: str) -> int | None:
    institution_name = CHAMBERS.get(source_id)
    if not institution_name:
        return None
    admin_level_id = upsert_admin_level(conn, "nacional", now_iso)
    return upsert_institution(conn, institution_name, "nacional", "", admin_level_id, None, now_iso)


def _group_rows(conn: Any, *, source_ids: tuple[str, ...], limit: int) -> list[Any]:
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
            mv.group_code,
            e.vote_date,
            mv.vote_event_id,
            mv.source_url
          FROM parl_vote_member_votes mv
          JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
          WHERE mv.source_id IN ({placeholders})
            AND TRIM(COALESCE(mv.group_code, '')) <> ''
        ),
        known_legislatures AS (
          SELECT
            source_id,
            group_code,
            COUNT(DISTINCT NULLIF(TRIM(legislature), '')) AS known_legs,
            MIN(NULLIF(TRIM(legislature), '')) AS known_leg
          FROM base
          GROUP BY source_id, group_code
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
           AND k.group_code = b.group_code
        )
        SELECT
          source_id,
          effective_legislature AS legislature,
          group_code,
          MIN(vote_date) AS first_vote_date,
          MAX(vote_date) AS last_vote_date,
          COUNT(*) AS vote_rows,
          COUNT(DISTINCT vote_event_id) AS vote_events,
          MIN(source_url) AS source_url
        FROM resolved
        GROUP BY source_id, effective_legislature, group_code
        ORDER BY source_id, effective_legislature, group_code
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()


def _membership_rows(conn: Any, *, source_ids: tuple[str, ...]) -> list[Any]:
    placeholders = ",".join(["?"] * len(source_ids))
    return conn.execute(
        f"""
        WITH base AS (
          SELECT
            mv.source_id,
            e.legislature,
            mv.group_code,
            mv.person_id,
            mv.member_name,
            e.vote_date,
            mv.vote_event_id,
            mv.source_url
          FROM parl_vote_member_votes mv
          JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
          WHERE mv.source_id IN ({placeholders})
            AND mv.person_id IS NOT NULL
            AND TRIM(COALESCE(mv.group_code, '')) <> ''
        ),
        known_legislatures AS (
          SELECT
            source_id,
            group_code,
            COUNT(DISTINCT NULLIF(TRIM(legislature), '')) AS known_legs,
            MIN(NULLIF(TRIM(legislature), '')) AS known_leg
          FROM base
          GROUP BY source_id, group_code
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
           AND k.group_code = b.group_code
        )
        SELECT
          source_id,
          effective_legislature AS legislature,
          group_code,
          person_id,
          MIN(member_name) AS member_name,
          MIN(vote_date) AS first_vote_date,
          MAX(vote_date) AS last_vote_date,
          COUNT(*) AS vote_rows,
          COUNT(DISTINCT vote_event_id) AS vote_events,
          MIN(source_url) AS source_url
        FROM resolved
        GROUP BY source_id, effective_legislature, group_code, person_id
        ORDER BY source_id, effective_legislature, group_code, member_name
        """,
        tuple(source_ids),
    ).fetchall()


def _upsert_group(conn: Any, *, row: Any, institution_id: int | None, now_iso: str) -> int:
    group_code = _norm(row["group_code"])
    legislature = _norm(row["legislature"]) or "unknown"
    name = _group_label(group_code)
    payload = {
        "source": "parl_vote_member_votes",
        "method": "observed_roll_call_group_code",
        "caveat": "Parliamentary group code is not treated as a one-party affiliation.",
        "source_id": _norm(row["source_id"]),
        "legislature": legislature,
        "group_code": group_code,
        "first_vote_date": _norm(row["first_vote_date"]),
        "last_vote_date": _norm(row["last_vote_date"]),
        "vote_rows": int(row["vote_rows"] or 0),
        "vote_events": int(row["vote_events"] or 0),
    }
    out = conn.execute(
        """
        INSERT INTO parliamentary_groups (
          source_id, institution_id, legislature, group_code, name, normalized_name,
          source_url, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, legislature, group_code) DO UPDATE SET
          institution_id = COALESCE(excluded.institution_id, parliamentary_groups.institution_id),
          name = excluded.name,
          normalized_name = excluded.normalized_name,
          source_url = COALESCE(excluded.source_url, parliamentary_groups.source_url),
          raw_payload = excluded.raw_payload,
          updated_at = excluded.updated_at
        RETURNING parliamentary_group_id
        """,
        (
            _norm(row["source_id"]),
            institution_id,
            legislature,
            group_code,
            name,
            normalize_key_part(name),
            sanitize_url_for_public(_norm(row["source_url"])) or None,
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if out is None:
        raise RuntimeError(f"could not upsert parliamentary group {group_code!r}")
    return int(out["parliamentary_group_id"])


def _update_member_votes_for_group(conn: Any, *, row: Any, group_id: int, now_iso: str) -> int:
    source_id = _norm(row["source_id"])
    group_code = _norm(row["group_code"])
    legislature = _norm(row["legislature"]) or "unknown"
    cur = conn.execute(
        """
        UPDATE parl_vote_member_votes
        SET parliamentary_group_id = ?,
            updated_at = ?
        WHERE member_vote_id IN (
          WITH base AS (
            SELECT
              mv.member_vote_id,
              mv.source_id,
              e.legislature,
              mv.group_code
            FROM parl_vote_member_votes mv
            JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
            WHERE mv.source_id = ?
              AND mv.group_code = ?
          ),
          known_legislatures AS (
            SELECT
              source_id,
              group_code,
              COUNT(DISTINCT NULLIF(TRIM(legislature), '')) AS known_legs,
              MIN(NULLIF(TRIM(legislature), '')) AS known_leg
            FROM base
            GROUP BY source_id, group_code
          )
          SELECT b.member_vote_id
          FROM base b
          LEFT JOIN known_legislatures k
            ON k.source_id = b.source_id
           AND k.group_code = b.group_code
          WHERE COALESCE(
              NULLIF(TRIM(b.legislature), ''),
              CASE WHEN k.known_legs = 1 THEN k.known_leg END,
              ''
            ) = ?
        )
        """,
        (group_id, now_iso, source_id, group_code, "" if legislature == "unknown" else legislature),
    )
    return int(cur.rowcount if cur.rowcount is not None else 0)


def backfill_parliamentary_groups_from_vote_member_votes(
    conn: Any,
    *,
    source_ids: tuple[str, ...] = DEFAULT_SOURCE_IDS,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not table_exists(conn, "parl_vote_member_votes") or not table_exists(conn, "parl_vote_events"):
        return {
            "source_rows_seen": 0,
            "groups_seen": 0,
            "groups_upserted": 0,
            "memberships_upserted": 0,
            "member_votes_updated": 0,
            "dry_run": bool(dry_run),
        }
    effective_source_ids = tuple(sid for sid in source_ids if sid in CHAMBERS and _source_exists(conn, sid))
    if not effective_source_ids:
        return {
            "source_rows_seen": 0,
            "groups_seen": 0,
            "groups_upserted": 0,
            "memberships_upserted": 0,
            "member_votes_updated": 0,
            "missing_or_unsupported_source_ids": list(source_ids),
            "dry_run": bool(dry_run),
        }

    groups = _group_rows(conn, source_ids=effective_source_ids, limit=limit)
    stats: dict[str, Any] = {
        "source_rows_seen": sum(int(row["vote_rows"] or 0) for row in groups),
        "groups_seen": len(groups),
        "groups_upserted": 0,
        "memberships_upserted": 0,
        "member_votes_updated": 0,
        "groups_by_source": dict(Counter(_norm(row["source_id"]) for row in groups)),
        "source_ids": list(effective_source_ids),
        "dry_run": bool(dry_run),
    }
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    group_ids: dict[tuple[str, str, str], int] = {}
    institutions: dict[str, int | None] = {}
    with conn:
        for row in groups:
            source_id = _norm(row["source_id"])
            institution_id = institutions.get(source_id)
            if source_id not in institutions:
                institution_id = _ensure_institution(conn, source_id=source_id, now_iso=now_iso)
                institutions[source_id] = institution_id
            group_id = _upsert_group(conn, row=row, institution_id=institution_id, now_iso=now_iso)
            key = (source_id, _norm(row["legislature"]) or "unknown", _norm(row["group_code"]))
            group_ids[key] = group_id
            stats["groups_upserted"] += 1
            stats["member_votes_updated"] += _update_member_votes_for_group(conn, row=row, group_id=group_id, now_iso=now_iso)

        for row in _membership_rows(conn, source_ids=effective_source_ids):
            key = (_norm(row["source_id"]), _norm(row["legislature"]) or "unknown", _norm(row["group_code"]))
            group_id = group_ids.get(key)
            if group_id is None:
                existing = conn.execute(
                    """
                    SELECT parliamentary_group_id
                    FROM parliamentary_groups
                    WHERE source_id = ?
                      AND legislature = ?
                      AND group_code = ?
                    """,
                    key,
                ).fetchone()
                if existing is None:
                    continue
                group_id = int(existing["parliamentary_group_id"])
            payload = {
                "source": "parl_vote_member_votes",
                "method": "observed_roll_call_group_membership",
                "source_id": _norm(row["source_id"]),
                "legislature": _norm(row["legislature"]) or "unknown",
                "group_code": _norm(row["group_code"]),
                "member_name": _norm(row["member_name"]),
                "first_vote_date": _norm(row["first_vote_date"]),
                "last_vote_date": _norm(row["last_vote_date"]),
                "vote_rows": int(row["vote_rows"] or 0),
                "vote_events": int(row["vote_events"] or 0),
            }
            conn.execute(
                """
                INSERT INTO person_parliamentary_group_memberships (
                  person_id, parliamentary_group_id, source_id, legislature,
                  start_date, end_date, source_url, evidence_quote, raw_payload,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id, parliamentary_group_id, source_id, start_date) DO UPDATE SET
                  legislature = excluded.legislature,
                  end_date = excluded.end_date,
                  source_url = COALESCE(excluded.source_url, person_parliamentary_group_memberships.source_url),
                  evidence_quote = excluded.evidence_quote,
                  raw_payload = excluded.raw_payload,
                  updated_at = excluded.updated_at
                """,
                (
                    int(row["person_id"]),
                    group_id,
                    _norm(row["source_id"]),
                    _norm(row["legislature"]) or "unknown",
                    _norm(row["first_vote_date"]) or None,
                    _norm(row["last_vote_date"]) or None,
                    sanitize_url_for_public(_norm(row["source_url"])) or None,
                    _norm(row["group_code"]),
                    json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
                    now_iso,
                    now_iso,
                ),
            )
            stats["memberships_upserted"] += 1
    return stats


def main() -> int:
    args = parse_args()
    with closing(open_db(Path(args.db))) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_parliamentary_groups_from_vote_member_votes(
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
        "OK parliamentary group backfill "
        + f"(groups={summary['groups_seen']} memberships={summary['memberships_upserted']} "
        + f"member_votes_updated={summary['member_votes_updated']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
