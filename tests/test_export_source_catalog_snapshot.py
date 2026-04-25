from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from scripts import graph_ui_server as g


class ExportSourceCatalogSnapshotTests(unittest.TestCase):
    def test_build_source_catalog_payload_exposes_public_source_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "catalog.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                conn.commit()
            finally:
                conn.close()

            payload = g.build_source_catalog_payload(db_path, snapshot_date="2026-04-13")

        self.assertEqual(payload["catalog_version"], "v1")
        self.assertEqual(payload["snapshot_date"], "2026-04-13")
        self.assertIn("summary", payload)
        self.assertIn("sources", payload)
        self.assertGreater(payload["summary"]["sources_total"], 0)
        self.assertEqual(payload["summary"]["sources_total"], len(payload["sources"]))

        by_domain_total = sum(int(row["sources_total"]) for row in payload["summary"]["by_domain"])
        by_scope_total = sum(int(row["sources_total"]) for row in payload["summary"]["by_scope"])
        self.assertEqual(by_domain_total, payload["summary"]["sources_total"])
        self.assertEqual(by_scope_total, payload["summary"]["sources_total"])

        first_source = payload["sources"][0]
        self.assertIn("source_id", first_source)
        self.assertIn("legal", first_source)
        self.assertIn("warehouse", first_source)
        self.assertIn("flags", first_source)
        self.assertIn("execution", first_source)
        self.assertIn("runner_script", first_source["execution"])
        self.assertIn("strict_target", first_source["execution"])
        self.assertIn("sample_available", first_source["execution"])
        self.assertIn(first_source["legal"]["verification_status"], payload["summary"]["legal_status_counts"])
        self.assertIn("sample_backed_total", payload["summary"])
        self.assertGreater(payload["summary"]["sample_backed_total"], 0)

        serialized = json.dumps(payload, ensure_ascii=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn(str(db_path), serialized)


if __name__ == "__main__":
    unittest.main()
