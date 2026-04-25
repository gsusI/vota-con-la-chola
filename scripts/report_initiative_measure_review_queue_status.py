#!/usr/bin/env python3
"""Report status for the initiative-measure review queue."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso
from scripts.export_initiative_measure_review_queue import (
    DEFAULT_DB,
    DEFAULT_DOC_SOURCE_ID,
    DEFAULT_INITIATIVE_SOURCE_IDS,
    DEFAULT_REVIEW_REASON,
    sync_review_queue,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Report status for initiative-measure review queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values to include",
    )
    p.add_argument("--doc-source-id", default=DEFAULT_DOC_SOURCE_ID, help="text_documents.source_id")
    p.add_argument("--review-reason", default=DEFAULT_REVIEW_REASON, help="Task review_reason")
    p.add_argument("--sync", action="store_true", help="Upsert queue candidates before reporting")
    p.add_argument("--top-n", type=int, default=10, help="Top pending tasks to include")
    p.add_argument("--enforce-gate", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_source_ids(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = _norm(token)
        if not item or item in seen:
            continue
        seen.add(item)
        values.append(item)
    return tuple(values)


def build_status_report(
    conn: sqlite3.Connection,
    *,
    initiative_source_ids: tuple[str, ...],
    doc_source_id: str,
    review_reason: str,
    sync: bool,
    top_n: int,
) -> dict[str, Any]:
    sync_summary = {"enabled": bool(sync), "candidate_rows": 0, "upserted": 0}
    if sync:
        sync_summary.update(
            sync_review_queue(
                conn,
                initiative_source_ids=initiative_source_ids,
                doc_source_id=_norm(doc_source_id),
                review_reason=_norm(review_reason) or DEFAULT_REVIEW_REASON,
            )
        )

    totals = conn.execute(
        """
        SELECT
          COUNT(*) AS tasks_total,
          SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_total,
          SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved_total,
          SUM(CASE WHEN status = 'ignored' THEN 1 ELSE 0 END) AS ignored_total,
          SUM(CASE WHEN COALESCE(TRIM(evidence_bundle_dir), '') <> '' THEN 1 ELSE 0 END) AS tasks_with_evidence_bundle_total,
          SUM(CASE WHEN status = 'pending' AND COALESCE(TRIM(evidence_bundle_dir), '') <> '' THEN 1 ELSE 0 END) AS pending_with_evidence_bundle_total,
          SUM(CASE WHEN status = 'pending' AND COALESCE(TRIM(evidence_bundle_dir), '') = '' THEN 1 ELSE 0 END) AS pending_without_evidence_bundle_total,
          SUM(CASE WHEN status = 'resolved' AND COALESCE(TRIM(evidence_bundle_dir), '') <> '' THEN 1 ELSE 0 END) AS resolved_with_evidence_bundle_total,
          SUM(CASE WHEN status = 'resolved' AND COALESCE(TRIM(evidence_bundle_dir), '') = '' THEN 1 ELSE 0 END) AS resolved_without_evidence_bundle_total,
          SUM(CASE WHEN priority >= 90 THEN 1 ELSE 0 END) AS priority_90_plus_total
        FROM parl_initiative_measure_review_tasks
        """
    ).fetchone()
    measure_totals = conn.execute(
        """
        SELECT
          COUNT(*) AS measure_points_total,
          COUNT(DISTINCT task_id) AS measure_tasks_total
        FROM parl_initiative_measure_points
        """
    ).fetchone()
    integrity = conn.execute(
        """
        WITH measure_counts AS (
          SELECT task_id, COUNT(*) AS measure_points_total
          FROM parl_initiative_measure_points
          GROUP BY task_id
        )
        SELECT
          SUM(CASE WHEN t.status = 'resolved' AND COALESCE(mc.measure_points_total, 0) = 0 THEN 1 ELSE 0 END) AS resolved_without_measure_points_total,
          SUM(CASE WHEN t.status = 'ignored' AND COALESCE(mc.measure_points_total, 0) > 0 THEN 1 ELSE 0 END) AS ignored_with_measure_points_total,
          SUM(CASE WHEN t.status = 'pending' AND COALESCE(mc.measure_points_total, 0) > 0 THEN 1 ELSE 0 END) AS pending_with_measure_points_total
        FROM parl_initiative_measure_review_tasks t
        LEFT JOIN measure_counts mc ON mc.task_id = t.task_id
        """
    ).fetchone()

    by_source_rows = conn.execute(
        """
        WITH measure_counts AS (
          SELECT task_id, COUNT(*) AS measure_points_total
          FROM parl_initiative_measure_points
          GROUP BY task_id
        )
        SELECT
          t.source_id,
          COUNT(*) AS tasks_total,
          SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) AS pending_total,
          SUM(CASE WHEN t.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_total,
          SUM(CASE WHEN t.status = 'ignored' THEN 1 ELSE 0 END) AS ignored_total,
          SUM(CASE WHEN COALESCE(mc.measure_points_total, 0) > 0 THEN mc.measure_points_total ELSE 0 END) AS measure_points_total
        FROM parl_initiative_measure_review_tasks t
        LEFT JOIN measure_counts mc ON mc.task_id = t.task_id
        GROUP BY t.source_id
        ORDER BY tasks_total DESC, t.source_id ASC
        """
    ).fetchall()
    by_review_reason_rows = conn.execute(
        """
        WITH measure_counts AS (
          SELECT task_id, COUNT(*) AS measure_points_total
          FROM parl_initiative_measure_points
          GROUP BY task_id
        )
        SELECT
          t.review_reason,
          COUNT(*) AS tasks_total,
          SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) AS pending_total,
          SUM(CASE WHEN t.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_total,
          SUM(CASE WHEN t.status = 'ignored' THEN 1 ELSE 0 END) AS ignored_total,
          SUM(CASE WHEN COALESCE(mc.measure_points_total, 0) > 0 THEN mc.measure_points_total ELSE 0 END) AS measure_points_total
        FROM parl_initiative_measure_review_tasks t
        LEFT JOIN measure_counts mc ON mc.task_id = t.task_id
        GROUP BY t.review_reason
        ORDER BY tasks_total DESC, t.review_reason ASC
        """
    ).fetchall()
    top_pending_rows = conn.execute(
        """
        WITH measure_counts AS (
          SELECT task_id, COUNT(*) AS measure_points_total
          FROM parl_initiative_measure_points
          GROUP BY task_id
        )
        SELECT
          t.task_id,
          t.initiative_id,
          t.source_id,
          t.review_reason,
          t.status,
          t.priority,
          COALESCE(t.evidence_bundle_dir, '') AS evidence_bundle_dir,
          COALESCE(i.expediente, '') AS expediente,
          COALESCE(i.title, '') AS initiative_title,
          COUNT(DISTINCT pvi.vote_event_id) AS linked_vote_count,
          COALESCE(mc.measure_points_total, 0) AS measure_points_total
        FROM parl_initiative_measure_review_tasks t
        JOIN parl_initiatives i ON i.initiative_id = t.initiative_id
        LEFT JOIN parl_vote_event_initiatives pvi ON pvi.initiative_id = t.initiative_id
        LEFT JOIN measure_counts mc ON mc.task_id = t.task_id
        WHERE t.status = 'pending'
        GROUP BY
          t.task_id,
          t.initiative_id,
          t.source_id,
          t.review_reason,
          t.status,
          t.priority,
          t.evidence_bundle_dir,
          i.expediente,
          i.title,
          mc.measure_points_total
        ORDER BY t.priority DESC, linked_vote_count DESC, i.title ASC, t.task_id ASC
        LIMIT ?
        """,
        (max(0, int(top_n or 0)),),
    ).fetchall()

    tasks_total = int(totals["tasks_total"] or 0)
    resolved_without_measure_points_total = int(integrity["resolved_without_measure_points_total"] or 0)
    ignored_with_measure_points_total = int(integrity["ignored_with_measure_points_total"] or 0)
    pending_with_measure_points_total = int(integrity["pending_with_measure_points_total"] or 0)

    checks = {
        "queue_started_ok": tasks_total > 0,
        "resolved_have_measure_points_ok": resolved_without_measure_points_total == 0,
        "ignored_have_no_measure_points_ok": ignored_with_measure_points_total == 0,
        "pending_without_measure_points_ok": pending_with_measure_points_total == 0,
    }
    if tasks_total == 0:
        status = "failed"
    elif all(checks.values()):
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "input": {
            "initiative_source_ids": list(initiative_source_ids),
            "doc_source_id": _norm(doc_source_id),
            "review_reason": _norm(review_reason),
            "sync": bool(sync),
            "top_n": max(0, int(top_n or 0)),
        },
        "sync": sync_summary,
        "totals": {
            "tasks_total": tasks_total,
            "pending_total": int(totals["pending_total"] or 0),
            "resolved_total": int(totals["resolved_total"] or 0),
            "ignored_total": int(totals["ignored_total"] or 0),
            "tasks_with_evidence_bundle_total": int(totals["tasks_with_evidence_bundle_total"] or 0),
            "pending_with_evidence_bundle_total": int(totals["pending_with_evidence_bundle_total"] or 0),
            "pending_without_evidence_bundle_total": int(totals["pending_without_evidence_bundle_total"] or 0),
            "resolved_with_evidence_bundle_total": int(totals["resolved_with_evidence_bundle_total"] or 0),
            "resolved_without_evidence_bundle_total": int(totals["resolved_without_evidence_bundle_total"] or 0),
            "priority_90_plus_total": int(totals["priority_90_plus_total"] or 0),
            "measure_points_total": int(measure_totals["measure_points_total"] or 0),
            "measure_tasks_total": int(measure_totals["measure_tasks_total"] or 0),
        },
        "integrity": {
            "resolved_without_measure_points_total": resolved_without_measure_points_total,
            "ignored_with_measure_points_total": ignored_with_measure_points_total,
            "pending_with_measure_points_total": pending_with_measure_points_total,
        },
        "checks": checks,
        "by_source": [
            {
                "source_id": _norm(row["source_id"]),
                "tasks_total": int(row["tasks_total"] or 0),
                "pending_total": int(row["pending_total"] or 0),
                "resolved_total": int(row["resolved_total"] or 0),
                "ignored_total": int(row["ignored_total"] or 0),
                "measure_points_total": int(row["measure_points_total"] or 0),
            }
            for row in by_source_rows
        ],
        "by_review_reason": [
            {
                "review_reason": _norm(row["review_reason"]),
                "tasks_total": int(row["tasks_total"] or 0),
                "pending_total": int(row["pending_total"] or 0),
                "resolved_total": int(row["resolved_total"] or 0),
                "ignored_total": int(row["ignored_total"] or 0),
                "measure_points_total": int(row["measure_points_total"] or 0),
            }
            for row in by_review_reason_rows
        ],
        "top_pending": [
            {
                "task_id": _norm(row["task_id"]),
                "initiative_id": _norm(row["initiative_id"]),
                "source_id": _norm(row["source_id"]),
                "review_reason": _norm(row["review_reason"]),
                "status": _norm(row["status"]),
                "priority": int(row["priority"] or 0),
                "expediente": _norm(row["expediente"]),
                "initiative_title": _norm(row["initiative_title"]),
                "linked_vote_count": int(row["linked_vote_count"] or 0),
                "measure_points_total": int(row["measure_points_total"] or 0),
                "has_evidence_bundle": bool(_norm(row["evidence_bundle_dir"])),
            }
            for row in top_pending_rows
        ],
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        report = build_status_report(
            conn,
            initiative_source_ids=_parse_source_ids(str(args.initiative_source_ids or "")),
            doc_source_id=str(args.doc_source_id or ""),
            review_reason=str(args.review_reason or ""),
            sync=bool(args.sync),
            top_n=int(args.top_n or 0),
        )

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if str(report.get("status")) == "failed":
        return 1
    if bool(args.enforce_gate) and str(report.get("status")) != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
