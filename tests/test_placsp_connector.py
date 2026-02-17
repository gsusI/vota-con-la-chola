from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.placsp_contracts import (
    PlacspAutonomicoConnector,
    PlacspSindicacionConnector,
    parse_placsp_atom_entries,
)
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source


class TestPlacspConnector(unittest.TestCase):
    def test_extract_from_sample_xml_includes_contracting_fields(self) -> None:
        connector = PlacspSindicacionConnector()
        sample_path = Path("etl/data/raw/samples/placsp_sindicacion_sample.xml")
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
            with_expediente = [r for r in extracted.records if str(r.get("expediente") or "").strip()]
            with_organo = [r for r in extracted.records if str(r.get("organo_contratacion") or "").strip()]
            with_cpv = [r for r in extracted.records if str(r.get("cpv") or "").strip()]
            with_amount = [r for r in extracted.records if r.get("amount_eur") is not None]
            with_pubdate = [r for r in extracted.records if str(r.get("published_at_iso") or "").strip()]
            self.assertGreater(len(with_expediente), 0)
            self.assertGreater(len(with_organo), 0)
            self.assertGreater(len(with_cpv), 0)
            self.assertGreater(len(with_amount), 0)
            self.assertGreater(len(with_pubdate), 0)

            ids = [str(r.get("source_record_id") or "") for r in extracted.records]
            self.assertTrue(all(id_value for id_value in ids))

    def test_parser_source_record_id_is_stable(self) -> None:
        sample_path = Path("etl/data/raw/samples/placsp_sindicacion_sample.xml")
        payload = sample_path.read_bytes()

        records_1 = parse_placsp_atom_entries(
            payload,
            feed_url="https://contrataciondelestado.es/sindicacion/sample.atom",
            content_type="application/atom+xml",
        )
        records_2 = parse_placsp_atom_entries(
            payload,
            feed_url="https://contrataciondelestado.es/sindicacion/sample.atom",
            content_type="application/atom+xml",
        )

        ids_1 = sorted(str(row.get("source_record_id") or "") for row in records_1)
        ids_2 = sorted(str(row.get("source_record_id") or "") for row in records_2)
        self.assertEqual(ids_1, ids_2)

    def test_source_records_ingest_is_idempotent_for_both_placsp_sources(self) -> None:
        snapshot_date = "2026-02-16"
        connectors = [PlacspSindicacionConnector(), PlacspAutonomicoConnector()]
        sample_paths = {
            "placsp_sindicacion": Path("etl/data/raw/samples/placsp_sindicacion_sample.xml"),
            "placsp_autonomico": Path("etl/data/raw/samples/placsp_autonomico_sample.xml"),
        }

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                for connector in connectors:
                    ingest_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_paths[connector.source_id],
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_1 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        """
                        SELECT source_id, COUNT(*) AS c
                        FROM source_records
                        WHERE source_id LIKE 'placsp_%'
                        GROUP BY source_id
                        ORDER BY source_id
                        """
                    ).fetchall()
                }
                self.assertGreater(counts_1.get("placsp_sindicacion", 0), 0)
                self.assertGreater(counts_1.get("placsp_autonomico", 0), 0)

                for connector in connectors:
                    ingest_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_paths[connector.source_id],
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                counts_2 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        """
                        SELECT source_id, COUNT(*) AS c
                        FROM source_records
                        WHERE source_id LIKE 'placsp_%'
                        GROUP BY source_id
                        ORDER BY source_id
                        """
                    ).fetchall()
                }
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

