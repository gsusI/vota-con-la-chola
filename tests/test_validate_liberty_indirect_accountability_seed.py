from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_liberty_indirect_accountability_seed import validate_seed


class TestValidateLibertyIndirectAccountabilitySeed(unittest.TestCase):
    def _valid_doc(self) -> dict:
        return {
            "schema_version": "liberty_indirect_accountability_seed_v1",
            "generated_at": "2026-02-23T00:00:00Z",
            "methodology": {
                "method_version": "indirect_chain_v1",
                "method_label": "Cadena causal indirecta v1",
                "confidence_rules": {
                    "attributable_confidence_min": 0.55,
                    "attributable_max_causal_distance": 2,
                },
            },
            "edges": [
                {
                    "fragment_id": "es:boe-a-test:fragment:1",
                    "actor_label": "Organo A",
                    "actor_person_name": "Persona A",
                    "actor_role_title": "Titular A",
                    "role": "delegate",
                    "direct_actor_label": "Organo B",
                    "appointment_start_date": "2024-01-01",
                    "appointment_end_date": "2026-12-31",
                    "causal_distance": 1,
                    "edge_confidence": 0.7,
                    "evidence_date": "2025-02-01",
                    "source_url": "https://example.org/a",
                },
                {
                    "fragment_id": "es:boe-a-test:fragment:1",
                    "actor_label": "Organo C",
                    "actor_person_name": "Persona B",
                    "actor_role_title": "Titular B",
                    "role": "design",
                    "direct_actor_label": "Organo A",
                    "appointment_start_date": "2024-01-01",
                    "appointment_end_date": "2026-12-31",
                    "causal_distance": 2,
                    "edge_confidence": 0.6,
                    "evidence_date": "2025-03-10",
                    "source_url": "https://example.org/b",
                },
            ],
        }

    def test_valid_seed(self) -> None:
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed.json"
            seed_path.write_text(json.dumps(self._valid_doc()), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertTrue(bool(got["valid"]))
        self.assertEqual(int(got["edges_total"]), 2)
        self.assertEqual(int(got["errors_count"]), 0)

    def test_invalid_seed_detects_errors(self) -> None:
        bad = self._valid_doc()
        bad["schema_version"] = "wrong"
        bad["edges"][0]["role"] = "invalid"
        bad["edges"][0]["edge_confidence"] = 1.5
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)

    def test_invalid_person_window_contract(self) -> None:
        bad = self._valid_doc()
        bad["edges"][0]["actor_person_name"] = ""
        bad["edges"][0]["appointment_start_date"] = "2026-01-01"
        bad["edges"][0]["appointment_end_date"] = "2025-01-01"
        bad["edges"][0]["evidence_date"] = "2024-01-01"
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad_window.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)


if __name__ == "__main__":
    unittest.main()
