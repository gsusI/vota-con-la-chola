from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_sources
from etl.politicos_es.registry import get_connectors


ROOT = Path(__file__).resolve().parents[1]


class TestSourceOnboardingScaffold(unittest.TestCase):
    def test_add_source_dry_run_lists_expected_files(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/add_source.py",
                "demo_public_dataset",
                "--name",
                "Demo public dataset",
                "--scope",
                "demo",
                "--url",
                "https://example.invalid/data.json",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("publicdata_connectors_es/contrib/parsers/demo_public_dataset.py", proc.stdout)
        self.assertIn("etl/data/raw/samples/demo_public_dataset_sample.json", proc.stdout)
        self.assertIn("docs/etl/sources/demo_public_dataset.md", proc.stdout)

    def test_contrib_sources_are_seeded_and_registered(self) -> None:
        connectors = get_connectors()
        for source_id in SOURCE_CONFIG:
            sample = Path(str(SOURCE_CONFIG[source_id]["fallback_file"]))
            self.assertIn("fallback_file", SOURCE_CONFIG[source_id])
            self.assertTrue(str(sample), f"empty fallback_file for {source_id}")
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sources.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                for source_id in connectors:
                    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
                    self.assertIsNotNone(row, f"connector missing seeded source row: {source_id}")
            finally:
                conn.close()

