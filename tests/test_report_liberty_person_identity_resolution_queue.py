from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_person_identity_resolution_seed import import_seed as import_identity_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_person_identity_resolution_queue import build_report


def _seed_rights(conn, root: Path) -> None:
    norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
    liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
    indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
    import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
    import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
    import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")


class TestReportLibertyPersonIdentityResolutionQueue(unittest.TestCase):
    def test_report_ok_with_unresolved_queue(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                got = build_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["queue_generated"]))
        self.assertTrue(bool(got["checks"]["unresolved_backlog_visible"]))
        self.assertTrue(bool(got["checks"]["manual_alias_upgrade_backlog_visible"]))
        self.assertTrue(bool(got["checks"]["official_alias_evidence_backlog_visible"]))
        self.assertTrue(bool(got["checks"]["official_alias_source_record_backlog_visible"]))
        self.assertTrue(bool(got["checks"]["manual_alias_share_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_share_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_evidence_gate"]))
        self.assertTrue(bool(got["checks"]["official_alias_source_record_gate"]))
        self.assertTrue(bool(got["checks"]["identity_resolution_gate"]))
        self.assertGreaterEqual(int(got["totals"]["indirect_person_edges_valid_window_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["indirect_person_edges_unresolved_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["queue_rows_total"]), 1)
        self.assertEqual(int(got["totals"]["aliases_total"]), 0)
        self.assertEqual(int(got["totals"]["manual_alias_upgrade_queue_rows_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_with_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_rows_missing_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_evidence_upgrade_queue_rows_total"]), 0)
        self.assertEqual(int(got["totals"]["official_alias_source_record_upgrade_queue_rows_total"]), 0)
        self.assertGreater(float(got["coverage"]["indirect_identity_unresolved_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["official_alias_share_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["official_alias_evidence_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["official_alias_source_record_coverage_pct"]), 1.0)
        self.assertGreaterEqual(len(got["queue_preview"]), 1)

    def test_report_degraded_when_identity_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                got = build_report(
                    conn,
                    identity_resolution_min_pct=1.0,
                    min_indirect_person_edges=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["identity_resolution_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))

    def test_identity_resolution_increases_with_matching_person(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_resolved.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)

                actor_name = str(
                    conn.execute(
                        """
                        SELECT TRIM(actor_person_name)
                        FROM liberty_indirect_responsibility_edges
                        WHERE TRIM(COALESCE(actor_person_name, '')) <> ''
                        ORDER BY edge_id ASC
                        LIMIT 1
                        """
                    ).fetchone()[0]
                )
                ts = "2026-02-23T00:00:00+00:00"
                canonical_key = "manual::" + hashlib.sha256(actor_name.strip().lower().encode("utf-8")).hexdigest()[:24]
                conn.execute(
                    """
                    INSERT INTO persons (
                      full_name, territory_code, canonical_key, created_at, updated_at
                    )
                    VALUES (?, '', ?, ?, ?)
                    """,
                    (actor_name, canonical_key, ts, ts),
                )
                conn.commit()
                got = build_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertGreaterEqual(int(got["totals"]["indirect_person_edges_identity_resolved_total"]), 1)
        self.assertGreater(float(got["coverage"]["indirect_identity_resolution_pct"]), 0.0)
        self.assertLess(
            int(got["totals"]["indirect_person_edges_unresolved_total"]),
            int(got["totals"]["indirect_person_edges_valid_window_total"]),
        )

    def test_report_degraded_when_non_manual_alias_resolution_threshold_is_impossible(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_non_manual_alias_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)

                identity_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_report(
                    conn,
                    non_manual_alias_resolution_min_pct=1.0,
                    min_non_manual_alias_resolution_edges=1,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["identity_non_manual_alias_resolution_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))
        self.assertEqual(int(got["totals"]["manual_alias_upgrade_queue_rows_total"]), 9)
        self.assertEqual(int(got["totals"]["manual_alias_rows_with_edge_impact_total"]), 9)
        self.assertGreaterEqual(len(got["manual_alias_upgrade_queue_preview"]), 1)

    def test_report_degraded_when_manual_alias_share_threshold_is_strict(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_manual_alias_share_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                identity_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_report(
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
            db_path = Path(td) / "identity_queue_official_alias_evidence_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                identity_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                upgraded = json.loads(json.dumps(identity_seed_doc))
                upgraded["mappings"][0]["source_kind"] = "official_nombramiento"
                upgraded["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
                upgraded["mappings"][0]["evidence_date"] = "2024-01-02"
                upgraded["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."
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
                got = build_report(
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
        self.assertEqual(int(got["totals"]["official_alias_evidence_upgrade_queue_rows_total"]), 1)
        self.assertEqual(float(got["coverage"]["official_alias_evidence_coverage_pct"]), 0.0)
        self.assertTrue(bool(got["checks"]["official_alias_evidence_backlog_visible"]))
        self.assertFalse(bool(got["checks"]["official_alias_evidence_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))
        self.assertGreaterEqual(len(got["official_alias_evidence_upgrade_queue_preview"]), 1)
        top_gap_row = got["official_alias_evidence_upgrade_queue_preview"][0]
        self.assertEqual(str(top_gap_row["source_kind"]), "official_nombramiento")
        self.assertEqual(str(top_gap_row["missing_fields_csv"]), "source_url, evidence_date, evidence_quote")

    def test_report_degraded_when_official_alias_source_record_is_missing(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_official_alias_source_record_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                identity_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                upgraded = json.loads(json.dumps(identity_seed_doc))
                upgraded["mappings"][0]["source_kind"] = "official_nombramiento"
                upgraded["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
                upgraded["mappings"][0]["evidence_date"] = "2024-01-02"
                upgraded["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."
                import_identity_seed(conn, seed_doc=upgraded, source_id="", snapshot_date="2026-02-23")
                got = build_report(
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
        self.assertEqual(int(got["totals"]["official_alias_source_record_upgrade_queue_rows_total"]), 1)
        self.assertEqual(float(got["coverage"]["official_alias_source_record_coverage_pct"]), 0.0)
        self.assertTrue(bool(got["checks"]["official_alias_source_record_backlog_visible"]))
        self.assertFalse(bool(got["checks"]["official_alias_source_record_gate"]))
        self.assertFalse(bool(got["gate"]["passed"]))
        self.assertGreaterEqual(len(got["official_alias_source_record_upgrade_queue_preview"]), 1)
        top_gap_row = got["official_alias_source_record_upgrade_queue_preview"][0]
        self.assertEqual(str(top_gap_row["source_kind"]), "official_nombramiento")
        self.assertEqual(int(top_gap_row["source_record_pk"]), 0)

    def test_report_degraded_when_official_alias_share_threshold_is_strict(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_queue_official_alias_share_degraded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                identity_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_report(
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
