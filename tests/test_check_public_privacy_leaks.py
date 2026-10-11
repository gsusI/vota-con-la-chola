from __future__ import annotations

import gzip
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from publicdata_publish import privacy as checker
from scripts import check_public_privacy_leaks as script_checker


class TestCheckPublicPrivacyLeaks(unittest.TestCase):
    def test_vortal_public_login_is_not_a_workstation_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            public = "https://community.vortal.biz/PRODSTS/Users/Login/Index?SkinName=aytogijon"
            for name in ("source.xml", "source.xml.gz"):
                target = root / name
                payload = public + " <tag>https://other.example/Users/alice/private.xml</tag> " + "/Users/alice/private.xml"
                if name.endswith(".gz"):
                    with gzip.open(target, "wt") as handle:
                        handle.write(payload)
                else:
                    target.write_text(payload)
            findings, _ = checker.collect_findings([root])
            self.assertEqual(len(findings), 4)
            self.assertTrue(all(f.kind == "local_user_path" for f in findings))

    def test_default_scan_paths_cover_next_public_tree(self) -> None:
        self.assertIn(Path("ui/gh-pages-next/public"), checker.DEFAULT_SCAN_PATHS)
        self.assertIs(script_checker.collect_findings, checker.collect_findings)

    def test_collect_findings_detects_local_paths_but_allows_public_email(self) -> None:
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
            self.assertNotIn("email", kinds)

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

    def test_collect_findings_detects_relative_db_path_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "citizen.json"
            artifact.write_text(
                '{"meta":{"generated_at":"2026-03-06T00:00:00Z","db_path":"etl/data/staging/politicos-es.db"}}',
                encoding="utf-8",
            )
            findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertEqual([f.kind for f in findings], ["internal_db_path"])

    def test_collect_findings_scans_gzip_text_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "public.json.gz"
            with gzip.open(artifact, "wt", encoding="utf-8") as handle:
                handle.write(
                    '{"source_url":"file:///Users/alice/private.json"}'
                )
            findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertIn("local_file_url", {finding.kind for finding in findings})

    def test_collect_findings_prefilters_large_safe_files_before_text_decode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "large.json"
            artifact.write_text("safe artifact without leak sentinels", encoding="utf-8")
            with mock.patch.object(checker, "LARGE_FILE_PREFILTER_BYTES", 1):
                with mock.patch.object(
                    checker,
                    "read_text_file",
                    side_effect=AssertionError("large safe file should not be decoded"),
                ):
                    findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertEqual(findings, [])

    def test_collect_findings_streams_large_text_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "large.json"
            artifact.write_text(
                '{"source_url":"file:///Users/alice/private.json"}',
                encoding="utf-8",
            )
            with mock.patch.object(checker, "LARGE_FILE_PREFILTER_BYTES", 1):
                with mock.patch.object(
                    checker,
                    "read_text_file",
                    side_effect=AssertionError("large candidate must stream"),
                ):
                    findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertIn("local_file_url", {finding.kind for finding in findings})

    def test_collect_findings_skips_non_candidates_reported_by_rg(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "public.json"
            artifact.write_text("safe artifact without leak sentinels", encoding="utf-8")
            with mock.patch.object(checker, "collect_rg_candidate_paths", return_value=set()):
                with mock.patch.object(
                    checker,
                    "read_text_file",
                    side_effect=AssertionError("rg prefilter should skip safe file decode"),
                ):
                    findings, files_scanned = checker.collect_findings([root])
            self.assertEqual(files_scanned, 1)
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
