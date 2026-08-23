from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_scale_snapshot import ScaleOriginError, sha256_file
from scripts.restore_hf_scale_origin import (
    destination_state,
    download_manifest_files_bounded,
    require_empty_destination,
    restore_preflight,
    restored_attestation_metadata,
    safe_destination_child,
    selected_manifest_files,
    validate_restore_reference,
    verify_restore_attestation_files,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CAPTURE = REPO_ROOT / "etl/data/raw/samples/congreso_votaciones_sample.json"
OFFICIAL_CAPTURES = (
    OFFICIAL_CAPTURE,
    REPO_ROOT / "etl/data/raw/samples/congreso_iniciativas_sample.json",
    REPO_ROOT / "etl/data/raw/samples/senado_votaciones_sample.xml",
)
CURRENT_MANIFEST = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-signed-scale-manifest-5d9ce557.json"
)
CURRENT_ATTESTATION = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-snapshot-attestation.json"
)
CURRENT_SIGNATURE = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-snapshot-attestation.json.sig"
)
CURRENT_PUBLIC_KEY = REPO_ROOT / "docs/ops/keys/vclc-snapshot-release-2026.pub"
CURRENT_ALLOWED_SIGNERS = (
    REPO_ROOT / "docs/ops/keys/vclc-snapshot-release-2026.allowed_signers"
)
CURRENT_PUBLISH_REPORT = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "signed-scale-publish-report.json"
)
CURRENT_SNAPSHOT_PATH = (
    "scale/snapshots/2026-08-19/"
    "5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd"
)
CURRENT_MANIFEST_URL = (
    "https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/"
    f"{CURRENT_SNAPSHOT_PATH}/manifest.json"
)


def current_attestation_pointer() -> dict[str, object]:
    publish = json.loads(CURRENT_PUBLISH_REPORT.read_text(encoding="utf-8"))
    attestation = copy.deepcopy(publish["attestation"])
    attestation.update(attestation.pop("remote_paths"))
    return attestation


