from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_scale_snapshot import ScaleOriginError, write_json
from scripts.restore_hf_scale_origin import RESTORED_ATTESTATION_PATHS
from scripts.validate_restored_scale_origin import (
    audit_restored_inventory,
    corpus_result_summary,
    parse_csv_set,
    safe_child,
    validate_restored_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_MANIFEST = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "current-signed-scale-manifest-5d9ce557.json"
)
CURRENT_PUBLISH_REPORT = (
    REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/"
    "signed-scale-publish-report.json"
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
CURRENT_SNAPSHOT_PATH = (
    "scale/snapshots/2026-08-19/"
    "5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd"
)
CURRENT_MANIFEST_URL = (
    "https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/"
    f"{CURRENT_SNAPSHOT_PATH}/manifest.json"
)
REAL_REGISTRY = REPO_ROOT / "docs/etl/real-corpus-registry.json"
SCALE_READINESS = REPO_ROOT / "etl/data/published/scale-readiness-latest.json"
CANDIDATE_MANIFEST = (
    REPO_ROOT
    / "etl/data/published/candidate-occurrence-semantic-partition-manifest-latest.json"
)
CANDIDATE_VALIDATION = (
    REPO_ROOT / "etl/data/published/"
    "candidate-occurrence-semantic-partition-validation-latest.json"
)
CANDIDATE_INCREMENTAL_MANIFEST = (
    REPO_ROOT / "etl/data/published/"
    "candidate-occurrence-semantic-partition-incremental-latest.json"
)
CANDIDATE_INCREMENTAL_VALIDATION = (
    REPO_ROOT / "etl/data/published/"
    "candidate-occurrence-semantic-partition-validation-incremental-latest.json"
)
CANDIDATE_DATA_ROOT = REPO_ROOT / "etl/data/derived/semantic-candidate-occurrences"
OFFICIAL_CAPTURE = REPO_ROOT / "etl/data/raw/samples/congreso_votaciones_sample.json"


def current_manifest() -> dict[str, object]:
    return json.loads(CURRENT_MANIFEST.read_text(encoding="utf-8"))


def current_candidate_corpus(manifest: dict[str, object]) -> dict[str, object]:
    return next(
        item for item in manifest["corpora"] if item["id"] == "candidate_occurrences"
    )


def stage_current_candidate_restore(root: Path) -> dict[str, object]:
    manifest = current_manifest()
    shutil.copy2(CURRENT_MANIFEST, root / "manifest.json")
    restore_reference = json.loads(CURRENT_PUBLISH_REPORT.read_text(encoding="utf-8"))
    attestation = dict(restore_reference["attestation"])
    attestation.update(attestation.pop("remote_paths"))
    attestation["restored_files"] = dict(RESTORED_ATTESTATION_PATHS)
    restore_reference["attestation"] = attestation
    restore_reference["manifest_url"] = CURRENT_MANIFEST_URL
    restore_reference["selection_mode"] = "explicit_immutable_snapshot"
    write_json(root / "restore-reference.json", restore_reference)
    sources = {
        "real-corpus-registry.json": REAL_REGISTRY,
        "scale-readiness.json": SCALE_READINESS,
        "corpora/candidate_occurrences/manifest.json": CANDIDATE_MANIFEST,
        "corpora/candidate_occurrences/validation.json": CANDIDATE_VALIDATION,
        "corpora/candidate_occurrences/incremental-manifest.json": (
            CANDIDATE_INCREMENTAL_MANIFEST
        ),
        "corpora/candidate_occurrences/incremental-validation.json": (
            CANDIDATE_INCREMENTAL_VALIDATION
        ),
    }
    for relative, source in sources.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    control_sources = {
        "attestation": CURRENT_ATTESTATION,
        "signature": CURRENT_SIGNATURE,
        "public_key": CURRENT_PUBLIC_KEY,
    }
    for name, source in control_sources.items():
        destination = root / RESTORED_ATTESTATION_PATHS[name]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    candidate_prefix = "corpora/candidate_occurrences/data/"
    for entry in manifest["files"]:
        relative = str(entry["path"])
        if not relative.startswith(candidate_prefix):
            continue
        source = CANDIDATE_DATA_ROOT / relative.removeprefix(candidate_prefix)
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return manifest


class ValidateRestoredScaleOriginTests(unittest.TestCase):
    def test_parse_csv_set_deduplicates_real_corpus_ids(self) -> None:
        self.assertEqual(
            parse_csv_set(
                "candidate_occurrences, member_votes, candidate_occurrences, "
            ),
            {"candidate_occurrences", "member_votes"},
        )

    def test_safe_child_rejects_escape(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            self.assertRaises(ScaleOriginError),
        ):
            safe_child(Path(temp_dir), "../outside.json", "restored evidence")

    def test_real_candidate_summary_reconciles_signed_release_contract(self) -> None:
        manifest = current_manifest()
        corpus = current_candidate_corpus(manifest)
        validation = json.loads(CANDIDATE_VALIDATION.read_text(encoding="utf-8"))
        summary, errors = corpus_result_summary(
            corpus=corpus,
            validation=validation,
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["actual"]["rows"], 10_820)
        self.assertEqual(summary["actual"]["files"], 2)
        self.assertEqual(summary["actual"]["bytes"], 2_083_541)
        self.assertEqual(
            validation["totals"]["exact_public_name_rows"],
            summary["actual"]["rows"],
        )
        self.assertEqual(
            validation["totals"]["exact_source_text_rows"],
            summary["actual"]["rows"],
        )
        self.assertTrue(all(summary["checks"].values()))

    def test_real_candidate_restore_has_exact_isolated_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = stage_current_candidate_restore(root)
            inventory = audit_restored_inventory(
                root=root,
                manifest=manifest,
                corpus_ids={"candidate_occurrences"},
                reference_file_name="restore-reference.json",
                include_signed_attestation=True,
            )

            self.assertTrue(inventory["passed"])
            self.assertEqual(inventory["expected_files"], 13)
            self.assertEqual(inventory["actual_files"], 13)
            self.assertEqual(inventory["missing_files"], [])
            self.assertEqual(inventory["undeclared_files"], [])
            self.assertEqual(inventory["symlinks"], [])

    def test_real_candidate_restore_rejects_undeclared_official_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = stage_current_candidate_restore(root)
            unexpected = root / "undeclared" / OFFICIAL_CAPTURE.name
            unexpected.parent.mkdir(parents=True)
            shutil.copy2(OFFICIAL_CAPTURE, unexpected)
            inventory = audit_restored_inventory(
                root=root,
                manifest=manifest,
                corpus_ids={"candidate_occurrences"},
                reference_file_name="restore-reference.json",
                include_signed_attestation=True,
            )

            self.assertFalse(inventory["passed"])
            self.assertEqual(
                inventory["undeclared_files"],
                [f"undeclared/{OFFICIAL_CAPTURE.name}"],
            )

    def test_isolated_validation_rejects_external_registry_override(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            self.assertRaisesRegex(
                ScaleOriginError,
                "isolated validation requires bundled registry",
            ),
        ):
            validate_restored_bundle(
                root=Path(temp_dir),
                registry_path=REAL_REGISTRY,
                corpus_ids={"candidate_occurrences"},
                batch_rows=10_000,
                max_peak_rss_mb=1536.0,
                require_isolated=True,
            )

    def test_isolated_validation_rejects_missing_real_release_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stage_current_candidate_restore(root)
            (root / RESTORED_ATTESTATION_PATHS["signature"]).unlink()
            with self.assertRaisesRegex(
                ScaleOriginError,
                "restored signed attestation failed",
            ):
                validate_restored_bundle(
                    root=root,
                    registry_path=None,
                    corpus_ids={"candidate_occurrences"},
                    batch_rows=10_000,
                    max_peak_rss_mb=1536.0,
                    require_isolated=True,
                )


if __name__ == "__main__":
    unittest.main()
