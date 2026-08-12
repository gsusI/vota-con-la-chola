from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_data_integrity import audit_database, audit_zero_byte_artifacts


NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def create_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE parents (id INTEGER PRIMARY KEY);
            CREATE TABLE children (
              id INTEGER PRIMARY KEY,
              parent_id INTEGER REFERENCES parents(id)
            );
            CREATE TABLE ingestion_runs (
              run_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              started_at TEXT NOT NULL,
              status TEXT NOT NULL,
              records_seen INTEGER NOT NULL DEFAULT 0,
              records_loaded INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        connection.commit()


class DataIntegrityAuditTests(unittest.TestCase):
    def test_clean_database_passes_all_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clean.db"
            create_database(path)

            result = audit_database(path, stale_after_hours=24, now=NOW)

            self.assertEqual(result["issues"], [])
            self.assertTrue(all(result["checks"].values()))

    def test_physical_corruption_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.db"
            path.write_bytes(b"not a sqlite database")

            result = audit_database(path, stale_after_hours=24, now=NOW)

            self.assertIn("sqlite_unreadable", result["issues"])
            self.assertFalse(result["checks"]["sqlite_quick_check"])

    def test_foreign_key_and_recovery_residue_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "residue.db"
            create_database(path)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("INSERT INTO children (id, parent_id) VALUES (1, 99)")
                connection.execute("CREATE TABLE lost_and_found (rootpgno INTEGER)")
                connection.execute("INSERT INTO lost_and_found VALUES (1)")
                connection.commit()

            result = audit_database(path, stale_after_hours=24, now=NOW)

            self.assertEqual(result["foreign_key_violations"], 1)
            self.assertEqual(result["lost_and_found_rows"], 1)
            self.assertIn("foreign_key_violations", result["issues"])
            self.assertIn("sqlite_recovery_residue", result["issues"])

    def test_stale_running_ingestion_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stale.db"
            create_database(path)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    """
                    INSERT INTO ingestion_runs
                      (run_id, source_id, started_at, status)
                    VALUES (1, 'example', '2026-08-10T12:00:00Z', 'running')
                    """
                )
                connection.commit()

            result = audit_database(path, stale_after_hours=24, now=NOW)

            self.assertIn("stale_ingestion_runs", result["issues"])
            self.assertEqual(result["stale_ingestion_runs"][0]["run_id"], 1)

    def test_zero_byte_artifacts_ignore_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.txt").touch()
            quarantined = root / "quarantine" / "2026-08-12"
            quarantined.mkdir(parents=True)
            (quarantined / "preserved.txt").touch()

            result = audit_zero_byte_artifacts(root)

            self.assertEqual(result["zero_byte_files"], [(root / "bad.txt").as_posix()])
            self.assertEqual(result["issues"], ["zero_byte_artifacts"])


if __name__ == "__main__":
    unittest.main()
