from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.scrub_workstation_paths import main, scrub_text

HOME = "/" + "Users" + "/alice"
REPO = HOME + "/Library/CloudStorage/GoogleDrive-alice@example.com/My Drive/Vault/vota-con-la-chola"


class TestScrubWorkstationPaths(unittest.TestCase):
    def test_repo_paths_become_repo_relative(self) -> None:
        self.assertEqual(scrub_text(f'"file://{REPO}/etl/data/raw/x.json"'), '"etl/data/raw/x.json"')
        self.assertEqual(scrub_text(f"Repository: `{REPO}`"), "Repository: `.`")
        self.assertEqual(scrub_text(f"{REPO}/a and {REPO}/b"), "a and b")

    def test_other_home_paths_and_drive_accounts_are_redacted(self) -> None:
        self.assertEqual(scrub_text(HOME + "/.cache/uv/x"), "~/.cache/uv/x")
        self.assertEqual(scrub_text("GoogleDrive-alice@example.com/x"), "GoogleDrive-<redacted-account>/x")

    def test_official_urls_are_untouched(self) -> None:
        url = "https://community.vortal.biz/PRODSTS/Users/Login/Index"
        self.assertEqual(scrub_text(url), url)
        self.assertEqual(scrub_text("https://github.com/gsusI/vota-con-la-chola/blob/main"), "https://github.com/gsusI/vota-con-la-chola/blob/main")

    def test_check_mode_reports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "log.md"
            target.write_text(f"see {REPO}/docs/a.md\n", encoding="utf-8")
            self.assertEqual(main([td, "--check"]), 1)
            self.assertIn(HOME, target.read_text(encoding="utf-8"))
            self.assertEqual(main([td]), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "see docs/a.md\n")
            self.assertEqual(main([td, "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
