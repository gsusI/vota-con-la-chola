from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_real_document_origin_release import (
    parse_args as parse_prepare_args,
)
from scripts.prepare_real_document_origin_release import prepare_release
from scripts.publish_real_document_origin_hf import (
    OriginPublicationError,
    batches,
    run,
    validate_local_upload_plan,
)
from scripts.publish_real_document_origin_hf import (
    parse_args as parse_publish_args,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
UPLOAD_PLAN = EVIDENCE_ROOT / "real-document-origin-upload-plan.json"
RELEASE_MANIFEST = EVIDENCE_ROOT / "real-document-origin-release-manifest.json"
POINTER = EVIDENCE_ROOT / "real-document-origin-release-latest.json"


class RealDocumentOriginReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        required = [UPLOAD_PLAN, RELEASE_MANIFEST, POINTER]
        missing = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in required
            if not path.is_file()
        ]
        if missing:
            raise unittest.SkipTest(
                "real production origin release artifacts unavailable: "
                + ", ".join(missing)
            )
        cls.validated = validate_local_upload_plan(UPLOAD_PLAN)

    def test_real_release_is_exact_and_retains_public_identity(self) -> None:
        manifest = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
        release_files = int(manifest["summary"]["release_files"])
        release_bytes = int(manifest["summary"]["release_bytes"])
        self.assertEqual(self.validated["total_files"], release_files)
        self.assertEqual(self.validated["total_bytes"], release_bytes)
        self.assertEqual(len(manifest["files"]), release_files)
        self.assertEqual(
            sum(int(item["bytes"]) for item in manifest["files"]),
            release_bytes,
        )
        self.assertEqual(manifest["summary"]["packs"], 25)
        self.assertEqual(manifest["summary"]["objects"], 240_226)
        self.assertGreater(manifest["summary"]["payload_bytes"], 0)
        self.assertIs(
            manifest["policy"]["official_public_domain_personal_information_retained"],
            True,
        )
        self.assertIs(manifest["policy"]["official_real_records_only"], True)
        self.assertIs(manifest["policy"]["synthetic_or_mock_records_forbidden"], True)
        serialized = RELEASE_MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("file:///", serialized)

    def test_prepare_replays_deterministically_from_real_generation(self) -> None:
        manifest_dir = REPO_ROOT / "etl/data/manifests"
        evidence_dir = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
        with (
            tempfile.TemporaryDirectory(
                prefix="origin-release-test-", dir=manifest_dir
            ) as manifest_temp,
            tempfile.TemporaryDirectory(
                prefix="origin-release-test-", dir=evidence_dir
            ) as evidence_temp,
        ):
            manifest_temp_path = Path(manifest_temp)
            evidence_temp_path = Path(evidence_temp)
            outputs = {
                "manifest": manifest_temp_path / "release.json",
                "plan": manifest_temp_path / "plan.json",
                "pointer": manifest_temp_path / "latest.json",
                "report": evidence_temp_path / "report.json",
            }
            args = parse_prepare_args(
                [
                    "--release-manifest-out",
                    outputs["manifest"].relative_to(REPO_ROOT).as_posix(),
                    "--upload-plan-out",
                    outputs["plan"].relative_to(REPO_ROOT).as_posix(),
                    "--pointer-out",
                    outputs["pointer"].relative_to(REPO_ROOT).as_posix(),
                    "--report-out",
                    outputs["report"].relative_to(REPO_ROOT).as_posix(),
                    "--enforce",
                ]
            )
            report = prepare_release(args)
            self.assertEqual(report["status"], "ready_for_authorized_publication")
            self.assertEqual(
                outputs["manifest"].read_bytes(), RELEASE_MANIFEST.read_bytes()
            )
            self.assertEqual(outputs["pointer"].read_bytes(), POINTER.read_bytes())
            replay = validate_local_upload_plan(outputs["plan"])
            self.assertEqual(replay["release_id"], self.validated["release_id"])

    def test_dry_run_rehashes_real_files_without_remote_mutation(self) -> None:
        evidence_dir = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
        with tempfile.TemporaryDirectory(
            prefix="origin-publish-test-", dir=evidence_dir
        ) as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            args = parse_publish_args(
                [
                    "--report-out",
                    report_path.relative_to(REPO_ROOT).as_posix(),
                    "--enforce",
                ]
            )
            report = run(args)
            self.assertEqual(report["status"], "ready_for_authorized_publication")
            self.assertIs(report["authorized"], False)
            self.assertIs(report["remote_preflight_performed"], False)
            self.assertIs(report["remote_publication_performed"], False)
            self.assertEqual(report["commits"], [])
            self.assertEqual(
                report["summary"]["immutable_files"],
                self.validated["total_files"],
            )
            persisted = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["release_id"], self.validated["release_id"])

    def test_remote_write_requires_both_explicit_flags(self) -> None:
        with self.assertRaisesRegex(OriginPublicationError, "--authorize-remote-write"):
            run(parse_publish_args(["--publish"]))
        with self.assertRaisesRegex(OriginPublicationError, "only valid together"):
            run(parse_publish_args(["--authorize-remote-write"]))

    def test_real_files_fit_bounded_upload_batches(self) -> None:
        grouped = list(
            batches(
                self.validated["immutable_files"],
                max_files=4,
                max_bytes=500 * 1024 * 1024,
            )
        )
        self.assertGreater(len(grouped), 1)
        self.assertEqual(
            sum(len(batch) for batch in grouped),
            self.validated["total_files"],
        )
        for batch in grouped:
            self.assertLessEqual(len(batch), 4)
            self.assertLessEqual(
                sum(int(item["bytes"]) for item in batch), 500 * 1024 * 1024
            )


if __name__ == "__main__":
    unittest.main()
