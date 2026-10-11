from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path

from publicdata_docs.extraction import DOCUMENT_EXTRACTION_ALGORITHM_VERSION
from publicdata_docs.generation_manifest import iter_generation_rows, sha256_file
from scripts.extract_real_document_corpus import (
    CorpusExtractionError,
    EXTRACTION_STATE_CONFIGURATION_SCHEMA,
    apply_state_schema,
    canonical_configuration_json,
    configuration_sha256,
    seed_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
NATIVE_REPORT = EVIDENCE_ROOT / "real-document-text-extraction.json"
NATIVE_VALIDATION = EVIDENCE_ROOT / "real-document-text-validation.json"
OCR_REPORT = EVIDENCE_ROOT / "real-document-page-ocr.json"
OCR_VALIDATION = EVIDENCE_ROOT / "real-document-page-ocr-validation.json"
OCR_REVIEW_REPORT = EVIDENCE_ROOT / "real-document-page-ocr-human-review-queue.json"
OCR_REVIEW_VALIDATION = (
    EVIDENCE_ROOT / "real-document-page-ocr-human-review-validation.json"
)
OCR_REVIEW_QUEUE = (
    REPO_ROOT
    / "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports"
    / "real-document-page-ocr-human-review.csv"
)
WAYBACK_REPORT = EVIDENCE_ROOT / "wayback-document-lineage.json"
WAYBACK_MANIFEST = EVIDENCE_ROOT / "wayback-document-lineage.jsonl"
WAYBACK_CHECKPOINT = EVIDENCE_ROOT / "wayback-document-checkpoint.jsonl"
NATIVE_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
)
INVENTORY_MANIFEST = (
    REPO_ROOT / "etl/data/manifests/real-document-format-inventory.jsonl"
)
PROVENANCE_MANIFEST = (
    REPO_ROOT / "etl/data/manifests/real-document-provenance-files.jsonl"
)
RAW_ROOT = REPO_ROOT / "etl/data/raw"
PROVENANCE_REPORT = EVIDENCE_ROOT / "real-document-provenance-audit.json"
OCR_MANIFEST = (
    REPO_ROOT / "etl/data/published/real-document-page-ocr-manifest-latest.jsonl"
)


