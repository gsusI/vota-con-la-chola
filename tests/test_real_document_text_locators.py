from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from publicdata_docs.extraction import (
    DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
    DOCUMENT_LOCATOR_ALGORITHM_VERSION,
    build_document_text_locators,
    normalize_plain_text,
)
from publicdata_docs.generation_manifest import iter_generation_rows, load_index_bytes
from scripts.locate_real_document_text import DATASET, REPORT_SCHEMA, ROW_SCHEMA
from scripts.validate_real_document_text_locators import VALIDATION_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "etl/data/raw"
NATIVE_ROOT = REPO_ROOT / "etl/data/derived/real-document-text-corpus-v2"
NATIVE_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
)
LOCATOR_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-text-locator-manifest-latest.jsonl"
)
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
LOCATOR_REPORT = EVIDENCE_ROOT / "real-document-text-locator-extraction.json"
LOCATOR_VALIDATION = EVIDENCE_ROOT / "real-document-text-locator-validation.json"
LOCATOR_LIFECYCLE = EVIDENCE_ROOT / "real-document-text-locator-generation-audit.json"
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
            row
            for row in rows
            if row["extension"] != "pdf" and row["native_text_chars"]
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

    def test_real_markup_sections_are_structural_bounded_and_lossless(self) -> None:
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
            "".join(
                text[item.text_start_char : item.text_end_char] for item in locators
            ),
            text,
        )
        self.assertTrue(all(0 < item.text_chars <= 4_096 for item in locators))
        self.assertTrue(all(item.locator_type == "markup_section" for item in locators))
        self.assertTrue(
            all(item.locator_value.startswith("xpath:/") for item in locators)
        )
        self.assertEqual(
            DOCUMENT_LOCATOR_ALGORITHM_VERSION,
            "document_text_locator_v3_major_markup_sections",
        )
        with self.assertRaisesRegex(ValueError, "fanout exceeds"):
            build_document_text_locators(
                text,
                raw_path=RAW_ROOT / str(row["path"]),
                content_type=str(row["mime_type"]),
                extraction_method=str(row["native_extraction_method"]),
                expected_page_count=row["page_count"],
                max_span_chars=4_096,
                max_locators_per_content=max(1, len(locators) - 1),
            )

    def test_real_markup_uses_exact_span_fallback_above_parse_budget(self) -> None:
        row = self.real_markup
        text = native_text(row)
        locators = build_document_text_locators(
            text,
            raw_path=RAW_ROOT / str(row["path"]),
            content_type=str(row["mime_type"]),
            extraction_method=str(row["native_extraction_method"]),
            expected_page_count=row["page_count"],
            max_span_chars=4_096,
            max_semantic_markup_bytes=1,
        )
        self.assertEqual(
            "".join(
                text[item.text_start_char : item.text_end_char] for item in locators
            ),
            text,
        )
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
        text = normalize_plain_text(completed.stdout.decode("utf-8", errors="replace"))
        self.assertIn("<50 %", text)
        self.assertIn(">= 75 %", text)
        self.assertEqual(
            row.get("native_extraction_algorithm_version"),
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        )

    def test_full_real_locator_generation_contract_when_materialized(self) -> None:
        required = [
            LOCATOR_MANIFEST,
            LOCATOR_REPORT,
            LOCATOR_VALIDATION,
            LOCATOR_LIFECYCLE,
        ]
        if any(not path.is_file() for path in required):
            self.skipTest("full real locator generation has not been materialized")
        source_report = json.loads(LOCATOR_REPORT.read_text(encoding="utf-8"))
        validation = json.loads(LOCATOR_VALIDATION.read_text(encoding="utf-8"))
        lifecycle = json.loads(LOCATOR_LIFECYCLE.read_text(encoding="utf-8"))
        index = load_index_bytes(LOCATOR_MANIFEST.read_bytes(), dataset=DATASET)
        self.assertEqual(source_report["schema_version"], REPORT_SCHEMA)
        self.assertEqual(source_report["status"], "ok")
        self.assertEqual(
            source_report["configuration"]["locator_algorithm_version"],
            DOCUMENT_LOCATOR_ALGORITHM_VERSION,
        )
        self.assertEqual(source_report["totals"]["file_instances"], 122_607)
        self.assertEqual(source_report["totals"]["content_locator_rows"], 818_781)
        self.assertEqual(source_report["totals"]["instance_locator_rows"], 879_104)
        self.assertEqual(source_report["totals"]["pdf_page_locators"], 30_634)
        self.assertEqual(source_report["totals"]["markup_section_locators"], 782_814)
        self.assertEqual(
            source_report["totals"]["normalized_text_span_locators"], 5_333
        )
        self.assertEqual(
            source_report["totals"]["semantic_markup_content_objects"], 119_473
        )
        self.assertEqual(
            source_report["totals"]["fallback_markup_content_objects"], 322
        )
        self.assertEqual(
            source_report["totals"][
                "projected_content_locator_rows_at_one_million_documents"
            ],
            6_780_402,
        )
        self.assertLessEqual(
            source_report["totals"]["average_locator_rows_per_content"], 10
        )
        self.assertLessEqual(
            source_report["totals"]["max_locator_rows_per_content"], 2_000
        )
        self.assertTrue(all(source_report["checks"].values()))
        self.assertEqual(index["row_schema_version"], ROW_SCHEMA)
        self.assertEqual(index["totals"]["rows"], 879_104)
        self.assertEqual(validation["schema_version"], VALIDATION_SCHEMA)
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["totals"]["mismatched_rows"], 0)
        self.assertEqual(validation["totals"]["validation_failures"], 0)
        self.assertEqual(lifecycle["status"], "ok")
        self.assertTrue(all(lifecycle["checks"].values()))


if __name__ == "__main__":
    unittest.main()
