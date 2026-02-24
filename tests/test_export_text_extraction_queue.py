from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_text_extraction_queue import build_queue_rows


class TestExportTextExtractionQueue(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE text_documents (
              source_id TEXT,
              source_url TEXT,
              source_record_pk INTEGER,
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT
            )
            """
        )
        return conn

    def test_build_queue_rows_dedupes_by_content_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_pdf = td_path / "same.pdf"
            raw_html = td_path / "a.html"
            raw_pdf.write_bytes(b"%PDF-1.4\n%")
            raw_html.write_text("<html><body>hola</body></html>", encoding="utf-8")

            db_path = td_path / "queue.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk, fetched_at,
                      content_type, content_sha256, bytes, raw_path, text_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "parl_initiative_docs",
                            "https://example.org/a.pdf",
                            1,
                            "2026-02-22T15:00:00Z",
                            "application/pdf",
                            "SHA-PDF-A",
                            100,
                            str(raw_pdf),
                            "",
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/a-dup.pdf",
                            2,
                            "2026-02-22T15:00:00Z",
                            "application/pdf",
                            "SHA-PDF-A",
                            98,
                            str(raw_pdf),
                            "",
                        ),
                        (
                            "congreso_intervenciones",
                            "https://example.org/a.html",
                            3,
                            "2026-02-22T15:00:00Z",
                            "text/html",
                            "SHA-HTML-A",
                            50,
                            str(raw_html),
                            "",
                        ),
                        (
                            "congreso_intervenciones",
                            "https://example.org/missing.html",
                            4,
                            "2026-02-22T15:00:00Z",
                            "text/html",
                            "SHA-MISSING",
                            45,
                            str(td_path / "missing.html"),
                            "",
                        ),
                        (
                            "congreso_intervenciones",
                            "https://example.org/already.html",
                            5,
                            "2026-02-22T15:00:00Z",
                            "text/html",
                            "SHA-ALREADY",
                            30,
                            str(raw_html),
                            "ya extraido",
                        ),
                    ],
                )
                conn.commit()

                queue_rows, summary = build_queue_rows(
                    conn,
                    source_ids=set(),
                    allowed_formats={"pdf", "html"},
                    only_missing_excerpt=True,
                    dedupe_by="content_sha256",
                    limit=0,
                )

                self.assertEqual(len(queue_rows), 3)
                by_key = {str(r["queue_key"]): r for r in queue_rows}

                pdf_key = "sha256:sha-pdf-a"
                self.assertIn(pdf_key, by_key)
                self.assertEqual(int(by_key[pdf_key]["refs_total"]), 2)
                self.assertEqual(int(by_key[pdf_key]["refs_missing_excerpt"]), 2)
                self.assertEqual(int(by_key[pdf_key]["has_raw_file"]), 1)

                self.assertEqual(int(summary["rows_scanned"]), 5)
                self.assertEqual(int(summary["queue_items_total"]), 3)
                self.assertEqual(int(summary["queue_items_pending"]), 2)
                self.assertEqual(int(summary["refs_missing_excerpt_all"]), 4)
                self.assertEqual(int(summary["refs_missing_raw_file_all"]), 1)
                self.assertEqual(int(summary["skipped_has_excerpt"]), 1)
            finally:
                conn.close()

    def test_build_queue_rows_falls_back_to_raw_path_when_sha_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_xml = td_path / "same.xml"
            raw_xml.write_text("<root>ok</root>", encoding="utf-8")

            db_path = td_path / "queue2.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk, fetched_at,
                      content_type, content_sha256, bytes, raw_path, text_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "parl_initiative_docs",
                            "https://example.org/a.xml",
                            11,
                            "2026-02-22T15:00:00Z",
                            "application/xml",
                            "",
                            25,
                            str(raw_xml),
                            "",
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/a2.xml",
                            12,
                            "2026-02-22T15:00:00Z",
                            "application/xml",
                            "",
                            24,
                            str(raw_xml),
                            "",
                        ),
                    ],
                )
                conn.commit()

                queue_rows, _summary = build_queue_rows(
                    conn,
                    source_ids={"parl_initiative_docs"},
                    allowed_formats={"xml"},
                    only_missing_excerpt=True,
                    dedupe_by="content_sha256",
                    limit=0,
                )

                self.assertEqual(len(queue_rows), 1)
                row = queue_rows[0]
                self.assertTrue(str(row["queue_key"]).startswith("path:"))
                self.assertEqual(int(row["refs_total"]), 2)
                self.assertEqual(int(row["refs_missing_excerpt"]), 2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
