#!/usr/bin/env python3
"""Export unresolved actor-label queue for the generic accountability ledger."""

from __future__ import annotations

import argparse
import csv
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
from publicdata_publish.sanitize import redact_sensitive_text, sanitize_url_for_public
from publicdata_sqlite import table_exists


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/accountability_actor_resolution_queue_latest.json")
DEFAULT_CSV_OUT = Path("docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/accountability_actor_resolution_queue_latest.csv")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export accountability actor-resolution queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--snapshot-date", required=True, help="Snapshot date label")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="JSON summary output")
    p.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT), help="CSV queue output")
    p.add_argument("--limit", type=int, default=0, help="Max queue rows; 0 means all")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(value: Any) -> str:
    return redact_sensitive_text(str(value or "").strip())


def _safe_url(value: Any) -> str:
    return sanitize_url_for_public(str(value or "").strip())


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _is_unresolved(row: Any) -> bool:
    return all(
        row[field] is None
        for field in ("person_id", "party_id", "parliamentary_group_id", "institution_id", "org_unit_id", "position_id")
    )


def _priority(row: dict[str, Any]) -> int:
    entries = int(row.get("unresolved_entries") or 0)
    if entries >= 100:
        return 100
    if entries >= 25:
        return 80
    if entries >= 5:
        return 60
    return 40


def build_actor_resolution_queue(conn: Any, *, snapshot_date: str, limit: int = 0) -> dict[str, Any]:
    if not table_exists(conn, "accountability_ledger_entries"):
        return {
            "meta": {
                "schema_version": "accountability_actor_resolution_queue_v1",
                "generated_at": now_utc_iso(),
                "snapshot_date": snapshot_date,
            },
            "coverage": {
                "entries_total": 0,
                "unresolved_entries_total": 0,
                "resolved_entries_total": 0,
                "unresolved_actor_labels_total": 0,
                "resolution_pct": 1.0,
            },
            "queue": [],
        }

    rows = conn.execute(
        """
        SELECT
          entry_id,
          issue_id,
          entry_kind,
          accountability_role,
          actor_label,
          actor_kind,
          person_id,
          party_id,
          parliamentary_group_id,
          institution_id,
          org_unit_id,
          position_id,
          event_date,
          published_date,
          title,
          source_id,
          source_url,
          source_locator
        FROM accountability_ledger_entries
        ORDER BY actor_label, entry_id
        """
    ).fetchall()

    entries_total = len(rows)
    unresolved_rows = [row for row in rows if _is_unresolved(row)]
    resolved_entries_total = entries_total - len(unresolved_rows)

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in unresolved_rows:
        actor_label = _norm(row["actor_label"])
        actor_kind = _norm(row["actor_kind"]) or "unknown"
        key = (actor_label.casefold(), actor_kind)
        item = grouped.setdefault(
            key,
            {
                "actor_label": actor_label,
                "actor_kind": actor_kind,
                "unresolved_entries": 0,
                "issues": set(),
                "entry_kinds": Counter(),
                "roles": Counter(),
                "source_ids": Counter(),
                "first_date": "",
                "last_date": "",
                "sample_entries": [],
                "sample_source_urls": [],
            },
        )
        item["unresolved_entries"] += 1
        item["issues"].add(_norm(row["issue_id"]))
        item["entry_kinds"][_norm(row["entry_kind"]) or "unknown"] += 1
        item["roles"][_norm(row["accountability_role"]) or "unknown"] += 1
        if _norm(row["source_id"]):
            item["source_ids"][_norm(row["source_id"])] += 1
        date_token = _norm(row["event_date"]) or _norm(row["published_date"])
        if date_token and (not item["first_date"] or date_token < item["first_date"]):
            item["first_date"] = date_token
        if date_token and (not item["last_date"] or date_token > item["last_date"]):
            item["last_date"] = date_token
        if len(item["sample_entries"]) < 5:
            sample = {
                "entry_id": _norm(row["entry_id"]),
                "issue_id": _norm(row["issue_id"]),
                "entry_kind": _norm(row["entry_kind"]),
                "accountability_role": _norm(row["accountability_role"]),
                "title": _norm(row["title"]),
                "source_locator": _norm(row["source_locator"]),
            }
            item["sample_entries"].append({k: v for k, v in sample.items() if v})
        safe_url = _safe_url(row["source_url"])
        if safe_url and safe_url not in item["sample_source_urls"] and len(item["sample_source_urls"]) < 5:
            item["sample_source_urls"].append(safe_url)

    queue_rows: list[dict[str, Any]] = []
    for item in grouped.values():
        issues = sorted(issue for issue in item["issues"] if issue)
        row = {
            "actor_label": item["actor_label"],
            "actor_kind": item["actor_kind"],
            "unresolved_entries": int(item["unresolved_entries"]),
            "issues_total": len(issues),
            "entry_kinds": dict(sorted(item["entry_kinds"].items())),
            "roles": dict(sorted(item["roles"].items())),
            "source_ids": dict(sorted(item["source_ids"].items())),
            "first_date": item["first_date"],
            "last_date": item["last_date"],
            "sample_issue_ids": issues[:5],
            "sample_entries": item["sample_entries"],
            "sample_source_urls": item["sample_source_urls"],
            "next_action": "map_actor_label_to_person_party_group_institution_or_alias",
        }
        row["priority"] = _priority(row)
        queue_rows.append(row)

    queue_rows.sort(key=lambda row: (-int(row["priority"]), -int(row["unresolved_entries"]), row["actor_label"]))
    if limit > 0:
        queue_rows = queue_rows[: int(limit)]

    resolution_pct = 1.0
    if entries_total:
        resolution_pct = round(resolved_entries_total / entries_total, 6)

    return {
        "meta": {
            "schema_version": "accountability_actor_resolution_queue_v1",
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "limit": int(limit or 0),
        },
        "coverage": {
            "entries_total": entries_total,
            "unresolved_entries_total": len(unresolved_rows),
            "resolved_entries_total": resolved_entries_total,
            "unresolved_actor_labels_total": len(grouped),
            "queue_rows_total": len(queue_rows),
            "queue_truncated": bool(limit > 0 and len(grouped) > len(queue_rows)),
            "resolution_pct": resolution_pct,
        },
        "queue": queue_rows,
    }


def write_csv(path: Path, queue_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "priority",
        "actor_label",
        "actor_kind",
        "unresolved_entries",
        "issues_total",
        "first_date",
        "last_date",
        "roles",
        "entry_kinds",
        "source_ids",
        "sample_issue_ids",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in queue_rows:
            writer.writerow(
                {
                    field: _json_cell(row[field]) if isinstance(row.get(field), (dict, list)) else row.get(field, "")
                    for field in fields
                }
            )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with closing(open_db(db_path)) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        payload = build_actor_resolution_queue(conn, snapshot_date=str(args.snapshot_date), limit=int(args.limit or 0))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if str(args.csv_out or "").strip():
        write_csv(Path(args.csv_out), list(payload["queue"]))
    coverage = payload["coverage"]
    print(
        "OK accountability actor resolution queue -> "
        + str(out_path)
        + f" (unresolved_labels={coverage['unresolved_actor_labels_total']} "
        + f"unresolved_entries={coverage['unresolved_entries_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
