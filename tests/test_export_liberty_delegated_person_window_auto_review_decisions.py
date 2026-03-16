from __future__ import annotations

import unittest

from scripts.export_liberty_delegated_person_window_auto_review_decisions import build_auto_review_rows


class TestExportLibertyDelegatedPersonWindowAutoReviewDecisions(unittest.TestCase):
    def test_build_auto_review_rows(self) -> None:
        review_rows = [
            {
                "link_key": "k1",
                "fragment_id": "f1",
                "norm_id": "n1",
                "boe_id": "BOE-A-1",
                "delegating_actor_label": "Ministerio X",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Delegación Especial",
                "current_designated_actor_label": "Delegaciones AEAT",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "2025-12-31",
                "current_source_url": "https://example.test/a",
                "current_evidence_quote": "q1",
                "chain_confidence": "0.8",
                "reasons_csv": "institutional_designated_actor",
                "actionability": "actionable",
            },
            {
                "link_key": "k2",
                "fragment_id": "f2",
                "norm_id": "n2",
                "boe_id": "BOE-A-2",
                "delegating_actor_label": "Ministerio Y",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Dirección General",
                "current_designated_actor_label": "",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "",
                "current_source_url": "https://example.test/b",
                "current_evidence_quote": "q2",
                "chain_confidence": "0.7",
                "reasons_csv": "missing_designated_actor|missing_enforcement_evidence_date",
                "actionability": "actionable",
            },
            {
                "link_key": "k3",
                "fragment_id": "f3",
                "norm_id": "n3",
                "boe_id": "BOE-A-3",
                "delegating_actor_label": "Ministerio Z",
                "delegated_institution_label": "ITSS",
                "designated_role_title": "Jefatura",
                "current_designated_actor_label": "",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "2025-12-31",
                "current_source_url": "https://example.test/c",
                "current_evidence_quote": "q3",
                "chain_confidence": "0.6",
                "reasons_csv": "missing_designated_actor",
                "actionability": "actionable",
            },
            {
                "link_key": "k4",
                "fragment_id": "f4",
                "norm_id": "n4",
                "boe_id": "BOE-A-4",
                "delegating_actor_label": "Ministerio W",
                "delegated_institution_label": "ITSS",
                "designated_role_title": "Direccion del Organismo Estatal ITSS",
                "current_designated_actor_label": "Organismo Estatal ITSS",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "2025-12-31",
                "current_source_url": "https://example.test/d",
                "current_evidence_quote": "q4",
                "chain_confidence": "0.9",
                "reasons_csv": "institutional_designated_actor",
                "actionability": "actionable",
            },
            {
                "link_key": "k5",
                "fragment_id": "f5",
                "norm_id": "n5",
                "boe_id": "BOE-A-5",
                "delegating_actor_label": "Ministerio del Interior",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Subdireccion de Gestion de Sanciones",
                "current_designated_actor_label": "Unidad sancionadora DGT",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "2025-12-31",
                "current_source_url": "https://example.test/e",
                "current_evidence_quote": "q5",
                "chain_confidence": "0.7",
                "reasons_csv": "institutional_designated_actor",
                "actionability": "actionable",
            },
        ]

        assist_rows = [
            {
                "link_key": "k1",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-2007-12769",
                "candidate_doc_url": "https://boe.es/doc1",
                "candidate_title": "Nombramiento de don Jose Ejemplo como Delegado Ejecutivo de la Delegación Especial de Andalucía.",
                "candidate_person_hint": "Jose Ejemplo",
                "candidate_publication_date_iso": "2007-06-30",
                "role_token_overlap": "1",
                "institution_token_overlap": "1",
            },
            {
                "link_key": "k2",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-2003-23115",
                "candidate_doc_url": "https://boe.es/doc2",
                "candidate_title": "Nombramiento de don Maria Ejemplo como Subdirector General de Normativa.",
                "candidate_person_hint": "Maria Ejemplo",
                "candidate_publication_date_iso": "2003-12-17",
                "role_token_overlap": "1",
                "institution_token_overlap": "1",
            },
            {
                "link_key": "k3",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-2001-17717",
                "candidate_doc_url": "https://boe.es/doc3",
                "candidate_title": "Nombramiento sin persona.",
                "candidate_person_hint": "",
                "candidate_publication_date_iso": "2001-09-19",
                "role_token_overlap": "0",
                "institution_token_overlap": "1",
            },
            {
                "link_key": "k4",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-1984-27292",
                "candidate_doc_url": "https://boe.es/doc4",
                "candidate_title": (
                    "Real Decreto 2206/1984, de 12 de diciembre, por el que se dispone "
                    "el nombramiento de don Juan Ignacio Molto Garcia como Director general "
                    "de Inspeccion de Trabajo y Seguridad Social."
                ),
                "candidate_person_hint": "Juan Ignacio Molto Garcia",
                "candidate_publication_date_iso": "1984-12-15",
                "role_token_overlap": "0",
                "institution_token_overlap": "3",
            },
            {
                "link_key": "k5",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-2003-23115",
                "candidate_doc_url": "https://boe.es/doc5",
                "candidate_title": (
                    "Orden INT/3514/2003, de 5 de diciembre, por la que se dispone "
                    "el nombramiento de don Mariano Fernández Fernández como Subdirector "
                    "General de Normativa y Recursos de la Dirección General de Tráfico."
                ),
                "candidate_person_hint": "Mariano Fernández Fernández",
                "candidate_publication_date_iso": "2003-12-17",
                "role_token_overlap": "0",
                "institution_token_overlap": "3",
            },
        ]

        rows, summary = build_auto_review_rows(
            review_rows=review_rows,
            assist_rows=assist_rows,
            min_candidate_score=25,
            max_candidates_per_link=2,
        )

        self.assertEqual(len(rows), 5)
        self.assertEqual(int(summary["approved_rows_total"]), 3)
        self.assertEqual(int(summary["pending_rows_total"]), 2)
        self.assertEqual(int(summary["rows_missing_required_person_hint_total"]), 1)
        self.assertEqual(int(summary["rows_missing_role_alignment_total"]), 1)

        by_key = {row["link_key"]: row for row in rows}
        self.assertEqual(by_key["k1"]["decision"], "approved")
        self.assertEqual(by_key["k1"]["reviewed_designated_actor_label"], "Jose Ejemplo")
        self.assertEqual(by_key["k2"]["decision"], "pending")
        self.assertEqual(
            by_key["k2"]["review_note"],
            "auto_assist:role_alignment_failed:hierarchy_mismatch_direction_vs_subdirection",
        )
        self.assertEqual(by_key["k3"]["decision"], "pending")
        self.assertEqual(
            by_key["k3"]["review_note"],
            "auto_assist:missing_person_hint_for_required_actor",
        )
        self.assertEqual(by_key["k4"]["decision"], "approved")
        self.assertEqual(
            by_key["k4"]["review_note"],
            "auto_assist:approved_from_BOE-A-1984-27292",
        )
        self.assertEqual(by_key["k5"]["decision"], "approved")
        self.assertEqual(by_key["k5"]["reviewed_designated_actor_label"], "Mariano Fernández Fernández")
        self.assertEqual(
            by_key["k5"]["review_note"],
            "auto_assist:approved_from_BOE-A-2003-23115",
        )

    def test_non_nominative_institutional_fallback(self) -> None:
        review_rows = [
            {
                "link_key": "ln1",
                "fragment_id": "f1",
                "norm_id": "n1",
                "boe_id": "BOE-A-2004-18398",
                "delegating_actor_label": "Ministerio de Hacienda",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Unidad procedimental sancionadora",
                "current_designated_actor_label": "",
                "current_appointment_start_date": "2024-01-01",
                "current_appointment_end_date": "",
                "current_enforcement_evidence_date": "",
                "current_source_url": "https://example.test/n1",
                "current_evidence_quote": "q",
                "chain_confidence": "0.6",
                "reasons_csv": "missing_designated_actor|missing_enforcement_evidence_date",
                "actionability": "actionable",
            }
        ]
        assist_rows = [
            {
                "link_key": "ln1",
                "candidate_score": "29",
                "candidate_rank_for_link": "1",
                "candidate_boe_id": "BOE-A-2024-12397",
                "candidate_doc_url": "https://boe.es/doc1",
                "candidate_title": (
                    "Resolución de 12 de junio de 2024, de la Presidencia de la Agencia "
                    "Estatal de Administración Tributaria, por la que se renueva el "
                    "nombramiento de vocales de la Comisión Consultiva de Ética."
                ),
                "candidate_person_hint": "",
                "candidate_publication_date_iso": "2024-06-19",
                "role_token_overlap": "0",
                "institution_token_overlap": "4",
            },
            {
                "link_key": "ln1",
                "candidate_score": "28",
                "candidate_rank_for_link": "2",
                "candidate_boe_id": "BOE-A-2010-5072",
                "candidate_doc_url": "https://boe.es/doc2",
                "candidate_title": (
                    "Resolución de 17 de marzo de 2010, de la Presidencia de la Agencia Estatal "
                    "de Administración Tributaria, por la que se delega el ejercicio de las "
                    "competencias para el nombramiento y cese de los representantes."
                ),
                "candidate_person_hint": "",
                "candidate_publication_date_iso": "2010-03-27",
                "role_token_overlap": "0",
                "institution_token_overlap": "4",
            },
        ]

        rows, summary = build_auto_review_rows(
            review_rows=review_rows,
            assist_rows=assist_rows,
            min_candidate_score=25,
            max_candidates_per_link=3,
            allow_non_nominative_institutional_actor_fallback=True,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["decision"], "approved")
        self.assertEqual(
            row["reviewed_designated_actor_label"],
            "Unidad procedimental sancionadora (AEAT)",
        )
        self.assertEqual(row["reviewed_enforcement_evidence_date"], "2010-03-27")
        self.assertEqual(
            row["review_note"],
            "auto_assist:approved_non_nominative_unit_from_BOE-A-2010-5072",
        )
        self.assertEqual(int(summary["approved_rows_total"]), 1)
        self.assertEqual(int(summary["pending_rows_total"]), 0)
        self.assertEqual(int(summary["approved_with_non_nominative_actor_fallback_total"]), 1)


if __name__ == "__main__":
    unittest.main()
