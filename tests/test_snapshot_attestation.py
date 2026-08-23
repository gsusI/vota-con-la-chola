from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.snapshot_attestation import (
    SnapshotAttestationError,
    build_snapshot_attestation,
    create_signed_attestation,
    derive_public_key,
    diff_scale_manifests,
    sha256_file,
    verify_signed_attestation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_REMOTE_MANIFEST = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/remote-scale-manifest-5872efaf.json"
)
REAL_LOCAL_MANIFEST = (
    REPO_ROOT
    / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/local-scale-manifest-f062ad4d.json"
)
MANIFEST_URL = (
    "https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/"
    "scale/snapshots/2026-08-12/"
    "5872efaf918430c0c9e2b3b5b01fd9efe4ba03ff586da75419e28dfdb0b2e139/"
    "manifest.json"
)
SNAPSHOT_PATH = (
    "scale/snapshots/2026-08-12/"
    "5872efaf918430c0c9e2b3b5b01fd9efe4ba03ff586da75419e28dfdb0b2e139"
)
SIGNER_IDENTITY = "vclc-snapshot-release-test"


def generate_ephemeral_signing_key(directory: Path, name: str = "release-key") -> Path:
    private_key = directory / name
    completed = subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "vclc real snapshot contract test",
            "-f",
            str(private_key),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return private_key


