from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.infoelectoral_es.config import DEFAULT_SCHEMA
from etl.infoelectoral_es.config import SOURCE_CONFIG as INFO_SOURCE_CONFIG
from etl.infoelectoral_es.db import seed_sources as seed_info_sources
from etl.infoelectoral_es.pipeline import ingest_one_source
from etl.infoelectoral_es.publish import build_infoelectoral_snapshot
from etl.infoelectoral_es.registry import get_connectors
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions


class TestPublishInfoelectoral(unittest.TestCase):
    def test_publish_snapshot_is_deterministic_and_traceable(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"
        source_id = "infoelectoral_descargas"
        self.assertIn(source_id, connectors)

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "infoelectoral-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                seed_info_sources(conn)
                seed_dimensions(conn)

                connector = connectors[source_id]
                sample_path = Path(INFO_SOURCE_CONFIG[source_id]["fallback_file"])
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

                snap1 = build_infoelectoral_snapshot(conn, snapshot_date=snapshot_date)
                snap2 = build_infoelectoral_snapshot(conn, snapshot_date=snapshot_date)
                self.assertEqual(snap1, snap2)

                self.assertEqual(snap1.get("fecha_referencia"), snapshot_date)
                self.assertIn("tipos", snap1)
                self.assertIsInstance(snap1.get("tipos"), list)
                self.assertGreater(len(snap1["tipos"]), 0)

                tot = snap1.get("totales") or {}
                self.assertIn("tipos", tot)
                self.assertIn("convocatorias", tot)
                self.assertIn("archivos_extraccion", tot)

                first_tipo = snap1["tipos"][0]
                self.assertIn("tipo_convocatoria", first_tipo)
                self.assertIn("convocatorias", first_tipo)
                self.assertIn("source", first_tipo)
                self.assertIn("source_id", first_tipo["source"])

                if first_tipo["convocatorias"]:
                    first_convocatoria = first_tipo["convocatorias"][0]
                    self.assertIn("convocatoria_id", first_convocatoria)
                    self.assertIn("source", first_convocatoria)
                    self.assertIn("archivos", first_convocatoria)

                    if first_convocatoria["archivos"]:
                        first_archivo = first_convocatoria["archivos"][0]
                        self.assertIn("archivo_id", first_archivo)
                        self.assertIn("source", first_archivo)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
