from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


class TestValidateAccountabilityArtifacts(unittest.TestCase):
    def test_validator_accepts_consistent_public_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = root / "accountability-ledger-latest.json"
            dossiers = root / "accountability-dossiers-latest.json"
            evidence_api = root / "accountability-evidence-api-latest.json"
            _write(
                ledger,
                {
                    "meta": {
                        "schema_version": "accountability_ledger_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "snapshot_date": "2026-05-10",
                    "coverage": {
                        "issues_total": 1,
                        "entries_total": 2,
                        "actors_total": 2,
                        "entries_with_resolved_actor_id": 2,
                    },
                    "actors": [],
                    "issues": [],
                },
            )
            _write(
                dossiers,
                {
                    "meta": {
                        "schema_version": "accountability_dossier_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "snapshot_date": "2026-05-10",
                    "coverage": {
                        "entries_total": 2,
                        "actors_total": 2,
                        "issues_total": 1,
                        "issue_actor_edges_total": 2,
                        "entries_with_person_id": 1,
                        "entries_with_party_id": 1,
                        "entries_with_parliamentary_group_id": 1,
                    },
                    "actors": [],
                    "issues": [],
                },
            )
            _write(
                evidence_api,
                {
                    "meta": {
                        "schema_version": "accountability_evidence_api_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "snapshot_date": "2026-05-10",
                    "coverage": {
                        "question_templates_total": 5,
                        "actor_answers_total": 2,
                        "issue_answers_total": 1,
                        "actor_issue_refs_total": 2,
                        "issue_clusters_total": 1,
                        "issue_cluster_links_total": 1,
                        "issue_cluster_review_items_total": 1,
                        "issue_cluster_review_status_counts": {"reviewed": 1},
                        "issue_cluster_issue_reviews_applied_total": 1,
                        "issue_cluster_reviewed_links_total": 1,
                        "issue_cluster_assignment_review_needed_total": 1,
                        "issue_cluster_assignment_review_queue_total": 1,
                        "gap_answers_total": 9,
                        "qa_answers_total": 4,
                        "qa_answers_with_self_route_total": 4,
                        "evidence_samples_total": 2,
                        "confidence_level_counts": {"medium": 3},
                        "freshness_level_counts": {"current": 3},
                    },
                    "question_templates": [],
                    "actor_answers": [],
                    "issue_answers": [],
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_accountability_artifacts.py",
                    "--ledger",
                    str(ledger),
                    "--dossiers",
                    str(dossiers),
                    "--evidence-api",
                    str(evidence_api),
                    "--snapshot-date",
                    "2026-05-10",
                    "--min-entries",
                    "2",
                    "--min-actors",
                    "2",
                    "--min-issues",
                    "1",
                    "--min-evidence-api-questions",
                    "5",
                    "--min-evidence-api-issue-clusters",
                    "1",
                    "--min-evidence-api-reviewed-issue-clusters",
                    "1",
                    "--min-evidence-api-issue-cluster-issue-reviews",
                    "1",
                    "--min-evidence-api-issue-cluster-assignment-review-needed",
                    "1",
                    "--min-evidence-api-gap-answers",
                    "9",
                    "--min-evidence-api-qa-answers",
                    "4",
                    "--min-person-id-entries",
                    "1",
                    "--min-party-id-entries",
                    "1",
                    "--min-parliamentary-group-id-entries",
                    "1",
                ],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
                check=True,
            )
            checks = json.loads(result.stdout)
            self.assertEqual(checks["ledger_entries_total"], 2)
            self.assertEqual(checks["dossier_entries_with_party_id"], 1)
            self.assertEqual(checks["evidence_api_question_templates_total"], 5)
            self.assertEqual(checks["evidence_api_issue_clusters_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_links_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_review_items_total"], 1)
            self.assertEqual(checks["evidence_api_reviewed_issue_clusters_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_issue_reviews_applied_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_reviewed_links_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_assignment_review_needed_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_assignment_review_queue_total"], 1)
            self.assertEqual(checks["evidence_api_gap_answers_total"], 9)
            self.assertEqual(checks["evidence_api_qa_answers_total"], 4)
            self.assertEqual(checks["evidence_api_qa_answers_with_self_route_total"], 4)
            self.assertEqual(checks["evidence_api_confidence_levels_total"], 3)
            self.assertEqual(checks["evidence_api_freshness_levels_total"], 3)

    def test_validator_rejects_mismatched_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = root / "accountability-ledger-latest.json"
            dossiers = root / "accountability-dossiers-latest.json"
            _write(
                ledger,
                {
                    "meta": {
                        "schema_version": "accountability_ledger_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "coverage": {
                        "issues_total": 1,
                        "entries_total": 3,
                        "actors_total": 2,
                        "entries_with_resolved_actor_id": 3,
                    },
                },
            )
            _write(
                dossiers,
                {
                    "meta": {
                        "schema_version": "accountability_dossier_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "coverage": {
                        "entries_total": 2,
                        "actors_total": 2,
                        "issues_total": 1,
                        "issue_actor_edges_total": 2,
                    },
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_accountability_artifacts.py",
                    "--ledger",
                    str(ledger),
                    "--dossiers",
                    str(dossiers),
                    "--snapshot-date",
                    "2026-05-10",
                ],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("dossier entries_total does not match ledger", result.stderr)

    def test_validator_rejects_issue_assignment_queue_above_maximum(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = root / "accountability-ledger-latest.json"
            dossiers = root / "accountability-dossiers-latest.json"
            evidence_api = root / "accountability-evidence-api-latest.json"
            _write(
                ledger,
                {
                    "meta": {
                        "schema_version": "accountability_ledger_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "coverage": {
                        "issues_total": 1,
                        "entries_total": 1,
                        "actors_total": 1,
                        "entries_with_resolved_actor_id": 1,
                    },
                },
            )
            _write(
                dossiers,
                {
                    "meta": {
                        "schema_version": "accountability_dossier_snapshot_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "coverage": {
                        "entries_total": 1,
                        "actors_total": 1,
                        "issues_total": 1,
                        "issue_actor_edges_total": 1,
                    },
                },
            )
            _write(
                evidence_api,
                {
                    "meta": {
                        "schema_version": "accountability_evidence_api_v1",
                        "snapshot_date": "2026-05-10",
                    },
                    "coverage": {
                        "actor_answers_total": 1,
                        "issue_answers_total": 1,
                        "issue_clusters_total": 0,
                        "issue_cluster_review_items_total": 0,
                        "issue_cluster_review_status_counts": {},
                        "issue_cluster_assignment_review_needed_total": 1,
                        "issue_cluster_assignment_review_queue_total": 1,
                        "qa_answers_total": 0,
                        "qa_answers_with_self_route_total": 0,
                        "confidence_level_counts": {"medium": 2},
                        "freshness_level_counts": {"current": 2},
                    },
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_accountability_artifacts.py",
                    "--ledger",
                    str(ledger),
                    "--dossiers",
                    str(dossiers),
                    "--evidence-api",
                    str(evidence_api),
                    "--snapshot-date",
                    "2026-05-10",
                    "--max-evidence-api-issue-cluster-assignment-review-needed",
                    "0",
                ],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("evidence_api issue cluster assignment review queue above maximum", result.stderr)


if __name__ == "__main__":
    unittest.main()
