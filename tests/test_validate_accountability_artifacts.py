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


PUBLIC_DIMENSIONS = [
    "promises",
    "parliamentary_actions",
    "rules",
    "appointments",
    "money",
    "implementation",
    "enforcement",
    "audits",
    "outcomes",
]


def _sample_ref(suffix: str) -> dict:
    return {
        "entry_id": f"entry-{suffix}",
        "issue_id": "issue-1",
        "issue_label": "Issue 1",
        "actor_label": "Actor 1",
        "actor_kind": "party",
        "entry_kind": "parliamentary_action",
        "accountability_role": "voted_for",
        "event_date": "2026-05-01",
        "evidence_tier": 1,
        "source_title": "Official vote",
        "source_url": "https://example.test/vote",
        "source_locator": f"vote-{suffix}",
        "evidence_quote": "SI",
        "summary": "Actor 1 voted yes.",
    }


def _confidence() -> dict:
    return {
        "level": "medium",
        "score": 0.7,
        "basis": ["tier_1_primary_or_official_evidence"],
        "best_evidence_tier": 1,
        "completeness": {
            "present_dimensions_total": 1,
            "missing_dimensions_total": 8,
            "expected_dimensions_total": 9,
            "pct": 0.111,
        },
    }


def _freshness() -> dict:
    return {
        "level": "current",
        "age_days": 1,
        "first_date": "2026-05-01",
        "last_date": "2026-05-01",
        "basis": "latest evidence date compared with snapshot 2026-05-10",
    }


def _actor_answer(actor_key: str, suffix: str) -> dict:
    return {
        "answer_id": f"actor:{actor_key}",
        "question_id": "actor_historical_record",
        "answer_status": "partial",
        "actor_key": actor_key,
        "actor_label": f"Actor {suffix}",
        "actor_kind": "party",
        "summary": f"Actor {suffix} has 1 accountability entries across 1 issues.",
        "coverage": {
            "entries_total": 1,
            "issues_total": 1,
            "first_date": "2026-05-01",
            "last_date": "2026-05-01",
        },
        "role_counts": [{"key": "voted_for", "count": 1}],
        "entry_kind_counts": [{"key": "parliamentary_action", "count": 1}],
        "present_dimensions": ["parliamentary_actions"],
        "missing_dimensions": [item for item in PUBLIC_DIMENSIONS if item != "parliamentary_actions"],
        "confidence": _confidence(),
        "freshness": _freshness(),
        "caveats": ["This answer is partial."],
        "evidence_samples": [_sample_ref(suffix)],
        "routes": {"dossier": f"/accountability-dossiers/actors/{actor_key}/"},
    }


def _issue_answer() -> dict:
    return {
        "answer_id": "issue:issue-1",
        "question_id": "issue_involved_actors",
        "answer_status": "partial",
        "issue_id": "issue-1",
        "issue_label": "Issue 1",
        "summary": "Issue 1 has 1 accountability entries across 1 actors.",
        "coverage": {
            "entries_total": 1,
            "actors_total": 1,
            "first_date": "2026-05-01",
            "last_date": "2026-05-01",
            "scope": "nacional",
        },
        "role_counts": [{"key": "voted_for", "count": 1}],
        "entry_kind_counts": [{"key": "parliamentary_action", "count": 1}],
        "actor_kind_counts": [{"key": "party", "count": 1}],
        "present_dimensions": ["parliamentary_actions"],
        "missing_dimensions": [item for item in PUBLIC_DIMENSIONS if item != "parliamentary_actions"],
        "confidence": _confidence(),
        "freshness": _freshness(),
        "caveats": ["This answer is partial."],
        "top_actors": [{"actor_key": "party_id:1", "actor_label": "Actor 1", "actor_kind": "party"}],
        "evidence_samples": [_sample_ref("issue")],
        "routes": {"dossier": "/accountability-dossiers/issues/issue-1/"},
        "primary_issue_cluster_id": "cluster-1",
        "issue_cluster_ids": ["cluster-1"],
    }


