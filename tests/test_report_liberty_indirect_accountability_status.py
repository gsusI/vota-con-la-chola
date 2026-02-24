from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_indirect_accountability_status import build_status_report


class TestReportLibertyIndirectAccountabilityStatus(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "indirect_report_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["edges_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "indirect_report_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["indirect_chain_started"]))
        self.assertTrue(bool(got["checks"]["anti_overattribution_guard"]))
        self.assertTrue(bool(got["checks"]["indirect_person_window_gate"]))
        self.assertTrue(bool(got["gate"]["passed"]))
        self.assertEqual(int(got["totals"]["edges_total"]), 12)
        self.assertEqual(int(got["totals"]["attributable_edges_total"]), 9)
        self.assertEqual(int(got["totals"]["attributable_edges_with_valid_person_window_total"]), 9)
        self.assertEqual(float(got["coverage"]["attributable_edges_with_valid_person_window_pct"]), 1.0)

    def test_report_degraded_when_person_window_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "indirect_report_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(
                    conn,
                    attributable_person_window_min=1.1,
                    min_attributable_edges_for_person_window=20,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["indirect_person_window_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))


if __name__ == "__main__":
    unittest.main()
