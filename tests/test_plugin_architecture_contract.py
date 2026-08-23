from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validate_plugin_architecture import (
    EXPECTED_HOOKS,
    EXPECTED_PLUGIN_TYPES,
    EXPECTED_TEST_HOOKS,
    validate_plugin_architecture,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "docs/architecture/plugin-manifest-v1.schema.json"
ONTOLOGY_PATH = REPO_ROOT / "docs/data-model/core-ontology-v1.json"
DOC_PATH = REPO_ROOT / "docs/architecture/plugin-system-v1.md"


class PluginArchitectureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")

    def validate(self, schema: dict[str, object]) -> list[str]:
        return validate_plugin_architecture(
            schema,
            ontology=self.ontology,
            doc_text=self.doc_text,
            repo_root=REPO_ROOT,
        )

    def test_repository_plugin_architecture_is_valid(self) -> None:
        self.assertEqual([], self.validate(self.schema))

    def test_plugin_types_and_hooks_are_complete(self) -> None:
        self.assertEqual(
            EXPECTED_PLUGIN_TYPES,
            set(self.schema["$defs"]["plugin_type"]["enum"]),
        )
        self.assertEqual(
            EXPECTED_HOOKS,
            set(self.schema["properties"]["hooks"]["items"]["enum"]),
        )
        self.assertEqual(
            EXPECTED_TEST_HOOKS,
            set(self.schema["$defs"]["test_hook"]["properties"]["kind"]["enum"]),
        )

    def test_outputs_use_exact_core_ontology_vocabulary(self) -> None:
        ontology_codes = {item["code"] for item in self.ontology["concepts"]}
        output_codes = set(
            self.schema["$defs"]["output"]["properties"]["ontology_concept"]["enum"]
        )
        self.assertEqual(ontology_codes, output_codes)

    def test_real_only_and_identity_rules_are_non_overridable(self) -> None:
        source_properties = self.schema["$defs"]["source"]["properties"]
        publication_properties = self.schema["$defs"]["publication"]["properties"]
        self.assertIs(source_properties["synthetic_or_mock_data"]["const"], False)
        self.assertIs(source_properties["implicit_fallback"]["const"], False)
        self.assertIs(
            source_properties["official_public_domain_personal_information_retained"][
                "const"
            ],
            True,
        )
        self.assertIs(publication_properties["official_records_only"]["const"], True)
        self.assertIs(
            publication_properties[
                "official_public_domain_personal_information_retained"
            ]["const"],
            True,
        )

    def test_missing_plugin_type_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.schema)
        invalid["$defs"]["plugin_type"]["enum"].remove("publisher")
        self.assertTrue(
            any(
                "plugin type enum mismatch" in error for error in self.validate(invalid)
            )
        )

    def test_ontology_drift_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.schema)
        invalid["$defs"]["output"]["properties"]["ontology_concept"]["enum"].remove(
            "outcome"
        )
        self.assertTrue(
            any("plugin output concepts" in error for error in self.validate(invalid))
        )

    def test_policy_regression_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.schema)
        invalid["$defs"]["publication"]["properties"][
            "official_public_domain_personal_information_retained"
        ]["const"] = False
        self.assertTrue(
            any(
                "publication.official_public_domain_personal_information_retained"
                in error
                for error in self.validate(invalid)
            )
        )

    def test_security_regression_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.schema)
        invalid["$defs"]["security"]["properties"]["remote_code_execution"]["const"] = (
            True
        )
        self.assertTrue(
            any(
                "security.remote_code_execution" in error
                for error in self.validate(invalid)
            )
        )


if __name__ == "__main__":
    unittest.main()
