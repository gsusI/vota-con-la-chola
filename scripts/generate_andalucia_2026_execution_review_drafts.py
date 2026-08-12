#!/usr/bin/env python3
"""Generate conservative draft execution-evidence reviews from the queue.

The output is a review-assist artifact, not an automatic accountability claim.
Rows keep explicit no-merit/no-blame statuses and should be promoted into the
review seed only after human review.
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


DEFAULT_ACCOUNTABILITY = Path("etl/data/published/andalucia-2026-accountability.json")
DEFAULT_EXISTING_REVIEWS = Path("etl/data/seeds/andalucia_2026_execution_evidence_reviews.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-execution-evidence-review-drafts.json")

NO_MERIT_CLAIM_STATUSES = {
    "official_budget_indicator_review_no_merit_or_blame",
    "official_budget_contract_indicator_review_no_merit_or_blame",
    "official_budget_grant_award_review_no_merit_or_blame",
    "official_treasury_payment_aggregate_review_no_merit_or_blame",
    "official_observed_outcome_baseline_no_merit_or_blame",
}

EVIDENCE_KIND_DRAFT_PRIORITY_BY_GAP = {
    "missing_outcomes": {
        "observed_outcome_series": 0,
        "indicator_target": 1,
        "contract_award": 2,
        "budget_plan": 3,
    },
    "missing_budget_execution": {
        "contract_award": 0,
        "grant_award": 1,
        "treasury_payment_aggregate": 2,
        "budget_plan": 3,
        "indicator_target": 4,
        "observed_outcome_series": 5,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conservative Andalucia 2026 execution-evidence review drafts"
    )
    parser.add_argument("--accountability", default=str(DEFAULT_ACCOUNTABILITY), help="Accountability JSON path")
    parser.add_argument("--existing-reviews", default=str(DEFAULT_EXISTING_REVIEWS), help="Existing review seed JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Draft review JSON output path")
    parser.add_argument("--reviewed-at", default="", help="Override reviewed_at/generator date")
    parser.add_argument("--max-drafts-per-item", type=int, default=3, help="Draft cap per queue item")
    parser.add_argument("--include-reviewed", action="store_true", help="Do not skip already-reviewed locators")
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def review_locator_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("topic_id") or ""),
            str(row.get("gap_id") or ""),
            str(row.get("source_id") or ""),
            str(row.get("source_locator") or ""),
        ]
    )


def existing_review_keys(payload: dict[str, Any]) -> set[str]:
    return {
        review_locator_key(row)
        for row in payload.get("reviews") or []
        if isinstance(row, dict) and row.get("source_locator")
    }


def evidence_kind_for_candidate(candidate: dict[str, Any], gap_id: str) -> str:
    source_kind = str(candidate.get("source_kind") or "")
    source_id = str(candidate.get("source_id") or "")
    if "procurement" in source_kind or source_id.startswith("junta_contratos_menores_"):
        return "contract_award"
    if source_kind == "official_grant_awards_open_data" or source_id.startswith("junta_subvenciones_"):
        return "grant_award"
    if source_kind == "official_treasury_payment_aggregate_open_data" or source_id.startswith("junta_tesoreria_"):
        return "treasury_payment_aggregate"
    if source_kind == "official_outcome_series_json":
        return "observed_outcome_series"
    if gap_id == "missing_outcomes" and (
        candidate.get("indicator_name") or candidate.get("indicator_code")
    ):
        return "indicator_target"
    if gap_id == "missing_budget_execution" and source_kind == "official_budget_open_data":
        return "budget_plan"
    return ""


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def draft_candidate_sort_key(candidate: dict[str, Any], gap_id: str, evidence_kind: str) -> tuple[int, int, int, int, str, str]:
    priority_by_kind = EVIDENCE_KIND_DRAFT_PRIORITY_BY_GAP.get(gap_id, {})
    return (
        priority_by_kind.get(evidence_kind, 99),
        int_value(candidate.get("review_priority"), 99),
        -int_value(candidate.get("match_score")),
        int_value(candidate.get("row_number"), 999999),
        str(candidate.get("source_id") or ""),
        str(candidate.get("source_locator") or ""),
    )


def review_confidence_for_kind(candidate: dict[str, Any], evidence_kind: str) -> str:
    if evidence_kind == "contract_award":
        contract_state = normalize_label(candidate.get("contract_state"))
        if contract_state in {"resuelto", "resuelta"}:
            return "medium"
        if any(
            [
                str(candidate.get("contract_award_formalization_date") or "").strip(),
                str(candidate.get("contract_award_resolution_date") or "").strip(),
                str(candidate.get("award_date") or "").strip(),
            ]
        ):
            return "medium"
        return "low"
    return "low"


def claim_status_for_kind(evidence_kind: str) -> str:
    if evidence_kind == "contract_award":
        return "official_budget_contract_indicator_review_no_merit_or_blame"
    if evidence_kind == "grant_award":
        return "official_budget_grant_award_review_no_merit_or_blame"
    if evidence_kind == "treasury_payment_aggregate":
        return "official_treasury_payment_aggregate_review_no_merit_or_blame"
    if evidence_kind == "observed_outcome_series":
        return "official_observed_outcome_baseline_no_merit_or_blame"
    return "official_budget_indicator_review_no_merit_or_blame"


def review_status_for_kind(evidence_kind: str) -> str:
    return {
        "budget_plan": "reviewed_budget_plan_linked_execution_pending",
        "contract_award": "reviewed_contract_award_linked_outcome_pending",
        "grant_award": "reviewed_grant_award_linked_delivery_outcome_pending",
        "treasury_payment_aggregate": "reviewed_treasury_payment_aggregate_linked_delivery_outcome_pending",
        "indicator_target": "reviewed_indicator_target_linked_observed_outcome_pending",
        "observed_outcome_series": "reviewed_observed_outcome_baseline_post_change_pending",
    }.get(evidence_kind, "draft_needs_human_review")


def interpretation_status_for_kind(evidence_kind: str) -> str:
    return {
        "budget_plan": "budget_plan_only_execution_beneficiaries_and_outcomes_pending",
        "contract_award": "contract_award_only_delivery_beneficiaries_and_outcomes_pending",
        "grant_award": "grant_award_only_beneficiaries_delivery_and_outcomes_pending",
        "treasury_payment_aggregate": "treasury_payment_aggregate_only_beneficiaries_delivery_and_outcomes_pending",
        "indicator_target": "indicator_target_only_observed_outcome_series_pending",
        "observed_outcome_series": "observed_outcome_series_pre_2026_baseline_only_post_change_pending",
    }.get(evidence_kind, "draft_needs_human_review")


def limitations_for_kind(evidence_kind: str) -> list[str]:
    if evidence_kind == "contract_award":
        return [
            "contract_award_not_final_delivery",
            "beneficiaries_not_linked",
            "observed_outcome_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ]
    if evidence_kind == "indicator_target":
        return [
            "indicator_target_not_observed_outcome",
            "baseline_not_linked",
            "post_period_result_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ]
    if evidence_kind == "grant_award":
        return [
            "grant_award_not_final_delivery",
            "observed_outcome_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ]
    if evidence_kind == "treasury_payment_aggregate":
        return [
            "treasury_payment_aggregate_not_beneficiary_level",
            "final_delivery_not_linked",
            "observed_outcome_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ]
    if evidence_kind == "observed_outcome_series":
        return [
            "observed_outcome_series_not_actor_linked",
            "post_period_result_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ]
    return [
        "budget_plan_not_execution",
        "beneficiaries_not_linked",
        "observed_outcome_not_linked",
        "causal_impact_not_claimed",
        "merit_blame_not_scored",
    ]


def reviewed_label(candidate: dict[str, Any], evidence_kind: str) -> str:
    if evidence_kind == "contract_award":
        return str(candidate.get("contract_object") or candidate.get("summary") or "Contract award candidate")
    if evidence_kind == "grant_award":
        return str(candidate.get("grant_finality") or candidate.get("grant_announcement") or candidate.get("summary") or "Grant award candidate")
    if evidence_kind == "treasury_payment_aggregate":
        return str(candidate.get("treasury_hierarchy_3") or candidate.get("summary") or "Treasury payment aggregate candidate")
    if evidence_kind in {"indicator_target", "observed_outcome_series"}:
        return str(candidate.get("indicator_name") or candidate.get("summary") or "Indicator candidate")
    return str(
        candidate.get("budget_project")
        or candidate.get("budget_item")
        or candidate.get("summary")
        or "Budget-plan candidate"
    )


def evidence_excerpt(candidate: dict[str, Any], evidence_kind: str) -> str:
    if evidence_kind == "contract_award":
        parts = [
            str(candidate.get("contract_reference") or "").strip(),
            str(candidate.get("contract_object") or candidate.get("summary") or "").strip(),
            str(candidate.get("contracting_body") or "").strip(),
        ]
        amount = candidate.get("amount_eur")
        if amount not in (None, ""):
            parts.append(f"importe {amount} EUR")
        return "; ".join(part for part in parts if part)
    if evidence_kind == "grant_award":
        parts = [
            str(candidate.get("grant_date") or "").strip(),
            str(candidate.get("grant_finality") or candidate.get("summary") or "").strip(),
            str(candidate.get("grant_beneficiary") or "").strip(),
            str(candidate.get("grant_organism") or "").strip(),
            str(candidate.get("program_code") or "").strip(),
        ]
        amount = candidate.get("amount_eur")
        if amount not in (None, ""):
            parts.append(f"importe {amount} EUR")
        return "; ".join(part for part in parts if part)
    if evidence_kind == "treasury_payment_aggregate":
        parts = [
            str(candidate.get("treasury_year") or "").strip(),
            str(candidate.get("treasury_month") or "").strip(),
            str(candidate.get("treasury_hierarchy_1") or "").strip(),
            str(candidate.get("treasury_hierarchy_2") or "").strip(),
            str(candidate.get("treasury_hierarchy_3") or "").strip(),
        ]
        amount = candidate.get("amount_eur")
        if amount not in (None, ""):
            parts.append(f"importe {amount} EUR")
        return "; ".join(part for part in parts if part)
    if evidence_kind == "observed_outcome_series":
        parts = [
            str(candidate.get("indicator_name") or candidate.get("summary") or "").strip(),
            str(candidate.get("outcome_territory") or "").strip(),
            str(candidate.get("outcome_year") or "").strip(),
        ]
        value = str(candidate.get("outcome_value_format") or candidate.get("outcome_value") or "").strip()
        unit = str(candidate.get("indicator_unit") or "").strip()
        context = str(candidate.get("outcome_dimension_context") or "").strip()
        if value or unit:
            parts.append(f"valor {value} {unit}".strip())
        if context:
            parts.append(context)
        return "; ".join(part for part in parts if part)
    if evidence_kind == "indicator_target":
        parts = [
            str(candidate.get("program_code") or "").strip(),
            str(candidate.get("program_name") or "").strip(),
            str(candidate.get("indicator_name") or candidate.get("summary") or "").strip(),
        ]
        prevision = str(candidate.get("indicator_prevision") or "").strip()
        unit = str(candidate.get("indicator_unit") or "").strip()
        if prevision or unit:
            parts.append(f"prevision {prevision} {unit}".strip())
        return "; ".join(part for part in parts if part)
    parts = [
        str(candidate.get("program_code") or "").strip(),
        str(candidate.get("program_name") or "").strip(),
        str(candidate.get("budget_project") or candidate.get("budget_item") or candidate.get("summary") or "").strip(),
    ]
    amount = candidate.get("amount_eur")
    if amount not in (None, ""):
        parts.append(f"importe {amount} EUR")
    return "; ".join(part for part in parts if part)


def review_summary(candidate: dict[str, Any], evidence_kind: str) -> str:
    label = reviewed_label(candidate, evidence_kind)
    if evidence_kind == "contract_award":
        state = str(candidate.get("contract_state") or "").strip()
        award_code = str(candidate.get("contract_award_code") or "").strip()
        award_dates = [
            str(candidate.get("contract_award_formalization_date") or ""),
            str(candidate.get("contract_award_resolution_date") or ""),
            str(candidate.get("award_date") or ""),
        ]
        award_dates = [date for date in award_dates if date]
        vendor = str(candidate.get("contract_award_vendor") or "").strip()
        extras = []
        if state:
            extras.append(f"estado administrativo {state}")
        if award_code:
            extras.append(f"señal de adjudicación {award_code}")
        if award_dates:
            extras.append(f"fechas {', '.join(award_dates)}")
        if vendor:
            extras.append(f"adjudicatario {vendor}")
        extra_msg = ""
        if extras:
            extra_msg = " " + ". ".join(extras) + "."
        return (
            f"Machine draft from an official procurement candidate for {label}. "
            f"It may document an award signal.{extra_msg} It does not prove final delivery, beneficiaries, outcome, merit or blame."
        )
    if evidence_kind == "indicator_target":
        return (
            f"Machine draft from an official budget-indicator candidate for {label}. "
            "It may document a target or prevision, not an observed post-change outcome, merit or blame."
        )
    if evidence_kind == "observed_outcome_series":
        return (
            f"Machine draft from an official outcome-series candidate for {label}. "
            "It needs actor, timing and causal review before any accountability claim."
        )
    if evidence_kind == "grant_award":
        return (
            f"Machine draft from an official grant-award candidate for {label}. "
            "It may document a beneficiary and amount, not final delivery, observed outcome, merit or blame."
        )
    if evidence_kind == "treasury_payment_aggregate":
        return (
            f"Machine draft from an official Treasury payment aggregate for {label}. "
            "It may document monthly aggregate payment volume, not beneficiary-level delivery, outcome, merit or blame."
        )
    return (
        f"Machine draft from an official budget candidate for {label}. "
        "It may document planned allocation, not executed spend, delivery, outcome, merit or blame."
    )


def compact_draft_row(
    candidate: dict[str, Any],
    *,
    topic_label: str,
    reviewed_at: str,
    evidence_kind: str,
) -> dict[str, Any]:
    review_confidence = review_confidence_for_kind(candidate, evidence_kind)
    claim_status = claim_status_for_kind(evidence_kind)
    return {
        "review_item_id": stable_slug(
            "andalucia-2026-execution-draft:"
            f"{candidate.get('topic_id')}:{candidate.get('gap_id')}:{candidate.get('source_id')}:"
            f"{candidate.get('source_locator')}"
        ),
        "candidate_row_id": str(candidate.get("candidate_row_id") or ""),
        "topic_id": str(candidate.get("topic_id") or ""),
        "topic_label": topic_label,
        "gap_id": str(candidate.get("gap_id") or ""),
        "source_id": str(candidate.get("source_id") or ""),
        "source_kind": str(candidate.get("source_kind") or ""),
        "source_url": str(candidate.get("source_url") or ""),
        "source_locator": str(candidate.get("source_locator") or ""),
        "evidence_kind": evidence_kind,
        "draft_status": "machine_draft_needs_human_review",
        "review_status": review_status_for_kind(evidence_kind),
        "claim_status": claim_status,
        "interpretation_status": interpretation_status_for_kind(evidence_kind),
        "reviewed_label": reviewed_label(candidate, evidence_kind),
        "program_code": str(candidate.get("program_code") or ""),
        "program_name": str(candidate.get("program_name") or ""),
        "org_section": str(candidate.get("org_section") or ""),
        "org_service": str(candidate.get("org_service") or ""),
        "policy_area": str(candidate.get("policy_area") or ""),
        "budget_item": str(candidate.get("budget_item") or ""),
        "budget_project": str(candidate.get("budget_project") or ""),
        "contract_object": str(candidate.get("contract_object") or ""),
        "contracting_body": str(candidate.get("contracting_body") or ""),
        "contract_reference": str(candidate.get("contract_reference") or ""),
        "contract_type": str(candidate.get("contract_type") or ""),
        "award_date": str(candidate.get("award_date") or ""),
        "contract_state": str(candidate.get("contract_state") or ""),
        "contract_award_code": str(candidate.get("contract_award_code") or ""),
        "contract_award_formalization_date": str(candidate.get("contract_award_formalization_date") or ""),
        "contract_award_resolution_date": str(candidate.get("contract_award_resolution_date") or ""),
        "contract_award_vendor": str(candidate.get("contract_award_vendor") or ""),
        "contract_award_vendor_nif": str(candidate.get("contract_award_vendor_nif") or ""),
        "contract_award_amount": candidate.get("contract_award_amount"),
        "contract_awards_total": int(candidate.get("contract_awards_total") or 0),
        "place": str(candidate.get("place") or ""),
        "grant_beneficiary": str(candidate.get("grant_beneficiary") or ""),
        "grant_announcement": str(candidate.get("grant_announcement") or ""),
        "grant_finality": str(candidate.get("grant_finality") or ""),
        "grant_date": str(candidate.get("grant_date") or ""),
        "grant_year": str(candidate.get("grant_year") or ""),
        "grant_type": str(candidate.get("grant_type") or ""),
        "grant_organism": str(candidate.get("grant_organism") or ""),
        "budget_application": str(candidate.get("budget_application") or ""),
        "regulatory_base": str(candidate.get("regulatory_base") or ""),
        "treasury_year": str(candidate.get("treasury_year") or ""),
        "treasury_month": str(candidate.get("treasury_month") or ""),
        "treasury_hierarchy_1": str(candidate.get("treasury_hierarchy_1") or ""),
        "treasury_hierarchy_2": str(candidate.get("treasury_hierarchy_2") or ""),
        "treasury_hierarchy_3": str(candidate.get("treasury_hierarchy_3") or ""),
        "amount_eur": candidate.get("amount_eur"),
        "indicator_name": str(candidate.get("indicator_name") or ""),
        "indicator_prevision": str(candidate.get("indicator_prevision") or ""),
        "indicator_unit": str(candidate.get("indicator_unit") or ""),
        "outcome_territory": str(candidate.get("outcome_territory") or ""),
        "outcome_year": str(candidate.get("outcome_year") or ""),
        "outcome_value": str(candidate.get("outcome_value") or ""),
        "outcome_value_format": str(candidate.get("outcome_value_format") or ""),
        "outcome_periodicity": str(candidate.get("outcome_periodicity") or ""),
        "outcome_status": str(candidate.get("outcome_status") or ""),
        "outcome_dimension_context": str(candidate.get("outcome_dimension_context") or ""),
        "outcome_first_year": str(candidate.get("outcome_first_year") or ""),
        "outcome_first_value": str(candidate.get("outcome_first_value") or ""),
        "outcome_first_value_format": str(candidate.get("outcome_first_value_format") or ""),
        "outcome_baseline_year": str(candidate.get("outcome_baseline_year") or ""),
        "outcome_baseline_value": str(candidate.get("outcome_baseline_value") or ""),
        "outcome_baseline_value_format": str(candidate.get("outcome_baseline_value_format") or ""),
        "outcome_latest_year": str(candidate.get("outcome_latest_year") or ""),
        "outcome_latest_value": str(candidate.get("outcome_latest_value") or ""),
        "outcome_latest_value_format": str(candidate.get("outcome_latest_value_format") or ""),
        "outcome_post_change_status": str(candidate.get("outcome_post_change_status") or ""),
        "outcome_post_change_rows_total": int(candidate.get("outcome_post_change_rows_total") or 0),
        "outcome_next_post_change_check_year": str(candidate.get("outcome_next_post_change_check_year") or ""),
        "review_summary": review_summary(candidate, evidence_kind),
        "review_confidence": review_confidence,
        "reviewed_by": "draft_generator",
        "reviewed_at": reviewed_at,
        "source_evidence": [
            {
                "source_kind": str(candidate.get("source_kind") or ""),
                "source_locator": str(candidate.get("source_locator") or ""),
                "evidence_excerpt": evidence_excerpt(candidate, evidence_kind),
            }
        ],
        "open_limitations": limitations_for_kind(evidence_kind),
    }


def generate_draft_execution_evidence_reviews(
    accountability: dict[str, Any],
    *,
    existing_keys: set[str],
    reviewed_at: str,
    max_drafts_per_item: int,
    include_reviewed: bool = False,
) -> dict[str, Any]:
    queue_items = (accountability.get("issue_execution_evidence_queue") or {}).get("queue") or []
    drafts: list[dict[str, Any]] = []
    skipped_existing = 0
    skipped_unsupported = 0
    skipped_over_limit = 0

    for item in queue_items:
        if not isinstance(item, dict):
            continue
        item_drafts = 0
        topic_label = str(item.get("topic_label") or "")
        gap_id = str(item.get("gap_id") or "")
        eligible_candidates: list[tuple[dict[str, Any], str]] = []
        for candidate in item.get("official_candidate_rows") or []:
            if not isinstance(candidate, dict):
                continue
            candidate_key = review_locator_key(candidate)
            if not include_reviewed and candidate_key in existing_keys:
                skipped_existing += 1
                continue
            evidence_kind = evidence_kind_for_candidate(candidate, gap_id)
            if not evidence_kind:
                skipped_unsupported += 1
                continue
            eligible_candidates.append((candidate, evidence_kind))
        eligible_candidates.sort(key=lambda row: draft_candidate_sort_key(row[0], gap_id, row[1]))
        for candidate, evidence_kind in eligible_candidates:
            if item_drafts >= max(0, max_drafts_per_item):
                skipped_over_limit += 1
                continue
            draft = compact_draft_row(
                candidate,
                topic_label=topic_label,
                reviewed_at=reviewed_at,
                evidence_kind=evidence_kind,
            )
            if draft["claim_status"] not in NO_MERIT_CLAIM_STATUSES:
                raise RuntimeError(f"Unsafe draft claim_status: {draft['claim_status']}")
            drafts.append(draft)
            item_drafts += 1

    return {
        "schema_version": "andalucia_2026_execution_evidence_review_drafts_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reviewed_at": reviewed_at,
        "generator": "scripts/generate_andalucia_2026_execution_review_drafts.py",
        "review_policy": (
            "Machine drafts only. Promote manually after checking the official row. "
            "Drafts must not publish merit, blame, causality, final delivery or outcome claims."
        ),
        "status": "drafts_ready" if drafts else "no_drafts",
        "drafts_total": len(drafts),
        "skipped_existing_reviews_total": skipped_existing,
        "skipped_unsupported_candidates_total": skipped_unsupported,
        "skipped_over_limit_total": skipped_over_limit,
        "drafts_by_topic": dict(sorted({row["topic_id"]: 0 for row in drafts}.items())),
        "drafts": drafts,
    }


def add_topic_counts(payload: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in payload.get("drafts") or []:
        topic_id = str(row.get("topic_id") or "")
        if topic_id:
            counts[topic_id] = counts.get(topic_id, 0) + 1
    payload["drafts_by_topic"] = dict(sorted(counts.items()))
    return payload


def main() -> int:
    args = parse_args()
    reviewed_at = args.reviewed_at or datetime.now(UTC).date().isoformat()
    accountability = load_json_object(Path(args.accountability))
    existing_reviews = load_json_object(Path(args.existing_reviews)) if Path(args.existing_reviews).exists() else {}
    payload = generate_draft_execution_evidence_reviews(
        accountability,
        existing_keys=existing_review_keys(existing_reviews),
        reviewed_at=reviewed_at,
        max_drafts_per_item=args.max_drafts_per_item,
        include_reviewed=bool(args.include_reviewed),
    )
    add_topic_counts(payload)
    changed = write_json(Path(args.out), payload)
    print(
        "OK Andalucia 2026 execution review drafts -> {out} ({state}); drafts={drafts} skipped_existing={existing} skipped_unsupported={unsupported}".format(
            out=args.out,
            state="updated" if changed else "unchanged",
            drafts=payload["drafts_total"],
            existing=payload["skipped_existing_reviews_total"],
            unsupported=payload["skipped_unsupported_candidates_total"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