def _gap_answer(dimension: str) -> dict:
    return {
        "answer_id": f"gap:{dimension}",
        "question_id": "missing_evidence",
        "answer_status": "partial",
        "dimension": dimension,
        "dimension_label": dimension,
        "summary": f"{dimension} coverage is partial.",
        "coverage": {
            "actor_answers_total": 2,
            "issue_answers_total": 1,
            "actor_answers_missing": 2,
            "issue_answers_missing": 1,
            "missing_answers_total": 3,
            "present_answers_total": 0,
        },
        "next_evidence_needed": "More primary evidence.",
        "sample_missing_issues": [
            {
                "answer_id": "issue:issue-1",
                "issue_id": "issue-1",
                "label": "Issue 1",
                "entries_total": 1,
                "route": "/accountability-dossiers/issues/issue-1/",
            }
        ],
        "sample_missing_actors": [
            {
                "answer_id": "actor:party_id:1",
                "actor_key": "party_id:1",
                "label": "Actor 1",
                "actor_kind": "party",
                "entries_total": 1,
                "route": "/accountability-dossiers/actors/party_id:1/",
            }
        ],
    }


def _blocker_answer() -> dict:
    return {
        "answer_id": "blocker:aemet_opendata_series",
        "question_id": "source_blocker",
        "answer_status": "blocked",
        "source_id": "aemet_opendata_series",
        "source_name": "AEMET OpenData",
        "institution_name": "AEMET",
        "domain": "politicos",
        "scope": "outcomes",
        "catalog_state": "blocked",
        "tracker_status": "PARTIAL",
        "sql_status": "PARTIAL",
        "blocker_kind": "http_403",
        "summary": "AEMET OpenData is blocked in the source catalog.",
        "blocker_reason": "HTTP 403 in strict network.",
        "evidence_refs": [{"path": "docs/etl/sprints/AI-OPS-1/evidence/aemet.log"}],
        "next_commands": [
            "python3 scripts/ingestar_politicos_es.py ingest --source aemet_opendata_series --strict-network"
        ],
        "source_url": "https://opendata.aemet.es/",
        "latest_snapshot": "2026-05-10T00:00:00Z",
        "coverage": {
            "runs_total": 1,
            "runs_ok": 0,
            "last_loaded": 0,
            "max_loaded_network": 0,
            "network_fetches": 0,
            "fallback_fetches": 1,
        },
        "routes": {
            "source_catalog": "/explorer-sources/",
            "datasets": "/methods/datasets/",
        },
        "caveats": ["Blocker answer, not responsibility claim."],
    }


