#!/usr/bin/env python3
"""Backfill generic accountability ledger entries from legal responsibility edges."""

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
from etl.politicos_es.db import apply_schema, open_db, upsert_institution
from etl.politicos_es.util import normalize_ws, now_utc_iso
from scripts.accountability_evidence_tiers import infer_accountability_evidence_tier


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill accountability ledger from legal responsibility edges")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--limit", type=int, default=0, help="Optional max responsibility rows to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


ROLE_MAP = {
    "propose": "proposed",
    "approve": "approved",
    "delegate": "delegated_to",
    "enforce": "enforced",
    "audit": "audited",
}

ENTRY_KIND_BY_ROLE = {
    "propose": "rule",
    "approve": "rule",
    "delegate": "implementation",
    "enforce": "enforcement",
    "audit": "audit",
}


def _actor_kind_for_ids(*, person_id: Any, institution_id: Any) -> str:
    if person_id is not None:
        return "person"
    if institution_id is not None:
        return "institution"
    return "unknown"


def _resolve_legal_institution_id(
    conn: Any,
    *,
    row: Any,
    now_iso: str,
    institution_cache: dict[tuple[str, str], int],
) -> int | None:
    if row["institution_id"] is not None:
        return int(row["institution_id"])
    if row["person_id"] is not None:
        return None
    actor_label = _norm(row["actor_label"])
    if not actor_label:
        return None
    level = _norm(row["norm_scope"]) or "nacional"
    cache_key = (actor_label, level)
    if cache_key not in institution_cache:
        institution_cache[cache_key] = upsert_institution(
            conn,
            actor_label,
            level,
            "",
            None,
            None,
            now_iso,
        )
    institution_id = institution_cache[cache_key]
    conn.execute(
        """
        UPDATE legal_fragment_responsibilities
        SET institution_id = COALESCE(institution_id, ?),
            updated_at = ?
        WHERE responsibility_id = ?
          AND person_id IS NULL
        """,
        (institution_id, now_iso, row["responsibility_id"]),
    )
    return institution_id


def _upsert_issue(conn: Any, *, row: Any, now_iso: str) -> str:
    issue_id = f"legal-norm:{row['norm_id']}"
    label = _norm(row["norm_title"]) or _norm(row["norm_id"])
    summary_parts = [_norm(row["fragment_label"]), _norm(row["fragment_title"])]
    summary = " / ".join(part for part in summary_parts if part) or "Legal norm accountability issue."
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
        ) VALUES (?, NULL, ?, ?, ?, ?, NULL, NULL, 'active', 'derived', ?, ?, ?)
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
            issue_id,
            issue_id,
            label,
            summary,
            _norm(row["norm_scope"]) or "nacional",
            _stable_json(
                {
                    "source": "legal_fragment_responsibilities",
                    "norm_id": row["norm_id"],
                }
            ),
            now_iso,
            now_iso,
        ),
    )
    return issue_id


def backfill_legal_responsibility_accountability_ledger(
    conn: Any,
    *,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    params: tuple[Any, ...] = (int(limit),) if int(limit or 0) > 0 else ()
    rows = conn.execute(
        f"""
        SELECT
          r.responsibility_id,
          r.fragment_id,
          r.role,
          r.person_id,
          r.institution_id,
          r.actor_label,
          r.evidence_date,
          r.source_id,
          r.source_url,
          r.source_record_pk,
          r.evidence_quote,
          f.norm_id,
          f.fragment_label,
          f.fragment_title,
          f.source_url AS fragment_source_url,
          n.title AS norm_title,
          n.scope AS norm_scope,
          n.published_date,
          n.source_url AS norm_source_url
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY n.norm_id, f.fragment_order, r.role, r.responsibility_id
        {limit_sql}
        """,
        params,
    ).fetchall()
    stats: dict[str, Any] = {
        "source_rows_seen": len(rows),
        "issues_upserted": 0,
        "entries_upserted": 0,
        "institution_stubs_upserted": 0,
        "entries_by_role": {},
        "dry_run": bool(dry_run),
    }
    for row in rows:
        role = ROLE_MAP.get(_norm(row["role"]), "unknown")
        stats["entries_by_role"][role] = int(stats["entries_by_role"].get(role, 0)) + 1
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    seen_issues: set[str] = set()
    institution_cache: dict[tuple[str, str], int] = {}
    with conn:
        for row in rows:
            role_raw = _norm(row["role"])
            issue_id = _upsert_issue(conn, row=row, now_iso=now_iso)
            if issue_id not in seen_issues:
                seen_issues.add(issue_id)
                stats["issues_upserted"] += 1
            actor_label = _norm(row["actor_label"]) or "Unknown legal responsibility actor"
            title = _norm(row["fragment_title"]) or _norm(row["fragment_label"]) or _norm(row["norm_title"])
            source_url = _norm(row["source_url"]) or _norm(row["fragment_source_url"]) or _norm(row["norm_source_url"])
            source_title = _norm(row["norm_title"])
            evidence_tier = infer_accountability_evidence_tier(
                source_id=_norm(row["source_id"]),
                source_url=source_url,
                source_title=source_title,
            )
            payload = {
                "source": "legal_fragment_responsibilities",
                "responsibility_id": row["responsibility_id"],
                "fragment_id": row["fragment_id"],
                "norm_id": row["norm_id"],
                "role": role_raw,
            }
            institution_id = _resolve_legal_institution_id(
                conn,
                row=row,
                now_iso=now_iso,
                institution_cache=institution_cache,
            )
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
                  ?, NULL, NULL, ?, NULL, NULL,
                  'legal_norm_fragment', ?, NULL, NULL, ?,
                  ?, ?, ?, ?, ?, NULL, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  entry_kind = excluded.entry_kind,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  person_id = excluded.person_id,
                  institution_id = excluded.institution_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  legal_fragment_id = excluded.legal_fragment_id,
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
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    f"legal-responsibility:{row['responsibility_id']}",
                    issue_id,
                    ENTRY_KIND_BY_ROLE.get(role_raw, "other"),
                    ROLE_MAP.get(role_raw, "unknown"),
                    role_raw,
                    actor_label,
                    _actor_kind_for_ids(person_id=row["person_id"], institution_id=institution_id),
                    row["person_id"],
                    institution_id,
                    row["fragment_id"],
                    row["fragment_id"],
                    row["evidence_date"],
                    row["published_date"],
                    title,
                    f"{actor_label} has role {role_raw} for {title}.",
                    "Who is responsible for this legal fragment?",
                    evidence_tier,
                    row["source_id"],
                    source_title,
                    source_url,
                    _norm(row["fragment_label"]),
                    row["source_record_pk"],
                    _norm(row["evidence_quote"]),
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["entries_upserted"] += 1
    stats["institution_stubs_upserted"] = len(institution_cache)
    return stats


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_legal_responsibility_accountability_ledger(
            conn,
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK legal responsibility accountability ledger "
        + f"(seen={summary['source_rows_seen']} entries={summary['entries_upserted']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
