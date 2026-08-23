from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_real_data_only import PROHIBITED_MARKERS
from scripts.validate_real_public_json import validate_paths


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BUILD_INPUTS = (
    ROOT / "etl/data/published/accountability-dossiers-latest.json",
    ROOT / "etl/data/published/accountability-ledger-latest.json",
    ROOT / "etl/data/published/accountability-evidence-api-latest.json",
    ROOT / "ui/gh-pages-next/public/parliamentary-accountability/data/accountability.json",
    ROOT / "ui/gh-pages-next/public/initiative-lifecycle/data/lifecycle.json",
    ROOT / "ui/gh-pages-next/public/people/data/xray.json",
    ROOT / "ui/gh-pages-next/public/legal-sanctions/data/legal-sanctions.json",
    ROOT / "ui/gh-pages-next/public/policy-outcomes/data/policy-outcomes.json",
    ROOT / "ui/gh-pages-next/public/responsibility-explainer/data",
)


class RealPublicBuildGateTests(unittest.TestCase):
    def test_committed_public_build_inputs_are_real_json(self) -> None:
        report = validate_paths(list(PUBLIC_BUILD_INPUTS))
        self.assertTrue(report["passed"], report["errors"])
        self.assertGreaterEqual(report["artifacts_total"], 11)

    def test_missing_required_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = validate_paths([Path(temporary_directory) / "absent.json"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["artifacts_total"], 0)
        self.assertEqual(len(report["errors"]), 1)

    def test_accountability_bundle_infers_and_enforces_snapshot_parity(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/validate_accountability_artifacts.py",
                "--ledger",
                "etl/data/published/accountability-ledger-latest.json",
                "--dossiers",
                "etl/data/published/accountability-dossiers-latest.json",
                "--evidence-api",
                "etl/data/published/accountability-evidence-api-latest.json",
                "--infer-snapshot-date",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        ledger = json.loads(
            (ROOT / "etl/data/published/accountability-ledger-latest.json").read_text(
                encoding="utf-8"
            )
        )
        expected_snapshot_date = ledger["meta"]["snapshot_date"]
        self.assertIn(
            f'"expected_snapshot_date":"{expected_snapshot_date}"',
            completed.stdout,
        )

    def test_public_build_recipes_cannot_emit_development_stubs(self) -> None:
        justfile = (ROOT / "justfile").read_text(encoding="utf-8")
        self.assertNotIn("dev-local-stub", justfile)
        self.assertGreaterEqual(justfile.count("validate_real_public_json.py"), 4)
        self.assertIn(b"dev-local-stub", PROHIBITED_MARKERS)


if __name__ == "__main__":
    unittest.main()
