#!/usr/bin/env python3
"""Validate public accountability ledger and dossier artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate public accountability artifacts")
    p.add_argument("--ledger", required=True, help="Path to accountability-ledger JSON")
    p.add_argument("--dossiers", required=True, help="Path to accountability-dossiers JSON")
    p.add_argument("--evidence-api", default="", help="Optional accountability Evidence API JSON")
    p.add_argument("--snapshot-date", required=True, help="Expected snapshot date")
    p.add_argument("--min-entries", type=int, default=1, help="Minimum ledger entries")
    p.add_argument("--min-actors", type=int, default=1, help="Minimum actor dossiers")
    p.add_argument("--min-issues", type=int, default=1, help="Minimum issue dossiers")
    p.add_argument("--min-evidence-api-questions", type=int, default=0, help="Minimum Evidence API question templates")
    p.add_argument("--min-evidence-api-issue-clusters", type=int, default=0, help="Minimum Evidence API issue clusters")
    p.add_argument(
        "--min-evidence-api-reviewed-issue-clusters",
        type=int,
        default=0,
        help="Minimum Evidence API reviewed issue clusters",
    )
    p.add_argument(
        "--min-evidence-api-issue-cluster-issue-reviews",
        type=int,
        default=0,
        help="Minimum Evidence API issue-level cluster assignments reviewed",
    )
    p.add_argument(
        "--min-evidence-api-issue-cluster-assignment-review-needed",
        type=int,
        default=0,
        help="Minimum Evidence API issue-level cluster assignments still queued for review",
    )
    p.add_argument(
        "--max-evidence-api-issue-cluster-assignment-review-needed",
        type=int,
        default=-1,
        help="Maximum Evidence API issue-level cluster assignments still queued for review; -1 disables",
    )
    p.add_argument("--min-evidence-api-gap-answers", type=int, default=0, help="Minimum Evidence API gap answers")
    p.add_argument("--min-evidence-api-qa-answers", type=int, default=0, help="Minimum Evidence API natural-language QA answers")
    p.add_argument("--min-resolution-pct", type=float, default=1.0, help="Minimum resolved actor coverage")
    p.add_argument("--min-person-id-entries", type=int, default=0, help="Minimum entries with person_id")
    p.add_argument("--min-party-id-entries", type=int, default=0, help="Minimum entries with party_id")
    p.add_argument(
        "--min-parliamentary-group-id-entries",
        type=int,
        default=0,
        help="Minimum entries with parliamentary_group_id",
    )
    p.add_argument("--max-ledger-bytes", type=int, default=5_000_000, help="Maximum ledger JSON size")
    p.add_argument("--max-dossiers-bytes", type=int, default=10_000_000, help="Maximum dossiers JSON size")
    p.add_argument("--max-evidence-api-bytes", type=int, default=8_000_000, help="Maximum Evidence API JSON size")
    p.add_argument("--json-out", default="", help="Optional validation report output")
    return p.parse_args()


def _die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        _die(f"File not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON in {path}: {exc}")
    if not isinstance(payload, dict):
        _die(f"JSON root is not object: {path}")
    return payload


def _coverage(payload: dict[str, Any], artifact_name: str) -> dict[str, Any]:
    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        _die(f"{artifact_name}.coverage missing or not object")
    return coverage


def _as_int(coverage: dict[str, Any], key: str) -> int:
    try:
        return int(coverage.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(coverage: dict[str, Any], key: str) -> float:
    try:
        return float(coverage.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _schema_version(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("schema_version") or "")


def _snapshot_date(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("snapshot_date"):
        return str(meta.get("snapshot_date") or "")
    return str(payload.get("snapshot_date") or "")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = Path(args.ledger)
    dossier_path = Path(args.dossiers)
    ledger = _load_json(ledger_path)
    dossiers = _load_json(dossier_path)
    evidence_api_path = Path(str(args.evidence_api)) if str(args.evidence_api or "").strip() else None
    evidence_api = _load_json(evidence_api_path) if evidence_api_path else {}
    ledger_cov = _coverage(ledger, "ledger")
    dossier_cov = _coverage(dossiers, "dossiers")
    evidence_api_cov = _coverage(evidence_api, "evidence_api") if evidence_api_path else {}
    errors: list[str] = []

    checks: dict[str, Any] = {
        "ledger_path": str(ledger_path),
        "dossiers_path": str(dossier_path),
        "evidence_api_path": str(evidence_api_path) if evidence_api_path else "",
        "ledger_bytes": os.path.getsize(ledger_path),
        "dossiers_bytes": os.path.getsize(dossier_path),
        "evidence_api_bytes": os.path.getsize(evidence_api_path) if evidence_api_path else 0,
        "ledger_schema_version": _schema_version(ledger),
        "dossiers_schema_version": _schema_version(dossiers),
        "evidence_api_schema_version": _schema_version(evidence_api) if evidence_api_path else "",
        "ledger_snapshot_date": _snapshot_date(ledger),
        "dossiers_snapshot_date": _snapshot_date(dossiers),
        "evidence_api_snapshot_date": _snapshot_date(evidence_api) if evidence_api_path else "",
        "expected_snapshot_date": str(args.snapshot_date),
        "ledger_entries_total": _as_int(ledger_cov, "entries_total"),
        "ledger_actors_total": _as_int(ledger_cov, "actors_total"),
        "ledger_issues_total": _as_int(ledger_cov, "issues_total"),
        "ledger_entries_with_resolved_actor_id": _as_int(ledger_cov, "entries_with_resolved_actor_id"),
        "dossier_entries_total": _as_int(dossier_cov, "entries_total"),
        "dossier_actors_total": _as_int(dossier_cov, "actors_total"),
        "dossier_issues_total": _as_int(dossier_cov, "issues_total"),
        "dossier_issue_actor_edges_total": _as_int(dossier_cov, "issue_actor_edges_total"),
        "dossier_entries_with_person_id": _as_int(dossier_cov, "entries_with_person_id"),
        "dossier_entries_with_party_id": _as_int(dossier_cov, "entries_with_party_id"),
        "dossier_entries_with_parliamentary_group_id": _as_int(
            dossier_cov,
            "entries_with_parliamentary_group_id",
        ),
        "evidence_api_question_templates_total": _as_int(evidence_api_cov, "question_templates_total"),
        "evidence_api_actor_answers_total": _as_int(evidence_api_cov, "actor_answers_total"),
        "evidence_api_issue_answers_total": _as_int(evidence_api_cov, "issue_answers_total"),
        "evidence_api_actor_issue_refs_total": _as_int(evidence_api_cov, "actor_issue_refs_total"),
        "evidence_api_issue_clusters_total": _as_int(evidence_api_cov, "issue_clusters_total"),
        "evidence_api_issue_cluster_links_total": _as_int(evidence_api_cov, "issue_cluster_links_total"),
        "evidence_api_issue_cluster_review_items_total": _as_int(
            evidence_api_cov,
            "issue_cluster_review_items_total",
        ),
        "evidence_api_issue_cluster_issue_reviews_applied_total": _as_int(
            evidence_api_cov,
            "issue_cluster_issue_reviews_applied_total",
        ),
        "evidence_api_issue_cluster_reviewed_links_total": _as_int(
            evidence_api_cov,
            "issue_cluster_reviewed_links_total",
        ),
        "evidence_api_issue_cluster_assignment_review_needed_total": _as_int(
            evidence_api_cov,
            "issue_cluster_assignment_review_needed_total",
        ),
        "evidence_api_issue_cluster_assignment_review_queue_total": _as_int(
            evidence_api_cov,
            "issue_cluster_assignment_review_queue_total",
        ),
        "evidence_api_gap_answers_total": _as_int(evidence_api_cov, "gap_answers_total"),
        "evidence_api_qa_answers_total": _as_int(evidence_api_cov, "qa_answers_total"),
        "evidence_api_qa_answers_with_self_route_total": _as_int(evidence_api_cov, "qa_answers_with_self_route_total"),
        "evidence_api_evidence_samples_total": _as_int(evidence_api_cov, "evidence_samples_total"),
        "evidence_api_confidence_levels_total": sum(
            int(value or 0) for value in (evidence_api_cov.get("confidence_level_counts") or {}).values()
        )
        if isinstance(evidence_api_cov.get("confidence_level_counts"), dict)
        else 0,
        "evidence_api_freshness_levels_total": sum(
            int(value or 0) for value in (evidence_api_cov.get("freshness_level_counts") or {}).values()
        )
        if isinstance(evidence_api_cov.get("freshness_level_counts"), dict)
        else 0,
    }
    checks["ledger_resolution_pct"] = (
        checks["ledger_entries_with_resolved_actor_id"] / checks["ledger_entries_total"]
        if checks["ledger_entries_total"]
        else 1.0
    )
    evidence_api_review_status_counts = (
        evidence_api_cov.get("issue_cluster_review_status_counts") if evidence_api_path else {}
    )
    if not isinstance(evidence_api_review_status_counts, dict):
        evidence_api_review_status_counts = {}
    checks["evidence_api_issue_cluster_review_statuses_total"] = sum(
        int(value or 0) for value in evidence_api_review_status_counts.values()
    )
    checks["evidence_api_reviewed_issue_clusters_total"] = int(
        evidence_api_review_status_counts.get("reviewed") or 0
    )

    expected = str(args.snapshot_date)
    if checks["ledger_schema_version"] != "accountability_ledger_snapshot_v1":
        errors.append("ledger schema_version mismatch")
    if checks["dossiers_schema_version"] != "accountability_dossier_snapshot_v1":
        errors.append("dossiers schema_version mismatch")
    if evidence_api_path and checks["evidence_api_schema_version"] != "accountability_evidence_api_v1":
        errors.append("evidence_api schema_version mismatch")
    if checks["ledger_snapshot_date"] != expected:
        errors.append("ledger snapshot_date mismatch")
    if checks["dossiers_snapshot_date"] != expected:
        errors.append("dossiers snapshot_date mismatch")
    if evidence_api_path and checks["evidence_api_snapshot_date"] != expected:
        errors.append("evidence_api snapshot_date mismatch")
    if checks["ledger_bytes"] > int(args.max_ledger_bytes):
        errors.append("ledger exceeds max bytes")
    if checks["dossiers_bytes"] > int(args.max_dossiers_bytes):
        errors.append("dossiers exceeds max bytes")
    if evidence_api_path and checks["evidence_api_bytes"] > int(args.max_evidence_api_bytes):
        errors.append("evidence_api exceeds max bytes")
    if checks["ledger_entries_total"] < int(args.min_entries):
        errors.append("ledger entries below minimum")
    if checks["dossier_entries_total"] != checks["ledger_entries_total"]:
        errors.append("dossier entries_total does not match ledger")
    if checks["dossier_actors_total"] < int(args.min_actors):
        errors.append("dossier actors below minimum")
    if checks["dossier_issues_total"] < int(args.min_issues):
        errors.append("dossier issues below minimum")
    if checks["dossier_issue_actor_edges_total"] < checks["dossier_actors_total"]:
        errors.append("issue_actor_edges_total below actors_total")
    if checks["ledger_resolution_pct"] < float(args.min_resolution_pct):
        errors.append("resolved actor coverage below minimum")
    if checks["dossier_entries_with_person_id"] < int(args.min_person_id_entries):
        errors.append("entries_with_person_id below minimum")
    if checks["dossier_entries_with_party_id"] < int(args.min_party_id_entries):
        errors.append("entries_with_party_id below minimum")
    if checks["dossier_entries_with_parliamentary_group_id"] < int(args.min_parliamentary_group_id_entries):
        errors.append("entries_with_parliamentary_group_id below minimum")
    if evidence_api_path:
        if checks["evidence_api_question_templates_total"] < int(args.min_evidence_api_questions):
            errors.append("evidence_api question_templates below minimum")
        if checks["evidence_api_issue_clusters_total"] < int(args.min_evidence_api_issue_clusters):
            errors.append("evidence_api issue_clusters below minimum")
        if checks["evidence_api_issue_cluster_review_items_total"] != checks["evidence_api_issue_clusters_total"]:
            errors.append("evidence_api issue cluster review queue does not match clusters")
        if (
            checks["evidence_api_issue_cluster_review_statuses_total"]
            != checks["evidence_api_issue_cluster_review_items_total"]
        ):
            errors.append("evidence_api issue cluster review status counts do not match review queue")
        if checks["evidence_api_reviewed_issue_clusters_total"] < int(args.min_evidence_api_reviewed_issue_clusters):
            errors.append("evidence_api reviewed issue clusters below minimum")
        if checks["evidence_api_issue_cluster_issue_reviews_applied_total"] < int(
            args.min_evidence_api_issue_cluster_issue_reviews
        ):
            errors.append("evidence_api issue cluster issue-level reviews below minimum")
        if checks["evidence_api_issue_cluster_assignment_review_needed_total"] < int(
            args.min_evidence_api_issue_cluster_assignment_review_needed
        ):
            errors.append("evidence_api issue cluster assignment review queue below minimum")
        if (
            int(args.max_evidence_api_issue_cluster_assignment_review_needed) >= 0
            and checks["evidence_api_issue_cluster_assignment_review_needed_total"]
            > int(args.max_evidence_api_issue_cluster_assignment_review_needed)
        ):
            errors.append("evidence_api issue cluster assignment review queue above maximum")
        if (
            checks["evidence_api_issue_cluster_assignment_review_queue_total"]
            > checks["evidence_api_issue_cluster_assignment_review_needed_total"]
        ):
            errors.append("evidence_api issue cluster assignment review queue exceeds needed total")
        if checks["evidence_api_gap_answers_total"] < int(args.min_evidence_api_gap_answers):
            errors.append("evidence_api gap_answers below minimum")
        if checks["evidence_api_qa_answers_total"] < int(args.min_evidence_api_qa_answers):
            errors.append("evidence_api qa_answers below minimum")
        if checks["evidence_api_qa_answers_with_self_route_total"] != checks["evidence_api_qa_answers_total"]:
            errors.append("evidence_api qa_answers missing self routes")
        if checks["evidence_api_actor_answers_total"] != checks["dossier_actors_total"]:
            errors.append("evidence_api actor_answers_total does not match dossiers")
        if checks["evidence_api_issue_answers_total"] != checks["dossier_issues_total"]:
            errors.append("evidence_api issue_answers_total does not match dossiers")
        answer_total = checks["evidence_api_actor_answers_total"] + checks["evidence_api_issue_answers_total"]
        if checks["evidence_api_confidence_levels_total"] != answer_total:
            errors.append("evidence_api confidence level counts do not match answers")
        if checks["evidence_api_freshness_levels_total"] != answer_total:
            errors.append("evidence_api freshness level counts do not match answers")

    return {
        "passed": not errors,
        "errors": errors,
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    report = validate(args)
    if str(args.json_out or "").strip():
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["checks"], ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
