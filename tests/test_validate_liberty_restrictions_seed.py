from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_liberty_restrictions_seed import validate_seed


def _seed_doc() -> dict:
    return {
        "schema_version": "liberty_restrictions_seed_v1",
        "generated_at": "2026-02-23T00:00:00Z",
        "methodology": {
            "method_version": "irlc_v1",
            "method_label": "IRLC v1",
            "scale_max": 100.0,
            "weights": {
                "reach_score": 0.2,
                "intensity_score": 0.25,
                "due_process_risk_score": 0.2,
                "reversibility_risk_score": 0.1,
                "discretionality_score": 0.15,
                "compliance_cost_score": 0.1,
            },
        },
        "right_categories": [
            {"right_category_id": "right:test", "label": "Test", "description": "desc"},
        ],
        "fragment_assessments": [
            {
                "fragment_id": "frag:test",
                "right_category_id": "right:test",
                "reach_score": 0.5,
                "intensity_score": 0.5,
                "due_process_risk_score": 0.5,
                "reversibility_risk_score": 0.5,
                "discretionality_score": 0.5,
                "compliance_cost_score": 0.5,
                "source_url": "https://example.org/seed",
            }
        ],
    }


class TestValidateLibertyRestrictionsSeed(unittest.TestCase):
    def test_validate_seed_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seed.json"
            p.write_text(json.dumps(_seed_doc(), ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["right_categories_total"]), 1)
            self.assertEqual(int(got["fragment_assessments_total"]), 1)

    def test_validate_seed_detects_invalid_weight_sum_and_duplicate_right(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            bad["methodology"]["weights"]["compliance_cost_score"] = 0.2
            bad["right_categories"].append({"right_category_id": "right:test", "label": "dup", "description": "dup"})
            p = Path(td) / "seed_bad.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_weight_sum", codes)
            self.assertIn("duplicate_right_category_id", codes)


if __name__ == "__main__":
    unittest.main()
