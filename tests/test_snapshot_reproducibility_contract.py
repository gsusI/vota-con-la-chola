from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_snapshot_reproducibility import (
    sha256_file,
    validate_reproducibility_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence"


def load(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE_ROOT / name).read_text(encoding="utf-8"))


class SnapshotReproducibilityContractTests(unittest.TestCase):
    def test_exact_real_published_release_evidence_passes(self) -> None:
        manifest_path = EVIDENCE_ROOT / "current-signed-scale-manifest-5d9ce557.json"
        report = validate_reproducibility_evidence(
            manifest=load(manifest_path.name),
            manifest_sha256=sha256_file(manifest_path),
            publish=load("signed-scale-publish-report.json"),
            live_signature=load("live-signed-snapshot-verification.json"),
            live_parity=load("live-scale-origin-parity.json"),
            diff=load("published-scale-manifest-diff.json"),
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["release"]["rows"], 5_414_326)
        self.assertEqual(report["release"]["corpora"], 7)
        self.assertFalse(report["checks"]["synthetic_or_mock_records"])
        self.assertTrue(
            report["checks"]["official_public_domain_personal_information_retained"]
        )

    def test_real_release_fails_when_public_identity_retention_is_removed(self) -> None:
        manifest_path = EVIDENCE_ROOT / "current-signed-scale-manifest-5d9ce557.json"
        manifest = load(manifest_path.name)
        manifest["policy"] = dict(manifest["policy"])
        manifest["policy"]["official_public_domain_personal_information_retained"] = (
            False
        )
        report = validate_reproducibility_evidence(
            manifest=manifest,
            manifest_sha256=sha256_file(manifest_path),
            publish=load("signed-scale-publish-report.json"),
            live_signature=load("live-signed-snapshot-verification.json"),
            live_parity=load("live-scale-origin-parity.json"),
            diff=load("published-scale-manifest-diff.json"),
        )
        self.assertFalse(report["passed"])
        self.assertIn(
            "mandatory policy is not true: official_public_domain_personal_information_retained",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
