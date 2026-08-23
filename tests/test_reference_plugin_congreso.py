from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from publicdata_core.plugins import (
    PluginContext,
    PluginContractError,
    PluginRegistry,
    load_plugin,
    validate_plugin_manifest,
)
from scripts.run_reference_plugin import run_reference_plugin

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "plugins/congreso_representatives/plugin.json"
ONTOLOGY_PATH = REPO_ROOT / "docs/data-model/core-ontology-v1.json"


class CongresoReferencePluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
        cls.ontology_concepts = {item["code"] for item in cls.ontology["concepts"]}

    def test_manifest_and_exact_official_capture_validate(self) -> None:
        errors = validate_plugin_manifest(
            self.manifest,
            repo_root=REPO_ROOT,
            ontology_concepts=self.ontology_concepts,
            verify_capture_bytes=True,
        )
        self.assertEqual([], errors)
        capture = self.manifest["sources"][0]["official_capture_contracts"][0]
        payload = (REPO_ROOT / capture["path"]).read_bytes()
        self.assertEqual(capture["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(capture["bytes"], len(payload))

    def test_loader_imports_only_after_contract_validation(self) -> None:
        loaded = load_plugin(
            MANIFEST_PATH,
            repo_root=REPO_ROOT,
            ontology_path=ONTOLOGY_PATH,
        )
        self.assertEqual(self.manifest["plugin_id"], loaded.instance.plugin_id)
        for hook in self.manifest["hooks"]:
            self.assertTrue(callable(getattr(loaded.instance, hook)))

    def test_hooks_parse_and_normalize_the_real_capture(self) -> None:
        loaded = load_plugin(
            MANIFEST_PATH,
            repo_root=REPO_ROOT,
            ontology_path=ONTOLOGY_PATH,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = PluginContext(
                repo_root=REPO_ROOT,
                raw_dir=Path(temp_dir) / "raw",
                snapshot_date="2026-02-12",
                network_enabled=False,
            )
            item = next(iter(loaded.instance.discover(ctx)))
            artifact = loaded.instance.acquire(item, ctx)
            records = tuple(loaded.instance.parse(artifact, ctx))
            batch = loaded.instance.normalize(records, ctx)
            validation = loaded.instance.validate(batch)
        capture = self.manifest["sources"][0]["official_capture_contracts"][0]
        self.assertEqual(capture["sha256"], artifact.content_sha256)
        self.assertEqual(capture["official_url"], artifact.source_url)
        self.assertEqual(3, len(records))
        self.assertEqual(3, batch.source_records_loaded)
        self.assertEqual("ok", validation["status"])
        self.assertTrue(
            validation["official_public_domain_personal_information_retained"]
        )
        self.assertFalse(validation["synthetic_or_mock"])
        self.assertTrue(all(row["full_name"] for row in batch.rows))
        self.assertTrue(all(row["raw_payload"] for row in batch.rows))
        self.assertTrue(
            all(row["actor_id"].startswith("urn:vclc:actor:") for row in batch.rows)
        )

    def test_real_capture_ingests_into_standard_schema_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            report = run_reference_plugin(
                manifest_path=MANIFEST_PATH,
                ontology_path=ONTOLOGY_PATH,
                db_path=temp_root / "plugin.db",
                raw_dir=temp_root / "raw",
                snapshot_date="2026-02-12",
                network_enabled=False,
                repeat=2,
            )
        self.assertEqual("ok", report["status"])
        self.assertFalse(report["policy"]["synthetic_or_mock"])
        self.assertTrue(
            report["policy"]["official_public_domain_personal_information_retained"]
        )
        self.assertEqual(3, report["sqlite"]["counts"]["source_records"])
        self.assertEqual(3, report["sqlite"]["counts"]["mandates"])
        self.assertEqual(3, report["sqlite"]["counts"]["persons_linked"])
        self.assertEqual(2, report["sqlite"]["counts"]["ingestion_runs"])
        self.assertEqual(0, report["sqlite"]["foreign_key_failures"])
        self.assertTrue(report["sqlite"]["idempotent"])
        self.assertEqual(
            [
                self.manifest["sources"][0]["official_capture_contracts"][0][
                    "official_url"
                ]
            ],
            report["sqlite"]["source_urls"],
        )

    def test_fact_ids_and_logical_hash_are_deterministic(self) -> None:
        loaded = load_plugin(
            MANIFEST_PATH,
            repo_root=REPO_ROOT,
            ontology_path=ONTOLOGY_PATH,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            ctx = PluginContext(
                repo_root=REPO_ROOT,
                raw_dir=Path(temp_dir) / "raw",
                snapshot_date="2026-02-12",
            )
            item = next(iter(loaded.instance.plan(ctx)))
            artifact = loaded.instance.acquire(item, ctx)
            records = tuple(loaded.instance.parse(artifact, ctx))
            first = loaded.instance.normalize(records, ctx)
            second = loaded.instance.normalize(records, ctx)
        self.assertEqual(first.logical_sha256, second.logical_sha256)
        self.assertEqual(
            [row["actor_id"] for row in first.rows],
            [row["actor_id"] for row in second.rows],
        )
        self.assertEqual(
            [row["role_assignment_id"] for row in first.rows],
            [row["role_assignment_id"] for row in second.rows],
        )

    def test_registry_rejects_duplicate_plugin_ids(self) -> None:
        registry = PluginRegistry()
        registry.load_paths(
            [MANIFEST_PATH],
            repo_root=REPO_ROOT,
            ontology_path=ONTOLOGY_PATH,
        )
        self.assertEqual((self.manifest["plugin_id"],), registry.plugin_ids())
        with self.assertRaises(PluginContractError):
            registry.load_paths(
                [MANIFEST_PATH],
                repo_root=REPO_ROOT,
                ontology_path=ONTOLOGY_PATH,
            )

    def test_manifest_rejects_policy_regression_before_import(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["sources"][0]["synthetic_or_mock_data"] = True
        invalid["publication"][
            "official_public_domain_personal_information_retained"
        ] = False
        errors = validate_plugin_manifest(
            invalid,
            repo_root=REPO_ROOT,
            ontology_concepts=self.ontology_concepts,
        )
        self.assertTrue(
            any("synthetic_or_mock_data must be false" in error for error in errors)
        )
        self.assertTrue(
            any(
                "official_public_domain_personal_information_retained must be true"
                in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
