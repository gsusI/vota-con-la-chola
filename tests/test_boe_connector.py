from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.boe_legal import BoeApiLegalConnector, parse_boe_payload, parse_boe_rss_items
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source


class TestBoeConnector(unittest.TestCase):
    def test_parse_open_data_summary_json_preserves_legal_context(self) -> None:
        payload = {
            "status": {"code": "200", "text": "ok"},
            "data": {
                "sumario": {
                    "metadatos": {"publicacion": "BOE", "fecha_publicacion": "20260212"},
                    "diario": [
                        {
                            "numero": "38",
                            "sumario_diario": {
                                "identificador": "BOE-S-2026-38",
                                "url_pdf": {
                                    "texto": "https://www.boe.es/boe/dias/2026/02/12/pdfs/BOE-S-2026-38.pdf"
                                },
                            },
                            "seccion": [
                                {
                                    "codigo": "2A",
                                    "nombre": "II.A. Nombramientos, situaciones e incidencias",
                                    "departamento": [
                                        {
                                            "codigo": "6111",
                                            "nombre": "MINISTERIO DE DEFENSA",
                                            "epigrafe": [
                                                {
                                                    "nombre": "Ceses",
                                                    "item": [
                                                        {
                                                            "identificador": "BOE-A-2026-3221",
                                                            "control": "2026/2521",
                                                            "titulo": (
                                                                "Real Decreto 94/2026, de 11 de febrero, por el "
                                                                "que se dispone el cese de Dona Test Persona "
                                                                "como Directora General."
                                                            ),
                                                            "url_html": (
                                                                "https://www.boe.es/diario_boe/txt.php"
                                                                "?id=BOE-A-2026-3221"
                                                            ),
                                                            "url_xml": (
                                                                "https://www.boe.es/diario_boe/xml.php"
                                                                "?id=BOE-A-2026-3221"
                                                            ),
                                                            "url_pdf": {
                                                                "pagina_inicial": "22110",
                                                                "pagina_final": "22111",
                                                                "texto": (
                                                                    "https://www.boe.es/boe/dias/2026/02/12/pdfs/"
                                                                    "BOE-A-2026-3221.pdf"
                                                                ),
                                                            },
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
        }

        records = parse_boe_payload(
            json.dumps(payload).encode("utf-8"),
            feed_url="https://www.boe.es/datosabiertos/api/boe/sumario/20260212",
            content_type="application/json",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["source_record_id"], "boe_ref:BOE-A-2026-3221")
        self.assertEqual(record["record_kind"], "boe_summary_item")
        self.assertEqual(record["published_at_iso"], "2026-02-12")
        self.assertEqual(record["daily_summary_id"], "BOE-S-2026-38")
        self.assertEqual(record["section_code"], "2A")
        self.assertEqual(record["department_name"], "MINISTERIO DE DEFENSA")
        self.assertEqual(record["epigraph_name"], "Ceses")
        self.assertEqual(
            record["source_url"],
            "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3221",
        )

    def test_extract_open_data_summary_json_file_is_idempotent_source_record_input(self) -> None:
        payload = {
            "status": {"code": "200", "text": "ok"},
            "data": {
                "sumario": {
                    "metadatos": {"fecha_publicacion": "20260212"},
                    "diario": {
                        "sumario_diario": {"identificador": "BOE-S-2026-38"},
                        "seccion": {
                            "codigo": "1",
                            "nombre": "I. Disposiciones generales",
                            "departamento": {
                                "codigo": "9568",
                                "nombre": "MINISTERIO PARA LA TRANSICION ECOLOGICA",
                                "epigrafe": {
                                    "nombre": "Energia electrica",
                                    "item": {
                                        "identificador": "BOE-A-2026-3212",
                                        "titulo": "Real Decreto 88/2026, de 11 de febrero.",
                                        "url_html": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3212",
                                    },
                                },
                            },
                        },
                    },
                }
            },
        }

        with tempfile.TemporaryDirectory() as td:
            sample_path = Path(td) / "boe-summary.json"
            sample_path.write_text(json.dumps(payload), encoding="utf-8")
            extracted = BoeApiLegalConnector().extract(
                raw_dir=Path(td) / "raw",
                timeout=5,
                from_file=sample_path,
                url_override=None,
                strict_network=True,
            )

        self.assertEqual(len(extracted.records), 1)
        self.assertEqual(extracted.records[0]["source_record_id"], "boe_ref:BOE-A-2026-3212")
        self.assertEqual(extracted.records[0]["published_at_iso"], "2026-02-12")

    def test_extract_from_official_capture_xml(self) -> None:
        connector = BoeApiLegalConnector()
        sample_path = Path("etl/data/raw/official-captures/boe/boe-rss-20260812.xml")
        self.assertTrue(sample_path.exists(), f"Missing official capture: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=None,
                strict_network=True,
            )
            self.assertGreaterEqual(len(extracted.records), 100)
            refs = {str(row.get("boe_ref") or "") for row in extracted.records}
            self.assertIn("BOE-A-2026-17573", refs)
            self.assertIn("BOE-A-2026-17574", refs)
            ids = [str(row.get("source_record_id") or "") for row in extracted.records]
            self.assertTrue(all(item.startswith("boe_ref:") for item in ids))

    def test_parser_source_record_id_is_stable(self) -> None:
        sample_path = Path("etl/data/raw/official-captures/boe/boe-rss-20260812.xml")
        payload = sample_path.read_bytes()
        records_1 = parse_boe_rss_items(payload, feed_url="https://www.boe.es/rss/boe.php", content_type="text/xml")
        records_2 = parse_boe_rss_items(payload, feed_url="https://www.boe.es/rss/boe.php", content_type="text/xml")

        ids_1 = sorted(str(row.get("source_record_id") or "") for row in records_1)
        ids_2 = sorted(str(row.get("source_record_id") or "") for row in records_2)
        self.assertEqual(ids_1, ids_2)

    def test_source_records_ingest_is_idempotent(self) -> None:
        snapshot_date = "2026-08-12"
        connector = BoeApiLegalConnector()
        sample_path = Path("etl/data/raw/official-captures/boe/boe-rss-20260812.xml")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

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

                count_1 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM source_records
                        WHERE source_id = 'boe_api_legal'
                        """
                    ).fetchone()["c"]
                )
                self.assertGreater(count_1, 0)

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

                count_2 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM source_records
                        WHERE source_id = 'boe_api_legal'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(count_1, count_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
