from __future__ import annotations

import unittest

from scripts.verify_hf_snapshot_quality import evaluate_contract, resolve_dataset_repo


class VerifyHFSnapshotQualityTests(unittest.TestCase):
    def test_resolve_dataset_repo_with_owner(self) -> None:
        self.assertEqual(resolve_dataset_repo("org/data", "ignored"), "org/data")

    def test_resolve_dataset_repo_without_owner_uses_username(self) -> None:
        self.assertEqual(resolve_dataset_repo("data", "jesus"), "jesus/data")

    def test_evaluate_contract_passes_when_payloads_are_consistent(self) -> None:
        latest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
                "initiative_gate_passed": True,
            },
        }
        manifest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
                "initiative_gate_passed": True,
            },
        }
        readme = (
            "...\n"
            "published/votaciones-kpis-es-2026-02-12.json\n"
            "Resumen de calidad del snapshot:\n"
            "- Vote gate: PASS\n"
        )
        checks, errors = evaluate_contract(
            latest_payload=latest,
            manifest_payload=manifest,
            readme_text=readme,
            expected_snapshot_date="2026-02-12",
            require_readme=True,
        )
        self.assertEqual(errors, [])
        self.assertTrue(checks["latest_has_quality_report"])
        self.assertTrue(checks["manifest_has_quality_report"])
        self.assertEqual(checks["quality_file_name"], "votaciones-kpis-es-2026-02-12.json")

    def test_evaluate_contract_fails_when_quality_missing(self) -> None:
        checks, errors = evaluate_contract(
            latest_payload={"snapshot_date": "2026-02-12"},
            manifest_payload={"snapshot_date": "2026-02-12"},
            readme_text="",
            expected_snapshot_date="2026-02-12",
            require_readme=False,
        )
        self.assertFalse(checks["latest_has_quality_report"])
        self.assertFalse(checks["manifest_has_quality_report"])
        self.assertIn("latest.json no incluye quality_report", errors)
        self.assertIn("manifest.json no incluye quality_report", errors)

    def test_evaluate_contract_fails_on_quality_mismatch(self) -> None:
        latest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
            },
        }
        manifest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": False,
            },
        }
        _checks, errors = evaluate_contract(
            latest_payload=latest,
            manifest_payload=manifest,
            readme_text="",
            expected_snapshot_date="2026-02-12",
            require_readme=False,
        )
        self.assertTrue(any("quality_report mismatch latest vs manifest" in msg for msg in errors))

    def test_evaluate_contract_fails_readme_checks(self) -> None:
        latest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
            },
        }
        manifest = {
            "snapshot_date": "2026-02-12",
            "quality_report": {
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
            },
        }
        _checks, errors = evaluate_contract(
            latest_payload=latest,
            manifest_payload=manifest,
            readme_text="README sin sección",
            expected_snapshot_date="2026-02-12",
            require_readme=True,
        )
        self.assertTrue(any("Resumen de calidad del snapshot" in msg for msg in errors))
        self.assertTrue(any("Vote gate:" in msg for msg in errors))


if __name__ == "__main__":
    unittest.main()
