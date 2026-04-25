#!/usr/bin/env python3
"""Apply reviewed responsibility-ledger rows into normalized SQLite tables."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso


DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_IN_DIR = Path("etl/data/manual/responsibility_explainer/reviewed_ledger_batches")
ALLOWED_LEDGER_KINDS = {
    "warning_timeline_event",
    "governing_rule",
    "official_finding",
    "administrative_act",
    "responsibility_link",
}
ALLOWED_REVIEW_STATUS = {"approved", "applied", "rejected", "ignored", "pending"}

REVIEW_HEADERS = [
    "case_id",
    "ledger_kind",
    "row_id",
    "review_status",
    "sort_order",
    "reviewer",
    "review_note",
    "channel_id",
    "channel_name",
    "operator",
    "event_time",
    "event_precision",
    "signal_level",
    "event_summary",
    "why_it_matters",
    "rule_kind",
    "title",
    "duty_summary",
    "exposure_mechanism",
    "category",
    "entity_name",
    "finding_date",
    "finding_summary",
    "accountability_implication",
    "act_type",
    "act_date",
    "status",
    "act_summary",
    "actor",
    "actor_scope",
    "linked_object_type",
    "linked_object_id",
    "role_in_chain",
    "obligation_basis",
    "accountability_question",
    "source_title",
    "source_url",
    "source_locator",
    "source_note",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply reviewed responsibility-ledger CSV rows")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in-dir", default=str(DEFAULT_IN_DIR), help="Directory containing reviewed CSV files")
    p.add_argument("--dry-run", action="store_true", help="Validate without writing rows")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _list_csv_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".csv")


def _read_review_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows: list[dict[str, str]] = []
        for raw_row in reader:
            row = {key: _norm(value) for key, value in (raw_row or {}).items()}
            if not any(row.values()):
                continue
            rows.append(row)
        return rows


def _case_exists(conn: Any, case_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM responsibility_explainer_cases WHERE case_id = ?",
        (case_id,),
    ).fetchone()
    return row is not None


def _upsert_warning_timeline_event(conn: Any, *, case_id: str, row_id: str, row: dict[str, str], order_value: int, now_iso: str) -> None:
    payload = {
        "case_id": case_id,
        "event_id": row_id,
        "channel_id": _norm(row.get("channel_id")),
        "channel_name": _norm(row.get("channel_name")),
        "operator": _norm(row.get("operator")),
        "event_time": _norm(row.get("event_time")),
        "event_precision": _norm(row.get("event_precision")),
        "signal_level": _norm(row.get("signal_level")),
        "event_summary": _norm(row.get("event_summary")),
        "why_it_matters": _norm(row.get("why_it_matters")),
        "source_title": _norm(row.get("source_title")),
        "source_url": _norm(row.get("source_url")),
        "source_locator": _norm(row.get("source_locator")),
        "source_note": _norm(row.get("source_note")),
        "reviewer": _norm(row.get("reviewer")),
        "review_note": _norm(row.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO responsibility_explainer_warning_timeline_events(
          case_event_pk,
          case_id,
          event_id,
          channel_id,
          channel_name,
          operator,
          event_time,
          event_precision,
          signal_level,
          event_summary,
          why_it_matters,
          source_title,
          source_url,
          source_locator,
          source_note,
          event_order,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_event_pk) DO UPDATE SET
          channel_id = excluded.channel_id,
          channel_name = excluded.channel_name,
          operator = excluded.operator,
          event_time = excluded.event_time,
          event_precision = excluded.event_precision,
          signal_level = excluded.signal_level,
          event_summary = excluded.event_summary,
          why_it_matters = excluded.why_it_matters,
          source_title = excluded.source_title,
          source_url = excluded.source_url,
          source_locator = excluded.source_locator,
          source_note = excluded.source_note,
          event_order = excluded.event_order,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            f"{case_id}:{row_id}",
            case_id,
            row_id,
            payload["channel_id"],
            payload["channel_name"],
            payload["operator"],
            payload["event_time"],
            payload["event_precision"],
            payload["signal_level"],
            payload["event_summary"],
            payload["why_it_matters"],
            payload["source_title"],
            payload["source_url"],
            payload["source_locator"],
            payload["source_note"],
            int(order_value),
            _stable_json(payload),
            now_iso,
            now_iso,
        ),
    )


def _upsert_governing_rule(conn: Any, *, case_id: str, row_id: str, row: dict[str, str], order_value: int, now_iso: str) -> None:
    payload = {
        "case_id": case_id,
        "rule_id": row_id,
        "rule_kind": _norm(row.get("rule_kind")),
        "title": _norm(row.get("title")),
        "duty_summary": _norm(row.get("duty_summary")),
        "exposure_mechanism": _norm(row.get("exposure_mechanism")),
        "source_title": _norm(row.get("source_title")),
        "source_url": _norm(row.get("source_url")),
        "source_locator": _norm(row.get("source_locator")),
        "source_note": _norm(row.get("source_note")),
        "reviewer": _norm(row.get("reviewer")),
        "review_note": _norm(row.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO responsibility_explainer_governing_rules(
          case_rule_pk,
          case_id,
          rule_id,
          rule_kind,
          title,
          duty_summary,
          exposure_mechanism,
          source_title,
          source_url,
          source_locator,
          source_note,
          rule_order,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_rule_pk) DO UPDATE SET
          rule_kind = excluded.rule_kind,
          title = excluded.title,
          duty_summary = excluded.duty_summary,
          exposure_mechanism = excluded.exposure_mechanism,
          source_title = excluded.source_title,
          source_url = excluded.source_url,
          source_locator = excluded.source_locator,
          source_note = excluded.source_note,
          rule_order = excluded.rule_order,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            f"{case_id}:{row_id}",
            case_id,
            row_id,
            payload["rule_kind"],
            payload["title"],
            payload["duty_summary"],
            payload["exposure_mechanism"],
            payload["source_title"],
            payload["source_url"],
            payload["source_locator"],
            payload["source_note"],
            int(order_value),
            _stable_json(payload),
            now_iso,
            now_iso,
        ),
    )


def _upsert_official_finding(conn: Any, *, case_id: str, row_id: str, row: dict[str, str], order_value: int, now_iso: str) -> None:
    payload = {
        "case_id": case_id,
        "finding_id": row_id,
        "category": _norm(row.get("category")),
        "entity_name": _norm(row.get("entity_name")),
        "finding_date": _norm(row.get("finding_date")),
        "finding_summary": _norm(row.get("finding_summary")),
        "accountability_implication": _norm(row.get("accountability_implication")),
        "source_title": _norm(row.get("source_title")),
        "source_url": _norm(row.get("source_url")),
        "source_locator": _norm(row.get("source_locator")),
        "source_note": _norm(row.get("source_note")),
        "reviewer": _norm(row.get("reviewer")),
        "review_note": _norm(row.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO responsibility_explainer_official_findings(
          case_finding_pk,
          case_id,
          finding_id,
          category,
          entity_name,
          finding_date,
          finding_summary,
          accountability_implication,
          source_title,
          source_url,
          source_locator,
          source_note,
          finding_order,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_finding_pk) DO UPDATE SET
          category = excluded.category,
          entity_name = excluded.entity_name,
          finding_date = excluded.finding_date,
          finding_summary = excluded.finding_summary,
          accountability_implication = excluded.accountability_implication,
          source_title = excluded.source_title,
          source_url = excluded.source_url,
          source_locator = excluded.source_locator,
          source_note = excluded.source_note,
          finding_order = excluded.finding_order,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            f"{case_id}:{row_id}",
            case_id,
            row_id,
            payload["category"],
            payload["entity_name"],
            payload["finding_date"],
            payload["finding_summary"],
            payload["accountability_implication"],
            payload["source_title"],
            payload["source_url"],
            payload["source_locator"],
            payload["source_note"],
            int(order_value),
            _stable_json(payload),
            now_iso,
            now_iso,
        ),
    )


def _upsert_administrative_act(conn: Any, *, case_id: str, row_id: str, row: dict[str, str], order_value: int, now_iso: str) -> None:
    payload = {
        "case_id": case_id,
        "act_id": row_id,
        "act_type": _norm(row.get("act_type")),
        "entity_name": _norm(row.get("entity_name")),
        "act_date": _norm(row.get("act_date")),
        "status": _norm(row.get("status")),
        "act_summary": _norm(row.get("act_summary")),
        "accountability_implication": _norm(row.get("accountability_implication")),
        "source_title": _norm(row.get("source_title")),
        "source_url": _norm(row.get("source_url")),
        "source_locator": _norm(row.get("source_locator")),
        "source_note": _norm(row.get("source_note")),
        "reviewer": _norm(row.get("reviewer")),
        "review_note": _norm(row.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO responsibility_explainer_administrative_acts(
          case_act_pk,
          case_id,
          act_id,
          act_type,
          entity_name,
          act_date,
          status,
          act_summary,
          accountability_implication,
          source_title,
          source_url,
          source_locator,
          source_note,
          act_order,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_act_pk) DO UPDATE SET
          act_type = excluded.act_type,
          entity_name = excluded.entity_name,
          act_date = excluded.act_date,
          status = excluded.status,
          act_summary = excluded.act_summary,
          accountability_implication = excluded.accountability_implication,
          source_title = excluded.source_title,
          source_url = excluded.source_url,
          source_locator = excluded.source_locator,
          source_note = excluded.source_note,
          act_order = excluded.act_order,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            f"{case_id}:{row_id}",
            case_id,
            row_id,
            payload["act_type"],
            payload["entity_name"],
            payload["act_date"],
            payload["status"],
            payload["act_summary"],
            payload["accountability_implication"],
            payload["source_title"],
            payload["source_url"],
            payload["source_locator"],
            payload["source_note"],
            int(order_value),
            _stable_json(payload),
            now_iso,
            now_iso,
        ),
    )


def _upsert_responsibility_link(conn: Any, *, case_id: str, row_id: str, row: dict[str, str], order_value: int, now_iso: str) -> None:
    payload = {
        "case_id": case_id,
        "link_id": row_id,
        "actor": _norm(row.get("actor")),
        "actor_scope": _norm(row.get("actor_scope")),
        "linked_object_type": _norm(row.get("linked_object_type")),
        "linked_object_id": _norm(row.get("linked_object_id")),
        "role_in_chain": _norm(row.get("role_in_chain")),
        "obligation_basis": _norm(row.get("obligation_basis")),
        "accountability_question": _norm(row.get("accountability_question")),
        "source_title": _norm(row.get("source_title")),
        "source_url": _norm(row.get("source_url")),
        "source_locator": _norm(row.get("source_locator")),
        "source_note": _norm(row.get("source_note")),
        "reviewer": _norm(row.get("reviewer")),
        "review_note": _norm(row.get("review_note")),
    }
    conn.execute(
        """
        INSERT INTO responsibility_explainer_responsibility_links(
          case_link_pk,
          case_id,
          link_id,
          actor,
          actor_scope,
          linked_object_type,
          linked_object_id,
          role_in_chain,
          obligation_basis,
          accountability_question,
          source_title,
          source_url,
          source_locator,
          source_note,
          link_order,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_link_pk) DO UPDATE SET
          actor = excluded.actor,
          actor_scope = excluded.actor_scope,
          linked_object_type = excluded.linked_object_type,
          linked_object_id = excluded.linked_object_id,
          role_in_chain = excluded.role_in_chain,
          obligation_basis = excluded.obligation_basis,
          accountability_question = excluded.accountability_question,
          source_title = excluded.source_title,
          source_url = excluded.source_url,
          source_locator = excluded.source_locator,
          source_note = excluded.source_note,
          link_order = excluded.link_order,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            f"{case_id}:{row_id}",
            case_id,
            row_id,
            payload["actor"],
            payload["actor_scope"],
            payload["linked_object_type"],
            payload["linked_object_id"],
            payload["role_in_chain"],
            payload["obligation_basis"],
            payload["accountability_question"],
            payload["source_title"],
            payload["source_url"],
            payload["source_locator"],
            payload["source_note"],
            int(order_value),
            _stable_json(payload),
            now_iso,
            now_iso,
        ),
    )


