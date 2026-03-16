from __future__ import annotations

import unittest

from scripts.export_liberty_delegated_person_window_review_assist_from_boe_candidates import (
    build_review_assist_rows,
)


class TestExportLibertyDelegatedReviewAssistFromBoeCandidates(unittest.TestCase):
    def test_build_review_assist_rows(self) -> None:
        review_rows = [
            {
                "link_key": "lk1",
                "fragment_id": "f1",
                "norm_id": "n1",
                "boe_id": "BOE-A-2003-23514",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Dirección General de la AEAT",
                "reasons_csv": "missing_designated_actor|institutional_designated_actor",
            }
        ]
        candidate_rows = [
            {
                "link_key": "lk1",
                "candidate_rank": "1",
                "candidate_score": "39",
                "candidate_boe_id": "BOE-A-2006-11416",
                "candidate_doc_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2006-11416",
                "candidate_publication_date": "14/06/2006",
                "candidate_department": "Ministerio de Hacienda",
                "candidate_title": (
                    "Real Decreto ... nombramiento de doña Pilar Valiente Ayala "
                    "como Directora General de la Agencia Estatal de Administración Tributaria ..."
                ),
                "candidate_person_hint": "Pilar Valiente Ayala",
            },
            {
                "link_key": "lk1",
                "candidate_rank": "2",
                "candidate_score": "12",
                "candidate_boe_id": "BOE-A-2005-00001",
                "candidate_doc_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2005-00001",
                "candidate_publication_date": "01/01/2005",
                "candidate_department": "Ministerio de Hacienda",
                "candidate_title": "Otro texto",
                "candidate_person_hint": "",
            },
        ]

        rows, summary = build_review_assist_rows(
            review_rows=review_rows,
            candidate_rows=candidate_rows,
            min_candidate_score=20,
            max_candidates_per_link=3,
        )

        self.assertEqual(int(summary["assist_rows_total"]), 1)
        self.assertEqual(int(summary["review_links_with_candidates_total"]), 1)
        self.assertEqual(int(summary["relevance_bucket_counts"]["strong"]), 1)

        row = rows[0]
        self.assertEqual(str(row["candidate_boe_id"]), "BOE-A-2006-11416")
        self.assertEqual(str(row["candidate_publication_date_iso"]), "2006-06-14")
        self.assertEqual(str(row["suggested_reviewed_designated_actor_label"]), "Pilar Valiente Ayala")
        self.assertEqual(str(row["candidate_relevance_bucket"]), "strong")
        self.assertEqual(str(row["autofill_confidence"]), "high")
        self.assertEqual(str(row["institution_overlap_ok"]), "1")

    def test_institution_overlap_hardening_for_itss(self) -> None:
        review_rows = [
            {
                "link_key": "lk2",
                "fragment_id": "f2",
                "norm_id": "n2",
                "boe_id": "BOE-A-2000-15060",
                "delegated_institution_label": "Inspeccion de Trabajo y Seguridad Social",
                "designated_role_title": "Jefatura de Inspeccion",
                "reasons_csv": "missing_designated_actor",
            }
        ]
        candidate_rows = [
            {
                "link_key": "lk2",
                "candidate_rank": "1",
                "candidate_score": "35",
                "candidate_boe_id": "BOE-A-1988-24053",
                "candidate_doc_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-1988-24053",
                "candidate_publication_date": "20/10/1988",
                "candidate_department": "Ministerio de Administraciones Publicas",
                "candidate_title": (
                    "Orden ... nombramiento de don X como Jefe de Inspección General de Servicios."
                ),
                "candidate_person_hint": "X",
            }
        ]

        rows, summary = build_review_assist_rows(
            review_rows=review_rows,
            candidate_rows=candidate_rows,
            min_candidate_score=20,
            max_candidates_per_link=3,
        )

        self.assertEqual(int(summary["assist_rows_total"]), 1)
        self.assertEqual(int(summary["rows_below_institution_overlap_min_total"]), 1)
        self.assertEqual(str(rows[0]["institution_overlap_ok"]), "0")
        self.assertEqual(str(rows[0]["candidate_relevance_bucket"]), "weak")
        self.assertEqual(str(rows[0]["recommended_action"]), "inspect_candidate_low_institution_overlap")


if __name__ == "__main__":
    unittest.main()
