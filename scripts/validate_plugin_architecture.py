#!/usr/bin/env python3
"""Validate plugin architecture v1 documentation and manifest schema."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

EXPECTED_PLUGIN_TYPES = {
    "connector",
    "parser",
    "normalizer",
    "extractor",
    "linker",
    "scorer",
    "publisher",
}

EXPECTED_HOOKS = {
    "register",
    "validate_config",
    "plan",
    "discover",
    "acquire",
    "parse",
    "normalize",
    "extract",
    "link",
    "score",
    "validate",
    "publish",
    "checkpoint",
    "cleanup",
}

EXPECTED_TEST_HOOKS = {
    "contract",
    "official_capture_replay",
    "idempotence",
    "schema",
    "provenance",
    "strict_network",
    "scale",
    "publish_dry_run",
    "restore",
    "regression",
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "plugin_id",
    "name",
    "version",
    "description",
    "license",
    "entry_point",
    "plugin_types",
    "maintainers",
    "compatibility",
    "sources",
    "capabilities",
    "hooks",
    "inputs",
    "outputs",
    "runtime",
    "partitions",
    "idempotency",
    "provenance",
    "quality_gates",
    "test_hooks",
    "security",
    "publication",
}

REQUIRED_CURRENT_PATHS = (
    "publicdata_core/connectors.py",
    "publicdata_core/types.py",
    "publicdata_core/sources.py",
    "publicdata_core/workflows.py",
    "publicdata_connectors_es",
    "scripts/add_source.py",
    "etl/load/sqlite_schema.sql",
)


def _definition(schema: dict[str, Any], name: str) -> dict[str, Any]:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return {}
    value = definitions.get(name)
    return value if isinstance(value, dict) else {}


def _property(schema: dict[str, Any], name: str) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    value = properties.get(name)
    return value if isinstance(value, dict) else {}


def _iter_pattern_values(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "pattern" and isinstance(child, str):
                yield child
            yield from _iter_pattern_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_pattern_values(child)


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: set[str] = set()
    for value in values:
        if value in seen:
            duplicated.add(value)
        seen.add(value)
    return sorted(duplicated)


def validate_plugin_architecture(
    schema: dict[str, Any],
    *,
    ontology: dict[str, Any],
    doc_text: str,
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("manifest schema must use JSON Schema draft 2020-12")
    if (
        schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        errors.append("manifest root must be a closed object")

    required = set(schema.get("required") or [])
    missing_required = sorted(REQUIRED_TOP_LEVEL_FIELDS - required)
    if missing_required:
        errors.append(
            f"manifest required fields missing: {', '.join(missing_required)}"
        )

    plugin_types = set(_definition(schema, "plugin_type").get("enum") or [])
    if plugin_types != EXPECTED_PLUGIN_TYPES:
        errors.append(
            "plugin type enum mismatch: "
            f"expected={sorted(EXPECTED_PLUGIN_TYPES)} actual={sorted(plugin_types)}"
        )

    hook_items = _property(schema, "hooks").get("items")
    hooks = set(hook_items.get("enum") or []) if isinstance(hook_items, dict) else set()
    if hooks != EXPECTED_HOOKS:
        errors.append(
            f"hook enum mismatch: expected={sorted(EXPECTED_HOOKS)} actual={sorted(hooks)}"
        )

    test_hook_kind = _property(_definition(schema, "test_hook"), "kind")
    test_hooks = set(test_hook_kind.get("enum") or [])
    if test_hooks != EXPECTED_TEST_HOOKS:
        errors.append(
            "test hook enum mismatch: "
            f"expected={sorted(EXPECTED_TEST_HOOKS)} actual={sorted(test_hooks)}"
        )

    ontology_codes = {
        str(item.get("code") or "")
        for item in ontology.get("concepts") or []
        if isinstance(item, dict)
    }
    output_concept = _property(_definition(schema, "output"), "ontology_concept")
    output_concepts = set(output_concept.get("enum") or [])
    if output_concepts != ontology_codes:
        errors.append(
            "plugin output concepts must exactly match core ontology: "
            f"missing={sorted(ontology_codes - output_concepts)} "
            f"extra={sorted(output_concepts - ontology_codes)}"
        )

    source_properties = _definition(schema, "source").get("properties")
    source_properties = source_properties if isinstance(source_properties, dict) else {}
    for key, expected in (
        ("official_public_domain_personal_information_retained", True),
        ("synthetic_or_mock_data", False),
        ("implicit_fallback", False),
    ):
        value = source_properties.get(key)
        if not isinstance(value, dict) or value.get("const") is not expected:
            errors.append(f"source.{key} must be const {str(expected).lower()}")

    publication_properties = _definition(schema, "publication").get("properties")
    publication_properties = (
        publication_properties if isinstance(publication_properties, dict) else {}
    )
    for key in (
        "official_records_only",
        "synthetic_or_mock_data_forbidden",
        "placeholder_data_forbidden",
        "implicit_fallback_forbidden",
        "official_public_domain_personal_information_retained",
        "publication_hygiene_required",
        "validation_before_publish_required",
    ):
        value = publication_properties.get(key)
        if not isinstance(value, dict) or value.get("const") is not True:
            errors.append(f"publication.{key} must be const true")

    security_properties = _definition(schema, "security").get("properties")
    security_properties = (
        security_properties if isinstance(security_properties, dict) else {}
    )
    for key in (
        "credentials_embedded",
        "remote_code_execution",
        "auto_install_dependencies",
        "manifest_contains_secrets",
    ):
        value = security_properties.get(key)
        if not isinstance(value, dict) or value.get("const") is not False:
            errors.append(f"security.{key} must be const false")
    runtime_enforcement = security_properties.get("runtime_capability_enforcement")
    if (
        not isinstance(runtime_enforcement, dict)
        or runtime_enforcement.get("const") is not True
    ):
        errors.append("security.runtime_capability_enforcement must be const true")

    uses_real_data = _property(
        _definition(schema, "test_hook"), "uses_official_real_data"
    )
    if uses_real_data.get("const") is not True:
        errors.append("test hooks must require official real data")

    for pattern in _iter_pattern_values(schema):
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"invalid regex pattern {pattern!r}: {exc}")

    serialized = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    if '"examples"' in serialized or '"example"' in serialized:
        errors.append("manifest schema must not embed sample dataset records")

    for required_heading in (
        "# Plugin system v1",
        "## 2. Estado actual, dirección y siguiente paso",
        "## 4. Tipos de plugin",
        "## 5. Lifecycle",
        "## 7. Manifest v1",
        "## 10. Ejecución y escala",
        "## 12. Test hooks",
        "## 14. Versionado",
        "## 15. Compatibilidad con implementación actual",
        "## 20. Definition of Done v1",
    ):
        if required_heading not in doc_text:
            errors.append(
                f"architecture documentation missing heading: {required_heading}"
            )

    for plugin_type in EXPECTED_PLUGIN_TYPES:
        label = plugin_type.capitalize()
        if not re.search(rf"^###\s+4\.\d+\s+{label}\s*$", doc_text, re.MULTILINE):
            errors.append(
                f"architecture documentation missing plugin type: {plugin_type}"
            )

    for required_phrase in (
        "official public personal identity remains",
        "No se usará dataset inventado",
        "at-least-once",
        "exactly-once lógico",
        "content hash",
        "bounded",
    ):
        if required_phrase.casefold() not in doc_text.casefold():
            errors.append(
                f"architecture documentation missing contract phrase: {required_phrase}"
            )

    for relative_path in REQUIRED_CURRENT_PATHS:
        if not (repo_root / relative_path).exists():
            errors.append(f"current implementation path missing: {relative_path}")

    connector_text = (repo_root / "publicdata_core/connectors.py").read_text(
        encoding="utf-8"
    )
    extracted_text = (repo_root / "publicdata_core/types.py").read_text(
        encoding="utf-8"
    )
    for token in ("class BaseConnector", "def resolve_url", "def extract"):
        if token not in connector_text:
            errors.append(f"current connector compatibility token missing: {token}")
    if "class Extracted" not in extracted_text:
        errors.append("current Extracted compatibility contract missing")

    all_of = schema.get("allOf")
    if not isinstance(all_of, list) or len(all_of) < 2:
        errors.append(
            "manifest schema must condition connector and publisher requirements"
        )

    duplicates = _duplicates(list(schema.get("required") or []))
    if duplicates:
        errors.append(f"duplicate root required fields: {', '.join(duplicates)}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        default="docs/architecture/plugin-manifest-v1.schema.json",
        help="Plugin manifest JSON Schema",
    )
    parser.add_argument(
        "--ontology",
        default="docs/data-model/core-ontology-v1.json",
        help="Core ontology machine contract",
    )
    parser.add_argument(
        "--doc",
        default="docs/architecture/plugin-system-v1.md",
        help="Plugin architecture document",
    )
    parser.add_argument("--out", default="", help="Optional JSON validation report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    ontology = json.loads(Path(args.ontology).read_text(encoding="utf-8"))
    doc_text = Path(args.doc).read_text(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    errors = validate_plugin_architecture(
        schema,
        ontology=ontology,
        doc_text=doc_text,
        repo_root=repo_root,
    )
    plugin_type_count = len(_definition(schema, "plugin_type").get("enum") or [])
    hook_items = _property(schema, "hooks").get("items")
    hook_count = (
        len(hook_items.get("enum") or []) if isinstance(hook_items, dict) else 0
    )
    output_concept_count = len(
        _property(_definition(schema, "output"), "ontology_concept").get("enum") or []
    )
    report = {
        "schema_version": "plugin_architecture_validation_v1",
        "status": "ok" if not errors else "error",
        "checks": {
            "manifest_schema_version": _property(schema, "schema_version").get("const"),
            "plugin_types_total": plugin_type_count,
            "lifecycle_hooks_total": hook_count,
            "ontology_output_concepts_total": output_concept_count,
            "test_hooks_total": len(
                _property(_definition(schema, "test_hook"), "kind").get("enum") or []
            ),
            "source_real_only_enforced": (
                _property(_definition(schema, "source"), "synthetic_or_mock_data").get(
                    "const"
                )
                is False
            ),
            "public_identity_retention_enforced": (
                _property(
                    _definition(schema, "publication"),
                    "official_public_domain_personal_information_retained",
                ).get("const")
                is True
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
