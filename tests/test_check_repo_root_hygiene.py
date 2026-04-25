from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import check_repo_root_hygiene as checker


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


class TestCheckRepoRootHygiene(unittest.TestCase):
    def test_collect_findings_passes_for_clean_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("# clean\n", encoding="utf-8")

            findings = checker.collect_findings(repo_root)

            self.assertEqual(findings, [])

    def test_collect_findings_flags_untracked_empty_root_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("# clean\n", encoding="utf-8")
            (repo_root / "strict-network").write_text("", encoding="utf-8")

            findings = checker.collect_findings(repo_root)

            self.assertEqual([finding.kind for finding in findings], ["empty_root_file"])
            self.assertEqual([finding.path for finding in findings], ["strict-network"])

    def test_collect_findings_flags_suspicious_root_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("# clean\n", encoding="utf-8")
            (repo_root / "-").write_text("artifact\n", encoding="utf-8")
            (repo_root / "{{ka[missing_urls]}}").write_text("artifact\n", encoding="utf-8")
            (repo_root / "1252").write_text("", encoding="utf-8")
            artifact_dir = repo_root / "python3 scripts" / "ingestar_politicos_es.py ingest --db etl"
            artifact_dir.mkdir(parents=True)

            findings = checker.collect_findings(repo_root)

            self.assertEqual(
                [(finding.kind, finding.path) for finding in findings],
                [
                    ("suspicious_root_entry", "-"),
                    ("suspicious_root_entry", "1252"),
                    ("suspicious_root_entry", "python3 scripts"),
                    ("suspicious_root_entry", "{{ka[missing_urls]}}"),
                ],
            )

    def test_collect_findings_ignores_tracked_empty_root_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            tracked = repo_root / "empty.txt"
            tracked.write_text("", encoding="utf-8")
            subprocess.run(["git", "add", "empty.txt"], cwd=repo_root, check=True)

            findings = checker.collect_findings(repo_root)

            self.assertEqual(findings, [])

    def test_collect_findings_flags_unescaped_gitignore_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("/{ka*\n/{{ka*\n", encoding="utf-8")

            findings = checker.collect_findings(repo_root)

            self.assertEqual(
                [(finding.kind, finding.line, finding.detail) for finding in findings],
                [
                    ("invalid_gitignore_pattern", 1, "/{ka*"),
                    ("invalid_gitignore_pattern", 2, "/{{ka*"),
                ],
            )

    def test_collect_findings_accepts_escaped_gitignore_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("/\\{ka*\n/\\{\\{ka*\n", encoding="utf-8")

            findings = checker.collect_findings(repo_root)

            self.assertEqual(findings, [])

    def test_findings_to_json_shape_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            init_git_repo(repo_root)
            (repo_root / ".gitignore").write_text("/{ka*\n", encoding="utf-8")
            (repo_root / "strict-network").write_text("", encoding="utf-8")
            (repo_root / "-").write_text("artifact\n", encoding="utf-8")

            payload = json.loads(checker.findings_to_json(repo_root, checker.collect_findings(repo_root)))

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["counts"]["findings_total"], 3)
            self.assertEqual(payload["counts"]["empty_root_file"], 1)
            self.assertEqual(payload["counts"]["suspicious_root_entry"], 1)
            self.assertEqual(payload["counts"]["invalid_gitignore_pattern"], 1)
            self.assertEqual(payload["findings"][0]["kind"], "empty_root_file")


if __name__ == "__main__":
    unittest.main()
