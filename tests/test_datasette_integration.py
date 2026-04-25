from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.integrations import datasette


class TestDatasetteIntegration(unittest.TestCase):
    def test_build_metadata_exposes_generic_queries(self) -> None:
        metadata = datasette.build_metadata(Path("etl/data/staging/politicos-es.db"))
        db_meta = metadata["databases"]["politicos-es"]
        self.assertIn("foreign_key_check", db_meta["queries"])
        self.assertIn("recent_ingestion_runs", db_meta["queries"])

    def test_write_metadata_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "metadata.json"
            datasette.write_metadata(Path("etl/data/staging/politicos-es.db"), out_path)
            self.assertTrue(out_path.exists())
            self.assertIn("Vota con la Chola Explorer", out_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
