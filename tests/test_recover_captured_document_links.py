from __future__ import annotations

import unittest
from pathlib import Path

from scripts.recover_captured_document_links import (
    load_existing_manifest_rows,
    merge_manifest_rows,
)


class TestRecoverCapturedDocumentLinks(unittest.TestCase):
    def test_incremental_merge_preserves_real_checked_in_relations(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest = (
            repo_root / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "captured-link-document-lineage.jsonl"
        )
        existing = load_existing_manifest_rows(manifest)

        self.assertGreaterEqual(len(existing), 50)
        replay = [existing[0]]
        merged = merge_manifest_rows(existing, replay)

        self.assertEqual(len(merged), len(existing))
        self.assertEqual(
            {(item["capture"]["sha256"], item["source_url"]) for item in merged},
            {(item["capture"]["sha256"], item["source_url"]) for item in existing},
        )


if __name__ == "__main__":
    unittest.main()
