#!/usr/bin/env python3
"""Export compact actor/issue accountability dossiers from the generic ledger."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from publicdata_publish.sanitize import redact_sensitive_text
from publicdata_sqlite import table_exists


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_OUT = Path("etl/data/published/accountability-dossiers-latest.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export compact accountability actor/issue dossiers")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--snapshot-date", required=True, help="Snapshot date label")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    p.add_argument("--latest-out", default="", help="Optional latest-alias JSON path")
    p.add_argument("--max-actors", type=int, default=5000, help="Max actor dossiers to export; 0 means all")
    p.add_argument("--max-issues", type=int, default=5000, help="Max issue dossiers to export; 0 means all")
    p.add_argument("--max-issues-per-actor", type=int, default=30, help="Max issue summaries per actor")
    p.add_argument("--max-actors-per-issue", type=int, default=50, help="Max actor summaries per issue")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(value: Any) -> str:
    return redact_sensitive_text(str(value or "").strip())


def _date_token(row: Any) -> str:
    return _norm(row["event_date"]) or _norm(row["published_date"])


def _actor_key(row: Any) -> str:
    for field in ("person_id", "party_id", "parliamentary_group_id", "institution_id", "org_unit_id", "position_id"):
        value = row[field]
        if value is not None:
            return f"{field}:{value}"
    return f"{_norm(row['actor_kind']) or 'unknown'}:label:{_norm(row['actor_label']).casefold()}"


def _bump_date(bucket: dict[str, Any], date_token: str) -> None:
    if not date_token:
        return
    if not bucket.get("first_date") or date_token < bucket["first_date"]:
        bucket["first_date"] = date_token
    if not bucket.get("last_date") or date_token > bucket["last_date"]:
        bucket["last_date"] = date_token


def _counter_payload(counter: Counter[str]) -> dict[str, int]:
    return {key: int(value) for key, value in sorted(counter.items())}


def _sorted_values(items: list[dict[str, Any]], *, limit: int, label_key: str) -> list[dict[str, Any]]:
    items.sort(key=lambda item: (-int(item.get("entries_total") or 0), _norm(item.get(label_key))))
    if limit > 0:
        return items[:limit]
    return items


def _compact_actor(actor: dict[str, Any], *, max_issues_per_actor: int) -> dict[str, Any]:
    issue_payloads = []
    for issue in actor["issues"].values():
        issue_payloads.append(
            {
                "issue_id": issue["issue_id"],
                "issue_label": issue["issue_label"],
                "entries_total": int(issue["entries_total"]),
                "roles": _counter_payload(issue["roles"]),
                "entry_kinds": _counter_payload(issue["entry_kinds"]),
                "first_date": issue.get("first_date", ""),
                "last_date": issue.get("last_date", ""),
            }
        )
    payload = {
        "actor_key": actor["actor_key"],
        "actor_label": actor["actor_label"],
        "actor_kind": actor["actor_kind"],
        "person_id": actor.get("person_id"),
        "party_id": actor.get("party_id"),
        "parliamentary_group_id": actor.get("parliamentary_group_id"),
        "mandate_id": actor.get("mandate_id"),
        "institution_id": actor.get("institution_id"),
        "org_unit_id": actor.get("org_unit_id"),
        "position_id": actor.get("position_id"),
        "entries_total": int(actor["entries_total"]),
        "issues_total": len(actor["issues"]),
        "roles": _counter_payload(actor["roles"]),
        "entry_kinds": _counter_payload(actor["entry_kinds"]),
        "first_date": actor.get("first_date", ""),
        "last_date": actor.get("last_date", ""),
        "top_issues": _sorted_values(issue_payloads, limit=max_issues_per_actor, label_key="issue_label"),
    }
    return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


def _compact_issue(issue: dict[str, Any], *, max_actors_per_issue: int) -> dict[str, Any]:
    actor_payloads = []
    for actor in issue["actors"].values():
        actor_payloads.append(
            {
                "actor_key": actor["actor_key"],
                "actor_label": actor["actor_label"],
                "actor_kind": actor["actor_kind"],
                "person_id": actor.get("person_id"),
                "party_id": actor.get("party_id"),
                "parliamentary_group_id": actor.get("parliamentary_group_id"),
                "mandate_id": actor.get("mandate_id"),
                "institution_id": actor.get("institution_id"),
                "org_unit_id": actor.get("org_unit_id"),
                "position_id": actor.get("position_id"),
                "entries_total": int(actor["entries_total"]),
                "roles": _counter_payload(actor["roles"]),
                "entry_kinds": _counter_payload(actor["entry_kinds"]),
                "first_date": actor.get("first_date", ""),
                "last_date": actor.get("last_date", ""),
            }
        )
    payload = {
        "issue_id": issue["issue_id"],
        "label": issue["label"],
        "summary": issue.get("summary", ""),
        "scope": issue.get("scope", ""),
        "issue_status": issue.get("issue_status", ""),
        "entries_total": int(issue["entries_total"]),
        "actors_total": len(issue["actors"]),
        "roles": _counter_payload(issue["roles"]),
        "entry_kinds": _counter_payload(issue["entry_kinds"]),
        "actor_kinds": _counter_payload(issue["actor_kinds"]),
        "first_date": issue.get("first_date", ""),
        "last_date": issue.get("last_date", ""),
        "top_actors": _sorted_values(actor_payloads, limit=max_actors_per_issue, label_key="actor_label"),
    }
    return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


def build_accountability_dossier_snapshot(
    conn: Any,
    *,
    snapshot_date: str,
    max_actors: int = 5000,
    max_issues: int = 5000,
    max_issues_per_actor: int = 30,
    max_actors_per_issue: int = 50,
) -> dict[str, Any]:
    if not table_exists(conn, "accountability_ledger_entries") or not table_exists(conn, "accountability_issues"):
        return {
            "meta": {
                "schema_version": "accountability_dossier_snapshot_v1",
                "generated_at": now_utc_iso(),
                "snapshot_date": snapshot_date,
            },
            "snapshot_date": snapshot_date,
            "coverage": {
                "entries_total": 0,
                "actors_total": 0,
                "issues_total": 0,
                "issue_actor_edges_total": 0,
            },
            "actors": [],
            "issues": [],
        }

    rows = conn.execute(
        """
        SELECT
          e.entry_id,
          e.issue_id,
          i.label AS issue_label,
          i.summary AS issue_summary,
          i.scope AS issue_scope,
          i.issue_status,
          e.entry_kind,
          e.accountability_role,
          e.actor_label,
          e.actor_kind,
          e.person_id,
          e.party_id,
          e.parliamentary_group_id,
          e.mandate_id,
          e.institution_id,
          e.org_unit_id,
          e.position_id,
          e.event_date,
          e.published_date
        FROM accountability_ledger_entries e
        JOIN accountability_issues i ON i.issue_id = e.issue_id
        ORDER BY e.issue_id, e.actor_kind, e.actor_label, e.entry_id
        """
    ).fetchall()

    actors: dict[str, dict[str, Any]] = {}
    issues: dict[str, dict[str, Any]] = {}
    role_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    actor_kind_counts: Counter[str] = Counter()
    id_coverage_counts: Counter[str] = Counter()
    edge_keys: set[tuple[str, str]] = set()

    for row in rows:
        actor_key = _actor_key(row)
        issue_id = _norm(row["issue_id"])
        actor_kind = _norm(row["actor_kind"]) or "unknown"
        role = _norm(row["accountability_role"]) or "unknown"
        entry_kind = _norm(row["entry_kind"]) or "unknown"
        date_token = _date_token(row)
        role_counts[role] += 1
        kind_counts[entry_kind] += 1
        actor_kind_counts[actor_kind] += 1
        edge_keys.add((issue_id, actor_key))
        for field in ("person_id", "party_id", "parliamentary_group_id", "mandate_id", "institution_id", "org_unit_id", "position_id"):
            if row[field] is not None:
                id_coverage_counts[field] += 1

        actor = actors.setdefault(
            actor_key,
            {
                "actor_key": actor_key,
                "actor_label": _norm(row["actor_label"]),
                "actor_kind": actor_kind,
                "person_id": row["person_id"],
                "party_id": row["party_id"],
                "parliamentary_group_id": row["parliamentary_group_id"],
                "mandate_id": row["mandate_id"],
                "institution_id": row["institution_id"],
                "org_unit_id": row["org_unit_id"],
                "position_id": row["position_id"],
                "entries_total": 0,
                "roles": Counter(),
                "entry_kinds": Counter(),
                "issues": {},
                "first_date": "",
                "last_date": "",
            },
        )
        actor["entries_total"] += 1
        actor["roles"][role] += 1
        actor["entry_kinds"][entry_kind] += 1
        _bump_date(actor, date_token)
        actor_issue = actor["issues"].setdefault(
            issue_id,
            {
                "issue_id": issue_id,
                "issue_label": _norm(row["issue_label"]),
                "entries_total": 0,
                "roles": Counter(),
                "entry_kinds": Counter(),
                "first_date": "",
                "last_date": "",
            },
        )
        actor_issue["entries_total"] += 1
        actor_issue["roles"][role] += 1
        actor_issue["entry_kinds"][entry_kind] += 1
        _bump_date(actor_issue, date_token)

        issue = issues.setdefault(
            issue_id,
            {
                "issue_id": issue_id,
                "label": _norm(row["issue_label"]),
                "summary": _norm(row["issue_summary"]),
                "scope": _norm(row["issue_scope"]),
                "issue_status": _norm(row["issue_status"]),
                "entries_total": 0,
                "roles": Counter(),
                "entry_kinds": Counter(),
                "actor_kinds": Counter(),
                "actors": {},
                "first_date": "",
                "last_date": "",
            },
        )
        issue["entries_total"] += 1
        issue["roles"][role] += 1
        issue["entry_kinds"][entry_kind] += 1
        issue["actor_kinds"][actor_kind] += 1
        _bump_date(issue, date_token)
        issue_actor = issue["actors"].setdefault(
            actor_key,
            {
                "actor_key": actor_key,
                "actor_label": _norm(row["actor_label"]),
                "actor_kind": actor_kind,
                "person_id": row["person_id"],
                "party_id": row["party_id"],
                "parliamentary_group_id": row["parliamentary_group_id"],
                "mandate_id": row["mandate_id"],
                "institution_id": row["institution_id"],
                "org_unit_id": row["org_unit_id"],
                "position_id": row["position_id"],
                "entries_total": 0,
                "roles": Counter(),
                "entry_kinds": Counter(),
                "first_date": "",
                "last_date": "",
            },
        )
        issue_actor["entries_total"] += 1
        issue_actor["roles"][role] += 1
        issue_actor["entry_kinds"][entry_kind] += 1
        _bump_date(issue_actor, date_token)

    actor_payloads = [_compact_actor(actor, max_issues_per_actor=max_issues_per_actor) for actor in actors.values()]
    issue_payloads = [_compact_issue(issue, max_actors_per_issue=max_actors_per_issue) for issue in issues.values()]
    actor_payloads = _sorted_values(actor_payloads, limit=max_actors, label_key="actor_label")
    issue_payloads = _sorted_values(issue_payloads, limit=max_issues, label_key="label")

    return {
        "meta": {
            "schema_version": "accountability_dossier_snapshot_v1",
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "max_actors": int(max_actors or 0),
            "max_issues": int(max_issues or 0),
            "max_issues_per_actor": int(max_issues_per_actor or 0),
            "max_actors_per_issue": int(max_actors_per_issue or 0),
        },
        "snapshot_date": snapshot_date,
        "coverage": {
            "entries_total": len(rows),
            "actors_total": len(actors),
            "actors_exported": len(actor_payloads),
            "actors_truncated": bool(max_actors > 0 and len(actors) > len(actor_payloads)),
            "issues_total": len(issues),
            "issues_exported": len(issue_payloads),
            "issues_truncated": bool(max_issues > 0 and len(issues) > len(issue_payloads)),
            "issue_actor_edges_total": len(edge_keys),
            "entries_with_person_id": int(id_coverage_counts["person_id"]),
            "entries_with_party_id": int(id_coverage_counts["party_id"]),
            "entries_with_parliamentary_group_id": int(id_coverage_counts["parliamentary_group_id"]),
            "entries_with_mandate_id": int(id_coverage_counts["mandate_id"]),
            "entries_with_institution_id": int(id_coverage_counts["institution_id"]),
            "entries_with_org_unit_id": int(id_coverage_counts["org_unit_id"]),
            "entries_with_position_id": int(id_coverage_counts["position_id"]),
            "entries_by_role": _counter_payload(role_counts),
            "entries_by_kind": _counter_payload(kind_counts),
            "entries_by_actor_kind": _counter_payload(actor_kind_counts),
        },
        "actors": actor_payloads,
        "issues": issue_payloads,
    }


def main() -> int:
    args = parse_args()
    with closing(open_db(Path(args.db))) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        snapshot = build_accountability_dossier_snapshot(
            conn,
            snapshot_date=str(args.snapshot_date),
            max_actors=int(args.max_actors or 0),
            max_issues=int(args.max_issues or 0),
            max_issues_per_actor=int(args.max_issues_per_actor or 0),
            max_actors_per_issue=int(args.max_actors_per_issue or 0),
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    latest_out = str(args.latest_out or "").strip()
    if latest_out:
        latest_path = Path(latest_out)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(payload, encoding="utf-8")
    print(
        "OK accountability dossier snapshot -> "
        + str(out_path)
        + f" (actors={snapshot['coverage']['actors_total']} issues={snapshot['coverage']['issues_total']} "
        + f"entries={snapshot['coverage']['entries_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
