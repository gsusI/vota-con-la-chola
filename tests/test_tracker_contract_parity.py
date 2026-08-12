from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.registry import get_connectors
from etl.politicos_es.run_snapshot_schema import (
    NORMALIZED_RUN_SNAPSHOT_FIELDS,
    RUN_SNAPSHOT_SCHEMA_VERSION,
    normalize_run_snapshot_row,
)


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
PLACSP_OFFICIAL_ARCHIVE = Path(
    "etl/data/object-origin/placsp-contracts/bd/a7/"
    "bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f.zip"
)
PLACSP_OFFICIAL_MEMBER = "licitacionesPerfilesContratanteCompleto3.atom"
PLACSP_OFFICIAL_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3_2025.zip"
)
BDNS_OFFICIAL_CAPTURE = Path(
    "etl/data/raw/official-captures/bdns/concesiones-page-0-20260812.json"
)
BDNS_OFFICIAL_URL = (
    "https://www.infosubvenciones.es/bdnstrans/api/concesiones/busqueda"
    "?page=0&size=10&sort=fechaAlta,desc"
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

    def test_official_outcome_captures_emit_tracker_compatible_payloads(self) -> None:
        connectors = get_connectors()
        captures = (
            ("eurostat_sdmx", EUROSTAT_OFFICIAL_CAPTURE, EUROSTAT_OFFICIAL_URL),
            ("bde_series_api", BDE_OFFICIAL_CAPTURE, None),
        )

        with tempfile.TemporaryDirectory() as td:
            raw_dir = Path(td)
            for source_id, capture_path, source_url in captures:
                with self.subTest(source_id=source_id):
                    self.assertTrue(
                        capture_path.exists(),
                        f"Missing official capture: {capture_path}",
                    )

                    extracted = connectors[source_id].extract(
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=capture_path,
                        url_override=source_url,
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
    def test_official_money_captures_follow_tracker_artifact_contract(self) -> None:
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_dir = td_path / "raw"
            placsp_path = td_path / PLACSP_OFFICIAL_MEMBER
            with zipfile.ZipFile(PLACSP_OFFICIAL_ARCHIVE) as archive:
                placsp_path.write_bytes(archive.read(PLACSP_OFFICIAL_MEMBER))
            captures = (
                ("placsp_sindicacion", placsp_path, PLACSP_OFFICIAL_URL),
                ("bdns_api_subvenciones", BDNS_OFFICIAL_CAPTURE, BDNS_OFFICIAL_URL),
            )
            for source_id, capture_path, source_url in captures:
                with self.subTest(source_id=source_id):
                    self.assertTrue(
                        capture_path.exists(),
                        f"Missing official capture: {capture_path}",
                    )

                    extracted = connectors[source_id].extract(
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=capture_path,
                        url_override=source_url,
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
