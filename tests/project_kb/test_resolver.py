"""Unit tests for project KB resolver behavior."""

from __future__ import annotations

from types import ModuleType

import pytest

from project_kb.resolver import (
    KBIndex,
    collect_all_entries,
    find_broken_refs,
    resolve_kb_ref,
)
from project_kb.schema import Decision, DomainConcept, Evidence, Fact
from project_kb.schema.core import to_root_type


@pytest.fixture
def kb_index() -> KBIndex:
    concept = DomainConcept(
        name="Project KB",
        description="Canonical project learning store.",
        evidence=[Evidence(source="test fixture")],
        aliases=["knowledge base"],
    )
    decision = Decision(
        name="Use project KB",
        description="Use the project KB as source of truth.",
        evidence=[Evidence(source="test fixture")],
    )
    return {
        "domain_concept": [concept],
        "decision": [decision],
    }


def test_to_root_type() -> None:
    assert to_root_type(DomainConcept) == "domain_concept"


def test_resolve_top_level_object(kb_index: KBIndex) -> None:
    result = resolve_kb_ref(kb_index, "domain_concept.Project KB")
    assert isinstance(result, DomainConcept)
    assert result.name == "Project KB"


def test_resolve_scalar_field(kb_index: KBIndex) -> None:
    assert (
        resolve_kb_ref(kb_index, "domain_concept.Project KB.description")
        == "Canonical project learning store."
    )


def test_resolve_list_value_by_name_returns_none_for_scalars(kb_index: KBIndex) -> None:
    assert (
        resolve_kb_ref(kb_index, "domain_concept.Project KB.aliases.knowledge base")
        is None
    )


def test_resolve_unknown_segments_return_none(kb_index: KBIndex) -> None:
    assert resolve_kb_ref(kb_index, "domain_concept.Missing") is None
    assert resolve_kb_ref(kb_index, "missing.Project KB") is None
    assert resolve_kb_ref(kb_index, "domain_concept.Project KB.missing") is None


def test_find_broken_refs(kb_index: KBIndex) -> None:
    entry = Fact(
        name="Fixture fact",
        description="References `project KB`.",
        evidence=[Evidence(source="test fixture")],
        references={"project KB": "domain_concept.Project KB"},
    )
    assert find_broken_refs(kb_index, [entry]) == []

    broken_entry = Fact(
        name="Broken fixture fact",
        description="References `missing`.",
        evidence=[Evidence(source="test fixture")],
        references={"missing": "domain_concept.Missing"},
    )
    assert find_broken_refs(kb_index, [broken_entry])


def test_collect_all_entries_includes_module_exports() -> None:
    module = ModuleType("fixture")
    module.ENTRIES = [
        Fact(
            name="Fixture fact",
            description="Fixture entry.",
            evidence=[Evidence(source="test fixture")],
        )
    ]
    assert collect_all_entries([module]) == module.ENTRIES