class RealDocumentCorpusProcessingTests(unittest.TestCase):
    def require_real_artifacts(self, *paths: Path) -> None:
        if not all(path.is_file() for path in paths):
            self.skipTest(
                "real full-corpus artifacts are excluded from this test context"
            )

    def test_native_extraction_and_independent_validation_cover_real_corpus(
        self,
    ) -> None:
        self.require_real_artifacts(NATIVE_REPORT, NATIVE_VALIDATION, NATIVE_MANIFEST)
        extraction = json.loads(NATIVE_REPORT.read_text(encoding="utf-8"))
        validation = json.loads(NATIVE_VALIDATION.read_text(encoding="utf-8"))
        self.assertEqual(extraction["status"], "ok")
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(
            extraction["extraction_algorithm_version"],
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        )
        self.assertEqual(
            validation["extraction_algorithm_version"],
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        )
        self.assertTrue(all(extraction["checks"].values()))
        self.assertTrue(all(validation["checks"].values()))
        extraction_totals = extraction["totals"]
        validation_totals = validation["totals"]
        self.assertGreaterEqual(extraction_totals["file_instances"], 100_000)
        self.assertEqual(
            extraction_totals["file_instances"], validation_totals["file_instances"]
        )
        self.assertEqual(
            extraction_totals["distinct_content_objects"],
            validation_totals["distinct_content_objects"],
        )
        self.assertEqual(
            validation_totals["raw_files_checksum_verified"],
            extraction_totals["file_instances"],
        )
        self.assertEqual(extraction["totals"]["native_truncated_objects"], 0)
        self.assertEqual(validation["totals"]["native_truncated_objects"], 0)
        self.assertEqual(
            extraction["totals"]["native_text_chars"],
            validation["totals"]["native_text_chars"],
        )
        self.assertEqual(
            extraction["totals"]["text_cas_files"],
            validation["totals"]["text_cas_files_observed"],
        )
        self.assertFalse(extraction["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(
            extraction["policy"]["official_public_domain_personal_information_retained"]
        )
        self.assertTrue(
            extraction["policy"]["xlsx_observed_public_cell_values_retained"]
        )
        self.assertTrue(
            extraction["policy"]["xlsx_public_phonetic_annotations_retained"]
        )
        self.assertTrue(
            extraction["policy"][
                "xlsx_formula_extraction_implemented_but_not_observed_in_real_cohort"
            ]
        )
        self.assertNotIn(
            "xlsx_public_cell_values_and_formulas_retained", extraction["policy"]
        )
        self.assertEqual(
            validation["validation_scope"]["xlsx_raw_to_cas_validator"],
            "openpyxl_semantic_plus_independent_openxml_phonetic_replay_v2",
        )
        self.assertEqual(validation["validation_scope"]["xlsx_raw_to_cas_workers"], 2)
        self.assertEqual(
            validation["validation_scope"]["xlsx_raw_to_cas_fetch_batch_rows"], 4
        )
        self.assertEqual(
            validation["validation_scope"]["xlsx_raw_to_cas_max_in_flight"], 4
        )
        self.assertTrue(
            validation["validation_scope"]["xlsx_raw_to_cas_validator_version"]
        )
        self.assertEqual(
            validation["policy"]["xlsx_formula_validation_status"],
            "not_observed_in_real_cohort",
        )
        self.assertGreater(validation_totals["xlsx_file_instances"], 0)
        self.assertEqual(
            validation_totals["xlsx_distinct_content_objects_raw_to_cas_replayed"],
            validation_totals["xlsx_distinct_content_objects"],
        )
        self.assertGreater(
            validation_totals["xlsx_nonempty_rows_raw_to_cas_replayed"], 0
        )
        self.assertGreater(
            validation_totals["xlsx_nonempty_cells_raw_to_cas_replayed"], 0
        )
        self.assertEqual(
            validation_totals["xlsx_formula_cells_observed_in_real_cohort"], 0
        )
        self.assertEqual(
            validation_totals[
                "xlsx_phonetic_annotations_raw_to_cas_replayed"
            ],
            validation_totals[
                "xlsx_phonetic_annotations_observed_in_real_cohort"
            ],
        )
        manifest = extraction["manifest"]
        self.assertEqual(
            manifest["path"], NATIVE_MANIFEST.relative_to(REPO_ROOT).as_posix()
        )
        self.assertEqual(manifest["rows"], extraction_totals["file_instances"])
        self.assertEqual(manifest["bytes"], NATIVE_MANIFEST.stat().st_size)
        self.assertEqual(manifest["sha256"], sha256_file(NATIVE_MANIFEST))
        self.assertEqual(validation["inputs"]["manifest"]["rows"], manifest["rows"])
        self.assertEqual(
            validation["inputs"]["manifest"]["sha256"], manifest["sha256"]
        )
        configuration = extraction["effective_configuration"]
        canonical = canonical_configuration_json(configuration)
        self.assertEqual(
            extraction["effective_configuration_sha256"],
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            extraction["effective_configuration_sha256"],
            configuration_sha256(canonical),
        )
        self.assertEqual(
            configuration["extraction_algorithm_version"],
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        )
        self.assertEqual(
            configuration["schema_version"],
            EXTRACTION_STATE_CONFIGURATION_SCHEMA,
        )
        self.assertGreater(configuration["max_input_bytes"], 0)
        self.assertGreater(configuration["max_text_chars"], 0)
        self.assertTrue(
            extraction["checks"][
                "effective_configuration_bound_before_state_reuse"
            ]
        )

    def test_real_state_reuse_rejects_semantic_limit_corruption(self) -> None:
        self.require_real_artifacts(
            NATIVE_REPORT,
            INVENTORY_MANIFEST,
            PROVENANCE_MANIFEST,
        )
        extraction = json.loads(NATIVE_REPORT.read_text(encoding="utf-8"))
        configuration = extraction.get("effective_configuration")
        state_ref = extraction.get("state", {}).get("database")
        if not isinstance(configuration, dict) or not state_ref:
            self.skipTest("real extraction predates effective configuration binding")
        state_db = REPO_ROOT / str(state_ref)
        if not state_db.is_file():
            self.skipTest("real extraction state database is unavailable")
        with sqlite3.connect(state_db) as source:
            metadata = source.execute(
                "SELECT key, value FROM extraction_metadata"
            ).fetchall()
        with sqlite3.connect(":memory:") as corrupted:
            corrupted.row_factory = sqlite3.Row
            apply_state_schema(corrupted)
            corrupted.executemany(
                "INSERT INTO extraction_metadata (key, value) VALUES (?, ?)",
                metadata,
            )
            with self.assertRaisesRegex(
                CorpusExtractionError, "different inputs/effective configuration"
            ):
                seed_state(
                    corrupted,
                    raw_root=RAW_ROOT,
                    inventory_path=INVENTORY_MANIFEST,
                    provenance_path=PROVENANCE_MANIFEST,
                    max_attempts=int(configuration["max_attempts"]),
                    max_input_bytes=int(configuration["max_input_bytes"]),
                    max_text_chars=int(configuration["max_text_chars"]) + 1,
                )

    def test_every_real_native_manifest_row_retains_identity_policy(self) -> None:
        self.require_real_artifacts(NATIVE_REPORT, NATIVE_MANIFEST)
        extraction = json.loads(NATIVE_REPORT.read_text(encoding="utf-8"))
        rows = 0
        for item in iter_generation_rows(
            NATIVE_MANIFEST,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
        ):
            rows += 1
            self.assertFalse(item["synthetic_or_mock"])
            self.assertTrue(
                item["official_public_domain_personal_information_retained"]
            )
            self.assertEqual(item["work_state"], "succeeded")
            self.assertIn(
                item["native_extraction_status"],
                {"native_text_extracted", "native_no_text"},
            )
            if item["native_extraction_status"] == "native_no_text":
                self.assertIsNone(item["native_text_sha256"])
                self.assertIsNone(item["native_text_cas_path"])
                self.assertEqual(item["native_text_chars"], 0)
        self.assertEqual(rows, extraction["totals"]["file_instances"])

    def test_page_ocr_and_independent_validation_cover_every_real_candidate(
        self,
    ) -> None:
        self.require_real_artifacts(OCR_REPORT, OCR_VALIDATION, OCR_MANIFEST)
        ocr = json.loads(OCR_REPORT.read_text(encoding="utf-8"))
        validation = json.loads(OCR_VALIDATION.read_text(encoding="utf-8"))
        self.assertEqual(ocr["status"], "ok")
        self.assertEqual(validation["status"], "ok")
        self.assertTrue(all(ocr["checks"].values()))
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(ocr["totals"]["candidate_pages"], 856)
        self.assertEqual(ocr["totals"]["documents"], 58)
        self.assertEqual(
            ocr["totals"]["empty_text_pages"] + ocr["totals"]["sparse_text_pages"],
            856,
        )
        self.assertFalse(ocr["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(
            ocr["policy"]["official_public_domain_personal_information_retained"]
        )

    def test_every_real_ocr_manifest_row_is_additive(self) -> None:
        self.require_real_artifacts(OCR_MANIFEST)
        rows = 0
        for item in iter_generation_rows(
            OCR_MANIFEST,
            dataset="page_ocr",
            row_schema_version="real_document_page_ocr_manifest_row_v1",
        ):
            rows += 1
            self.assertFalse(item["synthetic_or_mock"])
            self.assertTrue(item["additive_to_native_text"])
            self.assertTrue(
                item["official_public_domain_personal_information_retained"]
            )
            self.assertEqual(item["work_state"], "succeeded")
            self.assertIn(item["ocr_status"], {"ocr_text_extracted", "ocr_no_text"})
        self.assertEqual(rows, 856)

    def test_human_review_queue_contains_only_unlabeled_real_pages(self) -> None:
        self.require_real_artifacts(OCR_REVIEW_REPORT, OCR_REVIEW_QUEUE)
        report = json.loads(OCR_REVIEW_REPORT.read_text(encoding="utf-8"))
        with OCR_REVIEW_QUEUE.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(report["status"], "ready_for_human_review")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(len(rows), 40)
        self.assertEqual(report["review"]["human_reviews_completed"], 0)
        self.assertEqual(report["review"]["human_reviews_pending"], 40)
        self.assertFalse(report["review"]["promotion_ready"])
        for row in rows:
            self.assertTrue(row["document_sha256"])
            self.assertTrue(row["document_path"])
            self.assertTrue(row["source_group"])
            self.assertTrue(row["page_number"])
            self.assertEqual(row["review_decision"], "")
            self.assertEqual(row["review_notes"], "")
            self.assertEqual(row["reviewer_id"], "")
            self.assertEqual(row["reviewed_at"], "")

    def test_human_review_validation_keeps_pending_work_explicit(self) -> None:
        self.require_real_artifacts(
            OCR_REVIEW_REPORT, OCR_REVIEW_QUEUE, OCR_REVIEW_VALIDATION
        )
        queue_report = json.loads(OCR_REVIEW_REPORT.read_text(encoding="utf-8"))
        validation = json.loads(OCR_REVIEW_VALIDATION.read_text(encoding="utf-8"))
        self.assertEqual(validation["status"], "pending_human_review")
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(validation["totals"]["review_rows"], 40)
        self.assertEqual(validation["totals"]["human_reviews_completed"], 0)
        self.assertEqual(validation["totals"]["human_reviews_pending"], 40)
        self.assertFalse(validation["gates"]["batch_complete"])
        self.assertFalse(validation["gates"]["promotion_ready"])
        self.assertEqual(
            validation["inputs"]["review_csv"]["assignment_sha256"],
            queue_report["queue"]["assignment_sha256"],
        )

    def test_wayback_recovery_rejects_every_nonmatching_real_capture(self) -> None:
        self.require_real_artifacts(
            WAYBACK_REPORT,
            WAYBACK_MANIFEST,
            WAYBACK_CHECKPOINT,
            PROVENANCE_REPORT,
        )
        report = json.loads(WAYBACK_REPORT.read_text(encoding="utf-8"))
        provenance = json.loads(PROVENANCE_REPORT.read_text(encoding="utf-8"))
        self.assertIn(report["status"], {"ok", "partial"})
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(report["policy"]["public_domain_personal_information_retained"])
        self.assertGreater(report["totals"]["eligible_gap_file_instances"], 0)
        self.assertGreater(report["totals"]["unique_expected_content_targets"], 0)
        self.assertEqual(
            report["totals"]["eligible_gap_file_instances"]
            + report["totals"]["unseeded_gap_file_instances"],
            provenance["totals"]["unlinked"],
        )
        self.assertTrue(report["execution"]["no_network"])
        self.assertEqual(report["execution"]["network_requests_performed"], 0)
        self.assertGreaterEqual(report["totals"]["archive_candidates_indexed"], 5)
        checkpoint_rows = [
            json.loads(line)
            for line in WAYBACK_CHECKPOINT.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(checkpoint_rows), report["checkpoint"]["rows"])
        checkpoint_types = [row["record_type"] for row in checkpoint_rows]
        self.assertEqual(
            checkpoint_types.count("target"),
            report["totals"]["unique_expected_content_targets"],
        )
        self.assertEqual(
            checkpoint_types.count("target_path"),
            report["totals"]["eligible_gap_file_instances"],
        )
        self.assertEqual(
            checkpoint_types.count("archive_candidate"),
            report["totals"]["archive_candidates_indexed"],
        )
        for row in checkpoint_rows:
            self.assertEqual(row["schema_version"], "wayback_document_checkpoint_v1")
            self.assertFalse(row["synthetic_or_mock_records_counted"])
            self.assertTrue(row["public_domain_personal_information_retained"])
            self.assertFalse(row["remote_mutation_performed"])
        manifest_rows = [
            json.loads(line)
            for line in WAYBACK_MANIFEST.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(
            len(manifest_rows), report["totals"]["exact_archive_relations"]
        )
        for row in manifest_rows:
            self.assertEqual(
                row["capture"]["sha256"],
                row["archive_evidence"]["downloaded_sha256"],
            )
            self.assertEqual(
                row["capture"]["bytes"],
                row["archive_evidence"]["downloaded_bytes"],
            )
            self.assertFalse(row["synthetic_or_mock_records_counted"])
            self.assertTrue(row["public_domain_personal_information_retained"])


if __name__ == "__main__":
    unittest.main()
