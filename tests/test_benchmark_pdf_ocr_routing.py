from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_pdf_ocr_routing import (
    build_report,
    load_candidates,
    select_diverse_candidates,
)


class TestBenchmarkPdfOcrRouting(unittest.TestCase):
    def test_candidate_loading_and_selection_spreads_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.jsonl"
            rows = [
                {
                    "path": "a.pdf",
                    "sha256": "a" * 64,
                    "page_text_quality": {
                        "ocr_candidate_pages": [
                            {"page_number": 1, "reason": "empty_text", "source_text_chars": 0},
                            {"page_number": 2, "reason": "sparse_text", "source_text_chars": 10},
                        ]
                    },
                },
                {
                    "path": "b.pdf",
                    "sha256": "b" * 64,
                    "page_text_quality": {
                        "ocr_candidate_pages": [
                            {"page_number": 3, "reason": "sparse_text", "source_text_chars": 20}
                        ]
                    },
                },
            ]
            manifest.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            candidates = load_candidates(manifest)
            selected = select_diverse_candidates(candidates, 3)
            self.assertEqual(len(candidates), 3)
            self.assertEqual(selected[0]["reason"], "empty_text")
            self.assertEqual({row["path"] for row in selected}, {"a.pdf", "b.pdf"})

    def test_report_keeps_ocr_as_benchmark_not_promotion(self) -> None:
        candidate = {
            "path": "a.pdf",
            "page_number": 1,
            "reason": "empty_text",
            "source_text_chars": 0,
        }
        result = {
            **candidate,
            "status": "ok",
            "ocr_text_chars": 100,
            "improved_over_embedded_text": True,
            "elapsed_seconds": 0.5,
        }
        report = build_report(
            candidates=[candidate],
            selected=[candidate],
            results=[result],
            manifest_path=Path("manifest.jsonl"),
            dpi=200,
            language="spa",
            tool_versions={"pdftoppm": "x", "tesseract": "y"},
        )
        self.assertEqual(report["ocr"]["improved_over_embedded_text"], 1)
        self.assertIn("not full OCR", report["limitations"][0])


if __name__ == "__main__":
    unittest.main()