def apply_review_rows(conn: Any, *, review_files: list[Path], dry_run: bool) -> dict[str, Any]:
    now_iso = now_utc_iso()
    summary: dict[str, Any] = {
        "files_seen": 0,
        "rows_seen": 0,
        "rows_approved": 0,
        "rows_applied": 0,
        "applied_by_kind": {kind: 0 for kind in sorted(ALLOWED_LEDGER_KINDS)},
        "skipped_invalid_kind": 0,
        "skipped_blank_row_id": 0,
        "skipped_blank_case_id": 0,
        "skipped_missing_case": 0,
        "skipped_invalid_review_status": 0,
        "skipped_not_approved": 0,
    }
    per_case_kind_counters: dict[tuple[str, str], int] = defaultdict(int)
    pending_rows: list[tuple[str, str, str, dict[str, str], int]] = []

    for path in review_files:
        summary["files_seen"] += 1
        for row in _read_review_rows(path):
            summary["rows_seen"] += 1
            case_id = _norm(row.get("case_id"))
            ledger_kind = _norm(row.get("ledger_kind"))
            row_id = _norm(row.get("row_id"))
            review_status = _norm(row.get("review_status")).lower() or "pending"

            if not case_id:
                summary["skipped_blank_case_id"] += 1
                continue
            if not row_id:
                summary["skipped_blank_row_id"] += 1
                continue
            if ledger_kind not in ALLOWED_LEDGER_KINDS:
                summary["skipped_invalid_kind"] += 1
                continue
            if review_status not in ALLOWED_REVIEW_STATUS:
                summary["skipped_invalid_review_status"] += 1
                continue
            if review_status not in {"approved", "applied"}:
                summary["skipped_not_approved"] += 1
                continue
            if not _case_exists(conn, case_id):
                summary["skipped_missing_case"] += 1
                continue

            order_value = int(_norm(row.get("sort_order")) or 0)
            if order_value <= 0:
                per_case_kind_counters[(case_id, ledger_kind)] += 1
                order_value = per_case_kind_counters[(case_id, ledger_kind)]
            summary["rows_approved"] += 1
            pending_rows.append((case_id, ledger_kind, row_id, row, order_value))

    if dry_run or not pending_rows:
        return summary

    with conn:
        for case_id, ledger_kind, row_id, row, order_value in pending_rows:
            if ledger_kind == "warning_timeline_event":
                _upsert_warning_timeline_event(conn, case_id=case_id, row_id=row_id, row=row, order_value=order_value, now_iso=now_iso)
            elif ledger_kind == "governing_rule":
                _upsert_governing_rule(conn, case_id=case_id, row_id=row_id, row=row, order_value=order_value, now_iso=now_iso)
            elif ledger_kind == "official_finding":
                _upsert_official_finding(conn, case_id=case_id, row_id=row_id, row=row, order_value=order_value, now_iso=now_iso)
            elif ledger_kind == "administrative_act":
                _upsert_administrative_act(conn, case_id=case_id, row_id=row_id, row=row, order_value=order_value, now_iso=now_iso)
            elif ledger_kind == "responsibility_link":
                _upsert_responsibility_link(conn, case_id=case_id, row_id=row_id, row=row, order_value=order_value, now_iso=now_iso)
            else:
                continue
            summary["rows_applied"] += 1
            summary["applied_by_kind"][ledger_kind] += 1

    return summary


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_dir = Path(args.in_dir)
    review_files = _list_csv_files(in_dir)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = apply_review_rows(conn, review_files=review_files, dry_run=bool(args.dry_run))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(
        "OK responsibility ledger reviews -> "
        + str(db_path)
        + f" (files={summary['files_seen']} approved={summary['rows_approved']} applied={summary['rows_applied']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
