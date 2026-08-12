from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.candidate_occurrence_partition_validation import (
    validate_candidate_occurrence_partitions,
)
from publicdata_publish.candidate_occurrence_partitions import (
    CANDIDATE_OCCURRENCE_CONTRACT,
    export_candidate_occurrence_partitions,
)

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


def _occurrence_id(
    election_type: str,
    year: int,
    month: int,
    election_round: str,
    province: str,
    district: str,
    scope: str,
    party_code: str,
    order: int,
    candidate_type: str,
) -> str:
    payload = json.dumps(
        (
            election_type,
            year,
            month,
            election_round,
            province,
            district,
            scope,
            party_code,
            order,
            candidate_type,
        ),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return "infoelectoral-candidate:" + hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestCandidateOccurrencePartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT NOT NULL
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_id TEXT NOT NULL
            );
            CREATE TABLE persons (
              person_id INTEGER PRIMARY KEY,
              full_name TEXT NOT NULL
            );
            CREATE TABLE parties (
              party_id INTEGER PRIMARY KEY,
              name TEXT NOT NULL
            );
            CREATE TABLE territories (
              territory_id INTEGER PRIMARY KEY,
              code TEXT NOT NULL
            );
            CREATE TABLE infoelectoral_candidate_archives (
              archive_id TEXT PRIMARY KEY,
              election_id TEXT NOT NULL
            );
            CREATE TABLE infoelectoral_candidate_occurrences (
              candidate_occurrence_id TEXT PRIMARY KEY,
              archive_id TEXT NOT NULL,
              election_date TEXT NOT NULL,
              election_type_code TEXT NOT NULL,
              election_year INTEGER NOT NULL,
              election_month INTEGER NOT NULL,
              election_round TEXT NOT NULL,
              province_code TEXT NOT NULL,
              district_code TEXT NOT NULL,
              candidate_scope_code TEXT NOT NULL,
              party_source_code TEXT NOT NULL,
              candidate_order INTEGER NOT NULL,
              candidate_type_code TEXT NOT NULL,
              given_name TEXT NOT NULL,
              surname_1 TEXT NOT NULL,
              surname_2 TEXT,
              full_name TEXT NOT NULL,
              gender_code TEXT,
              birth_date TEXT,
              birth_date_source TEXT,
              dni TEXT,
              is_elected INTEGER NOT NULL,
              candidacy_name TEXT NOT NULL,
              candidacy_acronym TEXT,
              party_province_code TEXT,
              party_autonomy_code TEXT,
              party_national_code TEXT,
              person_id INTEGER NOT NULL,
              party_id INTEGER NOT NULL,
              territory_id INTEGER,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
              source_url TEXT NOT NULL,
              source_content_sha256 TEXT NOT NULL,
              source_member_name TEXT NOT NULL,
              source_line_number INTEGER NOT NULL,
              first_seen_snapshot_date TEXT NOT NULL,
              last_seen_snapshot_date TEXT NOT NULL,
              is_present INTEGER NOT NULL
            );
            INSERT INTO sources VALUES (
              'infoelectoral_candidates',
              'https://infoelectoral.interior.gob.es/'
            );
            INSERT INTO persons VALUES
              (1, 'Ana Uno'), (2, 'Beto Dos'), (3, 'Cora Tres'),
              (4, 'Dani Cuatro'), (5, 'Eva Cinco');
            INSERT INTO parties VALUES (1, 'Partido Uno'), (2, 'Partido Dos');
            INSERT INTO territories VALUES (1, 'ES-PROV-28'), (2, 'ES');
            INSERT INTO infoelectoral_candidate_archives VALUES
              ('archive-muni-2023', '04-2023-05'),
              ('archive-congress-2023', '02-2023-07');
            """
        )
        rows = [
            ("04", 2023, 5, "1", "28", "1", "001", "000001", 1, "T", 1, 1, 1),
            ("04", 2023, 5, "1", "28", "1", "001", "000001", 2, "T", 2, 1, 0),
            ("04", 2023, 5, "1", "28", "1", "001", "000002", 1, "T", 3, 2, 1),
            ("02", 2023, 7, "1", "00", "1", "000", "000001", 1, "T", 4, 1, 0),
            ("02", 2023, 7, "1", "00", "1", "000", "000002", 1, "T", 5, 2, 0),
        ]
        names = [
            ("Ana", "Uno", None),
            ("Beto", "Dos", None),
            ("Cora", "Tres", None),
            ("Dani", "Cuatro", None),
            ("Eva", "Cinco", None),
        ]
        for index, row in enumerate(rows, start=1):
            (
                election_type,
                year,
                month,
                election_round,
                province,
                district,
                scope,
                party_code,
                order,
                candidate_type,
                person_id,
                party_id,
                elected,
            ) = row
            occurrence_id = _occurrence_id(
                election_type,
                year,
                month,
                election_round,
                province,
                district,
                scope,
                party_code,
                order,
                candidate_type,
            )
            conn.execute(
                "INSERT INTO source_records VALUES (?, ?, ?)",
                (100 + index, "infoelectoral_candidates", occurrence_id),
            )
            given_name, surname_1, surname_2 = names[index - 1]
            archive_id = (
                "archive-muni-2023"
                if election_type == "04"
                else "archive-congress-2023"
            )
            election_date = "2023-05-28" if election_type == "04" else "2023-07-23"
            values = (
                    occurrence_id,
                    archive_id,
                    election_date,
                    election_type,
                    year,
                    month,
                    election_round,
                    province,
                    district,
                    scope,
                    party_code,
                    order,
                    candidate_type,
                    given_name,
                    surname_1,
                    surname_2,
                    " ".join(item for item in (given_name, surname_1, surname_2) if item),
                    "female" if index in {1, 3, 5} else "male",
                    "1980-01-01",
                    "01011980",
                    f"official-id-{index}",
                    elected,
                    "Partido Uno" if party_id == 1 else "Partido Dos",
                    "P1" if party_id == 1 else "P2",
                    province or None,
                    None,
                    "N1" if party_id == 1 else "N2",
                    person_id,
                    party_id,
                    1 if election_type == "04" else 2,
                    "infoelectoral_candidates",
                    100 + index,
                    "https://infoelectoral.interior.gob.es/archive.zip",
                    "a" * 64,
                    "040202303.DAT" if election_type == "04" else "040202307.DAT",
                    index,
                    "2026-08-11",
                    "2026-08-11",
                    1,
                )
            conn.execute(
                "INSERT INTO infoelectoral_candidate_occurrences VALUES ("
                + ",".join(["?"] * len(values))
                + ")",
                values,
            )
        conn.commit()
        conn.close()

    def test_full_validation_and_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "candidates.db"
            self._database(db_path)
            first_root = root / "first"
            first = export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-08-11",
                row_group_rows=2,
                max_file_rows=2,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 5)
            self.assertEqual(first["totals"]["elected_rows"], 2)
            self.assertEqual(first["totals"]["partitions"], 2)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])
            self.assertIn("dni", CANDIDATE_OCCURRENCE_CONTRACT.columns)
            self.assertIn("birth_date", CANDIDATE_OCCURRENCE_CONTRACT.columns)
            self.assertIn("birth_date_source", CANDIDATE_OCCURRENCE_CONTRACT.columns)
            self.assertNotIn("raw_payload", CANDIDATE_OCCURRENCE_CONTRACT.columns)
            validated = validate_candidate_occurrence_partitions(
                root=first_root, min_rows=5
            )
            self.assertEqual(validated["status"], "ok")
            self.assertTrue(validated["checks"]["occurrence_ids_match_natural_key"])
            self.assertTrue(validated["checks"]["public_dni_retained_exactly"])

            second_root = root / "second"
            second = export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-08-12",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(second["incremental_contract"]["partitions_reused"], 2)
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)

            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE infoelectoral_candidate_occurrences SET candidacy_name = ? WHERE election_type_code = '04' LIMIT 1",
                ("Partido Uno Actualizado",),
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-08-13",
                row_group_rows=2,
                max_file_rows=2,
                previous_manifest_path=second_root / "manifest.json",
                previous_root=second_root,
                min_rows=5,
                enforce=True,
            )
            self.assertEqual(third["incremental_contract"]["partitions_reused"], 1)
            self.assertEqual(third["incremental_contract"]["partitions_rebuilt"], 1)
            self.assertEqual(
                validate_candidate_occurrence_partitions(root=third_root, min_rows=5)[
                    "status"
                ],
                "ok",
            )

    def test_enforced_failure_does_not_promote_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "candidates.db"
            output_root = root / "failed"
            self._database(db_path)
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_candidate_occurrence_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-08-11",
                    min_rows=6,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())

    def test_non_public_source_url_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "candidates.db"
            output_root = root / "unsafe"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE infoelectoral_candidate_occurrences SET source_url = ?",
                ("file:///Users/example/private/archive.zip",),
            )
            conn.commit()
            conn.close()
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_candidate_occurrence_partitions(
                    db_path=db_path,
                    output_root=output_root,
                    snapshot_date="2026-08-11",
                    min_rows=5,
                    enforce=True,
                )
            self.assertFalse(output_root.exists())

    def test_validator_rejects_tampered_manifest_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "candidates.db"
            output_root = root / "output"
            self._database(db_path)
            export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=output_root,
                snapshot_date="2026-08-11",
                min_rows=5,
                enforce=True,
            )
            manifest_path = output_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["totals"]["elected_rows"] = 0
            manifest["partitions"][0]["present_rows"] += 1
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            report = validate_candidate_occurrence_partitions(
                root=output_root, min_rows=5
            )
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["checks"]["manifest_metric_totals"])
            self.assertFalse(report["checks"]["partition_rows"])


if __name__ == "__main__":
    unittest.main()
