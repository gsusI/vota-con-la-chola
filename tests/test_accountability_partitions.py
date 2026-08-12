from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.accountability_partition_validation import (
    validate_accountability_partitions,
)
from publicdata_publish.accountability_partitions import (
    export_accountability_partitions,
)

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestAccountabilityPartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT NOT NULL
            );
            CREATE TABLE accountability_issues (
              issue_id TEXT PRIMARY KEY,
              canonical_key TEXT NOT NULL,
              label TEXT NOT NULL,
              issue_status TEXT NOT NULL
            );
            CREATE TABLE accountability_ledger_entries (
              entry_id TEXT PRIMARY KEY,
              issue_id TEXT NOT NULL,
              entry_kind TEXT NOT NULL,
              accountability_role TEXT,
              role_in_chain TEXT,
              actor_label TEXT NOT NULL,
              actor_kind TEXT NOT NULL,
              person_id INTEGER,
              party_id INTEGER,
              parliamentary_group_id INTEGER,
              mandate_id INTEGER,
              institution_id INTEGER,
              org_unit_id INTEGER,
              position_id INTEGER,
              linked_object_type TEXT,
              linked_object_id TEXT,
              policy_event_id TEXT,
              topic_evidence_id INTEGER,
              legal_fragment_id TEXT,
              event_date TEXT,
              published_date TEXT,
              title TEXT,
              summary TEXT,
              accountability_question TEXT,
              confidence REAL,
              evidence_tier INTEGER,
              source_id TEXT,
              source_title TEXT,
              source_url TEXT,
              source_record_pk INTEGER,
              evidence_quote TEXT
            );
            INSERT INTO sources VALUES
              ('congreso_votaciones', 'https://example.test/congreso'),
              ('boe_api_legal', 'https://example.test/boe');
            INSERT INTO accountability_issues VALUES
              ('i1', 'water', 'Water', 'active'),
              ('i2', 'housing', 'Housing', 'active');
            INSERT INTO accountability_ledger_entries VALUES
              ('e001', 'i1', 'parliamentary_action', 'voted_for', NULL,
               'A', 'person', 1, NULL, NULL, 11, NULL, NULL, NULL,
               'vote', 'v1', NULL, NULL, NULL, '2024-01-01', NULL,
               'Vote A', 'Summary A', 'Question A', 1.0, 1,
               'congreso_votaciones', 'Congress',
               'file:///Users/example/private.json', 101, 'Yes'),
              ('e002', 'i1', 'parliamentary_action', 'voted_against', NULL,
               'B', 'person', 2, NULL, NULL, 12, NULL, NULL, NULL,
               'vote', 'v1', NULL, NULL, NULL, '2024-01-01', NULL,
               'Vote B', 'Summary B', 'Question B', 1.0, 1,
               'congreso_votaciones', 'Congress',
               'https://example.test/vote/2', 102, 'No'),
              ('e003', 'i1', 'parliamentary_action', 'abstained', NULL,
               'C', 'person', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
               'vote', 'v1', NULL, NULL, NULL, '2024-01-01', NULL,
               'Vote C', 'Summary C', 'Question C', 1.0, 1,
               'congreso_votaciones', 'Congress', NULL, NULL, 'Abstain'),
              ('e004', 'i2', 'rule', 'published', NULL,
               'Institution A', 'institution', NULL, NULL, NULL, NULL, 21,
               NULL, NULL, 'rule', 'r1', 'p1', NULL, NULL, '2025-02-01',
               NULL, 'Rule A', 'Summary D', 'Question D', 0.9, 1,
               'boe_api_legal', 'BOE', 'https://example.test/rule/4', 104,
               'Rule'),
              ('e005', 'i2', 'appointment', 'appointed', NULL,
               'D', 'person', 4, NULL, NULL, NULL, NULL, NULL, 31,
               'appointment', 'a1', 'p2', NULL, NULL, '2025-02-02', NULL,
               'Appointment', 'Summary E', 'Question E', 0.8, 2,
               'boe_api_legal', 'BOE', NULL, 105, 'Appointed'),
              ('e006', 'i2', 'money', 'funded', NULL,
               'Institution B', 'institution', NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, 'budget', 'b1', NULL, NULL, NULL, '2026-02-02',
               NULL, 'Budget', 'Summary F', 'Question F', 0.7, 2,
               'boe_api_legal', 'Official budget', 'https://example.test/budget/6',
               NULL, 'Funded'),
              ('e007', 'i2', 'outcome', 'unknown', NULL,
               'Unknown actor', 'unknown', NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, 'indicator', 'o1', NULL, NULL, NULL, NULL, NULL,
               'Outcome', 'Summary G', 'Question G', 0.5, 3,
               'boe_api_legal', 'Official outcome', 'https://example.test/outcome/7',
               NULL, 'Observed');
            """
        )
        conn.commit()
        conn.close()

    def test_full_validation_and_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "ledger.db"
            self._database(db_path)
            first_root = root / "first"
            first = export_accountability_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-02-25",
                row_group_rows=2,
                max_file_rows=3,
                min_rows=7,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 7)
            self.assertEqual(first["totals"]["source_url_rows"], 7)
            self.assertEqual(first["totals"]["private_token_findings"], 0)
            self.assertEqual(first["totals"]["unresolved_actor_rows"], 3)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])
            self.assertEqual(
                validate_accountability_partitions(root=first_root, min_rows=7)[
                    "status"
                ],
                "ok",
            )

            second_root = root / "second"
            second = export_accountability_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-02-26",
                row_group_rows=2,
                max_file_rows=3,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                min_rows=7,
                enforce=True,
            )
            self.assertEqual(
                second["incremental_contract"]["partitions_reused"],
                first["totals"]["partitions"],
            )
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE accountability_ledger_entries "
                "SET summary = 'Changed' WHERE entry_id = 'e001'"
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_accountability_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-02-27",
                row_group_rows=2,
                max_file_rows=3,
                previous_manifest_path=second_root / "manifest.json",
                previous_root=second_root,
                min_rows=7,
                enforce=True,
            )
            self.assertEqual(third["incremental_contract"]["partitions_rebuilt"], 1)
            self.assertEqual(
                third["incremental_contract"]["partitions_reused"],
                first["totals"]["partitions"] - 1,
            )
            self.assertEqual(
                validate_accountability_partitions(root=third_root, min_rows=7)[
                    "status"
                ],
                "ok",
            )

    def test_enforced_failure_does_not_promote_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "ledger.db"
            output_root = root / "failed"
            self._database(db_path)
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_accountability_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-02-25",
                    min_rows=8,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
