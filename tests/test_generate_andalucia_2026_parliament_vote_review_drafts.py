from __future__ import annotations

import unittest

from scripts.generate_andalucia_2026_parliament_vote_review_drafts import (
    existing_review_keys,
    generate_draft_parliament_vote_reviews,
)


def vote_item(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_item_id": "parliament-vote-impact-review-test-1",
        "vote_event_id": "parlamento-andalucia-votacion-test-1",
        "topic_id": "vivienda",
        "topic_label": "Vivienda",
        "topic_source": "official_initiative",
        "legal_effect_kind": "nonbinding_resolution_vote_rejected",
        "legal_effect_label": "rechazo de proposicion no de ley",
        "legal_effect_confidence": "high",
        "majority_side": "no",
        "total_si": 30,
        "total_no": 70,
        "total_abstenciones": 7,
        "total_blancos": 0,
        "priority_rank": 5,
        "date": "12/03/2026",
        "vote_number": "25",
        "session_number": "80",
        "numexp": "12-26/PNLP-000026",
        "title": "12-26/PNLP-000026, proposicion no de ley relativa a vivienda",
        "party_positions_summary": "PP:no:si=0,no=56,abs=0; PSOE-A:si:si=28,no=0,abs=0",
        "source_url": "https://www.parlamentodeandalucia.es/pdf.do?tipodoc=diario&id=201495",
        "source_locator": "documento-test::vote:25",
    }
    row.update(overrides)
    return row


class TestGenerateAndalucia2026ParliamentVoteReviewDrafts(unittest.TestCase):
    def test_generates_safe_drafts_for_vote_blocked_topics_and_skips_existing(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [
                    {"topic_id": "vivienda", "primary_blocker": "reviewed_vote_missing"},
                    {"topic_id": "sanidad", "blockers": ["reviewed_vote_missing"]},
                    {"topic_id": "educacion", "primary_blocker": "delivery_or_beneficiary_missing"},
                ]
            },
            "parliament_activity": {
                "vote_impact_review_queue": [
                    vote_item(),
                    vote_item(
                        review_item_id="parliament-vote-impact-review-test-sanidad",
                        vote_event_id="parlamento-andalucia-votacion-test-sanidad",
                        topic_id="sanidad",
                        topic_label="Sanidad",
                        legal_effect_kind="parliament_work_body_creation_vote_rejected",
                        numexp="12-25/COM-000012",
                        vote_number="8",
                    ),
                    vote_item(
                        review_item_id="parliament-vote-impact-review-test-educacion",
                        vote_event_id="parlamento-andalucia-votacion-test-educacion",
                        topic_id="educacion",
                        topic_label="Educacion",
                    ),
                    vote_item(
                        review_item_id="parliament-vote-impact-review-test-existing",
                        vote_event_id="parlamento-andalucia-votacion-test-existing",
                        topic_id="vivienda",
                    ),
                ]
            },
        }
        existing = {
            "reviews": [
                {
                    "review_item_id": "parliament-vote-impact-review-test-existing",
                    "vote_event_id": "parlamento-andalucia-votacion-test-existing",
                }
            ]
        }

        payload = generate_draft_parliament_vote_reviews(
            accountability,
            existing_keys=existing_review_keys(existing),
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["drafts_total"], 2)
        self.assertEqual(payload["skipped_existing_reviews_total"], 1)
        self.assertEqual(payload["blocked_vote_topics_with_drafts_total"], 2)
        self.assertEqual(payload["blocked_vote_topics_without_drafts"], [])
        self.assertEqual(payload["drafts_by_topic"], {"sanidad": 1, "vivienda": 1})
        self.assertTrue(all(row["claim_status"].endswith("no_merit_or_blame") for row in payload["drafts"]))
        vivienda = next(row for row in payload["drafts"] if row["topic_id"] == "vivienda")
        self.assertEqual(vivienda["legal_effect_status"], "observed_rejection_vote")
        self.assertEqual(vivienda["effect_outcome"], "rejected_by_majority_no")
        self.assertEqual(vivienda["impact_status"], "outcome_not_reviewed")
        self.assertEqual(vivienda["responsibility_status"], "party_positions_observed")
        self.assertIn("merit_blame_not_scored", vivienda["open_limitations"])
        self.assertIn("total si 30", vivienda["source_evidence"][0]["evidence_excerpt"])

    def test_reports_blocked_topics_without_eligible_vote_queue(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [
                    {"topic_id": "empleo", "primary_blocker": "reviewed_vote_missing"},
                    {"topic_id": "transparencia_corrupcion", "primary_blocker": "reviewed_vote_missing"},
                    {"topic_id": "vivienda", "primary_blocker": "reviewed_vote_missing"},
                ]
            },
            "parliament_activity": {"vote_impact_review_queue": [vote_item()]},
        }

        payload = generate_draft_parliament_vote_reviews(
            accountability,
            existing_keys=set(),
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["blocked_vote_topics_with_drafts"], ["vivienda"])
        self.assertEqual(payload["blocked_vote_topics_without_drafts"], ["empleo", "transparencia_corrupcion"])

    def test_caps_drafts_per_topic_after_priority_sort(self) -> None:
        accountability = {
            "accountability_readiness": {
                "issues": [{"topic_id": "seguridad_libertades", "primary_blocker": "reviewed_vote_missing"}]
            },
            "parliament_activity": {
                "vote_impact_review_queue": [
                    vote_item(
                        review_item_id="parliament-vote-impact-review-test-low",
                        vote_event_id="parlamento-andalucia-votacion-test-low",
                        topic_id="seguridad_libertades",
                        topic_label="Seguridad y libertades",
                        priority_rank=9,
                        vote_number="9",
                    ),
                    vote_item(
                        review_item_id="parliament-vote-impact-review-test-high",
                        vote_event_id="parlamento-andalucia-votacion-test-high",
                        topic_id="seguridad_libertades",
                        topic_label="Seguridad y libertades",
                        priority_rank=1,
                        vote_number="1",
                    ),
                ]
            },
        }

        payload = generate_draft_parliament_vote_reviews(
            accountability,
            existing_keys=set(),
            reviewed_at="2026-05-17",
            max_drafts_per_topic=1,
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["skipped_over_limit_total"], 1)
        self.assertEqual(payload["drafts"][0]["review_item_id"], "parliament-vote-impact-review-test-high")


if __name__ == "__main__":
    unittest.main()
