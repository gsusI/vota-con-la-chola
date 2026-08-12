from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.semantic_partition_validation import (
    validate_semantic_partitions,
)
from publicdata_publish.semantic_partitions import export_member_vote_partitions

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestSemanticPartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE parl_vote_events (
              vote_event_id TEXT PRIMARY KEY,
              legislature TEXT,
              vote_date TEXT,
              source_id TEXT NOT NULL,
              source_url TEXT,
              source_record_pk INTEGER,
              source_snapshot_date TEXT
            );
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT
            );
            CREATE TABLE parl_vote_member_votes (
              member_vote_id INTEGER PRIMARY KEY,
              vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id),
              seat TEXT,
              member_name TEXT,
              member_name_normalized TEXT,
              person_id INTEGER,
              group_code TEXT,
              vote_choice TEXT NOT NULL,
              source_id TEXT NOT NULL,
              source_url TEXT,
              source_snapshot_date TEXT,
              parliamentary_group_id INTEGER
            );
            INSERT INTO sources VALUES
              ('congreso_votaciones', 'https://example.test/congreso'),
              ('senado_votaciones', 'https://example.test/senado');
            INSERT INTO parl_vote_events VALUES
              ('e1', '15', '2024-01-10', 'congreso_votaciones',
               'https://example.test/congreso/e1', 101, '2026-02-25'),
              ('e2', '15', '2025-02-10', 'senado_votaciones',
               'https://example.test/senado/e2', 202, '2026-02-25');
            INSERT INTO parl_vote_member_votes VALUES
              (1, 'e1', '1', 'A', 'a', 11, 'G1', 'SI',
               'congreso_votaciones', 'https://example.test/v/1', '2026-02-25', 1),
              (2, 'e1', '2', 'B', 'b', 12, 'G2', 'NO',
               'congreso_votaciones', 'https://example.test/v/2', '2026-02-25', 2),
              (3, 'e1', '3', 'C', 'c', 13, 'G3', 'SI',
               'congreso_votaciones', 'https://example.test/v/3', '2026-02-25', 3),
              (4, 'e1', '4', 'D', 'd', 14, 'G4', 'NO',
               'congreso_votaciones', 'https://example.test/v/4', '2026-02-25', 4),
              (5, 'e2', '5', 'E', 'e', 15, 'G5', 'SI',
               'senado_votaciones', 'https://example.test/v/5', '2026-02-25', 5),
              (6, 'e2', '6', 'F', 'f', 16, 'G6', 'NO',
               'senado_votaciones', 'https://example.test/v/6', '2026-02-25', 6);
            """
        )
        conn.commit()
        conn.close()

    def test_full_validation_and_incremental_partition_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "votes.db"
            self._database(db_path)
            audit_path = root / "audit.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "schema_version": "vote_database_audit_v2",
                        "current": {
                            "foreign_key_errors": 0,
                            "totals": {
                                "events_totals_available": 2,
                                "events_reconciled": 2,
                                "events_not_reconciled": 0,
                                "events_reconciled_pct": 1.0,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            first_root = root / "first"
            first = export_member_vote_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-02-25",
                row_group_rows=2,
                max_file_rows=3,
                vote_audit_path=audit_path,
                min_rows=6,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 6)
            self.assertEqual(first["totals"]["partitions"], 2)
            self.assertEqual(first["incremental_contract"]["partitions_rebuilt"], 2)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])

            validation = validate_semantic_partitions(root=first_root, min_rows=6)
            self.assertEqual(validation["status"], "ok")
            self.assertEqual(validation["totals"]["rows"], 6)

            second_root = root / "second"
            second = export_member_vote_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-02-26",
                row_group_rows=2,
                max_file_rows=3,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                vote_audit_path=audit_path,
                min_rows=6,
                enforce=True,
            )
            self.assertEqual(second["incremental_contract"]["partitions_reused"], 2)
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)
            self.assertEqual(
                validate_semantic_partitions(root=second_root, min_rows=6)["status"],
                "ok",
            )

            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE parl_vote_member_votes SET vote_choice = 'ABSTENCION' "
                "WHERE member_vote_id = 1"
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_member_vote_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-02-27",
                row_group_rows=2,
                max_file_rows=3,
                previous_manifest_path=second_root / "manifest.json",
                previous_root=second_root,
                vote_audit_path=audit_path,
                min_rows=6,
                enforce=True,
            )
            self.assertEqual(third["incremental_contract"]["partitions_reused"], 1)
            self.assertEqual(third["incremental_contract"]["partitions_rebuilt"], 1)
            self.assertEqual(
                validate_semantic_partitions(root=third_root, min_rows=6)["status"],
                "ok",
            )

    def test_enforced_gate_failure_does_not_promote_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "votes.db"
            output_root = root / "failed-output"
            self._database(db_path)

            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_member_vote_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-02-25",
                    row_group_rows=2,
                    max_file_rows=3,
                    min_rows=7,
                    enforce=True,
                )

            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
