from __future__ import annotations

import unittest

from scripts.apply_andalucia_2026_issue_review_drafts import build_apply_plan


SAFE_DRAFT = {
    "review_id": "andalucia-2026-issue-review-draft-sanidad-001",
    "topic_id": "sanidad",
    "topic_label": "Sanidad",
    "draft_status": "machine_draft_needs_human_review",
    "review_status": "reviewed_issue_vote_direction_and_actor_partial",
    "claim_status": "issue_vote_direction_actor_review_no_merit_or_blame",
    "citizen_direction_status": "direction_partially_reviewed_outcome_pending",
    "responsible_actor_status": "responsible_actor_partially_observed",
    "execution_owner_status": "execution_owner_not_reviewed",
    "budget_execution_status": "budget_execution_not_linked",
    "outcome_status": "outcome_not_linked",
    "open_limitations": ["causal_impact_not_claimed", "merit_blame_not_scored"],
}


class TestApplyAndalucia2026IssueReviewDrafts(unittest.TestCase):
    def test_explicit_selection_can_promote_safe_machine_draft(self) -> None:
        plan, promoted = build_apply_plan(
            {"schema_version": "andalucia_2026_issue_review_drafts_v1", "drafts": [SAFE_DRAFT]},
            {"schema_version": "andalucia_2026_issue_reviews_v1", "reviews": []},
            review_ids=["andalucia-2026-issue-review-draft-sanidad-001"],
        )

        self.assertEqual(plan["status"], "ready_to_apply")
        self.assertEqual(plan["would_apply_total"], 1)
        self.assertEqual(plan["blocked_unsafe_total"], 0)
        self.assertEqual(len(promoted), 1)
        self.assertNotIn("draft_status", promoted[0])
        self.assertEqual(promoted[0]["promotion_status"], "promoted_from_machine_issue_draft_explicit_selection")

    def test_all_skips_machine_draft_without_allow_flag(self) -> None:
        plan, promoted = build_apply_plan(
            {"drafts": [SAFE_DRAFT]},
            {"reviews": []},
            include_all=True,
            allow_machine_drafts=False,
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_unapproved_total"], 1)
        self.assertEqual(promoted, [])

    def test_duplicate_topic_is_skipped(self) -> None:
        plan, promoted = build_apply_plan(
            {"drafts": [SAFE_DRAFT]},
            {"reviews": [{"topic_id": "sanidad"}]},
            review_ids=["andalucia-2026-issue-review-draft-sanidad-001"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["skipped_duplicate_total"], 1)
        self.assertEqual(promoted, [])

    def test_blocks_unsafe_score_field(self) -> None:
        unsafe = dict(SAFE_DRAFT)
        unsafe["merit_score"] = 1
        plan, promoted = build_apply_plan(
            {"drafts": [unsafe]},
            {"reviews": []},
            review_ids=["andalucia-2026-issue-review-draft-sanidad-001"],
        )

        self.assertEqual(plan["status"], "no_applicable_rows")
        self.assertEqual(plan["blocked_unsafe_total"], 1)
        self.assertIn("blocked_score_field:merit_score", plan["actions"][0]["violations"])
        self.assertEqual(promoted, [])


if __name__ == "__main__":
    unittest.main()
