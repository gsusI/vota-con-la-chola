#!/usr/bin/env python3
"""Create conservative person aliases from official parliamentary roll-call names."""

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
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import canonical_key, normalize_key_part, normalize_ws, now_utc_iso
from publicdata_publish.sanitize import sanitize_url_for_public
from publicdata_sqlite import table_exists


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_SOURCE_IDS = ("congreso_votaciones", "senado_votaciones")
SOURCE_KIND = "official_roll_call"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill persons from official roll-call member names")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-ids", nargs="*", default=list(DEFAULT_SOURCE_IDS), help="Vote source_ids to scan")
    p.add_argument("--limit", type=int, default=0, help="Max distinct labels to process; 0 means all")
    p.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _name_key(member_name: str, member_name_normalized: str = "") -> str:
    return normalize_key_part(member_name_normalized or member_name)


def _source_exists(conn: Any, source_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return row is not None


def _existing_person_id(conn: Any, *, full_name: str, name_key: str) -> int | None:
    row = conn.execute(
        """
        SELECT person_id
        FROM person_name_aliases
        WHERE canonical_alias = ?
        """,
        (name_key,),
    ).fetchone()
    if row is not None:
        return int(row["person_id"])
    ckey = canonical_key(full_name, None, "")
    row = conn.execute("SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)).fetchone()
    if row is not None:
        return int(row["person_id"])
    row = conn.execute(
        "SELECT person_id FROM persons WHERE lower(trim(full_name)) = lower(trim(?)) ORDER BY person_id LIMIT 1",
        (full_name,),
    ).fetchone()
    if row is not None:
        return int(row["person_id"])
    return None


def _create_person(conn: Any, *, full_name: str, now_iso: str) -> int:
    ckey = canonical_key(full_name, None, "")
    cur = conn.execute(
        """
        INSERT INTO persons (full_name, territory_code, canonical_key, created_at, updated_at)
        VALUES (?, '', ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (full_name, ckey, now_iso, now_iso),
    )
    if cur.lastrowid:
        return int(cur.lastrowid)
    row = conn.execute("SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)).fetchone()
    if row is None:
        raise RuntimeError(f"person upsert failed for {full_name!r}")
    return int(row["person_id"])


def _upsert_alias(
    conn: Any,
    *,
    person_id: int,
    alias: str,
    canonical_alias: str,
    source_id: str | None,
    source_url: str,
    now_iso: str,
) -> None:
    note = "Created from exact official roll-call member label; verify external person identifier separately."
    conn.execute(
        """
        INSERT INTO person_name_aliases (
          person_id, alias, canonical_alias, source_id, source_kind, source_url,
          confidence, note, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_alias) DO UPDATE SET
          person_id = excluded.person_id,
          alias = excluded.alias,
          source_id = COALESCE(excluded.source_id, person_name_aliases.source_id),
          source_kind = excluded.source_kind,
          source_url = COALESCE(excluded.source_url, person_name_aliases.source_url),
          confidence = COALESCE(excluded.confidence, person_name_aliases.confidence),
          note = COALESCE(excluded.note, person_name_aliases.note),
          updated_at = excluded.updated_at
        """,
        (person_id, alias, canonical_alias, source_id, SOURCE_KIND, source_url or None, 0.8, note, now_iso, now_iso),
    )


def _distinct_vote_member_rows(conn: Any, *, source_ids: tuple[str, ...], limit: int) -> list[Any]:
    placeholders = ",".join(["?"] * len(source_ids))
    limit_sql = "LIMIT ?" if limit > 0 else ""
    params: list[Any] = list(source_ids)
    if limit > 0:
        params.append(int(limit))
    return conn.execute(
        f"""
        SELECT
          COALESCE(NULLIF(TRIM(member_name_normalized), ''), lower(trim(member_name))) AS name_key_raw,
          MIN(member_name) AS member_name,
          MIN(member_name_normalized) AS member_name_normalized,
          COUNT(*) AS vote_rows,
          COUNT(DISTINCT vote_event_id) AS vote_events,
          COUNT(DISTINCT source_id) AS source_ids_total,
          MIN(source_id) AS source_id,
          MIN(source_url) AS source_url
        FROM parl_vote_member_votes
        WHERE source_id IN ({placeholders})
          AND TRIM(COALESCE(member_name, '')) <> ''
        GROUP BY COALESCE(NULLIF(TRIM(member_name_normalized), ''), lower(trim(member_name)))
        ORDER BY vote_rows DESC, member_name
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()


def backfill_persons_from_vote_member_names(
    conn: Any,
    *,
    source_ids: tuple[str, ...] = DEFAULT_SOURCE_IDS,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not table_exists(conn, "parl_vote_member_votes"):
        return {
            "source_rows_seen": 0,
            "distinct_labels_seen": 0,
            "persons_created": 0,
            "aliases_upserted": 0,
            "member_votes_updated": 0,
            "dry_run": bool(dry_run),
        }

    effective_source_ids = tuple(sid for sid in source_ids if _source_exists(conn, sid))
    if not effective_source_ids:
        return {
            "source_rows_seen": 0,
            "distinct_labels_seen": 0,
            "persons_created": 0,
            "aliases_upserted": 0,
            "member_votes_updated": 0,
            "missing_source_ids": list(source_ids),
            "dry_run": bool(dry_run),
        }

    rows = _distinct_vote_member_rows(conn, source_ids=effective_source_ids, limit=limit)
    stats: dict[str, Any] = {
        "source_rows_seen": sum(int(row["vote_rows"] or 0) for row in rows),
        "distinct_labels_seen": len(rows),
        "persons_created": 0,
        "persons_existing": 0,
        "aliases_upserted": 0,
        "member_votes_updated": 0,
        "rows_skipped_blank_key": 0,
        "source_ids": list(effective_source_ids),
        "created_by_source": {},
        "dry_run": bool(dry_run),
    }
    created_by_source: Counter[str] = Counter()
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    with conn:
        for row in rows:
            member_name = _norm(row["member_name"])
            member_name_normalized = _norm(row["member_name_normalized"])
            name_key = _name_key(member_name, member_name_normalized)
            if not name_key:
                stats["rows_skipped_blank_key"] += 1
                continue
            person_id = _existing_person_id(conn, full_name=member_name, name_key=name_key)
            if person_id is None:
                person_id = _create_person(conn, full_name=member_name, now_iso=now_iso)
                stats["persons_created"] += 1
                created_by_source[_norm(row["source_id"])] += 1
            else:
                stats["persons_existing"] += 1
            source_id = _norm(row["source_id"]) if int(row["source_ids_total"] or 0) == 1 else None
            _upsert_alias(
                conn,
                person_id=person_id,
                alias=member_name,
                canonical_alias=name_key,
                source_id=source_id,
                source_url=sanitize_url_for_public(_norm(row["source_url"])),
                now_iso=now_iso,
            )
            stats["aliases_upserted"] += 1
            cur = conn.execute(
                """
                UPDATE parl_vote_member_votes
                SET person_id = ?,
                    updated_at = ?
                WHERE source_id IN ({})
                  AND person_id IS NULL
                  AND COALESCE(NULLIF(TRIM(member_name_normalized), ''), lower(trim(member_name))) = ?
                """.format(",".join(["?"] * len(effective_source_ids))),
                (person_id, now_iso, *effective_source_ids, row["name_key_raw"]),
            )
            stats["member_votes_updated"] += int(cur.rowcount if cur.rowcount is not None else 0)
    stats["created_by_source"] = dict(sorted(created_by_source.items()))
    return stats


def main() -> int:
    args = parse_args()
    with closing(open_db(Path(args.db))) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_persons_from_vote_member_names(
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
        "OK vote-member person backfill "
        + f"(labels={summary['distinct_labels_seen']} created={summary['persons_created']} "
        + f"member_votes_updated={summary['member_votes_updated']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
