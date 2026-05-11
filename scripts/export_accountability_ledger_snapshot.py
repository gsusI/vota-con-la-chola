#!/usr/bin/env python3
"""Export generic issue-led accountability ledger JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from publicdata_sqlite import table_exists
from publicdata_publish.sanitize import redact_sensitive_text, sanitize_url_for_public


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_OUT = Path("etl/data/published/accountability-ledger-latest.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export issue-led accountability ledger JSON")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--snapshot-date", required=True, help="Snapshot date label")
    p.add_argument("--issue-id", default="", help="Optional single issue_id")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    p.add_argument("--latest-out", default="", help="Optional latest-alias JSON path")
    p.add_argument(
        "--max-entries-per-issue",
        type=int,
        default=0,
        help="Max evidence entries exported per issue; 0 means all. Coverage counts remain full.",
    )
    p.add_argument(
        "--max-sample-entries-per-actor",
        type=int,
        default=5,
        help="Max actor-level sample entries exported; 0 disables actor samples. Coverage counts remain full.",
    )
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_row(row: Any, fields: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in fields:
        value = row[field]
        if value is None:
            continue
        if field.endswith("_url"):
            value = sanitize_url_for_public(str(value))
            if not value:
                continue
        elif isinstance(value, str):
            value = redact_sensitive_text(value)
        payload[field] = value
    return payload


def _actor_key(entry: dict[str, Any]) -> str:
    for field in ("person_id", "party_id", "parliamentary_group_id", "institution_id", "org_unit_id", "position_id"):
        value = entry.get(field)
        if value not in (None, ""):
            return f"{field}:{value}"
    actor_kind = str(entry.get("actor_kind") or "unknown").strip() or "unknown"
    actor_label = str(entry.get("actor_label") or "").strip().casefold()
    return f"{actor_kind}:label:{actor_label}"


def _date_token(entry: dict[str, Any]) -> str:
    return str(entry.get("event_date") or entry.get("published_date") or "").strip()


def _register_actor_entry(
    actor_index: MutableMapping[str, dict[str, Any]],
    *,
    issue: dict[str, Any],
    entry: dict[str, Any],
    max_sample_entries_per_actor: int = 5,
) -> None:
    actor_key = _actor_key(entry)
    actor = actor_index.setdefault(
        actor_key,
        {
            "actor_key": actor_key,
            "actor_label": entry.get("actor_label") or "",
            "actor_kind": entry.get("actor_kind") or "unknown",
            "person_id": entry.get("person_id"),
            "party_id": entry.get("party_id"),
            "parliamentary_group_id": entry.get("parliamentary_group_id"),
            "institution_id": entry.get("institution_id"),
            "org_unit_id": entry.get("org_unit_id"),
            "position_id": entry.get("position_id"),
            "entries_total": 0,
            "issues_total": 0,
            "issues": set(),
            "roles": Counter(),
            "entry_kinds": Counter(),
            "evidence_tiers": Counter(),
            "first_date": "",
            "last_date": "",
            "sample_entries": [],
        },
    )
    actor["entries_total"] += 1
    actor["issues"].add(issue.get("issue_id") or "")
    actor["issues_total"] = len([item for item in actor["issues"] if item])
    actor["roles"][str(entry.get("accountability_role") or "unknown")] += 1
    actor["entry_kinds"][str(entry.get("entry_kind") or "unknown")] += 1
    if entry.get("evidence_tier") not in (None, ""):
        actor["evidence_tiers"][str(entry.get("evidence_tier"))] += 1
    date_token = _date_token(entry)
    if date_token and (not actor["first_date"] or date_token < actor["first_date"]):
        actor["first_date"] = date_token
    if date_token and (not actor["last_date"] or date_token > actor["last_date"]):
        actor["last_date"] = date_token
    if int(max_sample_entries_per_actor or 0) > 0 and len(actor["sample_entries"]) < int(
        max_sample_entries_per_actor
    ):
        sample = {
            "issue_id": issue.get("issue_id"),
            "issue_label": issue.get("label"),
            "entry_id": entry.get("entry_id"),
            "entry_kind": entry.get("entry_kind"),
            "accountability_role": entry.get("accountability_role"),
            "actor_label": entry.get("actor_label"),
            "event_date": entry.get("event_date"),
            "published_date": entry.get("published_date"),
            "title": entry.get("title"),
            "summary": entry.get("summary"),
            "evidence_tier": entry.get("evidence_tier"),
            "source_title": entry.get("source_title"),
            "source_url": entry.get("source_url"),
            "source_locator": entry.get("source_locator"),
            "evidence_quote": entry.get("evidence_quote"),
        }
        actor["sample_entries"].append(
            {key: value for key, value in sample.items() if value not in (None, "")}
        )


def _actor_payloads(actor_index: MutableMapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    actors: list[dict[str, Any]] = []
    for actor in actor_index.values():
        payload = {
            key: value
            for key, value in actor.items()
            if key not in {"issues", "roles", "entry_kinds", "evidence_tiers"}
            and value not in (None, "", {}, [])
        }
        payload["roles"] = dict(sorted(actor["roles"].items()))
        payload["entry_kinds"] = dict(sorted(actor["entry_kinds"].items()))
        payload["evidence_tiers"] = dict(sorted(actor["evidence_tiers"].items()))
        actors.append(payload)
    actors.sort(key=lambda item: (-int(item.get("entries_total") or 0), str(item.get("actor_label") or "")))
    return actors


def build_accountability_ledger_snapshot(
    conn: Any,
    *,
    snapshot_date: str,
    issue_id: str = "",
    max_entries_per_issue: int = 0,
    max_sample_entries_per_actor: int = 5,
) -> dict[str, Any]:
    if not table_exists(conn, "accountability_issues") or not table_exists(conn, "accountability_ledger_entries"):
        return {
            "meta": {
                "schema_version": "accountability_ledger_snapshot_v1",
                "generated_at": now_utc_iso(),
                "snapshot_date": snapshot_date,
                "issue_id": issue_id,
            },
            "snapshot_date": snapshot_date,
            "coverage": {
                "issues_total": 0,
                "entries_total": 0,
                "actors_total": 0,
                "entries_with_resolved_actor_id": 0,
                "entries_with_person_id": 0,
                "entries_with_party_id": 0,
                "entries_with_parliamentary_group_id": 0,
                "entries_with_mandate_id": 0,
                "entries_with_institution_id": 0,
                "entries_with_org_unit_id": 0,
                "entries_with_position_id": 0,
                "entries_by_role": {},
                "entries_by_kind": {},
                "entries_exported": 0,
                "entries_truncated": False,
            },
            "issues": [],
        }

    issue_params: tuple[Any, ...]
    issue_where = ""
    if issue_id:
        issue_where = "WHERE i.issue_id = ?"
        issue_params = (issue_id,)
    else:
        issue_params = ()

    issue_rows = conn.execute(
        f"""
        SELECT
          i.issue_id,
          i.case_id,
          i.canonical_key,
          i.label,
          i.summary,
          i.scope,
          i.issue_status,
          i.source_kind,
          i.updated_at
        FROM accountability_issues i
        {issue_where}
        ORDER BY i.label, i.issue_id
        """,
        issue_params,
    ).fetchall()

    issues: list[dict[str, Any]] = []
    actor_index: dict[str, dict[str, Any]] = {}
    role_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    actor_kind_counts: Counter[str] = Counter()
    entries_total = 0
    entries_exported = 0
    issues_truncated = 0
    entries_with_resolved_actor_id = 0
    id_coverage_fields = (
        "person_id",
        "party_id",
        "parliamentary_group_id",
        "mandate_id",
        "institution_id",
        "org_unit_id",
        "position_id",
    )
    id_coverage_counts: Counter[str] = Counter()
    entry_fields = [
        "entry_id",
        "entry_kind",
        "accountability_role",
        "role_in_chain",
        "actor_label",
        "actor_kind",
        "person_id",
        "party_id",
        "parliamentary_group_id",
        "mandate_id",
        "institution_id",
        "org_unit_id",
        "position_id",
        "linked_object_type",
        "linked_object_id",
        "event_date",
        "published_date",
        "title",
        "summary",
        "accountability_question",
        "confidence",
        "evidence_tier",
        "source_id",
        "source_title",
        "source_url",
        "source_locator",
        "evidence_quote",
    ]
    for issue_row in issue_rows:
        entries = conn.execute(
            """
            SELECT
              entry_id,
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
              evidence_quote
            FROM accountability_ledger_entries
            WHERE issue_id = ?
            ORDER BY
              COALESCE(event_date, published_date, ''),
              actor_label,
              entry_id
            """,
            (issue_row["issue_id"],),
        ).fetchall()
        entry_payloads_all = [_clean_row(row, entry_fields) for row in entries]
        if int(max_entries_per_issue or 0) > 0:
            entry_payloads = entry_payloads_all[: int(max_entries_per_issue)]
        else:
            entry_payloads = entry_payloads_all
        entries_exported += len(entry_payloads)
        entry_payloads_truncated = len(entry_payloads_all) > len(entry_payloads)
        if entry_payloads_truncated:
            issues_truncated += 1
        for entry in entry_payloads_all:
            entries_total += 1
            role_counts[str(entry.get("accountability_role") or "unknown")] += 1
            kind_counts[str(entry.get("entry_kind") or "unknown")] += 1
            actor_kind_counts[str(entry.get("actor_kind") or "unknown")] += 1
            if any(
                entry.get(field) not in (None, "")
                for field in (
                    "person_id",
                    "party_id",
                    "parliamentary_group_id",
                    "institution_id",
                    "org_unit_id",
                    "position_id",
                )
            ):
                entries_with_resolved_actor_id += 1
            for field in id_coverage_fields:
                if entry.get(field) not in (None, ""):
                    id_coverage_counts[field] += 1
            _register_actor_entry(
                actor_index,
                issue=_clean_row(issue_row, ["issue_id", "label"]),
                entry=entry,
                max_sample_entries_per_actor=int(max_sample_entries_per_actor or 0),
            )
        issues.append(
            {
                **_clean_row(
                    issue_row,
                    [
                        "issue_id",
                        "case_id",
                        "canonical_key",
                        "label",
                        "summary",
                        "scope",
                        "issue_status",
                        "source_kind",
                        "updated_at",
                    ],
                ),
                "entries_total": len(entry_payloads_all),
                "entries_exported": len(entry_payloads),
                "entries_truncated": entry_payloads_truncated,
                "entries": entry_payloads,
            }
        )
    actors = _actor_payloads(actor_index)

    return {
        "meta": {
            "schema_version": "accountability_ledger_snapshot_v1",
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "issue_id": issue_id,
            "max_entries_per_issue": int(max_entries_per_issue or 0),
            "max_sample_entries_per_actor": int(max_sample_entries_per_actor or 0),
        },
        "snapshot_date": snapshot_date,
        "coverage": {
            "issues_total": len(issues),
            "entries_total": entries_total,
            "entries_exported": entries_exported,
            "entries_truncated": bool(issues_truncated),
            "issues_with_truncated_entries": int(issues_truncated),
            "actors_total": len(actors),
            "entries_with_resolved_actor_id": entries_with_resolved_actor_id,
            "entries_with_person_id": int(id_coverage_counts["person_id"]),
            "entries_with_party_id": int(id_coverage_counts["party_id"]),
            "entries_with_parliamentary_group_id": int(id_coverage_counts["parliamentary_group_id"]),
            "entries_with_mandate_id": int(id_coverage_counts["mandate_id"]),
            "entries_with_institution_id": int(id_coverage_counts["institution_id"]),
            "entries_with_org_unit_id": int(id_coverage_counts["org_unit_id"]),
            "entries_with_position_id": int(id_coverage_counts["position_id"]),
            "entries_by_role": dict(sorted(role_counts.items())),
            "entries_by_kind": dict(sorted(kind_counts.items())),
            "entries_by_actor_kind": dict(sorted(actor_kind_counts.items())),
        },
        "actors": actors,
        "issues": issues,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    with closing(open_db(db_path)) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        snapshot = build_accountability_ledger_snapshot(
            conn,
            snapshot_date=str(args.snapshot_date),
            issue_id=str(args.issue_id or ""),
            max_entries_per_issue=int(args.max_entries_per_issue or 0),
            max_sample_entries_per_actor=int(args.max_sample_entries_per_actor or 0),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    latest_out = str(args.latest_out or "").strip()
    if latest_out:
        latest_path = Path(latest_out)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(payload, encoding="utf-8")
    print(
        "OK accountability ledger snapshot -> "
        + str(out_path)
        + f" (issues={snapshot['coverage']['issues_total']} entries={snapshot['coverage']['entries_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
