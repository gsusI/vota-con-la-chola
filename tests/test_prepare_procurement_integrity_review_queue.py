from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from publicdata_sqlite import open_db
from scripts.detect_procurement_integrity_signals import detect_threshold_patterns
from scripts.prepare_procurement_integrity_review_queue import (
    REVIEW_FIELDS,
    ReviewQueueError,
    build_tasks,
    validate_reviews,
)


class TestPrepareProcurementIntegrityReviewQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.connection = open_db(Path(self.temp.name) / "review.db")
        self.connection.executescript(
            """
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              content_sha256 TEXT NOT NULL
            );
            CREATE TABLE money_contract_records (
              contract_record_id INTEGER PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER NOT NULL,
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
        for index, amount in enumerate(("6000.00", "5500.00", "5000.00"), 1):
            url = f"https://contrataciondelestado.es/contract/{index}"
            self.connection.execute(
                "INSERT INTO source_records VALUES (?, ?)",
                (index, hashlib.sha256(url.encode()).hexdigest()),
            )
            self.connection.execute(
                """
                INSERT INTO money_contract_records (
                  contract_record_id, source_id, source_record_pk,
                  source_record_id, source_url, contracting_authority,
                  cpv_code, awarded_date, stable_contract_id, entry_updated_at
                ) VALUES (?, 'placsp_sindicacion', ?, ?, ?, 'Authority A',
                          '12340000', ?, ?, '2026-02-10T00:00:00Z')
                """,
                (
                    index,
                    index,
                    f"contract-{index}",
                    url,
                    f"2026-02-{index:02d}",
                    f"stable-{index}",
                ),
            )
            self.connection.execute(
                """
                INSERT INTO money_contract_award_results VALUES (
                  ?, 'placsp_sindicacion', ?, ?, ?, ?, ?, ?, ?
                )
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
        self.connection.commit()
        detect_threshold_patterns(
            self.connection,
            threshold_eur=15_000.0,
            min_records=3,
            source_ids=("placsp_sindicacion",),
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_queue_contains_every_exact_real_evidence_row_and_blank_reviews(self) -> None:
        tasks = build_tasks(self.connection, existing={}, limit=0)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["record_count"], "3")
        self.assertEqual(task["evidence_count"], "3")
        self.assertIn("supplier-1", task["supplier_identifiers_json"])
        self.assertIn("6000.00", task["amounts_eur_decimal_json"])
        self.assertTrue(all(task[field] == "" for field in REVIEW_FIELDS))
        self.assertEqual(validate_reviews(tasks)["pending_dual_review"], 1)

    def test_dual_review_requires_distinct_humans_and_independence(self) -> None:
        task = build_tasks(self.connection, existing={}, limit=0)[0]
        for slot in (1, 2):
            task[f"reviewer_{slot}_id"] = "same-human"
            task[f"reviewer_{slot}_independence_class"] = "maintainer"
            task[f"reviewer_{slot}_decision"] = "reject"
            task[f"reviewer_{slot}_rationale"] = "Official files show distinct needs."
            task[f"reviewer_{slot}_reviewed_at"] = "2026-08-13T00:00:00Z"
        with self.assertRaisesRegex(ReviewQueueError, "distinct humans"):
            validate_reviews([task])

    def test_regeneration_preserves_human_fields_and_rejects_task_drift(self) -> None:
        task = build_tasks(self.connection, existing={}, limit=0)[0]
        task["reviewer_1_id"] = "reviewer-one"
        task["reviewer_1_independence_class"] = "independent"
        task["reviewer_1_decision"] = "needs_more_evidence"
        task["reviewer_1_rationale"] = "Need procurement files."
        task["reviewer_1_reviewed_at"] = "2026-08-13T00:00:00Z"
        preserved = build_tasks(
            self.connection,
            existing={task["task_id"]: task},
            limit=0,
        )[0]
        self.assertEqual(preserved["reviewer_1_id"], "reviewer-one")

        self.connection.execute(
            "UPDATE integrity_signals SET summary='drifted' WHERE signal_id=?",
            (task["signal_id"],),
        )
        self.connection.commit()
        with self.assertRaisesRegex(ReviewQueueError, "immutable review task drifted"):
            build_tasks(
                self.connection,
                existing={task["task_id"]: task},
                limit=0,
            )


if __name__ == "__main__":
    unittest.main()