def _evidence_api_payload() -> dict:
    actor_answers = [_actor_answer("party_id:1", "1"), _actor_answer("party_id:2", "2")]
    issue_answers = [_issue_answer()]
    gap_answers = [_gap_answer(dimension) for dimension in PUBLIC_DIMENSIONS]
    blocker_answers = [_blocker_answer()]
    qa_answers = [
        {
            "answer_id": "qa:cluster:cluster-1",
            "question_id": "natural_language_qa",
            "source_collection": "issue_clusters",
            "source_answer_id": "cluster-1",
            "question": "What do we know about cluster 1?",
            "answer_text": "Cluster 1 is partial.",
            "answer_status": "partial",
            "evidence_basis": {"entries_total": 1},
            "routes": {
                "self": "/accountability-evidence/questions/qa-cluster-cluster-1/",
                "primary": "/accountability-dossiers/issues/issue-1/",
            },
            "caveats": ["Partial cluster."],
        },
        {
            "answer_id": "qa:issue:issue-1",
            "question_id": "natural_language_qa",
            "source_collection": "issue_answers",
            "source_answer_id": "issue:issue-1",
            "question": "Who touched issue 1?",
            "answer_text": "Issue 1 is partial.",
            "answer_status": "partial",
            "evidence_basis": {"entries_total": 1},
            "routes": {
                "self": "/accountability-evidence/questions/qa-issue-issue-1/",
                "primary": "/accountability-dossiers/issues/issue-1/",
            },
            "caveats": ["Partial issue."],
        },
        {
            "answer_id": "qa:actor:party_id:1",
            "question_id": "natural_language_qa",
            "source_collection": "actor_answers",
            "source_answer_id": "actor:party_id:1",
            "question": "What did actor 1 do?",
            "answer_text": "Actor 1 is partial.",
            "answer_status": "partial",
            "evidence_basis": {"entries_total": 1},
            "routes": {
                "self": "/accountability-evidence/questions/qa-actor-party-1/",
                "primary": "/accountability-dossiers/actors/party_id:1/",
            },
            "caveats": ["Partial actor."],
        },
        {
            "answer_id": "qa:blocker:aemet_opendata_series",
            "question_id": "natural_language_qa",
            "source_collection": "blocker_answers",
            "source_answer_id": "blocker:aemet_opendata_series",
            "question": "What source is blocked?",
            "answer_text": "AEMET OpenData is blocked.",
            "answer_status": "blocked",
            "evidence_basis": {"source_id": "aemet_opendata_series", "blocker_kind": "http_403"},
            "routes": {
                "self": "/accountability-evidence/questions/qa-blocker-aemet/",
                "primary": "/explorer-sources/",
            },
            "caveats": ["Blocker answer, not responsibility claim."],
        },
        {
            "answer_id": "qa:gap:promises",
            "question_id": "natural_language_qa",
            "source_collection": "gap_answers",
            "source_answer_id": "gap:promises",
            "question": "What promise evidence is missing?",
            "answer_text": "Promise evidence is partial.",
            "answer_status": "partial",
            "evidence_basis": {"dimension": "promises"},
            "routes": {"self": "/accountability-evidence/questions/qa-gap-promises/"},
            "caveats": ["Gap answer, not responsibility claim."],
        },
    ]
    return {
        "meta": {
            "schema_version": "accountability_evidence_api_v1",
            "snapshot_date": "2026-05-10",
        },
        "snapshot_date": "2026-05-10",
        "coverage": {
            "question_templates_total": 6,
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
            "blocker_answers_total": 1,
            "source_catalog_sources_total": 1,
            "source_catalog_blocked_total": 1,
            "qa_answers_total": 5,
            "qa_answers_with_self_route_total": 5,
            "evidence_samples_total": 3,
            "answer_status_counts": {"partial": 3},
            "qa_answer_status_counts": {"blocked": 1, "partial": 4},
            "gap_answer_status_counts": {"partial": 9},
            "blocker_answer_status_counts": {"blocked": 1},
            "blocker_kind_counts": {"http_403": 1},
            "confidence_level_counts": {"medium": 3},
            "freshness_level_counts": {"current": 3},
        },
        "question_templates": [
            {"question_id": "issue_involved_actors"},
            {"question_id": "actor_historical_record"},
            {"question_id": "actor_issue_record"},
            {"question_id": "missing_evidence"},
            {"question_id": "source_blocker"},
            {"question_id": "natural_language_qa"},
        ],
        "actor_answers": actor_answers,
        "issue_answers": issue_answers,
        "actor_issue_refs": [
            {
                "answer_id": "actor_issue:party_id:1:issue-1",
                "question_id": "actor_issue_record",
                "answer_status": "partial",
                "actor_key": "party_id:1",
                "actor_label": "Actor 1",
                "actor_kind": "party",
                "issue_id": "issue-1",
                "issue_label": "Issue 1",
                "entries_total": 1,
                "role_counts": [{"key": "voted_for", "count": 1}],
                "entry_kind_counts": [{"key": "parliamentary_action", "count": 1}],
                "first_date": "2026-05-01",
                "last_date": "2026-05-01",
                "routes": {
                    "actor_dossier": "/accountability-dossiers/actors/party_id:1/",
                    "issue_dossier": "/accountability-dossiers/issues/issue-1/",
                },
            },
            {
                "answer_id": "actor_issue:party_id:2:issue-1",
                "question_id": "actor_issue_record",
                "answer_status": "partial",
                "actor_key": "party_id:2",
                "actor_label": "Actor 2",
                "actor_kind": "party",
                "issue_id": "issue-1",
                "issue_label": "Issue 1",
                "entries_total": 1,
                "role_counts": [{"key": "voted_for", "count": 1}],
                "entry_kind_counts": [{"key": "parliamentary_action", "count": 1}],
                "first_date": "2026-05-01",
                "last_date": "2026-05-01",
                "routes": {
                    "actor_dossier": "/accountability-dossiers/actors/party_id:2/",
                    "issue_dossier": "/accountability-dossiers/issues/issue-1/",
                },
            },
        ],
        "issue_clusters": [
            {
                "cluster_id": "cluster-1",
                "label": "Cluster 1",
                "answer_status": "partial",
                "summary": "Cluster 1 groups 1 issue.",
                "coverage": {"issues_total": 1, "entries_total": 1},
                "method": {"method_id": "issue_level_review_v1"},
                "review_status": "reviewed",
                "top_issues": [
                    {
                        "answer_id": "issue:issue-1",
                        "issue_id": "issue-1",
                        "label": "Issue 1",
                        "entries_total": 1,
                        "route": "/accountability-dossiers/issues/issue-1/",
                    }
                ],
                "evidence_samples": [_sample_ref("cluster")],
                "caveats": ["Cluster partial."],
            }
        ],
        "issue_cluster_review_queue": [{"review_id": "issue-cluster-review:cluster-1", "cluster_id": "cluster-1"}],
        "issue_cluster_assignment_review_queue": [
            {"review_id": "issue-cluster-assignment-review:issue-1", "issue_id": "issue-1"}
        ],
        "gap_answers": gap_answers,
        "blocker_answers": blocker_answers,
        "qa_answers": qa_answers,
    }


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
            _write(evidence_api, _evidence_api_payload())
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
                    "6",
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
                    "5",
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
            self.assertEqual(checks["evidence_api_question_templates_total"], 6)
            self.assertEqual(checks["evidence_api_issue_clusters_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_links_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_review_items_total"], 1)
            self.assertEqual(checks["evidence_api_reviewed_issue_clusters_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_issue_reviews_applied_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_reviewed_links_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_assignment_review_needed_total"], 1)
            self.assertEqual(checks["evidence_api_issue_cluster_assignment_review_queue_total"], 1)
            self.assertEqual(checks["evidence_api_gap_answers_total"], 9)
            self.assertEqual(checks["evidence_api_blocker_answers_total"], 1)
            self.assertEqual(checks["evidence_api_source_catalog_blocked_total"], 1)
            self.assertEqual(checks["evidence_api_qa_answers_total"], 5)
            self.assertEqual(checks["evidence_api_qa_answers_with_self_route_total"], 5)
            self.assertEqual(checks["evidence_api_confidence_levels_total"], 3)
            self.assertEqual(checks["evidence_api_freshness_levels_total"], 3)
            self.assertEqual(checks["evidence_api_actor_answers_exported"], 2)
            self.assertEqual(checks["evidence_api_issue_answers_exported"], 1)
            self.assertEqual(checks["evidence_api_evidence_samples_exported"], 3)

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

    def test_validator_rejects_public_answer_without_evidence_contract(self) -> None:
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
                        "entries_total": 2,
                        "actors_total": 2,
                        "entries_with_resolved_actor_id": 2,
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
            payload = _evidence_api_payload()
            payload["actor_answers"][0]["evidence_samples"] = []
            payload["qa_answers"][1]["routes"].pop("primary")
            _write(evidence_api, payload)

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
                ],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("actor_answers[0] (actor:party_id:1) missing evidence_samples", result.stderr)
            self.assertIn("qa_answers[1] (qa:issue:issue-1) missing primary route", result.stderr)

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
