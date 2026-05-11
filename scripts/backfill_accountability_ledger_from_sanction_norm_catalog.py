#!/usr/bin/env python3
"""Backfill accountability ledger entries from sanction norm competent-body catalog rows."""

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
from etl.politicos_es.db import apply_schema, open_db, upsert_institution
from etl.politicos_es.util import normalize_ws, now_utc_iso
from publicdata_sqlite import table_exists
from scripts.accountability_evidence_tiers import infer_accountability_evidence_tier


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill accountability ledger from sanction norm catalog")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--limit", type=int, default=0, help="Optional max sanction norm fragments to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _source_id_or_none(conn: Any, value: Any) -> str | None:
    source_id = _norm(value)
    if not source_id:
        return None
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return source_id if row is not None else None


def _upsert_issue(conn: Any, *, row: Any, now_iso: str) -> str:
    issue_id = f"legal-norm:{row['norm_id']}"
    label = _norm(row["norm_title"]) or _norm(row["norm_id"])
    summary_parts = [_norm(row["fragment_label"]), _norm(row["fragment_title"])]
    summary = " / ".join(part for part in summary_parts if part) or "Sanction norm accountability issue."
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
            _norm(row["scope"]) or "nacional",
            _stable_json({"source": "sanction_norm_catalog", "norm_id": row["norm_id"]}),
            now_iso,
            now_iso,
        ),
    )
    return issue_id


def _resolve_competent_body_id(
    conn: Any,
    *,
    actor_label: str,
    scope: str,
    now_iso: str,
    institution_cache: dict[tuple[str, str], int],
) -> int | None:
    label = _norm(actor_label)
    if not label:
        return None
    level = _norm(scope) or "nacional"
    cache_key = (label, level)
    if cache_key not in institution_cache:
        institution_cache[cache_key] = upsert_institution(
            conn,
            label,
            level,
            "",
            None,
            None,
            now_iso,
        )
    return institution_cache[cache_key]


def backfill_sanction_norm_catalog_accountability_ledger(
    conn: Any,
    *,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    required_tables = (
        "sanction_norm_catalog",
        "sanction_norm_fragment_links",
        "legal_norms",
        "legal_norm_fragments",
    )
    if any(not table_exists(conn, table_name) for table_name in required_tables):
        return {
            "source_rows_seen": 0,
            "issues_upserted": 0,
            "entries_upserted": 0,
            "institution_stubs_upserted": 0,
            "dry_run": bool(dry_run),
        }

    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    params: tuple[Any, ...] = (int(limit),) if int(limit or 0) > 0 else ()
    rows = conn.execute(
        f"""
        SELECT
          c.norm_id,
          c.scope,
          c.organismo_competente,
          c.source_id,
          c.source_url AS catalog_source_url,
          n.title AS norm_title,
          n.published_date,
          n.source_url AS norm_source_url,
          rd.responsibility_evidence_date,
          l.fragment_id,
          f.fragment_label,
          f.fragment_title,
          f.source_url AS fragment_source_url
        FROM sanction_norm_catalog c
        JOIN sanction_norm_fragment_links l ON l.norm_id = c.norm_id
        JOIN legal_norms n ON n.norm_id = c.norm_id
        JOIN legal_norm_fragments f ON f.fragment_id = l.fragment_id
        LEFT JOIN (
          SELECT fragment_id, MIN(evidence_date) AS responsibility_evidence_date
          FROM legal_fragment_responsibilities
          WHERE TRIM(COALESCE(evidence_date, '')) <> ''
          GROUP BY fragment_id
        ) rd ON rd.fragment_id = l.fragment_id
        WHERE TRIM(COALESCE(c.organismo_competente, '')) <> ''
        ORDER BY c.norm_id, l.fragment_id
        {limit_sql}
        """,
        params,
    ).fetchall()
    stats: dict[str, Any] = {
        "source_rows_seen": len(rows),
        "issues_upserted": 0,
        "entries_upserted": 0,
        "institution_stubs_upserted": 0,
        "entries_by_role": {"current_owner": len(rows)},
        "dry_run": bool(dry_run),
    }
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    seen_issues: set[str] = set()
    institution_cache: dict[tuple[str, str], int] = {}
    with conn:
        for row in rows:
            issue_id = _upsert_issue(conn, row=row, now_iso=now_iso)
            if issue_id not in seen_issues:
                seen_issues.add(issue_id)
                stats["issues_upserted"] += 1

            actor_label = _norm(row["organismo_competente"])
            institution_id = _resolve_competent_body_id(
                conn,
                actor_label=actor_label,
                scope=_norm(row["scope"]),
                now_iso=now_iso,
                institution_cache=institution_cache,
            )
            source_url = (
                _norm(row["fragment_source_url"])
                or _norm(row["catalog_source_url"])
                or _norm(row["norm_source_url"])
            )
            source_id = _source_id_or_none(conn, row["source_id"])
            fragment_title = _norm(row["fragment_title"]) or _norm(row["fragment_label"]) or _norm(row["norm_title"])
            evidence_quote = f"Competent sanction body: {actor_label}. Fragment: {fragment_title}."
            payload = {
                "source": "sanction_norm_catalog",
                "norm_id": row["norm_id"],
                "fragment_id": row["fragment_id"],
                "role": "current_owner",
                "organismo_competente": actor_label,
            }
            evidence_date = _norm(row["published_date"]) or _norm(row["responsibility_evidence_date"])
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
                  ?, ?, 'enforcement', 'current_owner', 'competent_body',
                  ?, 'institution',
                  NULL, NULL, NULL, ?, NULL, NULL,
                  'sanction_norm_fragment', ?, NULL, NULL, ?,
                  ?, ?, ?, ?, ?, NULL, ?,
                  ?, ?, ?, ?, NULL, ?, ?, ?, ?
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
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    f"sanction-norm-current-owner:{row['fragment_id']}",
                    issue_id,
                    actor_label,
                    institution_id,
                    row["fragment_id"],
                    row["fragment_id"],
                    evidence_date,
                    evidence_date,
                    fragment_title,
                    f"{actor_label} is the competent body for {fragment_title}.",
                    "Which body currently owns enforcement for this sanction norm fragment?",
                    infer_accountability_evidence_tier(
                        source_id=source_id or _norm(row["source_id"]),
                        source_url=source_url,
                        source_title=_norm(row["norm_title"]),
                    ),
                    source_id,
                    _norm(row["norm_title"]),
                    source_url,
                    _norm(row["fragment_label"]),
                    evidence_quote,
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
        summary = backfill_sanction_norm_catalog_accountability_ledger(
            conn,
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK sanction-norm accountability ledger "
        + f"(seen={summary['source_rows_seen']} entries={summary['entries_upserted']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
