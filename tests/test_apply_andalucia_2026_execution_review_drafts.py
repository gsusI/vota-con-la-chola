from __future__ import annotations

import copy
import unittest

from scripts.apply_andalucia_2026_execution_review_drafts import (
    apply_promoted_reviews,
    build_apply_plan,
)


def safe_draft(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_item_id": "andalucia-2026-execution-draft-educacion-budget-row-1",
        "candidate_row_id": "candidate-1",
        "topic_id": "educacion",
        "topic_label": "Educacion",
        "gap_id": "missing_budget_execution",
        "source_id": "junta_presupuesto_2026_partidas_gastos",
        "source_kind": "official_budget_open_data",
        "source_url": "https://example.test/budget.xlsx",
        "source_locator": "partidas-de-gastos.xlsx:fila 6811",
        "evidence_kind": "budget_plan",
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_budget_plan_linked_execution_pending",
        "claim_status": "official_budget_indicator_review_no_merit_or_blame",
        "interpretation_status": "budget_plan_only_execution_beneficiaries_and_outcomes_pending",
        "reviewed_label": "FINANCIACION BECAS",
        "amount_eur": 2000000,
        "review_summary": (
            "Machine draft from an official budget candidate. It may document planned "
            "allocation, not executed spend, delivery, outcome, merit or blame."
        ),
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": "2026-05-17",
        "source_evidence": [
            {
                "source_kind": "official_budget_open_data",
                "source_locator": "partidas-de-gastos.xlsx:fila 6811",
                "evidence_excerpt": "42J; UNIVERSIDADES; FINANCIACION BECAS; importe 2000000 EUR",
            }
        ],
        "open_limitations": [
            "budget_plan_not_execution",
            "beneficiaries_not_linked",
            "observed_outcome_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }
    row.update(overrides)
    return row


class TestApplyAndalucia2026ExecutionReviewDrafts(unittest.TestCase):
    def test_explicit_selection_dry_run_would_apply_without_mutating_seed(self) -> None:
        draft = safe_draft()
        drafts = {"schema_version": "drafts_v1", "drafts": [draft]}
        seed = {"schema_version": "reviews_v1", "reviews": []}
        seed_before = copy.deepcopy(seed)

        plan, promoted = build_apply_plan(
            drafts,
            seed,
            review_item_ids=["andalucia-2026-execution-draft-educacion-budget-row-1"],
        )

        self.assertEqual(plan["status"], "ready_to_apply")
        self.assertEqual(plan["selected_total"], 1)
        self.assertEqual(plan["would_apply_total"], 1)
        self.assertEqual(plan["blocked_unsafe_total"], 0)
        self.assertEqual(seed, seed_before)
        self.assertEqual(len(promoted), 1)
        self.assertNotIn("draft_status", promoted[0])
        self.assertEqual(
            promoted[0]["promotion_status"],
            "promoted_from_machine_draft_explicit_selection",
        )
        self.assertEqual(
            promoted[0]["promoted_from_review_item_id"],
            "andalucia-2026-execution-draft-educacion-budget-row-1",
        )

    def test_duplicate_locator_is_skipped(self) -> None:
        draft = safe_draft()
        seed = {
            "reviews": [
                {
                    "topic_id": "educacion",
                    "gap_id": "missing_budget_execution",
                    "source_id": "junta_presupuesto_2026_partidas_gastos",
                    "source_locator": "partidas-de-gastos.xlsx:fila 6811",
                }
            ]
        }

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            seed,
            review_item_ids=["andalucia-2026-execution-draft-educacion-budget-row-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_duplicate_total"], 1)
        self.assertEqual(promoted, [])

    def test_unsafe_claim_status_is_blocked(self) -> None:
        draft = safe_draft(claim_status="published_merit_claim")

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            {"reviews": []},
            review_item_ids=["andalucia-2026-execution-draft-educacion-budget-row-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["blocked_unsafe_total"], 1)
        self.assertIn("claim_status_not_no_merit_or_blame", plan["actions"][0]["violations"])
        self.assertEqual(promoted, [])

    def test_grant_award_status_is_safe_for_explicit_selection(self) -> None:
        draft = safe_draft(
            review_item_id="andalucia-2026-execution-draft-energia-grant-row-1",
            source_id="junta_subvenciones_programas_prioritarios",
            source_kind="official_grant_awards_open_data",
            source_locator="junta_subvenciones_programas_prioritarios.json:fila 1",
            evidence_kind="grant_award",
            review_status="reviewed_grant_award_linked_delivery_outcome_pending",
            claim_status="official_budget_grant_award_review_no_merit_or_blame",
            interpretation_status="grant_award_only_beneficiaries_delivery_and_outcomes_pending",
            reviewed_label="Calidad del aire y cambio climatico",
            open_limitations=[
                "grant_award_not_final_delivery",
                "observed_outcome_not_linked",
                "causal_impact_not_claimed",
                "merit_blame_not_scored",
            ],
        )

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            {"reviews": []},
            review_item_ids=["andalucia-2026-execution-draft-energia-grant-row-1"],
        )

        self.assertEqual(plan["status"], "ready_to_apply")
        self.assertEqual(plan["would_apply_total"], 1)
        self.assertEqual(plan["blocked_unsafe_total"], 0)
        self.assertEqual(promoted[0]["evidence_kind"], "grant_award")

    def test_treasury_payment_aggregate_status_is_safe_for_explicit_selection(self) -> None:
        draft = safe_draft(
            review_item_id="andalucia-2026-execution-draft-energia-treasury-row-1",
            source_id="junta_tesoreria_2025_pagos_agregados",
            source_kind="official_treasury_payment_aggregate_open_data",
            source_locator="tesoreria_2025_movimientos.7z:2025T4_PAGOS_4.CSV:fila 8",
            evidence_kind="treasury_payment_aggregate",
            review_status="reviewed_treasury_payment_aggregate_linked_delivery_outcome_pending",
            claim_status="official_treasury_payment_aggregate_review_no_merit_or_blame",
            interpretation_status="treasury_payment_aggregate_only_beneficiaries_delivery_and_outcomes_pending",
            reviewed_label="Consejería de Sostenibilidad, Medio Ambiente y Economía Azul",
            treasury_year="2025",
            treasury_month="01",
            open_limitations=[
                "treasury_payment_aggregate_not_beneficiary_level",
                "final_delivery_not_linked",
                "observed_outcome_not_linked",
                "causal_impact_not_claimed",
                "merit_blame_not_scored",
            ],
        )

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            {"reviews": []},
            review_item_ids=["andalucia-2026-execution-draft-energia-treasury-row-1"],
        )

        self.assertEqual(plan["status"], "ready_to_apply")
        self.assertEqual(plan["would_apply_total"], 1)
        self.assertEqual(plan["blocked_unsafe_total"], 0)
        self.assertEqual(promoted[0]["evidence_kind"], "treasury_payment_aggregate")

    def test_all_requires_human_approved_unless_machine_drafts_are_allowed(self) -> None:
        draft = safe_draft()

        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_unapproved_total"], 1)
        self.assertEqual(promoted, [])

    def test_apply_promoted_reviews_appends_seed_row(self) -> None:
        draft = safe_draft(draft_status="human_approved")
        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        updated = apply_promoted_reviews(
            {
                "schema_version": "andalucia_2026_execution_evidence_reviews_v1",
                "review_policy": "review policy",
                "reviewed_at": "2026-05-16",
                "reviews": [],
            },
            promoted,
        )

        self.assertEqual(plan["would_apply_total"], 1)
        self.assertEqual(len(updated["reviews"]), 1)
        self.assertNotIn("draft_status", updated["reviews"][0])
        self.assertEqual(
            updated["reviews"][0]["promotion_status"],
            "promoted_from_human_approved_draft",
        )
        self.assertEqual(updated["reviewed_at"], "2026-05-16")


if __name__ == "__main__":
    unittest.main()
