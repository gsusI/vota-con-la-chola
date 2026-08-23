from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

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
        self.assertTrue(all(extraction["checks"].values()))
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(extraction["totals"]["file_instances"], 111_408)
        self.assertEqual(extraction["totals"]["distinct_content_objects"], 109_558)
        self.assertEqual(validation["totals"]["raw_files_checksum_verified"], 111_408)
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

    def test_every_real_native_manifest_row_retains_identity_policy(self) -> None:
        self.require_real_artifacts(NATIVE_MANIFEST)
        rows = 0
        with NATIVE_MANIFEST.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
                rows += 1
                self.assertFalse(item["synthetic_or_mock"])
                self.assertTrue(
                    item["official_public_domain_personal_information_retained"]
                )
                self.assertEqual(item["work_state"], "succeeded")
                self.assertEqual(
                    item["native_extraction_status"], "native_text_extracted"
                )
        self.assertEqual(rows, 111_408)

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
        with OCR_MANIFEST.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
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
            WAYBACK_REPORT, WAYBACK_MANIFEST, WAYBACK_CHECKPOINT
        )
        report = json.loads(WAYBACK_REPORT.read_text(encoding="utf-8"))
        self.assertIn(report["status"], {"ok", "partial"})
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(report["policy"]["public_domain_personal_information_retained"])
        self.assertEqual(report["totals"]["eligible_gap_file_instances"], 26)
        self.assertEqual(report["totals"]["unique_expected_content_targets"], 3)
        self.assertEqual(report["totals"]["unseeded_gap_file_instances"], 25)
        self.assertGreaterEqual(report["totals"]["archive_candidates_indexed"], 5)
        checkpoint_rows = [
            json.loads(line)
            for line in WAYBACK_CHECKPOINT.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(checkpoint_rows), report["checkpoint"]["rows"])
        checkpoint_types = [row["record_type"] for row in checkpoint_rows]
        self.assertEqual(checkpoint_types.count("target"), 3)
        self.assertEqual(checkpoint_types.count("target_path"), 26)
        self.assertGreaterEqual(checkpoint_types.count("archive_candidate"), 5)
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
