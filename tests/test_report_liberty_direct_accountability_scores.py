from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_direct_accountability_scores import build_status_report


class TestReportLibertyDirectAccountabilityScores(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "acc_report_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "acc_report_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["direct_chain_started"]))
        self.assertTrue(bool(got["checks"]["responsibility_score_available"]))
        self.assertTrue(bool(got["checks"]["direct_primary_evidence_gate"]))
        self.assertTrue(bool(got["gate"]["passed"]))
        self.assertGreaterEqual(int(got["totals"]["direct_edges_with_primary_evidence_total"]), 1)
        self.assertIn("direct_edges_with_primary_evidence_pct", got["coverage"])
        self.assertGreaterEqual(len(got["top_actor_scores"]), 1)

    def test_report_degraded_when_direct_primary_evidence_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "acc_report_degraded_primary_evidence.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(
                    conn,
                    direct_primary_evidence_min_pct=1.1,
                    min_direct_primary_evidence_edges=20,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["direct_primary_evidence_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))


if __name__ == "__main__":
    unittest.main()
