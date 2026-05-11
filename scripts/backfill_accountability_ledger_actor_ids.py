#!/usr/bin/env python3
"""Resolve accountability ledger actor labels to known persons, parties, institutions, org units, and positions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve accountability ledger actor IDs from exact labels")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--limit", type=int, default=0, help="Optional max unresolved ledger rows to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm_label(value: Any) -> str:
    return normalize_key_part(normalize_ws(str(value or "")))


def _add(mapping: dict[str, set[int]], label: Any, item_id: Any) -> None:
    key = _norm_label(label)
    if not key or item_id is None:
        return
    mapping[key].add(int(item_id))


def _load_actor_maps(conn: Any) -> dict[str, dict[str, set[int]]]:
    maps: dict[str, dict[str, set[int]]] = {
        "person": defaultdict(set),
        "party": defaultdict(set),
        "institution": defaultdict(set),
        "org_unit": defaultdict(set),
        "position": defaultdict(set),
    }
    for row in conn.execute("SELECT person_id, full_name FROM persons").fetchall():
        _add(maps["person"], row["full_name"], row["person_id"])
    for row in conn.execute("SELECT person_id, alias FROM person_name_aliases").fetchall():
        _add(maps["person"], row["alias"], row["person_id"])

    for row in conn.execute("SELECT party_id, name, acronym FROM parties").fetchall():
        _add(maps["party"], row["name"], row["party_id"])
        _add(maps["party"], row["acronym"], row["party_id"])
    for row in conn.execute("SELECT party_id, alias FROM party_aliases").fetchall():
        _add(maps["party"], row["alias"], row["party_id"])

    for row in conn.execute("SELECT institution_id, name FROM institutions").fetchall():
        _add(maps["institution"], row["name"], row["institution_id"])

    for row in conn.execute("SELECT org_unit_id, name, normalized_name, org_unit_code FROM government_org_units").fetchall():
        _add(maps["org_unit"], row["name"], row["org_unit_id"])
        _add(maps["org_unit"], row["normalized_name"], row["org_unit_id"])
        _add(maps["org_unit"], row["org_unit_code"], row["org_unit_id"])

    for row in conn.execute("SELECT position_id, title, position_code FROM government_positions").fetchall():
        _add(maps["position"], row["title"], row["position_id"])
        _add(maps["position"], row["position_code"], row["position_id"])
    return maps


def _unique_match(mapping: dict[str, set[int]], key: str) -> int | None:
    values = mapping.get(key) or set()
    if len(values) != 1:
        return None
    return next(iter(values))


def _resolve_actor(maps: dict[str, dict[str, set[int]]], actor_label: str) -> dict[str, int | str] | None:
    key = _norm_label(actor_label)
    if not key:
        return None
    for kind, field in (
        ("person", "person_id"),
        ("party", "party_id"),
        ("institution", "institution_id"),
        ("org_unit", "org_unit_id"),
        ("position", "position_id"),
    ):
        matched_id = _unique_match(maps[kind], key)
        if matched_id is not None:
            return {"actor_kind": kind, field: matched_id}
    return None


def backfill_accountability_ledger_actor_ids(
    conn: Any,
    *,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    maps = _load_actor_maps(conn)
    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    params: tuple[Any, ...] = (int(limit),) if int(limit or 0) > 0 else ()
    rows = conn.execute(
        f"""
        SELECT
          entry_id,
          actor_label,
          person_id,
          party_id,
          institution_id,
          org_unit_id,
          position_id
        FROM accountability_ledger_entries
        WHERE actor_label IS NOT NULL
          AND TRIM(actor_label) <> ''
          AND person_id IS NULL
          AND party_id IS NULL
          AND institution_id IS NULL
          AND org_unit_id IS NULL
          AND position_id IS NULL
        ORDER BY entry_id
        {limit_sql}
        """,
        params,
    ).fetchall()
    summary: dict[str, Any] = {
        "rows_seen": len(rows),
        "rows_resolved": 0,
        "rows_unresolved": 0,
        "resolved_by_kind": {"person": 0, "party": 0, "institution": 0, "org_unit": 0, "position": 0},
        "dry_run": bool(dry_run),
    }
    resolved: list[tuple[dict[str, int | str], str]] = []
    for row in rows:
        match = _resolve_actor(maps, str(row["actor_label"] or ""))
        if match is None:
            summary["rows_unresolved"] += 1
            continue
        kind = str(match["actor_kind"])
        summary["rows_resolved"] += 1
        summary["resolved_by_kind"][kind] += 1
        resolved.append((match, str(row["entry_id"])))

    if dry_run or not resolved:
        return summary

    now_iso = now_utc_iso()
    with conn:
        for match, entry_id in resolved:
            conn.execute(
                """
                UPDATE accountability_ledger_entries
                SET actor_kind = ?,
                    person_id = COALESCE(person_id, ?),
                    party_id = COALESCE(party_id, ?),
                    institution_id = COALESCE(institution_id, ?),
                    org_unit_id = COALESCE(org_unit_id, ?),
                    position_id = COALESCE(position_id, ?),
                    updated_at = ?
                WHERE entry_id = ?
                """,
                (
                    match["actor_kind"],
                    match.get("person_id"),
                    match.get("party_id"),
                    match.get("institution_id"),
                    match.get("org_unit_id"),
                    match.get("position_id"),
                    now_iso,
                    entry_id,
                ),
            )
    return summary


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_accountability_ledger_actor_ids(
            conn,
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK accountability actor id resolution "
        + f"(seen={summary['rows_seen']} resolved={summary['rows_resolved']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
