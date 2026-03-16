from __future__ import annotations

import unittest

from scripts.export_liberty_delegated_person_window_auto_review_qa_sample import (
    build_qa_sample_rows,
    stratified_sample,
)


class TestExportLibertyDelegatedPersonWindowAutoReviewQaSample(unittest.TestCase):
    def test_stratified_sample_preserves_institution_coverage(self) -> None:
        rows = [
            {"link_key": "a1", "delegated_institution_label": "AEAT", "selected_candidate_score": "30"},
            {"link_key": "a2", "delegated_institution_label": "AEAT", "selected_candidate_score": "20"},
            {"link_key": "d1", "delegated_institution_label": "DGT", "selected_candidate_score": "10"},
            {"link_key": "i1", "delegated_institution_label": "ITSS", "selected_candidate_score": "40"},
        ]

        got = stratified_sample(rows, sample_size=3)
        self.assertEqual(len(got), 3)
        institutions = {row["delegated_institution_label"] for row in got}
        self.assertIn("AEAT", institutions)
        self.assertIn("DGT", institutions)
        self.assertIn("ITSS", institutions)

    def test_build_qa_sample_uses_candidate_referenced_in_review_note(self) -> None:
        auto_review_rows = [
            {
                "link_key": "k1",
                "fragment_id": "f1",
                "norm_id": "n1",
                "boe_id": "BOE-A-1",
                "delegating_actor_label": "Ministerio",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Direccion",
                "decision": "approved",
                "reviewed_designated_actor_label": "Persona Correcta",
                "reviewed_enforcement_evidence_date": "2008-06-11",
                "reviewed_source_url": "https://boe.es/doc-ok",
                "reviewed_evidence_quote": "Nombramiento correcto",
                "review_note": "auto_assist:approved_from_BOE-A-2008-9974",
            },
            {
                "link_key": "k2",
                "fragment_id": "f2",
                "norm_id": "n2",
                "boe_id": "BOE-A-2",
                "delegating_actor_label": "Ministerio",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Direccion",
                "decision": "approved",
                "reviewed_designated_actor_label": "Persona 2",
                "reviewed_enforcement_evidence_date": "",
                "reviewed_source_url": "https://boe.es/doc2",
                "reviewed_evidence_quote": "Nombramiento 2",
                "review_note": "auto_assist:approved_from_BOE-A-2003-23115",
            },
        ]

        assist_rows = [
            {
                "link_key": "k1",
                "candidate_boe_id": "BOE-A-2024-12397",
                "candidate_score": "90",
                "candidate_rank_for_link": "1",
                "candidate_relevance_bucket": "strong",
                "candidate_title": "Candidato no usado",
                "candidate_person_hint": "",
            },
            {
                "link_key": "k1",
                "candidate_boe_id": "BOE-A-2008-9974",
                "candidate_score": "10",
                "candidate_rank_for_link": "2",
                "candidate_relevance_bucket": "weak",
                "candidate_title": "Candidato usado",
                "candidate_person_hint": "Persona Correcta",
                "candidate_publication_date_iso": "2008-06-11",
                "candidate_doc_url": "https://boe.es/doc-ok",
            },
            {
                "link_key": "k2",
                "candidate_boe_id": "BOE-A-2003-23115",
                "candidate_score": "49",
                "candidate_rank_for_link": "1",
                "candidate_relevance_bucket": "strong",
                "candidate_title": "Candidato 2",
                "candidate_person_hint": "Persona 2",
            },
        ]

        rows, summary = build_qa_sample_rows(
            auto_review_rows=auto_review_rows,
            assist_rows=assist_rows,
            sample_size=8,
            only_approved=True,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(int(summary["rows_considered_total"]), 2)
        self.assertEqual(int(summary["sample_rows_total"]), 2)

        by_key = {row["link_key"]: row for row in rows}
        self.assertEqual(by_key["k1"]["auto_decision"], "approved")
        self.assertEqual(by_key["k1"]["selected_candidate_boe_id"], "BOE-A-2008-9974")
        self.assertEqual(by_key["k1"]["selected_candidate_title"], "Candidato usado")
        self.assertEqual(by_key["k2"]["selected_candidate_boe_id"], "BOE-A-2003-23115")

    def test_build_qa_sample_can_filter_by_review_note_substring(self) -> None:
        auto_review_rows = [
            {
                "link_key": "k1",
                "fragment_id": "f1",
                "norm_id": "n1",
                "boe_id": "BOE-A-1",
                "delegating_actor_label": "Ministerio",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Unidad procedimental sancionadora",
                "decision": "approved",
                "reviewed_designated_actor_label": "Unidad procedimental sancionadora (AEAT)",
                "reviewed_enforcement_evidence_date": "2010-03-27",
                "reviewed_source_url": "https://boe.es/doc-ok",
                "reviewed_evidence_quote": "Delegacion competencial",
                "review_note": "auto_assist:approved_non_nominative_unit_from_BOE-A-2010-5072",
            },
            {
                "link_key": "k2",
                "fragment_id": "f2",
                "norm_id": "n2",
                "boe_id": "BOE-A-2",
                "delegating_actor_label": "Ministerio",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Direccion",
                "decision": "approved",
                "reviewed_designated_actor_label": "Persona 2",
                "reviewed_enforcement_evidence_date": "",
                "reviewed_source_url": "https://boe.es/doc2",
                "reviewed_evidence_quote": "Nombramiento 2",
                "review_note": "auto_assist:approved_from_BOE-A-2003-23115",
            },
        ]
        assist_rows = [
            {
                "link_key": "k1",
                "candidate_boe_id": "BOE-A-2024-12397",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_relevance_bucket": "medium",
                "candidate_title": "Candidato no referenciado",
                "candidate_person_hint": "",
                "candidate_publication_date_iso": "2024-06-19",
                "candidate_doc_url": "https://boe.es/doc-other",
            },
            {
                "link_key": "k1",
                "candidate_boe_id": "BOE-A-2010-5072",
                "candidate_score": "28",
                "candidate_rank_for_link": "2",
                "candidate_relevance_bucket": "medium",
                "candidate_title": "Delegacion competencial",
                "candidate_person_hint": "",
                "candidate_publication_date_iso": "2010-03-27",
                "candidate_doc_url": "https://boe.es/doc-ok",
            },
            {
                "link_key": "k2",
                "candidate_boe_id": "BOE-A-2003-23115",
                "candidate_score": "49",
                "candidate_rank_for_link": "1",
                "candidate_relevance_bucket": "strong",
                "candidate_title": "Candidato 2",
                "candidate_person_hint": "Persona 2",
            },
        ]

        rows, summary = build_qa_sample_rows(
            auto_review_rows=auto_review_rows,
            assist_rows=assist_rows,
            sample_size=8,
            only_approved=True,
            review_note_contains="approved_non_nominative_unit",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link_key"], "k1")
        self.assertEqual(rows[0]["selected_candidate_boe_id"], "BOE-A-2010-5072")
        self.assertEqual(int(summary["rows_considered_total"]), 1)
        self.assertEqual(int(summary["rows_excluded_by_review_note_filter_total"]), 1)
        self.assertEqual(str(summary["review_note_contains"]), "approved_non_nominative_unit")


if __name__ == "__main__":
    unittest.main()
