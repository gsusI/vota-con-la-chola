#!/usr/bin/env python3
"""Export a review queue for Evidence API issue-cluster assignments."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.sanitize import redact_sensitive_text, sanitize_url_for_public


DEFAULT_EVIDENCE_API = Path("etl/data/published/accountability-evidence-api-latest.json")
DEFAULT_OUT = Path(
    "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/"
    "accountability_issue_cluster_assignment_review_queue_latest.json"
)
DEFAULT_CSV_OUT = Path(
    "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/"
    "accountability_issue_cluster_assignment_review_queue_latest.csv"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export issue-cluster assignment review queue")
    p.add_argument("--evidence-api", default=str(DEFAULT_EVIDENCE_API), help="Evidence API JSON path")
    p.add_argument("--snapshot-date", default="", help="Snapshot date override")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="JSON queue output")
    p.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT), help="CSV queue output")
    p.add_argument("--limit", type=int, default=0, help="Max queue rows; 0 means all")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _norm(value: Any) -> str:
    return redact_sensitive_text(str(value or "").strip())


def _clip(value: Any, limit: int = 320) -> str:
    text = _norm(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _priority(entries_total: int) -> int:
    if entries_total >= 10_000:
        return 100
    if entries_total >= 1_000:
        return 90
    if entries_total >= 100:
        return 80
    return 60


def _match_ref(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_id": _norm(match.get("cluster_id")),
        "label": _clip(match.get("label"), 180),
        "method": _norm(match.get("method")),
        "issue_review_status": _norm(match.get("issue_review_status")) or "heuristic",
        "matched_keywords": [_norm(item) for item in _safe_array(match.get("matched_keywords"))[:8]],
    }


def build_issue_cluster_assignment_review_queue(
    evidence_api: dict[str, Any],
    *,
    snapshot_date: str = "",
    limit: int = 0,
) -> dict[str, Any]:
    meta = _safe_object(evidence_api.get("meta"))
    coverage = _safe_object(evidence_api.get("coverage"))
    queue_source = _safe_array(evidence_api.get("issue_cluster_assignment_review_queue"))
    rows: list[dict[str, Any]] = []
    for item_raw in queue_source:
        item = _safe_object(item_raw)
        coverage_obj = _safe_object(item.get("coverage"))
        routes = _safe_object(item.get("routes"))
        entries_total = int(coverage_obj.get("entries_total") or 0)
        cluster_ids = [_norm(value) for value in _safe_array(item.get("cluster_ids")) if _norm(value)]
        row = {
            "priority": _priority(entries_total),
            "review_id": _norm(item.get("review_id")),
            "issue_id": _norm(item.get("issue_id")),
            "answer_id": _norm(item.get("answer_id")),
            "issue_label": _clip(item.get("label"), 260),
            "review_status": _norm(item.get("review_status")) or "needs_review",
            "current_primary_cluster_id": _norm(item.get("primary_cluster_id")),
            "current_cluster_ids": cluster_ids,
            "current_matches": [_match_ref(_safe_object(match)) for match in _safe_array(item.get("current_matches"))],
            "entries_total": entries_total,
            "actors_total": int(coverage_obj.get("actors_total") or 0),
            "first_date": _norm(coverage_obj.get("first_date")),
            "last_date": _norm(coverage_obj.get("last_date")),
            "route": sanitize_url_for_public(_norm(routes.get("dossier"))),
            "decision_template": {
                "issue_id": _norm(item.get("issue_id")),
                "decision": "",
                "primary_cluster_id": _norm(item.get("primary_cluster_id")),
                "cluster_ids": cluster_ids,
                "reviewer": "",
                "reviewed_at": "",
                "review_scope": "source_issue_cluster_assignment",
                "rationale": "",
            },
            "allowed_decisions": ["accept_current", "set_clusters", "split", "merge", "reject", "needs_research"],
            "next_action": "copy_decision_template_to_accountability_issue_cluster_issue_reviews_seed_v1",
        }
        rows.append(row)

    rows.sort(key=lambda row: (-int(row["priority"]), -int(row["entries_total"]), row["issue_label"]))
    total_rows = len(rows)
    max_rows = int(limit or 0)
    if max_rows > 0:
        rows = rows[:max_rows]

    snapshot = str(snapshot_date or meta.get("snapshot_date") or evidence_api.get("snapshot_date") or "")
    return {
        "meta": {
            "schema_version": "accountability_issue_cluster_assignment_review_queue_v1",
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot,
            "source_evidence_api_schema": meta.get("schema_version"),
            "limit": max_rows,
        },
        "coverage": {
            "source_issue_answers_total": int(coverage.get("issue_answers_total") or 0),
            "source_issue_clusters_total": int(coverage.get("issue_clusters_total") or 0),
            "reviewed_issue_assignments_total": int(coverage.get("issue_cluster_issue_reviews_applied_total") or 0),
            "pending_issue_assignments_total": int(
                coverage.get("issue_cluster_assignment_review_needed_total") or total_rows
            ),
            "source_queue_rows_total": total_rows,
            "queue_rows_total": len(rows),
            "queue_truncated": bool(max_rows > 0 and total_rows > len(rows)),
        },
        "queue": rows,
    }


def write_csv(path: Path, queue_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "priority",
        "review_id",
        "issue_id",
        "issue_label",
        "entries_total",
        "actors_total",
        "first_date",
        "last_date",
        "current_primary_cluster_id",
        "current_cluster_ids",
        "current_matches",
        "route",
        "decision",
        "reviewed_primary_cluster_id",
        "reviewed_cluster_ids",
        "reviewer",
        "reviewed_at",
        "rationale",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in queue_rows:
            decision_template = _safe_object(row.get("decision_template"))
            writer.writerow(
                {
                    "priority": row.get("priority", ""),
                    "review_id": row.get("review_id", ""),
                    "issue_id": row.get("issue_id", ""),
                    "issue_label": row.get("issue_label", ""),
                    "entries_total": row.get("entries_total", ""),
                    "actors_total": row.get("actors_total", ""),
                    "first_date": row.get("first_date", ""),
                    "last_date": row.get("last_date", ""),
                    "current_primary_cluster_id": row.get("current_primary_cluster_id", ""),
                    "current_cluster_ids": _json_cell(row.get("current_cluster_ids") or []),
                    "current_matches": _json_cell(row.get("current_matches") or []),
                    "route": row.get("route", ""),
                    "decision": "",
                    "reviewed_primary_cluster_id": decision_template.get("primary_cluster_id", ""),
                    "reviewed_cluster_ids": _json_cell(decision_template.get("cluster_ids") or []),
                    "reviewer": "",
                    "reviewed_at": "",
                    "rationale": "",
                    "next_action": row.get("next_action", ""),
                }
            )


def main() -> int:
    args = parse_args()
    evidence_api_path = Path(args.evidence_api)
    evidence_api = json.loads(evidence_api_path.read_text(encoding="utf-8"))
    payload = build_issue_cluster_assignment_review_queue(
        _safe_object(evidence_api),
        snapshot_date=str(args.snapshot_date or ""),
        limit=int(args.limit or 0),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.csv_out or "").strip():
        write_csv(Path(args.csv_out), list(payload["queue"]))
    cov = payload["coverage"]
    print(
        "OK accountability issue-cluster assignment review queue -> "
        + str(out_path)
        + f" (pending={cov['pending_issue_assignments_total']} rows={cov['queue_rows_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
