from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_accountability_evidence_api_snapshot import build_evidence_api


class TestExportAccountabilityEvidenceApiSnapshot(unittest.TestCase):
    def test_build_evidence_api_from_dossiers_and_ledger(self) -> None:
        dossiers = {
            "meta": {"schema_version": "accountability_dossier_snapshot_v1"},
            "coverage": {"entries_total": 3, "actors_total": 1, "issues_total": 1},
            "actors": [
                {
                    "actor_key": "party_id:1",
                    "actor_label": "Partido A",
                    "actor_kind": "party",
                    "party_id": 1,
                    "entries_total": 2,
                    "issues_total": 1,
                    "roles": {"voted_for": 2},
                    "entry_kinds": {"parliamentary_action": 2},
                    "first_date": "2026-01-01",
                    "last_date": "2026-01-01",
                    "top_issues": [
                        {
                            "issue_id": "issue-1",
                            "issue_label": "Proyecto de Ley de Presupuestos Generales del Estado",
                            "entries_total": 2,
                            "roles": {"voted_for": 2},
                            "entry_kinds": {"parliamentary_action": 2},
                            "first_date": "2026-01-01",
                            "last_date": "2026-01-01",
                        }
                    ],
                }
            ],
            "issues": [
                {
                    "issue_id": "issue-1",
                    "label": "Proyecto de Ley de Presupuestos Generales del Estado",
                    "entries_total": 3,
                    "actors_total": 1,
                    "roles": {"voted_for": 2, "approved": 1},
                    "entry_kinds": {"parliamentary_action": 2, "rule": 1},
                    "actor_kinds": {"party": 2, "institution": 1},
                    "first_date": "2026-01-01",
                    "last_date": "2026-01-01",
                    "top_actors": [
                        {
                            "actor_key": "party_id:1",
                            "actor_label": "Partido A",
                            "actor_kind": "party",
                            "entries_total": 2,
                            "roles": {"voted_for": 2},
                        }
                    ],
                }
            ],
        }
        ledger = {
            "meta": {"schema_version": "accountability_ledger_snapshot_v1"},
            "actors": [
                {
                    "actor_key": "party_id:1",
                    "sample_entries": [
                        {
                            "entry_id": "entry-1",
                            "issue_id": "issue-1",
                            "issue_label": "Proyecto de Ley de Presupuestos Generales del Estado",
                            "actor_label": "Partido A",
                            "actor_kind": "party",
                            "entry_kind": "parliamentary_action",
                            "accountability_role": "voted_for",
                            "event_date": "2026-01-01",
                            "evidence_tier": 1,
                            "source_title": "Official vote",
                            "source_url": "https://example.test/vote",
                            "source_locator": "vote-1",
                            "evidence_quote": "SI",
                            "summary": "Partido A voted yes.",
                        }
                    ],
                }
            ],
            "issues": [
                {
                    "issue_id": "issue-1",
                    "entries": [
                        {
                            "entry_id": "entry-2",
                            "actor_label": "Partido A",
                            "actor_kind": "party",
                            "entry_kind": "parliamentary_action",
                            "accountability_role": "voted_for",
                            "event_date": "2026-01-01",
                            "evidence_tier": 1,
                        }
                    ],
                }
            ],
        }

        payload = build_evidence_api(dossiers, ledger, snapshot_date="2026-02-12")

        self.assertEqual(payload["meta"]["schema_version"], "accountability_evidence_api_v1")
        self.assertEqual(payload["coverage"]["question_templates_total"], 5)
        self.assertEqual(payload["coverage"]["actor_answers_total"], 1)
        self.assertEqual(payload["coverage"]["issue_answers_total"], 1)
        self.assertEqual(payload["coverage"]["actor_issue_refs_total"], 1)
        self.assertEqual(payload["coverage"]["issue_clusters_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_links_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_review_items_total"], 1)
        self.assertEqual(payload["coverage"]["fallback_issue_cluster_answers_total"], 0)
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_needed_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_queue_total"], 1)
        self.assertEqual(payload["coverage"]["gap_answers_total"], 9)
        self.assertGreaterEqual(payload["coverage"]["qa_answers_total"], 4)
        self.assertEqual(payload["coverage"]["qa_answers_with_self_route_total"], payload["coverage"]["qa_answers_total"])
        self.assertEqual(payload["actor_answers"][0]["answer_status"], "partial")
        self.assertIn("parliamentary_actions", payload["actor_answers"][0]["present_dimensions"])
        self.assertIn("money", payload["actor_answers"][0]["missing_dimensions"])
        self.assertEqual(payload["issue_answers"][0]["primary_issue_cluster_id"], "public-finance-taxation")
        self.assertIn("public-finance-taxation", payload["issue_answers"][0]["issue_cluster_ids"])
        self.assertEqual(payload["issue_clusters"][0]["cluster_id"], "public-finance-taxation")
        self.assertEqual(payload["issue_clusters"][0]["coverage"]["issues_total"], 1)
        self.assertTrue(payload["issue_clusters"][0]["method"]["requires_review"])
        self.assertEqual(payload["issue_cluster_review_queue"][0]["cluster_id"], "public-finance-taxation")
        self.assertEqual(payload["issue_cluster_review_queue"][0]["review_status"], "needs_review")
        self.assertTrue(payload["issue_cluster_review_queue"][0]["method"]["requires_review"])
        self.assertIn("decision", payload["issue_cluster_review_queue"][0]["expected_decision_fields"])
        self.assertEqual(payload["indexes"]["issue_clusters_by_issue_id"]["issue-1"], ["public-finance-taxation"])
        self.assertEqual(
            payload["indexes"]["issue_cluster_review_by_id"]["issue-cluster-review:public-finance-taxation"],
            "public-finance-taxation",
        )
        self.assertEqual(
            payload["issue_cluster_assignment_review_queue"][0]["review_id"],
            "issue-cluster-assignment-review:issue-1",
        )
        self.assertEqual(payload["issue_cluster_assignment_review_queue"][0]["primary_cluster_id"], "public-finance-taxation")
        self.assertEqual(
            payload["indexes"]["issue_cluster_assignment_review_by_id"]["issue-cluster-assignment-review:issue-1"],
            "issue-1",
        )
        qa_by_id = {answer["answer_id"]: answer for answer in payload["qa_answers"]}
        self.assertIn("qa:issue:issue-1", qa_by_id)
        self.assertIn("qa:actor_issue:party_id:1:issue-1", qa_by_id)
        self.assertIn("Proyecto de Ley de Presupuestos", qa_by_id["qa:issue:issue-1"]["question"])
        self.assertIn("accountability entries", qa_by_id["qa:issue:issue-1"]["answer_text"])
        self.assertEqual(qa_by_id["qa:actor_issue:party_id:1:issue-1"]["source_collection"], "actor_issue_refs")
        self.assertEqual(qa_by_id["qa:actor_issue:party_id:1:issue-1"]["evidence_basis"]["entries_total"], 2)
        self.assertRegex(
            qa_by_id["qa:actor_issue:party_id:1:issue-1"]["routes"]["self"],
            r"^/accountability-evidence/questions/qa-actor-issue-party-id-1-issue-1-[0-9a-z]+/$",
        )
        self.assertRegex(
            qa_by_id["qa:issue:issue-1"]["routes"]["self"],
            r"^/accountability-evidence/questions/qa-issue-issue-1-[0-9a-z]+/$",
        )
        self.assertEqual(payload["indexes"]["qa_answer_by_id"]["qa:issue:issue-1"], "qa:issue:issue-1")
        self.assertEqual(
            payload["indexes"]["qa_route_by_id"]["qa:issue:issue-1"],
            qa_by_id["qa:issue:issue-1"]["routes"]["self"],
        )
        self.assertEqual(payload["actor_answers"][0]["confidence"]["level"], "medium")
        self.assertEqual(payload["actor_answers"][0]["confidence"]["best_evidence_tier"], 1)
        self.assertEqual(payload["actor_answers"][0]["freshness"]["level"], "current")
        self.assertEqual(payload["coverage"]["confidence_level_counts"]["medium"], 2)
        self.assertEqual(payload["coverage"]["freshness_level_counts"]["current"], 2)
        gaps_by_dimension = {answer["dimension"]: answer for answer in payload["gap_answers"]}
        self.assertEqual(gaps_by_dimension["money"]["answer_status"], "unanswerable")
        self.assertEqual(gaps_by_dimension["rules"]["answer_status"], "partial")
        self.assertEqual(gaps_by_dimension["money"]["coverage"]["missing_answers_total"], 2)
        self.assertEqual(payload["indexes"]["gap_answer_by_dimension"]["money"], "gap:money")
        self.assertEqual(payload["actor_answers"][0]["evidence_samples"][0]["entry_id"], "entry-1")
        self.assertEqual(payload["issue_answers"][0]["evidence_samples"][0]["entry_id"], "entry-2")

    def test_build_applies_issue_cluster_review_seed(self) -> None:
        dossiers = {
            "meta": {"schema_version": "accountability_dossier_snapshot_v1"},
            "coverage": {"entries_total": 1, "actors_total": 1, "issues_total": 1},
            "actors": [],
            "issues": [
                {
                    "issue_id": "issue-1",
                    "label": "Proyecto de Ley de Presupuestos Generales del Estado",
                    "entries_total": 1,
                    "actors_total": 1,
                    "roles": {"approved": 1},
                    "entry_kinds": {"rule": 1},
                    "actor_kinds": {"institution": 1},
                    "first_date": "2026-01-01",
                    "last_date": "2026-01-01",
                    "top_actors": [],
                }
            ],
        }
        ledger = {
            "meta": {"schema_version": "accountability_ledger_snapshot_v1"},
            "actors": [],
            "issues": [{"issue_id": "issue-1", "entries": []}],
        }
        reviews = {
            "meta": {"schema_version": "accountability_issue_cluster_reviews_v1"},
            "reviews": [
                {
                    "cluster_id": "public-finance-taxation",
                    "decision": "accept",
                    "reviewed_label": "Hacienda publica, presupuestos e impuestos",
                    "reviewer": "Dev",
                    "reviewed_at": "2026-05-10",
                    "review_scope": "public_bucket_label",
                    "rationale": "Label checked against current keyword bucket.",
                    "caveat": "Membership still heuristic.",
                }
            ],
        }

        payload = build_evidence_api(
            dossiers,
            ledger,
            snapshot_date="2026-02-12",
            issue_cluster_reviews=reviews,
        )

        self.assertEqual(payload["meta"]["source_issue_cluster_reviews_schema"], "accountability_issue_cluster_reviews_v1")
        self.assertEqual(payload["coverage"]["issue_cluster_reviews_applied_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_review_status_counts"], {"reviewed": 1})
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_needed_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_queue_total"], 1)
        self.assertEqual(payload["issue_clusters"][0]["label"], "Hacienda publica, presupuestos e impuestos")
        self.assertEqual(payload["issue_clusters"][0]["review_status"], "reviewed")
        self.assertEqual(payload["issue_clusters"][0]["method"]["confidence"], "reviewed")
        self.assertEqual(payload["issue_clusters"][0]["method"]["membership_confidence"], "heuristic")
        self.assertFalse(payload["issue_clusters"][0]["method"]["requires_review"])
        self.assertEqual(payload["issue_cluster_review_queue"][0]["review_status"], "reviewed")
        self.assertEqual(payload["issue_cluster_review_queue"][0]["review"]["reviewer"], "Dev")

    def test_build_applies_issue_level_cluster_assignment_seed(self) -> None:
        dossiers = {
            "meta": {"schema_version": "accountability_dossier_snapshot_v1"},
            "coverage": {"entries_total": 1, "actors_total": 1, "issues_total": 1},
            "actors": [],
            "issues": [
                {
                    "issue_id": "issue-1",
                    "label": "Unclassified autonomy statute reform",
                    "entries_total": 1,
                    "actors_total": 1,
                    "roles": {"voted_for": 1},
                    "entry_kinds": {"parliamentary_action": 1},
                    "actor_kinds": {"person": 1},
                    "first_date": "2026-01-01",
                    "last_date": "2026-01-01",
                    "top_actors": [],
                }
            ],
        }
        ledger = {
            "meta": {"schema_version": "accountability_ledger_snapshot_v1"},
            "actors": [],
            "issues": [{"issue_id": "issue-1", "entries": []}],
        }
        issue_reviews = {
            "meta": {"schema_version": "accountability_issue_cluster_issue_reviews_v1"},
            "cluster_definitions": [
                {
                    "cluster_id": "territorial-autonomy-institutional-reform",
                    "reviewed_label": "Autonomia territorial e instituciones",
                    "reviewer": "Dev",
                    "reviewed_at": "2026-05-10",
                    "rationale": "Reviewed bucket.",
                }
            ],
            "issue_reviews": [
                {
                    "issue_id": "issue-1",
                    "decision": "set_clusters",
                    "primary_cluster_id": "territorial-autonomy-institutional-reform",
                    "cluster_ids": ["territorial-autonomy-institutional-reform"],
                    "reviewer": "Dev",
                    "reviewed_at": "2026-05-10",
                    "rationale": "Reviewed source issue assignment.",
                }
            ],
        }

        payload = build_evidence_api(
            dossiers,
            ledger,
            snapshot_date="2026-02-12",
            issue_cluster_issue_reviews=issue_reviews,
        )

        self.assertEqual(
            payload["meta"]["source_issue_cluster_issue_reviews_schema"],
            "accountability_issue_cluster_issue_reviews_v1",
        )
        self.assertEqual(payload["coverage"]["issue_cluster_issue_reviews_applied_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_reviewed_links_total"], 1)
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_needed_total"], 0)
        self.assertEqual(payload["coverage"]["issue_cluster_assignment_review_queue_total"], 0)
        self.assertEqual(payload["coverage"]["fallback_issue_cluster_answers_total"], 0)
        self.assertEqual(payload["issue_answers"][0]["primary_issue_cluster_id"], "territorial-autonomy-institutional-reform")
        self.assertEqual(payload["issue_answers"][0]["issue_cluster_assignment_review_status"], "reviewed")
        self.assertEqual(payload["issue_clusters"][0]["cluster_id"], "territorial-autonomy-institutional-reform")
        self.assertEqual(payload["issue_clusters"][0]["label"], "Autonomia territorial e instituciones")
        self.assertEqual(payload["issue_clusters"][0]["coverage"]["issue_membership_reviewed_links_total"], 1)
        self.assertEqual(payload["issue_clusters"][0]["method"]["membership_confidence"], "reviewed")
        self.assertEqual(payload["issue_cluster_review_queue"][0]["review_status"], "reviewed")

    def test_cli_writes_latest_alias(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dossiers = root / "dossiers.json"
            ledger = root / "ledger.json"
            out = root / "api.json"
            latest = root / "latest.json"
            dossiers.write_text(
                json.dumps(
                    {
                        "meta": {"schema_version": "accountability_dossier_snapshot_v1"},
                        "coverage": {"entries_total": 0, "actors_total": 0, "issues_total": 0},
                        "actors": [],
                        "issues": [],
                    }
                ),
                encoding="utf-8",
            )
            ledger.write_text(
                json.dumps({"meta": {"schema_version": "accountability_ledger_snapshot_v1"}, "actors": [], "issues": []}),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_evidence_api_snapshot.py",
                    "--dossiers",
                    str(dossiers),
                    "--ledger",
                    str(ledger),
                    "--snapshot-date",
                    "2026-02-12",
                    "--out",
                    str(out),
                    "--latest-out",
                    str(latest),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(out.exists())
            self.assertEqual(json.loads(out.read_text())["meta"]["schema_version"], "accountability_evidence_api_v1")
            self.assertEqual(out.read_text(), latest.read_text())
            self.assertNotIn("\n  ", out.read_text())


if __name__ == "__main__":
    unittest.main()
