from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import export_responsibility_explainer_snapshot as responsibility_explainer


class TestExportResponsibilityExplainerSnapshot(unittest.TestCase):
    def test_build_case_payload_degrades_cleanly_without_tables(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            payload = responsibility_explainer.build_case_payload(
                conn,
                case_def=responsibility_explainer.DANA_CASE,
                snapshot_date="2026-04-12",
                site_origin="https://gsusI.github.io",
                base_path="/vota-con-la-chola",
                max_initiatives=12,
                max_votes=12,
                max_measures=12,
                db_label=":memory:",
            )
        finally:
            conn.close()

        self.assertEqual(payload["case"]["case_id"], "dana-valencia-2024")
        self.assertEqual(int(payload["coverage"]["initiatives_total"]), 0)
        self.assertEqual(int(payload["coverage"]["vote_events_total"]), 0)
        self.assertEqual(int(payload["coverage"]["reviewed_measures_total"]), 0)
        self.assertEqual(int(payload["question_status_counts"]["partial"]), 0)
        self.assertEqual(int(payload["question_status_counts"]["missing"]), 8)
        self.assertEqual(payload["parliamentary_evidence"]["initiatives"], [])
        self.assertEqual(payload["parliamentary_evidence"]["votes"], [])
        self.assertEqual(payload["parliamentary_evidence"]["reviewed_measures"], [])

    def test_build_case_payload_uses_normative_seed_for_duty_chain(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            payload = responsibility_explainer.build_case_payload(
                conn,
                case_def=responsibility_explainer.DANA_CASE,
                case_seed={
                    "normative_duties": [
                        {
                            "duty_id": "generalitat-duty",
                            "category": "Direccion autonoma",
                            "actor": "Generalitat Valenciana",
                            "actor_scope": "Conseller competente",
                            "duty_summary": "Debe dirigir los planes y protocolos de emergencia.",
                            "why_it_matters": "Ubica el deber de coordinacion autonoma.",
                            "source_title": "Ley 13/2010",
                            "source_url": "https://example.org/law",
                            "source_locator": "art. 14",
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "warning_channels": [
                        {
                            "channel_id": "aemet",
                            "channel_name": "AEMET Meteoalerta",
                            "operator": "AEMET",
                            "scope": "Avisos FMA",
                            "signal_summary": "Canal oficial de avisos.",
                            "why_next": "Falta la serie concreta del episodio.",
                            "source_title": "AEMET",
                            "source_url": "https://example.org/aemet",
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "warning_timeline_events": [
                        {
                            "event_id": "aemet-warning-1",
                            "channel_id": "aemet",
                            "channel_name": "AEMET Meteoalerta",
                            "operator": "AEMET",
                            "event_time": "2024-10-29T07:36:00",
                            "event_precision": "minute_local",
                            "signal_level": "rojo observado",
                            "event_summary": "Aviso rojo observado en Litoral sur.",
                            "why_it_matters": "Marca un salto oficial a rojo.",
                            "source_title": "AEMET estudio",
                            "source_url": "https://example.org/aemet-study.pdf",
                            "source_locator": "p. 31",
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "governing_rules": [
                        {
                            "rule_id": "planning-rule",
                            "rule_kind": "planning",
                            "title": "Compatibilidad con riesgo",
                            "duty_summary": "El planeamiento debe incorporar riesgo.",
                            "exposure_mechanism": "Si no lo hace, consolida exposicion.",
                            "source_title": "PATRICOVA",
                            "source_url": "https://example.org/patricova",
                            "source_locator": "art. 1",
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "official_findings": [
                        {
                            "finding_id": "finding-1",
                            "category": "diagnosis",
                            "entity_name": "Paiporta",
                            "finding_date": "2024-01-01",
                            "finding_summary": "La red es deficitaria.",
                            "accountability_implication": "Habia diagnostico previo.",
                            "source_title": "Plan director",
                            "source_url": "https://example.org/plan",
                            "source_locator": "p. 2",
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "administrative_acts": [
                        {
                            "act_id": "act-1",
                            "act_type": "license-suspension",
                            "entity_name": "Ayuntamiento de Paiporta",
                            "act_date": "2024-03-07",
                            "status": "approved",
                            "act_summary": "Se tramita un expediente de urbanizacion.",
                            "accountability_implication": "La administracion tenia poder regulatorio.",
                            "source_title": "Expediente",
                            "source_url": "https://example.org/exp",
                            "source_locator": "folio 1",
                            "source_note": "Fuente oficial.",
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
                            "source_note": "Fuente oficial.",
                        }
                    ],
                    "structural_audit_targets": [
                        {
                            "target_id": "licenses",
                            "category": "Licencias y usos vulnerables",
                            "title": "Licencias en zona inundable",
                            "geography": "l'Horta Sud",
                            "why_priority": "Permite pasar de la regla a expedientes concretos.",
                            "audit_question": "Que licencias mantuvieron usos vulnerables en zona inundable?",
                            "documents_to_audit": [
                                "licencias urbanisticas",
                                "informes hidraulicos"
                            ],
                            "authority_chain": "Ayuntamiento -> CHJ",
                            "next_join_needed": "Cruzar parcelas con cartografia inundable.",
                            "source_title": "RDPH",
                            "source_url": "https://example.org/rdph",
                            "source_locator": "art. 9 bis",
                            "source_note": "Fuente oficial."
                        }
                    ],
                    "structural_evidence_rows": [
                        {
                            "evidence_id": "paiporta-row",
                            "target_id": "licenses",
                            "entity_name": "Paiporta",
                            "signal_type": "registro oficial",
                            "certainty": "medium",
                            "signal_title": "Expediente pendiente",
                            "pre_dana_reading": "La fila de prueba deja el expediente pendiente.",
                            "why_it_matters": "Permite exportar evidencia fila a fila.",
                            "source_title": "AVSRE",
                            "source_url": "https://example.org/avsre",
                            "source_locator": "fila Paiporta",
                            "source_note": "Fuente oficial."
                        }
                    ],
                },
                snapshot_date="2026-04-12",
                site_origin="https://gsusI.github.io",
                base_path="/vota-con-la-chola",
                max_initiatives=12,
                max_votes=12,
                max_measures=12,
                db_label=":memory:",
            )
        finally:
            conn.close()

        self.assertEqual(int(payload["coverage"]["normative_duties_total"]), 1)
        self.assertEqual(int(payload["coverage"]["warning_channels_total"]), 1)
        self.assertEqual(int(payload["coverage"]["warning_timeline_events_total"]), 1)
        self.assertEqual(int(payload["coverage"]["governing_rules_total"]), 1)
        self.assertEqual(int(payload["coverage"]["official_findings_total"]), 1)
        self.assertEqual(int(payload["coverage"]["administrative_acts_total"]), 1)
        self.assertEqual(int(payload["coverage"]["responsibility_links_total"]), 1)
        self.assertEqual(int(payload["coverage"]["structural_audit_targets_total"]), 1)
        self.assertEqual(int(payload["coverage"]["structural_evidence_rows_total"]), 1)
        self.assertEqual(int(payload["question_status_counts"]["partial"]), 2)
        self.assertEqual(int(payload["question_status_counts"]["missing"]), 6)

        questions = {item["question_id"]: item["status"] for item in payload["questions"]}
        self.assertEqual(questions["duty_chain"], "partial")
        self.assertEqual(questions["structural_exposure"], "missing")
        self.assertEqual(questions["warning_timeline"], "partial")
        self.assertEqual(payload["normative_evidence"]["normative_duties"][0]["actor"], "Generalitat Valenciana")
        self.assertEqual(payload["normative_evidence"]["warning_channels"][0]["channel_name"], "AEMET Meteoalerta")
        self.assertEqual(payload["normative_evidence"]["warning_timeline_events"][0]["event_id"], "aemet-warning-1")
        self.assertEqual(payload["accountability_ledger"]["governing_rules"][0]["rule_id"], "planning-rule")
        self.assertEqual(payload["accountability_ledger"]["official_findings"][0]["finding_id"], "finding-1")
        self.assertEqual(payload["accountability_ledger"]["administrative_acts"][0]["act_id"], "act-1")
        self.assertEqual(payload["accountability_ledger"]["responsibility_links"][0]["link_id"], "link-1")
        self.assertEqual(payload["structural_evidence"]["structural_audit_targets"][0]["target_id"], "licenses")
        self.assertEqual(
            payload["structural_evidence"]["structural_audit_targets"][0]["documents_to_audit"],
            ["licencias urbanisticas", "informes hidraulicos"],
        )
        self.assertEqual(payload["structural_evidence"]["evidence_rows"][0]["entity_name"], "Paiporta")
        self.assertEqual(payload["structural_evidence"]["evidence_rows"][0]["certainty"], "medium")

    def test_cli_export_writes_manifest_and_case_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "responsibility.db"
            out_dir = td_path / "out"
            seed_path = td_path / "responsibility-seed.json"

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                conn.executescript(
                    """
                    CREATE TABLE parl_initiatives (
                      initiative_id TEXT PRIMARY KEY,
                      source_id TEXT,
                      title TEXT,
                      type TEXT,
                      current_status TEXT,
                      presented_date TEXT,
                      source_url TEXT,
                      links_bocg_json TEXT,
                      links_ds_json TEXT,
                      source_snapshot_date TEXT
                    );
                    CREATE TABLE parl_vote_events (
                      vote_event_id TEXT PRIMARY KEY,
                      source_id TEXT,
                      vote_date TEXT,
                      title TEXT,
                      totals_yes INTEGER,
                      totals_no INTEGER,
                      totals_abstain INTEGER,
                      totals_present INTEGER,
                      source_url TEXT,
                      source_snapshot_date TEXT
                    );
                    CREATE TABLE parl_vote_event_initiatives (
                      vote_event_id TEXT,
                      initiative_id TEXT
                    );
                    CREATE TABLE parl_initiative_measure_points (
                      initiative_id TEXT,
                      measure_rank INTEGER,
                      measure_title TEXT,
                      citizen_summary TEXT,
                      policy_area TEXT,
                      measure_status TEXT,
                      primary_vote_event_ids_json TEXT,
                      updated_at TEXT
                    );
                    CREATE TABLE parl_initiative_documents (
                      initiative_id TEXT,
                      doc_kind TEXT,
                      doc_url TEXT
                    );
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, title, type, current_status, presented_date,
                      source_url, links_bocg_json, links_ds_json, source_snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:ley:12:2025",
                        "congreso_iniciativas",
                        "Real Decreto-ley 12/2025 sobre reconstruccion DANA.",
                        "Reales decretos",
                        "Convalidado",
                        "2025-10-28",
                        "https://example.org/rdl12",
                        json.dumps(["https://example.org/rdl12-bocg.pdf"]),
                        "[]",
                        "2026-04-12",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, source_id, vote_date, title, totals_yes, totals_no,
                      totals_abstain, totals_present, source_url, source_snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "vote-1",
                        "congreso_votaciones",
                        "2025-11-12",
                        "Convalidacion del Real Decreto-ley 12/2025.",
                        176,
                        165,
                        4,
                        345,
                        "https://example.org/vote-1",
                        "2026-04-12",
                    ),
                )
                conn.execute(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    ("vote-1", "congreso:ley:12:2025"),
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      initiative_id, measure_rank, measure_title, citizen_summary,
                      policy_area, measure_status, primary_vote_event_ids_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "congreso:ley:12:2025",
                            1,
                            "Ayudas urgentes para municipios afectados",
                            "Activa ayudas urgentes para hogares y municipios afectados por la DANA.",
                            "emergencias",
                            "approved",
                            json.dumps(["vote-1"]),
                            "2026-04-12T10:00:00Z",
                        ),
                        (
                            "congreso:ley:12:2025",
                            2,
                            "Refuerzo de reconstruccion de infraestructuras",
                            "Amplia la reconstruccion de infraestructuras basicas tras la DANA.",
                            "infraestructuras",
                            "approved",
                            json.dumps(["vote-1"]),
                            "2026-04-12T10:00:00Z",
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url) VALUES (?, ?, ?)",
                    ("congreso:ley:12:2025", "bocg", "https://example.org/doc-1.pdf"),
                )
                conn.commit()
            finally:
                conn.close()

            seed_path.write_text(
                json.dumps(
                    {
                        "schema_version": "responsibility_explainer_cases_seed_v1",
                        "cases": [
                            {
                                "case_id": "dana-valencia-2024",
                                "normative_duties": [
                                    {
                                        "duty_id": "generalitat-duty",
                                        "category": "Direccion autonoma",
                                        "actor": "Generalitat Valenciana",
                                        "actor_scope": "Conseller competente",
                                        "duty_summary": "Debe dirigir la respuesta de emergencia.",
                                        "why_it_matters": "Ubica la competencia autonoma.",
                                        "source_title": "Ley 13/2010",
                                        "source_url": "https://example.org/law",
                                        "source_locator": "art. 14",
                                        "source_note": "Fuente oficial.",
                                    }
                                ],
                                "warning_channels": [
                                    {
                                        "channel_id": "aemet",
                                        "channel_name": "AEMET Meteoalerta",
                                        "operator": "AEMET",
                                        "scope": "Avisos FMA",
                                        "signal_summary": "Canal oficial de avisos.",
                                        "why_next": "Falta la serie concreta del episodio.",
                                        "source_title": "AEMET",
                                        "source_url": "https://example.org/aemet",
                                        "source_note": "Fuente oficial.",
                                    }
                                ],
                                "structural_risk_factors": [
                                    {
                                        "factor_id": "soil-risk",
                                        "category": "Ordenacion territorial",
                                        "title": "Mapas de riesgo y urbanismo",
                                        "risk_mechanism": "La exposicion aumenta si el urbanismo no incorpora bien el riesgo natural.",
                                        "accountability_focus": "Auditar planeamiento y licencias.",
                                        "source_title": "Ley del Suelo",
                                        "source_url": "https://example.org/soil",
                                        "source_locator": "art. 22",
                                        "source_note": "Fuente oficial.",
                                    }
                                ],
                                "structural_audit_targets": [
                                    {
                                        "target_id": "licenses",
                                        "category": "Licencias y usos vulnerables",
                                        "title": "Licencias en zona inundable",
                                        "geography": "l'Horta Sud",
                                        "why_priority": "Permite pasar de la regla a expedientes concretos.",
                                        "audit_question": "Que licencias mantuvieron usos vulnerables en zona inundable?",
                                        "documents_to_audit": [
                                            "licencias urbanisticas",
                                            "informes hidraulicos"
                                        ],
                                        "authority_chain": "Ayuntamiento -> CHJ",
                                        "next_join_needed": "Cruzar parcelas con cartografia inundable.",
                                        "source_title": "RDPH",
                                        "source_url": "https://example.org/rdph",
                                        "source_locator": "art. 9 bis",
                                        "source_note": "Fuente oficial."
                                    }
                                ],
                                "structural_evidence_rows": [
                                    {
                                        "evidence_id": "paiporta-row",
                                        "target_id": "licenses",
                                        "entity_name": "Paiporta",
                                        "signal_type": "registro oficial",
                                        "certainty": "medium",
                                        "signal_title": "Expediente pendiente",
                                        "pre_dana_reading": "La fila de prueba deja el expediente pendiente.",
                                        "why_it_matters": "Permite exportar evidencia fila a fila.",
                                        "source_title": "AVSRE",
                                        "source_url": "https://example.org/avsre",
                                        "source_locator": "fila Paiporta",
                                        "source_note": "Fuente oficial."
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
                    str(REPO_ROOT / "scripts" / "export_responsibility_explainer_snapshot.py"),
                    "--db",
                    str(db_path),
                    "--seed",
                    str(seed_path),
                    "--out-dir",
                    str(out_dir),
                ],
                check=True,
                cwd=str(REPO_ROOT),
            )

            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            detail = json.loads((out_dir / "dana-valencia-2024.json").read_text(encoding="utf-8"))
            cash_case = json.loads((out_dir / "cash-payment-limit-spain.json").read_text(encoding="utf-8"))

        self.assertEqual(int(manifest["meta"]["total_cases"]), 2)
        self.assertEqual(manifest["cases"][0]["case_id"], "dana-valencia-2024")
        self.assertEqual(int(manifest["cases"][0]["coverage"]["initiatives_total"]), 1)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["vote_events_total"]), 1)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["reviewed_measures_total"]), 2)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["normative_duties_total"]), 1)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["structural_risk_factors_total"]), 1)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["structural_audit_targets_total"]), 1)
        self.assertEqual(int(manifest["cases"][0]["coverage"]["structural_evidence_rows_total"]), 1)
        self.assertEqual(manifest["cases"][1]["case_id"], "cash-payment-limit-spain")
        self.assertEqual(int(manifest["cases"][1]["coverage"]["governing_rules_total"]), 0)
        self.assertEqual(int(manifest["cases"][1]["coverage"]["named_accountability_total"]), 6)

        self.assertEqual(detail["case"]["canonical_path"], "/responsibility-explainer/dana-valencia-2024/")
        self.assertEqual(int(detail["coverage"]["initiatives_total"]), 1)
        self.assertEqual(int(detail["coverage"]["official_documents_total"]), 1)
        self.assertEqual(int(detail["coverage"]["normative_duties_total"]), 1)
        self.assertEqual(int(detail["coverage"]["warning_channels_total"]), 1)
        self.assertEqual(int(detail["coverage"]["structural_risk_factors_total"]), 1)
        self.assertEqual(int(detail["coverage"]["structural_audit_targets_total"]), 1)
        self.assertEqual(int(detail["coverage"]["structural_evidence_rows_total"]), 1)
        self.assertEqual(int(detail["question_status_counts"]["partial"]), 5)

        questions = {item["question_id"]: item["status"] for item in detail["questions"]}
        self.assertEqual(questions["duty_chain"], "partial")
        self.assertEqual(questions["structural_exposure"], "partial")
        self.assertEqual(questions["parliamentary_response"], "partial")
        self.assertEqual(questions["parliamentary_votes"], "partial")
        self.assertEqual(questions["reviewed_measures"], "partial")
        self.assertEqual(questions["warning_timeline"], "missing")
        self.assertEqual(detail["normative_evidence"]["normative_duties"][0]["source_locator"], "art. 14")
        self.assertEqual(detail["structural_evidence"]["structural_risk_factors"][0]["source_locator"], "art. 22")
        self.assertEqual(detail["structural_evidence"]["structural_audit_targets"][0]["source_locator"], "art. 9 bis")
        self.assertEqual(
            detail["structural_evidence"]["structural_audit_targets"][0]["documents_to_audit"],
            ["licencias urbanisticas", "informes hidraulicos"],
        )
        self.assertEqual(detail["structural_evidence"]["evidence_rows"][0]["entity_name"], "Paiporta")
        self.assertEqual(detail["structural_evidence"]["evidence_rows"][0]["source_locator"], "fila Paiporta")

        initiatives = detail["parliamentary_evidence"]["initiatives"]
        self.assertEqual(len(initiatives), 1)
        self.assertEqual(initiatives[0]["initiative_id"], "congreso:ley:12:2025")
        self.assertEqual(int(initiatives[0]["vote_events_count"]), 1)
        self.assertEqual(int(initiatives[0]["measure_points_count"]), 2)
        self.assertEqual(cash_case["case"]["canonical_path"], "/responsibility-explainer/cash-payment-limit-spain/")
        self.assertEqual(int(cash_case["coverage"]["named_accountability_total"]), 6)
        self.assertEqual(
            cash_case["accountability_ledger"]["named_accountability"][1]["actor_label"],
            "Maria Jesus Montero Cuadrado",
        )
        self.assertEqual(int(cash_case["question_status_counts"]["partial"]), 0)
        self.assertEqual(int(cash_case["question_status_counts"]["missing"]), 6)


if __name__ == "__main__":
    unittest.main()
