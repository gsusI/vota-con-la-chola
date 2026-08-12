from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.enqueue_pipeline_work import (
    iter_work_items,
    main,
    materialize_initiative_document_links,
)


class TestEnqueuePipelineWork(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "pipeline.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_id TEXT NOT NULL,
              source_snapshot_date TEXT
            );
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER,
              source_url TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              legislature TEXT,
              links_bocg_json TEXT,
              links_ds_json TEXT
            );
            CREATE TABLE parl_initiative_documents (
              initiative_id TEXT NOT NULL,
              doc_kind TEXT NOT NULL,
              doc_url TEXT NOT NULL,
              source_record_pk INTEGER,
              created_at TEXT,
              updated_at TEXT,
              UNIQUE (initiative_id, doc_kind, doc_url)
            );
            CREATE TABLE document_fetches (
              doc_url TEXT PRIMARY KEY,
              attempts INTEGER,
              fetched_ok INTEGER,
              last_http_status INTEGER
            );
            CREATE TABLE money_contract_documents (
              contract_document_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_url TEXT NOT NULL,
              document_kind TEXT,
              document_source_record_pk INTEGER
            );
            """
        )
        self.conn.executemany(
            "INSERT INTO source_records VALUES (?, ?, ?, '2026-08-10')",
            [(1, "source-a", "a-1"), (2, "source-a", "a-2"), (3, "source-b", "b-1")],
        )
        self.conn.executemany(
            "INSERT INTO text_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "source-a", 1, "https://example.test/a.pdf", "application/pdf", "abc", 10, "raw/a.pdf", None),
                (2, "source-a", 2, "https://example.test/b.pdf", "application/pdf", "def", 20, "raw/b.pdf", "done"),
            ],
        )
        self.conn.execute(
            "INSERT INTO parl_initiatives VALUES ('i-1', 'source-a', '15', NULL, NULL)"
        )
        self.conn.executemany(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk,
              created_at, updated_at
            ) VALUES ('i-1', 'bocg', ?, NULL, NULL, NULL)
            """,
            [("https://example.test/a.pdf",), ("https://example.test/b.pdf",)],
        )
        self.conn.execute(
            "INSERT INTO document_fetches VALUES ('https://example.test/b.pdf', 1, 1, 200)"
        )
        self.conn.executemany(
            "INSERT INTO money_contract_documents VALUES (?, ?, ?, ?, NULL)",
            [
                (1, "placsp_sindicacion", "https://example.test/contract-a.pdf", "legal"),
                (2, "placsp_sindicacion", "https://example.test/contract-a.pdf", "legal"),
                (3, "placsp_sindicacion", "https://example.test/contract-b.pdf", "technical"),
            ],
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_iterators_filter_and_keep_payloads_small(self) -> None:
        source_rows = list(
            iter_work_items(
                self.conn,
                kind="source-record-transform",
                source_ids=["source-a"],
                only_missing=False,
                limit=0,
                fetch_size=1,
                max_attempts=4,
            )
        )
        self.assertEqual([row["item_key"] for row in source_rows], ["source-a:a-1", "source-a:a-2"])
        self.assertNotIn("raw_payload", source_rows[0]["payload"])

        text_rows = list(
            iter_work_items(
                self.conn,
                kind="text-extract",
                source_ids=[],
                only_missing=True,
                limit=0,
                fetch_size=10,
                max_attempts=5,
            )
        )
        self.assertEqual([row["item_key"] for row in text_rows], ["sha256:abc"])

        fetch_rows = list(
            iter_work_items(
                self.conn,
                kind="document-fetch",
                source_ids=[],
                only_missing=True,
                limit=0,
                fetch_size=10,
                max_attempts=5,
            )
        )
        self.assertEqual([row["item_key"] for row in fetch_rows], ["https://example.test/a.pdf"])

        placsp_rows = list(
            iter_work_items(
                self.conn,
                kind="placsp-document-fetch",
                source_ids=["placsp_sindicacion"],
                only_missing=True,
                limit=0,
                fetch_size=10,
                max_attempts=5,
            )
        )
        self.assertEqual(len(placsp_rows), 2)
        self.assertEqual(placsp_rows[0]["payload"]["manifest_sightings"], 2)
        self.assertEqual(
            placsp_rows[0]["payload"]["document_source_id"],
            "placsp_contract_docs",
        )
        self.assertTrue(str(placsp_rows[0]["partition_key"]).startswith("placsp:"))

    def test_cli_streams_rows_into_durable_queue_and_writes_safe_report(self) -> None:
        self.conn.close()
        report_path = Path(self.temp_dir.name) / "report.json"
        exit_code = main(
            [
                "--db",
                str(self.db_path),
                "--kind",
                "source-record-transform",
                "--source-ids",
                "source-a",
                "--batch-size",
                "1",
                "--report-out",
                str(report_path),
            ]
        )
        self.assertEqual(exit_code, 0)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["enqueue"]["inserted_total"], 2)
        self.assertEqual(report["queue"]["state_counts"]["pending"], 2)
        self.assertNotIn(str(Path.home()), report_path.read_text(encoding="utf-8"))

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def test_materializes_json_links_before_network_fetch(self) -> None:
        self.conn.execute(
            "INSERT INTO parl_initiatives VALUES (?, ?, ?, ?, ?)",
            (
                "i-2",
                "source-a",
                "15",
                json.dumps(
                    [
                        "https://official.example/i-2.pdf",
                        "https://official.example/i-2.pdf",
                    ]
                ),
                json.dumps(
                    {"url": "https://official.example/i-2-details.html"}
                ),
            ),
        )
        report = materialize_initiative_document_links(
            self.conn,
            source_ids=["source-a"],
            fetch_size=1,
        )
        self.assertEqual(report["rows_candidate"], 2)
        self.assertEqual(report["rows_inserted"], 2)
        rows = self.conn.execute(
            """
            SELECT doc_kind, doc_url
            FROM parl_initiative_documents
            WHERE initiative_id = 'i-2'
            ORDER BY doc_kind, doc_url
            """
        ).fetchall()
        self.assertEqual(
            [(row["doc_kind"], row["doc_url"]) for row in rows],
            [
                ("bocg", "https://official.example/i-2.pdf"),
                ("ds", "https://official.example/i-2-details.html"),
            ],
        )

        queued = list(
            iter_work_items(
                self.conn,
                kind="document-fetch",
                source_ids=["source-a"],
                only_missing=True,
                limit=0,
                fetch_size=10,
                max_attempts=5,
            )
        )
        i2 = next(row for row in queued if row["item_key"].endswith("i-2.pdf"))
        self.assertEqual(i2["partition_key"], "source-a:leg15")
        self.assertGreater(int(i2["priority"]), 1_000)


if __name__ == "__main__":
    unittest.main()
