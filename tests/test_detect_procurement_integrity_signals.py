from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from publicdata_sqlite import open_db
from scripts.detect_procurement_integrity_signals import detect_threshold_patterns


class TestDetectProcurementIntegritySignals(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = open_db(Path(self.temp_dir.name) / "contracts.db")
        self.conn.executescript(
            """
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              content_sha256 TEXT NOT NULL
            );
            CREATE TABLE money_contract_records (
              contract_record_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk),
              source_record_id TEXT NOT NULL,
              source_url TEXT,
              contracting_authority TEXT,
              cpv_code TEXT,
              awarded_date TEXT,
              published_date TEXT,
              amount_eur REAL,
              amount_eur_decimal TEXT,
              stable_contract_id TEXT,
              entry_updated_at TEXT,
              source_snapshot_date TEXT,
              lot_id TEXT
            );
            CREATE TABLE money_contract_award_results (
              contract_award_result_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
              source_record_id TEXT NOT NULL,
              stable_contract_id TEXT NOT NULL,
              award_date TEXT,
              lot_id TEXT,
              supplier_identifier TEXT,
              amount_eur_decimal TEXT
            );
            """
        )
        rows = []
        for index, amount in enumerate((6_000.0, 5_500.0, 5_000.0), 1):
            url = f"https://official.example/contracts/{index}"
            self.conn.execute(
                "INSERT INTO source_records VALUES (?, ?)",
                (index, hashlib.sha256(url.encode()).hexdigest()),
            )
            rows.append(
                (
                    index,
                    "official-contracts",
                    index,
                    f"contract-{index}",
                    url,
                    "Authority A",
                    "12340000",
                    f"2026-02-{index:02d}",
                    None,
                    amount,
                )
            )
        self.conn.executemany(
            """
            INSERT INTO money_contract_records (
              contract_record_id, source_id, source_record_pk, source_record_id,
              source_url, contracting_authority, cpv_code, awarded_date,
              published_date, amount_eur
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_detector_creates_internal_review_signal_without_allegation(self) -> None:
        report = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
        )
        self.assertEqual(report["totals"]["signals_detected"], 1)
        self.assertEqual(report["totals"]["signals_persisted"], 1)
        self.assertEqual(report["totals"]["signals_materialized"], 1)
        self.assertEqual(report["totals"]["evidence_rows_materialized"], 3)
        self.assertFalse(report["safety"]["public_by_default"])
        self.assertFalse(report["safety"]["corruption_finding"])

        signal = self.conn.execute("SELECT * FROM integrity_signals").fetchone()
        self.assertEqual(signal["state"], "review_signal")
        self.assertEqual(signal["publication_status"], "internal")
        self.assertIn("not a finding", signal["summary"])
        self.assertEqual(signal["period_end"], "2026-02-28")
        evidence_total = int(
            self.conn.execute("SELECT COUNT(*) FROM integrity_signal_evidence").fetchone()[0]
        )
        self.assertEqual(evidence_total, 3)

        rerun = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
        )
        self.assertEqual(rerun["totals"]["signals_persisted"], 1)
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM integrity_signals").fetchone()[0]),
            1,
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM integrity_signal_evidence"
                ).fetchone()[0]
            ),
            3,
        )

    def test_dry_run_does_not_create_signal_tables(self) -> None:
        report = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
            persist=False,
        )
        self.assertEqual(report["status"], "dry_run")
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='integrity_signals'"
        ).fetchone()
        self.assertIsNone(exists)

    def test_detector_uses_awards_and_excludes_superseded_contract_versions(self) -> None:
        self.conn.execute(
            """
            UPDATE money_contract_records
            SET stable_contract_id = 'stable-' || contract_record_id,
                entry_updated_at = '2026-02-10T00:00:00Z'
            """
        )
        for index, amount in enumerate(("6000.00", "5500.00", "5000.00"), 1):
            self.conn.execute(
                """
                INSERT INTO money_contract_award_results (
                  contract_award_result_id, source_id, source_record_pk,
                  source_record_id, stable_contract_id, award_date, lot_id,
                  supplier_identifier, amount_eur_decimal
                ) VALUES (?, 'official-contracts', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    index,
                    index,
                    f"contract-{index}",
                    f"stable-{index}",
                    f"2026-02-{index:02d}",
                    f"lot-{index}",
                    f"supplier-{index}",
                    amount,
                ),
            )
        old_url = "https://official.example/contracts/1/old"
        self.conn.execute(
            "INSERT INTO source_records VALUES (4, ?)",
            (hashlib.sha256(old_url.encode()).hexdigest(),),
        )
        self.conn.execute(
            """
            INSERT INTO money_contract_records (
              contract_record_id, source_id, source_record_pk, source_record_id,
              source_url, contracting_authority, cpv_code, awarded_date,
              amount_eur, amount_eur_decimal, stable_contract_id, entry_updated_at
            ) VALUES (
              4, 'official-contracts', 4, 'contract-1-old', ?, 'Authority A',
              '12340000', '2026-02-01', 7000.0, '7000.00', 'stable-1',
              '2026-02-01T00:00:00Z'
            )
            """,
            (old_url,),
        )
        self.conn.commit()

        report = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
            persist=False,
        )

        self.assertEqual(
            report["evidence_basis"],
            "latest_contract_versions_with_award_results_preferred",
        )
        self.assertEqual(report["totals"]["matched_contract_rows"], 3)
        self.assertEqual(report["samples"][0]["records"], 3)
        self.assertEqual(report["samples"][0]["amount_eur"], 16_500.0)

    def test_detector_fingerprints_revisions_and_supersedes_missing_pattern(self) -> None:
        first = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
            supersede_missing=True,
        )
        first_signal_id = str(first["samples"][0]["signal_id"])

        self.conn.execute(
            "UPDATE money_contract_records SET amount_eur = 7000.0 WHERE contract_record_id = 1"
        )
        self.conn.commit()
        second = detect_threshold_patterns(
            self.conn,
            threshold_eur=15_000.0,
            min_records=3,
            supersede_missing=True,
        )

        self.assertNotEqual(second["samples"][0]["signal_id"], first_signal_id)
        self.assertEqual(second["totals"]["signals_superseded_missing"], 1)
        old = self.conn.execute(
            "SELECT state, publication_status FROM integrity_signals WHERE signal_id = ?",
            (first_signal_id,),
        ).fetchone()
        self.assertEqual((old["state"], old["publication_status"]), ("superseded", "withdrawn"))
        self.assertEqual(second["totals"]["signals_materialized"], 1)


if __name__ == "__main__":
    unittest.main()
