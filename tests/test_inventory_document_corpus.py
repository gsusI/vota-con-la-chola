from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.inventory_document_corpus import (
    _count_pdf_page_text,
    _size_bucket,
    inspect_markup,
    run_inventory,
)


class TestInventoryDocumentCorpus(unittest.TestCase):
    def test_markup_inventory_uses_relative_paths_and_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "official" / "record.html"
            path.parent.mkdir()
            path.write_text("<html><body>Public evidence 123</body></html>", encoding="utf-8")
            item = inspect_markup(path, root)
            self.assertEqual(item["path"], "official/record.html")
            self.assertEqual(item["source_group"], "official")
            self.assertEqual(item["quality_class"], "markup_with_text")
            self.assertGreater(item["text_chars"], 0)
            self.assertEqual(len(item["sha256"]), 64)

    def test_inventory_aggregates_real_formats_without_promoting_100k(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "source").mkdir()
            (root / "source" / "a.xml").write_text("<root>alpha</root>", encoding="utf-8")
            (root / "source" / "b.pdf").write_bytes(b"%PDF-fixture")
            fake_pdf = {
                "path": "source/b.pdf",
                "source_group": "source",
                "extension": "pdf",
                "mime_type": "application/pdf",
                "bytes": 12,
                "sha256": "a" * 64,
                "status": "ok",
                "page_count": 2,
                "text_chars": 400,
                "text_density_chars_per_page": 200.0,
                "quality_class": "pdf_digital_text",
                "page_text_quality": {
                    "segments": 2,
                    "pages_with_text": 2,
                    "pages_empty": 0,
                    "pages_sparse_ocr_candidate": 0,
                    "ocr_candidate_pages": [],
                },
                "error": None,
            }
            with mock.patch(
                "scripts.inventory_document_corpus.inspect_pdf",
                return_value=fake_pdf,
            ):
                items, report = run_inventory(
                    root=root,
                    workers=2,
                    pdf_timeout=1,
                )
            self.assertEqual(len(items), 2)
            self.assertEqual(report["totals"]["files"], 2)
            self.assertEqual(report["totals"]["distinct_content_objects"], 2)
            self.assertEqual(report["totals"]["pdf_pages"], 2)
            self.assertEqual(report["totals"]["pdf_pages_with_text"], 2)
            self.assertTrue(report["checks"]["all_files_accounted"])
            self.assertTrue(report["checks"]["repo_relative_manifest_paths"])
            self.assertFalse(report["checks"]["s1_100k_reached"])

    def test_size_buckets_are_stable(self) -> None:
        self.assertEqual(_size_bucket(9_999), "lt_10kb")
        self.assertEqual(_size_bucket(10_000), "10kb_to_100kb")
        self.assertEqual(_size_bucket(100_000), "100kb_to_1mb")
        self.assertEqual(_size_bucket(1_000_000), "1mb_to_10mb")
        self.assertEqual(_size_bucket(10_000_000), "gte_10mb")

    def test_pdf_page_counter_preserves_blank_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pages.txt"
            path.write_text("first page\f\fthird page\f", encoding="utf-8")
            self.assertEqual(_count_pdf_page_text(path, 3), [9, 0, 9])


if __name__ == "__main__":
    unittest.main()
