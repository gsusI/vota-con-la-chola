from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.actor_mandate_partition_validation import (
    validate_actor_mandate_partitions,
)
from publicdata_publish.actor_mandate_partitions import (
    export_actor_mandate_partitions,
)

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestActorMandatePartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT NOT NULL
            );
            CREATE TABLE persons (
              person_id INTEGER PRIMARY KEY,
              full_name TEXT NOT NULL,
              given_name TEXT,
              family_name TEXT,
              gender TEXT,
              gender_id INTEGER,
              birth_date TEXT,
              canonical_key TEXT NOT NULL
            );
            CREATE TABLE person_identifiers (
              person_identifier_id INTEGER PRIMARY KEY,
              person_id INTEGER NOT NULL,
              namespace TEXT NOT NULL,
              value TEXT NOT NULL
            );
            CREATE TABLE person_name_aliases (
              person_name_alias_id INTEGER PRIMARY KEY,
              person_id INTEGER NOT NULL,
              alias TEXT NOT NULL,
              canonical_alias TEXT NOT NULL
            );
            CREATE TABLE institutions (
              institution_id INTEGER PRIMARY KEY,
              name TEXT NOT NULL
            );
            CREATE TABLE parties (
              party_id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              acronym TEXT
            );
            CREATE TABLE roles (
              role_id INTEGER PRIMARY KEY,
              title TEXT NOT NULL
            );
            CREATE TABLE admin_levels (
              admin_level_id INTEGER PRIMARY KEY,
              code TEXT NOT NULL
            );
            CREATE TABLE genders (
              gender_id INTEGER PRIMARY KEY,
              code TEXT NOT NULL
            );
            CREATE TABLE mandates (
              mandate_id INTEGER PRIMARY KEY,
              person_id INTEGER NOT NULL,
              institution_id INTEGER NOT NULL,
              party_id INTEGER,
              role_title TEXT NOT NULL,
              role_id INTEGER,
              level TEXT NOT NULL,
              admin_level_id INTEGER,
              territory_code TEXT NOT NULL,
              territory_id INTEGER,
              start_date TEXT,
              end_date TEXT,
              is_active INTEGER NOT NULL,
              source_id TEXT NOT NULL,
              source_record_id TEXT NOT NULL,
              source_record_pk INTEGER,
              source_snapshot_date TEXT
            );
            INSERT INTO sources VALUES
              ('congreso', 'https://example.test/congreso'),
              ('municipios', 'https://example.test/municipios');
            INSERT INTO genders VALUES (1, 'female'), (2, 'male');
            INSERT INTO persons VALUES
              (1, 'Ana Uno', 'Ana', 'Uno', NULL, 1, '1980-01-01', 'ana-uno'),
              (2, 'Beto Dos', 'Beto', 'Dos', 'male', NULL, NULL, 'beto-dos'),
              (3, 'Cora Tres', NULL, NULL, NULL, NULL, NULL, 'cora-tres'),
              (4, 'Dani Cuatro', NULL, NULL, NULL, NULL, NULL, 'dani-cuatro');
            INSERT INTO person_identifiers VALUES
              (1, 1, 'congreso', 'A-1'),
              (2, 1, 'wikidata', 'Q1');
            INSERT INTO person_name_aliases VALUES
              (1, 1, 'A. Uno', 'a uno'),
              (2, 3, 'C. Tres', 'c tres');
            INSERT INTO institutions VALUES
              (1, 'Congress'),
              (2, 'Town Hall');
            INSERT INTO parties VALUES (1, 'Example Party', 'EP');
            INSERT INTO roles VALUES (1, 'Member'), (2, 'Mayor');
            INSERT INTO admin_levels VALUES (1, 'national'), (2, 'municipal');
            INSERT INTO mandates VALUES
              (1, 1, 1, 1, 'MP', 1, 'Nacional', 1, 'ES', NULL,
               '2024-01-01', NULL, 1, 'congreso', 'm1', 101, '2026-02-12'),
              (2, 2, 1, 1, 'MP', 1, 'Nacional', 1, 'ES', NULL,
               '2024-01-01', NULL, 1, 'congreso', 'm2', 102, '2026-02-12'),
              (3, 3, 1, NULL, 'MP', NULL, 'Nacional', 1, 'ES', NULL,
               NULL, NULL, 0, 'congreso', 'm3', NULL, '2025-02-12'),
              (4, 4, 2, NULL, 'Mayor', 2, 'Municipal', 2, 'ES-MAD-001', NULL,
               '2023-05-01', '2027-05-01', 1, 'municipios', 'm4', NULL,
               '2026-02-12'),
              (5, 1, 2, 1, 'Councillor', NULL, 'Municipal', 2,
               'ES-MAD-001', NULL, '2023-05-01', NULL, 1, 'municipios',
               'm5', NULL, '2026-02-12');
            """
        )
        conn.commit()
        conn.close()

    def test_full_validation_and_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "actors.db"
            self._database(db_path)
            first_root = root / "first"
            first = export_actor_mandate_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-02-25",
                row_group_rows=2,
                max_file_rows=2,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 5)
            self.assertEqual(first["totals"]["source_identifier_rows"], 2)
            self.assertEqual(first["totals"]["source_record_identity_rows"], 1)
            self.assertEqual(first["totals"]["alias_only_rows"], 1)
            self.assertEqual(first["totals"]["observed_label_only_rows"], 1)
            self.assertEqual(first["totals"]["lineage_rows"], 5)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])
            validated = validate_actor_mandate_partitions(root=first_root, min_rows=5)
            self.assertEqual(validated["status"], "ok")
            self.assertTrue(validated["checks"]["identity_lists_valid"])

            second_root = root / "second"
            second = export_actor_mandate_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-02-26",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(
                second["incremental_contract"]["partitions_reused"],
                first["totals"]["partitions"],
            )
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE person_name_aliases SET alias = 'Cora T.' WHERE person_id = 3"
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_actor_mandate_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-02-27",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=second_root / "manifest.json",
                previous_root=second_root,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(third["incremental_contract"]["partitions_rebuilt"], 1)
            self.assertEqual(
                third["incremental_contract"]["partitions_reused"],
                first["totals"]["partitions"] - 1,
            )
            self.assertEqual(
                validate_actor_mandate_partitions(root=third_root, min_rows=5)[
                    "status"
                ],
                "ok",
            )

    def test_enforced_failure_does_not_promote_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "actors.db"
            output_root = root / "failed"
            self._database(db_path)
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_actor_mandate_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-02-25",
                    min_rows=6,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())

    def test_nested_private_identity_value_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "actors.db"
            output_root = root / "unsafe"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO person_name_aliases VALUES (3, 4, ?, 'unsafe')",
                ("/Users/example/private",),
            )
            conn.commit()
            conn.close()
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_actor_mandate_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-02-25",
                    min_rows=5,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())

    def test_validator_rejects_tampered_manifest_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "actors.db"
            output_root = root / "output"
            self._database(db_path)
            export_actor_mandate_partitions(
                db_path=db_path,
                output_root=output_root,
                snapshot_date="2026-02-25",
                min_rows=5,
                enforce=True,
            )
            manifest_path = output_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["totals"]["alias_only_rows"] = 0
            manifest["partitions"][0]["active_rows"] += 1
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            report = validate_actor_mandate_partitions(root=output_root, min_rows=5)
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["checks"]["manifest_metric_totals"])
            self.assertFalse(report["checks"]["partition_rows"])


if __name__ == "__main__":
    unittest.main()
