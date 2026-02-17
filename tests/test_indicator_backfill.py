from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources, upsert_source_record
from etl.politicos_es.indicator_backfill import backfill_indicator_harmonization
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors
from etl.politicos_es.util import now_utc_iso, sha256_bytes, stable_json


class TestIndicatorBackfill(unittest.TestCase):
    def test_indicator_backfill_is_idempotent_and_traceable(self) -> None:
        snapshot_date = "2026-02-16"
        samples = (
            ("eurostat_sdmx", Path("etl/data/raw/samples/eurostat_sdmx_sample.json")),
            ("bde_series_api", Path("etl/data/raw/samples/bde_series_api_sample.json")),
            ("aemet_opendata_series", Path("etl/data/raw/samples/aemet_opendata_series_sample.json")),
        )
        for source_id, sample_path in samples:
            self.assertTrue(sample_path.exists(), f"Missing sample for {source_id}: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "indicator-backfill.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                connectors = get_connectors()
                for source_id, sample_path in samples:
                    ingest_one_source(
                        conn=conn,
                        connector=connectors[source_id],
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                result_1 = backfill_indicator_harmonization(conn)
                self.assertGreater(result_1["indicator_series_total"], 0)
                self.assertGreater(result_1["indicator_points_total"], 0)
                self.assertGreater(result_1["indicator_observation_records_total"], 0)
                self.assertEqual(
                    result_1["indicator_series_total"],
                    result_1["indicator_series_with_provenance"],
                )
                self.assertEqual(
                    result_1["indicator_observation_records_total"],
                    result_1["observation_records_with_provenance"],
                )
                self.assertGreater(result_1["indicator_series_by_source"].get("eurostat_sdmx", 0), 0)
                self.assertGreater(result_1["indicator_series_by_source"].get("bde_series_api", 0), 0)
                self.assertGreater(result_1["indicator_series_by_source"].get("aemet_opendata_series", 0), 0)

                traceability_series_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM indicator_series
                    WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series')
                      AND source_record_pk IS NOT NULL
                      AND source_snapshot_date IS NOT NULL
                      AND trim(source_snapshot_date) <> ''
                      AND source_url IS NOT NULL
                      AND trim(source_url) <> ''
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                    """
                ).fetchone()
                total_series_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM indicator_series
                    WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series')
                    """
                ).fetchone()
                self.assertEqual(int(traceability_series_row["c"]), int(total_series_row["c"]))

                traceability_obs_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM indicator_observation_records
                    WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series')
                      AND source_record_pk IS NOT NULL
                      AND source_record_id IS NOT NULL
                      AND trim(source_record_id) <> ''
                      AND source_snapshot_date IS NOT NULL
                      AND trim(source_snapshot_date) <> ''
                      AND source_url IS NOT NULL
                      AND trim(source_url) <> ''
                      AND methodology_version IS NOT NULL
                      AND trim(methodology_version) <> ''
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                    """
                ).fetchone()
                total_obs_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM indicator_observation_records
                    WHERE source_id IN ('eurostat_sdmx','bde_series_api','aemet_opendata_series')
                    """
                ).fetchone()
                self.assertEqual(int(traceability_obs_row["c"]), int(total_obs_row["c"]))

                result_2 = backfill_indicator_harmonization(conn)
                self.assertEqual(result_1["indicator_series_total"], result_2["indicator_series_total"])
                self.assertEqual(result_1["indicator_points_total"], result_2["indicator_points_total"])
                self.assertEqual(
                    result_1["indicator_observation_records_total"],
                    result_2["indicator_observation_records_total"],
                )

                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_rows, [])
            finally:
                conn.close()

    def test_frequency_conflicts_keep_separate_series_variants(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "indicator-backfill-freq.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                now_iso = now_utc_iso()

                payload_monthly = {
                    "record_kind": "bde_series",
                    "source_feed": "bde_series_api",
                    "dataset_code": "bde_series_api",
                    "source_url": "https://api.bde.es/datos/series/demo",
                    "series_code": "DEMO.SERIES",
                    "series_label": "Demo Series",
                    "frequency": "M",
                    "unit": "PERCENT",
                    "series_dimensions": {"source": "bde_api", "series_code": "DEMO.SERIES", "freq": "M"},
                    "points": [{"period": "2026-01", "value": 10.0}],
                }
                payload_annual = {
                    "record_kind": "bde_series",
                    "source_feed": "bde_series_api",
                    "dataset_code": "bde_series_api",
                    "source_url": "https://api.bde.es/datos/series/demo",
                    "series_code": "DEMO.SERIES",
                    "series_label": "Demo Series",
                    "frequency": "A",
                    "unit": "PERCENT",
                    "series_dimensions": {"source": "bde_api", "series_code": "DEMO.SERIES", "freq": "A"},
                    "points": [{"period": "2026", "value": 9.5}],
                }

                raw_monthly = stable_json(payload_monthly)
                raw_annual = stable_json(payload_annual)
                upsert_source_record(
                    conn=conn,
                    source_id="bde_series_api",
                    source_record_id="series:demo:m",
                    snapshot_date="2026-02-16",
                    raw_payload=raw_monthly,
                    content_sha256=sha256_bytes(raw_monthly.encode("utf-8")),
                    now_iso=now_iso,
                )
                upsert_source_record(
                    conn=conn,
                    source_id="bde_series_api",
                    source_record_id="series:demo:a",
                    snapshot_date="2026-02-16",
                    raw_payload=raw_annual,
                    content_sha256=sha256_bytes(raw_annual.encode("utf-8")),
                    now_iso=now_iso,
                )
                conn.commit()

                result = backfill_indicator_harmonization(conn, source_ids=("bde_series_api",))
                self.assertEqual(result["source_records_mapped"], 2)
                self.assertEqual(result["indicator_series_by_source"].get("bde_series_api", 0), 2)

                rows = conn.execute(
                    """
                    SELECT frequency, COUNT(*) AS c
                    FROM indicator_series
                    WHERE source_id='bde_series_api'
                      AND label='Demo Series'
                    GROUP BY frequency
                    ORDER BY frequency
                    """
                ).fetchall()
                self.assertEqual(len(rows), 2)
                frequencies = {str(row["frequency"]): int(row["c"]) for row in rows}
                self.assertIn("A", frequencies)
                self.assertIn("M", frequencies)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

