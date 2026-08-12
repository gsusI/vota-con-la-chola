from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors


EUROSTAT_OFFICIAL_CAPTURE = Path(
    "etl/data/object-origin/eurostat-indicators/fc/a5/"
    "fca5f0c54754173cab1048a6ca52e2e9f7094ca8fa1220f2c29babd9a3911018.json"
)
EUROSTAT_OFFICIAL_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "ilc_peps11n?lang=EN&sinceTimePeriod=2015"
)
BDE_OFFICIAL_CAPTURE = Path(
    "etl/data/raw/bde_series_api/2026/05/11/bde_series_api_20260511T175659Z.json"
)


class TestSamplesE2E(unittest.TestCase):
    def test_configured_official_captures_ingest_idempotently(self) -> None:
        connectors = get_connectors()
        connectors = {
            source_id: connector
            for source_id, connector in connectors.items()
            if str(SOURCE_CONFIG[source_id].get("fallback_file") or "").strip()
        }
        self.assertTrue(connectors)
        ingest_modes = {source_id: getattr(connector, "ingest_mode", "mandates") for source_id, connector in connectors.items()}
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                for source_id, connector in connectors.items():
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
                    self.assertTrue(
                        sample_path.exists(),
                        f"Missing configured capture for {source_id}: {sample_path}",
                    )
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

                mandates_counts_1 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM mandates GROUP BY source_id"
                    ).fetchall()
                }
                source_records_counts_1 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM source_records GROUP BY source_id"
                    ).fetchall()
                }
                self.assertTrue(
                    source_records_counts_1,
                    "Expected source_records after ingesting configured captures",
                )
                for source_id in connectors:
                    mode = ingest_modes[source_id]
                    if mode == "source_records_only":
                        self.assertGreater(
                            source_records_counts_1.get(source_id, 0),
                            0,
                            f"Expected source_records for {source_id}",
                        )
                    else:
                        self.assertGreater(
                            mandates_counts_1.get(source_id, 0),
                            0,
                            f"Expected mandates for {source_id}",
                        )

                # Run again: mandates are keyed by (source_id, source_record_id) so totals must stay stable.
                for source_id, connector in connectors.items():
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
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

                mandates_counts_2 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM mandates GROUP BY source_id"
                    ).fetchall()
                }
                source_records_counts_2 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        "SELECT source_id, COUNT(*) AS c FROM source_records GROUP BY source_id"
                    ).fetchall()
                }
                self.assertEqual(mandates_counts_1, mandates_counts_2)
                self.assertEqual(source_records_counts_1, source_records_counts_2)
            finally:
                conn.close()

    def test_eurostat_replay_container_from_official_capture_is_ingestable(self) -> None:
        connectors = get_connectors()
        connector = connectors["eurostat_sdmx"]
        sample_path = EUROSTAT_OFFICIAL_CAPTURE
        snapshot_date = "2026-08-12"
        self.assertTrue(sample_path.exists(), f"Missing official Eurostat capture: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            replay_path = Path(td) / "eurostat_replay_container.json"

            # Build a replay fixture with the same serialized `records` envelope
            # produced by strict/from-file extract paths.
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=EUROSTAT_OFFICIAL_URL,
                strict_network=True,
            )
            replay_path.write_bytes(extracted.payload)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                seen, loaded, note = ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=replay_path,
                    url_override=EUROSTAT_OFFICIAL_URL,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                self.assertGreater(seen, 0)
                self.assertGreater(loaded, 0)
                self.assertEqual(note, "from-file")
            finally:
                conn.close()

    def test_bde_replay_container_from_official_capture_is_ingestable(self) -> None:
        connectors = get_connectors()
        connector = connectors["bde_series_api"]
        sample_path = BDE_OFFICIAL_CAPTURE
        snapshot_date = "2026-05-11"
        self.assertTrue(sample_path.exists(), f"Missing official BDE capture: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            replay_path = Path(td) / "bde_replay_container.json"

            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=None,
                strict_network=True,
            )
            payload = json.loads(extracted.payload.decode("utf-8"))
            records = [
                record
                for record in payload.get("records", [])
                if record.get("series_code") == "D_1NBAF472"
            ]
            self.assertEqual(
                len(records),
                1,
                "Expected captured BDE Euribor series D_1NBAF472",
            )
            payload["records"] = records
            replay_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                seen, loaded, note = ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=replay_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                self.assertEqual(seen, 1)
                self.assertEqual(loaded, 1)
                self.assertEqual(note, "from-file")

                row = conn.execute(
                    """
                    SELECT source_record_id
                    FROM source_records
                    WHERE source_id='bde_series_api'
                    ORDER BY source_record_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(str(row["source_record_id"]), "series:d_1nbaf472")
            finally:
                conn.close()

    @unittest.skipUnless(
        os.environ.get("AEMET_REAL_CAPTURE"),
        "AEMET_REAL_CAPTURE not provided; synthetic capture forbidden",
    )
    def test_aemet_replay_container_from_official_capture_is_ingestable(self) -> None:
        connectors = get_connectors()
        connector = connectors["aemet_opendata_series"]
        sample_path = Path(str(os.environ["AEMET_REAL_CAPTURE"]))
        snapshot_date = "2026-08-12"
        self.assertTrue(sample_path.exists(), f"Missing official AEMET capture: {sample_path}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            replay_path = Path(td) / "aemet_replay_container.json"

            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=sample_path,
                url_override=None,
                strict_network=True,
            )
            payload = json.loads(extracted.payload.decode("utf-8"))
            records = list(payload.get("records", []))[:1]
            self.assertEqual(len(records), 1, "Expected at least one official AEMET station series")
            expected_source_record_id = str(records[0].get("source_record_id") or "")
            self.assertTrue(expected_source_record_id)
            payload["records"] = records
            replay_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                seen, loaded, note = ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=replay_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                self.assertEqual(seen, 1)
                self.assertEqual(loaded, 1)
                self.assertEqual(note, "from-file")

                row = conn.execute(
                    """
                    SELECT source_record_id
                    FROM source_records
                    WHERE source_id='aemet_opendata_series'
                    ORDER BY source_record_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(str(row["source_record_id"]), expected_source_record_id)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
