from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.infoelectoral_es.db import seed_sources as seed_info_sources
from etl.infoelectoral_es.pipeline import ingest_one_source as ingest_info_one_source
from etl.infoelectoral_es.registry import get_connectors as get_info_connectors
from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions

INFOELECTORAL_OFFICIAL_CAPTURES = {
    "infoelectoral_descargas": Path(
        "etl/data/raw/infoelectoral_descargas/2026/02/25/"
        "infoelectoral_descargas_20260225T172351Z.json"
    ),
    "infoelectoral_procesos": Path(
        "etl/data/raw/infoelectoral_procesos/2026/02/25/"
        "infoelectoral_procesos_20260225T172425Z.json"
    ),
}
INFOELECTORAL_OFFICIAL_URLS = {
    "infoelectoral_descargas": "https://infoelectoral.interior.gob.es/min/convocatorias/tipos/",
    "infoelectoral_procesos": "https://infoelectoral.interior.gob.es/min/procesos/",
}


class TestInfoelectoralSamplesE2E(unittest.TestCase):
    def test_official_captures_ingest_is_idempotent(self) -> None:
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
                    capture_path = INFOELECTORAL_OFFICIAL_CAPTURES[source_id]
                    self.assertTrue(
                        capture_path.is_file(),
                        f"Missing official capture for {source_id}: {capture_path}",
                    )
                    ingest_info_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=capture_path,
                        url_override=INFOELECTORAL_OFFICIAL_URLS[source_id],
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_1 = dict(
                    conn.execute(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM infoelectoral_convocatoria_tipos) AS tipos,
                          (SELECT COUNT(*) FROM infoelectoral_convocatorias) AS convocatorias,
                          (SELECT COUNT(*) FROM infoelectoral_archivos_extraccion) AS archivos,
                          (SELECT COUNT(*) FROM infoelectoral_procesos) AS procesos,
                          (SELECT COUNT(*) FROM infoelectoral_proceso_resultados) AS resultados
                        """
                    ).fetchone()
                )
                self.assertGreater(counts_1["tipos"], 0)
                self.assertGreater(counts_1["convocatorias"], 0)
                self.assertGreater(counts_1["archivos"], 0)
                self.assertGreater(counts_1["procesos"], 0)
                self.assertGreater(counts_1["resultados"], 0)

                fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_issues, [], f"FK issues: {fk_issues}")

                # Run again: upserts should keep totals stable.
                for source_id, connector in connectors.items():
                    ingest_info_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=INFOELECTORAL_OFFICIAL_CAPTURES[source_id],
                        url_override=INFOELECTORAL_OFFICIAL_URLS[source_id],
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_2 = dict(
                    conn.execute(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM infoelectoral_convocatoria_tipos) AS tipos,
                          (SELECT COUNT(*) FROM infoelectoral_convocatorias) AS convocatorias,
                          (SELECT COUNT(*) FROM infoelectoral_archivos_extraccion) AS archivos,
                          (SELECT COUNT(*) FROM infoelectoral_procesos) AS procesos,
                          (SELECT COUNT(*) FROM infoelectoral_proceso_resultados) AS resultados
                        """
                    ).fetchone()
                )
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()

    def test_official_descargas_capture_preserves_all_record_kinds(self) -> None:
        connector = get_info_connectors()["infoelectoral_descargas"]
        capture_path = INFOELECTORAL_OFFICIAL_CAPTURES["infoelectoral_descargas"]
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=capture_path,
                url_override=INFOELECTORAL_OFFICIAL_URLS["infoelectoral_descargas"],
                strict_network=True,
            )

            kinds = {str(row.get("kind") or "") for row in extracted.records}
            self.assertTrue(
                {"tipo_convocatoria", "convocatoria", "archivo_extraccion"}.issubset(
                    kinds
                )
            )
            self.assertEqual(
                extracted.source_url,
                INFOELECTORAL_OFFICIAL_URLS["infoelectoral_descargas"],
            )
            self.assertEqual(extracted.note, "from-file")
            self.assertTrue(extracted.raw_path.exists())


if __name__ == "__main__":
    unittest.main()
