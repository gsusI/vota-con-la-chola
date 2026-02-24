from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_sanction_volume_pilot_seed import validate_seed


def _seed_doc() -> dict:
    return {
        "schema_version": "sanction_volume_pilot_seed_v1",
        "generated_at": "2026-02-23T00:00:00Z",
        "volume_observations": [
            {
                "sanction_source_id": "es:sanctions:test",
                "period_date": "2025-12-31",
                "period_granularity": "year",
                "infraction_type_id": "inf:test",
                "expediente_count": 10,
                "importe_total_eur": 1000.0,
                "source_url": "https://example.org/obs",
            }
        ],
        "procedural_metrics": [
            {
                "kpi_id": "kpi:test",
                "sanction_source_id": "es:sanctions:test",
                "period_date": "2025-12-31",
                "period_granularity": "year",
                "value": 0.1,
                "source_url": "https://example.org/kpi",
            }
        ],
        "municipal_ordinances": [
            {
                "ordinance_id": "es:mun:test:ord",
                "city_name": "Test City",
                "ordinance_label": "Ordenanza test",
                "ordinance_status": "identified",
                "source_url": "https://example.org/ord",
            }
        ],
        "municipal_fragments": [
            {
                "ordinance_fragment_id": "es:mun:test:ord:f1",
                "ordinance_id": "es:mun:test:ord",
                "fragment_label": "Fragmento 1",
            }
        ],
    }


class TestValidateSanctionVolumePilotSeed(unittest.TestCase):
    def test_validate_seed_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seed.json"
            p.write_text(json.dumps(_seed_doc(), ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["volume_observations_total"]), 1)
            self.assertEqual(int(got["procedural_metrics_total"]), 1)
            self.assertEqual(int(got["municipal_ordinances_total"]), 1)
            self.assertEqual(int(got["municipal_fragments_total"]), 1)

    def test_validate_seed_detects_duplicate_ids_and_bad_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            bad["municipal_ordinances"].append(
                {
                    "ordinance_id": "es:mun:test:ord",
                    "city_name": "Dup City",
                    "ordinance_label": "Ordenanza dup",
                    "ordinance_status": "not_valid",
                    "source_url": "https://example.org/ord2",
                }
            )
            p = Path(td) / "seed_bad.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("duplicate_ordinance_id", codes)
            self.assertIn("invalid_ordinance_status", codes)


if __name__ == "__main__":
    unittest.main()
