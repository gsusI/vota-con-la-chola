from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_liberty_delegated_enforcement_seed import validate_seed


class TestValidateLibertyDelegatedEnforcementSeed(unittest.TestCase):
    def _valid_doc(self) -> dict:
        return {
            "schema_version": "liberty_delegated_enforcement_seed_v1",
            "generated_at": "2026-02-23T00:00:00Z",
            "methodology": {
                "method_version": "delegated_enforcement_v1",
                "method_label": "Cadena delegada de enforcement v1",
                "rules": {
                    "target_fragment_coverage_min": 0.6,
                    "designated_actor_coverage_min": 0.5,
                    "enforcement_evidence_coverage_min": 0.7,
                },
            },
            "links": [
                {
                    "fragment_id": "es:boe-a-test:fragment:1",
                    "delegating_actor_label": "Ministerio A",
                    "delegated_institution_label": "Organismo B",
                    "designated_role_title": "Direccion",
                    "designated_actor_label": "Actor B",
                    "enforcement_action_label": "Acto X",
                    "source_url": "https://example.org/a",
                    "chain_confidence": 0.8,
                }
            ],
        }

    def test_valid_seed(self) -> None:
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed.json"
            seed_path.write_text(json.dumps(self._valid_doc()), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertTrue(bool(got["valid"]))
        self.assertEqual(int(got["links_total"]), 1)

    def test_invalid_seed_detects_errors(self) -> None:
        bad = self._valid_doc()
        bad["schema_version"] = "wrong"
        bad["links"][0]["source_url"] = "ftp://nope"
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)


if __name__ == "__main__":
    unittest.main()
