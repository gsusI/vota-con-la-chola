from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_data_catalog_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.import_sanction_volume_pilot_seed import import_seed as import_volume_pilot_seed
from scripts.report_sanction_volume_pilot_status import build_status_report


class TestReportSanctionVolumePilotStatus(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "pilot_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["observations_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "pilot_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                data_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json").read_text(encoding="utf-8"))
                volume_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_volume_pilot_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed, source_id="", snapshot_date="2026-02-23")
                import_data_catalog_seed(conn, seed_doc=data_seed, source_id="", snapshot_date="2026-02-23")
                import_volume_pilot_seed(conn, seed_doc=volume_seed, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(conn, top_n=10, dossier_limit=5, sample_limit=20)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["ranking_top_norms_ready"]))
        self.assertTrue(bool(got["checks"]["dossiers_top_norms_ready"]))
        self.assertTrue(bool(got["checks"]["municipal_pilot_catalog_seeded"]))
        self.assertTrue(bool(got["checks"]["municipal_normalization_started"]))
        self.assertEqual(int(got["totals"]["observations_total"]), 9)
        self.assertGreaterEqual(int(got["totals"]["top_norms_total"]), 1)
        self.assertGreaterEqual(len(got["norm_dossiers"]), 1)
        self.assertEqual(int(got["municipal_normalization_progress"]["totals"]["ordinances_total"]), 20)
        self.assertEqual(int(got["municipal_normalization_progress"]["totals"]["normalized_total"]), 3)


if __name__ == "__main__":
    unittest.main()
