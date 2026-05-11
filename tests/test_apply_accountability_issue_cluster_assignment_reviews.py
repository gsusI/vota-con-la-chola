from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.apply_accountability_issue_cluster_assignment_reviews import (
    merge_reviews,
    read_review_csv,
)


class TestApplyAccountabilityIssueClusterAssignmentReviews(unittest.TestCase):
    def test_reads_review_csv_and_skips_blank_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "reviews.csv"
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "issue_id",
                        "decision",
                        "current_primary_cluster_id",
                        "current_cluster_ids",
                        "reviewed_primary_cluster_id",
                        "reviewed_cluster_ids",
                        "reviewer",
                        "reviewed_at",
                        "rationale",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "issue_id": "issue-1",
                        "decision": "accept_current",
                        "current_primary_cluster_id": "cluster-a",
                        "current_cluster_ids": json.dumps(["cluster-a"]),
                        "reviewer": "Reviewer",
                        "reviewed_at": "2026-05-10",
                        "rationale": "Title clearly matches cluster A.",
                    }
                )
                writer.writerow(
                    {
                        "issue_id": "issue-2",
                        "decision": "",
                        "current_primary_cluster_id": "cluster-b",
                        "current_cluster_ids": json.dumps(["cluster-b"]),
                    }
                )

            reviews, counts, skipped = read_review_csv(path)

            self.assertEqual(counts["input_rows_total"], 2)
            self.assertEqual(counts["applied_rows_total"], 1)
            self.assertEqual(counts["blank_decision_rows_total"], 1)
            self.assertEqual(skipped, [])
            self.assertEqual(reviews[0]["decision"], "set_clusters")
            self.assertEqual(reviews[0]["primary_cluster_id"], "cluster-a")
            self.assertEqual(reviews[0]["cluster_ids"], ["cluster-a"])
            self.assertEqual(reviews[0]["reviewer"], "Reviewer")

    def test_merge_reviews_appends_and_replaces_by_issue_id(self) -> None:
        seed = {
            "meta": {"schema_version": "accountability_issue_cluster_issue_reviews_v1"},
            "cluster_definitions": [],
            "issue_reviews": [
                {
                    "issue_id": "issue-existing",
                    "decision": "set_clusters",
                    "primary_cluster_id": "old-cluster",
                    "cluster_ids": ["old-cluster"],
                }
            ],
        }
        reviews = [
            {
                "issue_id": "issue-existing",
                "decision": "set_clusters",
                "primary_cluster_id": "new-cluster",
                "cluster_ids": ["new-cluster"],
            },
            {
                "issue_id": "issue-new",
                "decision": "set_clusters",
                "primary_cluster_id": "cluster-b",
                "cluster_ids": ["cluster-b"],
            },
        ]

        merged, counts = merge_reviews(seed, reviews)

        self.assertEqual(counts["seed_issue_reviews_before"], 1)
        self.assertEqual(counts["seed_issue_reviews_after"], 2)
        self.assertEqual(counts["seed_issue_reviews_replaced"], 1)
        self.assertEqual(counts["seed_issue_reviews_appended"], 1)
        by_issue = {row["issue_id"]: row for row in merged["issue_reviews"]}
        self.assertEqual(by_issue["issue-existing"]["primary_cluster_id"], "new-cluster")
        self.assertEqual(by_issue["issue-new"]["primary_cluster_id"], "cluster-b")

    def test_cli_writes_seed_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "reviews.csv"
            seed_path = root / "seed.json"
            out_path = root / "seed-out.json"
            report_path = root / "report.json"
            csv_path.write_text(
                "\n".join(
                    [
                        "issue_id,decision,current_primary_cluster_id,current_cluster_ids,reviewer,reviewed_at,rationale",
                        'issue-1,accept_current,cluster-a,"[""cluster-a""]",Dev,2026-05-10,Reviewed title',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            seed_path.write_text(
                json.dumps(
                    {
                        "meta": {"schema_version": "accountability_issue_cluster_issue_reviews_v1"},
                        "cluster_definitions": [],
                        "issue_reviews": [],
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "scripts/apply_accountability_issue_cluster_assignment_reviews.py",
                    "--csv",
                    str(csv_path),
                    "--seed",
                    str(seed_path),
                    "--out",
                    str(out_path),
                    "--report-out",
                    str(report_path),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(json.loads(out_path.read_text())["issue_reviews"][0]["issue_id"], "issue-1")
            report = json.loads(report_path.read_text())
            self.assertEqual(report["coverage"]["applied_rows_total"], 1)
            self.assertEqual(report["coverage"]["seed_issue_reviews_appended"], 1)


if __name__ == "__main__":
    unittest.main()
