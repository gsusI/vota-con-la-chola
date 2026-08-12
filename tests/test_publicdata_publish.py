from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publicdata_publish.hf_snapshot import collect_published_files, ensure_iso_date, parse_csv_list
from publicdata_publish.privacy import collect_findings
from publicdata_publish.sanitize import redact_sensitive_text, sanitize_url_for_public


class TestPublicDataPublish(unittest.TestCase):
    def test_sanitize_url_and_text_remove_sensitive_publication_fields(self) -> None:
        safe = sanitize_url_for_public("https://user:pass@example.org/x?token=123&ok=1")
        self.assertEqual(safe, "https://example.org/x?token=REDACTED&ok=1")
        self.assertEqual(sanitize_url_for_public("file:///Users/alice/private.json"), "")

        redacted = redact_sensitive_text("Bearer hf_abcdefghijklmnopqrstuvwxyz01234567 /Users/alice a@example.com")
        self.assertNotIn("hf_abcdefghijklmnopqrstuvwxyz01234567", redacted)
        self.assertNotIn("/Users/alice", redacted)
        self.assertIn("a@example.com", redacted)

    def test_privacy_collect_findings_detects_public_artifact_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "artifact.json"
            artifact.write_text(
                '{"source_url":"file:///Users/alice/private.json","db_path":"etl/data/staging/foo.db"}',
                encoding="utf-8",
            )

            findings, files_scanned = collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertEqual({finding.kind for finding in findings}, {"local_file_url", "local_user_path", "internal_db_path"})

    def test_hf_snapshot_helpers_are_packaged(self) -> None:
        self.assertEqual(ensure_iso_date("2026-02-12"), "2026-02-12")
        self.assertEqual(parse_csv_list("a,b\nc"), {"a", "b", "c"})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "thing-2026-02-12.json").write_text("{}", encoding="utf-8")
            (root / "accountability-ledger-latest.json").write_text("{}", encoding="utf-8")
            (root / "accountability-dossiers-latest.json").write_text("{}", encoding="utf-8")
            (root / "accountability-evidence-api-latest.json").write_text("{}", encoding="utf-8")
            files = collect_published_files(root, "2026-02-12")
            self.assertEqual(
                [path.name for path in files],
                [
                    "accountability-dossiers-latest.json",
                    "accountability-evidence-api-latest.json",
                    "accountability-ledger-latest.json",
                    "thing-2026-02-12.json",
                ],
            )


if __name__ == "__main__":
    unittest.main()
