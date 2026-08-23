from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from scripts.prepare_boe_candidate_correction_review_queue import (
    FIELDNAMES,
    REVIEW_FIELDS,
    task_fingerprint,
    validate_reviews,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE = (
    REPO_ROOT
    / "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports"
    / "boe-candidate-correction-review-queue.csv"
)
CONTEXT = (
    REPO_ROOT
    / "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports"
    / "boe-candidate-correction-review-context.jsonl"
)
REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
    / "boe-candidate-correction-review-queue.json"
)


class BoeCandidateCorrectionReviewQueueTests(unittest.TestCase):
    def require_real_artifacts(self) -> None:
        if not all(path.is_file() for path in (QUEUE, CONTEXT, REPORT)):
            self.skipTest("real BOE correction review artifacts are excluded here")

    def test_queue_retains_every_pending_real_paragraph_without_decisions(
        self,
    ) -> None:
        self.require_real_artifacts()
        with QUEUE.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames or ()), FIELDNAMES)
            tasks = list(reader)
        self.assertEqual(len(tasks), 776)
        self.assertEqual(
            {task["correction_document_id"] for task in tasks},
            {
                "BOE-A-2015-13053",
                "BOE-A-2015-13247",
                "BOE-A-2015-13868",
                "BOE-A-2016-5626",
                "BOE-A-2019-4948",
                "BOE-A-2019-5083",
                "BOE-A-2019-5322",
                "BOE-A-2019-6984",
            },
        )
        self.assertTrue(
            all(task["source_url"].startswith("https://www.boe.es/") for task in tasks)
        )
        self.assertTrue(all(task["source_text_exact"] for task in tasks))
        self.assertTrue(
            all(task["task_fingerprint"] == task_fingerprint(task) for task in tasks)
        )
        self.assertTrue(
            all(not task[field] for task in tasks for field in REVIEW_FIELDS)
        )
        self.assertEqual(validate_reviews(tasks), {"pending_dual_review": 776})

    def test_context_retains_all_pending_public_candidate_rows_once(self) -> None:
        self.require_real_artifacts()
        context_rows = [
            json.loads(line)
            for line in CONTEXT.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(context_rows), 3_713)
        occurrences = [
            occurrence
            for row in context_rows
            for occurrence in row["candidate_occurrences"]
        ]
        self.assertEqual(len(occurrences), 31_241)
        self.assertEqual(
            len({occurrence["candidate_occurrence_id"] for occurrence in occurrences}),
            31_241,
        )
        self.assertTrue(all(occurrence["full_name"] for occurrence in occurrences))
        self.assertTrue(
            all(occurrence["source_text_exact"] for occurrence in occurrences)
        )

        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pending_human_review")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["totals"]["pending_correction_documents"], 8)
        self.assertEqual(report["totals"]["pending_correction_paragraphs"], 776)
        self.assertEqual(report["totals"]["pending_dual_review"], 776)
        self.assertEqual(report["totals"]["context_candidacies"], 3_713)
        self.assertEqual(report["totals"]["context_candidate_occurrences"], 31_241)
        self.assertTrue(report["policy"]["public_domain_personal_information_retained"])
        self.assertFalse(report["policy"]["machine_decisions_invented"])
        self.assertFalse(report["policy"]["effective_state_mutated"])


if __name__ == "__main__":
    unittest.main()
