from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.infoelectoral_es.config import SOURCE_CONFIG as INFO_SOURCE_CONFIG
from etl.infoelectoral_es.db import seed_sources as seed_info_sources
from etl.infoelectoral_es.pipeline import ingest_one_source as ingest_info_one_source
from etl.infoelectoral_es.registry import get_connectors as get_info_connectors
from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions


class TestInfoelectoralSamplesE2E(unittest.TestCase):
    def test_samples_ingest_is_idempotent(self) -> None:
        connectors = get_info_connectors()
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "infoelectoral-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_info_sources(conn)
                seed_dimensions(conn)

                for source_id, connector in connectors.items():
                    sample_path = Path(INFO_SOURCE_CONFIG[source_id]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {source_id}: {sample_path}")
                    ingest_info_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_1 = dict(
                    conn.execute(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM infoelectoral_convocatoria_tipos) AS tipos,
                          (SELECT COUNT(*) FROM infoelectoral_convocatorias) AS convocatorias,
                          (SELECT COUNT(*) FROM infoelectoral_archivos_extraccion) AS archivos
                        """
                    ).fetchone()
                )
                self.assertGreater(counts_1["tipos"], 0)
                self.assertGreater(counts_1["convocatorias"], 0)
                self.assertGreater(counts_1["archivos"], 0)

                fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_issues, [], f"FK issues: {fk_issues}")

                # Run again: upserts should keep totals stable.
                for source_id, connector in connectors.items():
                    sample_path = Path(INFO_SOURCE_CONFIG[source_id]["fallback_file"])
                    ingest_info_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_2 = dict(
                    conn.execute(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM infoelectoral_convocatoria_tipos) AS tipos,
                          (SELECT COUNT(*) FROM infoelectoral_convocatorias) AS convocatorias,
                          (SELECT COUNT(*) FROM infoelectoral_archivos_extraccion) AS archivos
                        """
                    ).fetchone()
                )
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

