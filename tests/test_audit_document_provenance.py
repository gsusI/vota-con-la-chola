from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_document_provenance import run_audit


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class TestAuditDocumentProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp.name)
        self.raw_root = self.repo_root / "raw"
        self.raw_root.mkdir()
        self.manifest = self.repo_root / "inventory.jsonl"
        self.database = self.repo_root / "source.db"
        self.file_manifest = self.repo_root / "provenance-files.jsonl"
        self.edge_manifest = self.repo_root / "provenance-edges.jsonl"
        self.report = self.repo_root / "report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_inventory(self, files: dict[str, bytes]) -> None:
        rows = []
        for relative, payload in files.items():
            path = self.raw_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            rows.append(
                {
                    "path": relative,
                    "source_group": relative.split("/", 1)[0],
                    "extension": path.suffix.lstrip("."),
                    "bytes": len(payload),
                    "sha256": digest(payload),
                    "status": "ok",
                }
            )
        self.manifest.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )

    def create_database(self, rows: list[tuple[object, ...]]) -> None:
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            CREATE TABLE text_documents (
              raw_path TEXT,
              content_sha256 TEXT,
              source_id TEXT,
              source_url TEXT,
              fetched_at TEXT,
              bytes INTEGER,
              text_path TEXT,
              text_sha256 TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO text_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()
        connection.close()

    def execute_audit(self) -> dict[str, object]:
        return run_audit(
            repo_root=self.repo_root,
            inventory_root=self.raw_root,
            inventory_manifest=self.manifest,
            database_paths=[self.database],
            file_manifest_out=self.file_manifest,
            edge_manifest_out=self.edge_manifest,
            report_out=self.report,
        )

    def test_reconciles_exact_and_content_addressed_paths_without_hiding_gaps(
        self,
    ) -> None:
        exact = b"official-pdf"
        moved = b"official-xml"
        unlinked = b"official-html-with-missing-lineage"
        text = b"extracted official text"
        self.write_inventory(
            {
                "source/exact.pdf": exact,
                "source/moved.xml": moved,
                "source/unlinked.html": unlinked,
            }
        )
        text_path = self.repo_root / "derived" / "exact.txt.gz"
        text_path.parent.mkdir()
        with gzip.open(text_path, "wb") as handle:
            handle.write(text)
        self.create_database(
            [
                (
                    "raw/source/exact.pdf",
                    digest(exact),
                    "official_documents",
                    "https://public.example.es/exact.pdf",
                    "2026-08-12T00:00:00Z",
                    len(exact),
                    "derived/exact.txt.gz",
                    digest(text),
                ),
                (
                    "raw/old/location.xml",
                    digest(moved),
                    "official_documents",
                    "https://public.example.es/moved.xml",
                    "2026-08-12T00:00:00Z",
                    len(moved),
                    None,
                    None,
                ),
            ]
        )

        report = self.execute_audit()

        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["checks"]["integrity_passed"])
        self.assertFalse(report["checks"]["promotion_ready"])
        self.assertEqual(report["totals"]["files"], 3)
        self.assertEqual(report["totals"]["verified_path_checksum"], 1)
        self.assertEqual(report["totals"]["verified_content_checksum"], 1)
        self.assertEqual(report["totals"]["unlinked"], 1)
        self.assertEqual(report["totals"]["files_with_public_url"], 2)
        self.assertEqual(report["text_artifacts"]["checksum_verified"], 1)
        file_rows = [
            json.loads(line)
            for line in self.file_manifest.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            [row["provenance_status"] for row in file_rows],
            [
                "verified_path_checksum",
                "verified_content_checksum",
                "unlinked",
            ],
        )

    def test_checksum_conflict_fails_integrity_without_discarding_file(self) -> None:
        payload = b"official-document"
        self.write_inventory({"source/conflict.pdf": payload})
        self.create_database(
            [
                (
                    "raw/source/conflict.pdf",
                    "0" * 64,
                    "official_documents",
                    "https://public.example.es/conflict.pdf",
                    "2026-08-12T00:00:00Z",
                    len(payload),
                    None,
                    None,
                )
            ]
        )

        report = self.execute_audit()

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["integrity_passed"])
        self.assertEqual(report["totals"]["checksum_conflict"], 1)
        self.assertEqual(report["totals"]["files_with_checksum_conflict"], 1)

    def test_missing_declared_database_fails_integrity(self) -> None:
        self.write_inventory({"source/document.pdf": b"official-document"})

        report = self.execute_audit()

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["database_inputs_readable"])
        self.assertFalse(report["checks"]["integrity_passed"])


if __name__ == "__main__":
    unittest.main()
