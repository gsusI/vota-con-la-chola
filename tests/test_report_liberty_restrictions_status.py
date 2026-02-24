from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_restrictions_status import build_status_report


class TestReportLibertyRestrictionsStatus(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["assessments_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(conn, top_n=10)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["irlc_started"]))
        self.assertTrue(bool(got["checks"]["restriction_map_started"]))
        self.assertTrue(bool(got["checks"]["rights_with_data_gate"]))
        self.assertTrue(bool(got["checks"]["source_representativity_gate"]))
        self.assertTrue(bool(got["checks"]["scope_representativity_gate"]))
        self.assertTrue(bool(got["checks"]["source_dual_coverage_gate"]))
        self.assertTrue(bool(got["checks"]["scope_dual_coverage_gate"]))
        self.assertTrue(bool(got["checks"]["accountability_primary_evidence_gate"]))
        self.assertTrue(bool(got["focus_gate"]["passed"]))
        self.assertEqual(int(got["totals"]["assessments_total"]), 11)
        self.assertEqual(int(got["totals"]["right_categories_with_data_total"]), 6)
        self.assertGreaterEqual(int(got["totals"]["accountability_edges_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["accountability_edges_with_primary_evidence_total"]), 0)
        self.assertGreaterEqual(int(got["totals"]["sources_with_assessments_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["scopes_with_assessments_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["sources_with_dual_coverage_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["scopes_with_dual_coverage_total"]), 1)
        self.assertIn("accountability_edges_with_primary_evidence_pct", got["coverage"])
        self.assertGreaterEqual(len(got["restriction_map_by_right"]), 1)
        self.assertGreaterEqual(len(got["coverage_by_source"]), 1)
        self.assertGreaterEqual(len(got["coverage_by_scope"]), 1)
        self.assertGreaterEqual(len(got["top_restrictions"]), 1)

    def test_focus_gate_degrades_with_stricter_threshold(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_gate_degraded.db"
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
                    norms_classified_min=0.8,
                    fragments_irlc_min=0.6,
                    fragments_accountability_min=0.6,
                    rights_with_data_min=1.1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["focus_gate"]["passed"]))
        self.assertFalse(bool(got["checks"]["rights_with_data_gate"]))

    def test_report_ignores_norms_without_fragments_in_norms_total(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_ignore_norms_without_fragments.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, scope, topic_hint, source_id, source_url,
                      source_snapshot_date, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2099-1",
                        "BOE-A-2099-1",
                        "Norma de referencia sin fragmentos",
                        "nacional",
                        "ciudadania_sanciones_lineage_ref",
                        None,
                        "https://www.boe.es/",
                        "2026-02-23",
                        "{}",
                        "2026-02-23T00:00:00+00:00",
                        "2026-02-23T00:00:00+00:00",
                    ),
                )
                conn.commit()
                got = build_status_report(conn, top_n=10)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["norms_total"]), 8)

    def test_focus_gate_degrades_with_source_scope_diversity_thresholds(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_gate_degraded_source_scope.db"
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
                    min_assessment_sources=2,
                    min_assessment_scopes=2,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["focus_gate"]["passed"]))
        self.assertFalse(bool(got["checks"]["source_representativity_gate"]))
        self.assertFalse(bool(got["checks"]["scope_representativity_gate"]))

    def test_focus_gate_degrades_with_source_scope_dual_coverage_thresholds(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_gate_degraded_source_scope_dual.db"
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
                    min_dual_coverage_sources=2,
                    min_dual_coverage_scopes=2,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["focus_gate"]["passed"]))
        self.assertFalse(bool(got["checks"]["source_dual_coverage_gate"]))
        self.assertFalse(bool(got["checks"]["scope_dual_coverage_gate"]))

    def test_focus_gate_degrades_with_accountability_primary_evidence_thresholds(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "report_gate_degraded_accountability_primary_evidence.db"
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
                    accountability_primary_evidence_min_pct=1.1,
                    min_accountability_primary_evidence_edges=20,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["focus_gate"]["passed"]))
        self.assertFalse(bool(got["checks"]["accountability_primary_evidence_gate"]))


if __name__ == "__main__":
    unittest.main()
