from __future__ import annotations

import unittest

from scripts.generate_andalucia_2026_boja_review_drafts import (
    existing_review_keys,
    generate_draft_boja_reviews,
)


def boja_item(**overrides: object) -> dict[str, object]:
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
        "priority_rank": 21,
        "priority_score": 68,
        "source_url": "https://juntadeandalucia.es/eboja/2025/251/test.pdf",
        "detail_url": "https://datos.juntadeandalucia.es/api/v0/boja/disposition.2025.251.2",
        "source_locator": "disposition.2025.251.2::body::2",
        "evidence_excerpt": (
            "La disposicion final octava modifica el articulo 32 de la Ley 2/2021, "
            "de lucha contra el fraude y la corrupcion en Andalucia."
        ),
    }
    row.update(overrides)
    return row


class TestGenerateAndalucia2026BojaReviewDrafts(unittest.TestCase):
    def test_generates_safe_drafts_for_boja_blocked_topics_and_skips_existing(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [
                    {"topic_id": "transparencia_corrupcion", "primary_blocker": "reviewed_boja_missing"},
                    {"topic_id": "sanidad", "primary_blocker": "delivery_or_beneficiary_missing"},
                ]
            },
            "boja_norms": {
                "impact_review_queue": [
                    boja_item(),
                    boja_item(
                        review_item_id="boja-impact-review-sanidad",
                        topic_id="sanidad",
                        topic_label="Sanidad",
                    ),
                    boja_item(review_item_id="boja-impact-review-existing"),
                ]
            },
        }
        existing = {"reviews": [{"review_item_id": "boja-impact-review-existing"}]}

        payload = generate_draft_boja_reviews(
            accountability,
            existing_keys=existing_review_keys(existing),
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["skipped_existing_reviews_total"], 1)
        self.assertEqual(payload["blocked_boja_topics_with_drafts"], ["transparencia_corrupcion"])
        self.assertEqual(payload["blocked_boja_topics_without_drafts"], [])
        draft = payload["drafts"][0]
        self.assertEqual(draft["claim_status"], "reviewed_boja_legal_change_no_merit_claim")
        self.assertEqual(draft["review_status"], "reviewed_legal_change_only")
        self.assertEqual(draft["impact_status"], "legal_change_documented_outcome_pending")
        self.assertEqual(draft["responsibility_status"], "official_publisher_observed")
        self.assertEqual(draft["candidate_direction"], "unknown")
        self.assertIn("merit_blame_not_scored", draft["open_limitations"])
        self.assertIn("Ley 2/2021", draft["source_evidence"][0]["evidence_excerpt"])

    def test_reports_blocked_topics_without_eligible_boja_queue(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [
                    {"topic_id": "transparencia_corrupcion", "primary_blocker": "reviewed_boja_missing"},
                    {"topic_id": "empleo", "blockers": ["reviewed_boja_missing"]},
                ]
            },
            "boja_norms": {"impact_review_queue": [boja_item()]},
        }

        payload = generate_draft_boja_reviews(
            accountability,
            existing_keys=set(),
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["blocked_boja_topics_with_drafts"], ["transparencia_corrupcion"])
        self.assertEqual(payload["blocked_boja_topics_without_drafts"], ["empleo"])

    def test_caps_drafts_per_topic_after_priority_sort(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [{"topic_id": "transparencia_corrupcion", "primary_blocker": "reviewed_boja_missing"}]
            },
            "boja_norms": {
                "impact_review_queue": [
                    boja_item(review_item_id="boja-impact-review-low", priority_rank=40),
                    boja_item(review_item_id="boja-impact-review-high", priority_rank=5),
                ]
            },
        }

        payload = generate_draft_boja_reviews(
            accountability,
            existing_keys=set(),
            reviewed_at="2026-05-17",
            max_drafts_per_topic=1,
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["skipped_over_limit_total"], 1)
        self.assertEqual(payload["drafts"][0]["review_item_id"], "boja-impact-review-high")


if __name__ == "__main__":
    unittest.main()
