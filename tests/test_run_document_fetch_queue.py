from __future__ import annotations

import tempfile
import unittest
import hashlib
from pathlib import Path

from publicdata_core.blobstore import StoredBlob
from publicdata_ops import enqueue_work_items, ensure_work_queue_schema
from publicdata_sqlite import open_db
from scripts.run_document_fetch_queue import (
    HostLimiter,
    _classify_download_failure,
    _validate_official_download,
    _validate_payload_contract,
    process_document_fetch_queue,
)


class TestRunDocumentFetchQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.conn = open_db(self.root / "docs.db")
        self.conn.executescript(
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
              content_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_id, source_record_id)
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL
            );
            CREATE TABLE parl_initiative_documents (
              parl_initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id),
              doc_kind TEXT NOT NULL,
              doc_url TEXT NOT NULL,
              source_record_pk INTEGER REFERENCES source_records(source_record_pk),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (initiative_id, doc_kind, doc_url)
            );
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              source_url TEXT NOT NULL,
              source_record_pk INTEGER UNIQUE REFERENCES source_records(source_record_pk),
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT,
              text_chars INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE document_fetches (
              doc_url TEXT PRIMARY KEY,
              source_id TEXT,
              first_attempt_at TEXT,
              last_attempt_at TEXT,
              attempts INTEGER NOT NULL DEFAULT 0,
              fetched_ok INTEGER NOT NULL DEFAULT 0,
              last_http_status INTEGER,
              last_error TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT
            );
            CREATE TABLE money_contract_documents (
              contract_document_id INTEGER PRIMARY KEY,
              source_url TEXT NOT NULL,
              document_source_record_pk INTEGER REFERENCES source_records(source_record_pk),
              updated_at TEXT NOT NULL
            );
            INSERT INTO sources VALUES (
              'congreso_iniciativas', 'Congreso', 'nacional', 'https://example.test',
              'json', 1, 'now', 'now'
            );
            INSERT INTO parl_initiatives VALUES ('initiative-1', 'congreso_iniciativas');
            """
        )
        ensure_work_queue_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _queue_file(self, *, filename: str, payload: bytes, max_attempts: int = 3) -> str:
        source_file = self.root / filename
        source_file.write_bytes(payload)
        url = source_file.as_uri()
        self.conn.execute(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
            ) VALUES ('initiative-1', 'bocg', ?, NULL, 'now', 'now')
            """,
            (url,),
        )
        self.conn.commit()
        enqueue_work_items(
            self.conn,
            pipeline_id="document_fetch",
            items=[
                {
                    "item_key": url,
                    "partition_key": "congreso_iniciativas",
                    "payload": {
                        "doc_url": url,
                        "initiative_id": "initiative-1",
                        "source_id": "congreso_iniciativas",
                    },
                    "max_attempts": max_attempts,
                }
            ],
        )
        return url

    def test_download_worker_streams_persists_links_and_completes_queue(self) -> None:
        url = self._queue_file(filename="official.pdf", payload=b"%PDF-1.7\ncontent")
        report = process_document_fetch_queue(
            self.conn,
            raw_root=self.root / "raw",
            pipeline_id="document_fetch",
            worker_id="worker-a",
            workers=2,
            per_host_workers=1,
            claim_size=10,
            max_items=0,
            lease_seconds=60,
            timeout=5,
            max_bytes=1_000,
            download_attempts=1,
            retry_delay_seconds=60,
            snapshot_date="2026-08-10",
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["totals"]["succeeded"], 1)
        self.assertEqual(report["totals"]["bytes_received"], 16)
        self.assertGreater(report["performance"]["items_per_second"], 0)
        self.assertGreater(report["performance"]["peak_rss_bytes"], 0)
        self.assertEqual(report["queue"]["state_counts"]["succeeded"], 1)

        document = self.conn.execute(
            "SELECT source_record_pk, content_sha256, raw_path FROM text_documents WHERE source_url = ?",
            (url,),
        ).fetchone()
        self.assertIsNotNone(document)
        self.assertTrue(Path(document["raw_path"]).is_file())
        linked = self.conn.execute(
            "SELECT source_record_pk FROM parl_initiative_documents WHERE doc_url = ?",
            (url,),
        ).fetchone()
        self.assertEqual(int(linked["source_record_pk"]), int(document["source_record_pk"]))
        fetch = self.conn.execute(
            "SELECT fetched_ok, attempts FROM document_fetches WHERE doc_url = ?",
            (url,),
        ).fetchone()
        self.assertEqual((int(fetch["fetched_ok"]), int(fetch["attempts"])), (1, 1))

    def test_oversize_download_is_dead_lettered_without_partial_file(self) -> None:
        url = self._queue_file(filename="too-big.pdf", payload=b"0123456789", max_attempts=1)
        report = process_document_fetch_queue(
            self.conn,
            raw_root=self.root / "raw",
            pipeline_id="document_fetch",
            worker_id="worker-a",
            workers=1,
            per_host_workers=1,
            claim_size=1,
            max_items=1,
            lease_seconds=60,
            timeout=5,
            max_bytes=5,
            download_attempts=1,
            retry_delay_seconds=60,
        )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["totals"]["dead"], 1)
        self.assertEqual(report["queue"]["state_counts"]["dead"], 1)
        fetch = self.conn.execute(
            "SELECT fetched_ok, last_error FROM document_fetches WHERE doc_url = ?",
            (url,),
        ).fetchone()
        self.assertEqual(int(fetch["fetched_ok"]), 0)
        self.assertIn("max_bytes", str(fetch["last_error"]))
        partial_root = self.root / "raw" / ".partial"
        self.assertFalse(partial_root.exists() and any(partial_root.iterdir()))

    def test_placsp_document_source_persists_and_links_all_url_sightings(self) -> None:
        source_file = self.root / "contract.pdf"
        source_file.write_bytes(b"%PDF-1.7\ncontract")
        url = source_file.as_uri()
        self.conn.executemany(
            "INSERT INTO money_contract_documents VALUES (?, ?, NULL, 'now')",
            [(1, url), (2, url)],
        )
        enqueue_work_items(
            self.conn,
            pipeline_id="placsp_document_fetch",
            items=[
                {
                    "item_key": url,
                    "partition_key": "placsp:00",
                    "payload": {
                        "doc_url": url,
                        "contract_document_id": 1,
                        "document_source_id": "placsp_contract_docs",
                    },
                    "max_attempts": 3,
                }
            ],
        )
        report = process_document_fetch_queue(
            self.conn,
            raw_root=self.root / "raw-contracts",
            pipeline_id="placsp_document_fetch",
            worker_id="worker-contracts",
            workers=1,
            per_host_workers=1,
            claim_size=1,
            max_items=1,
            lease_seconds=60,
            timeout=5,
            max_bytes=1_000,
            download_attempts=1,
            retry_delay_seconds=60,
            snapshot_date="2026-08-11",
        )
        self.assertEqual(report["status"], "ok")
        rows = self.conn.execute(
            """
            SELECT DISTINCT document_source_record_pk
            FROM money_contract_documents
            WHERE source_url = ?
            """,
            (url,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0]["document_source_record_pk"])
        source = self.conn.execute(
            "SELECT source_id FROM text_documents WHERE source_url = ?",
            (url,),
        ).fetchone()
        self.assertEqual(source["source_id"], "placsp_contract_docs")

    def test_failure_taxonomy_separates_permanent_and_retryable_errors(self) -> None:
        self.assertEqual(
            _classify_download_failure(http_status=404, error="HTTP 404"),
            ("not_fetchable", False),
        )
        self.assertEqual(
            _classify_download_failure(http_status=403, error="HTTP 403"),
            ("access_blocked", True),
        )
        self.assertEqual(
            _classify_download_failure(http_status=None, error="max_bytes exceeded"),
            ("oversize", False),
        )

    def test_boe_document_validator_requires_embedded_exact_identifier(self) -> None:
        path = self.root / "boe.xml"
        payload = (
            b'<?xml version="1.0"?><documento><metadatos><identificador>'
            b"BOE-A-2026-123</identificador></metadatos></documento>"
        )
        path.write_bytes(payload)
        stored = StoredBlob(
            content_sha256=hashlib.sha256(payload).hexdigest(),
            bytes=len(payload),
            path=path,
            content_type="application/xml",
            etag=None,
            last_modified=None,
            deduplicated=False,
        )
        self.assertIsNone(
            _validate_official_download(
                url="https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-123",
                source_id="boe_document_xml",
                stored=stored,
            )
        )
        self.assertEqual(
            _validate_official_download(
                url="https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-999",
                source_id="boe_document_xml",
                stored=stored,
            ),
            "boe_document_identifier_mismatch",
        )

    def test_payload_contract_accepts_real_semantic_html_and_detects_block_page(self) -> None:
        path = self.root / "initiative.html"
        payload = (
            b'<!DOCTYPE html><html><head><title>12-22/DL-000002</title>'
            b"</head><body>Official initiative</body></html>"
        )
        path.write_bytes(payload)
        stored = StoredBlob(
            content_sha256=hashlib.sha256(payload).hexdigest(),
            bytes=len(payload),
            path=path,
            content_type="text/html;charset=UTF-8",
            etag=None,
            last_modified=None,
            deduplicated=False,
        )
        contract = {
            "require_https": True,
            "expected_host": "www.parlamentodeandalucia.es",
            "minimum_bytes": 32,
            "allowed_content_types": ["text/html"],
            "required_ascii_casefolded": ["<!doctype html", "12-22/dl-000002"],
            "forbidden_ascii_casefolded": ["<title>just a moment...</title>"],
        }
        self.assertIsNone(
            _validate_payload_contract(
                url="https://www.parlamentodeandalucia.es/initiative",
                stored=stored,
                contract=contract,
            )
        )
        path.write_bytes(b"<title>Just a moment...</title>")
        blocked = StoredBlob(
            content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            bytes=path.stat().st_size,
            path=path,
            content_type="text/html",
            etag=None,
            last_modified=None,
            deduplicated=False,
        )
        self.assertEqual(
            _validate_payload_contract(
                url="https://www.parlamentodeandalucia.es/initiative",
                stored=blocked,
                contract={
                    **contract,
                    "minimum_bytes": 1,
                    "required_ascii_casefolded": [],
                },
            ),
            "validation_contract_forbidden_pattern_present",
        )

    def test_payload_contract_enforces_immutable_content_hash(self) -> None:
        path = self.root / "official.pdf"
        payload = b"%PDF-1.7\nreal official bytes"
        path.write_bytes(payload)
        stored = StoredBlob(
            content_sha256=hashlib.sha256(payload).hexdigest(),
            bytes=len(payload),
            path=path,
            content_type="application/pdf",
            etag=None,
            last_modified=None,
            deduplicated=False,
        )
        self.assertEqual(
            _validate_payload_contract(
                url="https://official.example/document.pdf",
                stored=stored,
                contract={"expected_content_sha256": "0" * 64},
            ),
            "validation_contract_expected_sha256_mismatch",
        )

    def test_storage_floor_blocks_before_claim(self) -> None:
        self._queue_file(filename="official.pdf", payload=b"%PDF-1.7\ncontent")
        report = process_document_fetch_queue(
            self.conn,
            raw_root=self.root / "raw",
            pipeline_id="document_fetch",
            worker_id="worker-storage-gate",
            workers=2,
            per_host_workers=1,
            claim_size=10,
            max_items=0,
            lease_seconds=60,
            timeout=5,
            max_bytes=1_000,
            min_free_bytes=10**20,
            download_attempts=1,
            retry_delay_seconds=60,
        )
        self.assertEqual(report["status"], "blocked_storage")
        self.assertEqual(report["totals"]["claimed"], 0)
        self.assertEqual(report["queue"]["state_counts"]["pending"], 1)

    def test_host_circuit_opens_after_repeated_hard_failures(self) -> None:
        limiter = HostLimiter(per_host_workers=2, hard_failure_threshold=2)
        url = "https://blocked.example/legis10/document.pdf"
        limiter.record_status(url, 403)
        self.assertFalse(limiter.is_open(url))
        limiter.record_status(url, 403)
        self.assertTrue(limiter.is_open(url))
        self.assertEqual(limiter.opened_hosts(), ["blocked.example"])
        self.assertFalse(
            limiter.is_open("https://blocked.example/legis15/document.pdf")
        )
        self.assertEqual(
            limiter.opened_circuits(),
            ["blocked.example|legis:10|legis10/document.pdf"],
        )

    def test_repeated_server_errors_open_only_the_affected_cohort(self) -> None:
        limiter = HostLimiter(per_host_workers=1, hard_failure_threshold=2)
        old_url = (
            "https://www.senado.es/web/ficopendataservlet?legis=10&tipoFich=12"
        )
        current_url = (
            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=12"
        )
        limiter.record_status(old_url, 500)
        limiter.record_status(old_url, 500)
        self.assertTrue(limiter.is_open(old_url))
        self.assertFalse(limiter.is_open(current_url))


if __name__ == "__main__":
    unittest.main()
