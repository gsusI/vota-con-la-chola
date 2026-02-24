from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_proportionality_seed import import_seed as import_prop_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_proportionality_status import build_status_report


class TestReportLibertyProportionalityStatus(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "prop_report_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["reviews_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "prop_report_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                prop_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_proportionality_seed_v1.json").read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_prop_seed(conn, seed_doc=prop_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["proportionality_started"]))
        self.assertTrue(bool(got["gate"]["passed"]))
        self.assertEqual(int(got["totals"]["reviews_total"]), 8)
        self.assertGreaterEqual(len(got["by_assessment_label"]), 1)


if __name__ == "__main__":
    unittest.main()
