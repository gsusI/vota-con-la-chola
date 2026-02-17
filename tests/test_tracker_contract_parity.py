from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import SOURCE_CONFIG
from etl.politicos_es.registry import get_connectors
from etl.politicos_es.run_snapshot_schema import (
    NORMALIZED_RUN_SNAPSHOT_FIELDS,
    RUN_SNAPSHOT_SCHEMA_VERSION,
    normalize_run_snapshot_row,
)


class TestTrackerContractParity(unittest.TestCase):
    def test_replay_snapshot_normalization_uses_canonical_fields(self) -> None:
        normalized = normalize_run_snapshot_row(
            {
                "mode": "replay",
                "command": (
                    "python3 scripts/ingestar_politicos_es.py ingest "
                    "--source eurostat_sdmx --from-file /tmp/eurostat_replay.json"
                ),
                "exit_code": "0",
                "run_records_seen": "2",
                "run_records_loaded": "2",
                "snapshot": "20260217",
                "source_url": "file:///tmp/eurostat_replay.json",
                "series_id": "une_rt_a|freq=A|geo=ES|unit=PC_ACT",
            }
        )

        self.assertEqual(list(normalized.keys()), list(NORMALIZED_RUN_SNAPSHOT_FIELDS))
        self.assertEqual(normalized["schema_version"], RUN_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(normalized["source_id"], "eurostat_sdmx")
        self.assertEqual(normalized["mode"], "replay")
        self.assertEqual(normalized["snapshot_date"], "2026-02-17")
        self.assertEqual(normalized["entity_id"], "une_rt_a|freq=A|geo=ES|unit=PC_ACT")
        self.assertEqual(normalized["run_records_seen"], "2")
        self.assertEqual(normalized["run_records_loaded"], "2")

    def test_outcomes_fallback_samples_emit_parseable_from_file_payloads(self) -> None:
        connectors = get_connectors()
        source_ids = ("eurostat_sdmx", "bde_series_api", "aemet_opendata_series")

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td)
            for source_id in source_ids:
                with self.subTest(source_id=source_id):
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing fallback sample: {sample_path}")

                    extracted = connectors[source_id].extract(
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        strict_network=True,
                    )
                    self.assertEqual(extracted.note, "from-file")

                    payload = json.loads(extracted.payload.decode("utf-8"))
                    self.assertEqual(payload.get("source"), f"{source_id}_file")
                    records = payload.get("records")
                    self.assertIsInstance(records, list)
                    self.assertGreater(len(records), 0)

                    first = records[0]
                    self.assertTrue(str(first.get("source_record_id") or "").strip())
                    self.assertIn("points", first)
                    self.assertIsInstance(first.get("points"), list)
                    self.assertGreater(len(first.get("points", [])), 0)

                    if source_id == "eurostat_sdmx":
                        self.assertEqual(first.get("record_kind"), "eurostat_series")
                        self.assertTrue(str(first.get("series_code") or "").strip())
                    elif source_id == "bde_series_api":
                        self.assertEqual(first.get("record_kind"), "bde_series")
                        self.assertTrue(str(first.get("series_code") or "").strip())
                    else:
                        self.assertEqual(first.get("record_kind"), "aemet_station_series")
                        self.assertTrue(str(first.get("station_id") or "").strip())
                        self.assertTrue(str(first.get("variable") or "").strip())

    def test_placsp_bdns_samples_follow_tracker_artifact_contract(self) -> None:
        connectors = get_connectors()
        source_ids = (
            "placsp_sindicacion",
            "placsp_autonomico",
            "bdns_api_subvenciones",
            "bdns_autonomico",
        )

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td)
            for source_id in source_ids:
                with self.subTest(source_id=source_id):
                    sample_path = Path(SOURCE_CONFIG[source_id]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing fallback sample: {sample_path}")

                    extracted = connectors[source_id].extract(
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        strict_network=True,
                    )
                    self.assertEqual(extracted.note, "from-file")

                    payload = json.loads(extracted.payload.decode("utf-8"))
                    self.assertEqual(payload.get("source"), f"{source_id}_file")
                    records = payload.get("records")
                    self.assertIsInstance(records, list)
                    self.assertGreater(len(records), 0)

                    first = records[0]
                    self.assertTrue(str(first.get("source_record_id") or "").strip())
                    self.assertTrue(str(first.get("record_kind") or "").strip())
                    self.assertTrue(str(first.get("source_feed") or "").strip())
                    self.assertTrue(str(first.get("feed_url") or "").strip())

                    if source_id.startswith("placsp_"):
                        self.assertEqual(first.get("record_kind"), "placsp_atom_entry")
                        self.assertIn("title", first)
                        self.assertIn("source_url", first)
                        self.assertIn("expediente", first)
                    else:
                        self.assertEqual(first.get("record_kind"), "bdns_subsidy_record")
                        self.assertIn("convocatoria_id", first)
                        self.assertIn("importe_eur", first)
                        self.assertIn("raw_row", first)


if __name__ == "__main__":
    unittest.main()
