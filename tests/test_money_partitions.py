from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.money_partition_validation import validate_money_partitions
from publicdata_publish.money_partitions import _iter_rows, export_money_partitions

try:
    import pyarrow
    import pyarrow.parquet as pq
except ModuleNotFoundError:
    pyarrow = None


@unittest.skipIf(pyarrow is None, "pyarrow optional dependency is not installed")
class TestMoneyPartitions(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              default_url TEXT NOT NULL
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY
            );
            CREATE TABLE money_contract_records (
              contract_record_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
              source_record_id TEXT NOT NULL,
              source_snapshot_date TEXT,
              source_url TEXT,
              contract_id TEXT,
              lot_id TEXT,
              notice_type TEXT,
              cpv_code TEXT,
              cpv_label TEXT,
              contracting_authority TEXT,
              procedure_type TEXT,
              territory_code TEXT,
              published_date TEXT,
              awarded_date TEXT,
              amount_eur REAL,
              currency TEXT,
              stable_contract_id TEXT,
              entry_updated_at TEXT,
              amount_eur_decimal TEXT,
              amount_semantics TEXT,
              contract_status_code TEXT
            );
            CREATE TABLE money_contract_award_results (
              contract_award_result_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
              source_record_id TEXT NOT NULL,
              stable_contract_id TEXT NOT NULL,
              lot_id TEXT,
              award_date TEXT,
              supplier_name TEXT,
              supplier_identifier TEXT,
              amount_eur_decimal TEXT,
              currency TEXT
            );
            CREATE TABLE money_subsidy_records (
              subsidy_record_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
              source_record_id TEXT NOT NULL,
              source_snapshot_date TEXT,
              source_url TEXT,
              call_id TEXT,
              grant_id TEXT,
              granting_body TEXT,
              beneficiary_name TEXT,
              beneficiary_identifier TEXT,
              program_code TEXT,
              territory_code TEXT,
              published_date TEXT,
              concession_date TEXT,
              amount_eur REAL,
              currency TEXT
            );
            INSERT INTO sources VALUES
              ('placsp_sindicacion', 'https://example.test/contracts'),
              ('placsp_autonomico', 'https://example.test/contracts-regional'),
              ('bdns_api_subvenciones', 'https://example.test/subsidies'),
              ('bdns_autonomico', 'https://example.test/subsidies-regional');
            INSERT INTO source_records VALUES (1), (2), (3), (4), (5), (6);
            INSERT INTO money_contract_records VALUES
              (1, 'placsp_sindicacion', 1, 'c1', '2026-02-12',
               'https://example.test/contracts/1', 'CON-1', NULL, 'notice',
               '12345678', 'Roads', 'Ministry A', 'open', NULL,
               '2024-01-01', NULL, 100.25, 'eur', 'contract:1',
               '2024-01-01T00:00:00Z', '100.25',
               'estimated_overall_contract_amount', 'PUB'),
              (2, 'placsp_sindicacion', 2, 'c2', '2026-02-12',
               'file:///Users/example/private.xml', 'CON-2', 'L1', 'award',
               '87654321', 'Software', 'Ministry B', 'restricted', NULL,
               '2025-01-01', '2025-02-01', 200.50, 'EUR', 'contract:2',
               '2025-02-01T00:00:00Z', '200.50',
               'budget_tax_exclusive_amount', 'ADJ'),
              (3, 'placsp_autonomico', 3, 'c3', '2026-02-12',
               'https://example.test/contracts/3', 'CON-3', NULL, NULL,
               NULL, NULL, 'Region A', NULL, 'AN', '2025-03-01', NULL,
               300.75, 'EUR', 'contract:3', '2025-03-01T00:00:00Z',
               '300.75', 'budget_total_amount', 'PUB');
            INSERT INTO money_contract_award_results VALUES
              (1, 'placsp_sindicacion', 2, 'c2', 'contract:2', 'L1',
               '0024-12-09', 'Awarded Company', 'A12345678', '150.25', 'EUR');
            INSERT INTO money_subsidy_records VALUES
              (1, 'bdns_api_subvenciones', 4, 's1', '2026-02-12',
               'https://example.test/subsidies/1', 'CALL-1', 'GRANT-1',
               'Ministry C', 'Company One', 'A12345678', 'ENERGY', NULL,
               '2024-04-01', NULL, 400.125, 'EUR'),
              (2, 'bdns_api_subvenciones', 5, 's2', '2026-02-12',
               'https://example.test/subsidies/2', 'CALL-2', NULL,
               'Ministry D', 'Association Two', NULL, NULL, NULL,
               '2025-04-01', NULL, 500.875, 'EUR'),
              (3, 'bdns_autonomico', 6, 's3', '2026-02-12',
               'https://example.test/subsidies/3', 'CALL-3', 'GRANT-3',
               'Region B', 'Foundation Three', 'G12345678', 'CULTURE', 'CT',
               '2025-05-01', '2025-06-01', 600.00, 'EUR');
            """
        )
        conn.commit()
        conn.close()

    def test_full_validation_and_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "money.db"
            self._database(db_path)
            first_root = root / "first"
            first = export_money_partitions(
                db_path=db_path,
                output_root=first_root,
                snapshot_date="2026-02-25",
                row_group_rows=2,
                max_file_rows=2,
                min_rows=7,
                enforce=True,
            )
            self.assertEqual(first["totals"]["rows"], 7)
            self.assertEqual(first["totals"]["contract_notice_rows"], 3)
            self.assertEqual(first["totals"]["contract_award_rows"], 1)
            self.assertEqual(first["totals"]["subsidy_record_rows"], 3)
            self.assertEqual(first["totals"]["unknown_year_rows"], 0)
            self.assertEqual(first["totals"]["amount_eur_total"], "2252.750000")
            self.assertEqual(
                first["totals"]["counterparty_published_legal_entity_rows"], 3
            )
            self.assertEqual(
                first["totals"]["counterparty_published_unclassified_rows"], 1
            )
            self.assertEqual(first["totals"]["counterparty_published_rows"], 4)
            self.assertEqual(first["totals"]["counterparty_not_available_rows"], 0)
            self.assertEqual(
                first["coverage"]["counterparty_publication_state"], 1.0
            )
            self.assertEqual(first["totals"]["private_token_findings"], 0)
            self.assertTrue(first["analytical_partition_gate_passed"])
            self.assertFalse(first["promotion_gate_passed"])
            report = validate_money_partitions(root=first_root, min_rows=7)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(
                report["performance"]["distinct_index_storage"],
                "temporary_sqlite_disk",
            )
            self.assertGreater(report["performance"]["distinct_index_bytes"], 0)
            self.assertEqual(report["totals"]["amount_eur_total"], "2252.750000")
            self.assertTrue(
                report["checks"]["public_domain_counterparty_retention_complete"]
            )
            self.assertTrue(report["checks"]["counterparty_names_retained_exactly"])
            self.assertTrue(
                report["checks"]["counterparty_identifiers_retained_exactly"]
            )

            second_root = root / "second"
            second = export_money_partitions(
                db_path=db_path,
                output_root=second_root,
                snapshot_date="2026-02-26",
                row_group_rows=2,
                max_file_rows=2,
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
                "UPDATE money_subsidy_records SET amount_eur = 601 "
                "WHERE subsidy_record_id = 3"
            )
            conn.commit()
            conn.close()
            third_root = root / "third"
            third = export_money_partitions(
                db_path=db_path,
                output_root=third_root,
                snapshot_date="2026-02-27",
                row_group_rows=2,
                max_file_rows=2,
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
                validate_money_partitions(root=third_root, min_rows=7)["status"],
                "ok",
            )

    def test_fixed_width_ids_preserve_lexical_order_past_single_digits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "money.db"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT INTO source_records VALUES (10)")
            conn.execute(
                "INSERT INTO money_subsidy_records VALUES "
                "(10, 'bdns_api_subvenciones', 10, 's10', '2026-02-12', "
                "'https://example.test/subsidies/10', 'CALL-10', 'GRANT-10', "
                "'Ministry E', 'Company Ten', 'B12345678', 'ENERGY', NULL, "
                "'2025-04-01', NULL, 10.00, 'EUR')"
            )
            conn.commit()
            conn.close()
            subsidy_ids = [
                row["money_fact_id"]
                for row in _iter_rows(db_path)
                if row["fact_kind"] == "subsidy_record"
                and row["source_id"] == "bdns_api_subvenciones"
                and row["fact_year"] == "2025"
            ]
            self.assertEqual(subsidy_ids, sorted(subsidy_ids))
            self.assertIn("subsidy_record:00000000000000000010", subsidy_ids)

    def test_negative_amount_and_private_counterparty_fail_closed(self) -> None:
        for column, value in (
            ("amount_eur", -1),
            ("beneficiary_name", "/Users/example/private"),
        ):
            with self.subTest(column=column), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                db_path = root / "money.db"
                output_root = root / "failed"
                self._database(db_path)
                conn = sqlite3.connect(db_path)
                conn.execute(
                    f"UPDATE money_subsidy_records SET {column} = ? "
                    "WHERE subsidy_record_id = 1",
                    (value,),
                )
                conn.commit()
                conn.close()
                with self.assertRaisesRegex(
                    RuntimeError, "analytical partition gate failed"
                ):
                    export_money_partitions(
                        db_path=db_path,
                        output_root=output_root,
                        snapshot_date="2026-02-25",
                        min_rows=7,
                        enforce=True,
                    )
                self.assertFalse(output_root.exists())

    def test_official_natural_person_identity_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "money.db"
            output_root = root / "published"
            self._database(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE money_subsidy_records "
                "SET beneficiary_name = 'PERSON TEST', "
                "beneficiary_identifier = '12345678Z' "
                "WHERE subsidy_record_id = 1"
            )
            conn.commit()
            conn.close()
            manifest = export_money_partitions(
                db_path=db_path,
                output_root=output_root,
                snapshot_date="2026-02-25",
                min_rows=7,
                enforce=True,
            )
            self.assertEqual(
                manifest["totals"][
                    "counterparty_published_natural_person_rows"
                ],
                1,
            )
            self.assertEqual(manifest["totals"]["counterparty_published_rows"], 4)
            self.assertEqual(
                validate_money_partitions(root=output_root, min_rows=7)["status"],
                "ok",
            )
            natural_rows = []
            for parquet_path in output_root.rglob("*.parquet"):
                natural_rows.extend(
                    row
                    for row in pq.ParquetFile(parquet_path).read().to_pylist()
                    if row["counterparty_entity_type"] == "potential_natural_person"
                )
            self.assertEqual(len(natural_rows), 1)
            self.assertEqual(natural_rows[0]["counterparty_name"], "PERSON TEST")
            self.assertEqual(
                natural_rows[0]["counterparty_identifier"], "12345678Z"
            )
            self.assertEqual(
                natural_rows[0]["counterparty_publication_state"],
                "published_natural_person",
            )

    def test_minimum_rows_and_tampered_manifest_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "money.db"
            self._database(db_path)
            with self.assertRaisesRegex(
                RuntimeError, "analytical partition gate failed"
            ):
                export_money_partitions(
                    db_path=db_path,
                    output_root=root / "too-small",
                    snapshot_date="2026-02-25",
                    min_rows=8,
                    enforce=True,
                )
            valid_root = root / "valid"
            export_money_partitions(
                db_path=db_path,
                output_root=valid_root,
                snapshot_date="2026-02-25",
                min_rows=7,
                enforce=True,
            )
            manifest_path = valid_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["totals"]["amount_eur_total"] = "0.000000"
            manifest["partitions"][0]["amount_eur_total"] = "0.000000"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
            )
            report = validate_money_partitions(root=valid_root, min_rows=7)
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["checks"]["manifest_metric_totals"])
            self.assertFalse(report["checks"]["partition_rows_and_money"])


if __name__ == "__main__":
    unittest.main()
