from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publicdata_core.util import sha256_bytes
from publicdata_sqlite import (
    ensure_column,
    open_db,
    seed_sources_from_config,
    table_columns,
    table_exists,
    upsert_source_record,
    upsert_source_record_for_event,
    upsert_source_records,
    upsert_source_records_with_content_sha256,
)


class TestPublicDataSqlite(unittest.TestCase):
    def test_open_db_enables_fk_and_schema_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            conn = open_db(db_path)
            try:
                conn.execute("CREATE TABLE demo (demo_id INTEGER PRIMARY KEY)")
                self.assertEqual(int(conn.execute("PRAGMA foreign_keys").fetchone()[0]), 1)
                self.assertTrue(table_exists(conn, "demo"))
                ensure_column(conn, "demo", "label", "label TEXT")
                self.assertIn("label", table_columns(conn, "demo"))
            finally:
                conn.close()

    def test_seed_sources_and_source_record_upserts_are_generic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            conn = open_db(Path(td) / "test.db")
            try:
                self._create_provenance_schema(conn)
                seed_sources_from_config(
                    conn,
                    {
                        "source_test": {
                            "name": "Test source",
                            "scope": "test",
                            "default_url": "https://example.test/data.json",
                            "format": "json",
                        }
                    },
                    now_iso="2026-05-09T00:00:00+00:00",
                )

                row = conn.execute("SELECT data_format FROM sources WHERE source_id = 'source_test'").fetchone()
                self.assertEqual(row["data_format"], "json")

                pk1 = upsert_source_record(
                    conn,
                    "source_test",
                    "row-1",
                    "2026-02-12",
                    '{"a":1}',
                    sha256_bytes(b'{"a":1}'),
                    "2026-05-09T00:00:00+00:00",
                )
                pk2 = upsert_source_record_for_event(
                    conn,
                    source_id="source_test",
                    source_record_id="row-1",
                    snapshot_date="2026-02-12",
                    raw_payload='{"a":2}',
                    now_iso="2026-05-09T00:01:00+00:00",
                )
                self.assertEqual(pk1, pk2)

                batch = upsert_source_records(
                    conn,
                    source_id="source_test",
                    rows=[
                        {"source_record_id": "row-2", "raw_payload": '{"b":2}'},
                        {"source_record_id": "row-3", "raw_payload": '{"c":3}'},
                    ],
                    snapshot_date="2026-02-12",
                    now_iso="2026-05-09T00:02:00+00:00",
                )
                self.assertEqual(set(batch), {"row-2", "row-3"})

                batch_with_hash = upsert_source_records_with_content_sha256(
                    conn,
                    source_id="source_test",
                    rows=[
                        {"source_record_id": "row-4", "raw_payload": '{"d":4}', "content_sha256": "custom"},
                    ],
                    snapshot_date="2026-02-12",
                    now_iso="2026-05-09T00:03:00+00:00",
                )
                self.assertEqual(set(batch_with_hash), {"row-4"})
                row4 = conn.execute(
                    "SELECT content_sha256 FROM source_records WHERE source_record_id = 'row-4'"
                ).fetchone()
                self.assertEqual(row4["content_sha256"], "custom")
            finally:
                conn.close()

    @staticmethod
    def _create_provenance_schema(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              scope TEXT NOT NULL,
              default_url TEXT NOT NULL,
              data_format TEXT NOT NULL,
              is_active INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              source_record_id TEXT NOT NULL,
              source_snapshot_date TEXT,
              raw_payload TEXT NOT NULL,
              content_sha256 TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_id, source_record_id)
            );
            """
        )


if __name__ == "__main__":
    unittest.main()
