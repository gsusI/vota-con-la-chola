from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestImportResponsibilityExplainerSeed(unittest.TestCase):
    def test_importer_populates_sqlite_and_exporter_reads_db_backed_case(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "responsibility.db"
            out_dir = td_path / "out"
            seed_path = td_path / "responsibility-seed.json"

            seed_path.write_text(
                json.dumps(
                    {
                        "schema_version": "responsibility_explainer_cases_seed_v1",
                        "cases": [
                            {
                                "case_id": "dana-valencia-2024",
                                "current_scope_note": "Seed import note for DB-backed export.",
                        "normative_duties": [
                            {
                                "duty_id": "generalitat-duty",
                                "actor": "Generalitat Valenciana",
                                "duty_summary": "Debe dirigir la respuesta de emergencia.",
                                "source_title": "Ley 13/2010",
                                "source_url": "https://example.org/law",
                                "source_locator": "art. 14",
                            }
                        ],
                        "warning_timeline_events": [
                            {
                                "event_id": "aemet-warning-1",
                                "channel_id": "aemet-meteoalerta",
                                "channel_name": "AEMET Meteoalerta",
                                "operator": "AEMET",
                                "event_time": "2024-10-29T07:36:00",
                                "event_precision": "minute_local",
                                "signal_level": "rojo observado",
                                "event_summary": "Aviso rojo observado en Litoral sur.",
                                "why_it_matters": "Marca una elevacion oficial a rojo.",
                                "source_title": "AEMET estudio",
                                "source_url": "https://example.org/aemet-study.pdf",
                                "source_locator": "p. 31",
                            }
                        ],
                        "governing_rules": [
                            {
                                "rule_id": "rule-1",
                                "rule_kind": "planning",
                                "title": "Compatibilidad con riesgo",
                                "duty_summary": "El planeamiento debe incorporar riesgo.",
                                "exposure_mechanism": "Si no lo hace, consolida exposicion.",
                                "source_title": "PATRICOVA",
                                "source_url": "https://example.org/patricova",
                                "source_locator": "art. 1",
                            }
                        ],
                        "official_findings": [
                            {
                                "finding_id": "finding-1",
                                "category": "diagnosis",
                                "entity_name": "Paiporta",
                                "finding_date": "2024-01-01",
                                "finding_summary": "La red era deficitaria.",
                                "accountability_implication": "Habia hallazgo previo.",
                                "source_title": "Plan director",
                                "source_url": "https://example.org/plan",
                                "source_locator": "p. 2",
                            }
                        ],
                        "administrative_acts": [
                            {
                                "act_id": "act-1",
                                "act_type": "urbanization-file",
                                "entity_name": "Ayuntamiento de Paiporta",
                                "act_date": "2024-03-07",
                                "status": "registered",
                                "act_summary": "Se registra el expediente.",
                                "accountability_implication": "La administracion tenia un rol directo.",
                                "source_title": "Expediente",
                                "source_url": "https://example.org/exp",
                                "source_locator": "folio 1",
                            }
                        ],
                        "responsibility_links": [
                            {
                                "link_id": "link-1",
                                "actor": "Ayuntamiento de Paiporta",
                                "actor_scope": "Pleno",
                                "linked_object_type": "administrative_act",
                                "linked_object_id": "act-1",
                                "role_in_chain": "condiciona usos",
                                "obligation_basis": "licencias y planeamiento",
                                "accountability_question": "Quien podia evitar la exposicion?",
                                "source_title": "Expediente",
                                "source_url": "https://example.org/exp",
                                "source_locator": "folio 1",
                            }
                        ],
                    }
                ],
            },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "import_responsibility_explainer_seed.py"),
                    "--db",
                    str(db_path),
                    "--seed",
                    str(seed_path),
                    "--snapshot-date",
                    "2026-04-12",
                ],
                check=True,
                cwd=str(REPO_ROOT),
            )
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "export_responsibility_explainer_snapshot.py"),
                    "--db",
                    str(db_path),
                    "--seed",
                    str(td_path / "missing-seed.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                check=True,
                cwd=str(REPO_ROOT),
            )

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                case_row = conn.execute(
                    "SELECT title, current_scope_note FROM responsibility_explainer_cases WHERE case_id = ?",
                    ("dana-valencia-2024",),
                ).fetchone()
            finally:
                conn.close()

            detail = json.loads((out_dir / "dana-valencia-2024.json").read_text(encoding="utf-8"))

        self.assertIsNotNone(case_row)
        self.assertEqual(case_row["title"], "DANA Valencia 2024")
        self.assertEqual(case_row["current_scope_note"], "Seed import note for DB-backed export.")
        self.assertEqual(int(detail["coverage"]["initiatives_total"]), 0)
        self.assertEqual(int(detail["coverage"]["normative_duties_total"]), 1)
        self.assertEqual(int(detail["coverage"]["warning_timeline_events_total"]), 1)
        self.assertEqual(int(detail["coverage"]["governing_rules_total"]), 1)
        self.assertEqual(int(detail["coverage"]["official_findings_total"]), 1)
        self.assertEqual(int(detail["coverage"]["administrative_acts_total"]), 1)
        self.assertEqual(int(detail["coverage"]["responsibility_links_total"]), 1)
        self.assertEqual(detail["case"]["current_scope_note"], "Seed import note for DB-backed export.")
        self.assertEqual(detail["normative_evidence"]["normative_duties"][0]["source_locator"], "art. 14")
        self.assertEqual(detail["normative_evidence"]["warning_timeline_events"][0]["event_id"], "aemet-warning-1")
        self.assertEqual(detail["accountability_ledger"]["governing_rules"][0]["rule_id"], "rule-1")
        self.assertEqual(detail["accountability_ledger"]["official_findings"][0]["finding_id"], "finding-1")
        self.assertEqual(detail["accountability_ledger"]["administrative_acts"][0]["act_id"], "act-1")
        self.assertEqual(detail["accountability_ledger"]["responsibility_links"][0]["link_id"], "link-1")
        self.assertEqual(int(detail["question_status_counts"]["partial"]), 2)
        self.assertEqual(int(detail["question_status_counts"]["missing"]), 6)


if __name__ == "__main__":
    unittest.main()
