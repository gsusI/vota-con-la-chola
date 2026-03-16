from __future__ import annotations

import unittest

from scripts.apply_liberty_delegated_person_window_reviews import apply_review_decisions


class TestApplyLibertyDelegatedPersonWindowReviews(unittest.TestCase):
    def test_apply_updates_seed_link_when_approved(self) -> None:
        seed_doc = {
            "schema_version": "liberty_delegated_enforcement_seed_v1",
            "generated_at": "2026-02-23T00:00:00Z",
            "methodology": {
                "method_version": "delegated_enforcement_v1",
                "method_label": "test",
                "rules": {
                    "target_fragment_coverage_min": 0.6,
                    "designated_actor_coverage_min": 0.5,
                    "enforcement_evidence_coverage_min": 0.7,
                },
            },
            "links": [
                {
                    "fragment_id": "es:boe-a-2000-15060:fragment:articulo:bloque-de-tipificacion-laboral",
                    "delegating_actor_label": "Ministerio de Trabajo",
                    "delegated_institution_label": "Inspeccion de Trabajo y Seguridad Social",
                    "designated_role_title": "Jefatura de Inspeccion",
                    "designated_actor_label": "",
                    "appointment_start_date": "2024-01-01",
                    "appointment_end_date": "",
                    "enforcement_action_label": "Tipificacion e impulso sancionador en orden social",
                    "enforcement_evidence_date": "",
                    "chain_confidence": 0.63,
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                    "evidence_quote": "quote",
                    "link_key": "delegated_enforcement_v1|es:boe-a-2000-15060:fragment:articulo:bloque-de-tipificacion-laboral|Ministerio de Trabajo|Inspeccion de Trabajo y Seguridad Social||https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                }
            ],
        }
        rows = [
            {
                "decision": "approved",
                "link_key": "delegated_enforcement_v1|es:boe-a-2000-15060:fragment:articulo:bloque-de-tipificacion-laboral|Ministerio de Trabajo|Inspeccion de Trabajo y Seguridad Social||https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                "reviewed_designated_actor_label": "Nombre Persona Ejemplo",
                "reviewed_enforcement_evidence_date": "2025-12-31",
                "reviewed_source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-99999",
                "reviewed_evidence_quote": "Nombramiento oficial de la persona para el cargo.",
                "review_note": "validado",
            }
        ]

        updated_seed_doc, meta = apply_review_decisions(seed_doc, rows=rows)
        counts = meta["counts"]
        self.assertEqual(int(counts["approved_rows"]), 1)
        self.assertEqual(int(counts["updated_rows"]), 1)
        link = updated_seed_doc["links"][0]
        self.assertEqual(str(link["designated_actor_label"]), "Nombre Persona Ejemplo")
        self.assertEqual(str(link["enforcement_evidence_date"]), "2025-12-31")
        self.assertIn("review:validado", str(link["evidence_quote"]))


if __name__ == "__main__":
    unittest.main()
