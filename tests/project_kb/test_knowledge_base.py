"""Dynamic validation for project KB content."""

from __future__ import annotations

import re

from project_kb.resolver import (
    build_kb_index,
    collect_all_entries,
    collect_top_level_entries,
    find_broken_refs,
)
from project_kb.resolver.resolver import load_knowledge_base_modules
from project_kb.schema import BaseKBEntry, EntryStatus, EntryType

EVIDENCE_REQUIRED_TYPES = {
    EntryType.DECISION,
    EntryType.FACT,
    EntryType.WORKFLOW,
    EntryType.GOTCHA,
    EntryType.DOMAIN_CONCEPT,
    EntryType.REFERENCE_MAP,
}


def test_knowledge_base_modules_export_entries() -> None:
    modules = load_knowledge_base_modules()
    assert modules, (
        "Expected at least one Python module under project_kb/knowledge_base."
    )

    for module in modules:
        entries = collect_top_level_entries([module])
        assert entries, f"Expected {module.__name__} to export at least one KB entry."
        assert all(isinstance(entry, BaseKBEntry) for entry in entries), module.__name__


def test_entries_round_trip() -> None:
    for entry in collect_all_entries():
        dumped = entry.model_dump()
        restored = type(entry).model_validate(dumped)
        assert restored == entry


def test_top_level_names_are_unique_per_root_type() -> None:
    for root_type, entries in build_kb_index().items():
        names = [entry.name for entry in entries]
        assert len(names) == len(set(names)), root_type


def test_all_references_resolve() -> None:
    broken = find_broken_refs(build_kb_index(), collect_all_entries())
    assert not broken, "Unresolved references:\n" + "\n".join(broken)


def test_reference_anchors_match_inline_code_in_descriptions() -> None:
    missing_markers = []
    unreferenced_markers = []

    for entry in collect_all_entries():
        reference_anchors = set(entry.references)
        inline_code_anchors = set(re.findall(r"`([^`]+)`", entry.description))

        for anchor in sorted(reference_anchors - inline_code_anchors):
            missing_markers.append(f"  [{entry.name}] {anchor!r}")
        for anchor in sorted(inline_code_anchors - reference_anchors):
            unreferenced_markers.append(f"  [{entry.name}] {anchor!r}")

    assert not missing_markers, (
        "Reference anchors must appear as inline code:\n" + "\n".join(missing_markers)
    )
    assert not unreferenced_markers, (
        "Inline-code anchors must appear in references:\n"
        + "\n".join(unreferenced_markers)
    )


def test_confirmed_durable_entries_have_evidence() -> None:
    missing = [
        entry.name
        for entry in collect_all_entries()
        if entry.status == EntryStatus.CONFIRMED
        and entry.entry_type in EVIDENCE_REQUIRED_TYPES
        and not entry.evidence
    ]
    assert not missing, "Confirmed durable entries need evidence:\n" + "\n".join(
        missing
    )
