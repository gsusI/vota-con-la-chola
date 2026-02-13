from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etl.infoelectoral_es.config import SOURCE_CONFIG as INFO_SOURCE_CONFIG
from etl.infoelectoral_es.connectors.descargas import InfoelectoralDescargasConnector
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
                          (SELECT COUNT(*) FROM infoelectoral_archivos_extraccion) AS archivos,
                          (SELECT COUNT(*) FROM infoelectoral_procesos) AS procesos,
                          (SELECT COUNT(*) FROM infoelectoral_proceso_resultados) AS resultados
                        """
                    ).fetchone()
                )
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()

    def test_network_partial_failures_do_not_abort_extract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"

            tipos_payload = b"""{
                "cod":"200",
                "data":[{"cod":"1","descripcion":"Tipo prueba"}]
            }"""
            convocatorias_payload = b"""{
                "cod":"200",
                "data":[
                  {"cod":"100","fecha":"2024","descripcion":"A","tipoConvocatoria":"1"},
                  {"cod":"198305","fecha":"198305","descripcion":"B","tipoConvocatoria":"1"}
                ]
            }"""
            archivos_payload_ok = b"""{
                "cod":"200",
                "data":[{"nombreDoc":"doc-a.zip","url":"https://example.com/doc-a.zip","descripcion":"Doc A (Madrid)"}]
            }"""
            html_error = b"<html><head>Security Police Violation</head></html>"

            def fake_http_get_bytes(url: str, timeout: int, headers=None, insecure_ssl=False):
                _ = timeout, headers, insecure_ssl
                if "convocatorias/tipos/" in url:
                    return tipos_payload, "application/json"
                if "convocatorias?" in url:
                    return convocatorias_payload, "application/json"
                if "archivos/extraccion" in url:
                    if "idConvocatoria=198305" in url:
                        return html_error, "text/html; charset=iso-8859-1"
                    return archivos_payload_ok, "application/json"
                raise AssertionError(f"Unexpected URL: {url}")

            connector = InfoelectoralDescargasConnector()
            with patch("etl.infoelectoral_es.connectors.descargas.http_get_bytes", side_effect=fake_http_get_bytes):
                extracted = connector.extract(
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=None,
                    url_override=None,
                    strict_network=True,
                )

            kinds = sorted(r["kind"] for r in extracted.records)
            self.assertIn("tipo_convocatoria", kinds)
            self.assertIn("convocatoria", kinds)
            self.assertIn("archivo_extraccion", kinds)
            self.assertEqual(len([k for k in kinds if k == "archivo_extraccion"]), 1)
            self.assertEqual(len(extracted.records), 4)
            self.assertIn("network-with-partial-errors", extracted.note)
            self.assertTrue(extracted.raw_path.exists())


if __name__ == "__main__":
    unittest.main()
