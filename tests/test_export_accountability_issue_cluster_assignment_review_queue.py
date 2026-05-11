from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_accountability_issue_cluster_assignment_review_queue import (
    build_issue_cluster_assignment_review_queue,
    write_csv,
)


class TestExportAccountabilityIssueClusterAssignmentReviewQueue(unittest.TestCase):
    def test_builds_priority_review_rows_from_evidence_api_queue(self) -> None:
        payload = {
            "meta": {"schema_version": "accountability_evidence_api_v1", "snapshot_date": "2026-02-12"},
            "coverage": {
                "issue_answers_total": 2,
                "issue_clusters_total": 1,
                "issue_cluster_issue_reviews_applied_total": 1,
                "issue_cluster_assignment_review_needed_total": 2,
            },
            "issue_cluster_assignment_review_queue": [
                {
                    "review_id": "issue-cluster-assignment-review:low",
                    "issue_id": "low",
                    "answer_id": "issue:low",
                    "label": "Low volume issue",
                    "review_status": "needs_review",
                    "primary_cluster_id": "cluster-a",
                    "cluster_ids": ["cluster-a"],
                    "current_matches": [
                        {
                            "cluster_id": "cluster-a",
                            "label": "Cluster A",
                            "method": "label_keyword_v1",
                            "matched_keywords": ["low"],
                        }
                    ],
                    "coverage": {"entries_total": 10, "actors_total": 2, "first_date": "2026-01-01"},
                    "routes": {"dossier": "/accountability-dossiers/issues/low/"},
                },
                {
                    "review_id": "issue-cluster-assignment-review:high",
                    "issue_id": "high",
                    "answer_id": "issue:high",
                    "label": "High volume issue",
                    "review_status": "needs_review",
                    "primary_cluster_id": "cluster-b",
                    "cluster_ids": ["cluster-b"],
                    "current_matches": [
                        {
                            "cluster_id": "cluster-b",
                            "label": "Cluster B",
                            "method": "label_keyword_v1",
                            "matched_keywords": ["high"],
                        }
                    ],
                    "coverage": {"entries_total": 10000, "actors_total": 8, "first_date": "2026-01-02"},
                    "routes": {"dossier": "/accountability-dossiers/issues/high/"},
                },
            ],
        }

        queue = build_issue_cluster_assignment_review_queue(payload, limit=1)

        self.assertEqual(queue["meta"]["schema_version"], "accountability_issue_cluster_assignment_review_queue_v1")
        self.assertEqual(queue["coverage"]["pending_issue_assignments_total"], 2)
        self.assertEqual(queue["coverage"]["source_queue_rows_total"], 2)
        self.assertEqual(queue["coverage"]["queue_rows_total"], 1)
        self.assertTrue(queue["coverage"]["queue_truncated"])
        self.assertEqual(queue["queue"][0]["issue_id"], "high")
        self.assertEqual(queue["queue"][0]["priority"], 100)
        self.assertEqual(queue["queue"][0]["decision_template"]["primary_cluster_id"], "cluster-b")
        self.assertIn("accept_current", queue["queue"][0]["allowed_decisions"])

    def test_write_csv_outputs_review_columns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "queue.csv"
            write_csv(
                out,
                [
                    {
                        "priority": 100,
                        "review_id": "review-1",
                        "issue_id": "issue-1",
                        "issue_label": "Issue 1",
                        "entries_total": 5,
                        "actors_total": 2,
                        "first_date": "2026-01-01",
                        "last_date": "2026-01-02",
                        "current_primary_cluster_id": "cluster-a",
                        "current_cluster_ids": ["cluster-a"],
                        "current_matches": [{"cluster_id": "cluster-a"}],
                        "route": "/accountability-dossiers/issues/issue-1/",
                        "decision_template": {
                            "primary_cluster_id": "cluster-a",
                            "cluster_ids": ["cluster-a"],
                        },
                        "next_action": "copy_decision_template_to_accountability_issue_cluster_issue_reviews_seed_v1",
                    }
                ],
            )

            with out.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["review_id"], "review-1")
            self.assertEqual(rows[0]["reviewed_primary_cluster_id"], "cluster-a")
            self.assertEqual(json.loads(rows[0]["reviewed_cluster_ids"]), ["cluster-a"])
            self.assertIn("decision", rows[0])

    def test_cli_writes_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence_api = root / "evidence-api.json"
            out = root / "queue.json"
            csv_out = root / "queue.csv"
            evidence_api.write_text(
                json.dumps(
                    {
                        "meta": {
                            "schema_version": "accountability_evidence_api_v1",
                            "snapshot_date": "2026-02-12",
                        },
                        "coverage": {
                            "issue_answers_total": 1,
                            "issue_clusters_total": 1,
                            "issue_cluster_assignment_review_needed_total": 0,
                        },
                        "issue_cluster_assignment_review_queue": [],
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_issue_cluster_assignment_review_queue.py",
                    "--evidence-api",
                    str(evidence_api),
                    "--out",
                    str(out),
                    "--csv-out",
                    str(csv_out),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(out.exists())
            self.assertTrue(csv_out.exists())
            self.assertEqual(json.loads(out.read_text())["coverage"]["queue_rows_total"], 0)


if __name__ == "__main__":
    unittest.main()
