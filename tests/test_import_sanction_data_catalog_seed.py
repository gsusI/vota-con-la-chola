from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed


class TestImportSanctionDataCatalogSeed(unittest.TestCase):
    def test_import_seed_upserts_catalog_tables(self) -> None:
        seed_doc = {
            "schema_version": "sanction_data_catalog_seed_v1",
            "volume_sources": [
                {
                    "sanction_source_id": "es:sanctions:test",
                    "label": "Test source",
                    "organismo": "Test org",
                    "admin_scope": "estado",
                    "territory_scope": "nacional",
                    "publication_frequency": "yearly",
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
                    "confidence": 0.8,
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

        with TemporaryDirectory() as td:
            db_path = Path(td) / "catalog.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                got1 = import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got1["counts"]["volume_sources_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["infraction_types_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["infraction_mappings_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["procedural_kpis_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["unresolved_norm_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_fragment_refs"]), 0)

                got2 = import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got2["counts"]["volume_sources_inserted"]), 0)
                self.assertGreaterEqual(int(got2["counts"]["volume_sources_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["infraction_types_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["infraction_mappings_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["procedural_kpis_updated"]), 1)

                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_volume_sources").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_infraction_types").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_infraction_type_mappings").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_kpi_definitions").fetchone()
                self.assertEqual(int(row["n"]), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
