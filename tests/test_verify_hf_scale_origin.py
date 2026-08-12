from __future__ import annotations

import unittest

from scripts.publicar_hf_scale_snapshot import (
    ARTIFACT_CONTRACT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    artifact_contract_sha256,
)
from scripts.verify_hf_scale_origin import evaluate_origin_parity


class VerifyHFScaleOriginTests(unittest.TestCase):
    def _payloads(self):
        readiness = {
            "registry": {"sha256": "r" * 64},
            "corpora": [
                {
                    "id": "money",
                    "rows": 1_000_000,
                    "files": 10,
                    "bytes": 1234,
                    "promotion_gate_passed": False,
                }
            ],
        }
        latest = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_date": "2026-08-12",
            "manifest_sha256": "a" * 64,
            "release_id": "a" * 64,
            "snapshot_path": f"scale/snapshots/2026-08-12/{'a' * 64}",
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_date": "2026-08-12",
            "status": "validated_real_origin_bundle",
            "policy": {
                "official_real_records_only": True,
                "synthetic_or_mock_records_forbidden": True,
                "official_public_domain_personal_information_retained": True,
                "secrets_workstation_traces_and_non_public_data_forbidden": True,
            },
            "source_evidence": {
                "readiness": {"sha256": "l" * 64},
                "registry": {"sha256": "r" * 64},
            },
            "corpora": [
                {
                    "id": "money",
                    "kind": "parquet_manifest",
                    "rows": 1_000_000,
                    "files": 10,
                    "bytes": 1234,
                    "promotion_gate_passed": False,
                    "source_ids": ["official_money"],
                    "official_hosts": ["official.example"],
                    "source_url_rows": 1_000_000,
                    "source_url_https_rows": 1_000_000,
                    "manifest": {"sha256": "m" * 64},
                    "validation": {"sha256": "v" * 64},
                    "extra_evidence": {},
                }
            ],
            "files": [
                {
                    "kind": "data",
                    "corpus_id": "money",
                    "path": f"corpora/money/data/part-{index}.parquet",
                    "bytes": 100 + index,
                    "sha256": f"{index:x}" * 64,
                }
                for index in range(10)
            ],
        }
        contract_sha256 = artifact_contract_sha256(manifest)
        manifest["artifact_contract"] = {
            "schema_version": ARTIFACT_CONTRACT_SCHEMA_VERSION,
            "sha256": contract_sha256,
        }
        latest["artifact_contract_sha256"] = contract_sha256
        return readiness, latest, manifest

    def test_matching_remote_origin_passes(self) -> None:
        readiness, latest, manifest = self._payloads()
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertEqual(errors, [])
        self.assertTrue(checks["required_policy_passed"])
        self.assertTrue(checks["corpus_contracts_match"])

    def test_stale_remote_readiness_is_metadata_warning(self) -> None:
        readiness, latest, manifest = self._payloads()
        manifest["source_evidence"]["readiness"]["sha256"] = "x" * 64
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertEqual(errors, [])
        self.assertFalse(checks["metadata_freshness"])
        self.assertIn(
            "remote scale origin does not contain the current readiness report",
            checks["metadata_warnings"],
        )

    def test_promotion_state_drift_does_not_break_data_parity(self) -> None:
        readiness, latest, manifest = self._payloads()
        manifest["corpora"][0]["promotion_gate_passed"] = True
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertEqual(errors, [])
        self.assertFalse(checks["promotion_states_match"])
        self.assertIn(
            "remote scale origin contains older promotion-state metadata",
            checks["metadata_warnings"],
        )

    def test_old_release_schema_fails(self) -> None:
        readiness, latest, manifest = self._payloads()
        latest["schema_version"] = "real-scale-origin-bundle-v1"
        manifest["schema_version"] = "real-scale-origin-bundle-v1"
        _checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertIn(
            "remote scale latest pointer has unsupported schema version", errors
        )
        self.assertIn("remote scale manifest has unsupported schema version", errors)

    def test_mutable_date_only_snapshot_path_fails(self) -> None:
        readiness, latest, manifest = self._payloads()
        latest["snapshot_path"] = "scale/snapshots/2026-08-12"
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertFalse(checks["immutable_snapshot_path"])
        self.assertIn("remote scale snapshot path is not content-addressed", errors)

    def test_missing_public_identity_retention_policy_fails(self) -> None:
        readiness, latest, manifest = self._payloads()
        manifest["policy"]["official_public_domain_personal_information_retained"] = (
            False
        )
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256=manifest["artifact_contract"]["sha256"],
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertFalse(checks["required_policy_passed"])
        self.assertTrue(
            any("mandatory real/public-data policy" in item for item in errors)
        )

    def test_remote_artifact_contract_drift_fails(self) -> None:
        readiness, latest, manifest = self._payloads()
        checks, errors = evaluate_origin_parity(
            local_readiness=readiness,
            local_readiness_sha256="l" * 64,
            local_artifact_contract_sha256="b" * 64,
            remote_latest=latest,
            remote_manifest=manifest,
            remote_manifest_sha256="a" * 64,
        )
        self.assertNotEqual(
            checks["artifact_contract"]["local_sha256"],
            checks["artifact_contract"]["declared_sha256"],
        )
        self.assertIn(
            "remote scale artifact contract differs from local artifacts", errors
        )


if __name__ == "__main__":
    unittest.main()
