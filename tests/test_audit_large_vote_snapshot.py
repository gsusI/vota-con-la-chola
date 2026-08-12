from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_large_vote_snapshot import audit_snapshot, iter_snapshot_items


class TestAuditLargeVoteSnapshot(unittest.TestCase):
    def test_streaming_audit_separates_observation_from_promotion(self) -> None:
        item = {
            "event": {
                "vote_event_id": "vote-1",
                "source_id": "official-votes",
                "totals_yes": 1,
                "totals_no": 0,
                "totals_abstain": 0,
                "totals_no_vote": 0,
            },
            "member_votes": [
                {
                    "seat": "1",
                    "member_name": "Person One",
                    "member_name_normalized": "person one",
                    "person_id": 1,
                    "vote_choice": "Sí",
                    "source": {
                        "source_id": "official-votes",
                        "source_url": "https://official.example/vote-1",
                        "source_hash": "a" * 64,
                        "source_record_pk": None,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "votes.json"
            path.write_text(
                json.dumps({"metadata": {"items_word": "safe"}, "items": [item]}),
                encoding="utf-8",
            )
            self.assertEqual(len(list(iter_snapshot_items(path, chunk_chars=7))), 1)
            report = audit_snapshot(
                path,
                min_member_votes=1,
                min_source_url_pct=1.0,
                min_source_hash_pct=1.0,
                min_source_record_pk_pct=1.0,
                min_reconciled_events_pct=1.0,
                max_duplicate_member_rate=0.0,
                max_public_artifact_bytes=10_000,
                chunk_chars=7,
            )
        self.assertEqual(report["status"], "observed_not_promoted")
        self.assertTrue(report["checks"]["million_real_member_votes_observed"])
        self.assertFalse(report["checks"]["source_record_lineage_coverage"])
        self.assertFalse(report["promotion_gate_passed"])

    def test_parent_event_lineage_is_counted_but_not_claimed_as_direct(self) -> None:
        item = {
            "event": {
                "vote_event_id": "vote-1",
                "source_id": "official-votes",
                "totals_yes": 1,
                "totals_no": 0,
                "totals_abstain": 0,
                "totals_no_vote": 0,
            },
            "source": {
                "source_id": "official-votes",
                "source_url": "https://official.example/vote-1",
                "source_hash": "b" * 64,
                "source_record_id": "vote-1",
                "source_record_pk": 7,
            },
            "member_votes": [
                {
                    "seat": "1",
                    "member_name": "Person One",
                    "member_name_normalized": "person one",
                    "person_id": 1,
                    "vote_choice": "Sí",
                    "source": {
                        "source_id": "official-votes",
                        "source_url": "https://official.example/vote-1",
                        "source_hash": "a" * 64,
                        "source_record_pk": None,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "votes.json"
            path.write_text(json.dumps({"items": [item]}), encoding="utf-8")
            report = audit_snapshot(
                path,
                min_member_votes=1,
                min_source_url_pct=1.0,
                min_source_hash_pct=1.0,
                min_source_record_pk_pct=1.0,
                min_reconciled_events_pct=1.0,
                max_duplicate_member_rate=0.0,
                max_public_artifact_bytes=10_000,
            )
        self.assertEqual(report["coverage"]["source_record_pk_direct_pct"], 0.0)
        self.assertEqual(
            report["coverage"]["source_record_parent_inherited_pct"], 1.0
        )
        self.assertEqual(
            report["coverage"]["source_record_lineage_effective_pct"], 1.0
        )
        self.assertTrue(report["checks"]["source_record_lineage_coverage"])

    def test_duplicate_event_and_member_are_detected(self) -> None:
        member = {
            "seat": "1",
            "member_name": "Person One",
            "member_name_normalized": "person one",
            "vote_choice": "No",
            "source": {
                "source_id": "official-votes",
                "source_url": "https://official.example/vote",
                "source_hash": "b" * 64,
                "source_record_pk": 1,
            },
        }
        event = {
            "vote_event_id": "duplicate",
            "source_id": "official-votes",
            "totals_yes": 0,
            "totals_no": 2,
            "totals_abstain": 0,
            "totals_no_vote": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "votes.json"
            path.write_text(
                json.dumps(
                    {
                        "items": [
                            {"event": event, "member_votes": [member, member]},
                            {"event": event, "member_votes": []},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = audit_snapshot(
                path,
                min_member_votes=1,
                min_source_url_pct=1.0,
                min_source_hash_pct=1.0,
                min_source_record_pk_pct=1.0,
                min_reconciled_events_pct=1.0,
                max_duplicate_member_rate=0.0,
                max_public_artifact_bytes=10_000,
            )
        self.assertEqual(report["totals"]["duplicate_event_ids"], 1)
        self.assertEqual(report["totals"]["duplicate_member_rows"], 1)
        self.assertFalse(report["checks"]["unique_event_ids"])
        self.assertFalse(report["checks"]["duplicate_member_rate"])

    def test_absent_is_distinct_from_no_vote_and_reconciled_when_available(self) -> None:
        item = {
            "event": {
                "vote_event_id": "senate-vote-1",
                "source_id": "senado_votaciones",
                "totals_yes": 1,
                "totals_no": 0,
                "totals_abstain": 0,
                "totals_no_vote": 0,
                "totals_absent": 1,
            },
            "member_votes": [
                {
                    "seat": "1",
                    "member_name": "Present Person",
                    "member_name_normalized": "present person",
                    "person_id": 1,
                    "vote_choice": "SI",
                    "source": {},
                },
                {
                    "seat": "2",
                    "member_name": "Absent Person",
                    "member_name_normalized": "absent person",
                    "person_id": 2,
                    "vote_choice": "AUSENTE",
                    "source": {},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "votes.json"
            path.write_text(json.dumps({"items": [item]}), encoding="utf-8")
            report = audit_snapshot(
                path,
                min_member_votes=1,
                min_source_url_pct=0.0,
                min_source_hash_pct=0.0,
                min_source_record_pk_pct=0.0,
                min_reconciled_events_pct=1.0,
                max_duplicate_member_rate=0.0,
                max_public_artifact_bytes=10_000,
                min_person_id_pct=1.0,
            )
        self.assertEqual(report["vote_choice_counts"]["absent"], 1)
        self.assertEqual(report["vote_choice_counts"].get("no_vote", 0), 0)
        self.assertEqual(report["totals"]["member_votes_absent_observed"], 1)
        self.assertEqual(report["totals"]["events_absent_totals_available"], 1)
        self.assertEqual(report["totals"]["events_reconciled"], 1)


if __name__ == "__main__":
    unittest.main()
