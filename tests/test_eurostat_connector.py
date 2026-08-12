from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.eurostat_indicators import (
    EurostatSdmxConnector,
    parse_eurostat_records,
)
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source

EUROSTAT_OFFICIAL_CAPTURE = Path(
    "etl/data/object-origin/eurostat-indicators/fc/a5/"
    "fca5f0c54754173cab1048a6ca52e2e9f7094ca8fa1220f2c29babd9a3911018.json"
)
EUROSTAT_OFFICIAL_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "ilc_peps11n?lang=EN&sinceTimePeriod=2015"
)


class TestEurostatConnector(unittest.TestCase):
    def test_extract_from_official_capture_has_series_unit_and_dimensions(self) -> None:
        connector = EurostatSdmxConnector()
        sample_path = EUROSTAT_OFFICIAL_CAPTURE
        self.assertTrue(sample_path.exists(), f"Missing official capture: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td) / "raw"
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=EUROSTAT_OFFICIAL_URL,
                strict_network=True,
            )
            self.assertGreaterEqual(len(extracted.records), 2)
            first = extracted.records[0]
            self.assertTrue(str(first.get("series_code") or "").strip())
            self.assertTrue(str(first.get("unit") or "").strip())
            self.assertTrue(isinstance(first.get("series_dimensions"), dict))
            self.assertGreater(int(first.get("points_count") or 0), 0)
            self.assertIn("dimension_codelists", first)

    def test_parser_source_record_id_is_stable(self) -> None:
        sample_path = EUROSTAT_OFFICIAL_CAPTURE
        payload = sample_path.read_bytes()
        records_1 = parse_eurostat_records(
            payload,
            feed_url=EUROSTAT_OFFICIAL_URL,
            content_type="application/json",
        )
        records_2 = parse_eurostat_records(
            payload,
            feed_url=EUROSTAT_OFFICIAL_URL,
            content_type="application/json",
        )
        ids_1 = sorted(str(row.get("source_record_id") or "") for row in records_1)
        ids_2 = sorted(str(row.get("source_record_id") or "") for row in records_2)
        self.assertEqual(ids_1, ids_2)

    def test_parser_accepts_serialized_records_container(self) -> None:
        sample_path = EUROSTAT_OFFICIAL_CAPTURE
        payload = sample_path.read_bytes()
        baseline = parse_eurostat_records(
            payload,
            feed_url=EUROSTAT_OFFICIAL_URL,
            content_type="application/json",
        )
        wrapped_payload = json.dumps(
            {
                "source": "eurostat_sdmx_network",
                "feed_url": EUROSTAT_OFFICIAL_URL,
                "records": baseline,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        replay_records = parse_eurostat_records(
            wrapped_payload,
            feed_url="file:///tmp/eurostat-replay.json",
            content_type="application/json",
        )
        baseline_ids = sorted(str(row.get("source_record_id") or "") for row in baseline)
        replay_ids = sorted(str(row.get("source_record_id") or "") for row in replay_records)
        self.assertEqual(baseline_ids, replay_ids)

    def test_parser_rejects_metric_value_snapshot_payload(self) -> None:
        snapshot_payload = b"metric,value\\nrun_records_loaded,2\\n"
        with self.assertRaisesRegex(RuntimeError, "metric,value"):
            parse_eurostat_records(
                snapshot_payload,
                feed_url="file:///tmp/eurostat-run-snapshot.csv",
                content_type="text/csv",
            )

    def test_source_records_ingest_is_idempotent(self) -> None:
        connector = EurostatSdmxConnector()
        sample_path = EUROSTAT_OFFICIAL_CAPTURE
        snapshot_date = "2026-08-11"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "eurostat-test.db"
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
                    url_override=EUROSTAT_OFFICIAL_URL,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                count_1 = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM source_records WHERE source_id='eurostat_sdmx'"
                    ).fetchone()["c"]
                )
                self.assertGreater(count_1, 0)

                ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=EUROSTAT_OFFICIAL_URL,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                count_2 = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM source_records WHERE source_id='eurostat_sdmx'"
                    ).fetchone()["c"]
                )
                self.assertEqual(count_1, count_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