class SnapshotAttestationTests(unittest.TestCase):
    def test_signs_and_verifies_the_real_published_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = generate_ephemeral_signing_key(root)
            result = create_signed_attestation(
                manifest_path=REAL_REMOTE_MANIFEST,
                manifest_url=MANIFEST_URL,
                snapshot_path=SNAPSHOT_PATH,
                private_key_path=private_key,
                signer_identity=SIGNER_IDENTITY,
                issued_at="2026-08-19T18:00:00+00:00",
                out_dir=root / "attestation",
            )
            verification = verify_signed_attestation(
                manifest_path=REAL_REMOTE_MANIFEST,
                attestation_path=root / "attestation/attestation.json",
                signature_path=root / "attestation/attestation.json.sig",
                allowed_signers_path=root / "attestation/allowed_signers",
                signer_identity=SIGNER_IDENTITY,
            )

        self.assertEqual(result["status"], "signed_and_verified")
        self.assertEqual(
            result["manifest_sha256"],
            "5872efaf918430c0c9e2b3b5b01fd9efe4ba03ff586da75419e28dfdb0b2e139",
        )
        self.assertTrue(verification["passed"])
        self.assertTrue(verification["checks"]["signature_verified"])
        self.assertTrue(
            verification["checks"][
                "official_public_domain_personal_information_retained"
            ]
        )

    def test_signature_does_not_validate_a_different_real_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = generate_ephemeral_signing_key(root)
            create_signed_attestation(
                manifest_path=REAL_REMOTE_MANIFEST,
                manifest_url=MANIFEST_URL,
                snapshot_path=SNAPSHOT_PATH,
                private_key_path=private_key,
                signer_identity=SIGNER_IDENTITY,
                issued_at="2026-08-19T18:00:00+00:00",
                out_dir=root / "attestation",
            )
            verification = verify_signed_attestation(
                manifest_path=REAL_LOCAL_MANIFEST,
                attestation_path=root / "attestation/attestation.json",
                signature_path=root / "attestation/attestation.json.sig",
                allowed_signers_path=root / "attestation/allowed_signers",
                signer_identity=SIGNER_IDENTITY,
            )

        self.assertFalse(verification["passed"])
        self.assertIn(
            "attested manifest checksum does not match downloaded manifest",
            verification["errors"],
        )

    def test_untrusted_real_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trusted_key = generate_ephemeral_signing_key(root, "trusted-key")
            untrusted_key = generate_ephemeral_signing_key(root, "untrusted-key")
            create_signed_attestation(
                manifest_path=REAL_REMOTE_MANIFEST,
                manifest_url=MANIFEST_URL,
                snapshot_path=SNAPSHOT_PATH,
                private_key_path=trusted_key,
                signer_identity=SIGNER_IDENTITY,
                issued_at="2026-08-19T18:00:00+00:00",
                out_dir=root / "attestation",
            )
            public_key = derive_public_key(untrusted_key).split()
            wrong_allowed_signers = root / "wrong-allowed-signers"
            wrong_allowed_signers.write_text(
                f'{SIGNER_IDENTITY} namespaces="vota-con-la-chola-snapshot-v1" '
                f"{public_key[0]} {public_key[1]}\n",
                encoding="utf-8",
            )
            verification = verify_signed_attestation(
                manifest_path=REAL_REMOTE_MANIFEST,
                attestation_path=root / "attestation/attestation.json",
                signature_path=root / "attestation/attestation.json.sig",
                allowed_signers_path=wrong_allowed_signers,
                signer_identity=SIGNER_IDENTITY,
            )

        self.assertFalse(verification["passed"])
        self.assertFalse(verification["checks"]["signature_verified"])

    def test_attestation_payload_is_deterministic_for_real_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            private_key = generate_ephemeral_signing_key(Path(tmp))
            manifest = json.loads(REAL_REMOTE_MANIFEST.read_text(encoding="utf-8"))
            public_key = derive_public_key(private_key)
            kwargs = {
                "manifest": manifest,
                "manifest_sha256": sha256_file(REAL_REMOTE_MANIFEST),
                "manifest_url": MANIFEST_URL,
                "snapshot_path": SNAPSHOT_PATH,
                "signer_identity": SIGNER_IDENTITY,
                "public_key": public_key,
                "issued_at": "2026-08-19T18:00:00+00:00",
            }
            first = build_snapshot_attestation(**kwargs)
            second = build_snapshot_attestation(**kwargs)

        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["rows"], 5_403_506)
        self.assertEqual(first["summary"]["data_files"], 8_595)

    def test_rejects_manifest_when_real_data_policy_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            private_key = generate_ephemeral_signing_key(Path(tmp))
            manifest = json.loads(REAL_REMOTE_MANIFEST.read_text(encoding="utf-8"))
            manifest["policy"]["official_real_records_only"] = False
            with self.assertRaises(SnapshotAttestationError):
                build_snapshot_attestation(
                    manifest=manifest,
                    manifest_sha256=sha256_file(REAL_REMOTE_MANIFEST),
                    manifest_url=MANIFEST_URL,
                    snapshot_path=SNAPSHOT_PATH,
                    signer_identity=SIGNER_IDENTITY,
                    public_key=derive_public_key(private_key),
                    issued_at="2026-08-19T18:00:00+00:00",
                )

    def test_exact_diff_uses_two_real_scale_manifests(self) -> None:
        report = diff_scale_manifests(
            before_path=REAL_REMOTE_MANIFEST,
            after_path=REAL_LOCAL_MANIFEST,
        )

        self.assertTrue(report["artifact_contract_changed"])
        self.assertEqual(report["files"]["before_total"], 8_619)
        self.assertEqual(report["files"]["after_total"], 8_625)
        self.assertEqual(report["files"]["unchanged"], 8_617)
        self.assertEqual(report["files"]["added"], 6)
        self.assertEqual(report["files"]["changed"], 2)
        self.assertEqual(report["files"]["removed"], 0)
        self.assertEqual(report["corpora"]["added"], ["candidate_occurrences"])
        self.assertTrue(
            report["policy"]["official_public_domain_personal_information_retained"]
        )

    def test_copied_real_manifest_retains_exact_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "manifest.json"
            shutil.copy2(REAL_REMOTE_MANIFEST, copied)
            self.assertEqual(sha256_file(copied), sha256_file(REAL_REMOTE_MANIFEST))


if __name__ == "__main__":
    unittest.main()
