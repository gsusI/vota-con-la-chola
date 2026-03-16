import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.sqlite_export_pragmas import tune_sqlite_export_connection


class SqliteExportPragmasTest(unittest.TestCase):
    def test_tune_sqlite_export_connection_applies_readback_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "export.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
                applied = tune_sqlite_export_connection(conn)
                self.assertEqual(applied.get("query_only"), 1)
                self.assertEqual(applied.get("temp_store"), 2)
                self.assertEqual(applied.get("cache_size"), -131072)
            finally:
                conn.close()
