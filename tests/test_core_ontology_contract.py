from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validate_core_ontology_contract import (
    EXPECTED_CONCEPTS,
    REQUIRED_RELATIONSHIPS,
    schema_table_names,
    validate_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs/data-model/core-ontology-v1.json"
DOC_PATH = REPO_ROOT / "docs/data-model/core-ontology-v1.md"
SCHEMA_PATH = REPO_ROOT / "etl/load/sqlite_schema.sql"


class CoreOntologyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.schema_text = SCHEMA_PATH.read_text(encoding="utf-8")

    def validate(self, contract: dict[str, object]) -> list[str]:
        return validate_contract(
            contract,
            doc_text=self.doc_text,
            schema_text=self.schema_text,
        )

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], self.validate(self.contract))

    def test_contract_has_exactly_the_nineteen_required_concepts(self) -> None:
        codes = {item["code"] for item in self.contract["concepts"]}
        self.assertEqual(EXPECTED_CONCEPTS, codes)
        self.assertEqual(19, len(codes))

    def test_every_mapped_table_exists_in_current_schema(self) -> None:
        schema_tables = schema_table_names(self.schema_text)
        mapped_tables = {
            table
            for concept in self.contract["concepts"]
            for table in concept["current_tables"]
        }
        self.assertEqual(set(), mapped_tables - schema_tables)

    def test_every_relationship_is_evidence_backed(self) -> None:
        relationships = self.contract["relationship_types"]
        self.assertTrue(relationships)
        self.assertTrue(all(item["evidence_required"] is True for item in relationships))
        self.assertTrue(
            REQUIRED_RELATIONSHIPS.issubset({item["code"] for item in relationships})
        )

    def test_real_only_and_public_identity_policy_are_enforced(self) -> None:
        policy = self.contract["policy"]
        self.assertTrue(policy["official_records_only"])
        self.assertTrue(policy["synthetic_or_mock_data_forbidden"])
        self.assertTrue(policy["placeholder_records_forbidden"])
        self.assertTrue(policy["implicit_fixture_fallback_forbidden"])
        self.assertTrue(policy["official_public_domain_personal_information_retained"])

    def test_missing_concept_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.contract)
        invalid["concepts"] = [
            item for item in invalid["concepts"] if item["code"] != "outcome"
        ]
        self.assertTrue(
            any("missing concepts: outcome" in error for error in self.validate(invalid))
        )

    def test_unknown_table_mapping_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.contract)
        invalid["concepts"][0]["current_tables"].append("table_that_does_not_exist")
        self.assertTrue(
            any("mapped table does not exist" in error for error in self.validate(invalid))
        )

    def test_identity_policy_regression_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.contract)
        invalid["policy"][
            "official_public_domain_personal_information_retained"
        ] = False
        self.assertTrue(
            any(
                "official_public_domain_personal_information_retained must be true"
                in error
                for error in self.validate(invalid)
            )
        )


if __name__ == "__main__":
    unittest.main()
