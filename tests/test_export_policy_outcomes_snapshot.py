from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import export_policy_outcomes_snapshot as policy_outcomes


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-validation.json"
)
MATERIALIZATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-materialization.json"
)
SEMANTIC_SOURCE = (
    REPO_ROOT
    / "etl/data/staging/outcome-context-candidates-v1/versions/"
    "193c3c8b7e5f442d0373408a28acde31972e19807f21c31c59955e3d770d1abc/"
    "22f43918a8a6e54a3a8549f2f809abfcf98c3d04ef82dc37f634cd0fd71a980a/"
    "outcome-context-candidates-v1.json"
)
PAGE_SOURCE = REPO_ROOT / "ui/site/app/policy-outcomes/page.js"
PAGE_STYLES = REPO_ROOT / "ui/site/app/policy-outcomes/policy-outcomes.module.css"
CONTRACT_SOURCE = (
    REPO_ROOT / "ui/site/app/policy-outcomes/status-contract.mjs"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_values(value: object):
    yield value
    if isinstance(value, dict):
        for nested in value.values():
            yield from walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_values(nested)


class TestExportPolicyOutcomesSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))
        cls.semantic = json.loads(SEMANTIC_SOURCE.read_text(encoding="utf-8"))
        cls.plan = policy_outcomes.build_export_plan(VALIDATION_REPORT)

    def test_status_discloses_one_pending_pair_and_zero_validated_links(self) -> None:
        status = self.plan["status"]
        counts = self.report["counts"]
        reconstruction = self.report["source_reconstruction"]

        self.assertEqual(status["schema_version"], "policy_outcomes_public_status_v3")
        self.assertEqual(
            status["publication_state"],
            "one_pending_methodological_candidate_disclosed_zero_validated_outcome_links",
        )
        self.assertEqual(status["pipeline"]["pending_methodological_candidates_disclosed"], 1)
        self.assertEqual(status["pipeline"]["validated_outcome_links"], 0)
        self.assertEqual(status["pipeline"]["published_outcome_links"], 0)
        self.assertEqual(status["pipeline"]["human_reviews"], 0)
        self.assertEqual(
            status["selected_inputs"]["relationship_state"],
            "selected_together_in_one_pending_methodological_candidate",
        )
        self.assertEqual(
            status["selected_inputs"]["validation_state"],
            "not_a_validated_outcome_link",
        )
        self.assertEqual(status["bounded_universe"]["action_candidates"], reconstruction["action_candidate_rows"])
        self.assertEqual(
            status["bounded_universe"]["eligible_indicator_series"],
            reconstruction["eligible_indicator_series"],
        )
        self.assertEqual(status["bounded_universe"]["candidate_pairs"], counts["bounded_candidate_pairs"])
        self.assertEqual(
            status["bounded_universe"]["candidate_pairs"],
            status["bounded_universe"]["action_candidates"]
            * status["bounded_universe"]["eligible_indicator_series"],
        )
        self.assertFalse(status["bounded_universe"]["all_possible_action_indicator_pairs_searched"])
        self.assertEqual(
            status["claim_boundary"],
            {
                "statistical_association_claim": "none",
                "causal_claim": "none",
                "effect_estimate": "not_computed",
                "political_merit_or_blame": "not_assessed",
                "success_or_failure_assessment": "not_assessed",
                "corruption_assessment": "not_assessed",
            },
        )

    def test_validation_and_scope_facts_come_from_approved_evidence(self) -> None:
        status = self.plan["status"]
        validation = status["validation_identity"]
        reconstruction = self.report["source_reconstruction"]
        self.assertEqual(validation["check_count"], self.report["check_count"])
        self.assertEqual(validation["deterministic_fingerprint"], self.report["deterministic_fingerprint"])
        self.assertEqual(
            validation["report_sha256"],
            hashlib.sha256(self.plan["source"]["validation_evidence_raw"]).hexdigest(),
        )
        self.assertEqual(validation["artifact_set_sha256"], self.report["artifacts"]["artifact_set_sha256"])
        self.assertEqual(validation["bundle_semantic_sha256"], self.report["artifacts"]["bundle_semantic_sha256"])
        self.assertEqual(
            status["bounded_universe"]["action_universe_canonical_bytes"],
            reconstruction["action_universe_canonical_bytes"],
        )
        self.assertEqual(
            status["bounded_universe"]["action_universe_sha256"],
            reconstruction["action_universe_sha256"],
        )
        self.assertEqual(
            status["bounded_universe"]["eligible_indicator_series_sha256"],
            reconstruction["eligible_indicator_series_sha256"],
        )
        self.assertEqual(
            status["bounded_universe"]["combined_scope_sha256"],
            self.plan["source"]["scope"]["combined_scope_sha256"],
        )

    def test_status_has_no_arrays_internal_ids_or_individual_names(self) -> None:
        status = self.plan["status"]
        serialized = json.dumps(status, ensure_ascii=False, sort_keys=True)
        self.assertFalse(any(isinstance(value, list) for value in walk_values(status)))
        for forbidden in (
            "vclc:outcome-link:",
            "vclc:outcome-link-version:",
            "urn:vclc:actor:",
            "official_member_name",
            '"participants"',
            '"observations"',
            '"associations"',
        ):
            self.assertNotIn(forbidden, serialized)
        official_names = {
            row["official_member_name"] for row in self.semantic["participant_refs"]
        }
        self.assertEqual(len(official_names), self.report["truth"]["official_public_names_retained"])
        for name in official_names:
            self.assertNotIn(name, serialized)

    def test_export_writes_exact_content_addressed_real_evidence_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vclc-real-policy-evidence-") as directory:
            root = Path(directory)
            result = policy_outcomes.export_public_package(
                VALIDATION_REPORT,
                root / "data/policy-outcomes.json",
                root / "evidence",
            )
            manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
            self.assertEqual(result["package_dir"].name, manifest["package_id"])
            self.assertEqual(len(manifest["assets"]), 17)
            self.assertEqual(manifest["authentication"]["state"], "unsigned")
            self.assertFalse(
                manifest["signed_scale_origin_linkage"]["outcome_package_in_signed_scale_origin"]
            )
            self.assertTrue(
                manifest["signed_scale_origin_linkage"]["scale_origin_signature_verified"]
            )
            self.assertEqual(
                manifest["signed_scale_origin_linkage"]["scale_origin_signer_identity"],
                policy_outcomes.SCALE_ORIGIN_SIGNER_IDENTITY,
            )
            self.assertEqual(
                manifest["signed_scale_origin_linkage"]["scale_origin_public_key_fingerprint"],
                policy_outcomes.SCALE_ORIGIN_PUBLIC_KEY_FINGERPRINT,
            )
            self.assertIn("scale_origin_allowed_signers", manifest["assets"])
            for key, fact in manifest["assets"].items():
                asset_path = result["package_dir"] / fact["path"]
                with self.subTest(asset=key):
                    self.assertTrue(asset_path.is_file())
                    self.assertEqual(asset_path.stat().st_size, fact["bytes"])
                    self.assertEqual(file_sha256(asset_path), fact["sha256"])

            action_fact = manifest["assets"]["action_candidate_universe"]
            action_path = result["package_dir"] / action_fact["path"]
            action_rows = json.loads(action_path.read_text(encoding="utf-8"))
            self.assertEqual(len(action_rows), manifest["bounded_universe"]["action_candidates"])
            self.assertEqual(action_fact["bytes"], manifest["bounded_universe"]["action_universe_canonical_bytes"])
            self.assertEqual(action_fact["sha256"], manifest["bounded_universe"]["action_universe_sha256"])

            eligible_fact = manifest["assets"]["eligible_indicator_series_universe"]
            eligible_path = result["package_dir"] / eligible_fact["path"]
            eligible_rows = json.loads(eligible_path.read_text(encoding="utf-8"))
            self.assertEqual(len(eligible_rows), manifest["bounded_universe"]["eligible_indicator_series"])
            self.assertEqual(eligible_fact["sha256"], manifest["bounded_universe"]["eligible_indicator_series_sha256"])

    def test_exact_source_bytes_and_all_official_names_are_publicly_retained(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vclc-real-policy-identities-") as directory:
            root = Path(directory)
            result = policy_outcomes.export_public_package(
                VALIDATION_REPORT,
                root / "data/policy-outcomes.json",
                root / "evidence",
            )
            manifest = result["manifest"]
            package_dir = result["package_dir"]
            selected = result["status"]["selected_inputs"]

            vote_fact = manifest["assets"]["senate_vote_normalized_record"]
            initiative_fact = manifest["assets"]["senate_initiative_normalized_record"]
            eurostat_fact = manifest["assets"]["eurostat_raw_capture"]
            self.assertEqual(vote_fact["bytes"], selected["senate_vote"]["normalized_record_bytes"])
            self.assertEqual(vote_fact["sha256"], selected["senate_vote"]["normalized_record_sha256"])
            self.assertEqual(initiative_fact["bytes"], selected["senate_initiative"]["normalized_record_bytes"])
            self.assertEqual(initiative_fact["sha256"], selected["senate_initiative"]["normalized_record_sha256"])
            self.assertEqual(eurostat_fact["bytes"], selected["eurostat_indicator"]["source_bytes"])
            self.assertEqual(eurostat_fact["sha256"], selected["eurostat_indicator"]["source_sha256"])

            semantic_fact = manifest["assets"]["semantic_evidence"]
            public_semantic_path = package_dir / semantic_fact["path"]
            self.assertEqual(public_semantic_path.read_bytes(), SEMANTIC_SOURCE.read_bytes())
            public_semantic = json.loads(public_semantic_path.read_text(encoding="utf-8"))
            source_names = [row["official_member_name"] for row in self.semantic["participant_refs"]]
            public_names = [row["official_member_name"] for row in public_semantic["participant_refs"]]
            self.assertEqual(public_names, source_names)
            self.assertEqual(len(set(public_names)), manifest["identity_retention"]["official_public_names_retained"])
            self.assertEqual(manifest["identity_retention"]["official_public_names_removed_or_pseudonymized"], 0)

    def test_export_is_byte_reproducible_and_manifest_is_last_commit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vclc-real-policy-repro-") as directory:
            root = Path(directory)
            results = []
            for lane in ("first", "second"):
                lane_root = root / lane
                results.append(
                    policy_outcomes.export_public_package(
                        VALIDATION_REPORT,
                        lane_root / "data/policy-outcomes.json",
                        lane_root / "evidence",
                    )
                )
            self.assertEqual(results[0]["status_raw"], results[1]["status_raw"])
            self.assertEqual(results[0]["manifest_raw"], results[1]["manifest_raw"])
            self.assertEqual(results[0]["package_id"], results[1]["package_id"])
            for key in results[0]["assets"]:
                first = results[0]["package_dir"] / results[0]["assets"][key]["path"]
                second = results[1]["package_dir"] / results[1]["assets"][key]["path"]
                self.assertEqual(first.read_bytes(), second.read_bytes())

            exporter_source = Path(policy_outcomes.__file__).read_text(encoding="utf-8")
            self.assertLess(
                exporter_source.index("_atomic_write_bytes(out, plan[\"status_raw\"])") ,
                exporter_source.index("_commit_immutable_bytes(package_dir / \"manifest.json\"") ,
            )

    def test_public_validation_evidence_excludes_physical_database_churn(self) -> None:
        fact = self.plan["assets"]["independent_validation_evidence_projection"]
        spec = self.plan["specs"]["independent_validation_evidence_projection"]
        evidence = json.loads(spec["data"].decode("utf-8"))
        serialized = spec["data"].decode("utf-8")
        self.assertEqual(
            evidence["schema_version"],
            "outcome_context_validation_public_evidence_v1",
        )
        self.assertEqual(
            hashlib.sha256(spec["data"]).hexdigest(),
            policy_outcomes.APPROVED_VALIDATION_EVIDENCE_SHA256,
        )
        self.assertFalse(evidence["telemetry_policy"]["raw_validation_report_is_public_asset"])
        self.assertNotIn("physical_database_facts_report_only", serialized)
        self.assertNotIn("stat_identity_sha256", serialized)
        self.assertEqual(fact["bytes"], len(spec["data"]))
        self.assertEqual(fact["sha256"], hashlib.sha256(spec["data"]).hexdigest())

        drifted = json.loads(json.dumps(self.report))
        drifted["inputs"]["physical_database_facts_report_only"]["indicators"][
            "sha256"
        ] = "f" * 64
        drifted_raw = policy_outcomes._build_public_validation_evidence(
            validation_report=drifted,
            artifacts=drifted["artifacts"],
            scope=self.plan["source"]["scope"],
        )
        self.assertEqual(drifted_raw, spec["data"])

    def test_public_materialization_evidence_excludes_volatile_telemetry(self) -> None:
        fact = self.plan["assets"]["materialization_evidence_projection"]
        spec = self.plan["specs"]["materialization_evidence_projection"]
        evidence = json.loads(spec["data"].decode("utf-8"))
        serialized = spec["data"].decode("utf-8")
        self.assertEqual(
            evidence["schema_version"],
            "outcome_context_materialization_public_evidence_v1",
        )
        self.assertEqual(
            evidence["validation_binding"]["validation_evidence_projection_sha256"],
            policy_outcomes.APPROVED_VALIDATION_EVIDENCE_SHA256,
        )
        self.assertFalse(
            evidence["telemetry_policy"]["raw_materialization_report_is_public_asset"]
        )
        self.assertNotIn("pre_pointer_wall_time_seconds", serialized)
        self.assertNotIn("peak_rss_mb", serialized)
        self.assertNotIn("stat_identity_sha256", serialized)
        self.assertEqual(fact["bytes"], len(spec["data"]))
        self.assertEqual(fact["sha256"], hashlib.sha256(spec["data"]).hexdigest())

    def test_volatile_raw_materialization_metrics_do_not_change_public_identity(self) -> None:
        materialization = json.loads(MATERIALIZATION_REPORT.read_text(encoding="utf-8"))
        materialization["execution"]["pre_pointer_wall_time_seconds"] = 999999.123456
        materialization["execution"]["peak_rss_mb"] = 999999.0
        original_loader = policy_outcomes.strict_json_file

        def load_with_volatile_metrics(path: Path):
            if Path(path).resolve() == MATERIALIZATION_REPORT.resolve():
                return materialization
            return original_loader(path)

        with mock.patch.object(
            policy_outcomes,
            "strict_json_file",
            side_effect=load_with_volatile_metrics,
        ):
            rebuilt = policy_outcomes.build_export_plan(VALIDATION_REPORT)
        self.assertEqual(rebuilt["package_id"], self.plan["package_id"])
        self.assertEqual(rebuilt["status_raw"], self.plan["status_raw"])
        self.assertEqual(rebuilt["manifest_raw"], self.plan["manifest_raw"])

    def test_nonvalidator_artifact_is_rejected(self) -> None:
        self.assertTrue(MATERIALIZATION_REPORT.is_file())
        with self.assertRaises(policy_outcomes.PolicyOutcomesExportError):
            policy_outcomes.build_public_status(MATERIALIZATION_REPORT)

    def test_tampered_scale_origin_signature_is_rejected_cryptographically(self) -> None:
        original = policy_outcomes.DEFAULT_SCALE_ATTESTATION_SIGNATURE.read_bytes()
        with tempfile.TemporaryDirectory(prefix="vclc-scale-signature-tamper-") as directory:
            tampered = Path(directory) / "attestation.json.sig"
            tampered.write_bytes(original.replace(b"Gjqcf7", b"Hjqcf7", 1))
            with mock.patch.object(
                policy_outcomes,
                "DEFAULT_SCALE_ATTESTATION_SIGNATURE",
                tampered,
            ):
                with self.assertRaisesRegex(
                    policy_outcomes.PolicyOutcomesExportError,
                    "cryptographic verification failed",
                ):
                    policy_outcomes._validate_signed_scale_origin()

    def test_tampered_scale_origin_trust_root_is_rejected_before_verification(self) -> None:
        original = policy_outcomes.DEFAULT_SCALE_ALLOWED_SIGNERS.read_bytes()
        with tempfile.TemporaryDirectory(prefix="vclc-scale-trust-root-tamper-") as directory:
            tampered = Path(directory) / "allowed_signers"
            tampered.write_bytes(original + b"\n")
            with mock.patch.object(
                policy_outcomes,
                "DEFAULT_SCALE_ALLOWED_SIGNERS",
                tampered,
            ):
                with self.assertRaisesRegex(
                    policy_outcomes.PolicyOutcomesExportError,
                    "trust root drift",
                ):
                    policy_outcomes._validate_signed_scale_origin()

    def test_page_uses_central_runtime_contract_and_semantic_markup(self) -> None:
        page = PAGE_SOURCE.read_text(encoding="utf-8")
        styles = PAGE_STYLES.read_text(encoding="utf-8")
        contract = CONTRACT_SOURCE.read_text(encoding="utf-8")
        for required in (
            "validatePolicyOutcomesPackage",
            "policy-outcomes-status-page",
            "policy-outcomes-pending-candidate",
            "policy-outcomes-bounded-universe",
            "policy-outcomes-public-evidence",
            "Un candidato metodológico pendiente",
            "0 vínculos de resultado validados",
            "seleccionadas juntas",
            "Descargar universo exacto de 20 acciones",
            "Descargar evidencia semántica con nombres oficiales",
            "Descargar trust root público Ed25519",
            "Descargar attestation del origen de escala",
            "Descargar firma del origen de escala",
        ):
            self.assertIn(required, page)
        for required in (
            "CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256",
            "manifest:release_identity",
            "cross.action_universe_asset",
            "cross.eligible_series_universe_asset",
            "array_forbidden",
            "internal_detail_value_forbidden",
        ):
            self.assertIn(required, contract)
        self.assertIn("transition:", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)


if __name__ == "__main__":
    unittest.main()
