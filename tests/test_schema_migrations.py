from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db


class TestSchemaMigrations(unittest.TestCase):
    def test_text_documents_allows_duplicate_urls_after_apply_schema(self) -> None:
        # Older DBs briefly had UNIQUE(source_id, source_url) on text_documents, which is invalid:
        # multiple records can legitimately reuse the same URL (e.g. Congreso interventions).
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "migrations.db"
            conn = open_db(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE text_documents (
                      text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      source_id TEXT NOT NULL REFERENCES sources(source_id),
                      source_url TEXT NOT NULL,
                      source_record_pk INTEGER UNIQUE REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
                      fetched_at TEXT,
                      content_type TEXT,
                      content_sha256 TEXT,
                      bytes INTEGER,
                      raw_path TEXT,
                      text_excerpt TEXT,
                      text_chars INTEGER,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL,
                      UNIQUE (source_id, source_url)
                    )
                    """
                )
                conn.commit()

                apply_schema(conn, DEFAULT_SCHEMA)

                sql = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='text_documents'"
                ).fetchone()[0]
                self.assertNotIn("UNIQUE (source_id, source_url)", str(sql))

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

