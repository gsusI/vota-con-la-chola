from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from publicdata_core.object_store import FilesystemObjectStore
from publicdata_sqlite import open_db
from scripts.replicate_content_objects import iter_local_documents, replicate_objects
from scripts.verify_object_store_restore import (
    deterministic_manifest_sample,
    restore_sample,
)


class TestContentObjectReplication(unittest.TestCase):
    def test_database_to_manifest_to_clean_restore(self) -> None:
        payloads = [b"official pdf one", b"official html two"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "documents.db"
            conn = open_db(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE text_documents (
                      text_document_id INTEGER PRIMARY KEY,
                      content_sha256 TEXT,
                      bytes INTEGER,
                      content_type TEXT,
                      raw_path TEXT
                    )
                    """
                )
                for index, payload in enumerate(payloads, 1):
                    path = root / "cache" / f"document-{index}.bin"
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(payload)
                    conn.execute(
                        "INSERT INTO text_documents VALUES (?, ?, ?, ?, ?)",
                        (
                            index,
                            hashlib.sha256(payload).hexdigest(),
                            len(payload),
                            "application/octet-stream",
                            str(path),
                        ),
                    )
                conn.commit()

                store = FilesystemObjectStore(root / "origin")
                manifest = root / "manifest.jsonl"
                report = replicate_objects(
                    iter_local_documents(conn),
                    store=store,
                    namespace="raw/documents",
                    manifest_out=manifest,
                )
            finally:
                conn.close()

            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["totals"]["replicated"], 2)
            manifest_text = manifest.read_text(encoding="utf-8")
            self.assertNotIn(str(root), manifest_text)
            manifest_rows = [json.loads(line) for line in manifest_text.splitlines()]
            self.assertEqual(len(manifest_rows), 2)

            sampled = deterministic_manifest_sample(manifest, sample_size=2)
            restore_report = restore_sample(
                sampled,
                store=store,
                restore_root=root / "clean-room",
                max_object_bytes=1_000,
            )
            self.assertEqual(restore_report["status"], "ok")
            self.assertEqual(restore_report["sample_total"], 2)
            self.assertEqual(restore_report["restored_bytes"], sum(map(len, payloads)))


if __name__ == "__main__":
    unittest.main()
