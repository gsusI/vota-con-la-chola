from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_sanction_data_catalog_status import build_status_report


class TestReportSanctionDataCatalogStatus(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["volume_sources_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_ok.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json"
                norm_seed_doc = json.loads(norm_seed_path.read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["volume_sources_seeded"]))
        self.assertTrue(bool(got["checks"]["infraction_types_seeded"]))
        self.assertTrue(bool(got["checks"]["mappings_with_fragment_seeded"]))
        self.assertTrue(bool(got["checks"]["procedural_kpis_seeded"]))
        self.assertGreaterEqual(float(got["coverage"]["mapping_fragment_coverage_pct"]), 0.6)


if __name__ == "__main__":
    unittest.main()
