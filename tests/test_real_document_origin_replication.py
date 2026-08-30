from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publicdata_core.object_store import FilesystemObjectStore, hash_file
from publicdata_docs.generation_manifest import (
    audit_generation_lifecycle,
    iter_generation_rows,
    publish_generation_manifest,
)
from scripts.replicate_real_document_origin import (
    DATASET,
    POLICY,
    ROW_SCHEMA,
    iter_replica_rows,
    open_state,
    replicate_queue,
    state_counts,
    upsert_object,
)
from scripts.verify_real_document_origin_restore import (
    restore_all_bounded,
    scan_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "etl/data/raw"
NATIVE_ROOT = ROOT / "etl/data/derived/real-document-text-corpus-v2"
OCR_ROOT = ROOT / "etl/data/derived/real-document-page-ocr-v2"
NATIVE_MANIFEST = ROOT / "etl/data/published/real-document-text-manifest-latest.jsonl"
OCR_MANIFEST = ROOT / "etl/data/published/real-document-page-ocr-manifest-latest.jsonl"


class RealDocumentOriginReplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        required = [RAW_ROOT, NATIVE_ROOT, OCR_ROOT, NATIVE_MANIFEST, OCR_MANIFEST]
        if not all(path.exists() for path in required):
            self.skipTest("real production raw/native/OCR corpus is unavailable")
        self.native_row = next(
            row
            for row in iter_generation_rows(
                NATIVE_MANIFEST,
                dataset="native_text",
                row_schema_version="real_document_text_manifest_row_v1",
            )
            if row.get("native_text_cas_path")
        )
        self.ocr_row = next(
            row
            for row in iter_generation_rows(
                OCR_MANIFEST,
                dataset="page_ocr",
                row_schema_version="real_document_page_ocr_manifest_row_v1",
            )
            if row.get("ocr_text_cas_path")
        )

    def test_real_raw_native_and_ocr_objects_replicate_and_clean_restore(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="real-document-origin-test-", dir=ROOT / "etl/data/staging"
        ) as temp_dir:
            root = Path(temp_dir)
            conn = open_state(root / "state.sqlite")
            try:
                raw_relative = str(self.native_row["path"])
                upsert_object(
                    conn,
                    object_class="raw_document",
                    semantic_sha256=str(self.native_row["content_sha256"]),
                    blob_sha256=str(self.native_row["content_sha256"]),
                    bytes_value=int(self.native_row["bytes"]),
                    content_type=str(self.native_row["mime_type"]),
                    source_relative_path=raw_relative,
                    namespace="real-documents/raw",
                )
                native_relative = str(self.native_row["native_text_cas_path"])
                native_blob_sha, native_bytes = hash_file(NATIVE_ROOT / native_relative)
                upsert_object(
                    conn,
                    object_class="native_text",
                    semantic_sha256=str(self.native_row["native_text_sha256"]),
                    blob_sha256=native_blob_sha,
                    bytes_value=native_bytes,
                    content_type="application/gzip",
                    source_relative_path=native_relative,
                    namespace="real-documents/native-text-gzip",
                )
                ocr_relative = str(self.ocr_row["ocr_text_cas_path"])
                ocr_blob_sha, ocr_bytes = hash_file(OCR_ROOT / ocr_relative)
                upsert_object(
                    conn,
                    object_class="ocr_text",
                    semantic_sha256=str(self.ocr_row["ocr_text_sha256"]),
                    blob_sha256=ocr_blob_sha,
                    bytes_value=ocr_bytes,
                    content_type="application/gzip",
                    source_relative_path=ocr_relative,
                    namespace="real-documents/ocr-text-gzip",
                )
                conn.commit()
                store = FilesystemObjectStore(root / "origin")
                run = replicate_queue(
                    conn,
                    store=store,
                    raw_root=RAW_ROOT,
                    native_root=NATIVE_ROOT,
                    ocr_root=OCR_ROOT,
                    workers=3,
                    claim_size=3,
                    max_items=0,
                    max_attempts=2,
                    lease_seconds=60,
                )
                manifest = root / "replicas.json"
                published = publish_generation_manifest(
                    manifest_path=manifest,
                    rows=iter_replica_rows(conn),
                    dataset=DATASET,
                    row_schema_version=ROW_SCHEMA,
                    state_connection=conn,
                    max_rows=2,
                    max_uncompressed_bytes=1024 * 1024,
                    policy=POLICY,
                )
            finally:
                conn.close()

            lifecycle = audit_generation_lifecycle(
                manifest,
                dataset=DATASET,
                full_shard_check=True,
                full_state_check=True,
            )
            inventory = scan_manifest(manifest)
            restored = restore_all_bounded(
                manifest=manifest,
                store=store,
                workers=3,
                batch_size=3,
                max_object_bytes=2 * 1024 * 1024 * 1024,
                scratch_root=root / "clean-room",
            )
            self.assertEqual(run, {"attempted": 3, "succeeded": 3, "failed": 0})
            check_conn = open_state(root / "state.sqlite")
            try:
                self.assertEqual(state_counts(check_conn), {"succeeded": 3})
            finally:
                check_conn.close()
            self.assertEqual(published["rows"], 3)
            self.assertEqual(lifecycle["status"], "ok")
            self.assertEqual(
                inventory["objects_by_class"],
                {"native_text": 1, "ocr_text": 1, "raw_document": 1},
            )
            self.assertEqual(restored["objects"], 3)
            self.assertEqual(restored["bytes"], inventory["bytes"])
            self.assertEqual(
                restored["objects_by_class"], inventory["objects_by_class"]
            )


if __name__ == "__main__":
    unittest.main()
