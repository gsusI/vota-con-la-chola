from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_liberty_proportionality_seed import validate_seed


def _seed_doc() -> dict:
    return {
        "schema_version": "liberty_proportionality_seed_v1",
        "generated_at": "2026-02-23T00:00:00Z",
        "methodology": {
            "method_version": "proportionality_v1",
            "method_label": "Proporcionalidad v1",
            "weights": {
                "necessity_score": 0.35,
                "observed_effectiveness_score": 0.25,
                "alternatives_less_restrictive_considered": 0.15,
                "objective_defined": 0.1,
                "indicator_defined": 0.1,
                "sunset_review_present": 0.05,
            },
        },
        "reviews": [
            {
                "fragment_id": "frag:test",
                "objective_defined": 1,
                "indicator_defined": 1,
                "alternatives_less_restrictive_considered": 1,
                "sunset_review_present": 0,
                "observed_effectiveness_score": 0.5,
                "necessity_score": 0.6,
                "assessment_label": "supported",
                "source_url": "https://example.org/test",
            }
        ],
    }


class TestValidateLibertyProportionalitySeed(unittest.TestCase):
    def test_validate_seed_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seed.json"
            p.write_text(json.dumps(_seed_doc(), ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["reviews_total"]), 1)

    def test_validate_seed_detects_invalid_weight_sum_and_duplicate_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            bad["methodology"]["weights"]["sunset_review_present"] = 0.15
            bad["reviews"].append({**bad["reviews"][0]})
            p = Path(td) / "seed_bad.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_weight_sum", codes)
            self.assertIn("duplicate_fragment_id", codes)


if __name__ == "__main__":
    unittest.main()
