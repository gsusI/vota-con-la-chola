from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_initdoc_extraction_review_queue import fetch_review_rows


class TestExportInitdocExtractionReviewQueue(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiative_doc_extractions (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT,
              sample_initiative_id TEXT,
              doc_format TEXT,
              doc_kinds_csv TEXT,
              initiatives_count INTEGER,
              doc_refs_count INTEGER,
              extractor_version TEXT,
              analysis_payload_json TEXT,
              confidence REAL,
              needs_review INTEGER,
              extracted_subject TEXT,
              extracted_title TEXT,
              extracted_excerpt TEXT
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT,
              title TEXT
            );
            CREATE TABLE text_documents (
              source_record_pk INTEGER,
              source_id TEXT,
              source_url TEXT,
              raw_path TEXT
            );
            """
        )
        return conn

    def test_fetch_review_rows_filters_only_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "review_queue.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id, title) VALUES ('i1', 'senado_iniciativas', 'Titulo i1')"
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, doc_format,
                      doc_kinds_csv, initiatives_count, doc_refs_count, extractor_version,
                      analysis_payload_json, confidence, needs_review, extracted_subject, extracted_title, extracted_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (1, "parl_initiative_docs", "i1", "pdf", "bocg", 1, 1, "v1", '{"subject_method":"title_hint"}', 0.65, 1, "s1", "t1", "e1"),
                        (2, "parl_initiative_docs", "i1", "xml", "ds", 1, 1, "v1", '{"subject_method":"keyword_window"}', 0.80, 0, "s2", "t2", "e2"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO text_documents(source_record_pk, source_id, source_url, raw_path) VALUES (?, ?, ?, ?)",
                    [
                        (1, "parl_initiative_docs", "https://example.org/1", "/tmp/1"),
                        (2, "parl_initiative_docs", "https://example.org/2", "/tmp/2"),
                    ],
                )
                conn.commit()

                rows = fetch_review_rows(
                    conn,
                    source_id="parl_initiative_docs",
                    only_needs_review=True,
                    limit=0,
                    offset=0,
                )

                self.assertEqual(len(rows), 1)
                self.assertEqual(int(rows[0]["source_record_pk"]), 1)
                self.assertEqual(int(rows[0]["needs_review"]), 1)
                self.assertEqual(str(rows[0]["subject_method"]), "title_hint")
            finally:
                conn.close()

    def test_fetch_review_rows_offset_batches_stably(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "review_queue_offset.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id, title) VALUES ('i1', 'senado_iniciativas', 'Titulo i1')"
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, doc_format,
                      doc_kinds_csv, initiatives_count, doc_refs_count, extractor_version,
                      analysis_payload_json, confidence, needs_review, extracted_subject, extracted_title, extracted_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (1, "parl_initiative_docs", "i1", "pdf", "bocg", 1, 1, "v2", '{"subject_method":"title_hint"}', 0.20, 1, "s1", "t1", "e1"),
                        (2, "parl_initiative_docs", "i1", "xml", "ds", 1, 1, "v2", '{"subject_method":"keyword_window"}', 0.40, 1, "s2", "t2", "e2"),
                        (3, "parl_initiative_docs", "i1", "html", "bocg", 1, 1, "v2", '{"subject_method":"keyword_window"}', 0.60, 1, "s3", "t3", "e3"),
                    ],
                )
                conn.commit()

                rows = fetch_review_rows(
                    conn,
                    source_id="parl_initiative_docs",
                    only_needs_review=True,
                    limit=1,
                    offset=1,
                )

                self.assertEqual(len(rows), 1)
                self.assertEqual(int(rows[0]["source_record_pk"]), 2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