class RestoreHFScaleOriginTests(unittest.TestCase):
    def test_explicit_restore_reference_requires_content_addressed_path(self) -> None:
        manifest = json.loads(CURRENT_MANIFEST.read_text(encoding="utf-8"))
        manifest_sha256 = sha256_file(CURRENT_MANIFEST)
        reference = validate_restore_reference(
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            snapshot_path=CURRENT_SNAPSHOT_PATH,
            selection_mode="explicit_immutable_snapshot",
        )
        self.assertEqual(reference["snapshot_path"], CURRENT_SNAPSHOT_PATH)
        self.assertEqual(reference["release_id"], manifest_sha256)
        self.assertEqual(reference["selection_mode"], "explicit_immutable_snapshot")

    def test_selects_one_corpus_and_global_evidence(self) -> None:
        manifest = json.loads(CURRENT_MANIFEST.read_text(encoding="utf-8"))
        selected = selected_manifest_files(manifest, {"candidate_occurrences"})
        self.assertEqual(len(selected), 8)
        self.assertEqual(sum(int(item["bytes"]) for item in selected), 2_211_900)
        self.assertEqual(
            sum(1 for item in selected if item.get("kind") == "data"),
            2,
        )
        self.assertIn(
            "real-corpus-registry.json", {str(item["path"]) for item in selected}
        )

    def test_real_release_attestation_is_bound_to_restore_subject(self) -> None:
        verification = verify_restore_attestation_files(
            manifest_path=CURRENT_MANIFEST,
            attestation_path=CURRENT_ATTESTATION,
            signature_path=CURRENT_SIGNATURE,
            public_key_path=CURRENT_PUBLIC_KEY,
            allowed_signers_path=CURRENT_ALLOWED_SIGNERS,
            signer_identity="vclc-snapshot-release-2026",
            manifest_url=CURRENT_MANIFEST_URL,
            snapshot_path=CURRENT_SNAPSHOT_PATH,
            snapshot_date="2026-08-19",
            attestation_meta=current_attestation_pointer(),
        )

        self.assertTrue(verification["passed"])
        self.assertEqual(verification["errors"], [])
        metadata = restored_attestation_metadata(
            verification,
            snapshot_path=CURRENT_SNAPSHOT_PATH,
        )
        self.assertEqual(
            metadata["restored_files"],
            {
                "attestation": "attestation/attestation.json",
                "signature": "attestation/attestation.json.sig",
                "public_key": "attestation/signing-key.pub",
            },
        )
        self.assertEqual(
            metadata["public_key_fingerprint"],
            "SHA256:R2B1jFbkLoigmKxObr+ExlBLrKENkaUDp0C3ip0Lj7A",
        )

    def test_real_release_attestation_rejects_cross_release_pointer(self) -> None:
        attestation_meta = current_attestation_pointer()
        attestation_meta["signature"] = (
            "scale/snapshots/2026-08-12/"
            "5872efaf918430c0c9e2b3b5b01fd9efe4ba03ff586da75419e28dfdb0b2e139/"
            "attestation/attestation.json.sig"
        )
        verification = verify_restore_attestation_files(
            manifest_path=CURRENT_MANIFEST,
            attestation_path=CURRENT_ATTESTATION,
            signature_path=CURRENT_SIGNATURE,
            public_key_path=CURRENT_PUBLIC_KEY,
            allowed_signers_path=CURRENT_ALLOWED_SIGNERS,
            signer_identity="vclc-snapshot-release-2026",
            manifest_url=CURRENT_MANIFEST_URL,
            snapshot_path=CURRENT_SNAPSHOT_PATH,
            snapshot_date="2026-08-19",
            attestation_meta=attestation_meta,
        )

        self.assertFalse(verification["passed"])
        self.assertIn(
            "latest pointer signature path escapes selected snapshot",
            verification["errors"],
        )

    def test_clean_room_destination_must_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "candidate-clean-room"
            initial = require_empty_destination(destination)
            self.assertFalse(initial["existed"])
            destination.mkdir()
            shutil.copy2(OFFICIAL_CAPTURE, destination / OFFICIAL_CAPTURE.name)
            with self.assertRaisesRegex(
                ScaleOriginError, "clean-room restore destination is not empty"
            ):
                require_empty_destination(destination)
            state = destination_state(destination)
            self.assertEqual(state["files"], 1)
            self.assertEqual(state["bytes"], OFFICIAL_CAPTURE.stat().st_size)

    def test_restore_target_rejects_descendant_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            destination = temp_root / "candidate-clean-room"
            outside = temp_root / "outside"
            destination.mkdir()
            outside.mkdir()
            (destination / "corpora").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                ScaleOriginError,
                "restore target escapes destination",
            ):
                safe_destination_child(
                    destination,
                    "corpora/candidate_occurrences/data/part-00000.parquet",
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

    def test_download_queue_is_worker_bounded_for_real_official_captures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            files = []
            for source in OFFICIAL_CAPTURES:
                relative = f"corpora/official-captures/data/{source.name}"
                restored = destination / relative
                restored.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, restored)
                files.append(
                    {
                        "path": relative,
                        "bytes": source.stat().st_size,
                        "sha256": sha256_file(source),
                    }
                )
            summary = download_manifest_files_bounded(
                base_url=(
                    "https://huggingface.co/datasets/"
                    "JesusIC/vota-con-la-chola-data/resolve/main"
                ),
                snapshot_path=CURRENT_SNAPSHOT_PATH,
                destination=destination,
                files=files,
                workers=1,
                timeout=120,
            )

            self.assertEqual(summary["downloaded_files"], 0)
            self.assertEqual(summary["reused_files"], len(OFFICIAL_CAPTURES))
            self.assertEqual(
                summary["reused_bytes"],
                sum(source.stat().st_size for source in OFFICIAL_CAPTURES),
            )
            self.assertLessEqual(
                summary["max_pending_downloads"],
                summary["download_queue_limit"],
            )
            self.assertEqual(summary["download_queue_limit"], 2)


if __name__ == "__main__":
    unittest.main()
