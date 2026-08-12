from __future__ import annotations

import copy
import unittest

from scripts.apply_andalucia_2026_parliament_vote_review_drafts import (
    apply_promoted_reviews,
    build_apply_plan,
)


def safe_vote_draft(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_item_id": "parliament-vote-impact-review-test-1",
        "vote_event_id": "parlamento-andalucia-votacion-test-1",
        "topic_id": "vivienda",
        "topic_label": "Vivienda",
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_vote_result_only",
        "claim_status": "official_vote_result_review_no_merit_or_blame",
        "legal_effect_status": "observed_rejection_vote",
        "legal_effect_kind": "nonbinding_resolution_vote_rejected",
        "effect_outcome": "rejected_by_majority_no",
        "impact_status": "outcome_not_reviewed",
        "responsibility_status": "party_positions_observed",
        "candidate_direction": "unknown",
        "reviewed_issue_label": "Vivienda",
        "date": "12/03/2026",
        "vote_number": "25",
        "numexp": "12-26/PNLP-000026",
        "title": "Proposicion no de ley relativa a vivienda",
        "majority_side": "no",
        "total_si": 30,
        "total_no": 70,
        "total_abstenciones": 7,
        "review_summary": "Machine draft from the official parliament vote queue.",
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": "2026-05-17",
        "source_evidence": [
            {
                "source_kind": "official_vote_pdf_text",
                "source_locator": "documento-test::vote:25",
                "evidence_excerpt": "12-26/PNLP-000026; votacion numero 25; total si 30; total no 70",
            }
        ],
        "open_limitations": [
            "legal_effect_auto_triage_needs_human_review",
            "citizen_direction_not_reviewed",
            "outcome_not_reviewed",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }
    row.update(overrides)
    return row


class TestApplyAndalucia2026ParliamentVoteReviewDrafts(unittest.TestCase):
    def test_explicit_selection_dry_run_would_apply_without_mutating_seed(self) -> None:
        draft = safe_vote_draft()
        seed = {"schema_version": "reviews_v1", "reviews": []}
        seed_before = copy.deepcopy(seed)

        plan, promoted = build_apply_plan(
            {"schema_version": "drafts_v1", "drafts": [draft]},
            seed,
            review_item_ids=["parliament-vote-impact-review-test-1"],
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
            "promoted_from_machine_vote_draft_explicit_selection",
        )
        self.assertEqual(promoted[0]["review_status"], "reviewed_vote_result_only")

    def test_duplicate_vote_event_is_skipped(self) -> None:
        draft = safe_vote_draft()
        seed = {"reviews": [{"vote_event_id": "parlamento-andalucia-votacion-test-1"}]}

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            seed,
            review_item_ids=["parliament-vote-impact-review-test-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_duplicate_total"], 1)
        self.assertEqual(promoted, [])

    def test_unsafe_claim_status_is_blocked(self) -> None:
        draft = safe_vote_draft(claim_status="published_merit_claim")

        plan, promoted = build_apply_plan(
            {"drafts": [draft]},
            {"reviews": []},
            review_item_ids=["parliament-vote-impact-review-test-1"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["blocked_unsafe_total"], 1)
        self.assertIn("claim_status_not_no_merit_or_blame", plan["actions"][0]["violations"])
        self.assertEqual(promoted, [])

    def test_all_requires_human_approved_unless_machine_drafts_are_allowed(self) -> None:
        draft = safe_vote_draft()

        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_unapproved_total"], 1)
        self.assertEqual(promoted, [])

    def test_apply_promoted_reviews_appends_seed_row(self) -> None:
        draft = safe_vote_draft(draft_status="human_approved")
        plan, promoted = build_apply_plan({"drafts": [draft]}, {"reviews": []}, include_all=True)

        updated = apply_promoted_reviews(
            {
                "schema_version": "andalucia_2026_parliament_vote_reviews_v1",
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
            "promoted_from_human_approved_vote_draft",
        )
        self.assertEqual(updated["reviewed_at"], "2026-05-16")


if __name__ == "__main__":
    unittest.main()
