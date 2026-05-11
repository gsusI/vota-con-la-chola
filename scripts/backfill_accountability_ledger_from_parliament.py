#!/usr/bin/env python3
"""Backfill generic accountability ledger entries from parliamentary roll-call votes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso
from scripts.accountability_evidence_tiers import PRIMARY_RECORD_TIER


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_VOTE_SOURCE_IDS = ("congreso_votaciones", "senado_votaciones")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill accountability ledger from roll-call votes")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--vote-source-ids",
        nargs="+",
        default=list(DEFAULT_VOTE_SOURCE_IDS),
        help="Vote source_id values to backfill",
    )
    p.add_argument("--limit", type=int, default=0, help="Optional max source vote rows to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _choice_role(vote_choice: str) -> str:
    key = normalize_key_part(vote_choice)
    if key in {"si", "s"}:
        return "voted_for"
    if key == "no":
        return "voted_against"
    if key in {"abstencion", "abstencin"}:
        return "abstained"
    return "unknown"


def _resolve_mandate(conn: Any, *, person_id: int | None, vote_date: str | None) -> dict[str, Any]:
    if person_id is None:
        return {"mandate_id": None, "party_id": None, "institution_id": None}
    row = conn.execute(
        """
        SELECT mandate_id, party_id, institution_id
        FROM mandates
        WHERE person_id = ?
          AND (
            ? IS NULL OR ? = ''
            OR start_date IS NULL OR start_date = '' OR start_date <= ?
          )
          AND (
            ? IS NULL OR ? = ''
            OR end_date IS NULL OR end_date = '' OR end_date >= ?
          )
        ORDER BY
          CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
          COALESCE(start_date, '') DESC,
          mandate_id DESC
        LIMIT 1
        """,
        (person_id, vote_date, vote_date, vote_date, vote_date, vote_date, vote_date),
    ).fetchone()
    if row is None:
        return {"mandate_id": None, "party_id": None, "institution_id": None}
    return {
        "mandate_id": row["mandate_id"],
        "party_id": row["party_id"],
        "institution_id": row["institution_id"],
    }


def _issue_from_row(row: Any) -> dict[str, str]:
    initiative_id = _norm(row["initiative_id"])
    vote_event_id = _norm(row["vote_event_id"])
    initiative_title = _norm(row["initiative_title"])
    vote_title = _norm(row["vote_title"])
    if initiative_id:
        return {
            "issue_id": f"parl-initiative:{initiative_id}",
            "canonical_key": f"parl-initiative:{initiative_id}",
            "label": initiative_title or vote_title or initiative_id,
            "summary": f"Parliamentary initiative linked to vote {vote_event_id}.",
        }
    return {
        "issue_id": f"parl-vote:{vote_event_id}",
        "canonical_key": f"parl-vote:{vote_event_id}",
        "label": vote_title or vote_event_id,
        "summary": "Parliamentary vote without deterministic initiative link.",
    }


def _upsert_issue(conn: Any, *, issue: dict[str, str], now_iso: str) -> None:
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
        ) VALUES (?, NULL, ?, ?, ?, 'nacional', NULL, NULL, 'active', 'derived', ?, ?, ?)
        ON CONFLICT(issue_id) DO UPDATE SET
          canonical_key = excluded.canonical_key,
          label = excluded.label,
          summary = excluded.summary,
          scope = excluded.scope,
          source_kind = excluded.source_kind,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            issue["issue_id"],
            issue["canonical_key"],
            issue["label"],
            issue["summary"],
            _stable_json({"source": "parliamentary_rollcall_backfill"}),
            now_iso,
            now_iso,
        ),
    )


def _entry_id(row: Any, issue_id: str) -> str:
    seat = _norm(row["seat"]) or str(row["member_vote_id"])
    return f"parl-vote:{row['vote_event_id']}:{seat}:{issue_id}"


def _group_entry_id(*, vote_event_id: str, parliamentary_group_id: int, role: str, issue_id: str) -> str:
    return f"parl-group-vote:{vote_event_id}:{parliamentary_group_id}:{role}:{issue_id}"


def _party_entry_id(*, vote_event_id: str, party_id: int, role: str, issue_id: str) -> str:
    return f"parl-party-vote:{vote_event_id}:{party_id}:{role}:{issue_id}"


def _load_party_labels(conn: Any) -> dict[int, str]:
    return {
        int(row["party_id"]): _norm(row["name"]) or _norm(row["acronym"]) or f"Party {row['party_id']}"
        for row in conn.execute("SELECT party_id, name, acronym FROM parties").fetchall()
    }


def backfill_parliamentary_accountability_ledger(
    conn: Any,
    *,
    vote_source_ids: tuple[str, ...] = DEFAULT_VOTE_SOURCE_IDS,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not vote_source_ids:
        raise ValueError("vote_source_ids cannot be empty")

    placeholders = ",".join("?" for _ in vote_source_ids)
    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    params: list[Any] = list(vote_source_ids)
    if int(limit or 0) > 0:
        params.append(int(limit))

    rows = conn.execute(
        f"""
        SELECT
          mv.member_vote_id,
          mv.vote_event_id,
          mv.seat,
          mv.member_name,
          mv.person_id,
          mv.group_code,
          mv.parliamentary_group_id,
          mv.vote_choice,
          mv.source_id,
          mv.source_url AS member_source_url,
          mv.source_snapshot_date AS member_snapshot_date,
          e.legislature,
          e.vote_date,
          e.title AS vote_title,
          e.source_url AS vote_source_url,
          e.source_record_pk AS vote_source_record_pk,
          e.source_snapshot_date AS vote_snapshot_date,
          vei.initiative_id,
          i.title AS initiative_title,
          i.source_url AS initiative_source_url,
          pg.name AS parliamentary_group_name,
          pg.institution_id AS parliamentary_group_institution_id
        FROM parl_vote_member_votes mv
        JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
        LEFT JOIN parl_vote_event_initiatives vei ON vei.vote_event_id = mv.vote_event_id
        LEFT JOIN parl_initiatives i ON i.initiative_id = vei.initiative_id
        LEFT JOIN parliamentary_groups pg ON pg.parliamentary_group_id = mv.parliamentary_group_id
        WHERE mv.source_id IN ({placeholders})
        ORDER BY mv.vote_event_id, mv.member_vote_id, COALESCE(vei.initiative_id, '')
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()

    stats: dict[str, Any] = {
        "vote_source_ids": list(vote_source_ids),
        "source_rows_seen": len(rows),
        "issues_upserted": 0,
        "entries_upserted": 0,
        "member_entries_upserted": 0,
        "group_entries_upserted": 0,
        "party_entries_upserted": 0,
        "entries_by_role": {},
        "dry_run": bool(dry_run),
    }
    if dry_run:
        for row in rows:
            role = _choice_role(_norm(row["vote_choice"]))
            stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1
        return stats

    now_iso = now_utc_iso()
    seen_issues: set[str] = set()
    issue_labels: dict[str, str] = {}
    group_rollups: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    party_rollups: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    party_labels = _load_party_labels(conn)
    with conn:
        for row in rows:
            issue = _issue_from_row(row)
            issue_labels[issue["issue_id"]] = issue["label"]
            if issue["issue_id"] not in seen_issues:
                _upsert_issue(conn, issue=issue, now_iso=now_iso)
                seen_issues.add(issue["issue_id"])
                stats["issues_upserted"] += 1

            person_id = row["person_id"]
            person_id_int = int(person_id) if person_id is not None else None
            mandate = _resolve_mandate(conn, person_id=person_id_int, vote_date=row["vote_date"])
            actor_label = _norm(row["member_name"]) or _norm(row["group_code"]) or "Unknown parliamentary actor"
            role = _choice_role(_norm(row["vote_choice"]))
            source_url = _norm(row["member_source_url"]) or _norm(row["vote_source_url"]) or _norm(row["initiative_source_url"])
            payload = {
                "source": "parl_vote_member_votes",
                "member_vote_id": row["member_vote_id"],
                "vote_event_id": row["vote_event_id"],
                "initiative_id": row["initiative_id"],
                "vote_choice": row["vote_choice"],
                "seat": row["seat"],
                "group_code": row["group_code"],
                "parliamentary_group_id": row["parliamentary_group_id"],
                "legislature": row["legislature"],
            }
            parliamentary_group_id = row["parliamentary_group_id"]
            if parliamentary_group_id is not None:
                group_key = (issue["issue_id"], _norm(row["vote_event_id"]), int(parliamentary_group_id), role)
                group = group_rollups.setdefault(
                    group_key,
                    {
                        "issue_id": issue["issue_id"],
                        "vote_event_id": _norm(row["vote_event_id"]),
                        "parliamentary_group_id": int(parliamentary_group_id),
                        "parliamentary_group_name": _norm(row["parliamentary_group_name"])
                        or _norm(row["group_code"])
                        or f"Parliamentary group {parliamentary_group_id}",
                        "group_code": _norm(row["group_code"]),
                        "role": role,
                        "vote_choice": _norm(row["vote_choice"]),
                        "vote_count": 0,
                        "vote_title": _norm(row["vote_title"]) or issue["label"],
                        "vote_date": row["vote_date"],
                        "source_id": row["source_id"],
                        "source_url": source_url,
                        "source_record_pk": row["vote_source_record_pk"],
                        "institution_id": row["parliamentary_group_institution_id"],
                        "initiative_id": row["initiative_id"],
                    },
                )
                group["vote_count"] += 1
            party_id = mandate["party_id"]
            if party_id is not None:
                party_id_int = int(party_id)
                party_key = (issue["issue_id"], _norm(row["vote_event_id"]), party_id_int, role)
                party = party_rollups.setdefault(
                    party_key,
                    {
                        "issue_id": issue["issue_id"],
                        "vote_event_id": _norm(row["vote_event_id"]),
                        "party_id": party_id_int,
                        "party_label": party_labels.get(party_id_int, f"party_id:{party_id_int}"),
                        "role": role,
                        "vote_choice": _norm(row["vote_choice"]),
                        "vote_count": 0,
                        "vote_title": _norm(row["vote_title"]) or issue["label"],
                        "vote_date": row["vote_date"],
                        "source_id": row["source_id"],
                        "source_url": source_url,
                        "source_record_pk": row["vote_source_record_pk"],
                        "institution_id": mandate["institution_id"],
                        "initiative_id": row["initiative_id"],
                    },
                )
                party["vote_count"] += 1
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
                  parliamentary_group_id,
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
                  ?, ?, 'parliamentary_action', ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, NULL, NULL,
                  'parl_vote_event', ?, NULL, NULL, NULL,
                  ?, NULL, ?, ?, ?, 1.0, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  person_id = excluded.person_id,
                  party_id = excluded.party_id,
                  parliamentary_group_id = excluded.parliamentary_group_id,
                  mandate_id = excluded.mandate_id,
                  institution_id = excluded.institution_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  event_date = excluded.event_date,
                  title = excluded.title,
                  summary = excluded.summary,
                  accountability_question = excluded.accountability_question,
                  confidence = excluded.confidence,
                  evidence_tier = excluded.evidence_tier,
                  source_id = excluded.source_id,
                  source_title = excluded.source_title,
                  source_url = excluded.source_url,
                  source_locator = excluded.source_locator,
                  source_record_pk = excluded.source_record_pk,
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    _entry_id(row, issue["issue_id"]),
                    issue["issue_id"],
                    role,
                    role,
                    actor_label,
                    "person" if person_id_int is not None else "unknown",
                    person_id_int,
                    mandate["party_id"],
                    row["parliamentary_group_id"],
                    mandate["mandate_id"],
                    mandate["institution_id"],
                    row["vote_event_id"],
                    row["vote_date"],
                    _norm(row["vote_title"]) or issue["label"],
                    f"{actor_label} voted {row['vote_choice']} on {issue['label']}.",
                    "What did this actor vote on this issue?",
                    PRIMARY_RECORD_TIER,
                    row["source_id"],
                    "Official parliamentary roll-call vote",
                    source_url,
                    _norm(row["vote_event_id"]),
                    row["vote_source_record_pk"],
                    _norm(row["vote_choice"]),
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["entries_upserted"] += 1
            stats["member_entries_upserted"] += 1
            stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1

        for group in group_rollups.values():
            role = str(group["role"])
            issue_id = str(group["issue_id"])
            actor_label = str(group["parliamentary_group_name"])
            vote_count = int(group["vote_count"])
            payload = {
                "source": "parl_vote_member_votes_group_rollup",
                "vote_event_id": group["vote_event_id"],
                "initiative_id": group["initiative_id"],
                "parliamentary_group_id": group["parliamentary_group_id"],
                "group_code": group["group_code"],
                "accountability_role": role,
                "vote_choice": group["vote_choice"],
                "vote_count": vote_count,
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
                  parliamentary_group_id,
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
                  ?, ?, 'parliamentary_action', ?, ?, ?, 'group',
                  NULL, NULL, ?, NULL, ?, NULL, NULL,
                  'parl_vote_event', ?, NULL, NULL, NULL,
                  ?, NULL, ?, ?, ?, 1.0, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  parliamentary_group_id = excluded.parliamentary_group_id,
                  institution_id = excluded.institution_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  event_date = excluded.event_date,
                  title = excluded.title,
                  summary = excluded.summary,
                  accountability_question = excluded.accountability_question,
                  confidence = excluded.confidence,
                  evidence_tier = excluded.evidence_tier,
                  source_id = excluded.source_id,
                  source_title = excluded.source_title,
                  source_url = excluded.source_url,
                  source_locator = excluded.source_locator,
                  source_record_pk = excluded.source_record_pk,
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    _group_entry_id(
                        vote_event_id=str(group["vote_event_id"]),
                        parliamentary_group_id=int(group["parliamentary_group_id"]),
                        role=role,
                        issue_id=issue_id,
                    ),
                    issue_id,
                    role,
                    role,
                    actor_label,
                    group["parliamentary_group_id"],
                    group["institution_id"],
                    group["vote_event_id"],
                    group["vote_date"],
                    str(group["vote_title"]),
                    f"{actor_label}: {vote_count} member vote(s) counted as {role} on {issue_labels.get(issue_id, issue_id)}.",
                    "How did this parliamentary group vote on this issue?",
                    PRIMARY_RECORD_TIER,
                    group["source_id"],
                    "Official parliamentary roll-call vote group rollup",
                    group["source_url"],
                    group["vote_event_id"],
                    group["source_record_pk"],
                    f"{vote_count} member vote(s): {group['vote_choice']}",
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["entries_upserted"] += 1
            stats["group_entries_upserted"] += 1
            stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1

        for party in party_rollups.values():
            role = str(party["role"])
            issue_id = str(party["issue_id"])
            actor_label = str(party["party_label"])
            vote_count = int(party["vote_count"])
            payload = {
                "source": "parl_vote_member_votes_party_rollup",
                "vote_event_id": party["vote_event_id"],
                "initiative_id": party["initiative_id"],
                "party_id": party["party_id"],
                "accountability_role": role,
                "vote_choice": party["vote_choice"],
                "vote_count": vote_count,
                "basis": "dated mandate.party_id",
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
                  parliamentary_group_id,
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
                  ?, ?, 'parliamentary_action', ?, ?, ?, 'party',
                  NULL, ?, NULL, NULL, ?, NULL, NULL,
                  'parl_vote_event', ?, NULL, NULL, NULL,
                  ?, NULL, ?, ?, ?, 1.0, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  party_id = excluded.party_id,
                  institution_id = excluded.institution_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  event_date = excluded.event_date,
                  title = excluded.title,
                  summary = excluded.summary,
                  accountability_question = excluded.accountability_question,
                  confidence = excluded.confidence,
                  evidence_tier = excluded.evidence_tier,
                  source_id = excluded.source_id,
                  source_title = excluded.source_title,
                  source_url = excluded.source_url,
                  source_locator = excluded.source_locator,
                  source_record_pk = excluded.source_record_pk,
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    _party_entry_id(
                        vote_event_id=str(party["vote_event_id"]),
                        party_id=int(party["party_id"]),
                        role=role,
                        issue_id=issue_id,
                    ),
                    issue_id,
                    role,
                    role,
                    actor_label,
                    party["party_id"],
                    party["institution_id"],
                    party["vote_event_id"],
                    party["vote_date"],
                    str(party["vote_title"]),
                    f"{actor_label}: {vote_count} source-backed member vote(s) counted as {role} on {issue_labels.get(issue_id, issue_id)}.",
                    "How did this party vote on this issue where member mandates identify party affiliation?",
                    PRIMARY_RECORD_TIER,
                    party["source_id"],
                    "Official parliamentary roll-call vote party rollup",
                    party["source_url"],
                    party["vote_event_id"],
                    party["source_record_pk"],
                    f"{vote_count} mandate-linked member vote(s): {party['vote_choice']}",
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["entries_upserted"] += 1
            stats["party_entries_upserted"] += 1
            stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1
    return stats


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_parliamentary_accountability_ledger(
            conn,
            vote_source_ids=tuple(str(item) for item in args.vote_source_ids),
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK parliamentary accountability ledger "
        + f"(seen={summary['source_rows_seen']} entries={summary['entries_upserted']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
