from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.boe_legal import BoeApiLegalConnector, parse_boe_rss_items
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source


class TestBoeConnector(unittest.TestCase):
    def test_extract_from_sample_xml(self) -> None:
        connector = BoeApiLegalConnector()
        sample_path = Path("etl/data/raw/samples/boe_api_legal_sample.xml")
        self.assertTrue(sample_path.exists(), f"Missing sample: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=None,
                strict_network=True,
            )
            self.assertGreaterEqual(len(extracted.records), 3)
            refs = {str(row.get("boe_ref") or "") for row in extracted.records}
            self.assertIn("BOE-A-2026-3482", refs)
            self.assertIn("BOE-A-2026-3499", refs)
            ids = [str(row.get("source_record_id") or "") for row in extracted.records]
            self.assertTrue(all(item.startswith("boe_ref:") for item in ids))

    def test_parser_source_record_id_is_stable(self) -> None:
        sample_path = Path("etl/data/raw/samples/boe_api_legal_sample.xml")
        payload = sample_path.read_bytes()
        records_1 = parse_boe_rss_items(payload, feed_url="https://www.boe.es/rss/boe.php", content_type="text/xml")
        records_2 = parse_boe_rss_items(payload, feed_url="https://www.boe.es/rss/boe.php", content_type="text/xml")

        ids_1 = sorted(str(row.get("source_record_id") or "") for row in records_1)
        ids_2 = sorted(str(row.get("source_record_id") or "") for row in records_2)
        self.assertEqual(ids_1, ids_2)

    def test_source_records_ingest_is_idempotent(self) -> None:
        snapshot_date = "2026-02-16"
        connector = BoeApiLegalConnector()
        sample_path = Path("etl/data/raw/samples/boe_api_legal_sample.xml")

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
