#!/usr/bin/env python3
"""Safely promote Andalucia 2026 execution-evidence review drafts.

Default mode is dry-run. A seed write requires --apply and either explicit
review item ids or approved drafts selected with --all. --auto-safe is an
alias for safe machine-approved automation in both dry-run and apply modes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_andalucia_2026_accountability_snapshot import stable_slug, write_json
from scripts.generate_andalucia_2026_execution_review_drafts import (
    NO_MERIT_CLAIM_STATUSES,
    existing_review_keys,
    review_locator_key,
)


DEFAULT_DRAFTS = Path("etl/data/published/andalucia-2026-execution-evidence-review-drafts.json")
DEFAULT_REVIEWS = Path("etl/data/seeds/andalucia_2026_execution_evidence_reviews.json")

SAFE_REVIEW_STATUSES = {
    "reviewed_budget_plan_linked_execution_pending",
    "reviewed_contract_award_linked_outcome_pending",
    "reviewed_grant_award_linked_delivery_outcome_pending",
    "reviewed_treasury_payment_aggregate_linked_delivery_outcome_pending",
    "reviewed_indicator_target_linked_observed_outcome_pending",
    "reviewed_observed_outcome_baseline_post_change_pending",
}

SAFE_INTERPRETATION_STATUSES = {
    "budget_plan_only_execution_beneficiaries_and_outcomes_pending",
    "contract_award_only_delivery_beneficiaries_and_outcomes_pending",
    "grant_award_only_beneficiaries_delivery_and_outcomes_pending",
    "treasury_payment_aggregate_only_beneficiaries_delivery_and_outcomes_pending",
    "indicator_target_only_observed_outcome_series_pending",
    "observed_outcome_series_pre_2026_baseline_only_post_change_pending",
}

BLOCKED_SCORE_KEYS = {
    "score",
    "impact_score",
    "merit_score",
    "blame_score",
    "accountability_score",
    "responsibility_score",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply safe Andalucia 2026 execution review draft promotions"
    )
    parser.add_argument("--drafts", default=str(DEFAULT_DRAFTS), help="Draft review JSON path")
    parser.add_argument("--reviews", default=str(DEFAULT_REVIEWS), help="Review seed JSON path")
    parser.add_argument("--out", default="", help="Optional apply-plan summary JSON path")
    parser.add_argument(
        "--review-item-id",
        action="append",
        default=[],
        help="Promote one explicit draft id; repeat for multiple ids",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Select all human-approved drafts; machine drafts still need --allow-machine-drafts",
    )
    parser.add_argument(
        "--allow-machine-drafts",
        action="store_true",
        help="Allow --all to select machine drafts. Explicit ids are already treated as reviewed selection.",
    )
    parser.add_argument(
        "--auto-safe",
        action="store_true",
        help="Equivalent to --all --allow-machine-drafts for automated safe drafts.",
    )
    parser.add_argument("--apply", action="store_true", help="Write promoted reviews into the seed")
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def draft_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in payload.get("drafts") or [] if isinstance(row, dict)]


def selected_drafts(
    drafts: list[dict[str, Any]],
    *,
    review_item_ids: list[str],
    include_all: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {str(row.get("review_item_id") or ""): row for row in drafts}
    if review_item_ids:
        selected: list[dict[str, Any]] = []
        missing: list[str] = []
        seen: set[str] = set()
        for item_id in review_item_ids:
            item_id = str(item_id)
            if item_id in seen:
                continue
            seen.add(item_id)
            row = by_id.get(item_id)
            if row is None:
                missing.append(item_id)
                continue
            selected.append(row)
        return selected, missing
    if include_all:
        return list(drafts), []
    return [], []


def safe_draft_violations(row: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    claim_status = str(row.get("claim_status") or "")
    review_status = str(row.get("review_status") or "")
    interpretation_status = str(row.get("interpretation_status") or "")
    limitations = row.get("open_limitations") or []
    limitation_set = {str(item) for item in limitations if isinstance(item, str)}

    if claim_status not in NO_MERIT_CLAIM_STATUSES:
        violations.append("claim_status_not_no_merit_or_blame")
    if review_status not in SAFE_REVIEW_STATUSES:
        violations.append("review_status_not_safe_pending_status")
    if interpretation_status not in SAFE_INTERPRETATION_STATUSES:
        violations.append("interpretation_status_not_safe_pending_status")
    if "merit_blame_not_scored" not in limitation_set:
        violations.append("missing_merit_blame_not_scored_limitation")
    if "causal_impact_not_claimed" not in limitation_set:
        violations.append("missing_causal_impact_not_claimed_limitation")
    for key in BLOCKED_SCORE_KEYS:
        if row.get(key) not in (None, "", []):
            violations.append(f"blocked_score_field:{key}")
    return violations


def promoted_review_item_id(row: dict[str, Any]) -> str:
    return stable_slug(
        "andalucia-2026-execution-review:"
        f"{row.get('topic_id')}:{row.get('gap_id')}:{row.get('source_id')}:{row.get('source_locator')}"
    )


def promote_draft_review(
    row: dict[str, Any], *, explicit_selection: bool, auto_safe: bool = False
) -> dict[str, Any]:
    promoted = {key: value for key, value in row.items() if key != "draft_status"}
    draft_id = str(row.get("review_item_id") or "")
    promoted["review_item_id"] = promoted_review_item_id(row)
    promoted["promoted_from_review_item_id"] = draft_id
    if explicit_selection:
        promoted["promotion_status"] = "promoted_from_machine_draft_explicit_selection"
        promoted["reviewed_by"] = "draft_generator_explicit_review_selection"
    elif auto_safe:
        promoted["promotion_status"] = "promoted_from_machine_draft_auto_safe"
        promoted["reviewed_by"] = "draft_generator_auto_safe"
    else:
        promoted["promotion_status"] = "promoted_from_human_approved_draft"
    return promoted


def action_for_row(
    row: dict[str, Any],
    *,
    existing_keys: set[str],
    planned_keys: set[str],
    existing_ids: set[str],
    planned_ids: set[str],
    allow_machine_drafts: bool,
    explicit_selection: bool,
    auto_safe: bool = False,
) -> tuple[str, str, list[str], dict[str, Any] | None]:
    draft_status = str(row.get("draft_status") or "")
    if not explicit_selection and draft_status != "human_approved" and not allow_machine_drafts:
        return "skipped_unapproved", "draft_not_human_approved", [], None

    violations = safe_draft_violations(row)
    if violations:
        return "blocked_unsafe", "unsafe_draft", violations, None

    key = review_locator_key(row)
    promoted = promote_draft_review(
        row, explicit_selection=explicit_selection, auto_safe=auto_safe
    )
    promoted_id = str(promoted.get("review_item_id") or "")
    if key in existing_keys or key in planned_keys:
        return "skipped_duplicate", "duplicate_source_locator", [], None
    if promoted_id in existing_ids or promoted_id in planned_ids:
        return "skipped_duplicate", "duplicate_review_item_id", [], None
    return "would_apply", "safe_for_seed_promotion", [], promoted


def build_apply_plan(
    drafts_payload: dict[str, Any],
    reviews_payload: dict[str, Any],
    *,
    review_item_ids: list[str] | None = None,
    include_all: bool = False,
    allow_machine_drafts: bool = False,
    auto_safe: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if auto_safe:
        include_all = True
        allow_machine_drafts = True
    drafts = draft_rows(drafts_payload)
    review_item_ids = review_item_ids or []
    selected, missing = selected_drafts(drafts, review_item_ids=review_item_ids, include_all=include_all)
    explicit_selection = bool(review_item_ids)
    existing_keys = existing_review_keys(reviews_payload)
    existing_ids = {
        str(row.get("review_item_id") or "")
        for row in reviews_payload.get("reviews") or []
        if isinstance(row, dict)
    }
    planned_keys: set[str] = set()
    planned_ids: set[str] = set()
    promoted_rows: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    counts = {
        "would_apply_total": 0,
        "skipped_duplicate_total": 0,
        "skipped_unapproved_total": 0,
        "blocked_unsafe_total": 0,
    }

    for row in selected:
        action, reason, violations, promoted = action_for_row(
            row,
            existing_keys=existing_keys,
            planned_keys=planned_keys,
            existing_ids=existing_ids,
            planned_ids=planned_ids,
            allow_machine_drafts=allow_machine_drafts,
            explicit_selection=explicit_selection,
            auto_safe=auto_safe,
        )
        if action == "would_apply" and promoted is not None:
            promoted_rows.append(promoted)
            planned_keys.add(review_locator_key(row))
            planned_ids.add(str(promoted.get("review_item_id") or ""))
        counts[f"{action}_total"] += 1
        actions.append(
            {
                "action": action,
                "reason": reason,
                "review_item_id": str(row.get("review_item_id") or ""),
                "promoted_review_item_id": promoted_review_item_id(row),
                "topic_id": str(row.get("topic_id") or ""),
                "gap_id": str(row.get("gap_id") or ""),
                "source_id": str(row.get("source_id") or ""),
                "source_locator": str(row.get("source_locator") or ""),
                "violations": violations,
            }
        )

    if promoted_rows:
        status = "ready_to_apply"
    elif selected:
        status = "no_applicable_rows"
    else:
        status = "no_selection"

    selection_mode = "auto_safe" if auto_safe else ("explicit_ids" if explicit_selection else ("all" if include_all else "none"))
    plan = {
        "schema_version": "andalucia_2026_execution_evidence_review_apply_plan_v1",
        "generated_at": now_utc(),
        "source_schema_version": str(drafts_payload.get("schema_version") or ""),
        "status": status,
        "selection_mode": selection_mode,
        "allow_machine_drafts": bool(allow_machine_drafts),
        "drafts_total": len(drafts),
        "existing_reviews_total": len(reviews_payload.get("reviews") or []),
        "selected_total": len(selected),
        "missing_review_item_ids": missing,
        "missing_review_item_ids_total": len(missing),
        **counts,
        "actions": actions,
    }
    return plan, promoted_rows


def apply_promoted_reviews(
    reviews_payload: dict[str, Any],
    promoted_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = dict(reviews_payload)
    updated.setdefault("schema_version", "andalucia_2026_execution_evidence_reviews_v1")
    updated.setdefault(
        "review_policy",
        (
            "Rows in this seed review official budget-plan, contract-award, indicator-target "
            "and observed baseline evidence only. They do not document final delivery, "
            "beneficiaries, post-change outcomes, causality, merit or blame."
        ),
    )
    updated.setdefault("reviewed_at", datetime.now(UTC).date().isoformat())
    reviews = [row for row in updated.get("reviews") or [] if isinstance(row, dict)]
    reviews.extend(promoted_rows)
    updated["reviews"] = reviews
    return updated


def main() -> int:
    args = parse_args()
    auto_safe = bool(args.auto_safe)
    drafts_path = Path(args.drafts)
    reviews_path = Path(args.reviews)
    drafts_payload = load_json_object(drafts_path)
    reviews_payload = load_json_object(reviews_path)
    plan, promoted_rows = build_apply_plan(
        drafts_payload,
        reviews_payload,
        review_item_ids=args.review_item_id,
        include_all=bool(args.all) or auto_safe,
        allow_machine_drafts=bool(args.allow_machine_drafts) or auto_safe,
        auto_safe=auto_safe,
    )
    plan["dry_run"] = not bool(args.apply)
    plan["applied_total"] = 0
    plan["apply_changed"] = False

    if args.apply and promoted_rows:
        updated = apply_promoted_reviews(reviews_payload, promoted_rows)
        plan["apply_changed"] = write_json(reviews_path, updated)
        plan["applied_total"] = len(promoted_rows)
    elif args.apply and not promoted_rows:
        plan["status"] = "apply_requested_no_applicable_rows"

    if args.out:
        write_json(Path(args.out), plan)

    print(
        "OK Andalucia 2026 execution review apply plan: status={status} dry_run={dry_run} selection_mode={selection_mode} selected={selected} would_apply={would_apply} duplicates={duplicates} unsafe={unsafe} unapproved={unapproved} applied={applied}".format(
            status=plan["status"],
            dry_run=plan["dry_run"],
            selection_mode=plan["selection_mode"],
            selected=plan["selected_total"],
            would_apply=plan["would_apply_total"],
            duplicates=plan["skipped_duplicate_total"],
            unsafe=plan["blocked_unsafe_total"],
            unapproved=plan["skipped_unapproved_total"],
            applied=plan["applied_total"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
