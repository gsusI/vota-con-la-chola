from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.report_scale_readiness import (
    REPO_ROOT,
    checks_pass,
    load_json,
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
        self.assertTrue(checks_pass({"status": "ok", "checks": {"hash": True}}, require_status=True))
        self.assertFalse(checks_pass({"status": "failed", "checks": {"hash": True}}, require_status=True))
        self.assertFalse(checks_pass({"status": "ok", "checks": {"hash": False}}, require_status=True))

    def test_one_captured_official_vote_shard_matches_manifest(self) -> None:
        corpus = next(item for item in self.registry["corpora"] if item["id"] == "member_votes")
        manifest = json.loads(repo_path(corpus["manifest"]).read_text(encoding="utf-8"))
        entry = next(item for item in manifest["entries"] if item["member_votes"] > 0)
        observed_rows, observed_source_urls, observed_https_urls, source_ids, hosts = validate_member_vote_shard(
            repo_path(corpus["root"]) / entry["shard"],
            entry,
            allowed_source_ids=set(corpus["official_source_ids"]),
            allowed_hosts=set(corpus["official_hosts"]),
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


if __name__ == "__main__":
    unittest.main()
