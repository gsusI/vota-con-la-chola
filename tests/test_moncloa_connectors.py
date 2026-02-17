from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.moncloa_exec import (
    MoncloaReferenciasConnector,
    MoncloaRssReferenciasConnector,
)
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.types import Extracted


class TestMoncloaConnectors(unittest.TestCase):
    def test_referencias_extract_from_sample_html(self) -> None:
        connector = MoncloaReferenciasConnector()
        sample_path = Path("etl/data/raw/samples/moncloa_referencias_sample.html")
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
            self.assertGreaterEqual(len(extracted.records), 2)
            first = extracted.records[0]
            self.assertTrue(str(first.get("stable_id_slug") or "").endswith(".aspx"))
            self.assertTrue(str(first.get("source_url") or "").startswith("https://www.lamoncloa.gob.es/"))

    def test_rss_extract_from_sample_xml(self) -> None:
        connector = MoncloaRssReferenciasConnector()
        sample_path = Path("etl/data/raw/samples/moncloa_rss_referencias_sample.xml")
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
            self.assertGreaterEqual(len(extracted.records), 4)
            feeds = {str(r.get("source_feed") or "") for r in extracted.records}
            self.assertEqual(feeds, {"tipo16"})

    def test_referencias_extract_from_batch_dir_merges_detail(self) -> None:
        connector = MoncloaReferenciasConnector()
        batch_dir = Path("etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216")
        self.assertTrue(batch_dir.exists(), f"Missing batch dir: {batch_dir}")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=batch_dir,
                url_override=None,
                strict_network=True,
            )
            self.assertGreaterEqual(len(extracted.records), 18)
            with_summary = [r for r in extracted.records if str(r.get("summary_text") or "").strip()]
            self.assertGreater(len(with_summary), 0, "Expected summary_text from detail pages")

    def test_moncloa_source_records_ingest_is_idempotent(self) -> None:
        snapshot_date = "2026-02-12"
        connectors = [MoncloaReferenciasConnector(), MoncloaRssReferenciasConnector()]

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                sample_paths = {
                    "moncloa_referencias": Path("etl/data/raw/samples/moncloa_referencias_sample.html"),
                    "moncloa_rss_referencias": Path("etl/data/raw/samples/moncloa_rss_referencias_sample.xml"),
                }

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
                        WHERE source_id LIKE 'moncloa_%'
                        GROUP BY source_id
                        """
                    ).fetchall()
                }
                self.assertGreater(counts_1.get("moncloa_referencias", 0), 0)
                self.assertGreater(counts_1.get("moncloa_rss_referencias", 0), 0)

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
                        WHERE source_id LIKE 'moncloa_%'
                        GROUP BY source_id
                        """
                    ).fetchall()
                }
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()

    def test_strict_network_applies_min_loaded_on_partial_network_note(self) -> None:
        connector = MoncloaReferenciasConnector()
        snapshot_date = "2026-02-16"
        payload = b'{"source":"moncloa_referencias_network","records":[{"stable_id_slug":"referencia-prueba.aspx"}]}'

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / "moncloa_referencias_partial.json"
            raw_path.write_bytes(payload)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                extracted = Extracted(
                    source_id="moncloa_referencias",
                    source_url="https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx",
                    resolved_url="https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx",
                    fetched_at="2026-02-16T00:00:00+00:00",
                    raw_path=raw_path,
                    content_sha256=hashlib.sha256(payload).hexdigest(),
                    content_type="application/json",
                    bytes=len(payload),
                    note="network-with-partial-errors (detail[https://example.invalid]: HTTPError: HTTP Error 500)",
                    payload=payload,
                    records=[
                        {
                            "stable_id_slug": "referencia-prueba.aspx",
                            "source_url": "https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/referencia-prueba.aspx",
                        }
                    ],
                )

                with mock.patch.object(MoncloaReferenciasConnector, "extract", return_value=extracted):
                    with self.assertRaisesRegex(RuntimeError, "strict-network abortado"):
                        ingest_one_source(
                            conn=conn,
                            connector=connector,
                            raw_dir=raw_dir,
                            timeout=5,
                            from_file=None,
                            url_override=None,
                            snapshot_date=snapshot_date,
                            strict_network=True,
                        )

                count_after = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM source_records
                        WHERE source_id = 'moncloa_referencias'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(count_after, 0)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
