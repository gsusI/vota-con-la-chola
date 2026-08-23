from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_document_provenance_gap_queue import GapQueueError, export_queue


class TestExportDocumentProvenanceGapQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.file_manifest = self.root / "provenance-files.jsonl"
        self.audit_report = self.root / "audit.json"
        self.queue = self.root / "queue.jsonl"
        self.report = self.root / "queue-report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def digest(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def write_inputs(self) -> None:
        rows = [
            {
                "path": "source/complete.html",
                "source_group": "source",
                "extension": "html",
                "bytes": 10,
                "sha256": "1" * 64,
                "provenance_status": "verified_path_checksum",
                "public_url_edges": 1,
            },
            {
                "path": "elections/url-gap.pdf",
                "source_group": "elections",
                "extension": "pdf",
                "bytes": 20,
                "sha256": "2" * 64,
                "provenance_status": "verified_content_checksum",
                "public_url_edges": 0,
            },
            {
                "path": "text_documents/parl_initiative_docs/unlinked.html",
                "source_group": "text_documents/parl_initiative_docs",
                "extension": "html",
                "bytes": 30,
                "sha256": "3" * 64,
                "provenance_status": "unlinked",
                "public_url_edges": 0,
            },
        ]
        self.file_manifest.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        self.audit_report.write_text(
            json.dumps(
                {
                    "file_manifest": {
                        "path": "provenance-files.jsonl",
                        "rows": 3,
                        "bytes": self.file_manifest.stat().st_size,
                        "sha256": self.digest(self.file_manifest.read_bytes()),
                    },
                    "totals": {
                        "files": 3,
                        "verified_checksum_files": 2,
                        "files_with_public_url": 1,
                    },
                    "checks": {"integrity_passed": True},
                }
            ),
            encoding="utf-8",
        )

    def execute(self) -> dict[str, object]:
        return export_queue(
            repo_root=self.root,
            file_manifest=self.file_manifest,
            audit_report=self.audit_report,
            queue_out=self.queue,
            report_out=self.report,
        )

    def test_exports_only_real_actionable_gaps_deterministically(self) -> None:
        self.write_inputs()

        first = self.execute()
        first_sha = first["queue"]["sha256"]
        second = self.execute()

        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["queue"]["rows"], 2)
        self.assertEqual(first["totals"]["checksum_lineage_gaps"], 1)
        self.assertEqual(first["totals"]["public_url_gaps"], 2)
        self.assertEqual(second["queue"]["sha256"], first_sha)
        rows = [
            json.loads(line)
            for line in self.queue.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(all(not row["guessed_source_url"] for row in rows))
        self.assertTrue(
            all(row["public_domain_personal_information_retained"] for row in rows)
        )
        self.assertEqual(rows[0]["priority"], "p0")
        self.assertFalse(rows[0]["needs_checksum_lineage"])
        self.assertTrue(rows[0]["needs_public_url"])

    def test_rejects_manifest_drift_from_audit(self) -> None:
        self.write_inputs()
        audit = json.loads(self.audit_report.read_text(encoding="utf-8"))
        audit["file_manifest"]["sha256"] = "0" * 64
        self.audit_report.write_text(json.dumps(audit), encoding="utf-8")

        with self.assertRaisesRegex(GapQueueError, "sha256 does not match"):
            self.execute()

    def test_completed_provenance_emits_valid_empty_queue(self) -> None:
        row = {
            "path": "source/complete.html",
            "source_group": "source",
            "extension": "html",
            "bytes": 10,
            "sha256": "1" * 64,
            "provenance_status": "verified_path_checksum",
            "public_url_edges": 1,
        }
        self.file_manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.audit_report.write_text(
            json.dumps(
                {
                    "file_manifest": {
                        "path": "provenance-files.jsonl",
                        "rows": 1,
                        "bytes": self.file_manifest.stat().st_size,
                        "sha256": self.digest(self.file_manifest.read_bytes()),
                    },
                    "totals": {
                        "files": 1,
                        "verified_checksum_files": 1,
                        "files_with_public_url": 1,
                    },
                    "checks": {"integrity_passed": True},
                }
            ),
            encoding="utf-8",
        )

        report = self.execute()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["queue"]["rows"], 0)
        self.assertTrue(report["queue"]["empty"])
        self.assertTrue(report["checks"]["queue_rows_balance_gap_union"])
        self.assertEqual(self.queue.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
