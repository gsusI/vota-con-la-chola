from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import manage_boe_document_corpus
from scripts.audit_boe_document_corpus_generations import audit_generations
from scripts.audit_document_provenance import (
    create_work_database,
    load_boe_document_corpus_lineage_manifest,
)
from scripts.manage_boe_document_corpus import export_manifest, source_record_metadata
from scripts.validate_boe_document_corpus_manifest import validate_manifest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = ROOT / "etl/data/staging/politicos-es.db"


class BoeDocumentCorpusShardedManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        if not PRODUCTION_DB.is_file():
            self.skipTest("real BOE corpus database is unavailable")
        source = sqlite3.connect(PRODUCTION_DB)
        source.row_factory = sqlite3.Row
        try:
            documents = source.execute(
                """
                SELECT t.source_url, t.source_id, t.fetched_at, t.content_type,
                       t.content_sha256, t.bytes, t.raw_path, s.raw_payload
                FROM text_documents AS t
                JOIN source_records AS s
                  ON s.source_record_pk = t.source_record_pk
                WHERE t.source_id = 'boe_document_xml'
                ORDER BY t.source_url
                LIMIT 2
                """
            ).fetchall()
            if len(documents) != 2:
                self.skipTest("two real BOE document captures are unavailable")
            summary_urls = sorted(
                {
                    str(
                        (
                            source_record_metadata(row["raw_payload"]).get(
                                "queue_payload"
                            )
                            or {}
                        ).get("summary_source_url")
                        or ""
                    )
                    for row in documents
                }
            )
            summaries = source.execute(
                f"""
                SELECT t.source_url, t.source_id, t.fetched_at, t.content_type,
                       t.content_sha256, t.bytes, t.raw_path, s.raw_payload
                FROM text_documents AS t
                JOIN source_records AS s
                  ON s.source_record_pk = t.source_record_pk
                WHERE t.source_id = 'boe_daily_summaries'
                  AND t.source_url IN ({",".join("?" for _ in summary_urls)})
                ORDER BY t.source_url
                """,
                summary_urls,
            ).fetchall()
        finally:
            source.close()
        if len(summaries) != len(summary_urls):
            self.skipTest("real BOE summary lineage is incomplete")
        self.documents = [dict(row) for row in documents]
        self.summaries = [dict(row) for row in summaries]

    def new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              raw_payload TEXT NOT NULL
            );
            CREATE TABLE text_documents (
              source_url TEXT NOT NULL,
              source_id TEXT NOT NULL,
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              source_record_pk INTEGER NOT NULL
            );
            """
        )
        rows = [*self.summaries, *self.documents]
        for source_record_pk, row in enumerate(rows, start=1):
            connection.execute(
                "INSERT INTO source_records(source_record_pk, raw_payload) VALUES (?, ?)",
                (source_record_pk, row["raw_payload"]),
            )
            connection.execute(
                """
                INSERT INTO text_documents(
                  source_url, source_id, fetched_at, content_type,
                  content_sha256, bytes, raw_path, source_record_pk
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source_url"],
                    row["source_id"],
                    row["fetched_at"],
                    row["content_type"],
                    row["content_sha256"],
                    row["bytes"],
                    row["raw_path"],
                    source_record_pk,
                ),
            )
        connection.commit()
        return connection

    def test_real_rows_export_to_deterministic_bounded_shards(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="boe-lineage-test-", dir=ROOT / "etl/data/staging"
        ) as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            connection = self.new_connection()
            try:
                first = export_manifest(
                    connection,
                    output_path=manifest_path,
                    shard_max_rows=1,
                    shard_max_uncompressed_bytes=1024 * 1024,
                )
                second = export_manifest(
                    connection,
                    output_path=manifest_path,
                    shard_max_rows=1,
                    shard_max_uncompressed_bytes=1024 * 1024,
                )
            finally:
                connection.close()
            self.assertEqual(first["rows"], 2)
            self.assertEqual(first["shard_files"], 2)
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["logical_sha256"], second["logical_sha256"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["schema_version"],
                "boe_document_corpus_lineage_manifest_v1",
            )
            self.assertEqual(manifest["totals"]["rows"], 2)
            self.assertEqual(manifest["totals"]["shard_files"], 2)
            validation = validate_manifest(manifest_path, full_raw_check=True)
            self.assertEqual(validation["status"], "ok")
            self.assertTrue(all(validation["checks"].values()))
            self.assertEqual(validation["totals"]["rows"], 2)
            self.assertTrue(
                validation["checks"]["policy_retains_official_public_information"]
            )
            self.assertTrue(validation["checks"]["no_synthetic_or_mock_rows"])
            work = create_work_database(Path(temp_dir) / "audit.sqlite")
            try:
                audit = load_boe_document_corpus_lineage_manifest(
                    work,
                    manifest_path,
                    repo_root=ROOT,
                    inventory_root=ROOT / "etl/data/raw",
                )
            finally:
                work.close()
            self.assertEqual(audit["status"], "ok")
            self.assertEqual(audit["rows"], 2)
            self.assertEqual(audit["accepted_checksum_captures"], 2)
            self.assertEqual(audit["sha256"], first["sha256"])

    def test_interrupted_rebuild_preserves_live_index_and_superseded_generation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="boe-lineage-lifecycle-test-", dir=ROOT / "etl/data/staging"
        ) as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            connection = self.new_connection()
            try:
                first = export_manifest(
                    connection,
                    output_path=manifest_path,
                    shard_max_rows=1,
                    shard_max_uncompressed_bytes=1024 * 1024,
                )
                first_bytes = manifest_path.read_bytes()
                first_root = ROOT / first["shard_root"]
                connection.execute(
                    """
                    DELETE FROM text_documents
                    WHERE rowid = (
                      SELECT MAX(rowid) FROM text_documents
                      WHERE source_id = 'boe_document_xml'
                    )
                    """
                )
                connection.commit()
                original_atomic_write_text = (
                    manage_boe_document_corpus.atomic_write_text
                )

                def interrupt_live_switch(path: Path, payload: str) -> None:
                    if Path(path) == manifest_path:
                        raise OSError("simulated interruption before live index switch")
                    original_atomic_write_text(Path(path), payload)

                with (
                    mock.patch.object(
                        manage_boe_document_corpus,
                        "atomic_write_text",
                        side_effect=interrupt_live_switch,
                    ),
                    self.assertRaisesRegex(OSError, "simulated interruption"),
                ):
                    export_manifest(
                        connection,
                        output_path=manifest_path,
                        shard_max_rows=1,
                        shard_max_uncompressed_bytes=1024 * 1024,
                    )
                self.assertEqual(manifest_path.read_bytes(), first_bytes)
                interrupted = audit_generations(
                    manifest_path,
                    full_shard_check=True,
                )
                self.assertEqual(interrupted["status"], "degraded")
                self.assertEqual(
                    interrupted["totals"]["unactivated_manifest_archives"], 1
                )
                self.assertEqual(
                    interrupted["totals"]["unactivated_generation_directories"],
                    1,
                )
                self.assertEqual(interrupted["totals"]["automatic_deletions"], 0)
                self.assertEqual(
                    validate_manifest(manifest_path, full_raw_check=True)["status"],
                    "ok",
                )
                second = export_manifest(
                    connection,
                    output_path=manifest_path,
                    shard_max_rows=1,
                    shard_max_uncompressed_bytes=1024 * 1024,
                )
                replay = export_manifest(
                    connection,
                    output_path=manifest_path,
                    shard_max_rows=1,
                    shard_max_uncompressed_bytes=1024 * 1024,
                )
                canonical_second_bytes = manifest_path.read_bytes()
                restored_document = self.documents[-1]
                restored_source_record_pk = connection.execute(
                    "SELECT source_record_pk FROM source_records WHERE raw_payload = ?",
                    (restored_document["raw_payload"],),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO text_documents(
                      source_url, source_id, fetched_at, content_type,
                      content_sha256, bytes, raw_path, source_record_pk
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        restored_document["source_url"],
                        restored_document["source_id"],
                        restored_document["fetched_at"],
                        restored_document["content_type"],
                        restored_document["content_sha256"],
                        restored_document["bytes"],
                        restored_document["raw_path"],
                        restored_source_record_pk,
                    ),
                )
                connection.commit()
                with self.assertRaisesRegex(
                    RuntimeError,
                    "historical BOE lineage manifest reactivation requires",
                ):
                    export_manifest(
                        connection,
                        output_path=manifest_path,
                        shard_max_rows=1,
                        shard_max_uncompressed_bytes=1024 * 1024,
                    )
            finally:
                connection.close()
            completed = audit_generations(
                manifest_path,
                full_shard_check=True,
            )
            self.assertEqual(second["rows"], 1)
            self.assertNotEqual(first["sha256"], second["sha256"])
            self.assertEqual(replay["sha256"], second["sha256"])
            self.assertFalse(replay["publication"]["live_index_changed"])
            self.assertTrue(replay["publication"]["superseded_predecessor"])
            self.assertEqual(manifest_path.read_bytes(), canonical_second_bytes)
            self.assertEqual(completed["status"], "ok")
            self.assertTrue(all(completed["checks"].values()))
            self.assertEqual(completed["totals"]["manifest_archives"], 2)
            self.assertEqual(completed["totals"]["activation_receipts"], 2)
            self.assertEqual(completed["totals"]["superseded_generations"], 1)
            self.assertEqual(completed["totals"]["retained_unique_generations"], 2)
            self.assertEqual(completed["totals"]["automatic_deletions"], 0)
            self.assertTrue(first_root.is_dir())


if __name__ == "__main__":
    unittest.main()
