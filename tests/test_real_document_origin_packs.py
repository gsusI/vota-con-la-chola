from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publicdata_docs.generation_manifest import (
    audit_generation_lifecycle,
    iter_generation_rows,
    publish_generation_manifest,
)
from scripts.pack_real_document_origin import (
    DATASET,
    POLICY,
    ROW_SCHEMA,
    iter_pack_rows,
    open_state,
    run_pack_queue,
    seed_plan,
    state_counts,
)
from scripts.replicate_real_document_origin import (
    DATASET as ORIGIN_DATASET,
)
from scripts.replicate_real_document_origin import (
    POLICY as ORIGIN_POLICY,
)
from scripts.replicate_real_document_origin import (
    ROW_SCHEMA as ORIGIN_ROW_SCHEMA,
)
from scripts.verify_real_document_origin_packs import verify_all

ROOT = Path(__file__).resolve().parents[1]
ORIGIN_ROOT = ROOT / "etl/data/object-origin/real-document-corpus-v1"
ORIGIN_MANIFEST = ROOT / "etl/data/manifests/real-document-origin-replicas.json"


class RealDocumentOriginPackTests(unittest.TestCase):
    def setUp(self) -> None:
        if not ORIGIN_ROOT.is_dir() or not ORIGIN_MANIFEST.is_file():
            self.skipTest("real production object-origin generation is unavailable")
        selected = {}
        for row in iter_generation_rows(
            ORIGIN_MANIFEST,
            dataset=ORIGIN_DATASET,
            row_schema_version=ORIGIN_ROW_SCHEMA,
            allow_legacy_jsonl=False,
        ):
            selected.setdefault(str(row["object_class"]), row)
            if len(selected) == 3:
                break
        self.real_rows = [
            selected[object_class]
            for object_class in ("raw_document", "native_text", "ocr_text")
        ]

    def test_real_objects_form_deterministic_bounded_pack_and_fully_verify(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="real-document-pack-test-", dir=ROOT / "etl/data/staging"
        ) as temp_dir:
            root = Path(temp_dir)
            source_state = open_state(root / "source-state.sqlite")
            source_manifest = root / "origin-subset.json"
            try:
                source_manifest_report = publish_generation_manifest(
                    manifest_path=source_manifest,
                    rows=self.real_rows,
                    dataset=ORIGIN_DATASET,
                    row_schema_version=ORIGIN_ROW_SCHEMA,
                    state_connection=source_state,
                    max_rows=3,
                    max_uncompressed_bytes=1024 * 1024,
                    policy=ORIGIN_POLICY,
                )
            finally:
                source_state.close()

            state = open_state(root / "pack-state.sqlite")
            pack_manifest = root / "packs.json"
            try:
                plan = seed_plan(
                    state,
                    origin_manifest=source_manifest,
                    origin_root=ORIGIN_ROOT,
                    max_objects=3,
                    max_payload_bytes=2 * 1024**3,
                )
                run = run_pack_queue(
                    state,
                    origin_root=ORIGIN_ROOT,
                    pack_root=root / "pack-root",
                    gzip_level=6,
                    workers=1,
                    max_packs=0,
                    max_attempts=2,
                    lease_seconds=60,
                )
                published = publish_generation_manifest(
                    manifest_path=pack_manifest,
                    rows=iter_pack_rows(state, source_manifest_report["sha256"]),
                    dataset=DATASET,
                    row_schema_version=ROW_SCHEMA,
                    state_connection=state,
                    max_rows=10,
                    max_uncompressed_bytes=1024 * 1024,
                    policy=POLICY,
                )
                states = state_counts(state)
                original_descriptor = next(
                    iter_pack_rows(state, source_manifest_report["sha256"])
                )
            finally:
                state.close()

            lifecycle = audit_generation_lifecycle(
                pack_manifest,
                dataset=DATASET,
                full_shard_check=True,
                full_state_check=True,
            )
            replay_state = open_state(root / "pack-replay-state.sqlite")
            try:
                seed_plan(
                    replay_state,
                    origin_manifest=source_manifest,
                    origin_root=ORIGIN_ROOT,
                    max_objects=3,
                    max_payload_bytes=2 * 1024**3,
                )
                replay_run = run_pack_queue(
                    replay_state,
                    origin_root=ORIGIN_ROOT,
                    pack_root=root / "pack-replay-root",
                    gzip_level=6,
                    workers=1,
                    max_packs=0,
                    max_attempts=2,
                    lease_seconds=60,
                )
                replay_descriptor = next(
                    iter_pack_rows(replay_state, source_manifest_report["sha256"])
                )
            finally:
                replay_state.close()
            verified = verify_all(
                manifest=pack_manifest,
                pack_root=root / "pack-root",
                max_object_bytes=2 * 1024**3,
            )
            expected_bytes = sum(int(row["bytes"]) for row in self.real_rows)
            self.assertEqual(plan["packs"], 1)
            self.assertEqual(plan["objects"], 3)
            self.assertEqual(run, {"attempted": 1, "succeeded": 1, "failed": 0})
            self.assertEqual(replay_run, {"attempted": 1, "succeeded": 1, "failed": 0})
            self.assertEqual(states, {"succeeded": 1})
            self.assertEqual(published["rows"], 1)
            self.assertEqual(lifecycle["status"], "ok")
            self.assertEqual(verified["objects"], 3)
            self.assertEqual(verified["payload_bytes"], expected_bytes)
            self.assertEqual(
                original_descriptor["archive_sha256"],
                replay_descriptor["archive_sha256"],
            )
            self.assertEqual(
                original_descriptor["member_manifest_sha256"],
                replay_descriptor["member_manifest_sha256"],
            )
            self.assertEqual(
                verified["objects_by_class"],
                {"native_text": 1, "ocr_text": 1, "raw_document": 1},
            )


if __name__ == "__main__":
    unittest.main()
