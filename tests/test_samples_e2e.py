from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors


class TestSamplesE2E(unittest.TestCase):
    def test_samples_ingest_is_idempotent(self) -> None:
        connectors = get_connectors()
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
                self.assertTrue(source_records_counts_1, "Expected source_records after ingesting samples")
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

    def test_eurostat_replay_container_fixture_is_ingestable(self) -> None:
        connectors = get_connectors()
        connector = connectors["eurostat_sdmx"]
        sample_path = Path(SOURCE_CONFIG["eurostat_sdmx"]["fallback_file"])
        snapshot_date = "2026-02-12"
        self.assertTrue(sample_path.exists(), f"Missing sample for eurostat_sdmx: {sample_path}")

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
                url_override=None,
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
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )
                self.assertGreater(seen, 0)
                self.assertGreater(loaded, 0)
                self.assertEqual(note, "from-file")
            finally:
                conn.close()

    def test_bde_replay_container_fixture_is_ingestable_for_stable_series(self) -> None:
        connectors = get_connectors()
        connector = connectors["bde_series_api"]
        sample_path = Path(SOURCE_CONFIG["bde_series_api"]["fallback_file"])
        snapshot_date = "2026-02-12"
        self.assertTrue(sample_path.exists(), f"Missing sample for bde_series_api: {sample_path}")

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
            records = [record for record in payload.get("records", []) if record.get("series_code") == "PARO.TASA.ES.M"]
            self.assertEqual(len(records), 1, "Expected exactly one stable PARO.TASA.ES.M record in sample")
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
                self.assertEqual(str(row["source_record_id"]), "series:parotasaesm")
            finally:
                conn.close()

    def test_aemet_replay_container_fixture_is_ingestable_for_stable_series(self) -> None:
        connectors = get_connectors()
        connector = connectors["aemet_opendata_series"]
        sample_path = Path(SOURCE_CONFIG["aemet_opendata_series"]["fallback_file"])
        snapshot_date = "2026-02-12"
        self.assertTrue(sample_path.exists(), f"Missing sample for aemet_opendata_series: {sample_path}")

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
            records = [
                record
                for record in payload.get("records", [])
                if record.get("station_id") == "3195" and record.get("variable") == "tmed"
            ]
            self.assertEqual(len(records), 1, "Expected exactly one stable station:3195:var:tmed record in sample")
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
                self.assertEqual(str(row["source_record_id"]), "station:3195:var:tmed")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
