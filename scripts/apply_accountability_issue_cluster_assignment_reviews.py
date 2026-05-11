#!/usr/bin/env python3
"""Apply reviewed issue-cluster assignment CSV rows to the Evidence API seed."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.sanitize import redact_sensitive_text


DEFAULT_REVIEWS_CSV = Path(
    "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/exports/"
    "accountability_issue_cluster_assignment_reviews_latest.csv"
)
DEFAULT_SEED = Path("etl/data/seeds/accountability_issue_cluster_issue_reviews_seed_v1.json")
DEFAULT_REPORT_OUT = Path(
    "docs/etl/sprints/AI-OPS-ACCOUNTABILITY/evidence/"
    "accountability_issue_cluster_assignment_reviews_apply_report_latest.json"
)

APPLY_DECISIONS = {"accept_current", "set_clusters", "split", "merge"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply reviewed issue-cluster assignment CSV rows")
    p.add_argument("--csv", default=str(DEFAULT_REVIEWS_CSV), help="Reviewed CSV path")
    p.add_argument("--seed", default=str(DEFAULT_SEED), help="Input seed JSON path")
    p.add_argument("--out", default=str(DEFAULT_SEED), help="Output seed JSON path")
    p.add_argument("--report-out", default=str(DEFAULT_REPORT_OUT), help="Apply report JSON path")
    p.add_argument("--reviewer-default", default="Dev", help="Reviewer when CSV row leaves reviewer blank")
    p.add_argument("--reviewed-at-default", default="", help="Reviewed date when CSV row leaves reviewed_at blank")
    p.add_argument("--dry-run", action="store_true", help="Validate and report without writing the seed")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_iso() -> str:
    return date.today().isoformat()


def _norm(value: Any) -> str:
    return redact_sensitive_text(str(value or "").strip())


def _safe_array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _parse_json_list(value: Any) -> list[str]:
    text = _norm(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [part.strip() for part in text.split(";")]
    return [_norm(item) for item in _safe_array(parsed) if _norm(item)]


def _row_cluster_ids(row: dict[str, str]) -> list[str]:
    reviewed = _parse_json_list(row.get("reviewed_cluster_ids"))
    if reviewed:
        return reviewed
    current = _parse_json_list(row.get("current_cluster_ids"))
    if current:
        return current
    primary = _norm(row.get("reviewed_primary_cluster_id")) or _norm(row.get("current_primary_cluster_id"))
    return [primary] if primary else []


def _row_primary_cluster_id(row: dict[str, str], cluster_ids: list[str]) -> str:
    primary = _norm(row.get("reviewed_primary_cluster_id")) or _norm(row.get("current_primary_cluster_id"))
    if primary:
        return primary
    return cluster_ids[0] if cluster_ids else ""


def _review_from_row(
    row: dict[str, str],
    *,
    reviewer_default: str,
    reviewed_at_default: str,
) -> tuple[dict[str, Any] | None, str]:
    decision = _norm(row.get("decision")).lower()
    if not decision:
        return None, "blank_decision"
    if decision not in APPLY_DECISIONS:
        return None, "unsupported_decision"
    issue_id = _norm(row.get("issue_id"))
    if not issue_id:
        return None, "missing_issue_id"
    cluster_ids = _row_cluster_ids(row)
    primary_cluster_id = _row_primary_cluster_id(row, cluster_ids)
    if not primary_cluster_id or not cluster_ids:
        return None, "missing_cluster_ids"
    if primary_cluster_id not in cluster_ids:
        cluster_ids.insert(0, primary_cluster_id)

    rationale = _norm(row.get("rationale"))
    if decision in {"split", "merge"} and rationale:
        rationale = f"{decision}: {rationale}"
    elif decision in {"split", "merge"}:
        rationale = f"{decision}: reviewed cluster assignment"

    return (
        {
            "issue_id": issue_id,
            "decision": "set_clusters",
            "primary_cluster_id": primary_cluster_id,
            "cluster_ids": cluster_ids,
            "reviewer": _norm(row.get("reviewer")) or _norm(reviewer_default),
            "reviewed_at": _norm(row.get("reviewed_at")) or _norm(reviewed_at_default) or _today_iso(),
            "review_scope": "source_issue_cluster_assignment",
            "rationale": rationale or "Reviewed issue title and accepted current cluster assignment.",
        },
        "applied",
    )


def read_review_csv(
    path: Path,
    *,
    reviewer_default: str = "Dev",
    reviewed_at_default: str = "",
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    counts = {
        "input_rows_total": 0,
        "applied_rows_total": 0,
        "blank_decision_rows_total": 0,
        "unsupported_rows_total": 0,
        "invalid_rows_total": 0,
    }
    reviews: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            counts["input_rows_total"] += 1
            review, status = _review_from_row(
                {str(k): str(v or "") for k, v in row.items()},
                reviewer_default=reviewer_default,
                reviewed_at_default=reviewed_at_default,
            )
            if status == "applied" and review:
                counts["applied_rows_total"] += 1
                reviews.append(review)
            elif status == "blank_decision":
                counts["blank_decision_rows_total"] += 1
            elif status == "unsupported_decision":
                counts["unsupported_rows_total"] += 1
                skipped.append({"issue_id": _norm(row.get("issue_id")), "reason": status, "decision": _norm(row.get("decision"))})
            else:
                counts["invalid_rows_total"] += 1
                skipped.append({"issue_id": _norm(row.get("issue_id")), "reason": status})
    return reviews, counts, skipped


def merge_reviews(seed: dict[str, Any], reviews: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    merged = json.loads(json.dumps(seed, ensure_ascii=True))
    issue_reviews = [_safe_object(item) for item in _safe_array(merged.get("issue_reviews"))]
    before_total = len(issue_reviews)
    by_issue = {_norm(item.get("issue_id")): idx for idx, item in enumerate(issue_reviews) if _norm(item.get("issue_id"))}
    appended = 0
    replaced = 0
    for review in reviews:
        issue_id = _norm(review.get("issue_id"))
        if issue_id in by_issue:
            issue_reviews[by_issue[issue_id]] = review
            replaced += 1
        else:
            by_issue[issue_id] = len(issue_reviews)
            issue_reviews.append(review)
            appended += 1
    merged["issue_reviews"] = issue_reviews
    meta = _safe_object(merged.get("meta"))
    meta["updated_at"] = now_utc_iso()
    meta["last_apply_source"] = "accountability_issue_cluster_assignment_reviews_csv"
    merged["meta"] = meta
    return (
        merged,
        {
            "seed_issue_reviews_before": before_total,
            "seed_issue_reviews_after": len(issue_reviews),
            "seed_issue_reviews_appended": appended,
            "seed_issue_reviews_replaced": replaced,
        },
    )


def build_apply_report(
    *,
    csv_path: Path,
    seed_path: Path,
    out_path: Path,
    counts: dict[str, int],
    merge_counts: dict[str, int],
    reviews: list[dict[str, Any]],
    skipped_rows: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "meta": {
            "schema_version": "accountability_issue_cluster_assignment_reviews_apply_report_v1",
            "generated_at": now_utc_iso(),
            "csv_path": str(csv_path),
            "seed_path": str(seed_path),
            "out_path": str(out_path),
            "dry_run": dry_run,
        },
        "coverage": {**counts, **merge_counts},
        "applied_issue_ids": [str(review.get("issue_id") or "") for review in reviews],
        "skipped_rows": skipped_rows[:100],
    }


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv)
    seed_path = Path(args.seed)
    out_path = Path(args.out)
    report_path = Path(args.report_out)
    seed = _load_json(seed_path)
    reviews, counts, skipped_rows = read_review_csv(
        csv_path,
        reviewer_default=str(args.reviewer_default or ""),
        reviewed_at_default=str(args.reviewed_at_default or ""),
    )
    merged, merge_counts = merge_reviews(seed, reviews)
    report = build_apply_report(
        csv_path=csv_path,
        seed_path=seed_path,
        out_path=out_path,
        counts=counts,
        merge_counts=merge_counts,
        reviews=reviews,
        skipped_rows=skipped_rows,
        dry_run=bool(args.dry_run),
    )

    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(merged, ensure_ascii=True, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "OK applied issue-cluster assignment reviews -> "
        + str(out_path)
        + f" (applied={counts['applied_rows_total']} appended={merge_counts['seed_issue_reviews_appended']} "
        + f"replaced={merge_counts['seed_issue_reviews_replaced']} dry_run={bool(args.dry_run)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
