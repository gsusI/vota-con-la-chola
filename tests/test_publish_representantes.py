from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.publish import build_representantes_snapshot
from etl.politicos_es.registry import get_connectors


class TestPublishRepresentantes(unittest.TestCase):
    def test_publish_snapshot_is_deterministic_and_traceable(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"

        # Use one connector with no per-record URL and one with detail_url to test fallback + inference.
        source_ids = ["congreso_diputados", "corts_valencianes_diputats"]
        for sid in source_ids:
            self.assertIn(sid, connectors, f"Missing connector: {sid}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                for sid in source_ids:
                    connector = connectors[sid]
                    sample_path = Path(SOURCE_CONFIG[sid]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {sid}: {sample_path}")
                    ingest_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                snap1 = build_representantes_snapshot(conn, snapshot_date=snapshot_date, exclude_levels=("municipal",))
                snap2 = build_representantes_snapshot(conn, snapshot_date=snapshot_date, exclude_levels=("municipal",))
                self.assertEqual(snap1, snap2)

                items = snap1.get("items")
                self.assertIsInstance(items, list)
                self.assertGreater(len(items), 0)

                for it in items[:10]:
                    self.assertIn("person", it)
                    self.assertIn("mandate", it)
                    self.assertIn("institution", it)
                    self.assertIn("source", it)
                    src = it["source"]
                    self.assertTrue(src.get("source_id"))
                    self.assertTrue(src.get("source_record_id"))
                    self.assertTrue(src.get("source_url"))
                    self.assertTrue(src.get("source_hash"))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

