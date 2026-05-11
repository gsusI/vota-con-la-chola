#!/usr/bin/env python3
"""Backfill generic accountability ledger entries from policy_events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso
from scripts.accountability_evidence_tiers import infer_accountability_evidence_tier


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill accountability ledger from policy_events")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-ids", nargs="*", default=[], help="Optional policy_events source_id filter")
    p.add_argument("--limit", type=int, default=0, help="Optional max policy events to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _role_for_event(source_id: str, instrument_code: str) -> str:
    if instrument_code == "public_contracting" or source_id.startswith("placsp_"):
        return "contracted"
    if instrument_code == "public_subsidy" or source_id.startswith("bdns_"):
        return "subsidized"
    if instrument_code.startswith("boe_") or source_id.startswith("boe_"):
        return "published"
    if instrument_code.startswith("exec_") or source_id.startswith("moncloa_"):
        return "proposed"
    return "unknown"


def _kind_for_event(source_id: str, instrument_code: str) -> str:
    if instrument_code in {"public_contracting", "public_subsidy"} or source_id.startswith(("placsp_", "bdns_")):
        return "money"
    if instrument_code.startswith("boe_") or source_id.startswith("boe_"):
        return "rule"
    if instrument_code.startswith("exec_") or source_id.startswith("moncloa_"):
        return "implementation"
    return "other"


def _tier_for_event(source_id: str, instrument_code: str) -> int | None:
    return infer_accountability_evidence_tier(source_id=source_id, instrument_code=instrument_code)


def _upsert_issue(conn: Any, *, row: Any, now_iso: str) -> str:
    issue_id = f"policy-event:{row['policy_event_id']}"
    label = _norm(row["title"]) or _norm(row["policy_event_id"])
    conn.execute(
        """
        INSERT INTO accountability_issues (
          issue_id,
          case_id,
          canonical_key,
          label,
          summary,
          scope,
          domain_id,
          topic_id,
          issue_status,
          source_kind,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, NULL, 'active', 'derived', ?, ?, ?)
        ON CONFLICT(issue_id) DO UPDATE SET
          canonical_key = excluded.canonical_key,
          label = excluded.label,
          summary = excluded.summary,
          scope = excluded.scope,
          domain_id = excluded.domain_id,
          source_kind = excluded.source_kind,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            issue_id,
            issue_id,
            label,
            _norm(row["summary"]),
            _norm(row["scope"]),
            row["domain_id"],
            _stable_json({"source": "policy_events", "policy_event_id": row["policy_event_id"]}),
            now_iso,
            now_iso,
        ),
    )
    return issue_id


def backfill_policy_event_accountability_ledger(
    conn: Any,
    *,
    source_ids: tuple[str, ...] = (),
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    where = ""
    params: list[Any] = []
    if source_ids:
        where = "WHERE pe.source_id IN ({})".format(",".join("?" for _ in source_ids))
        params.extend(source_ids)
    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    if int(limit or 0) > 0:
        params.append(int(limit))
    rows = conn.execute(
        f"""
        SELECT
          pe.policy_event_id,
          pe.event_date,
          pe.published_date,
          pe.domain_id,
          pe.policy_instrument_id,
          pe.title,
          pe.summary,
          pe.institution_id,
          pe.source_id,
          pe.source_url,
          pe.source_record_pk,
          pe.source_snapshot_date,
          pe.scope,
          pi.code AS instrument_code,
          pi.label AS instrument_label,
          s.name AS source_name,
          i.name AS institution_name
        FROM policy_events pe
        LEFT JOIN policy_instruments pi ON pi.policy_instrument_id = pe.policy_instrument_id
        LEFT JOIN sources s ON s.source_id = pe.source_id
        LEFT JOIN institutions i ON i.institution_id = pe.institution_id
        {where}
        ORDER BY COALESCE(pe.event_date, pe.published_date, ''), pe.policy_event_id
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()
    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_rows_seen": len(rows),
        "issues_upserted": 0,
        "entries_upserted": 0,
        "entries_by_role": {},
        "dry_run": bool(dry_run),
    }
    for row in rows:
        role = _role_for_event(_norm(row["source_id"]), _norm(row["instrument_code"]))
        stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    with conn:
        for row in rows:
            source_id = _norm(row["source_id"])
            instrument_code = _norm(row["instrument_code"])
            issue_id = _upsert_issue(conn, row=row, now_iso=now_iso)
            actor_label = _norm(row["institution_name"]) or _norm(row["source_name"]) or source_id
            role = _role_for_event(source_id, instrument_code)
            payload = {
                "source": "policy_events",
                "policy_event_id": row["policy_event_id"],
                "policy_instrument_id": row["policy_instrument_id"],
                "instrument_code": instrument_code,
            }
            conn.execute(
                """
                INSERT INTO accountability_ledger_entries (
                  entry_id,
                  issue_id,
                  entry_kind,
                  accountability_role,
                  role_in_chain,
                  actor_label,
                  actor_kind,
                  person_id,
                  party_id,
                  mandate_id,
                  institution_id,
                  org_unit_id,
                  position_id,
                  linked_object_type,
                  linked_object_id,
                  policy_event_id,
                  topic_evidence_id,
                  legal_fragment_id,
                  event_date,
                  published_date,
                  title,
                  summary,
                  accountability_question,
                  confidence,
                  evidence_tier,
                  source_id,
                  source_title,
                  source_url,
                  source_locator,
                  source_record_pk,
                  evidence_quote,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (
                  ?, ?, ?, ?, ?, ?, ?,
                  NULL, NULL, NULL, ?, NULL, NULL,
                  'policy_event', ?, ?, NULL, NULL,
                  ?, ?, ?, ?, ?, NULL, ?,
                  ?, ?, ?, ?, ?, NULL, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  entry_kind = excluded.entry_kind,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  institution_id = excluded.institution_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  policy_event_id = excluded.policy_event_id,
                  event_date = excluded.event_date,
                  published_date = excluded.published_date,
                  title = excluded.title,
                  summary = excluded.summary,
                  accountability_question = excluded.accountability_question,
                  evidence_tier = excluded.evidence_tier,
                  source_id = excluded.source_id,
                  source_title = excluded.source_title,
                  source_url = excluded.source_url,
                  source_locator = excluded.source_locator,
                  source_record_pk = excluded.source_record_pk,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    f"policy-event:{row['policy_event_id']}",
                    issue_id,
                    _kind_for_event(source_id, instrument_code),
                    role,
                    role,
                    actor_label,
                    "institution" if row["institution_id"] is not None else "unknown",
                    row["institution_id"],
                    row["policy_event_id"],
                    row["policy_event_id"],
                    row["event_date"],
                    row["published_date"],
                    _norm(row["title"]),
                    _norm(row["summary"]),
                    "What official policy event happened for this issue?",
                    _tier_for_event(source_id, instrument_code),
                    source_id,
                    _norm(row["instrument_label"]) or _norm(row["source_name"]),
                    _norm(row["source_url"]),
                    _norm(row["policy_event_id"]),
                    row["source_record_pk"],
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["issues_upserted"] += 1
            stats["entries_upserted"] += 1
    return stats


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_policy_event_accountability_ledger(
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
        "OK policy-event accountability ledger "
        + f"(seen={summary['source_rows_seen']} entries={summary['entries_upserted']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
