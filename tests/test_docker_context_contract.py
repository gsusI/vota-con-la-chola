from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDockerContextContract(unittest.TestCase):
    def test_etl_image_installs_git_for_repository_hygiene_gates(self) -> None:
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("    git \\\n", dockerfile)

    def test_local_corpora_and_tooling_are_excluded_but_samples_remain(self) -> None:
        lines = {
            line.strip()
            for line in (REPO_ROOT / ".dockerignore")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertTrue(
            {
                ".venv",
                ".scale-origin-*",
                "docs/etl/runs",
                "docs/etl/sprints",
                "docs/gh-pages",
                "docs/screenshots",
                "etl/data/derived",
                "etl/data/object-origin",
                "etl/data/raw/**",
                "etl/data/restored",
                "etl/data/staging/**",
                "etl/data/published/**",
            }.issubset(lines)
        )
        self.assertIn("!etl/data/raw/samples", lines)
        self.assertIn("!etl/data/raw/samples/**", lines)
        self.assertIn(
            "!etl/data/published/proximas-elecciones-espana.json",
            lines,
        )


if __name__ == "__main__":
    unittest.main()
