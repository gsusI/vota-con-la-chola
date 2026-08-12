from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.check_real_data_only import scan_db, scan_paths


class CheckRealDataOnlyTests(unittest.TestCase):
    def test_artifact_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "artifact.json"
            path.write_text('{"source_url":"https://example.invalid/record"}', encoding="utf-8")
            files_scanned, findings = scan_paths([path])
        self.assertEqual(files_scanned, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "prohibited_non_real_marker")

    def test_official_public_identity_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "artifact.json"
            path.write_text(
                '{"beneficiario":"***8299** ANGELA CESPEDES ROJAS"}', encoding="utf-8"
            )
            _files_scanned, findings = scan_paths([path])
        self.assertEqual(findings, [])

    def test_database_implicit_fallback_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.db"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE source_records(source_id TEXT, raw_payload TEXT);
                CREATE TABLE ingestion_runs(source_id TEXT, message TEXT);
                INSERT INTO source_records VALUES ('eurostat_sdmx', '{"source":"synthetic sample"}');
                INSERT INTO ingestion_runs VALUES ('eurostat_sdmx', 'network-error-fallback');
                """
            )
            conn.close()
            findings = scan_db(path)
        self.assertEqual({row["kind"] for row in findings}, {
            "implicit_fallback_ingestion_run",
            "prohibited_non_real_source_records",
        })


if __name__ == "__main__":
    unittest.main()
