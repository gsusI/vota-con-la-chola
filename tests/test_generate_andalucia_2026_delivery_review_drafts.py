from __future__ import annotations

import unittest

from scripts.generate_andalucia_2026_delivery_review_drafts import generate_delivery_review_drafts


class TestGenerateAndalucia2026DeliveryReviewDrafts(unittest.TestCase):
    def test_matches_existing_reviews_and_drafts_only_high_confidence_candidates(self) -> None:
        hunt_results = {
            "targets": [
                {
                    "topic_id": "cultura_patrimonio",
                    "topic_label": "Cultura",
                    "hunt_id": "hunt-cultura",
                    "registry": "bdns",
                    "grant_beneficiary": "DIPUTACION DE CADIZ",
                    "reviewed_label": "FOM. Y PROM. GESTION CULTURAL",
                    "result_candidates": [
                        {
                            "candidate_id": "bdns-valcarcel",
                            "candidate_type": "concession",
                            "machine_readable": True,
                            "cod_concesion": "SB141021614",
                            "numero_convocatoria": "881761",
                            "title": "SUBV EXCEPCIONAL A LA DIPUTACION DE CADIZ RESTAURACIÓN EDIFICIO VALCARCEL",
                            "beneficiario": "P1100000G DIPUTACION DE CADIZ",
                            "importe": 3000000,
                            "fecha_concesion": "2025-12-30",
                            "instrumento": "SUBVENCIÓN",
                            "nivel3": "CONSEJERÍA DE CULTURA Y DEPORTE",
                            "api_url": "https://example.test/bdns/concesiones",
                            "boja_url": "https://example.test/boja",
                            "matched_query_variant": "concession_distinctive_bdns_term",
                        }
                    ],
                },
                {
                    "topic_id": "campo_agua",
                    "topic_label": "Campo y agua",
                    "hunt_id": "hunt-agua",
                    "registry": "bdns",
                    "grant_beneficiary": "EMPRESA METROPOLITANA DE ABASTECIMIENTO Y SANEAMIE",
                    "reviewed_label": "DIGITALIZACIÓN CONTROL USOS DEL AGUA URBANA",
                    "result_candidates": [
                        {
                            "candidate_id": "bdns-broad",
                            "candidate_type": "concession",
                            "machine_readable": True,
                            "cod_concesion": "SB137490077",
                            "title": "MOVES III",
                            "beneficiario": "A41039496 EMPRESA METROPOLITANA DE ABASTECIMIENTO",
                            "importe": 2900,
                            "matched_query_variant": "concession_beneficiary_only",
                        }
                    ],
                },
                {
                    "topic_id": "cultura_patrimonio",
                    "topic_label": "Cultura",
                    "hunt_id": "hunt-contract",
                    "registry": "junta_procurement_registry",
                    "contract_reference": "CONTR 2024 0001008630",
                    "result_candidates": [
                        {
                            "candidate_id": "pdc-contract",
                            "candidate_type": "contract",
                            "machine_readable": True,
                            "numero_expediente": "CONTR 2024 0001008630",
                            "id_expediente": "740593",
                            "title": "Organización y descripción del archivo de oficina del SV PPH",
                            "perfil_contratante": "Dirección General de Patrimonio Histórico",
                            "tipo_contrato": "Servicios",
                            "url": "https://example.test/pdc/detalle",
                            "adjudicaciones": [
                                {
                                    "importe_adjudicacion": 14760,
                                    "fecha_formalizacion": "2024-11-15T00:00:00+0100",
                                }
                            ],
                        }
                    ],
                },
                {
                    "topic_id": "educacion",
                    "topic_label": "Educación",
                    "hunt_id": "hunt-new-contract",
                    "registry": "junta_procurement_registry",
                    "contract_reference": "CONTR 2026 0000000001",
                    "result_candidates": [
                        {
                            "candidate_id": "pdc-new-contract",
                            "candidate_type": "contract",
                            "machine_readable": True,
                            "numero_expediente": "CONTR 2026 0000000001",
                            "id_expediente": "900001",
                            "title": "Contrato menor de apoyo universitario",
                            "perfil_contratante": "Consejería de Universidad",
                            "tipo_contrato": "Servicios",
                            "url": "https://example.test/pdc/new",
                            "adjudicaciones": [{"importe_adjudicacion": 12000}],
                        }
                    ],
                },
            ]
        }
        existing_reviews = {
            "reviews": [
                {
                    "review_item_id": "review-grant-valcarcel",
                    "topic_id": "cultura_patrimonio",
                    "evidence_kind": "grant_award",
                    "grant_beneficiary": "DIPUTACION DE CADIZ",
                    "grant_finality": "FOM. Y PROM. GESTION CULTURAL",
                    "reviewed_label": "FOM. Y PROM. GESTION CULTURAL",
                    "amount_eur": 3000000,
                    "source_id": "junta_subvenciones_programas_prioritarios",
                    "source_locator": "junta_subvenciones_programas_prioritarios.json:fila 359",
                },
                {
                    "review_item_id": "review-contract-archive",
                    "topic_id": "cultura_patrimonio",
                    "evidence_kind": "contract_award",
                    "contract_reference": "CONTR 2024 0001008630",
                    "reviewed_label": "Archivo PPH",
                    "source_id": "junta_contratos_menores_2024",
                    "source_locator": "menores_2024_v1_20250420.json:fila 31655",
                },
            ]
        }

        payload = generate_delivery_review_drafts(
            hunt_results,
            existing_reviews,
            reviewed_at="2026-05-17",
        )

        self.assertEqual(payload["machine_candidates_total"], 4)
        self.assertEqual(payload["confirmations_total"], 2)
        self.assertEqual(payload["drafts_total"], 1)
        self.assertEqual(payload["skipped_broad_bdns_total"], 1)
        self.assertEqual(payload["confirmations_by_topic"], {"cultura_patrimonio": 2})
        self.assertEqual(payload["drafts_by_topic"], {"educacion": 1})
        self.assertEqual(payload["confirmations"][0]["match_basis"], "topic_beneficiary_amount_and_finality")
        self.assertEqual(payload["confirmations"][1]["match_basis"], "contract_reference")
        draft = payload["drafts"][0]
        self.assertEqual(draft["evidence_kind"], "contract_award")
        self.assertEqual(draft["contract_reference"], "CONTR 2026 0000000001")
        self.assertIn("no_merit_or_blame", draft["claim_status"])
        self.assertIn("merit_blame_not_scored", draft["open_limitations"])


if __name__ == "__main__":
    unittest.main()
