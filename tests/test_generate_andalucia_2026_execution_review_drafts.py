from __future__ import annotations

import unittest

from scripts.generate_andalucia_2026_execution_review_drafts import (
    generate_draft_execution_evidence_reviews,
    existing_review_keys,
)


class TestGenerateAndalucia2026ExecutionReviewDrafts(unittest.TestCase):
    def test_generates_safe_drafts_and_skips_existing_reviews(self) -> None:
        accountability = {
            "issue_execution_evidence_queue": {
                "queue": [
                    {
                        "topic_id": "educacion",
                        "topic_label": "Educacion",
                        "gap_id": "missing_budget_execution",
                        "official_candidate_rows": [
                            {
                                "candidate_row_id": "existing-budget",
                                "topic_id": "educacion",
                                "gap_id": "missing_budget_execution",
                                "source_id": "junta_presupuesto_2026_partidas_gastos",
                                "source_kind": "official_budget_open_data",
                                "source_url": "https://example.test/budget.xlsx",
                                "source_locator": "partidas-de-gastos.xlsx:fila 6805",
                                "program_code": "42J",
                                "program_name": "UNIVERSIDADES",
                                "budget_item": "AJUSTES FINANCIACION UNIVERSIDADES PUBLICAS ANDALUZAS",
                                "amount_eur": 191560745,
                                "summary": "Ajustes universidades",
                            },
                            {
                                "candidate_row_id": "new-budget",
                                "topic_id": "educacion",
                                "gap_id": "missing_budget_execution",
                                "source_id": "junta_presupuesto_2026_partidas_gastos",
                                "source_kind": "official_budget_open_data",
                                "source_url": "https://example.test/budget.xlsx",
                                "source_locator": "partidas-de-gastos.xlsx:fila 6811",
                                "program_code": "42J",
                                "program_name": "UNIVERSIDADES",
                                "budget_item": "FINANCIACION BECAS",
                                "amount_eur": 2000000,
                                "summary": "Becas",
                            },
                        ],
                    },
                    {
                        "topic_id": "energia_clima",
                        "topic_label": "Energia y clima",
                        "gap_id": "missing_outcomes",
                        "official_candidate_rows": [
                            {
                                "candidate_row_id": "new-indicator",
                                "topic_id": "energia_clima",
                                "gap_id": "missing_outcomes",
                                "source_id": "junta_presupuesto_2026_objetivos_indicadores",
                                "source_kind": "official_budget_indicator_open_data",
                                "source_url": "https://example.test/indicators.xlsx",
                                "source_locator": "objetivos-actuaciones-e-indicadores.xlsx:fila 3857",
                                "program_code": "44B",
                                "program_name": "PREVENCION Y CALIDAD AMBIENTAL",
                                "indicator_code": "0000000938",
                                "indicator_name": "Planes de mejora de la calidad del aire",
                                "indicator_prevision": "12",
                                "indicator_unit": "NUMERO",
                                "summary": "Planes calidad aire",
                            },
                            {
                                "candidate_row_id": "new-outcome",
                                "topic_id": "energia_clima",
                                "gap_id": "missing_outcomes",
                                "source_id": "ieca_ods_aire_pm10_85172",
                                "source_kind": "official_outcome_series_json",
                                "source_url": "https://example.test/ieca-pm10.json",
                                "source_locator": "ieca_ods_aire_pm10_85172.json:fila 1",
                                "indicator_name": "Nivel medio de partículas PM10",
                                "indicator_unit": "Microgramos por metro cubico",
                                "outcome_territory": "Andalucía",
                                "outcome_year": "2024",
                                "outcome_value": "29.2",
                                "outcome_value_format": "29,20",
                                "outcome_periodicity": "Anual",
                                "outcome_status": "",
                                "outcome_dimension_context": "",
                                "summary": "Nivel medio PM10",
                            }
                        ],
                    },
                    {
                        "topic_id": "energia_clima",
                        "topic_label": "Energia y clima",
                        "gap_id": "missing_budget_execution",
                        "official_candidate_rows": [
                            {
                                "candidate_row_id": "new-grant",
                                "topic_id": "energia_clima",
                                "gap_id": "missing_budget_execution",
                                "source_id": "junta_subvenciones_programas_prioritarios",
                                "source_kind": "official_grant_awards_open_data",
                                "source_url": "https://example.test/subventions",
                                "source_locator": "junta_subvenciones_programas_prioritarios.json:fila 1",
                                "program_code": "44B",
                                "program_name": "PREVENCION Y CALIDAD AMBIENTAL",
                                "grant_beneficiary": "AYUNTAMIENTO TEST",
                                "grant_announcement": "Ayudas calidad del aire",
                                "grant_finality": "Calidad del aire y cambio climatico",
                                "grant_date": "2025-09-01",
                                "grant_type": "Reglada",
                                "grant_organism": "C. SOSTENIBILIDAD, MEDIO AMBIENTE Y ECONOMIA AZUL",
                                "budget_application": "G/44B/46000/00",
                                "amount_eur": 50000,
                                "summary": "Calidad del aire y cambio climatico",
                            },
                            {
                                "candidate_row_id": "new-treasury",
                                "topic_id": "energia_clima",
                                "gap_id": "missing_budget_execution",
                                "source_id": "junta_tesoreria_2025_pagos_agregados",
                                "source_kind": "official_treasury_payment_aggregate_open_data",
                                "source_url": "https://example.test/tesoreria.7z",
                                "source_locator": "tesoreria_2025_movimientos.7z:2025T4_PAGOS_4.CSV:fila 8",
                                "treasury_year": "2025",
                                "treasury_month": "01",
                                "treasury_hierarchy_1": "2. Pagos presupuestarios",
                                "treasury_hierarchy_2": "2.1. Consejerías",
                                "treasury_hierarchy_3": "Consejería de Sostenibilidad, Medio Ambiente y Economía Azul",
                                "amount_eur": 5043448,
                                "summary": "Consejería de Sostenibilidad, Medio Ambiente y Economía Azul",
                            },
                        ],
                    },
                ]
            }
        }
        existing = {
            "reviews": [
                {
                    "topic_id": "educacion",
                    "gap_id": "missing_budget_execution",
                    "source_id": "junta_presupuesto_2026_partidas_gastos",
                    "source_locator": "partidas-de-gastos.xlsx:fila 6805",
                }
            ]
        }

        payload = generate_draft_execution_evidence_reviews(
            accountability,
            existing_keys=existing_review_keys(existing),
            reviewed_at="2026-05-17",
            max_drafts_per_item=3,
        )

        self.assertEqual(payload["drafts_total"], 5)
        self.assertEqual(payload["skipped_existing_reviews_total"], 1)
        self.assertEqual(
            {row["evidence_kind"] for row in payload["drafts"]},
            {"budget_plan", "indicator_target", "observed_outcome_series", "grant_award", "treasury_payment_aggregate"},
        )
        self.assertTrue(
            all("no_merit_or_blame" in row["claim_status"] for row in payload["drafts"])
        )
        self.assertTrue(
            all("merit_blame_not_scored" in row["open_limitations"] for row in payload["drafts"])
        )
        budget = next(row for row in payload["drafts"] if row["evidence_kind"] == "budget_plan")
        self.assertEqual(budget["review_status"], "reviewed_budget_plan_linked_execution_pending")
        self.assertEqual(budget["amount_eur"], 2000000)
        outcome = next(row for row in payload["drafts"] if row["evidence_kind"] == "observed_outcome_series")
        self.assertEqual(outcome["review_status"], "reviewed_observed_outcome_baseline_post_change_pending")
        self.assertEqual(outcome["outcome_territory"], "Andalucía")
        self.assertEqual(outcome["outcome_year"], "2024")
        self.assertEqual(outcome["outcome_value_format"], "29,20")
        self.assertIn("valor 29,20 Microgramos por metro cubico", outcome["source_evidence"][0]["evidence_excerpt"])
        grant = next(row for row in payload["drafts"] if row["evidence_kind"] == "grant_award")
        self.assertEqual(grant["review_status"], "reviewed_grant_award_linked_delivery_outcome_pending")
        self.assertEqual(grant["grant_beneficiary"], "AYUNTAMIENTO TEST")
        self.assertIn("importe 50000 EUR", grant["source_evidence"][0]["evidence_excerpt"])
        treasury = next(row for row in payload["drafts"] if row["evidence_kind"] == "treasury_payment_aggregate")
        self.assertEqual(treasury["review_status"], "reviewed_treasury_payment_aggregate_linked_delivery_outcome_pending")
        self.assertEqual(treasury["treasury_month"], "01")
        self.assertIn("importe 5043448 EUR", treasury["source_evidence"][0]["evidence_excerpt"])

    def test_prioritizes_observed_outcome_series_when_missing_outcome_item_is_capped(self) -> None:
        accountability = {
            "issue_execution_evidence_queue": {
                "queue": [
                    {
                        "topic_id": "cultura_patrimonio",
                        "topic_label": "Cultura y patrimonio",
                        "gap_id": "missing_outcomes",
                        "official_candidate_rows": [
                            {
                                "candidate_row_id": "indicator-target",
                                "topic_id": "cultura_patrimonio",
                                "gap_id": "missing_outcomes",
                                "source_id": "junta_presupuesto_2026_objetivos_indicadores",
                                "source_kind": "official_budget_indicator_open_data",
                                "source_locator": "objetivos-actuaciones-e-indicadores.xlsx:fila 3610",
                                "indicator_name": "Expedientes de adquisiciones y cesiones tramitados",
                                "indicator_prevision": "25",
                                "indicator_unit": "NUMERO",
                                "review_priority": 0,
                                "match_score": 25,
                            },
                            {
                                "candidate_row_id": "outcome-baseline",
                                "topic_id": "cultura_patrimonio",
                                "gap_id": "missing_outcomes",
                                "source_id": "ieca_ods_cultura_patrimonio_gasto_85763",
                                "source_kind": "official_outcome_series_json",
                                "source_locator": "ieca_ods_cultura_patrimonio_gasto_85763.json:fila 1",
                                "indicator_name": "Gasto per cápita en patrimonio cultural",
                                "indicator_unit": "Euros per capita",
                                "outcome_territory": "Andalucía",
                                "outcome_year": "2023",
                                "outcome_value": "23.23",
                                "outcome_value_format": "23,23",
                                "review_priority": 0,
                                "match_score": 13,
                            },
                        ],
                    }
                ]
            }
        }

        payload = generate_draft_execution_evidence_reviews(
            accountability,
            existing_keys=set(),
            reviewed_at="2026-05-17",
            max_drafts_per_item=1,
        )

        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["skipped_over_limit_total"], 1)
        self.assertEqual(payload["drafts"][0]["candidate_row_id"], "outcome-baseline")
        self.assertEqual(payload["drafts"][0]["evidence_kind"], "observed_outcome_series")


if __name__ == "__main__":
    unittest.main()
