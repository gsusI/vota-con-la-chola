from __future__ import annotations

import csv
import io
import json
import unittest

from scripts.export_liberty_delegated_pending_resolution_review_queue import build_pending_resolution_rows


class TestExportLibertyDelegatedPendingResolutionReviewQueue(unittest.TestCase):
    def test_build_pending_queue_only_keeps_pending_rows(self) -> None:
        auto_rows = [
            {
                "link_key": "k-pending",
                "decision": "pending",
                "review_note": "auto_assist:role_alignment_failed:director_general_not_found",
                "designated_role_title": "Direccion General",
                "delegated_institution_label": "DGT",
            },
            {
                "link_key": "k-approved",
                "decision": "approved",
                "review_note": "auto_assist:approved_from_BOE-A-1",
                "designated_role_title": "Delegacion Especial",
                "delegated_institution_label": "AEAT",
            },
        ]
        assist_rows = [
            {
                "link_key": "k-pending",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-1",
                "candidate_score": "40",
                "candidate_relevance_bucket": "strong",
                "role_token_overlap": "1",
                "institution_token_overlap": "1",
                "candidate_title": "Candidato 1",
                "candidate_doc_url": "https://boe.es/1",
                "candidate_publication_date_iso": "2001-01-01",
            },
            {
                "link_key": "k-pending",
                "candidate_rank_for_link": "2",
                "candidate_boe_id": "BOE-A-2",
                "candidate_score": "35",
                "candidate_relevance_bucket": "medium",
                "role_token_overlap": "0",
                "institution_token_overlap": "1",
                "candidate_title": "Candidato 2",
                "candidate_doc_url": "https://boe.es/2",
                "candidate_publication_date_iso": "2002-01-01",
            },
        ]

        rows, summary = build_pending_resolution_rows(
            auto_review_rows=auto_rows,
            assist_rows=assist_rows,
            top_candidates_per_link=2,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link_key"], "k-pending")
        self.assertEqual(rows[0]["decision"], "pending")
        self.assertEqual(rows[0]["top_candidates_count"], "2")

        cands = json.loads(rows[0]["top_candidates_json"])
        self.assertEqual(len(cands), 2)
        self.assertEqual(cands[0]["candidate_boe_id"], "BOE-A-1")

        self.assertEqual(int(summary["pending_rows_total"]), 1)
        self.assertEqual(int(summary["links_with_candidates_total"]), 1)
        self.assertIn("auto_assist:role_alignment_failed:director_general_not_found", summary["pending_reason_counts"])


if __name__ == "__main__":
    unittest.main()
