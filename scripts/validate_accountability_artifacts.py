#!/usr/bin/env python3
"""Validate public accountability ledger and dossier artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_PUBLIC_DIMENSIONS = (
    "promises",
    "parliamentary_actions",
    "rules",
    "appointments",
    "money",
    "implementation",
    "enforcement",
    "audits",
    "outcomes",
)
PUBLIC_ANSWER_STATUSES = {"answerable", "partial", "unanswerable", "blocked"}
PUBLIC_CONFIDENCE_LEVELS = {"none", "low", "medium", "high"}
PUBLIC_FRESHNESS_LEVELS = {"unknown", "current", "recent", "historical"}
EXPECTED_EVIDENCE_API_TEMPLATE_IDS = {
    "issue_involved_actors",
    "actor_historical_record",
    "actor_issue_record",
    "missing_evidence",
    "source_blocker",
    "natural_language_qa",
}
EVIDENCE_API_COLLECTION_CHECKS = (
    ("question_templates", "evidence_api_question_templates_total", "evidence_api_question_templates_exported"),
    ("actor_answers", "evidence_api_actor_answers_total", "evidence_api_actor_answers_exported"),
    ("issue_answers", "evidence_api_issue_answers_total", "evidence_api_issue_answers_exported"),
    ("actor_issue_refs", "evidence_api_actor_issue_refs_total", "evidence_api_actor_issue_refs_exported"),
    ("issue_clusters", "evidence_api_issue_clusters_total", "evidence_api_issue_clusters_exported"),
    ("gap_answers", "evidence_api_gap_answers_total", "evidence_api_gap_answers_exported"),
    ("blocker_answers", "evidence_api_blocker_answers_total", "evidence_api_blocker_answers_exported"),
    ("qa_answers", "evidence_api_qa_answers_total", "evidence_api_qa_answers_exported"),
    (
        "issue_cluster_review_queue",
        "evidence_api_issue_cluster_review_items_total",
        "evidence_api_issue_cluster_review_queue_exported",
    ),
    (
        "issue_cluster_assignment_review_queue",
        "evidence_api_issue_cluster_assignment_review_queue_total",
        "evidence_api_issue_cluster_assignment_review_queue_exported",
    ),
)


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
    p.add_argument(
        "--min-evidence-api-blocker-answers",
        type=int,
        default=0,
        help="Minimum Evidence API source blocker answers",
    )
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


def _safe_array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _answer_label(collection: str, index: int, answer: dict[str, Any]) -> str:
    identifier = (
        answer.get("answer_id")
        or answer.get("cluster_id")
        or answer.get("dimension")
        or answer.get("question_id")
        or index
    )
    return f"{collection}[{index}] ({identifier})"


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _counter_dict(values: Any) -> dict[str, int]:
    if not isinstance(values, dict):
        return {}
    return {str(key): _int_value(value) for key, value in values.items() if _int_value(value) != 0}


def _sum_count_values(values: Any) -> int:
    if not isinstance(values, dict):
        return 0
    return sum(_int_value(value) for value in values.values())


def _evidence_api_collections(evidence_api: dict[str, Any]) -> dict[str, list[Any]]:
    return {
        collection_key: _safe_array(evidence_api.get(collection_key))
        for collection_key, _coverage_key, _exported_key in EVIDENCE_API_COLLECTION_CHECKS
    }


def _validate_evidence_api_collection_counts(
    collections: dict[str, list[Any]],
    checks: dict[str, Any],
    errors: list[str],
) -> None:
    for collection_key, coverage_key, exported_key in EVIDENCE_API_COLLECTION_CHECKS:
        collection = collections[collection_key]
        checks[exported_key] = len(collection)
        if checks[coverage_key] != len(collection):
            errors.append(f"evidence_api {collection_key} array count mismatch")


def _validate_public_evidence_sample(
    sample: dict[str, Any],
    *,
    label: str,
    errors: list[str],
) -> None:
    if not _text(sample.get("entry_id")):
        errors.append(f"{label} evidence sample missing entry_id")
    if not _text(sample.get("entry_kind")):
        errors.append(f"{label} evidence sample missing entry_kind")
    if not _text(sample.get("accountability_role")):
        errors.append(f"{label} evidence sample missing accountability_role")
    tier = _int_value(sample.get("evidence_tier"))
    if tier <= 0:
        errors.append(f"{label} evidence sample missing evidence_tier")
    if not _text(sample.get("source_title")):
        errors.append(f"{label} evidence sample missing source_title")
    if not (_text(sample.get("source_url")) or _text(sample.get("source_locator"))):
        errors.append(f"{label} evidence sample missing source_url/source_locator")
    if not (_text(sample.get("summary")) or _text(sample.get("evidence_quote"))):
        errors.append(f"{label} evidence sample missing summary/evidence_quote")


def _validate_dimension_partition(answer: dict[str, Any], *, label: str, errors: list[str]) -> None:
    present = {_text(item) for item in _safe_array(answer.get("present_dimensions")) if _text(item)}
    missing = {_text(item) for item in _safe_array(answer.get("missing_dimensions")) if _text(item)}
    expected = set(EXPECTED_PUBLIC_DIMENSIONS)
    if present | missing != expected:
        errors.append(f"{label} dimension partition does not cover expected public dimensions")
    if present & missing:
        errors.append(f"{label} dimension partition has overlap")
    expected_status = "unanswerable"
    entries_total = _int_value(_safe_object(answer.get("coverage")).get("entries_total"))
    if entries_total > 0:
        expected_status = "partial" if missing else "answerable"
    if _text(answer.get("answer_status")) != expected_status:
        errors.append(f"{label} answer_status does not match dimension coverage")


def _validate_actor_or_issue_answers(
    collection: str,
    answers: list[Any],
    *,
    expected_question_id: str,
    errors: list[str],
) -> None:
    for index, raw_answer in enumerate(answers):
        answer = _safe_object(raw_answer)
        label = _answer_label(collection, index, answer)
        if not _text(answer.get("answer_id")):
            errors.append(f"{label} missing answer_id")
        if _text(answer.get("question_id")) != expected_question_id:
            errors.append(f"{label} question_id mismatch")
        if _text(answer.get("answer_status")) not in PUBLIC_ANSWER_STATUSES:
            errors.append(f"{label} invalid answer_status")
        if not _text(answer.get("summary")):
            errors.append(f"{label} missing summary")
        coverage = _safe_object(answer.get("coverage"))
        entries_total = _int_value(coverage.get("entries_total"))
        if entries_total <= 0:
            errors.append(f"{label} entries_total must be positive")
        if not _text(_safe_object(answer.get("routes")).get("dossier")):
            errors.append(f"{label} missing dossier route")
        _validate_dimension_partition(answer, label=label, errors=errors)

        confidence = _safe_object(answer.get("confidence"))
        if _text(confidence.get("level")) not in PUBLIC_CONFIDENCE_LEVELS:
            errors.append(f"{label} invalid confidence level")
        if entries_total > 0 and _int_value(confidence.get("best_evidence_tier")) <= 0:
            errors.append(f"{label} missing best_evidence_tier")
        completeness = _safe_object(confidence.get("completeness"))
        if _int_value(completeness.get("expected_dimensions_total")) != len(EXPECTED_PUBLIC_DIMENSIONS):
            errors.append(f"{label} confidence completeness expected_dimensions_total mismatch")

        freshness = _safe_object(answer.get("freshness"))
        if _text(freshness.get("level")) not in PUBLIC_FRESHNESS_LEVELS:
            errors.append(f"{label} invalid freshness level")

        if _text(answer.get("answer_status")) != "answerable" and not _safe_array(answer.get("caveats")):
            errors.append(f"{label} missing caveats for incomplete answer")
        evidence_samples = _safe_array(answer.get("evidence_samples"))
        if not evidence_samples:
            errors.append(f"{label} missing evidence_samples")
        for sample_index, raw_sample in enumerate(evidence_samples):
            _validate_public_evidence_sample(
                _safe_object(raw_sample),
                label=f"{label}.evidence_samples[{sample_index}]",
                errors=errors,
            )


def _validate_actor_issue_refs(refs: list[Any], *, errors: list[str]) -> None:
    for index, raw_ref in enumerate(refs):
        ref = _safe_object(raw_ref)
        label = _answer_label("actor_issue_refs", index, ref)
        if not _text(ref.get("answer_id")):
            errors.append(f"{label} missing answer_id")
        if _text(ref.get("question_id")) != "actor_issue_record":
            errors.append(f"{label} question_id mismatch")
        if _text(ref.get("answer_status")) not in PUBLIC_ANSWER_STATUSES:
            errors.append(f"{label} invalid answer_status")
        if not _text(ref.get("actor_key")):
            errors.append(f"{label} missing actor_key")
        if not _text(ref.get("issue_id")):
            errors.append(f"{label} missing issue_id")
        if _int_value(ref.get("entries_total")) <= 0:
            errors.append(f"{label} entries_total must be positive")
        routes = _safe_object(ref.get("routes"))
        if not _text(routes.get("actor_dossier")):
            errors.append(f"{label} missing actor_dossier route")
        if not _text(routes.get("issue_dossier")):
            errors.append(f"{label} missing issue_dossier route")
        if not _safe_array(ref.get("role_counts")):
            errors.append(f"{label} missing role_counts")


def _validate_issue_clusters(clusters: list[Any], *, errors: list[str]) -> None:
    for index, raw_cluster in enumerate(clusters):
        cluster = _safe_object(raw_cluster)
        label = _answer_label("issue_clusters", index, cluster)
        if not _text(cluster.get("cluster_id")):
            errors.append(f"{label} missing cluster_id")
        if not _text(cluster.get("label")):
            errors.append(f"{label} missing label")
        if _text(cluster.get("answer_status")) not in PUBLIC_ANSWER_STATUSES:
            errors.append(f"{label} invalid answer_status")
        coverage = _safe_object(cluster.get("coverage"))
        if _int_value(coverage.get("entries_total")) <= 0:
            errors.append(f"{label} entries_total must be positive")
        if _int_value(coverage.get("issues_total")) <= 0:
            errors.append(f"{label} issues_total must be positive")
        if not _safe_object(cluster.get("method")):
            errors.append(f"{label} missing method")
        if not _text(cluster.get("review_status")):
            errors.append(f"{label} missing review_status")
        if not _safe_array(cluster.get("top_issues")):
            errors.append(f"{label} missing top_issues")
        if not _safe_array(cluster.get("caveats")):
            errors.append(f"{label} missing caveats")
        evidence_samples = _safe_array(cluster.get("evidence_samples"))
        if not evidence_samples:
            errors.append(f"{label} missing evidence_samples")
        for sample_index, raw_sample in enumerate(evidence_samples):
            _validate_public_evidence_sample(
                _safe_object(raw_sample),
                label=f"{label}.evidence_samples[{sample_index}]",
                errors=errors,
            )


def _validate_gap_answers(gap_answers: list[Any], *, errors: list[str]) -> None:
    seen_dimensions: set[str] = set()
    for index, raw_answer in enumerate(gap_answers):
        answer = _safe_object(raw_answer)
        label = _answer_label("gap_answers", index, answer)
        dimension = _text(answer.get("dimension"))
        if not dimension:
            errors.append(f"{label} missing dimension")
            continue
        seen_dimensions.add(dimension)
        if dimension not in EXPECTED_PUBLIC_DIMENSIONS:
            errors.append(f"{label} unexpected dimension")
        if _text(answer.get("question_id")) != "missing_evidence":
            errors.append(f"{label} question_id mismatch")
        if _text(answer.get("answer_status")) not in PUBLIC_ANSWER_STATUSES:
            errors.append(f"{label} invalid answer_status")
        if not _text(answer.get("next_evidence_needed")):
            errors.append(f"{label} missing next_evidence_needed")
        coverage = _safe_object(answer.get("coverage"))
        if not coverage:
            errors.append(f"{label} missing coverage")
        samples = _safe_array(answer.get("sample_missing_issues")) + _safe_array(answer.get("sample_missing_actors"))
        if _int_value(coverage.get("missing_answers_total")) > 0 and not samples:
            errors.append(f"{label} missing sample refs for missing evidence")
        for sample_index, raw_sample in enumerate(samples):
            route = _safe_object(raw_sample).get("route")
            if not _text(route):
                errors.append(f"{label}.sample[{sample_index}] missing route")
    if seen_dimensions != set(EXPECTED_PUBLIC_DIMENSIONS):
        errors.append("evidence_api gap answers do not cover expected public dimensions")


def _validate_blocker_answers(blocker_answers: list[Any], *, errors: list[str]) -> None:
    for index, raw_answer in enumerate(blocker_answers):
        answer = _safe_object(raw_answer)
        label = _answer_label("blocker_answers", index, answer)
        if not _text(answer.get("answer_id")):
            errors.append(f"{label} missing answer_id")
        if _text(answer.get("question_id")) != "source_blocker":
            errors.append(f"{label} question_id mismatch")
        if _text(answer.get("answer_status")) != "blocked":
            errors.append(f"{label} answer_status must be blocked")
        if not _text(answer.get("source_id")):
            errors.append(f"{label} missing source_id")
        if not _text(answer.get("source_name")):
            errors.append(f"{label} missing source_name")
        if _text(answer.get("catalog_state")) != "blocked":
            errors.append(f"{label} catalog_state must be blocked")
        if not _text(answer.get("blocker_kind")):
            errors.append(f"{label} missing blocker_kind")
        if not _text(answer.get("summary")):
            errors.append(f"{label} missing summary")
        if not _text(answer.get("blocker_reason")):
            errors.append(f"{label} missing blocker_reason")
        evidence_refs = _safe_array(answer.get("evidence_refs"))
        if not evidence_refs:
            errors.append(f"{label} missing evidence_refs")
        for ref_index, raw_ref in enumerate(evidence_refs):
            if not _text(_safe_object(raw_ref).get("path")):
                errors.append(f"{label}.evidence_refs[{ref_index}] missing path")
        if not _safe_array(answer.get("next_commands")):
            errors.append(f"{label} missing next_commands")
        if not _text(_safe_object(answer.get("routes")).get("source_catalog")):
            errors.append(f"{label} missing source_catalog route")
        if not _safe_array(answer.get("caveats")):
            errors.append(f"{label} missing caveats")


def _validate_qa_answers(qa_answers: list[Any], *, errors: list[str]) -> None:
    for index, raw_answer in enumerate(qa_answers):
        answer = _safe_object(raw_answer)
        label = _answer_label("qa_answers", index, answer)
        if _text(answer.get("question_id")) != "natural_language_qa":
            errors.append(f"{label} question_id mismatch")
        if _text(answer.get("answer_status")) not in PUBLIC_ANSWER_STATUSES:
            errors.append(f"{label} invalid answer_status")
        if not _text(answer.get("source_collection")):
            errors.append(f"{label} missing source_collection")
        if not _text(answer.get("source_answer_id")):
            errors.append(f"{label} missing source_answer_id")
        if not _text(answer.get("question")):
            errors.append(f"{label} missing question")
        if not _text(answer.get("answer_text")):
            errors.append(f"{label} missing answer_text")
        if not _safe_object(answer.get("evidence_basis")):
            errors.append(f"{label} missing evidence_basis")
        routes = _safe_object(answer.get("routes"))
        if not _text(routes.get("self")):
            errors.append(f"{label} missing self route")
        if (
            _text(answer.get("answer_status")) != "unanswerable"
            and _text(answer.get("source_collection")) != "gap_answers"
            and not _text(routes.get("primary"))
        ):
            errors.append(f"{label} missing primary route")
        if not _safe_array(answer.get("caveats")):
            errors.append(f"{label} missing caveats")


def _validate_evidence_api_contract(
    evidence_api: dict[str, Any],
    checks: dict[str, Any],
    errors: list[str],
) -> None:
    collections = _evidence_api_collections(evidence_api)
    question_templates = collections["question_templates"]
    actor_answers = collections["actor_answers"]
    issue_answers = collections["issue_answers"]
    actor_issue_refs = collections["actor_issue_refs"]
    issue_clusters = collections["issue_clusters"]
    gap_answers = collections["gap_answers"]
    blocker_answers = collections["blocker_answers"]
    qa_answers = collections["qa_answers"]

    _validate_evidence_api_collection_counts(collections, checks, errors)

    template_ids = {_text(_safe_object(item).get("question_id")) for item in question_templates}
    if not EXPECTED_EVIDENCE_API_TEMPLATE_IDS.issubset(template_ids):
        errors.append("evidence_api question templates missing required public answer shapes")

    _validate_actor_or_issue_answers(
        "actor_answers",
        actor_answers,
        expected_question_id="actor_historical_record",
        errors=errors,
    )
    _validate_actor_or_issue_answers(
        "issue_answers",
        issue_answers,
        expected_question_id="issue_involved_actors",
        errors=errors,
    )
    _validate_actor_issue_refs(actor_issue_refs, errors=errors)
    _validate_issue_clusters(issue_clusters, errors=errors)
    _validate_gap_answers(gap_answers, errors=errors)
    _validate_blocker_answers(blocker_answers, errors=errors)
    _validate_qa_answers(qa_answers, errors=errors)

    evidence_samples_total = sum(
        len(_safe_array(_safe_object(answer).get("evidence_samples")))
        for answer in actor_answers + issue_answers
    )
    checks["evidence_api_evidence_samples_exported"] = evidence_samples_total
    if checks["evidence_api_evidence_samples_total"] != evidence_samples_total:
        errors.append("evidence_api evidence_samples_total does not match answer samples")

    answer_status_counts = Counter(
        _text(_safe_object(answer).get("answer_status")) or "unknown"
        for answer in actor_answers + issue_answers
    )
    qa_status_counts = Counter(
        _text(_safe_object(answer).get("answer_status")) or "unknown"
        for answer in qa_answers
    )
    gap_status_counts = Counter(
        _text(_safe_object(answer).get("answer_status")) or "unknown"
        for answer in gap_answers
    )
    blocker_status_counts = Counter(
        _text(_safe_object(answer).get("answer_status")) or "unknown"
        for answer in blocker_answers
    )
    blocker_kind_counts = Counter(
        _text(_safe_object(answer).get("blocker_kind")) or "unknown"
        for answer in blocker_answers
    )
    confidence_counts = Counter(
        _text(_safe_object(_safe_object(answer).get("confidence")).get("level")) or "unknown"
        for answer in actor_answers + issue_answers
    )
    freshness_counts = Counter(
        _text(_safe_object(_safe_object(answer).get("freshness")).get("level")) or "unknown"
        for answer in actor_answers + issue_answers
    )
    issue_cluster_link_total = sum(
        len(_safe_array(_safe_object(answer).get("issue_cluster_ids")))
        for answer in issue_answers
    )
    checks["evidence_api_issue_cluster_links_exported"] = issue_cluster_link_total
    if checks["evidence_api_issue_cluster_links_total"] != issue_cluster_link_total:
        errors.append("evidence_api issue_cluster_links_total does not match issue answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("answer_status_counts")) != dict(
        sorted(answer_status_counts.items())
    ):
        errors.append("evidence_api answer_status_counts do not match answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("qa_answer_status_counts")) != dict(
        sorted(qa_status_counts.items())
    ):
        errors.append("evidence_api qa_answer_status_counts do not match qa_answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("gap_answer_status_counts")) != dict(
        sorted(gap_status_counts.items())
    ):
        errors.append("evidence_api gap_answer_status_counts do not match gap_answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("blocker_answer_status_counts")) != dict(
        sorted(blocker_status_counts.items())
    ):
        errors.append("evidence_api blocker_answer_status_counts do not match blocker_answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("blocker_kind_counts")) != dict(
        sorted(blocker_kind_counts.items())
    ):
        errors.append("evidence_api blocker_kind_counts do not match blocker_answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("confidence_level_counts")) != dict(
        sorted(confidence_counts.items())
    ):
        errors.append("evidence_api confidence_level_counts do not match answers")
    if _counter_dict(_safe_object(evidence_api.get("coverage")).get("freshness_level_counts")) != dict(
        sorted(freshness_counts.items())
    ):
        errors.append("evidence_api freshness_level_counts do not match answers")


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
        "evidence_api_blocker_answers_total": _as_int(evidence_api_cov, "blocker_answers_total"),
        "evidence_api_source_catalog_blocked_total": _as_int(evidence_api_cov, "source_catalog_blocked_total"),
        "evidence_api_qa_answers_total": _as_int(evidence_api_cov, "qa_answers_total"),
        "evidence_api_qa_answers_with_self_route_total": _as_int(evidence_api_cov, "qa_answers_with_self_route_total"),
        "evidence_api_evidence_samples_total": _as_int(evidence_api_cov, "evidence_samples_total"),
        "evidence_api_confidence_levels_total": _sum_count_values(evidence_api_cov.get("confidence_level_counts")),
        "evidence_api_freshness_levels_total": _sum_count_values(evidence_api_cov.get("freshness_level_counts")),
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
    checks["evidence_api_issue_cluster_review_statuses_total"] = _sum_count_values(evidence_api_review_status_counts)
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
        if checks["evidence_api_blocker_answers_total"] < int(args.min_evidence_api_blocker_answers):
            errors.append("evidence_api blocker_answers below minimum")
        if (
            checks["evidence_api_source_catalog_blocked_total"] > 0
            and checks["evidence_api_blocker_answers_total"] != checks["evidence_api_source_catalog_blocked_total"]
        ):
            errors.append("evidence_api blocker_answers_total does not match source catalog blocked total")
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
        _validate_evidence_api_contract(evidence_api, checks, errors)

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
