from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_liberty_enforcement_seed import validate_seed


class TestValidateLibertyEnforcementSeed(unittest.TestCase):
    def _valid_doc(self) -> dict:
        return {
            "schema_version": "liberty_enforcement_seed_v1",
            "generated_at": "2026-02-23T00:00:00Z",
            "methodology": {
                "method_version": "enforcement_variation_v1",
                "method_label": "Variacion territorial de enforcement v1",
                "thresholds": {
                    "sanction_rate_spread_pct": 0.35,
                    "annulment_rate_spread_pp": 0.08,
                    "resolution_delay_spread_days": 45,
                },
            },
            "observations": [
                {
                    "fragment_id": "es:boe-a-test:fragment:1",
                    "territory_key": "es-md",
                    "territory_label": "Madrid",
                    "period_date": "2025-12-31",
                    "sanction_rate_per_1000": 10.2,
                    "annulment_rate": 0.1,
                    "resolution_delay_p90_days": 120,
                    "sample_size": 100,
                    "source_url": "https://example.org/a",
                },
                {
                    "fragment_id": "es:boe-a-test:fragment:1",
                    "territory_key": "es-ct",
                    "territory_label": "Cataluna",
                    "period_date": "2025-12-31",
                    "sanction_rate_per_1000": 8.5,
                    "annulment_rate": 0.14,
                    "resolution_delay_p90_days": 150,
                    "sample_size": 80,
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
        self.assertEqual(int(got["observations_total"]), 2)
        self.assertEqual(int(got["errors_count"]), 0)

    def test_invalid_seed_detects_errors(self) -> None:
        bad = self._valid_doc()
        bad["schema_version"] = "wrong"
        bad["observations"][0]["annulment_rate"] = 1.5
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)


if __name__ == "__main__":
    unittest.main()
