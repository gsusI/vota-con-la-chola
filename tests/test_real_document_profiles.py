from __future__ import annotations

import json
import unittest
from pathlib import Path

from publicdata_docs.document_profile import (
    LANGUAGE_MODEL,
    LANGUAGE_MODEL_VERSION,
    PROFILE_ALGORITHM_VERSION,
    profile_document_content,
    safe_child,
)
from publicdata_docs.generation_manifest import (
    iter_generation_rows,
    load_index_bytes,
    sha256_file,
)
from scripts.classify_real_document_profiles import DATASET, REPORT_SCHEMA, ROW_SCHEMA
from scripts.validate_real_document_profiles import VALIDATION_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "etl/data/raw"
NATIVE_ROOT = REPO_ROOT / "etl/data/derived/real-document-text-corpus-v2"
NATIVE_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
)
PROFILE_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-profile-manifest-latest.jsonl"
)
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
PROFILE_REPORT = EVIDENCE_ROOT / "real-document-language-encryption-profile.json"
PROFILE_VALIDATION = EVIDENCE_ROOT / "real-document-language-encryption-validation.json"
PROFILE_LIFECYCLE = EVIDENCE_ROOT / "real-document-profile-generation-audit.json"


class RealDocumentProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not NATIVE_MANIFEST.is_file():
            raise unittest.SkipTest("real native document generation is unavailable")
        cls.real_pdf_row = next(
            row
            for row in iter_generation_rows(
                NATIVE_MANIFEST,
                dataset="native_text",
                row_schema_version="real_document_text_manifest_row_v1",
                allow_legacy_jsonl=False,
            )
            if row["extension"] == "pdf"
        )

    def test_profiles_one_actual_pdf_without_changing_public_text(self) -> None:
        row = self.real_pdf_row
        result = profile_document_content(
            raw_path=safe_child(RAW_ROOT, row["path"]),
            content_sha256=row["content_sha256"],
            extension=row["extension"],
            text_cas_path=safe_child(NATIVE_ROOT, row["native_text_cas_path"]),
            text_sha256=row["native_text_sha256"],
            sample_bytes=65_536,
            min_alpha_chars=200,
            min_confidence=0.80,
            min_margin=0.20,
            pdf_timeout=60.0,
        )
        self.assertEqual(
            result["native_text_sha256_verified"], row["native_text_sha256"]
        )
        self.assertEqual(result["language_model"], LANGUAGE_MODEL)
        self.assertEqual(result["language_model_version"], LANGUAGE_MODEL_VERSION)
        self.assertEqual(result["profile_algorithm_version"], PROFILE_ALGORITHM_VERSION)
        self.assertIn(result["encryption_status"], {"encrypted", "not_encrypted"})
        self.assertIn(
            result["machine_language_status"],
            {
                "candidate_threshold_passed",
                "candidate_below_threshold",
                "insufficient_alphabetic_text",
            },
        )
        self.assertEqual(result["language_review_status"], "unreviewed")
        self.assertIn("machine_language_candidate", result)
        self.assertNotIn("detected_language", result)
        self.assertNotIn("text", result)
        self.assertNotIn("public_name", result)

    def test_full_real_generation_contract_when_materialized(self) -> None:
        required = [
            PROFILE_MANIFEST,
            PROFILE_REPORT,
            PROFILE_VALIDATION,
            PROFILE_LIFECYCLE,
        ]
        if any(not path.is_file() for path in required):
            self.skipTest("full real profile generation has not been materialized")
        source_report = json.loads(PROFILE_REPORT.read_text(encoding="utf-8"))
        validation = json.loads(PROFILE_VALIDATION.read_text(encoding="utf-8"))
        lifecycle = json.loads(PROFILE_LIFECYCLE.read_text(encoding="utf-8"))
        native_index = load_index_bytes(
            NATIVE_MANIFEST.read_bytes(), dataset="native_text"
        )
        index = load_index_bytes(PROFILE_MANIFEST.read_bytes(), dataset=DATASET)
        self.assertEqual(source_report["schema_version"], REPORT_SCHEMA)
        self.assertEqual(source_report["status"], "ok")
        self.assertEqual(PROFILE_ALGORITHM_VERSION, "document_profile_v2")
        self.assertEqual(
            source_report["configuration"]["profile_algorithm_version"],
            PROFILE_ALGORITHM_VERSION,
        )
        totals = source_report["totals"]
        self.assertEqual(totals["file_instances"], native_index["totals"]["rows"])
        self.assertEqual(
            totals["file_instances"],
            totals["distinct_content_objects"] + totals["duplicate_file_instances"],
        )
        self.assertEqual(
            sum(source_report["by_format_file_instances"].values()),
            totals["file_instances"],
        )
        self.assertEqual(source_report["by_format_file_instances"]["xlsx"], 46)
        self.assertEqual(totals["office_format_file_instances"], 46)
        self.assertEqual(
            source_report["by_encryption_status_file_instances"],
            {
                "encrypted": 1,
                "not_applicable_office_archive": 46,
                "not_applicable_plain_markup": 121_170,
                "not_encrypted": 1_436,
            },
        )
        self.assertEqual(
            sum(source_report["by_encryption_status_file_instances"].values()),
            totals["file_instances"],
        )
        self.assertIs(
            source_report["format_coverage"][
                "representative_office_format_cohort_present"
            ],
            False,
        )
        self.assertEqual(
            source_report["format_coverage"][
                "representative_office_format_cohort_reason"
            ],
            "not_established_by_xlsx_only_cohort",
        )
        self.assertIs(
            source_report["format_coverage"]["office_extraction_support_claimed"],
            True,
        )
        self.assertIs(
            source_report["format_coverage"][
                "independent_office_extraction_validation_bound"
            ],
            False,
        )
        self.assertEqual(
            source_report["format_coverage"]["reason"],
            "observed_real_xlsx_cohort_extracted_only",
        )
        self.assertNotIn(
            "validated", source_report["format_coverage"]["reason"]
        )
        self.assertNotIn("validation", source_report["inputs"])
        self.assertTrue(
            source_report["policy"][
                "office_extraction_validation_requires_bound_validation_artifact"
            ]
        )
        self.assertEqual(
            source_report["format_coverage"]["observed_office_extensions"],
            ["xlsx"],
        )
        self.assertEqual(
            source_report["format_coverage"]["supported_office_extensions"],
            ["xlsx"],
        )
        self.assertTrue(all(source_report["checks"].values()))
        self.assertEqual(index["row_schema_version"], ROW_SCHEMA)
        self.assertEqual(index["totals"]["rows"], totals["file_instances"])
        self.assertEqual(
            source_report["inputs"]["native_manifest"]["sha256"],
            sha256_file(NATIVE_MANIFEST),
        )
        self.assertEqual(
            validation["inputs"]["profile_manifest"]["logical_sha256"],
            index["logical_sha256"],
        )
        self.assertEqual(
            validation["inputs"]["native_manifest"]["sha256"],
            sha256_file(NATIVE_MANIFEST),
        )
        self.assertEqual(
            validation["inputs"]["profile_manifest"]["sha256"],
            sha256_file(PROFILE_MANIFEST),
        )
        self.assertEqual(
            validation["inputs"]["profile_report"]["sha256"],
            sha256_file(PROFILE_REPORT),
        )
        self.assertIs(index["policy"]["synthetic_or_mock_records_counted"], False)
        self.assertIs(
            index["policy"]["official_public_domain_personal_information_retained"],
            True,
        )
        self.assertEqual(validation["schema_version"], VALIDATION_SCHEMA)
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(
            validation["configuration"]["profile_algorithm_version"],
            PROFILE_ALGORITHM_VERSION,
        )
        self.assertEqual(validation["configuration"], source_report["configuration"])
        self.assertEqual(
            validation["totals"]["content_objects_rehashed_and_reclassified"],
            totals["distinct_content_objects"],
        )
        self.assertEqual(
            validation["totals"]["profile_file_instances"],
            index["totals"]["rows"],
        )
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(lifecycle["status"], "ok")
        self.assertTrue(all(lifecycle["checks"].values()))


if __name__ == "__main__":
    unittest.main()
