from __future__ import annotations

import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from publicdata_ops import enqueue_work_items
from publicdata_sqlite import open_db
from scripts.run_text_extraction_queue import process_text_extraction_queue


class TestRunTextExtractionQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.conn = open_db(self.root / "extract.db")
        self.conn.execute(
            """
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL,
              source_url TEXT NOT NULL,
              source_record_pk INTEGER UNIQUE,
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT,
              text_chars INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_worker_extracts_once_and_updates_all_content_duplicates(self) -> None:
        raw_path = self.root / "document.html"
        payload = b"<html><body><h1>Official record</h1><p>Decision evidence.</p></body></html>"
        raw_path.write_bytes(payload)
        content_sha = hashlib.sha256(payload).hexdigest()
        self.conn.executemany(
            """
            INSERT INTO text_documents (
              source_id, source_url, source_record_pk, content_type,
              content_sha256, bytes, raw_path, created_at, updated_at
            ) VALUES ('official_docs', ?, ?, 'text/html', ?, ?, ?, 'now', 'now')
            """,
            [
                ("https://example.test/a", 1, content_sha, len(payload), str(raw_path)),
                ("https://example.test/b", 2, content_sha, len(payload), str(raw_path)),
            ],
        )
        self.conn.commit()
        enqueue_work_items(
            self.conn,
            pipeline_id="text_extraction",
            items=[
                {
                    "item_key": f"sha256:{content_sha}",
                    "partition_key": "official_docs",
                    "payload": {
                        "text_document_id": 1,
                        "content_sha256": content_sha,
                        "content_type": "text/html",
                        "raw_path": str(raw_path),
                    },
                }
            ],
        )

        report = process_text_extraction_queue(
            self.conn,
            text_root=self.root / "text",
            pipeline_id="text_extraction",
            worker_id="worker-a",
            workers=2,
            claim_size=4,
            max_items=0,
            lease_seconds=60,
            max_input_bytes=1_000,
            max_text_chars=10_000,
            excerpt_chars=100,
            retry_delay_seconds=60,
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["succeeded"], 1)
        self.assertEqual(report["totals"]["document_rows_updated"], 2)
        rows = self.conn.execute(
            """
            SELECT text_excerpt, text_path, text_sha256, text_extraction_method, text_truncated
            FROM text_documents ORDER BY text_document_id
            """
        ).fetchall()
        self.assertEqual(len({row["text_path"] for row in rows}), 1)
        self.assertIn("Official record", rows[0]["text_excerpt"])
        self.assertEqual(rows[0]["text_extraction_method"], "markup_path")
        self.assertEqual(int(rows[0]["text_truncated"]), 0)
        with gzip.open(rows[0]["text_path"], "rt", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "Official record Decision evidence.")

    def test_missing_file_reaches_dead_letter(self) -> None:
        self.conn.execute(
            """
            INSERT INTO text_documents (
              source_id, source_url, source_record_pk, content_type,
              content_sha256, bytes, raw_path, created_at, updated_at
            ) VALUES ('official_docs', 'https://example.test/missing', 3, 'text/html',
              'missing-sha', 10, ?, 'now', 'now')
            """,
            (str(self.root / "missing.html"),),
        )
        self.conn.commit()
        enqueue_work_items(
            self.conn,
            pipeline_id="text_extraction",
            items=[
                {
                    "item_key": "sha256:missing-sha",
                    "payload": {
                        "text_document_id": 1,
                        "content_sha256": "missing-sha",
                        "content_type": "text/html",
                        "raw_path": str(self.root / "missing.html"),
                    },
                    "max_attempts": 1,
                }
            ],
        )
        report = process_text_extraction_queue(
            self.conn,
            text_root=self.root / "text",
            pipeline_id="text_extraction",
            worker_id="worker-a",
            workers=1,
            claim_size=1,
            max_items=1,
            lease_seconds=60,
            max_input_bytes=1_000,
            max_text_chars=10_000,
            excerpt_chars=100,
            retry_delay_seconds=60,
        )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["dead"], 1)
        self.assertIn("FileNotFoundError", report["failure_samples"][0]["error"])


if __name__ == "__main__":
    unittest.main()
