from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from scripts import export_responsibility_explainer_snapshot as responsibility_explainer
from scripts import import_responsibility_explainer_seed as responsibility_import
from scripts.apply_responsibility_ledger_reviews import apply_review_rows


REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_BATCH = (
    REPO_ROOT
    / "etl"
    / "data"
    / "manual"
    / "responsibility_explainer"
    / "reviewed_ledger_batches"
    / "20260413-cash-payment-limit-spain.csv"
)


class TestApplyResponsibilityLedgerReviews(unittest.TestCase):
    def test_apply_review_rows_populates_non_dana_case(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "responsibility-ledger.db"

            with open_db(db_path) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                case_defs, skipped = responsibility_import.build_import_case_defs({})
                self.assertEqual(skipped, [])
                seed_summary = responsibility_import.import_seed(
                    conn,
                    case_defs=case_defs,
                    seed_map={},
                    snapshot_date="2026-04-13",
                )
                self.assertEqual(seed_summary["counts"]["cases_total"], 2)

                result = apply_review_rows(conn, review_files=[REVIEW_BATCH], dry_run=False)
                self.assertEqual(result["rows_applied"], 9)
                self.assertEqual(result["applied_by_kind"]["governing_rule"], 2)
                self.assertEqual(result["applied_by_kind"]["official_finding"], 2)
                self.assertEqual(result["applied_by_kind"]["administrative_act"], 2)
                self.assertEqual(result["applied_by_kind"]["responsibility_link"], 3)

                db_case_defs = responsibility_explainer.load_case_defs_from_db(conn)
                case_def = next(item for item in db_case_defs if item["case_id"] == "cash-payment-limit-spain")
                payload = responsibility_explainer.build_case_payload(
                    conn,
                    case_def=case_def,
                    snapshot_date="2026-04-13",
                    site_origin="https://gsusI.github.io",
                    base_path="/vota-con-la-chola",
                    max_initiatives=12,
                    max_votes=12,
                    max_measures=12,
                    db_label="test.db",
                )

            self.assertEqual(payload["case"]["title"], "Limite de pagos en efectivo en Espana")
            self.assertEqual(int(payload["coverage"]["governing_rules_total"]), 2)
            self.assertEqual(int(payload["coverage"]["official_findings_total"]), 2)
            self.assertEqual(int(payload["coverage"]["administrative_acts_total"]), 2)
            self.assertEqual(int(payload["coverage"]["responsibility_links_total"]), 3)
            self.assertEqual(int(payload["question_status_counts"]["partial"]), 4)
            self.assertEqual(int(payload["question_status_counts"]["missing"]), 2)
            question_status = {item["question_id"]: item["status"] for item in payload["questions"]}
            self.assertEqual(question_status["formal_rule"], "partial")
            self.assertEqual(question_status["formal_enforcement_chain"], "partial")
            self.assertEqual(question_status["sanction_mechanics"], "partial")
            self.assertEqual(question_status["official_interpretation"], "partial")
            self.assertEqual(question_status["who_can_change_now"], "missing")
            self.assertEqual(question_status["real_enforcement"], "missing")

            links = payload["accountability_ledger"]["responsibility_links"]
            self.assertEqual(links[0]["actor"], "Cortes Generales")
            self.assertEqual(links[0]["linked_object_type"], "administrative_act")
            self.assertEqual(links[0]["source_url"], "https://www.boe.es/buscar/act.php?id=BOE-A-2021-11473")
            acts = payload["accountability_ledger"]["administrative_acts"]
            self.assertEqual(acts[0]["act_type"], "law-publication")
            self.assertEqual(acts[0]["act_date"], "2021-07-10")
            named = payload["accountability_ledger"]["named_accountability"]
            self.assertEqual(int(payload["coverage"]["named_accountability_total"]), 6)
            self.assertEqual(named[1]["actor_label"], "Maria Jesus Montero Cuadrado")
            self.assertIn("Patricia Blanquer Alcaraz", named[4]["person_names"])


if __name__ == "__main__":
    unittest.main()
