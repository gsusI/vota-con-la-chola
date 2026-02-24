from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_person_identity_resolution_seed import import_seed as import_identity_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_personal_accountability_scores import build_status_report


class TestReportLibertyPersonalAccountabilityScores(unittest.TestCase):
    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["persons_scored_total"]), 0)

    def test_report_ok_when_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_ok.db"
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
        self.assertTrue(bool(got["checks"]["personal_scores_available"]))
        self.assertTrue(bool(got["checks"]["indirect_person_window_gate"]))
        self.assertTrue(bool(got["checks"]["indirect_identity_resolution_gate"]))
        self.assertTrue(bool(got["gate"]["passed"]))
        self.assertGreaterEqual(int(got["totals"]["persons_scored_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["indirect_person_edges_valid_window_total"]), 1)
        self.assertIn("personal_edges_with_primary_evidence_pct", got["coverage"])
        self.assertIn("indirect_identity_resolution_pct", got["coverage"])
        self.assertGreaterEqual(len(got["top_person_scores"]), 1)

    def test_report_degraded_when_thresholds_are_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_degraded.db"
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
                    personal_fragment_coverage_min=1.1,
                    personal_primary_evidence_min_pct=1.1,
                    min_personal_primary_evidence_edges=20,
                    min_persons_scored=20,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["gate"]["passed"]))
        self.assertFalse(bool(got["checks"]["min_persons_scored_gate"]))

    def test_report_degraded_when_identity_resolution_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_identity_gate.db"
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
                    indirect_identity_resolution_min_pct=1.0,
                    min_indirect_identity_resolution_edges=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["indirect_identity_resolution_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_persons_scored_total_not_truncated_by_top_n(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_topn.db"
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

                got_full = build_status_report(conn, top_n=200)
                got_top1 = build_status_report(conn, top_n=1)
            finally:
                conn.close()

        self.assertEqual(int(got_full["totals"]["persons_scored_total"]), int(got_top1["totals"]["persons_scored_total"]))
        self.assertGreaterEqual(int(got_top1["totals"]["persons_scored_total"]), len(got_top1["top_person_scores"]))
        self.assertEqual(int(got_top1["totals"]["top_person_scores_total"]), len(got_top1["top_person_scores"]))
        self.assertEqual(len(got_top1["top_person_scores"]), 1)

    def test_identity_resolution_uses_alias_mappings(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_identity_alias.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["indirect_person_edges_identity_resolved_total"]), 9)
        self.assertEqual(int(got["totals"]["indirect_person_edges_identity_resolved_alias_total"]), 9)
        self.assertEqual(int(got["totals"]["indirect_person_edges_identity_resolved_alias_non_manual_total"]), 0)
        self.assertEqual(int(got["totals"]["indirect_person_edges_identity_resolved_alias_manual_total"]), 9)
        self.assertEqual(int(got["totals"]["aliases_total"]), 9)
        self.assertEqual(int(got["totals"]["manual_alias_rows_total"]), 9)
        self.assertEqual(int(got["totals"]["manual_alias_rows_with_edge_impact_total"]), 9)
        self.assertEqual(int(got["totals"]["manual_alias_edges_with_impact_total"]), 9)
        self.assertEqual(int(got["totals"]["official_alias_rows_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_source_record_total"]), 0)
        self.assertEqual(float(got["coverage"]["indirect_non_manual_alias_resolution_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["manual_alias_share_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["manual_alias_upgrade_edge_impact_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["official_alias_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["official_alias_evidence_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["official_alias_source_record_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["indirect_identity_resolution_pct"]), 1.0)
        self.assertTrue(bool(got["checks"]["manual_alias_share_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_share_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_evidence_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_source_record_gate"]))

    def test_report_degraded_when_non_manual_alias_resolution_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_non_manual_alias_gate.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(
                    conn,
                    indirect_non_manual_alias_resolution_min_pct=1.0,
                    min_indirect_non_manual_alias_resolution_edges=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["indirect_non_manual_alias_resolution_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_report_degraded_when_manual_alias_share_threshold_is_strict(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_manual_alias_share_gate.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(
                    conn,
                    manual_alias_share_max=0.0,
                    min_alias_rows_for_manual_share_gate=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["manual_alias_share_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_report_degraded_when_official_alias_evidence_is_missing(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_official_alias_evidence_gate.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                upgraded = json.loads(json.dumps(identity_seed_doc))
                upgraded["mappings"][0]["source_kind"] = "official_nombramiento"
                upgraded["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
                upgraded["mappings"][0]["evidence_date"] = "2024-01-02"
                upgraded["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=upgraded, source_id="", snapshot_date="2026-02-23")
                conn.execute(
                    """
                    UPDATE person_name_aliases
                    SET source_url = NULL, evidence_date = NULL, evidence_quote = NULL
                    WHERE canonical_alias = ?
                    """,
                    ("persona seed empleo nombramientos",),
                )
                conn.commit()

                got = build_status_report(
                    conn,
                    official_alias_evidence_min_pct=1.0,
                    min_official_alias_rows_for_evidence_gate=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["official_alias_rows_total"]), 1)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_evidence_total"]), 1)
        self.assertEqual(float(got["coverage"]["official_alias_evidence_coverage_pct"]), 0.0)
        self.assertFalse(bool(got["checks"]["official_alias_evidence_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_report_degraded_when_official_alias_source_record_is_missing(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_official_alias_source_record_gate.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                upgraded = json.loads(json.dumps(identity_seed_doc))
                upgraded["mappings"][0]["source_kind"] = "official_nombramiento"
                upgraded["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
                upgraded["mappings"][0]["evidence_date"] = "2024-01-02"
                upgraded["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=upgraded, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(
                    conn,
                    official_alias_source_record_min_pct=1.0,
                    min_official_alias_rows_for_source_record_gate=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["official_alias_rows_total"]), 1)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_source_record_total"]), 1)
        self.assertEqual(float(got["coverage"]["official_alias_source_record_coverage_pct"]), 0.0)
        self.assertFalse(bool(got["checks"]["official_alias_source_record_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_report_degraded_when_official_alias_share_threshold_is_strict(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "personal_report_official_alias_share_gate.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_status_report(
                    conn,
                    official_alias_share_min_pct=0.1,
                    min_alias_rows_for_official_share_gate=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["aliases_total"]), 9)
        self.assertEqual(int(got["totals"]["official_alias_rows_total"]), 0)
        self.assertEqual(float(got["coverage"]["official_alias_share_pct"]), 0.0)
        self.assertFalse(bool(got["checks"]["official_alias_share_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))


if __name__ == "__main__":
    unittest.main()
