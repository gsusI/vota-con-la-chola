from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from scripts import graph_ui_server as g


class ExportSourceScrapeQueueSnapshotTests(unittest.TestCase):
    def test_build_source_scrape_queue_payload_exposes_actionable_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "queue.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                conn.commit()
            finally:
                conn.close()

            payload = g.build_source_scrape_queue_payload(db_path, snapshot_date="2026-04-13")

        self.assertEqual(payload["queue_version"], "v1")
        self.assertEqual(payload["snapshot_date"], "2026-04-13")
        self.assertGreater(payload["summary"]["queue_items_total"], 0)
        self.assertEqual(payload["summary"]["queue_items_total"], len(payload["items"]))
        self.assertGreater(payload["summary"]["batches_total"], 0)
        self.assertIn("by_repeatability_state", payload["summary"])
        self.assertIn("batches", payload)

        first_item = payload["items"][0]
        self.assertIn("source_id", first_item)
        self.assertIn("priority_score", first_item)
        self.assertIn("queue_reason", first_item)
        self.assertIn("commands", first_item)
        self.assertIn("execution", first_item)
        self.assertIn("repeatability_state", first_item["execution"])
        self.assertIn("network_command", first_item["execution"])
        self.assertIn("validation_command", first_item["execution"])
        self.assertGreater(first_item["priority_score"], 0)

        commands_blob = " ".join(first_item["commands"])
        self.assertNotIn(str(db_path), commands_blob)
        self.assertIn("<db>", commands_blob)
        self.assertIn("<db>", first_item["execution"]["network_command"])
        self.assertIn("<db>", first_item["execution"]["validation_command"])

        first_batch = payload["batches"][0]
        self.assertIn("batch_key", first_batch)
        self.assertIn("network_commands", first_batch)
        self.assertGreater(first_batch["items_total"], 0)

        canonical_money = next(item for item in payload["items"] if item["source_id"] == "bdns_subvenciones")
        self.assertEqual(canonical_money["execution"]["runner_script"], "")
        self.assertEqual(canonical_money["execution"]["network_command"], "")
        self.assertEqual(canonical_money["execution"]["sample_command"], "")
        self.assertEqual(canonical_money["commands"], [canonical_money["execution"]["validation_command"]])

        congreso_intervenciones = next(item for item in payload["items"] if item["source_id"] == "congreso_intervenciones")
        self.assertEqual(
            congreso_intervenciones["execution"]["prerequisite_source_ids"],
            ["congreso_votaciones", "congreso_iniciativas"],
        )
        self.assertGreaterEqual(len(congreso_intervenciones["execution"]["pre_commands"]), 2)
        self.assertIn("<db>", " ".join(congreso_intervenciones["execution"]["pre_commands"]))

        serialized = json.dumps(payload, ensure_ascii=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn(str(db_path), serialized)


if __name__ == "__main__":
    unittest.main()
