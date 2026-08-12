from __future__ import annotations

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from publicdata_ops import (
    claim_work_items,
    collect_futures_with_heartbeat,
    complete_work_items,
    enqueue_work_items,
    ensure_work_queue_schema,
    fail_work_items,
    heartbeat_work_items,
    requeue_expired_leases,
    work_queue_stats,
    work_queue_observability,
)
from publicdata_sqlite import open_db


BASE_TIME = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)


class TestDurableWorkQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = open_db(Path(self.temp_dir.name) / "queue.db")
        ensure_work_queue_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_enqueue_is_streaming_friendly_and_idempotent(self) -> None:
        generated = (
            {
                "item_key": f"document:{index}",
                "partition_key": f"source-{index % 4}",
                "priority": index % 3,
                "payload": {"source_record_pk": index},
            }
            for index in range(2_500)
        )
        first = enqueue_work_items(
            self.conn,
            pipeline_id="text_extraction",
            items=generated,
            batch_size=137,
            now=BASE_TIME,
        )
        self.assertEqual(first["input_total"], 2_500)
        self.assertEqual(first["inserted_total"], 2_500)

        second = enqueue_work_items(
            self.conn,
            pipeline_id="text_extraction",
            items=[{"item_key": "document:4", "priority": 99, "payload": {"source_record_pk": 4}}],
            now=BASE_TIME,
        )
        self.assertEqual(second["inserted_total"], 0)
        self.assertEqual(second["existing_total"], 1)
        row = self.conn.execute(
            "SELECT priority, state FROM pipeline_work_items WHERE item_key = 'document:4'"
        ).fetchone()
        self.assertEqual(int(row["priority"]), 99)
        self.assertEqual(row["state"], "pending")

    def test_enqueue_can_join_caller_transaction(self) -> None:
        result = enqueue_work_items(
            self.conn,
            pipeline_id="atomic_expand",
            items=[{"item_key": "page:1"}],
            now=BASE_TIME,
            commit=False,
        )
        self.assertEqual(result["inserted_total"], 1)
        self.conn.rollback()
        remaining = self.conn.execute(
            "SELECT COUNT(*) FROM pipeline_work_items WHERE pipeline_id = ?",
            ("atomic_expand",),
        ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_claim_orders_by_priority_and_complete_requires_owner(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="document_fetch",
            items=[
                {"item_key": "low", "priority": 1, "payload": {"url": "https://example.test/low.pdf"}},
                {"item_key": "high", "priority": 100, "payload": {"url": "https://example.test/high.pdf"}},
            ],
            now=BASE_TIME,
        )
        claimed = claim_work_items(
            self.conn,
            pipeline_id="document_fetch",
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=BASE_TIME,
        )
        self.assertEqual([row["item_key"] for row in claimed], ["high"])
        self.assertEqual(claimed[0]["payload"]["url"], "https://example.test/high.pdf")
        claimed_id = int(claimed[0]["work_item_id"])
        self.assertEqual(
            heartbeat_work_items(
                self.conn,
                worker_id="worker-b",
                work_item_ids=[claimed_id],
                now=BASE_TIME,
            ),
            0,
        )
        self.assertEqual(
            complete_work_items(
                self.conn,
                worker_id="worker-b",
                work_item_ids=[claimed_id],
                now=BASE_TIME,
            ),
            0,
        )
        self.assertEqual(
            complete_work_items(
                self.conn,
                worker_id="worker-a",
                work_item_ids=[claimed_id],
                now=BASE_TIME,
            ),
            1,
        )
        stats = work_queue_stats(self.conn, pipeline_id="document_fetch")
        self.assertEqual(stats["state_counts"]["succeeded"], 1)
        self.assertEqual(stats["state_counts"]["pending"], 1)

    def test_retry_then_dead_letter_at_attempt_limit(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="pdf_fetch",
            items=[{"item_key": "blocked", "max_attempts": 2}],
            now=BASE_TIME,
        )
        first = claim_work_items(
            self.conn,
            pipeline_id="pdf_fetch",
            worker_id="worker-a",
            limit=1,
            now=BASE_TIME,
        )
        item_id = int(first[0]["work_item_id"])
        failed = fail_work_items(
            self.conn,
            worker_id="worker-a",
            work_item_ids=[item_id],
            error="HTTP 503",
            now=BASE_TIME,
        )
        self.assertEqual(failed, {"retry_total": 1, "dead_total": 0})

        second = claim_work_items(
            self.conn,
            pipeline_id="pdf_fetch",
            worker_id="worker-b",
            limit=1,
            now=BASE_TIME,
        )
        self.assertEqual(len(second), 1)
        failed = fail_work_items(
            self.conn,
            worker_id="worker-b",
            work_item_ids=[item_id],
            error="HTTP 503",
            now=BASE_TIME,
        )
        self.assertEqual(failed, {"retry_total": 0, "dead_total": 1})
        self.assertEqual(work_queue_stats(self.conn, pipeline_id="pdf_fetch")["state_counts"]["dead"], 1)

    def test_non_retryable_failure_dead_letters_immediately(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="pdf_fetch",
            items=[{"item_key": "missing", "max_attempts": 5}],
            now=BASE_TIME,
        )
        claimed = claim_work_items(
            self.conn,
            pipeline_id="pdf_fetch",
            worker_id="worker-a",
            limit=1,
            now=BASE_TIME,
        )
        result = fail_work_items(
            self.conn,
            worker_id="worker-a",
            work_item_ids=[int(claimed[0]["work_item_id"])],
            error="not_found: HTTP 404",
            retryable=False,
            now=BASE_TIME,
        )
        self.assertEqual(result, {"retry_total": 0, "dead_total": 1})

    def test_expired_lease_is_recovered_after_worker_crash(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="vote_normalize",
            items=[{"item_key": "vote:1"}],
            now=BASE_TIME,
        )
        claimed = claim_work_items(
            self.conn,
            pipeline_id="vote_normalize",
            worker_id="crashed-worker",
            limit=1,
            lease_seconds=5,
            now=BASE_TIME,
        )
        self.assertEqual(len(claimed), 1)
        recovered = requeue_expired_leases(
            self.conn,
            pipeline_id="vote_normalize",
            now=BASE_TIME + timedelta(seconds=6),
        )
        self.conn.commit()
        self.assertEqual(recovered, 1)
        replacement = claim_work_items(
            self.conn,
            pipeline_id="vote_normalize",
            worker_id="replacement-worker",
            limit=1,
            now=BASE_TIME + timedelta(seconds=6),
        )
        self.assertEqual(len(replacement), 1)
        attempts = self.conn.execute(
            "SELECT status FROM pipeline_work_attempts ORDER BY work_attempt_id"
        ).fetchall()
        self.assertEqual([row["status"] for row in attempts], ["lease_expired", "running"])

    def test_claim_can_isolate_partition(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="candidate_enrich",
            items=[
                {"item_key": "a:1", "partition_key": "andalucia"},
                {"item_key": "m:1", "partition_key": "madrid"},
            ],
            now=BASE_TIME,
        )
        rows = claim_work_items(
            self.conn,
            pipeline_id="candidate_enrich",
            worker_id="worker-a",
            limit=10,
            partition_key="madrid",
            now=BASE_TIME,
        )
        self.assertEqual([row["item_key"] for row in rows], ["m:1"])

    def test_long_batch_heartbeats_unfinished_futures(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="long_ocr",
            items=[{"item_key": "document:slow"}],
            now=BASE_TIME,
        )
        claimed = claim_work_items(
            self.conn,
            pipeline_id="long_ocr",
            worker_id="worker-a",
            limit=1,
            lease_seconds=3,
        )
        work_item_id = int(claimed[0]["work_item_id"])

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: (time.sleep(0.15), "done")[1])
            with mock.patch(
                "publicdata_ops.work_queue.heartbeat_work_items",
                wraps=heartbeat_work_items,
            ) as heartbeat:
                outcomes = collect_futures_with_heartbeat(
                    self.conn,
                    futures={future: work_item_id},
                    worker_id="worker-a",
                    lease_seconds=3,
                    heartbeat_interval_seconds=0.03,
                )

        self.assertEqual(outcomes, ["done"])
        self.assertGreaterEqual(heartbeat.call_count, 1)
        self.assertEqual(
            complete_work_items(
                self.conn,
                worker_id="worker-a",
                work_item_ids=[work_item_id],
            ),
            1,
        )

    def test_observability_reports_retries_partitions_and_dead_letters(self) -> None:
        enqueue_work_items(
            self.conn,
            pipeline_id="money_transform",
            items=[
                {"item_key": "contract:1", "partition_key": "2025", "max_attempts": 1},
                {"item_key": "contract:2", "partition_key": "2026"},
            ],
            now=BASE_TIME,
        )
        claimed = claim_work_items(
            self.conn,
            pipeline_id="money_transform",
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=BASE_TIME,
        )
        fail_work_items(
            self.conn,
            worker_id="worker-a",
            work_item_ids=[int(claimed[0]["work_item_id"])],
            error="not_fetchable: HTTP 404",
            retryable=False,
            now=BASE_TIME,
        )

        report = work_queue_observability(
            self.conn,
            pipeline_id="money_transform",
            now=BASE_TIME,
        )
        self.assertEqual(report["items_total"], 2)
        self.assertEqual(report["state_counts"]["dead"], 1)
        self.assertEqual(report["attempt_status_counts"]["dead"], 1)
        self.assertEqual(report["dead_letter_rate"], 1.0)
        self.assertEqual(report["overdue_leases_total"], 0)
        self.assertEqual(
            {row["partition_key"] for row in report["top_partitions"]},
            {"2025", "2026"},
        )


if __name__ == "__main__":
    unittest.main()
