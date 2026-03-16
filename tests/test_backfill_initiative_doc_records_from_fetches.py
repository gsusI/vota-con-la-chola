from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_initiative_doc_records_from_fetches import backfill


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE source_records (
          source_record_pk INTEGER PRIMARY KEY AUTOINCREMENT,
          source_id TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          source_snapshot_date TEXT,
          raw_payload TEXT,
          content_sha256 TEXT,
          created_at TEXT,
          updated_at TEXT,
          UNIQUE(source_id, source_record_id)
        );

        CREATE TABLE text_documents (
          text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_id TEXT NOT NULL,
          source_url TEXT,
          source_record_pk INTEGER NOT NULL UNIQUE,
          fetched_at TEXT,
          content_type TEXT,
          content_sha256 TEXT,
          bytes INTEGER,
          raw_path TEXT,
          text_excerpt TEXT,
          text_chars INTEGER,
          created_at TEXT,
          updated_at TEXT
        );

        CREATE TABLE parl_initiatives (
          initiative_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL
        );

        CREATE TABLE parl_initiative_documents (
          initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
          initiative_id TEXT NOT NULL,
          doc_kind TEXT NOT NULL,
          doc_url TEXT NOT NULL,
          source_record_pk INTEGER,
          created_at TEXT,
          updated_at TEXT
        );

        CREATE TABLE document_fetches (
          doc_url TEXT NOT NULL,
          source_id TEXT NOT NULL,
          first_attempt_at TEXT,
          last_attempt_at TEXT,
          attempts INTEGER,
          fetched_ok INTEGER,
          last_http_status INTEGER,
          last_error TEXT,
          content_type TEXT,
          content_sha256 TEXT,
          bytes INTEGER,
          raw_path TEXT,
          PRIMARY KEY (doc_url)
        );
        """
    )
    conn.commit()


class TestBackfillInitiativeDocRecordsFromFetches(unittest.TestCase):
    def test_rehydrates_source_record_text_document_and_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "rehydrate.db"
            raw_path = td_path / "sample.html"
            raw_path.write_text("<html><body><h1>Titulo</h1><p>Texto de prueba</p></body></html>", encoding="utf-8")

            conn = _open_db(db_path)
            try:
                _init_schema(conn)
                now = "2026-02-27T08:00:00+00:00"
                url = "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=15&id1=600&id2=000001"

                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    ("senado:leg15:exp:600/000001", "senado_iniciativas"),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, ?)
                    """,
                    ("senado:leg15:exp:600/000001", "ds", url, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO document_fetches(
                      doc_url, source_id, first_attempt_at, last_attempt_at,
                      attempts, fetched_ok, last_http_status, last_error,
                      content_type, content_sha256, bytes, raw_path
                    ) VALUES (?, 'parl_initiative_docs', ?, ?, 1, 1, 200, NULL, 'text/html', '', ?, ?)
                    """,
                    (url, now, now, raw_path.stat().st_size, str(raw_path)),
                )
                conn.commit()

                report = backfill(
                    conn,
                    source_id="parl_initiative_docs",
                    initiative_source_id="senado_iniciativas",
                    snapshot_date="2026-02-27",
                    limit=0,
                    dry_run=False,
                )

                self.assertEqual(int(report["candidate_urls_total"]), 1)
                self.assertEqual(int(report["usable_candidates_total"]), 1)
                self.assertEqual(int(report["source_records_created"]), 1)
                self.assertEqual(int(report["text_documents_upserted"]), 1)
                self.assertEqual(int(report["mapping_rows_updated"]), 1)
                self.assertEqual(int(report["coverage_after"]["missing_doc_links"]), 0)

                mapped_pk = conn.execute(
                    "SELECT source_record_pk FROM parl_initiative_documents WHERE doc_url = ?",
                    (url,),
                ).fetchone()["source_record_pk"]
                self.assertTrue(int(mapped_pk) > 0)

                td_row = conn.execute(
                    "SELECT source_url, text_excerpt FROM text_documents WHERE source_record_pk = ?",
                    (mapped_pk,),
                ).fetchone()
                self.assertEqual(str(td_row["source_url"]), url)
                self.assertIn("Texto de prueba", str(td_row["text_excerpt"] or ""))

                report_second = backfill(
                    conn,
                    source_id="parl_initiative_docs",
                    initiative_source_id="senado_iniciativas",
                    snapshot_date="2026-02-27",
                    limit=0,
                    dry_run=False,
                )
                self.assertEqual(int(report_second["candidate_urls_total"]), 0)
                self.assertEqual(int(report_second["mapping_rows_updated"]), 0)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
