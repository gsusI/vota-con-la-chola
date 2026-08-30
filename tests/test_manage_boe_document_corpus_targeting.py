from __future__ import annotations

import argparse
import sqlite3
import unittest
from pathlib import Path

from publicdata_ops import ensure_work_queue_schema
from scripts.manage_boe_document_corpus import (
    BoeCorpusError,
    exact_summary_dates,
    expand_documents,
    requeue_document_budget_failures,
    requeue_document_transient_failures,
    selected_boe_ids,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = ROOT / "etl/data/staging/politicos-es.db"
SUMMARY_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/20240514"
PROCLAMATION_ID = "BOE-A-2024-9687"


def targeting_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "summary_date": [],
        "start_date": "",
        "end_date": "",
        "boe_id": [],
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ManageBoeDocumentCorpusTargetingTests(unittest.TestCase):
    def setUp(self) -> None:
        if not PRODUCTION_DB.is_file():
            self.skipTest("real BOE corpus database is unavailable")
        source = sqlite3.connect(PRODUCTION_DB)
        source.row_factory = sqlite3.Row
        try:
            row = source.execute(
                """
                SELECT t.source_url, t.fetched_at, t.content_type,
                       t.content_sha256, t.bytes, t.raw_path, s.raw_payload
                FROM text_documents AS t
                JOIN source_records AS s
                  ON s.source_record_pk = t.source_record_pk
                WHERE t.source_id = 'boe_daily_summaries'
                  AND t.source_url = ?
                """,
                (SUMMARY_URL,),
            ).fetchone()
        finally:
            source.close()
        if row is None:
            self.skipTest("real 2024-05-14 BOE summary capture is unavailable")
        self.real_summary = dict(row)

    def new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              raw_payload TEXT NOT NULL
            );
            CREATE TABLE text_documents (
              source_url TEXT NOT NULL,
              source_id TEXT NOT NULL,
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              source_record_pk INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO source_records(source_record_pk, raw_payload) VALUES (1, ?)",
            (self.real_summary["raw_payload"],),
        )
        connection.execute(
            """
            INSERT INTO text_documents(
              source_url, source_id, fetched_at, content_type,
              content_sha256, bytes, raw_path, source_record_pk
            ) VALUES (?, 'boe_daily_summaries', ?, ?, ?, ?, ?, 1)
            """,
            (
                self.real_summary["source_url"],
                self.real_summary["fetched_at"],
                self.real_summary["content_type"],
                self.real_summary["content_sha256"],
                self.real_summary["bytes"],
                self.real_summary["raw_path"],
            ),
        )
        ensure_work_queue_schema(connection)
        connection.executescript(
            """
            CREATE TABLE document_fetch_request_events (
              document_fetch_request_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              work_item_id INTEGER NOT NULL,
              pipeline_id TEXT NOT NULL,
              queue_attempt_number INTEGER NOT NULL,
              worker_id TEXT NOT NULL,
              source_url TEXT NOT NULL,
              source_host TEXT NOT NULL,
              outcome_state TEXT NOT NULL,
              network_requests_started INTEGER NOT NULL,
              http_status INTEGER,
              failure_class TEXT,
              bytes_received INTEGER NOT NULL DEFAULT 0,
              recorded_at TEXT NOT NULL,
              UNIQUE (work_item_id, queue_attempt_number)
            );
            """
        )
        connection.commit()
        return connection

    def test_sparse_dates_and_exact_ids_are_normalized(self) -> None:
        args = targeting_args(
            summary_date=["2019-10-15", "2015-11-24", "2019-10-15"],
            boe_id=[PROCLAMATION_ID.lower(), PROCLAMATION_ID],
        )
        self.assertEqual(
            [value.isoformat() for value in exact_summary_dates(args)],
            ["2015-11-24", "2019-10-15"],
        )
        self.assertEqual(selected_boe_ids(args), (PROCLAMATION_ID,))

    def test_exact_document_filter_enqueues_only_real_requested_record(self) -> None:
        connection = self.new_connection()
        try:
            report = expand_documents(
                connection,
                bounds=None,
                summary_dates=(),
                boe_ids=(PROCLAMATION_ID,),
                limit=0,
                batch_size=100,
                max_attempts=3,
            )
            self.assertGreater(report["documents_discovered"], 1)
            self.assertEqual(report["documents_selected"], 1)
            self.assertEqual(report["selected_boe_ids"], [PROCLAMATION_ID])
            self.assertTrue(report["selected_boe_ids_complete"])
            self.assertEqual(report["selected_boe_ids_count"], 1)
            self.assertEqual(
                report["selected_boe_ids_sample"]["first"], [PROCLAMATION_ID]
            )
            queued = connection.execute(
                """
                SELECT item_key, payload_json
                FROM pipeline_work_items
                WHERE pipeline_id = 'boe_document_fetch'
                """
            ).fetchall()
            self.assertEqual(len(queued), 1)
            self.assertIn(PROCLAMATION_ID, str(queued[0]["item_key"]))
            self.assertIn(PROCLAMATION_ID, str(queued[0]["payload_json"]))
        finally:
            connection.close()

    def test_unfiltered_expansion_keeps_report_identity_evidence_bounded(self) -> None:
        connection = self.new_connection()
        try:
            report = expand_documents(
                connection,
                bounds=None,
                summary_dates=(),
                boe_ids=(),
                limit=0,
                batch_size=100,
                max_attempts=3,
            )
            self.assertGreater(report["documents_selected"], 1)
            self.assertEqual(report["selected_boe_ids"], [])
            self.assertFalse(report["selected_boe_ids_complete"])
            self.assertEqual(
                report["selected_boe_ids_count"], report["documents_selected"]
            )
            self.assertEqual(
                len(report["selected_boe_ids_ordered_stream_sha256"]), 64
            )
            self.assertLessEqual(
                len(report["selected_boe_ids_sample"]["first"]), 10
            )
            self.assertLessEqual(
                len(report["selected_boe_ids_sample"]["last"]), 10
            )
        finally:
            connection.close()

    def test_budget_failure_requeue_requires_zero_request_event(self) -> None:
        connection = self.new_connection()
        try:
            connection.execute(
                """
                INSERT INTO pipeline_work_items(
                  pipeline_id, item_key, state, payload_json, available_at,
                  attempts, max_attempts, last_error, created_at, updated_at,
                  completed_at
                ) VALUES (
                  'boe_document_fetch', 'https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-9687',
                  'dead', '{}', '2026-08-30T00:00:00+00:00', 3, 3,
                  'host_request_budget_exhausted', '2026-08-30T00:00:00+00:00',
                  '2026-08-30T00:00:00+00:00', '2026-08-30T00:00:00+00:00'
                )
                """
            )
            work_item_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """
                INSERT INTO document_fetch_request_events(
                  work_item_id, pipeline_id, queue_attempt_number, worker_id,
                  source_url, source_host, outcome_state,
                  network_requests_started, failure_class, recorded_at
                ) VALUES (?, 'boe_document_fetch', 3, 'worker', ?, 'www.boe.es',
                          'failed', 0, 'host_request_budget_exhausted',
                          '2026-08-30T00:00:00+00:00')
                """,
                (work_item_id, "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-9687"),
            )
            connection.commit()

            report = requeue_document_budget_failures(connection)

            self.assertEqual(report["items_requeued"], 1)
            self.assertEqual(report["unsafe_items"], 0)
            row = connection.execute(
                "SELECT state, attempts, max_attempts, last_error FROM pipeline_work_items"
            ).fetchone()
            self.assertEqual(tuple(row), ("pending", 3, 4, None))
            event = connection.execute(
                "SELECT network_requests_started, failure_class FROM document_fetch_request_events"
            ).fetchone()
            self.assertEqual(tuple(event), (0, "host_request_budget_exhausted"))
        finally:
            connection.close()

    def test_budget_failure_requeue_rejects_missing_telemetry(self) -> None:
        connection = self.new_connection()
        try:
            connection.execute(
                """
                INSERT INTO pipeline_work_items(
                  pipeline_id, item_key, state, payload_json, available_at,
                  attempts, max_attempts, last_error, created_at, updated_at,
                  completed_at
                ) VALUES (
                  'boe_document_fetch', 'missing-telemetry', 'dead', '{}',
                  '2026-08-30T00:00:00+00:00', 1, 3,
                  'host_request_budget_exhausted', '2026-08-30T00:00:00+00:00',
                  '2026-08-30T00:00:00+00:00', '2026-08-30T00:00:00+00:00'
                )
                """
            )
            connection.commit()
            with self.assertRaisesRegex(BoeCorpusError, "zero-request telemetry"):
                requeue_document_budget_failures(connection)
        finally:
            connection.close()

    def test_transient_failure_requeue_requires_positive_request_event(self) -> None:
        connection = self.new_connection()
        try:
            connection.execute(
                """
                INSERT INTO pipeline_work_items(
                  pipeline_id, item_key, state, payload_json, available_at,
                  attempts, max_attempts, last_error, created_at, updated_at,
                  completed_at
                ) VALUES (
                  'boe_document_fetch', 'network-timeout', 'dead', '{}',
                  '2026-08-30T00:00:00+00:00', 3, 3, 'network timeout',
                  '2026-08-30T00:00:00+00:00', '2026-08-30T00:00:00+00:00',
                  '2026-08-30T00:00:00+00:00'
                )
                """
            )
            work_item_id = int(
                connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO document_fetch_request_events(
                  work_item_id, pipeline_id, queue_attempt_number, worker_id,
                  source_url, source_host, outcome_state,
                  network_requests_started, failure_class, recorded_at
                ) VALUES (?, 'boe_document_fetch', 3, 'worker', ?, 'www.boe.es',
                          'failed', 3, 'network',
                          '2026-08-30T00:00:00+00:00')
                """,
                (work_item_id, "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-9687"),
            )
            connection.commit()

            report = requeue_document_transient_failures(connection)

            self.assertEqual(report["items_requeued"], 1)
            row = connection.execute(
                "SELECT state, attempts, max_attempts, last_error FROM pipeline_work_items"
            ).fetchone()
            self.assertEqual(tuple(row), ("pending", 3, 4, None))
        finally:
            connection.close()

    def test_missing_exact_document_fails_before_queue_mutation(self) -> None:
        connection = self.new_connection()
        try:
            with self.assertRaisesRegex(
                BoeCorpusError, "missing from captured summaries"
            ):
                expand_documents(
                    connection,
                    bounds=None,
                    summary_dates=(),
                    boe_ids=("BOE-A-2019-14801",),
                    limit=0,
                    batch_size=100,
                    max_attempts=3,
                )
            queued = connection.execute(
                """
                SELECT COUNT(*)
                FROM pipeline_work_items
                WHERE pipeline_id = 'boe_document_fetch'
                """
            ).fetchone()[0]
            self.assertEqual(queued, 0)
        finally:
            connection.close()

    def test_sparse_dates_cannot_be_mixed_with_range(self) -> None:
        args = targeting_args(summary_date=["2019-10-15"], start_date="2019-10-15")
        with self.assertRaisesRegex(BoeCorpusError, "cannot be combined"):
            exact_summary_dates(args)


if __name__ == "__main__":
    unittest.main()
