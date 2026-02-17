from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from etl.politicos_es import run_snapshot_schema as schema


class TestRunSnapshotSchema(unittest.TestCase):
    def test_normalize_metric_value_snapshot_to_canonical_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "legacy_run_snapshot.csv"
            legacy_path.write_text(
                "\n".join(
                    [
                        "metric,value",
                        "source_id,placsp_autonomico",
                        "mode,strict-network",
                        "command,python3 scripts/ingestar_politicos_es.py ingest --source placsp_autonomico",
                        "exit_code,0",
                        "run_records_seen,106",
                        "run_records_loaded,106",
                        "snapshot,20260217",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            normalized_path = Path(td) / "normalized_run_snapshot.csv"

            out_path, legacy_out, normalized = schema.normalize_run_snapshot_file(
                input_path=legacy_path,
                output_path=normalized_path,
            )

            self.assertEqual(out_path, normalized_path)
            self.assertIsNone(legacy_out)
            self.assertEqual(normalized["schema_version"], schema.RUN_SNAPSHOT_SCHEMA_VERSION)
            self.assertEqual(normalized["source_id"], "placsp_autonomico")
            self.assertEqual(normalized["mode"], "strict-network")
            self.assertEqual(normalized["run_records_loaded"], "106")
            self.assertEqual(normalized["snapshot_date"], "2026-02-17")

            with normalized_path.open("r", encoding="utf-8", newline="") as fh:
                row = next(csv.DictReader(fh))
            self.assertEqual(row["source_id"], "placsp_autonomico")
            self.assertEqual(row["snapshot_date"], "2026-02-17")

    def test_normalize_tabular_snapshot_derives_source_id_from_command(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tabular_path = Path(td) / "tabular_run_snapshot.csv"
            tabular_path.write_text(
                "\n".join(
                    [
                        (
                            "series_id,mode,command,exit_code,run_records_loaded,snapshot"
                        ),
                        (
                            "une_rt_a|freq=A|geo=ES|unit=PC_ACT,replay,"
                            "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db "
                            "--source eurostat_sdmx --from-file /tmp/replay.json,1,0,2026-02-17"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            normalized = schema.normalize_run_snapshot_row(schema.load_run_snapshot_file(tabular_path))
            self.assertEqual(normalized["source_id"], "eurostat_sdmx")
            self.assertEqual(normalized["mode"], "replay")
            self.assertEqual(normalized["snapshot_date"], "2026-02-17")
            self.assertEqual(normalized["entity_id"], "une_rt_a|freq=A|geo=ES|unit=PC_ACT")

    def test_write_legacy_metric_value_from_canonical_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            normalized_row = {
                "source_id": "bdns_api_subvenciones",
                "mode": "from-file",
                "exit_code": "0",
                "run_records_loaded": "3",
                "snapshot_date": "2026-02-17",
            }
            legacy_path = Path(td) / "legacy_metric_value.csv"
            schema.write_legacy_metric_value_snapshot(legacy_path, normalized_row)
            payload = legacy_path.read_text(encoding="utf-8")
            self.assertTrue(payload.startswith("metric,value\n"))
            self.assertIn("source_id,bdns_api_subvenciones\n", payload)
            self.assertIn("run_records_loaded,3\n", payload)
            self.assertIn("snapshot_date,2026-02-17\n", payload)

