from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from publicdata_docs import generation_manifest
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    audit_generation_lifecycle,
    iter_generation_rows,
    publish_generation_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_MANIFEST = (
    ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
)
POLICY = {
    "official_real_documents_only": True,
    "synthetic_or_mock_records_counted": False,
    "official_public_domain_personal_information_retained": True,
    "native_text_is_not_sanitized_or_identity_stripped": True,
    "automatic_deletion_forbidden": True,
}


class RealDocumentGenerationLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        if not PRODUCTION_MANIFEST.is_file():
            self.skipTest("real native document manifest is unavailable")
        self.real_rows = []
        for row in iter_generation_rows(
            PRODUCTION_MANIFEST,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
        ):
            self.real_rows.append(row)
            if len(self.real_rows) == 2:
                break
        if len(self.real_rows) != 2:
            self.skipTest("two real native document rows are unavailable")

    def new_state(self, path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(str(path))
        connection.execute(
            "CREATE TABLE real_rows(path TEXT PRIMARY KEY, content_sha256 TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO real_rows(path, content_sha256) VALUES (?, ?)",
            [(str(row["path"]), str(row["content_sha256"])) for row in self.real_rows],
        )
        connection.commit()
        return connection

    def publish(
        self,
        connection: sqlite3.Connection,
        manifest: Path,
        rows: list[dict[str, object]],
    ) -> dict[str, object]:
        return publish_generation_manifest(
            manifest_path=manifest,
            rows=rows,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            state_connection=connection,
            max_rows=1,
            max_uncompressed_bytes=1024 * 1024,
            policy=POLICY,
        )

    def test_interruption_preserves_active_real_generation_and_retains_candidate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="real-document-generation-test-", dir=ROOT / "etl/data/staging"
        ) as temp_dir:
            root = Path(temp_dir)
            manifest = root / "manifest-latest.jsonl"
            connection = self.new_state(root / "state.sqlite")
            try:
                first = self.publish(connection, manifest, self.real_rows)
                first_bytes = manifest.read_bytes()
                connection.execute(
                    "DELETE FROM real_rows WHERE path = ?",
                    (str(self.real_rows[1]["path"]),),
                )
                connection.commit()
                original_atomic_write = generation_manifest.atomic_write_bytes

                def interrupt_live_switch(path: Path, payload: bytes) -> None:
                    if Path(path) == manifest:
                        raise OSError("simulated interruption before live index switch")
                    original_atomic_write(Path(path), payload)

                with (
                    mock.patch.object(
                        generation_manifest,
                        "atomic_write_bytes",
                        side_effect=interrupt_live_switch,
                    ),
                    self.assertRaisesRegex(OSError, "simulated interruption"),
                ):
                    self.publish(connection, manifest, self.real_rows[:1])
                self.assertEqual(manifest.read_bytes(), first_bytes)
                interrupted = audit_generation_lifecycle(
                    manifest,
                    dataset="native_text",
                    full_shard_check=True,
                    full_state_check=True,
                )
                self.assertEqual(interrupted["status"], "degraded")
                self.assertEqual(
                    interrupted["totals"]["unactivated_manifest_archives"], 1
                )
                self.assertEqual(
                    interrupted["totals"]["unactivated_activation_receipts"], 1
                )
                second = self.publish(connection, manifest, self.real_rows[:1])
                replay = self.publish(connection, manifest, self.real_rows[:1])
                second_bytes = manifest.read_bytes()
                connection.execute(
                    "INSERT INTO real_rows(path, content_sha256) VALUES (?, ?)",
                    (
                        str(self.real_rows[1]["path"]),
                        str(self.real_rows[1]["content_sha256"]),
                    ),
                )
                connection.commit()
                with self.assertRaisesRegex(
                    GenerationManifestError,
                    "historical generation reactivation requires",
                ):
                    self.publish(connection, manifest, self.real_rows)
            finally:
                connection.close()
            completed = audit_generation_lifecycle(
                manifest,
                dataset="native_text",
                full_shard_check=True,
                full_state_check=True,
            )
            self.assertEqual(first["rows"], 2)
            self.assertEqual(second["rows"], 1)
            self.assertEqual(second["sha256"], replay["sha256"])
            self.assertFalse(replay["publication"]["live_index_changed"])
            self.assertEqual(manifest.read_bytes(), second_bytes)
            self.assertEqual(completed["status"], "ok")
            self.assertTrue(all(completed["checks"].values()))
            self.assertEqual(completed["totals"]["manifest_archives"], 2)
            self.assertEqual(completed["totals"]["activation_receipts"], 2)
            self.assertEqual(completed["totals"]["superseded_generations"], 1)
            self.assertEqual(completed["totals"]["retained_state_snapshots"], 2)
            self.assertEqual(completed["totals"]["automatic_deletions"], 0)


if __name__ == "__main__":
    unittest.main()
