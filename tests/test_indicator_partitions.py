from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.indicator_partition_validation import (
    validate_indicator_partitions,
)
from publicdata_publish.indicator_partitions import export_indicator_partitions

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestIndicatorPartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT NOT NULL
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              source_record_id TEXT NOT NULL
            );
            CREATE TABLE domains (
              domain_id INTEGER PRIMARY KEY,
              canonical_key TEXT NOT NULL
            );
            CREATE TABLE admin_levels (
              admin_level_id INTEGER PRIMARY KEY,
              code TEXT NOT NULL
            );
            CREATE TABLE territories (
              territory_id INTEGER PRIMARY KEY,
              code TEXT NOT NULL,
              name TEXT NOT NULL
            );
            CREATE TABLE indicator_series (
              indicator_series_id INTEGER PRIMARY KEY,
              canonical_key TEXT NOT NULL,
              label TEXT NOT NULL,
              domain_id INTEGER,
              admin_level_id INTEGER,
              territory_id INTEGER,
              source_id TEXT NOT NULL,
              source_url TEXT,
              source_record_pk INTEGER,
              dimensions_json TEXT
            );
            CREATE TABLE indicator_observation_records (
              observation_record_id INTEGER PRIMARY KEY,
              indicator_series_id INTEGER,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER,
              source_record_id TEXT,
              source_snapshot_date TEXT,
              source_url TEXT,
              series_code TEXT NOT NULL,
              point_date TEXT NOT NULL,
              value REAL,
              value_text TEXT,
              unit TEXT,
              frequency TEXT,
              dimensions_json TEXT,
              methodology_version TEXT
            );
            INSERT INTO sources VALUES
              ('bde_series_api', 'https://example.test/bde');
            INSERT INTO source_records VALUES
              (1, 'series-a-v1'),
              (2, 'series-a-v2'),
              (3, 'series-b-v1');
            INSERT INTO domains VALUES (1, 'employment');
            INSERT INTO admin_levels VALUES (1, 'nacional');
            INSERT INTO territories VALUES (1, 'ES', 'Spain');
            INSERT INTO indicator_series VALUES
              (1, 'series-a', 'Series A', 1, 1, 1,
               'bde_series_api', 'https://example.test/series/a', 2, '{"geo":"ES"}'),
              (2, 'series-b', 'Series B', NULL, NULL, NULL,
               'bde_series_api', NULL, 3, '{}');
            INSERT INTO indicator_observation_records VALUES
              (1, 1, 'bde_series_api', 1, 'series-a-v1', '2025-01-01',
               'https://example.test/obs/1', 'A', '2024-01-01', 10.0, NULL,
               'index', 'annual', '{"geo":"ES"}', 'v1'),
              (2, 1, 'bde_series_api', 2, 'series-a-v2', '2026-01-01',
               'https://example.test/obs/2', 'A', '2024-01-01', 11.0, NULL,
               'index', 'annual', '{"geo":"ES"}', 'v2'),
              (3, 1, 'bde_series_api', 2, 'series-a-v2', '2026-01-01',
               NULL, 'A', '2025-01-01', NULL, 'not available',
               'index', 'annual', '{"geo":"ES"}', 'v2'),
              (4, 2, 'bde_series_api', 3, 'series-b-v1', '2026-01-01',
               'file:///private/result', 'B', '2025-02-01', NULL, NULL,
               NULL, NULL, '{}', NULL);
            """
        )
        conn.commit()
        conn.close()

    def test_full_validation_revisions_and_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "indicators.db"
            self._database(db_path)
            first_root = root / "first"
            first = export_indicator_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-08-11",
                row_group_rows=2,
                max_file_rows=2,
                min_rows=4,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 4)
            self.assertEqual(first["totals"]["revision_groups"], 3)
            self.assertEqual(first["totals"]["revised_groups"], 1)
            self.assertEqual(first["totals"]["latest_revision_rows"], 1)
            self.assertEqual(first["totals"]["superseded_revision_rows"], 1)
            self.assertEqual(first["totals"]["text_rows"], 1)
            self.assertEqual(first["totals"]["missing_rows"], 1)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])
            validation = validate_indicator_partitions(
                root=first_root,
                min_rows=4,
            )
            self.assertEqual(validation["status"], "ok")
            self.assertEqual(validation["totals"]["revision_groups"], 3)

            second_root = root / "second"
            second = export_indicator_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-08-12",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                min_rows=4,
                enforce=True,
            )
            self.assertEqual(
                second["incremental_contract"]["partitions_reused"],
                first["totals"]["partitions"],
            )
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE indicator_observation_records SET value = 12.0 "
                "WHERE observation_record_id = 2"
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_indicator_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-08-13",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=second_root / "manifest.json",
                previous_root=second_root,
                min_rows=4,
                enforce=True,
            )
            self.assertEqual(third["incremental_contract"]["partitions_rebuilt"], 1)
            self.assertEqual(
                validate_indicator_partitions(root=third_root, min_rows=4)["status"],
                "ok",
            )

    def test_unlinked_observation_fails_closed_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "indicators.db"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE indicator_observation_records "
                "SET indicator_series_id = NULL WHERE observation_record_id = 4"
            )
            conn.commit()
            conn.close()
            output_root = root / "failed"
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_indicator_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-08-11",
                    min_rows=4,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())

    def test_zero_revisions_and_non_monotonic_ids_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "indicators.db"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM indicator_observation_records WHERE observation_record_id = 1")
            conn.execute(
                "UPDATE indicator_observation_records SET observation_record_id = 200 "
                "WHERE observation_record_id = 2"
            )
            conn.execute(
                "UPDATE indicator_observation_records SET observation_record_id = 10 "
                "WHERE observation_record_id = 3"
            )
            conn.execute(
                "UPDATE indicator_observation_records SET observation_record_id = 100 "
                "WHERE observation_record_id = 4"
            )
            conn.commit()
            conn.close()

            output_root = root / "no-revisions"
            manifest = export_indicator_partitions(
                db_path=db_path,
                output_root=output_root,
                snapshot_date="2026-08-11",
                row_group_rows=2,
                max_file_rows=3,
                min_rows=3,
                enforce=True,
            )
            self.assertEqual(manifest["totals"]["revised_groups"], 0)
            validation = validate_indicator_partitions(
                root=output_root,
                min_rows=3,
            )
            self.assertEqual(validation["status"], "ok")
            self.assertTrue(validation["checks"]["file_minmax"])
            self.assertTrue(validation["checks"]["revision_groups"])


if __name__ == "__main__":
    unittest.main()
