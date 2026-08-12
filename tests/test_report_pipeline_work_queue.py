from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from publicdata_ops import enqueue_work_items, ensure_work_queue_schema
from publicdata_sqlite import open_db
from scripts.report_pipeline_work_queue import main


class TestReportPipelineWorkQueue(unittest.TestCase):
    def test_cli_emits_bounded_queue_health_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "queue.db"
            out_path = root / "queue-health.json"
            conn = open_db(db_path)
            try:
                ensure_work_queue_schema(conn)
                enqueue_work_items(
                    conn,
                    pipeline_id="document_fetch",
                    items=[
                        {"item_key": "a", "partition_key": "source-a"},
                        {"item_key": "b", "partition_key": "source-b"},
                    ],
                )
            finally:
                conn.close()

            result = main(
                [
                    "--db",
                    str(db_path),
                    "--pipeline-id",
                    "document_fetch",
                    "--out",
                    str(out_path),
                    "--enforce",
                ]
            )
            self.assertEqual(result, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["items_total"], 2)
            self.assertEqual(report["state_counts"]["pending"], 2)
            self.assertLessEqual(len(report["top_partitions"]), 20)


if __name__ == "__main__":
    unittest.main()
