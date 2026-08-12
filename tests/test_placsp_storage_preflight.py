from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from publicdata_ops import enqueue_work_items
from scripts.ingest_placsp_archives import (
    _archive_pipeline,
    _bulk_run,
    _member_pipeline,
    _open_runtime,
    _storage_preflight,
    enqueue_archives,
    main,
    run_member_worker,
)


class TestPlacspStoragePreflight(unittest.TestCase):
    def test_preflight_reserves_next_item_before_enforcing_floor(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            usage = SimpleNamespace(total=1_000, used=600, free=400)
            with patch(
                "scripts.ingest_placsp_archives.shutil.disk_usage",
                return_value=usage,
            ):
                ready = _storage_preflight(
                    root,
                    min_free_bytes=200,
                    reserve_bytes=150,
                )
                blocked = _storage_preflight(
                    root,
                    min_free_bytes=300,
                    reserve_bytes=150,
                )

            self.assertTrue(ready["ready"])
            self.assertEqual(ready["headroom_bytes"], 50)
            self.assertEqual(ready["free_after_reserve_bytes"], 250)
            self.assertFalse(blocked["ready"])
            self.assertEqual(blocked["headroom_bytes"], -50)

    def test_archive_worker_blocks_before_claim_or_network(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "placsp.db"
            report_path = root / "archive-worker.json"
            conn = _open_runtime(db_path, Path("etl/load/sqlite_schema.sql"))
            try:
                enqueue_archives(
                    conn,
                    pipeline_id="history",
                    snapshot_date="2026-08-11",
                    archives=[("2012", "https://official.example/2012.zip")],
                )
            finally:
                conn.close()

            usage = SimpleNamespace(total=1_000, used=851, free=149)
            with patch(
                "scripts.ingest_placsp_archives.shutil.disk_usage",
                return_value=usage,
            ):
                exit_code = main(
                    [
                        "--db",
                        str(db_path),
                        "--pipeline-id",
                        "history",
                        "--report-out",
                        str(report_path),
                        "work-archives",
                        "--raw-root",
                        str(root / "raw"),
                        "--max-items",
                        "1",
                        "--max-archive-bytes",
                        "50",
                        "--min-free-bytes",
                        "100",
                    ]
                )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "blocked_storage")
            self.assertEqual(report["stop_reason"], "insufficient_free_space")
            self.assertEqual(report["processed"], 0)
            self.assertEqual(report["archive_queue"]["state_counts"]["pending"], 1)
            self.assertEqual(report["archive_queue"]["attempts_total"], 0)
            self.assertFalse(report["storage_preflight"]["ready"])

    def test_member_worker_blocks_before_claim_or_parse(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            conn = _open_runtime(root / "placsp.db", Path("etl/load/sqlite_schema.sql"))
            try:
                enqueue_archives(
                    conn,
                    pipeline_id="history",
                    snapshot_date="2026-08-11",
                    archives=[("2012", "https://official.example/2012.zip")],
                )
                run = _bulk_run(conn, "history")
                self.assertIsNotNone(run)
                archive_item = conn.execute(
                    "SELECT work_item_id FROM pipeline_work_items WHERE pipeline_id = ?",
                    (_archive_pipeline("history"),),
                ).fetchone()
                self.assertIsNotNone(archive_item)
                conn.execute(
                    "UPDATE pipeline_work_items SET state = 'succeeded' WHERE work_item_id = ?",
                    (int(archive_item[0]),),
                )
                archive_id = int(
                    conn.execute(
                        """
                        INSERT INTO placsp_bulk_archives (
                          placsp_bulk_run_id, work_item_id, period, source_url,
                          transport_security, fetched_at, content_sha256, bytes,
                          raw_path, members_total, uncompressed_bytes, status,
                          created_at, updated_at
                        ) VALUES (?, ?, '2012', ?, 'verified_system_ca', ?, ?, 10,
                                  'raw/archive.zip', 1, 10, 'ok', ?, ?)
                        RETURNING placsp_bulk_archive_id
                        """,
                        (
                            int(run["placsp_bulk_run_id"]),
                            int(archive_item[0]),
                            "https://official.example/2012.zip",
                            "2026-08-11T00:00:00+00:00",
                            "a" * 64,
                            "2026-08-11T00:00:00+00:00",
                            "2026-08-11T00:00:00+00:00",
                        ),
                    ).fetchone()[0]
                )
                member_id = int(
                    conn.execute(
                        """
                        INSERT INTO placsp_bulk_members (
                          placsp_bulk_archive_id, member_name, crc32,
                          compressed_bytes, uncompressed_bytes, status,
                          created_at, updated_at
                        ) VALUES (?, 'feed.atom', 1, 5, 10, 'pending', ?, ?)
                        RETURNING placsp_bulk_member_id
                        """,
                        (
                            archive_id,
                            "2026-08-11T00:00:00+00:00",
                            "2026-08-11T00:00:00+00:00",
                        ),
                    ).fetchone()[0]
                )
                enqueue_work_items(
                    conn,
                    pipeline_id=_member_pipeline("history"),
                    items=[
                        {
                            "item_key": f"member:{archive_id}:{member_id}",
                            "payload": {
                                "placsp_bulk_run_id": int(run["placsp_bulk_run_id"]),
                                "placsp_bulk_archive_id": archive_id,
                                "placsp_bulk_member_id": member_id,
                                "member_name": "feed.atom",
                                "raw_path": "raw/archive.zip",
                                "snapshot_date": "2026-08-11",
                            },
                        }
                    ],
                )
                usage = SimpleNamespace(total=1_000, used=851, free=149)
                with patch(
                    "scripts.ingest_placsp_archives.shutil.disk_usage",
                    return_value=usage,
                ):
                    report = run_member_worker(
                        conn,
                        pipeline_id="history",
                        worker_id="member-worker",
                        claim_size=1,
                        max_items=1,
                        lease_seconds=60,
                        max_records=10,
                        max_documents_per_record=10,
                        max_member_bytes=50,
                        min_free_bytes=100,
                        retry_delay_seconds=30,
                    )

                self.assertEqual(report["status"], "blocked_storage")
                self.assertEqual(
                    report["worker"]["stop_reason"], "insufficient_free_space"
                )
                self.assertEqual(report["worker"]["processed"], 0)
                self.assertEqual(report["member_queue"]["state_counts"]["pending"], 1)
                self.assertEqual(report["member_queue"]["attempts_total"], 0)
                self.assertFalse(report["worker"]["storage_preflight"]["ready"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
