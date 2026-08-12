"""Resolver utilities for the project knowledge base."""

from .resolver import (
    KBIndex,
    build_kb_index,
    collect_all_entries,
    collect_top_level_entries,
    find_broken_refs,
    iter_reference_entries,
    load_knowledge_base_modules,
    resolve_kb_ref,
)

__all__ = [
    "KBIndex",
    "build_kb_index",
    "collect_all_entries",
    "collect_top_level_entries",
    "find_broken_refs",
    "iter_reference_entries",
    "load_knowledge_base_modules",
    "resolve_kb_ref",
]
