from __future__ import annotations

import json
import tempfile
import unittest

from scripts.report_scale_readiness import (
    REPO_ROOT,
    ReadinessError,
    audit_gap,
    build_failure_report,
    checks_pass,
    load_json,
    main,
    official_host,
    reject_disallowed_evidence,
    repo_path,
    validate_member_vote_shard,
)


class RealScaleReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry_path = REPO_ROOT / "docs/etl/real-corpus-registry.json"
        self.registry = load_json(self.registry_path)

    def test_registry_contains_only_real_artifact_contracts(self) -> None:
        reject_disallowed_evidence(self.registry, "registry")
        self.assertTrue(self.registry["policy"]["official_real_records_only"])
        self.assertTrue(self.registry["policy"]["synthetic_or_mock_records_forbidden"])
        self.assertTrue(
            self.registry["policy"][
                "official_public_domain_personal_information_retained"
            ]
        )
        self.assertTrue(
            self.registry["policy"][
                "classification_never_suppresses_public_domain_identity"
            ]
        )
        self.assertGreaterEqual(len(self.registry["corpora"]), 4)
        for corpus in self.registry["corpora"]:
            self.assertTrue(repo_path(corpus["root"]).is_dir())
            self.assertTrue(repo_path(corpus["manifest"]).is_file())
            self.assertTrue(repo_path(corpus["validation"]).is_file())

    def test_official_host_requires_http_origin_and_allowlist(self) -> None:
        self.assertEqual(
            official_host("https://www.congreso.es/datos", {"www.congreso.es"}),
            "www.congreso.es",
        )
        self.assertEqual(
            official_host("http://www.congreso.es/datos", {"www.congreso.es"}),
            "www.congreso.es",
        )
        with self.assertRaisesRegex(RuntimeError, "official HTTP"):
            official_host("ftp://www.congreso.es/datos", {"www.congreso.es"})
        with self.assertRaisesRegex(RuntimeError, "allowlist"):
            official_host("https://www.senado.es/datos", {"www.congreso.es"})

    def test_validation_contract_requires_all_checks_and_ok_status(self) -> None:
        self.assertTrue(
            checks_pass({"status": "ok", "checks": {"hash": True}}, require_status=True)
        )
        self.assertFalse(
            checks_pass(
                {"status": "failed", "checks": {"hash": True}}, require_status=True
            )
        )
        self.assertFalse(
            checks_pass(
                {"status": "ok", "checks": {"hash": False}}, require_status=True
            )
        )

    def test_one_captured_official_vote_shard_matches_manifest(self) -> None:
        corpus = next(
            item for item in self.registry["corpora"] if item["id"] == "member_votes"
        )
        manifest = json.loads(repo_path(corpus["manifest"]).read_text(encoding="utf-8"))
        entry = next(item for item in manifest["entries"] if item["member_votes"] > 0)
        observed_rows, observed_source_urls, observed_https_urls, source_ids, hosts = (
            validate_member_vote_shard(
                repo_path(corpus["root"]) / entry["shard"],
                entry,
                allowed_source_ids=set(corpus["official_source_ids"]),
                allowed_hosts=set(corpus["official_hosts"]),
            )
        )
        self.assertEqual(observed_rows, entry["member_votes"])
        self.assertGreater(observed_source_urls, 0)
        self.assertGreater(observed_https_urls, 0)
        self.assertTrue(source_ids)
        self.assertTrue(hosts)

    def test_registry_paths_are_portable(self) -> None:
        raw = self.registry_path.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", raw)
        self.assertNotIn("/home/", raw)
        self.assertNotIn("file://", raw)

    def test_official_sample_audit_is_readiness_evidence(self) -> None:
        evidence = self.registry["supporting_evidence"]
        report = load_json(repo_path(evidence["official_sample_corpus_audit"]))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["configured_sources"], 25)
        self.assertEqual(report["synthetic_or_mock_records"], 0)
        self.assertTrue(report["public_domain_personal_information_retained"])

    def test_public_source_records_retain_official_personal_information(self) -> None:
        evidence = self.registry["supporting_evidence"]
        report = load_json(repo_path(evidence["public_source_records_publish_audit"]))
        self.assertEqual(report["status"], "pass")
        self.assertGreater(report["rows"], 100_000)
        self.assertTrue(report["raw_payload_published_exactly"])
        self.assertTrue(report["public_domain_personal_information_retained"])
        self.assertEqual(report["identity_fields_removed"], 0)

    def test_document_gap_fails_closed_on_current_boe_tail(self) -> None:
        gap = next(
            item for item in self.registry["gaps"] if item["id"] == "document_corpus"
        )
        self.assertEqual(gap["current_real_rows"], 122_607)
        with self.assertRaisesRegex(ReadinessError, "BOE document corpus checks failed"):
            audit_gap(gap)

    def test_boe_candidate_gap_retains_exact_public_identity_and_corrections(
        self,
    ) -> None:
        gap = next(
            item
            for item in self.registry["gaps"]
            if item["id"] == "candidate_occurrences"
        )
        audited = audit_gap(gap)
        metrics = audited["metrics"]
        self.assertEqual(metrics["base_candidates"], 42_056)
        self.assertEqual(metrics["captured_base_candidates"], 42_056)
        self.assertEqual(metrics["reviewed_base_candidates"], 10_815)
        self.assertEqual(metrics["pending_base_candidates"], 31_241)
        self.assertEqual(metrics["candidates"], 10_820)
        self.assertEqual(metrics["effective_candidates"], 10_820)
        self.assertEqual(metrics["official_public_identity_rows_retained"], 42_056)
        self.assertEqual(metrics["effective_public_identity_rows_retained"], 10_820)
        self.assertEqual(metrics["identity_fields_removed"], 0)
        self.assertEqual(metrics["documents"], 7)
        self.assertEqual(metrics["candidacies"], 4_901)
        self.assertEqual(metrics["reviewed_base_candidacies"], 1_188)
        self.assertEqual(metrics["pending_base_candidacies"], 3_713)
        self.assertEqual(metrics["correction_documents"], 11)
        self.assertEqual(metrics["correction_targets"], 12)
        self.assertEqual(metrics["correction_paragraphs"], 956)
        self.assertEqual(metrics["correction_operations"], 17)
        self.assertEqual(metrics["reviewed_correction_paragraphs"], 180)
        self.assertEqual(metrics["pending_correction_paragraphs"], 776)
        self.assertEqual(metrics["correction_paragraphs_referenced_by_operations"], 127)
        self.assertEqual(metrics["contextual_correction_paragraphs_retained"], 53)
        self.assertEqual(metrics["applied_correction_documents"], 3)
        self.assertEqual(metrics["captured_unapplied_correction_documents"], 8)
        self.assertEqual(metrics["correction_review_tasks"], 776)
        self.assertEqual(metrics["correction_review_context_candidacies"], 3_713)
        self.assertEqual(metrics["correction_review_context_candidates"], 31_241)
        self.assertEqual(metrics["correction_review_pending_dual_review"], 776)
        self.assertEqual(metrics["pending_effective_candidacies"], 0)
        self.assertEqual(metrics["pending_effective_candidates"], 0)
        self.assertEqual(metrics["foreign_key_violations"], 0)
        self.assertEqual(metrics["semantic_rows"], 10_820)
        self.assertEqual(metrics["semantic_files"], 2)
        self.assertEqual(metrics["semantic_exact_public_name_rows"], 10_820)
        self.assertEqual(metrics["semantic_exact_source_text_rows"], 10_820)
        self.assertEqual(metrics["semantic_correction_backed_rows"], 88)
        self.assertEqual(metrics["semantic_outcome_known_rows"], 0)
        self.assertTrue(metrics["semantic_unchanged_replay"]["passed"])
        self.assertEqual(metrics["semantic_unchanged_replay"]["partitions_reused"], 2)
        self.assertEqual(metrics["semantic_unchanged_replay"]["files_hardlinked"], 2)

    def test_candidate_corpus_is_real_validated_and_not_overpromoted(self) -> None:
        corpus = next(
            item
            for item in self.registry["corpora"]
            if item["id"] == "candidate_occurrences"
        )
        self.assertEqual(corpus["official_source_ids"], ["boe_election_candidates"])
        self.assertEqual(corpus["official_hosts"], ["www.boe.es"])
        self.assertEqual(corpus["minimum_real_rows"], 10_000)
        self.assertFalse(corpus["representative_scope"])
        self.assertTrue(corpus["durable_public_origin"])
        self.assertFalse(corpus["clean_room_restore"])
        self.assertTrue(corpus["corrections_workflow"])

    def test_boe_candidate_gap_rejects_stale_registry_count(self) -> None:
        gap = dict(
            next(
                item
                for item in self.registry["gaps"]
                if item["id"] == "candidate_occurrences"
            )
        )
        gap["current_real_rows"] += 1
        with self.assertRaisesRegex(ReadinessError, "registry count drifted"):
            audit_gap(gap)

    def test_document_gap_rejects_stale_registry_count(self) -> None:
        gap = dict(
            next(
                item
                for item in self.registry["gaps"]
                if item["id"] == "document_corpus"
            )
        )
        gap["current_real_rows"] += 1
        with self.assertRaisesRegex(ReadinessError, "file totals drifted"):
            audit_gap(gap)

    def test_failure_report_retains_policy_and_never_claims_readiness(self) -> None:
        report = build_failure_report(
            self.registry_path,
            ReadinessError("BOE document corpus checks failed"),
        )
        self.assertEqual(report["status"], "not_ready")
        self.assertIs(report["foundation"]["ready"], False)
        self.assertEqual(
            report["failure"]["reason"], "BOE document corpus checks failed"
        )
        self.assertTrue(report["registry"]["available"])
        self.assertTrue(report["policy"]["official_real_records_only"])
        self.assertTrue(
            report["policy"][
                "official_public_domain_personal_information_retained"
            ]
        )

    def test_failed_main_atomically_replaces_stale_success_control(self) -> None:
        published_dir = REPO_ROOT / "etl/data/published"
        with tempfile.TemporaryDirectory(
            prefix="readiness-failure-test-", dir=published_dir
        ) as temp_dir:
            output_path = (
                REPO_ROOT / temp_dir / "scale-readiness-failure-control.json"
            )
            output_path.write_text(
                '{"status":"real_foundation_ready_scale_incomplete"}\n',
                encoding="utf-8",
            )
            return_code = main(
                [
                    "--registry",
                    "docs/etl/missing-readiness-registry.json",
                    "--out",
                    output_path.relative_to(REPO_ROOT).as_posix(),
                    "--enforce-foundation",
                ]
            )
            report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(return_code, 1)
        self.assertEqual(report["status"], "not_ready")
        self.assertIs(report["foundation"]["ready"], False)
        self.assertEqual(report["failure"]["kind"], "readiness_validation_failed")
        self.assertIn("missing evidence file", report["failure"]["reason"])


if __name__ == "__main__":
    unittest.main()
