#!/usr/bin/env python3
"""Classify delivery-evidence hunt candidates into confirmations and drafts.

The delivery hunt finds official registry rows. This script reduces review work
by matching exact machine-readable registry results back to already reviewed
execution evidence. Unmatched high-confidence registry rows become conservative
draft reviews. Broad beneficiary-only BDNS rows stay explicit as skipped noise.
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

from scripts.export_andalucia_2026_accountability_snapshot import normalize_label, stable_slug, write_json
from scripts.generate_andalucia_2026_execution_review_drafts import (
    NO_MERIT_CLAIM_STATUSES,
    compact_draft_row,
    existing_review_keys,
)


DEFAULT_HUNT_RESULTS = Path("etl/data/published/andalucia-2026-delivery-evidence-hunt-results.json")
DEFAULT_EXISTING_REVIEWS = Path("etl/data/seeds/andalucia_2026_execution_evidence_reviews.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-delivery-evidence-review-drafts.json")
DEFAULT_PUBLIC_OUT = Path("ui/gh-pages-next/public/elecciones/andalucia-2026/data/delivery-evidence-review-drafts.json")

BROAD_BDNS_VARIANTS = {"concession_beneficiary_only"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Andalucia 2026 delivery-evidence review confirmations and drafts"
    )
    parser.add_argument("--hunt-results", default=str(DEFAULT_HUNT_RESULTS), help="Delivery hunt results JSON")
    parser.add_argument("--existing-reviews", default=str(DEFAULT_EXISTING_REVIEWS), help="Existing execution reviews seed")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Published confirmation/draft JSON output")
    parser.add_argument("--public-out", default=str(DEFAULT_PUBLIC_OUT), help="Static UI JSON output")
    parser.add_argument("--reviewed-at", default="", help="Override reviewed_at/generator date")
    parser.add_argument("--include-broad-bdns", action="store_true", help="Allow beneficiary-only BDNS concession drafts")
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def money_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def amount_matches(left: Any, right: Any) -> bool:
    left_num = money_value(left)
    right_num = money_value(right)
    if left_num is None or right_num is None:
        return False
    return abs(left_num - right_num) <= max(1.0, abs(left_num) * 0.0001)


def normalized_contains(left: str, right: str) -> bool:
    left_norm = normalize_label(left)
    right_norm = normalize_label(right)
    return bool(left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm))


def existing_contract_reviews(reviews_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in reviews_payload.get("reviews") or []:
        if not isinstance(row, dict):
            continue
        reference = normalize_label(row.get("contract_reference"))
        if reference:
            rows[reference] = row
    return rows


def existing_grant_reviews(reviews_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in reviews_payload.get("reviews") or []
        if isinstance(row, dict) and str(row.get("evidence_kind") or "") == "grant_award"
    ]


def match_existing_grant_review(
    *,
    target: dict[str, Any],
    candidate: dict[str, Any],
    grant_reviews: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    topic_id = str(target.get("topic_id") or "")
    target_beneficiary = str(target.get("grant_beneficiary") or "")
    reviewed_label = str(target.get("reviewed_label") or "")
    candidate_title = str(candidate.get("title") or "")
    candidate_beneficiary = str(candidate.get("beneficiario") or "")
    for review in grant_reviews:
        if str(review.get("topic_id") or "") != topic_id:
            continue
        if not amount_matches(candidate.get("importe"), review.get("amount_eur")):
            continue
        review_beneficiary = str(review.get("grant_beneficiary") or "")
        review_finality = str(review.get("grant_finality") or review.get("reviewed_label") or "")
        beneficiary_ok = normalized_contains(target_beneficiary, review_beneficiary) or normalized_contains(
            candidate_beneficiary,
            review_beneficiary,
        )
        title_ok = normalized_contains(reviewed_label, review_finality) or normalized_contains(
            review_finality,
            candidate_title,
        )
        if beneficiary_ok and title_ok:
            return review, "topic_beneficiary_amount_and_finality"
    return None, ""


def delivery_candidate_id(target: dict[str, Any], candidate: dict[str, Any]) -> str:
    return stable_slug(
        "andalucia-2026-delivery-candidate:"
        f"{target.get('topic_id')}:{target.get('hunt_id')}:{candidate.get('candidate_id')}:"
        f"{candidate.get('cod_concesion') or candidate.get('numero_expediente') or candidate.get('url')}"
    )


def candidate_source_locator(candidate: dict[str, Any]) -> str:
    candidate_type = str(candidate.get("candidate_type") or "")
    if candidate_type == "contract":
        return f"junta-pdc-elastic:id-expediente:{candidate.get('id_expediente') or candidate.get('numero_expediente')}"
    if candidate_type == "concession":
        return f"bdns:concesion:{candidate.get('cod_concesion') or candidate.get('bdns_concession_id')}"
    return f"{candidate.get('registry') or 'official-registry'}:{candidate.get('candidate_id') or candidate.get('url')}"


def mapped_contract_candidate(target: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    awards = [row for row in candidate.get("adjudicaciones") or [] if isinstance(row, dict)]
    first_award = awards[0] if awards else {}
    award_code = str(first_award.get("codigo_resultado") or "")
    award_formalization_date = str(first_award.get("fecha_formalizacion") or "")
    award_resolution_date = str(first_award.get("fecha_resolucion") or "")
    award_vendor_name = str(first_award.get("nombre_adjudicatario") or "")
    award_vendor_nif = str(first_award.get("nif_adjudicatario") or "")
    award_amount = first_award.get("importe_adjudicacion")
    contract_state = str(candidate.get("estado") or "")
    amount = first_award.get("importe_adjudicacion") or candidate.get("importe_licitacion")
    return {
        "candidate_row_id": delivery_candidate_id(target, candidate),
        "topic_id": str(target.get("topic_id") or ""),
        "gap_id": "missing_budget_execution",
        "source_id": "junta_procurement_registry_elastic",
        "source_kind": "official_procurement_registry_json",
        "source_url": str(candidate.get("url") or candidate.get("api_url") or ""),
        "source_locator": candidate_source_locator(candidate),
        "contract_object": str(candidate.get("title") or target.get("reviewed_label") or ""),
        "contracting_body": str(candidate.get("perfil_contratante") or ""),
        "contract_reference": str(candidate.get("numero_expediente") or target.get("contract_reference") or ""),
        "contract_type": str(candidate.get("tipo_contrato") or ""),
        "award_date": str(first_award.get("fecha_formalizacion") or first_award.get("fecha_resolucion") or ""),
        "amount_eur": amount,
        "contract_state": contract_state,
        "contract_award_code": award_code,
        "contract_award_formalization_date": award_formalization_date,
        "contract_award_resolution_date": award_resolution_date,
        "contract_award_vendor": award_vendor_name,
        "contract_award_vendor_nif": award_vendor_nif,
        "contract_award_amount": award_amount,
        "contract_awards_total": int(candidate.get("adjudicaciones_total") or len(awards) or 0),
        "summary": str(candidate.get("title") or ""),
    }


def mapped_grant_candidate(target: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_row_id": delivery_candidate_id(target, candidate),
        "topic_id": str(target.get("topic_id") or ""),
        "gap_id": "missing_budget_execution",
        "source_id": "bdns_concesiones_api",
        "source_kind": "official_grant_registry_json",
        "source_url": str(candidate.get("url") or candidate.get("api_url") or ""),
        "source_locator": candidate_source_locator(candidate),
        "program_code": str(target.get("program_code") or ""),
        "grant_beneficiary": str(candidate.get("beneficiario") or target.get("grant_beneficiary") or ""),
        "grant_announcement": str(candidate.get("title") or ""),
        "grant_finality": str(target.get("reviewed_label") or candidate.get("title") or ""),
        "grant_date": str(candidate.get("fecha_concesion") or candidate.get("fecha_alta") or ""),
        "grant_type": str(candidate.get("instrumento") or ""),
        "grant_organism": str(candidate.get("nivel3") or ""),
        "amount_eur": candidate.get("importe"),
        "summary": str(candidate.get("title") or ""),
    }


def confirmation_row(
    *,
    target: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
    match_basis: str,
) -> dict[str, Any]:
    candidate_type = str(candidate.get("candidate_type") or "")
    reference = (
        str(candidate.get("numero_expediente") or "")
        if candidate_type == "contract"
        else str(candidate.get("cod_concesion") or candidate.get("numero_convocatoria") or "")
    )
    return {
        "confirmation_id": stable_slug(
            "andalucia-2026-delivery-confirmation:"
            f"{review.get('review_item_id')}:{candidate.get('candidate_id')}:{reference}"
        ),
        "confirmation_status": "official_registry_match_existing_review",
        "match_basis": match_basis,
        "review_item_id": str(review.get("review_item_id") or ""),
        "topic_id": str(target.get("topic_id") or review.get("topic_id") or ""),
        "topic_label": str(target.get("topic_label") or ""),
        "hunt_id": str(target.get("hunt_id") or ""),
        "registry": str(target.get("registry") or candidate.get("registry") or ""),
        "candidate_type": candidate_type,
        "evidence_kind": str(review.get("evidence_kind") or ""),
        "reviewed_label": str(review.get("reviewed_label") or target.get("reviewed_label") or candidate.get("title") or ""),
        "matched_reference": reference,
        "official_title": str(candidate.get("title") or ""),
        "official_url": str(candidate.get("url") or ""),
        "api_url": str(candidate.get("api_url") or ""),
        "boja_url": str(candidate.get("boja_url") or ""),
        "source_locator": candidate_source_locator(candidate),
        "amount_eur": candidate.get("importe") or candidate.get("importe_licitacion"),
        "machine_readable": bool(candidate.get("machine_readable")),
    }


def skipped_candidate_row(
    *,
    target: dict[str, Any],
    candidate: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "topic_id": str(target.get("topic_id") or ""),
        "registry": str(target.get("registry") or candidate.get("registry") or ""),
        "candidate_type": str(candidate.get("candidate_type") or ""),
        "reason": reason,
        "title": str(candidate.get("title") or ""),
        "source_locator": candidate_source_locator(candidate),
    }


def add_counts(payload: dict[str, Any]) -> dict[str, Any]:
    confirmations_by_topic: dict[str, int] = {}
    drafts_by_topic: dict[str, int] = {}
    for row in payload.get("confirmations") or []:
        topic_id = str(row.get("topic_id") or "")
        if topic_id:
            confirmations_by_topic[topic_id] = confirmations_by_topic.get(topic_id, 0) + 1
    for row in payload.get("drafts") or []:
        topic_id = str(row.get("topic_id") or "")
        if topic_id:
            drafts_by_topic[topic_id] = drafts_by_topic.get(topic_id, 0) + 1
    payload["confirmations_by_topic"] = dict(sorted(confirmations_by_topic.items()))
    payload["drafts_by_topic"] = dict(sorted(drafts_by_topic.items()))
    return payload


def generate_delivery_review_drafts(
    hunt_results: dict[str, Any],
    existing_reviews: dict[str, Any],
    *,
    reviewed_at: str,
    include_broad_bdns: bool = False,
) -> dict[str, Any]:
    contract_reviews = existing_contract_reviews(existing_reviews)
    grant_reviews = existing_grant_reviews(existing_reviews)
    existing_keys = existing_review_keys(existing_reviews)
    confirmations: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    machine_candidates_total = 0

    for target in hunt_results.get("targets") or []:
        if not isinstance(target, dict):
            continue
        for candidate in target.get("result_candidates") or []:
            if not isinstance(candidate, dict) or not candidate.get("machine_readable"):
                continue
            machine_candidates_total += 1
            candidate_type = str(candidate.get("candidate_type") or "")
            if candidate_type not in {"contract", "concession"}:
                skipped.append(
                    skipped_candidate_row(target=target, candidate=candidate, reason="unsupported_candidate_type")
                )
                continue
            if candidate_type == "contract":
                reference = normalize_label(candidate.get("numero_expediente") or target.get("contract_reference"))
                review = contract_reviews.get(reference)
                if review:
                    confirmations.append(
                        confirmation_row(
                            target=target,
                            candidate=candidate,
                            review=review,
                            match_basis="contract_reference",
                        )
                    )
                    continue
                mapped = mapped_contract_candidate(target, candidate)
                evidence_kind = "contract_award"
            else:
                matched_variant = str(candidate.get("matched_query_variant") or "")
                review, match_basis = match_existing_grant_review(
                    target=target,
                    candidate=candidate,
                    grant_reviews=grant_reviews,
                )
                if review:
                    confirmations.append(
                        confirmation_row(
                            target=target,
                            candidate=candidate,
                            review=review,
                            match_basis=match_basis,
                        )
                    )
                    continue
                if matched_variant in BROAD_BDNS_VARIANTS and not include_broad_bdns:
                    skipped.append(
                        skipped_candidate_row(
                            target=target,
                            candidate=candidate,
                            reason="broad_beneficiary_only_bdns_result",
                        )
                    )
                    continue
                mapped = mapped_grant_candidate(target, candidate)
                evidence_kind = "grant_award"

            key = "|".join(
                [
                    mapped["topic_id"],
                    mapped["gap_id"],
                    mapped["source_id"],
                    mapped["source_locator"],
                ]
            )
            if key in existing_keys:
                skipped.append(
                    skipped_candidate_row(target=target, candidate=candidate, reason="duplicate_existing_locator")
                )
                continue
            draft = compact_draft_row(
                mapped,
                topic_label=str(target.get("topic_label") or ""),
                reviewed_at=reviewed_at,
                evidence_kind=evidence_kind,
            )
            draft["delivery_hunt_id"] = str(target.get("hunt_id") or "")
            draft["delivery_candidate_id"] = str(candidate.get("candidate_id") or "")
            draft["registry"] = str(target.get("registry") or candidate.get("registry") or "")
            if draft["claim_status"] not in NO_MERIT_CLAIM_STATUSES:
                raise RuntimeError(f"Unsafe delivery draft claim_status: {draft['claim_status']}")
            drafts.append(draft)

    payload = {
        "schema_version": "andalucia_2026_delivery_evidence_review_drafts_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reviewed_at": reviewed_at,
        "generator": "scripts/generate_andalucia_2026_delivery_review_drafts.py",
        "source_hunt_results": str(DEFAULT_HUNT_RESULTS),
        "review_policy": (
            "Classifies machine-readable delivery-hunt candidates. Confirmations only strengthen "
            "existing reviewed rows. Drafts still require human review and cannot publish merit, "
            "blame, causality, final delivery or outcome claims."
        ),
        "status": "confirmations_or_drafts_ready" if confirmations or drafts else "no_confirmations_or_drafts",
        "machine_candidates_total": machine_candidates_total,
        "confirmations_total": len(confirmations),
        "drafts_total": len(drafts),
        "skipped_candidates_total": len(skipped),
        "skipped_broad_bdns_total": sum(1 for row in skipped if row.get("reason") == "broad_beneficiary_only_bdns_result"),
        "confirmations": confirmations,
        "drafts": drafts,
        "skipped_candidates": skipped,
    }
    return add_counts(payload)


def main() -> int:
    args = parse_args()
    reviewed_at = args.reviewed_at or datetime.now(UTC).date().isoformat()
    hunt_results = load_json_object(Path(args.hunt_results))
    existing_reviews = load_json_object(Path(args.existing_reviews))
    payload = generate_delivery_review_drafts(
        hunt_results,
        existing_reviews,
        reviewed_at=reviewed_at,
        include_broad_bdns=bool(args.include_broad_bdns),
    )
    payload["source_hunt_results"] = args.hunt_results
    changed = write_json(Path(args.out), payload)
    public_changed = write_json(Path(args.public_out), payload)
    print(
        "OK Andalucia 2026 delivery review drafts -> {out} ({state}); confirmations={confirmations} drafts={drafts} skipped={skipped}".format(
            out=args.out,
            state="updated" if changed or public_changed else "unchanged",
            confirmations=payload["confirmations_total"],
            drafts=payload["drafts_total"],
            skipped=payload["skipped_candidates_total"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
