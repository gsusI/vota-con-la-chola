#!/usr/bin/env python3
"""Validate the core ontology contract against its documentation and SQLite schema."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_CONCEPTS = {
    "actor",
    "organization",
    "role",
    "territory",
    "source",
    "document",
    "evidence",
    "topic",
    "claim",
    "promise",
    "initiative",
    "vote",
    "spending_item",
    "contract",
    "agreement",
    "meeting",
    "event",
    "indicator",
    "outcome",
}

REQUIRED_RELATIONSHIPS = {
    "IDENTIFIES",
    "ALIAS_OF",
    "MEMBER_OF",
    "HOLDS_ROLE",
    "SUBUNIT_OF",
    "LOCATED_IN",
    "PUBLISHED_BY",
    "VERSION_OF",
    "EXTRACTED_FROM",
    "SUPPORTS",
    "CONTRADICTS",
    "ABOUT",
    "ATTRIBUTED_TO",
    "COMMITS_TO",
    "SPONSORS",
    "VOTES_IN",
    "IMPLEMENTS",
    "PAYS",
    "RECEIVES",
    "PARTY_TO",
    "ATTENDS",
    "MEASURES",
    "OBSERVED_AS",
    "PRECEDES",
    "SUPERSEDES",
    "CORRECTS",
}

DOC_LABELS = {
    "actor": "Actor",
    "organization": "Organization",
    "role": "Role",
    "territory": "Territory",
    "source": "Source",
    "document": "Document",
    "evidence": "Evidence",
    "topic": "Topic",
    "claim": "Claim",
    "promise": "Promise",
    "initiative": "Initiative",
    "vote": "Vote",
    "spending_item": "Spending item",
    "contract": "Contract",
    "agreement": "Agreement",
    "meeting": "Meeting",
    "event": "Event",
    "indicator": "Indicator",
    "outcome": "Outcome",
}


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def schema_table_names(schema_text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)",
            schema_text,
            flags=re.IGNORECASE,
        )
    }


def validate_contract(
    contract: dict[str, Any],
    *,
    doc_text: str,
    schema_text: str,
) -> list[str]:
    errors: list[str] = []

    if contract.get("schema_version") != "core_ontology_v1":
        errors.append("schema_version must be core_ontology_v1")

    policy = contract.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
        policy = {}
    for policy_key in (
        "official_records_only",
        "synthetic_or_mock_data_forbidden",
        "placeholder_records_forbidden",
        "implicit_fixture_fallback_forbidden",
        "official_public_domain_personal_information_retained",
        "private_or_secret_material_excluded",
        "derived_signals_are_not_corruption_findings",
        "causality_requires_separate_methodological_gate",
    ):
        if policy.get(policy_key) is not True:
            errors.append(f"policy.{policy_key} must be true")

    id_contract = contract.get("id_contract")
    if not isinstance(id_contract, dict):
        errors.append("id_contract must be an object")
        id_contract = {}
    if id_contract.get("person_name_alone_may_define_identity") is not False:
        errors.append("person names alone must never define identity")
    if id_contract.get("cross_source_resolution_requires_evidence") is not True:
        errors.append("cross-source identity resolution must require evidence")

    time_contract = contract.get("time_contract")
    if not isinstance(time_contract, dict):
        errors.append("time_contract must be an object")
        time_contract = {}
    required_observation_fields = set(time_contract.get("required_observation_fields") or [])
    if not {"observed_at", "source_snapshot_date"}.issubset(required_observation_fields):
        errors.append("time_contract must require observed_at and source_snapshot_date")

    provenance = contract.get("provenance_contract")
    if not isinstance(provenance, dict):
        errors.append("provenance_contract must be an object")
        provenance = {}
    required_fact_fields = set(provenance.get("required_fact_fields") or [])
    for field in (
        "source_id",
        "source_record_id_or_pk",
        "source_snapshot_date",
        "observed_at",
        "content_sha256_or_cas_reference",
    ):
        if field not in required_fact_fields:
            errors.append(f"provenance_contract.required_fact_fields missing {field}")

    concepts = contract.get("concepts")
    if not isinstance(concepts, list):
        errors.append("concepts must be an array")
        concepts = []
    concept_codes = [str(item.get("code") or "") for item in concepts if isinstance(item, dict)]
    if duplicate_concepts := _duplicates(concept_codes):
        errors.append(f"duplicate concept codes: {', '.join(duplicate_concepts)}")
    actual_concepts = set(concept_codes)
    missing_concepts = sorted(EXPECTED_CONCEPTS - actual_concepts)
    extra_concepts = sorted(actual_concepts - EXPECTED_CONCEPTS)
    if missing_concepts:
        errors.append(f"missing concepts: {', '.join(missing_concepts)}")
    if extra_concepts:
        errors.append(f"unexpected concepts: {', '.join(extra_concepts)}")

    relationships = contract.get("relationship_types")
    if not isinstance(relationships, list):
        errors.append("relationship_types must be an array")
        relationships = []
    relationship_codes = [
        str(item.get("code") or "") for item in relationships if isinstance(item, dict)
    ]
    if duplicate_relationships := _duplicates(relationship_codes):
        errors.append(f"duplicate relationship codes: {', '.join(duplicate_relationships)}")
    actual_relationships = set(relationship_codes)
    missing_relationships = sorted(REQUIRED_RELATIONSHIPS - actual_relationships)
    if missing_relationships:
        errors.append(f"missing relationship types: {', '.join(missing_relationships)}")

    declared_tables = schema_table_names(schema_text)
    for concept in concepts:
        if not isinstance(concept, dict):
            errors.append("every concept must be an object")
            continue
        code = str(concept.get("code") or "")
        public_id_field = str(concept.get("public_id_field") or "")
        required_fields = set(concept.get("required_fields") or [])
        if not public_id_field.endswith("_id"):
            errors.append(f"concept {code}: public_id_field must end with _id")
        if public_id_field and public_id_field not in required_fields:
            errors.append(f"concept {code}: required_fields missing {public_id_field}")
        if not {"created_at", "updated_at"}.issubset(required_fields):
            errors.append(f"concept {code}: created_at and updated_at are required")
        if not str(concept.get("provenance_mode") or "").strip():
            errors.append(f"concept {code}: provenance_mode is required")
        for table in concept.get("current_tables") or []:
            if table not in declared_tables:
                errors.append(f"concept {code}: mapped table does not exist: {table}")
        unknown_relation_refs = sorted(set(concept.get("relations") or []) - actual_relationships)
        if unknown_relation_refs:
            errors.append(
                f"concept {code}: unknown relation refs: {', '.join(unknown_relation_refs)}"
            )

    for relationship in relationships:
        if not isinstance(relationship, dict):
            errors.append("every relationship must be an object")
            continue
        code = str(relationship.get("code") or "")
        if relationship.get("evidence_required") is not True:
            errors.append(f"relationship {code}: evidence_required must be true")
        for endpoint_key in ("source_concepts", "target_concepts"):
            endpoints = relationship.get(endpoint_key)
            if not isinstance(endpoints, list) or not endpoints:
                errors.append(f"relationship {code}: {endpoint_key} must be a non-empty array")
                continue
            unknown_endpoints = sorted(set(endpoints) - EXPECTED_CONCEPTS)
            if unknown_endpoints:
                errors.append(
                    f"relationship {code}: unknown {endpoint_key}: {', '.join(unknown_endpoints)}"
                )

    scale = contract.get("scale_contract")
    if not isinstance(scale, dict):
        errors.append("scale_contract must be an object")
        scale = {}
    if int(scale.get("minimum_supported_facts") or 0) < 10_000_000:
        errors.append("scale_contract.minimum_supported_facts must be at least 10000000")
    if int(scale.get("minimum_supported_documents") or 0) < 1_000_000:
        errors.append("scale_contract.minimum_supported_documents must be at least 1000000")
    if int(scale.get("target_supported_facts_without_ontology_change") or 0) < 100_000_000:
        errors.append(
            "scale_contract.target_supported_facts_without_ontology_change must be at least 100000000"
        )
    if scale.get("promotion_requires_real_official_corpus") is not True:
        errors.append("scale promotion must require a real official corpus")

    if "# Core ontology v1" not in doc_text:
        errors.append("documentation title missing")
    if "## 18. Gates de conformidad" not in doc_text:
        errors.append("documentation conformity gates missing")
    if "official_public_domain_personal_information_retained" not in json.dumps(
        contract, ensure_ascii=False
    ):
        errors.append("machine policy for public-domain identity retention missing")
    for code, label in DOC_LABELS.items():
        if not re.search(rf"^###\s+7\.\d+\s+{re.escape(label)}\s*$", doc_text, re.MULTILINE):
            errors.append(f"documentation section missing for concept {code}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/data-model/core-ontology-v1.json",
        help="Machine-readable ontology contract",
    )
    parser.add_argument(
        "--doc",
        default="docs/data-model/core-ontology-v1.md",
        help="Human-readable ontology document",
    )
    parser.add_argument(
        "--schema",
        default="etl/load/sqlite_schema.sql",
        help="Current SQLite schema used to validate table mappings",
    )
    parser.add_argument("--out", default="", help="Optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract)
    doc_path = Path(args.doc)
    schema_path = Path(args.schema)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    doc_text = doc_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    errors = validate_contract(contract, doc_text=doc_text, schema_text=schema_text)
    report = {
        "schema_version": "core_ontology_validation_v1",
        "status": "ok" if not errors else "error",
        "checks": {
            "ontology_schema_version": contract.get("schema_version"),
            "concepts_total": len(contract.get("concepts") or []),
            "relationship_types_total": len(contract.get("relationship_types") or []),
            "mapped_schema_tables_total": len(
                {
                    table
                    for concept in contract.get("concepts") or []
                    if isinstance(concept, dict)
                    for table in concept.get("current_tables") or []
                }
            ),
            "official_records_only": (contract.get("policy") or {}).get(
                "official_records_only"
            ),
            "official_public_domain_personal_information_retained": (
                contract.get("policy") or {}
            ).get("official_public_domain_personal_information_retained"),
            "minimum_supported_facts": (contract.get("scale_contract") or {}).get(
                "minimum_supported_facts"
            ),
            "minimum_supported_documents": (contract.get("scale_contract") or {}).get(
                "minimum_supported_documents"
            ),
        },
        "errors": errors,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
