from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_raw_blocks import (
    build_dataset_readme,
    chunk_paths,
    collect_raw_files,
    should_exclude,
)


class PublicarHFRawBlocksTests(unittest.TestCase):
    def test_chunk_paths_respects_block_size(self) -> None:
        items = [Path(f"f{i}") for i in range(25)]
        chunks = chunk_paths(items, 10)
        self.assertEqual([len(c) for c in chunks], [10, 10, 5])

    def test_should_exclude_manual_by_default(self) -> None:
        rel = Path("manual/session/file.json")
        self.assertTrue(should_exclude(rel, include_manual=False, exclude_globs=[]))
        self.assertFalse(should_exclude(rel, include_manual=True, exclude_globs=[]))

    def test_collect_raw_files_filters_manual_and_globs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td)
            (raw / "manual" / "x").mkdir(parents=True, exist_ok=True)
            (raw / "text_documents").mkdir(parents=True, exist_ok=True)
            (raw / "manual" / "x" / "a.json").write_text("a", encoding="utf-8")
            (raw / "text_documents" / "b.pdf").write_text("b", encoding="utf-8")
            (raw / "text_documents" / "ignore.storage.json").write_text("c", encoding="utf-8")

            files = collect_raw_files(
                raw,
                include_manual=False,
                exclude_globs=["**/*storage*.json"],
                max_files=0,
            )
            rels = [p.relative_to(raw).as_posix() for p in files]
            self.assertEqual(rels, ["text_documents/b.pdf"])

    def test_build_dataset_readme_mentions_blocks_contract(self) -> None:
        text = build_dataset_readme(
            dataset_repo="org/raw",
            source_repo_url="https://github.com/example/repo",
            snapshot_date="2026-02-12",
            snapshot_rel_dir=Path("snapshots/2026-02-12"),
            blocks=[{"block_id": "block-00000"}],
            include_manual=False,
            exclude_globs=["manual/**"],
            max_files_per_block=10_000,
        )
        self.assertIn("Bloques `tar.gz`", text)
        self.assertIn("10000", text)
        self.assertIn("manual/**", text)


if __name__ == "__main__":
    unittest.main()
