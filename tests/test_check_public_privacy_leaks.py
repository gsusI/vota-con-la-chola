from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import check_public_privacy_leaks as checker


class TestCheckPublicPrivacyLeaks(unittest.TestCase):
    def test_collect_findings_detects_local_paths_and_email(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            leak_file = root / "status.json"
            leak_file.write_text(
                (
                    '{"source_url":"file:///Users/alice/Projects/private.json","tracker":"'
                    '/Users/alice/repo/docs/etl/e2e-scrape-load-tracker.md","email":"alice@example.com"}'
                ),
                encoding="utf-8",
            )
            findings, files_scanned = checker.collect_findings([root])
            self.assertGreaterEqual(files_scanned, 1)
            kinds = {f.kind for f in findings}
            self.assertIn("local_file_url", kinds)
            self.assertIn("local_user_path", kinds)
            self.assertIn("email", kinds)

    def test_collect_findings_skips_binary_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parquet_like = root / "data.parquet"
            parquet_like.write_text(
                "file:///Users/alice/private.parquet alice@example.com",
                encoding="utf-8",
            )
            findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 0)
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
