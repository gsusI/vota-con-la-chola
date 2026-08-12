from __future__ import annotations

import copy
import unittest

from scripts.apply_andalucia_2026_boja_review_drafts import apply_promoted_reviews, build_apply_plan


def safe_boja_draft(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_item_id": "boja-impact-review-test-1",
        "topic_id": "transparencia_corrupcion",
        "topic_label": "Transparencia y corrupcion",
        "boja_id": "disposition.2025.251.2",
        "fragment_id": "disposition.2025.251.2:body:2",
        "date": "31/12/2025",
        "organisation": "Presidencia",
        "type": "Leyes",
        "action_kind": "modifica_norma",
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_legal_change_only",
        "claim_status": "reviewed_boja_legal_change_no_merit_claim",
        "impact_status": "legal_change_documented_outcome_pending",
        "responsibility_status": "official_publisher_observed",
        "candidate_direction": "unknown",
        "reviewed_legal_change_label": "disposition.2025.251.2: modifica norma",
        "source_url": "https://juntadeandalucia.es/eboja/2025/251/test.pdf",
        "detail_url": "https://datos.juntadeandalucia.es/api/v0/boja/disposition.2025.251.2",
        "source_locator": "disposition.2025.251.2::body::2",
        "evidence_excerpt": "Modifica Ley 2/2021 de lucha contra el fraude y la corrupcion.",
        "review_summary": "Machine draft from the official BOJA impact-review queue.",
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": "2026-05-17",
        "source_evidence": [
            {
                "source_kind": "official_boja_text",
                "source_locator": "disposition.2025.251.2::body::2",
                "evidence_excerpt": "Modifica Ley 2/2021 de lucha contra el fraude y la corrupcion.",
            }
        ],
        "open_limitations": [
            "legal_change_only",
            "execution_owner_not_reviewed",
            "budget_execution_not_linked",
            "outcome_not_reviewed",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }
    row.update(overrides)
    return row


class TestApplyAndalucia2026BojaReviewDrafts(unittest.TestCase):
    def test_explicit_selection_dry_run_would_apply_without_mutating_seed(self) -> None:
        draft = safe_boja_draft()
        seed = {"schema_version": "reviews_v1", "reviews": []}
        seed_before = copy.deepcopy(seed)

        plan, promoted = build_apply_plan(
            {"schema_version": "drafts_v1", "drafts": [draft]},
            seed,
            review_item_ids=["boja-impact-review-test-1"],
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
            "promoted_from_machine_boja_draft_explicit_selection",
        )
        self.assertEqual(promoted[0]["review_status"], "reviewed_legal_change_only")

    def test_duplicate_review_item_is_skipped(self) -> None:
        draft = safe_boja_draft()
        seed = {"reviews": [{"review_item_id": "boja-impact-review-test-1"}]}

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            seed,
            review_item_ids=["boja-impact-review-test-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_duplicate_total"], 1)
        self.assertEqual(promoted, [])

    def test_unsafe_claim_status_is_blocked(self) -> None:
        draft = safe_boja_draft(claim_status="published_merit_claim")

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            {"reviews": []},
            review_item_ids=["boja-impact-review-test-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["blocked_unsafe_total"], 1)
        self.assertIn("claim_status_not_no_merit_or_blame", plan["actions"][0]["violations"])
        self.assertEqual(promoted, [])

    def test_all_requires_human_approved_unless_machine_drafts_are_allowed(self) -> None:
        draft = safe_boja_draft()

        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_unapproved_total"], 1)
        self.assertEqual(promoted, [])

    def test_apply_promoted_reviews_appends_seed_row(self) -> None:
        draft = safe_boja_draft(draft_status="human_approved")
        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        updated = apply_promoted_reviews(
            {
                "schema_version": "andalucia_2026_boja_impact_reviews_v1",
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
            "promoted_from_human_approved_boja_draft",
        )
        self.assertEqual(updated["reviewed_at"], "2026-05-16")


if __name__ == "__main__":
    unittest.main()
