from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_vote_database import audit_database


class TestAuditVoteDatabase(unittest.TestCase):
    def test_reconciles_absence_separately_from_no_vote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "votes.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE parl_vote_events (
                  vote_event_id TEXT PRIMARY KEY,
                  source_id TEXT NOT NULL,
                  totals_present INTEGER,
                  totals_yes INTEGER,
                  totals_no INTEGER,
                  totals_abstain INTEGER,
                  totals_no_vote INTEGER,
                  totals_absent INTEGER
                );
                CREATE TABLE parl_vote_member_votes (
                  member_vote_id INTEGER PRIMARY KEY,
                  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id),
                  person_id INTEGER,
                  vote_choice TEXT NOT NULL
                );
                CREATE TABLE persons (person_id INTEGER PRIMARY KEY);
                CREATE TABLE mandates (mandate_id INTEGER PRIMARY KEY);
                INSERT INTO persons VALUES (10);
                INSERT INTO parl_vote_events VALUES (
                  'v1', 'senado_votaciones', 1, 1, 0, 0, 0, 1
                );
                INSERT INTO parl_vote_events VALUES (
                  'v2', 'senado_votaciones', 2, 2, 0, 0, 0, 0
                );
                INSERT INTO parl_vote_events VALUES (
                  'v3', 'senado_votaciones', 1, 1, 0, 0, 0, 0
                );
                INSERT INTO parl_vote_events VALUES (
                  'v4', 'senado_votaciones', 1, 1, 0, 0, 0, 0
                );
                INSERT INTO parl_vote_member_votes VALUES (1, 'v1', 10, 'SI');
                INSERT INTO parl_vote_member_votes VALUES (2, 'v1', NULL, 'AUSENTE');
                INSERT INTO parl_vote_member_votes VALUES (3, 'v2', 10, 'SI');
                INSERT INTO parl_vote_member_votes VALUES (4, 'v3', 10, 'SI');
                INSERT INTO parl_vote_member_votes VALUES (5, 'v3', 10, 'NO');
                INSERT INTO parl_vote_member_votes VALUES (6, 'v4', 10, 'NO');
                """
            )
            conn.close()
            report = audit_database(db_path, include_sha256=False)

        self.assertEqual(report["foreign_key_errors"], 0)
        self.assertEqual(report["totals"]["events_reconciled"], 1)
        self.assertEqual(report["totals"]["events_not_reconciled"], 3)
        self.assertEqual(report["totals"]["member_votes_absent"], 1)
        self.assertEqual(report["totals"]["member_votes_other_choice"], 0)
        self.assertEqual(report["totals"]["member_votes_with_person_id_pct"], 0.833333)
        self.assertEqual(report["entity_counts"], {"persons": 1, "mandates": 0})
        profile = report["mismatch_profile"]["total"]
        self.assertEqual(profile["events"], 3)
        self.assertEqual(
            profile["classes"],
            {
                "observed_rows_below_official_categories": 1,
                "observed_rows_above_official_categories": 1,
                "same_category_total_wrong_distribution": 1,
            },
        )
        self.assertEqual(profile["dimensions"]["yes"]["events_mismatched"], 2)
        self.assertEqual(profile["dimensions"]["no"]["events_mismatched"], 2)
        self.assertEqual(
            report["mismatch_profile"]["sources"]["senado_votaciones"]["events"],
            3,
        )


if __name__ == "__main__":
    unittest.main()
