from __future__ import annotations

import unittest

from scripts.generate_andalucia_2026_issue_review_drafts import (
    eligible_issue_packet,
    generate_issue_review_drafts,
    unsafe_draft_reasons,
)


class TestGenerateAndalucia2026IssueReviewDrafts(unittest.TestCase):
    def test_generates_safe_direction_actor_draft_from_reviewed_vote_packet(self) -> None:
        accountability = {
            "issue_accountability_packets": {
                "packets": [
                    {
                        "topic_id": "sanidad",
                        "topic_label": "Sanidad",
                        "open_gaps": ["missing_citizen_direction", "missing_responsible_actor"],
                        "reviewed_vote_items_total": 1,
                        "reviewed_vote_boja_expected_total": 0,
                        "reviewed_vote_boja_not_expected_total": 1,
                        "reviewed_boja_legal_changes_total": 0,
                        "observed_responsibility_claims_total": 5,
                        "reviewed_vote_samples": [
                            {
                                "review_item_id": "vote-review-1",
                                "vote_event_id": "vote-event-1",
                                "numexp": "12-25/COM-000012",
                                "title": "Solicitud de comision de investigacion sanitaria",
                                "effect_outcome": "rejected_by_majority_no",
                                "source_url": "https://example.test/vote.pdf",
                            }
                        ],
                        "observed_responsibility_claim_samples": [
                            {
                                "claim_id": "claim-1",
                                "statement": "PP voto no en Sanidad; resultado oficial revisado.",
                                "source_url": "https://example.test/vote.pdf",
                            }
                        ],
                    },
                    {
                        "topic_id": "campo_agua",
                        "topic_label": "Campo y agua",
                        "open_gaps": ["missing_budget_execution"],
                        "reviewed_vote_items_total": 1,
                        "observed_responsibility_claims_total": 5,
                    },
                ]
            }
        }

        payload = generate_issue_review_drafts(
            accountability,
            existing_topics=set(),
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["status"], "drafts_ready")
        self.assertEqual(payload["drafts_total"], 1)
        draft = payload["drafts"][0]
        self.assertEqual(draft["topic_id"], "sanidad")
        self.assertEqual(draft["claim_status"], "issue_vote_direction_actor_review_no_merit_or_blame")
        self.assertEqual(draft["citizen_direction_status"], "direction_partially_reviewed_outcome_pending")
        self.assertEqual(draft["responsible_actor_status"], "responsible_actor_partially_observed")
        self.assertEqual(draft["execution_owner_status"], "execution_owner_not_reviewed")
        self.assertEqual(draft["budget_execution_status"], "budget_execution_not_linked")
        self.assertEqual(draft["outcome_status"], "outcome_not_linked")
        self.assertIn("merit_blame_not_scored", draft["open_limitations"])
        self.assertIn("causal_impact_not_claimed", draft["open_limitations"])
        self.assertEqual(unsafe_draft_reasons(draft), [])

    def test_skips_existing_reviewed_topic_and_missing_vote(self) -> None:
        packet = {
            "topic_id": "sanidad",
            "open_gaps": ["missing_citizen_direction"],
            "reviewed_vote_items_total": 0,
            "observed_responsibility_claims_total": 1,
        }
        eligible, reason = eligible_issue_packet(packet, existing_topics=set())
        self.assertFalse(eligible)
        self.assertEqual(reason, "reviewed_vote_missing")

        packet["reviewed_vote_items_total"] = 1
        eligible, reason = eligible_issue_packet(packet, existing_topics={"sanidad"})
        self.assertFalse(eligible)
        self.assertEqual(reason, "topic_already_has_issue_review")

    def test_blocks_draft_with_score_field(self) -> None:
        draft = {
            "claim_status": "issue_vote_direction_actor_review_no_merit_or_blame",
            "citizen_direction_status": "direction_partially_reviewed_outcome_pending",
            "responsible_actor_status": "responsible_actor_partially_observed",
            "execution_owner_status": "execution_owner_not_reviewed",
            "budget_execution_status": "budget_execution_not_linked",
            "outcome_status": "outcome_not_linked",
            "open_limitations": ["causal_impact_not_claimed", "merit_blame_not_scored"],
            "merit_score": 1,
        }

        self.assertIn("blocked_score_field:merit_score", unsafe_draft_reasons(draft))


if __name__ == "__main__":
    unittest.main()
