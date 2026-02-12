from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors


class TestCongresoIniciativasSamplesE2E(unittest.TestCase):
    def test_congreso_iniciativas_sample_is_idempotent(self) -> None:
        connectors = get_connectors()
        connector = connectors["congreso_iniciativas"]
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                sample_path = Path(PARL_SOURCE_CONFIG["congreso_iniciativas"]["fallback_file"])
                self.assertTrue(sample_path.exists(), f"Missing sample: {sample_path}")

                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                n1 = int(conn.execute("SELECT COUNT(*) AS c FROM parl_initiatives").fetchone()["c"])
                self.assertGreaterEqual(n1, 3)

                row = conn.execute(
                    "SELECT initiative_id, legislature, expediente, title FROM parl_initiatives ORDER BY initiative_id LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertTrue(str(row["initiative_id"]).startswith("congreso:leg"))
                self.assertIsNotNone(row["legislature"])
                self.assertIsNotNone(row["expediente"])
                self.assertIsNotNone(row["title"])

                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                n2 = int(conn.execute("SELECT COUNT(*) AS c FROM parl_initiatives").fetchone()["c"])
                self.assertEqual(n1, n2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

