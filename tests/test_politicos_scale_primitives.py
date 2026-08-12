from __future__ import annotations

import sqlite3
import unittest

from etl.politicos_es.db import close_missing_mandates


class TestPoliticosScalePrimitives(unittest.TestCase):
    def test_close_missing_mandates_exceeds_sqlite_variable_limit(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE mandates (
                  mandate_id INTEGER PRIMARY KEY,
                  source_id TEXT NOT NULL,
                  source_record_id TEXT NOT NULL,
                  is_active INTEGER NOT NULL,
                  end_date TEXT,
                  last_seen_at TEXT
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO mandates (
                  source_id, source_record_id, is_active, end_date, last_seen_at
                ) VALUES ('source-a', ?, 1, NULL, 'old')
                """,
                ((f"record-{index}",) for index in range(40_001)),
            )
            seen_ids = [f"record-{index}" for index in range(40_000)]

            close_missing_mandates(
                conn,
                "source-a",
                seen_ids,
                "2026-08-10",
                "2026-08-10T08:00:00+00:00",
            )

            active = int(conn.execute("SELECT COUNT(*) FROM mandates WHERE is_active = 1").fetchone()[0])
            closed = conn.execute(
                "SELECT is_active, end_date FROM mandates WHERE source_record_id = 'record-40000'"
            ).fetchone()
            self.assertEqual(active, 40_000)
            self.assertEqual(int(closed["is_active"]), 0)
            self.assertEqual(closed["end_date"], "2026-08-10")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
