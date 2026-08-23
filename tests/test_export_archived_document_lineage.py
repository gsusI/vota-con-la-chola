from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_archived_document_lineage import discover_databases, run_export


class TestExportArchivedDocumentLineage(unittest.TestCase):
    def test_discovers_root_and_nested_legacy_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            root_database = root / "politicos-root.db"
            nested_database = root / "archive" / "politicos-nested.db"
            unrelated_database = root / "archive" / "other.db"
            nested_database.parent.mkdir()
            root_database.touch()
            nested_database.touch()
            unrelated_database.touch()

            self.assertEqual(
                discover_databases(root),
                [nested_database, root_database],
            )

    def test_exports_only_exact_real_public_capture_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw = root / "raw"
            raw.mkdir()
            payload = b"official public XML"
            sha256 = hashlib.sha256(payload).hexdigest()
            relative = "europarl_meps/2026/02/14/capture.xml"
            capture = raw / relative
            capture.parent.mkdir(parents=True)
            capture.write_bytes(payload)
            queue = root / "queue.jsonl"
            queue.write_text(
                json.dumps(
                    {
                        "path": relative,
                        "source_group": "europarl_meps",
                        "sha256": sha256,
                        "bytes": len(payload),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            inventory = root / "inventory.jsonl"
            inventory.write_text(
                json.dumps(
                    {
                        "path": relative,
                        "source_group": "europarl_meps",
                        "sha256": sha256,
                        "bytes": len(payload),
                        "real_data_status": "eligible_real_capture",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            database = root / "politicos.db"
            connection = sqlite3.connect(database)
            connection.execute(
                """
                CREATE TABLE raw_fetches (
                  raw_path TEXT,
                  source_url TEXT,
                  content_sha256 TEXT,
                  bytes INTEGER,
                  source_id TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO raw_fetches VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        f"etl/data/raw/{relative}",
                        "https://www.europarl.europa.eu/meps/es/full-list/xml",
                        sha256,
                        len(payload),
                        "europarl_meps",
                    ),
                    (
                        f"etl/data/raw/{relative}",
                        "https://example.invalid/not-real.xml",
                        sha256,
                        len(payload),
                        "europarl_meps",
                    ),
                ],
            )
            connection.commit()
            connection.close()
            manifest = root / "lineage.jsonl"
            report_path = root / "report.json"

            report = run_export(
                inventory_root=raw,
                inventory_manifest_path=inventory,
                queue_path=queue,
                database_paths=[database],
                manifest_out=manifest,
                report_out=report_path,
            )

            self.assertEqual(report["counts"]["accepted_unique_files"], 1)
            self.assertEqual(report["counts"]["skipped_non_public_url"], 1)
            record = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(record["capture"]["sha256"], sha256)
            self.assertEqual(
                record["source_url"],
                "https://www.europarl.europa.eu/meps/es/full-list/xml",
            )
            self.assertFalse(record["synthetic_or_mock_records_counted"])


if __name__ == "__main__":
    unittest.main()
