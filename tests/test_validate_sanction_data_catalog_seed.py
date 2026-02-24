from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_sanction_data_catalog_seed import validate_seed


def _seed_doc() -> dict:
    return {
        "schema_version": "sanction_data_catalog_seed_v1",
        "generated_at": "2026-02-23T00:00:00Z",
        "volume_sources": [
            {
                "sanction_source_id": "es:sanctions:test",
                "label": "Test source",
                "organismo": "Test org",
                "admin_scope": "estado",
                "territory_scope": "nacional",
                "source_url": "https://example.org/source",
                "expected_metrics": ["expediente_count", "importe_total_eur"],
            }
        ],
        "infraction_types": [
            {
                "infraction_type_id": "inf:test",
                "label": "Test type",
                "domain": "traffic",
                "description": "Test description",
                "canonical_unit": "case",
            }
        ],
        "infraction_mappings": [
            {
                "mapping_scope": "source_only",
                "infraction_type_id": "inf:test",
                "source_system": "test",
                "source_code": "code1",
                "source_label": "Code 1",
                "norm_id": "",
                "fragment_id": "",
                "source_url": "https://example.org/mapping",
            }
        ],
        "procedural_kpis": [
            {
                "kpi_id": "kpi:test",
                "label": "Test KPI",
                "metric_formula": "num/den",
                "target_direction": "lower_is_better",
                "source_requirements": ["num", "den"],
            }
        ],
    }


class TestValidateSanctionDataCatalogSeed(unittest.TestCase):
    def test_validate_seed_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seed.json"
            p.write_text(json.dumps(_seed_doc(), ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["volume_sources_total"]), 1)
            self.assertEqual(int(got["infraction_types_total"]), 1)
            self.assertEqual(int(got["infraction_mappings_total"]), 1)
            self.assertEqual(int(got["procedural_kpis_total"]), 1)

    def test_validate_seed_detects_invalid_mapping_scope_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            bad["infraction_types"].append(
                {
                    "infraction_type_id": "inf:test",
                    "label": "Dup",
                    "domain": "traffic",
                    "description": "Dup",
                }
            )
            bad["infraction_mappings"][0]["mapping_scope"] = "bad_scope"
            p = Path(td) / "seed_bad.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("duplicate_infraction_type_id", codes)
            self.assertIn("invalid_mapping_scope", codes)


if __name__ == "__main__":
    unittest.main()
