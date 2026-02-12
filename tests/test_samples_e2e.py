from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors


class TestSamplesE2E(unittest.TestCase):
    def test_samples_ingest_is_idempotent(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                for source_id, connector in connectors.items():
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {source_id}: {sample_path}")
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

                counts_1 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM mandates GROUP BY source_id"
                    ).fetchall()
                }
                self.assertTrue(counts_1, "Expected mandates after ingesting samples")
                for source_id in connectors:
                    self.assertGreater(counts_1.get(source_id, 0), 0, f"Expected mandates for {source_id}")

                # Run again: mandates are keyed by (source_id, source_record_id) so totals must stay stable.
                for source_id, connector in connectors.items():
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
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

                counts_2 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM mandates GROUP BY source_id"
                    ).fetchall()
                }
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

