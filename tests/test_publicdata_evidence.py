from __future__ import annotations

import unittest

from etl.parlamentario_es import initdoc_review as vota_initdoc_review
from etl.parlamentario_es import review_queue as vota_review_queue
from publicdata_evidence import initdoc_review, quality, review_queue


class TestPublicdataEvidencePackage(unittest.TestCase):
    def test_vota_wrappers_reexport_review_helpers(self) -> None:
        self.assertIs(
            vota_review_queue.build_topic_evidence_review_report,
            review_queue.build_topic_evidence_review_report,
        )
        self.assertIs(
            vota_review_queue.apply_topic_evidence_review_decision,
            review_queue.apply_topic_evidence_review_decision,
        )

    def test_vota_wrapper_reexports_quality_helpers(self) -> None:
        from etl.parlamentario_es import quality as vota_quality

        self.assertIs(vota_quality.compute_vote_quality_kpis, quality.compute_vote_quality_kpis)
        self.assertIs(
            vota_quality.compute_initiative_quality_kpis,
            quality.compute_initiative_quality_kpis,
        )
        self.assertIs(
            vota_quality.compute_declared_quality_kpis,
            quality.compute_declared_quality_kpis,
        )

    def test_vota_wrapper_keeps_default_db_out_of_reusable_package(self) -> None:
        self.assertFalse(hasattr(initdoc_review, "DEFAULT_DB"))
        self.assertTrue(hasattr(vota_initdoc_review, "DEFAULT_DB"))
        self.assertIs(vota_initdoc_review.apply_review_decisions, initdoc_review.apply_review_decisions)

    def test_label_studio_source_link_has_semantic_class(self) -> None:
        tasks = initdoc_review.export_label_studio_tasks(
            [
                {
                    "source_record_pk": 11,
                    "source_url": "https://example.org/doc",
                    "extracted_subject": "tema",
                }
            ]
        )

        html = tasks[0]["data"]["source_link_html"]
        self.assertIn('class="initdoc-review__source-link"', html)


if __name__ == "__main__":
    unittest.main()
