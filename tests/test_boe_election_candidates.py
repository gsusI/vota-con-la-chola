from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from etl.politicos_es.db import apply_schema
from publicdata_connectors_es.elections.boe_candidates import (
    BoeCandidateParseError,
    parse_boe_candidate_correction,
    parse_boe_candidate_document,
)
from publicdata_publish.candidate_occurrence_partition_validation import (
    validate_candidate_occurrence_partitions,
)
from publicdata_publish.candidate_occurrence_partitions import (
    export_candidate_occurrence_partitions,
)
from publicdata_sqlite import open_db
from scripts.ingest_boe_election_candidates import parse_args, run
from scripts.materialize_boe_candidate_corrections import (
    parse_args as parse_materialize_args,
)
from scripts.materialize_boe_candidate_corrections import (
    run as materialize_run,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = ROOT / "etl/data/staging/politicos-es.db"
try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None
EUROPEAN_SHA256 = "76ce3855a65f55a760509fa7d1ae63e895703f7e2151345256d295aeb83da23f"
EUROPEAN_PATH = (
    ROOT
    / "etl/data/raw/text_documents/boe_document_xml/76/ce/"
    / f"{EUROPEAN_SHA256}.xml"
)
EUROPEAN_CORRECTION_SHA256 = (
    "897f130a66de54db2d07eb1e0b8576af0838c4922da2f7191a2c7976df5061dc"
)
EUROPEAN_CORRECTION_PATH = (
    ROOT
    / "etl/data/raw/text_documents/boe_document_xml/89/7f/"
    / f"{EUROPEAN_CORRECTION_SHA256}.xml"
)
GENERAL_SHA256 = "0fbc2de13c0f2ae9707c631828687657b62142523d7054f42e6b116a6a647d84"
GENERAL_PATH = (
    ROOT
    / "etl/data/raw/text_documents/boe_document_xml/0f/bc/"
    / f"{GENERAL_SHA256}.xml"
)
GENERAL_CORRECTION_PATHS = (
    ROOT
    / "etl/data/raw/text_documents/boe_document_xml/d1/2f/"
    / "d12f14ff69a8573c3a1afcd2f8c20791b842a24c9b91752bdd68c3a1fbaff8d5.xml",
    ROOT
    / "etl/data/raw/text_documents/boe_document_xml/4e/8b/"
    / "4e8bc5226c167bca77b4c7ee84ffb6dc56b046d4f32c37d32db4e291a996640f.xml",
)

CURRENT_COHORT_PATHS = {
    "BOE-A-2023-15066": GENERAL_PATH,
    "BOE-A-2023-15548": GENERAL_CORRECTION_PATHS[0],
    "BOE-A-2023-15828": GENERAL_CORRECTION_PATHS[1],
    "BOE-A-2024-9687": EUROPEAN_PATH,
    "BOE-A-2024-10230": (
        ROOT
        / "etl/data/raw/text_documents/boe_document_xml/dc/b9/"
        / "dcb9a2060927227c420dabe03be309106b1ccf33b6b451d2f7cc66fae106f814.xml"
    ),
    "BOE-A-2024-10569": EUROPEAN_CORRECTION_PATH,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BoeElectionCandidateTests(unittest.TestCase):
    def test_exact_real_historical_proclamations_parse(self) -> None:
        expected = {
            "BOE-A-2015-12734": (1_282, 10_498, 5_830, 4_668, 31),
            "BOE-A-2016-5186": (1_165, 9_258, 5_134, 4_124, 39),
            "BOE-A-2019-4902": (1_234, 9_578, 5_425, 4_153, 49),
            "BOE-A-2019-6475": (32, 1_907, 1_728, 179, 0),
        }
        connection = sqlite3.connect(PRODUCTION_DB)
        connection.row_factory = sqlite3.Row
        try:
            for document_id, totals in expected.items():
                row = connection.execute(
                    """
                    SELECT raw_path
                    FROM text_documents
                    WHERE source_id='boe_document_xml' AND source_url=?
                    """,
                    ("https://www.boe.es/diario_boe/xml.php?id=" + document_id,),
                ).fetchone()
                if row is None:
                    self.skipTest(f"real BOE document unavailable: {document_id}")
                parsed = parse_boe_candidate_document(ROOT / str(row["raw_path"]))
                candidate_types = Counter(
                    item.candidate_type_code for item in parsed.candidates
                )
                statuses = Counter(
                    item.proclamation_status for item in parsed.candidacies
                )
                observed = (
                    len(parsed.candidacies),
                    len(parsed.candidates),
                    candidate_types["titular"],
                    candidate_types["suplente"],
                    statuses["not_proclaimed"],
                )
                self.assertEqual(observed, totals, document_id)
        finally:
            connection.close()

    def test_malformed_real_2019_november_heading_fails_closed(self) -> None:
        connection = sqlite3.connect(PRODUCTION_DB)
        try:
            row = connection.execute(
                """
                SELECT raw_path
                FROM text_documents
                WHERE source_id='boe_document_xml'
                  AND source_url LIKE '%id=BOE-A-2019-14801'
                """
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            self.skipTest("real 2019-11 BOE proclamation is unavailable")
        with self.assertRaisesRegex(
            BoeCandidateParseError, "candidacy heading has no official number"
        ):
            parse_boe_candidate_document(ROOT / str(row[0]))

    def _create_current_cohort_db(self, db_path: Path) -> None:
        if not all(path.is_file() for path in CURRENT_COHORT_PATHS.values()):
            self.skipTest("exact official BOE candidate cohort is unavailable")
        conn = open_db(db_path)
        apply_schema(conn, ROOT / "etl/load/sqlite_schema.sql")
        now = "2026-08-13T00:00:00Z"
        conn.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "boe_document_xml",
                "Documentos individuales oficiales del BOE",
                "nacional",
                "https://www.boe.es/diario_boe/xml.php",
                "xml",
                1,
                now,
                now,
            ),
        )
        for document_id, path in CURRENT_COHORT_PATHS.items():
            source_url = "https://www.boe.es/diario_boe/xml.php?id=" + document_id
            source_sha256 = _sha256(path)
            conn.execute(
                """
                INSERT INTO source_records (
                  source_id, source_record_id, source_snapshot_date,
                  raw_payload, content_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    source_url,
                    "2026-08-13",
                    '{"url":"'
                    + source_url
                    + '","synthetic_or_mock_records_counted":false}',
                    source_sha256,
                    now,
                    now,
                ),
            )
            source_record_pk = int(
                conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO text_documents (
                  source_id, source_url, source_record_pk, fetched_at,
                  content_type, content_sha256, bytes, raw_path,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    source_url,
                    source_record_pk,
                    now,
                    "application/xml",
                    source_sha256,
                    path.stat().st_size,
                    str(path.relative_to(ROOT)),
                    now,
                    now,
                ),
            )
        conn.commit()
        conn.close()
        ingest_args = parse_args(
            [
                "--db",
                str(db_path),
                "--schema",
                str(ROOT / "etl/load/sqlite_schema.sql"),
                "--snapshot-date",
                "2026-08-13",
                "--boe-id",
                "BOE-A-2023-15066",
                "--boe-id",
                "BOE-A-2024-9687",
                "--boe-id",
                "BOE-A-2024-10230",
                "--report-out",
                str(db_path.with_suffix(".ingest.json")),
                "--enforce",
            ]
        )
        self.assertEqual(run(ingest_args)["status"], "ok")

    def test_exact_real_european_proclamation_parses(self) -> None:
        if not EUROPEAN_PATH.is_file():
            self.skipTest("exact official BOE-A-2024-9687 capture is unavailable")
        self.assertEqual(_sha256(EUROPEAN_PATH), EUROPEAN_SHA256)
        parsed = parse_boe_candidate_document(EUROPEAN_PATH)
        self.assertEqual(parsed.document.document_id, "BOE-A-2024-9687")
        self.assertEqual(parsed.document.correction_refs, ("BOE-A-2024-10569",))
        self.assertEqual(len(parsed.candidacies), 33)
        self.assertEqual(len(parsed.candidates), 2_206)
        self.assertEqual(
            Counter(row.candidate_type_code for row in parsed.candidates),
            {"titular": 2_013, "suplente": 193},
        )
        self.assertEqual(parsed.candidates[0].full_name, "Guillermo del Valle Alcalá")
        self.assertEqual(
            parsed.candidates[0].source_text_exact,
            "1.\u2003Guillermo del Valle Alcalá.",
        )

    def test_exact_real_general_proclamation_parses(self) -> None:
        if not GENERAL_PATH.is_file():
            self.skipTest("exact official BOE-A-2023-15066 capture is unavailable")
        self.assertEqual(_sha256(GENERAL_PATH), GENERAL_SHA256)
        parsed = parse_boe_candidate_document(GENERAL_PATH)
        self.assertEqual(parsed.document.document_id, "BOE-A-2023-15066")
        self.assertEqual(len(parsed.candidacies), 1_154)
        self.assertEqual(len(parsed.candidates), 8_548)
        self.assertEqual(
            Counter(row.proclamation_status for row in parsed.candidacies),
            {"proclaimed": 1_088, "not_proclaimed": 66},
        )
        self.assertEqual(
            Counter(row.candidate_type_code for row in parsed.candidates),
            {"titular": 4_886, "suplente": 3_662},
        )
        self.assertEqual(
            Counter(row.chamber_code for row in parsed.candidates),
            {"CONGRESS": 5_095, "SENATE": 3_453},
        )

    def test_exact_real_general_corrections_remain_unabridged(self) -> None:
        if not all(path.is_file() for path in GENERAL_CORRECTION_PATHS):
            self.skipTest("exact official 2023 BOE correction captures are unavailable")
        parsed = [
            parse_boe_candidate_correction(path) for path in GENERAL_CORRECTION_PATHS
        ]
        self.assertEqual(
            [item.document.document_id for item in parsed],
            ["BOE-A-2023-15548", "BOE-A-2023-15828"],
        )
        self.assertEqual([len(item.paragraphs) for item in parsed], [46, 25])
        self.assertTrue(
            all(
                paragraph.source_text_exact
                for item in parsed
                for paragraph in item.paragraphs
            )
        )

    def test_real_document_ingestion_is_set_based_and_idempotent(self) -> None:
        if not EUROPEAN_PATH.is_file() or not EUROPEAN_CORRECTION_PATH.is_file():
            self.skipTest("exact official BOE candidate captures are unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "candidates.db"
            conn = open_db(db_path)
            apply_schema(conn, ROOT / "etl/load/sqlite_schema.sql")
            now = "2026-08-13T00:00:00Z"
            url = "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-9687"
            conn.execute(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "boe_document_xml",
                    "Documentos individuales oficiales del BOE",
                    "nacional",
                    "https://www.boe.es/diario_boe/xml.php",
                    "xml",
                    1,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO source_records (
                  source_id, source_record_id, source_snapshot_date,
                  raw_payload, content_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    url,
                    "2026-08-13",
                    '{"url":"' + url + '","synthetic_or_mock_records_counted":false}',
                    EUROPEAN_SHA256,
                    now,
                    now,
                ),
            )
            source_record_pk = int(
                conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO text_documents (
                  source_id, source_url, source_record_pk, fetched_at,
                  content_type, content_sha256, bytes, raw_path,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    url,
                    source_record_pk,
                    now,
                    "application/xml",
                    EUROPEAN_SHA256,
                    EUROPEAN_PATH.stat().st_size,
                    str(EUROPEAN_PATH.relative_to(ROOT)),
                    now,
                    now,
                ),
            )
            correction_url = "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-10569"
            conn.execute(
                """
                INSERT INTO source_records (
                  source_id, source_record_id, source_snapshot_date,
                  raw_payload, content_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    correction_url,
                    "2026-08-13",
                    '{"url":"'
                    + correction_url
                    + '","synthetic_or_mock_records_counted":false}',
                    EUROPEAN_CORRECTION_SHA256,
                    now,
                    now,
                ),
            )
            correction_source_record_pk = int(
                conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO text_documents (
                  source_id, source_url, source_record_pk, fetched_at,
                  content_type, content_sha256, bytes, raw_path,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "boe_document_xml",
                    correction_url,
                    correction_source_record_pk,
                    now,
                    "application/xml",
                    EUROPEAN_CORRECTION_SHA256,
                    EUROPEAN_CORRECTION_PATH.stat().st_size,
                    str(EUROPEAN_CORRECTION_PATH.relative_to(ROOT)),
                    now,
                    now,
                ),
            )
            conn.commit()
            conn.close()

            args = parse_args(
                [
                    "--db",
                    str(db_path),
                    "--schema",
                    str(ROOT / "etl/load/sqlite_schema.sql"),
                    "--boe-id",
                    "BOE-A-2024-9687",
                    "--snapshot-date",
                    "2026-08-13",
                    "--enforce",
                ]
            )
            first = run(args)
            second = run(args)
            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")

            conn = sqlite3.connect(
                f"file:{db_path}?mode=ro",
                uri=True,
            )
            try:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_occurrences"
                    ).fetchone()[0],
                    2_206,
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM source_records
                        WHERE source_id='boe_election_candidates'
                        """
                    ).fetchone()[0],
                    2_206,
                )
                self.assertEqual(
                    conn.execute("PRAGMA foreign_key_check").fetchall(), []
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidate_correction_paragraphs
                        WHERE correction_document_id='BOE-A-2024-10569'
                        """
                    ).fetchone()[0],
                    109,
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT application_state
                        FROM boe_election_candidate_correction_documents
                        WHERE correction_document_id='BOE-A-2024-10569'
                        """
                    ).fetchone()[0],
                    "captured_unapplied",
                )
            finally:
                conn.close()

    def test_exact_real_corrections_materialize_without_mutating_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "corrected-candidates.db"
            self._create_current_cohort_db(db_path)
            args = parse_materialize_args(
                [
                    "--db",
                    str(db_path),
                    "--schema",
                    str(ROOT / "etl/load/sqlite_schema.sql"),
                    "--report-out",
                    str(Path(temporary) / "corrections.json"),
                    "--enforce",
                ]
            )
            first = materialize_run(args)
            second = materialize_run(args)
            self.assertEqual(first["status"], "ok")
            self.assertEqual(first["totals"], second["totals"])
            self.assertEqual(first["totals"]["correction_operations"], 17)
            self.assertEqual(first["totals"]["base_candidates"], 10_815)
            self.assertEqual(first["totals"]["effective_candidates"], 10_820)
            self.assertEqual(first["totals"]["correction_paragraphs_retained"], 180)
            self.assertEqual(
                first["totals"]["correction_paragraphs_referenced_by_operations"],
                127,
            )
            self.assertEqual(
                first["totals"]["contextual_correction_paragraphs_retained"], 53
            )
            self.assertEqual(first["totals"]["partial_base_match_operations"], 1)

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_occurrences"
                    ).fetchone()[0],
                    10_815,
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidate_correction_documents
                        WHERE application_state='applied'
                        """
                    ).fetchone()[0],
                    3,
                )
                base_name = conn.execute(
                    """
                    SELECT full_name FROM boe_election_candidate_occurrences
                    WHERE document_id='BOE-A-2023-15066'
                      AND electoral_board='JUNTA ELECTORAL DE BALEARES'
                      AND chamber_code='CONGRESS' AND candidacy_number=8
                      AND candidate_type_code='titular' AND candidate_order=8
                    """
                ).fetchone()[0]
                effective_name = conn.execute(
                    """
                    SELECT full_name
                    FROM boe_election_effective_candidate_occurrences
                    WHERE base_document_id='BOE-A-2023-15066'
                      AND electoral_board='JUNTA ELECTORAL DE BALEARES'
                      AND chamber_code='CONGRESS' AND candidacy_number=8
                      AND candidate_type_code='titular' AND candidate_order=8
                    """
                ).fetchone()[0]
                self.assertEqual(base_name, "María Juana Fernández López «Alcorocho»")
                self.assertEqual(
                    effective_name, "María Juana Fernández López-Alcorocho"
                )
                teruel = conn.execute(
                    """
                    SELECT base.proclamation_status AS base_status,
                           effective.proclamation_status AS effective_status,
                           COUNT(candidate.effective_candidate_occurrence_id) AS rows
                    FROM boe_election_candidacies AS base
                    JOIN boe_election_effective_candidacies AS effective
                      ON effective.candidacy_id=base.candidacy_id
                    LEFT JOIN boe_election_effective_candidate_occurrences AS candidate
                      ON candidate.candidacy_id=effective.candidacy_id
                    WHERE base.document_id='BOE-A-2023-15066'
                      AND base.electoral_board='JUNTA ELECTORAL DE TERUEL'
                      AND base.chamber_code='CONGRESS'
                      AND base.candidacy_number=13
                    GROUP BY base.candidacy_id
                    """
                ).fetchone()
                self.assertEqual(
                    (teruel["base_status"], teruel["effective_status"], teruel["rows"]),
                    ("not_proclaimed", "proclaimed", 4),
                )
                luke = conn.execute(
                    """
                    SELECT full_name
                    FROM boe_election_effective_candidate_occurrences
                    WHERE base_document_id='BOE-A-2024-9687'
                      AND candidacy_number=2 AND candidate_type_code='titular'
                      AND candidate_order=13
                    """
                ).fetchone()[0]
                self.assertEqual(luke, "Luke Uribe-Etxeberria Apalategi (EAJ-PNV)")
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_effective_candidate_occurrences
                        WHERE base_document_id='BOE-A-2024-9687'
                          AND candidacy_number=11
                          AND candidate_type_code='suplente'
                        """
                    ).fetchone()[0],
                    9,
                )
                self.assertEqual(
                    conn.execute("PRAGMA foreign_key_check").fetchall(), []
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_effective_candidate_occurrences
                        WHERE person_id IS NOT NULL AND party_id IS NOT NULL
                          AND source_id='boe_election_candidates'
                          AND source_record_pk IS NOT NULL
                          AND document_source_record_pk IS NOT NULL
                          AND first_seen_snapshot_date='2026-08-13'
                          AND last_seen_snapshot_date='2026-08-13'
                          AND is_present=1
                        """
                    ).fetchone()[0],
                    10_820,
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_effective_candidate_occurrences
                        WHERE correction_operation_id IS NOT NULL
                          AND person_identity_state=
                              'source_scoped_correction_exact'
                        """
                    ).fetchone()[0],
                    88,
                )
            finally:
                conn.close()

            self.assertEqual(
                run(
                    parse_args(
                        [
                            "--db",
                            str(db_path),
                            "--boe-id",
                            "BOE-A-2023-15066",
                            "--boe-id",
                            "BOE-A-2024-9687",
                            "--boe-id",
                            "BOE-A-2024-10230",
                            "--enforce",
                        ]
                    )
                )["status"],
                "ok",
            )
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidate_documents
                        WHERE correction_state='applied'
                        """
                    ).fetchone()[0],
                    3,
                )
            finally:
                conn.close()

    @unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
    def test_real_effective_cohort_exports_validated_incremental_partitions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db_path = root / "effective-candidates.db"
            self._create_current_cohort_db(db_path)
            materialize = materialize_run(
                parse_materialize_args(
                    [
                        "--db",
                        str(db_path),
                        "--schema",
                        str(ROOT / "etl/load/sqlite_schema.sql"),
                        "--snapshot-date",
                        "2026-08-13",
                        "--report-out",
                        str(root / "corrections.json"),
                        "--enforce",
                    ]
                )
            )
            self.assertEqual(materialize["status"], "ok")

            first_root = root / "first"
            first = export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-08-13",
                row_group_rows=1_000,
                max_file_rows=2_000,
                min_rows=10_820,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 10_820)
            self.assertEqual(first["totals"]["boe_rows"], 10_820)
            self.assertEqual(first["totals"]["correction_backed_rows"], 88)
            self.assertEqual(first["totals"]["exact_public_name_rows"], 10_820)
            self.assertEqual(first["totals"]["exact_source_text_rows"], 10_820)
            self.assertEqual(first["totals"]["outcome_known_rows"], 0)
            self.assertEqual(first["totals"]["partitions"], 2)
            validated = validate_candidate_occurrence_partitions(
                root=first_root, min_rows=10_820
            )
            self.assertEqual(validated["status"], "ok")
            self.assertTrue(validated["checks"]["boe_election_outcomes_not_inferred"])
            self.assertTrue(validated["checks"]["public_names_retained_exactly"])
            self.assertTrue(validated["checks"]["boe_correction_lineage_retained"])

            second_root = root / "second"
            second = export_candidate_occurrence_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-08-14",
                row_group_rows=1_000,
                max_file_rows=2_000,
                previous_manifest_path=first_root / "manifest.json",
                previous_root=first_root,
                min_rows=10_820,
                enforce=True,
            )
            self.assertEqual(second["incremental_contract"]["partitions_reused"], 2)
            self.assertEqual(second["incremental_contract"]["partitions_rebuilt"], 0)
            self.assertEqual(
                validate_candidate_occurrence_partitions(
                    root=second_root, min_rows=10_820
                )["status"],
                "ok",
            )

            manifest_path = second_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["totals"]["correction_backed_rows"] = 0
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            tampered = validate_candidate_occurrence_partitions(
                root=second_root, min_rows=10_820
            )
            self.assertEqual(tampered["status"], "failed")
            self.assertFalse(tampered["checks"]["manifest_metric_totals"])


if __name__ == "__main__":
    unittest.main()
