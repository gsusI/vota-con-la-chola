from __future__ import annotations

import gzip
import hashlib
import subprocess
import unittest
from pathlib import Path

from publicdata_docs.extraction import (
    DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
    build_document_text_locators,
    normalize_plain_text,
)
from publicdata_docs.generation_manifest import iter_generation_rows


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "etl/data/raw"
NATIVE_ROOT = REPO_ROOT / "etl/data/derived/real-document-text-corpus-v2"
NATIVE_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
)
INEQUALITY_PDF_SHA256 = (
    "1a709b563421e608f3ee9ac5aaa4bcc68663f32fbf552e06efffa3cdd7c35827"
)


def native_text(row: dict[str, object]) -> str:
    relative = str(row["native_text_cas_path"])
    with gzip.open(NATIVE_ROOT / relative, "rt", encoding="utf-8") as handle:
        return handle.read()


class RealDocumentTextLocatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not NATIVE_MANIFEST.is_file():
            raise unittest.SkipTest("real native document generation is unavailable")
        rows = iter_generation_rows(
            NATIVE_MANIFEST,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            allow_legacy_jsonl=False,
        )
        cls.real_pdf = next(row for row in rows if row["extension"] == "pdf")
        rows = iter_generation_rows(
            NATIVE_MANIFEST,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            allow_legacy_jsonl=False,
        )
        cls.real_markup = next(
            row for row in rows if row["extension"] != "pdf" and row["native_text_chars"]
        )
        rows = iter_generation_rows(
            NATIVE_MANIFEST,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            allow_legacy_jsonl=False,
        )
        cls.inequality_pdf = next(
            row for row in rows if row["content_sha256"] == INEQUALITY_PDF_SHA256
        )

    def test_real_pdf_pages_reconstruct_exact_native_text(self) -> None:
        row = self.real_pdf
        text = native_text(row)
        locators = build_document_text_locators(
            text,
            raw_path=RAW_ROOT / str(row["path"]),
            content_type=str(row["mime_type"]),
            extraction_method=str(row["native_extraction_method"]),
            expected_page_count=int(row["page_count"]),
        )
        self.assertEqual(len(locators), int(row["page_count"]))
        self.assertEqual(
            [item.page_number for item in locators],
            list(range(1, int(row["page_count"]) + 1)),
        )
        for item in locators:
            segment = text[item.text_start_char : item.text_end_char]
            self.assertEqual(len(segment), item.text_chars)
            self.assertEqual(
                hashlib.sha256(segment.encode("utf-8")).hexdigest(),
                item.text_sha256,
            )

    def test_real_markup_spans_are_bounded_and_lossless(self) -> None:
        row = self.real_markup
        text = native_text(row)
        locators = build_document_text_locators(
            text,
            raw_path=RAW_ROOT / str(row["path"]),
            content_type=str(row["mime_type"]),
            extraction_method=str(row["native_extraction_method"]),
            expected_page_count=row["page_count"],
            max_span_chars=4_096,
        )
        self.assertEqual(
            "".join(text[item.text_start_char : item.text_end_char] for item in locators),
            text,
        )
        self.assertTrue(all(0 < item.text_chars <= 4_096 for item in locators))
        self.assertTrue(
            all(item.locator_type == "normalized_text_span" for item in locators)
        )

    def test_real_pdf_plain_normalization_retains_inequality_symbols(self) -> None:
        row = self.inequality_pdf
        completed = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(RAW_ROOT / str(row["path"])), "-"],
            check=True,
            capture_output=True,
        )
        text = normalize_plain_text(
            completed.stdout.decode("utf-8", errors="replace")
        )
        self.assertIn("<50 %", text)
        self.assertIn(">= 75 %", text)
        self.assertEqual(
            row.get("native_extraction_algorithm_version"),
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
