from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.db import ensure_schema_compat


class TestIndicatorSchemaCompat(unittest.TestCase):
    def test_legacy_source_constraint_is_rebuilt_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(
                """
                CREATE TABLE sources (source_id TEXT PRIMARY KEY);
                CREATE TABLE source_records (source_record_pk INTEGER PRIMARY KEY);
                CREATE TABLE indicator_series (indicator_series_id INTEGER PRIMARY KEY);
                INSERT INTO sources VALUES ('bde_series_api'), ('ree_esios_indicators');
                CREATE TABLE indicator_observation_records (
                  observation_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source_id TEXT NOT NULL REFERENCES sources(source_id)
                    CHECK (
                      source_id LIKE 'eurostat_%'
                      OR source_id LIKE 'bde_%'
                      OR source_id LIKE 'aemet_%'
                    ),
                  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
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
                  methodology_version TEXT,
                  raw_payload TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE (source_id, series_code, point_date, source_record_id)
                );
                INSERT INTO indicator_observation_records (
                  source_id, source_record_id, source_snapshot_date,
                  source_url, series_code, point_date, value, dimensions_json,
                  raw_payload, created_at, updated_at
                ) VALUES (
                  'bde_series_api', 'legacy-bde', '2026-08-11',
                  'https://example.test/bde', 'BDE-1', '2026-01-01', 1.0,
                  '{}', '{}', '2026-08-11T00:00:00Z', '2026-08-11T00:00:00Z'
                );
                """
            )
            ensure_schema_compat(conn)
            series_columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(indicator_series)")
            }
            self.assertIn("dimensions_json", series_columns)
            columns = {
                str(row["name"])
                for row in conn.execute(
                    "PRAGMA table_info(indicator_observation_records)"
                )
            }
            self.assertIn("indicator_series_id", columns)
            legacy = conn.execute(
                "SELECT source_id, indicator_series_id "
                "FROM indicator_observation_records"
            ).fetchone()
            self.assertEqual(str(legacy["source_id"]), "bde_series_api")
            self.assertIsNone(legacy["indicator_series_id"])
            conn.execute(
                """
                INSERT INTO indicator_observation_records (
                  source_id, source_record_id, source_snapshot_date,
                  source_url, series_code, point_date, value, dimensions_json,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ree_esios_indicators",
                    "ree-1",
                    "2026-08-11",
                    "https://example.test/ree",
                    "REE-1",
                    "2026-01-01",
                    2.0,
                    "{}",
                    "{}",
                    "2026-08-11T00:00:00Z",
                    "2026-08-11T00:00:00Z",
                ),
            )
            conn.commit()
            self.assertEqual(
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM indicator_observation_records"
                    ).fetchone()[0]
                ),
                2,
            )
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            conn.close()


if __name__ == "__main__":
    unittest.main()
