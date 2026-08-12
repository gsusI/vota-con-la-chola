from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_scale_snapshot import sha256_file
from scripts.restore_hf_scale_origin import (
    restore_preflight,
    selected_manifest_files,
    validate_restore_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CAPTURE = REPO_ROOT / "etl/data/raw/samples/congreso_votaciones_sample.json"


class RestoreHFScaleOriginTests(unittest.TestCase):
    def test_explicit_restore_reference_requires_content_addressed_path(self) -> None:
        manifest = {
            "schema_version": "real-scale-origin-bundle-v2",
            "project": "vota-con-la-chola",
            "snapshot_date": "2026-08-12",
            "corpora": [],
            "files": [],
        }
        from scripts.publicar_hf_scale_snapshot import artifact_contract_sha256

        manifest["artifact_contract"] = {
            "schema_version": "real-scale-artifact-contract-v1",
            "sha256": artifact_contract_sha256(manifest),
        }
        import hashlib
        import json

        manifest_sha256 = hashlib.sha256(
            (
                json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
            ).encode()
        ).hexdigest()
        path = f"scale/snapshots/2026-08-12/{manifest_sha256}"
        reference = validate_restore_reference(
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            snapshot_path=path,
            selection_mode="explicit_immutable_snapshot",
        )
        self.assertEqual(reference["snapshot_path"], path)
        self.assertEqual(reference["release_id"], manifest_sha256)
        self.assertEqual(reference["selection_mode"], "explicit_immutable_snapshot")

    def test_selects_one_corpus_and_global_evidence(self) -> None:
        manifest = {
            "corpora": [{"id": "votes"}, {"id": "money"}],
            "files": [
                {
                    "path": "real-corpus-registry.json",
                    "bytes": 1,
                    "sha256": "a" * 64,
                    "kind": "metadata",
                },
                {
                    "path": "corpora/votes/data/votes.json.gz",
                    "bytes": 2,
                    "sha256": "b" * 64,
                    "kind": "data",
                },
                {
                    "path": "corpora/money/data/money.parquet",
                    "bytes": 3,
                    "sha256": "c" * 64,
                    "kind": "data",
                },
            ],
        }
        selected = selected_manifest_files(manifest, {"money"})
        self.assertEqual(
            [item["path"] for item in selected],
            [
                "corpora/money/data/money.parquet",
                "real-corpus-registry.json",
            ],
        )

    def test_preflight_reuses_checksum_verified_official_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            restored = destination / "corpora/votes/data/capture.json"
            restored.parent.mkdir(parents=True)
            shutil.copy2(OFFICIAL_CAPTURE, restored)
            files = [
                {
                    "path": "corpora/votes/data/capture.json",
                    "bytes": OFFICIAL_CAPTURE.stat().st_size,
                    "sha256": sha256_file(OFFICIAL_CAPTURE),
                }
            ]
            report = restore_preflight(
                destination_root=destination,
                files=files,
                min_free_bytes=0,
            )
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["reusable_files"], 1)
            self.assertEqual(report["missing_files"], 0)
            self.assertEqual(report["missing_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
