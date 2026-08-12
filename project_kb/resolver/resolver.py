"""Discovery, indexing, and KBRef resolution for the project knowledge base."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from importlib import import_module
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel

from project_kb.schema import BaseKBEntry, to_root_type

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_PARENT = _PACKAGE_ROOT.parent
_KB_ROOT = _PACKAGE_ROOT / "knowledge_base"

KBIndex = dict[str, list[BaseKBEntry]]


def build_kb_index(modules: list[ModuleType] | None = None) -> KBIndex:
    index: KBIndex = {}
    for obj in collect_top_level_entries(_resolve_modules(modules)):
        index.setdefault(to_root_type(type(obj)), []).append(obj)
    return index


def resolve_kb_ref(kb_index: KBIndex, ref: str) -> object | None:
    parts = ref.split(".")
    if len(parts) < 2:
        return None

    root_type, name, *segments = parts
    current: object = next(
        (obj for obj in kb_index.get(root_type, []) if obj.name == name), None
    )
    if current is None:
        return None

    for segment in segments:
        if isinstance(current, BaseModel):
            if not hasattr(current, segment):
                return None
            current = getattr(current, segment)
        elif isinstance(current, list):
            current = next(
                (
                    item
                    for item in current
                    if isinstance(item, BaseModel)
                    and getattr(item, "name", None) == segment
                ),
                None,
            )
            if current is None:
                return None
        elif isinstance(current, dict):
            current = current.get(segment)
            if current is None:
                return None
        else:
            return None
    return current


def load_knowledge_base_modules() -> list[ModuleType]:
    module_names = [
        _module_name_from_path(path)
        for path in _KB_ROOT.rglob("*.py")
        if path.name != "__init__.py"
    ]
    return [import_module(name) for name in sorted(module_names)]


def collect_top_level_entries(modules: list[ModuleType]) -> list[BaseKBEntry]:
    objects: list[BaseKBEntry] = []
    for module in modules:
        for value in vars(module).values():
            objects.extend(_models_from_value(value))
    return objects


def collect_all_entries(modules: list[ModuleType] | None = None) -> list[BaseKBEntry]:
    seen: set[int] = set()
    return [
        entry
        for top in collect_top_level_entries(_resolve_modules(modules))
        for entry in iter_reference_entries(top, seen)
    ]


def find_broken_refs(
    kb_index: KBIndex, entries: list[BaseKBEntry] | None = None
) -> list[str]:
    if entries is None:
        entries = collect_all_entries()

    broken = []
    for entry in entries:
        for anchor, ref in entry.references.items():
            if resolve_kb_ref(kb_index, ref) is None:
                broken.append(f"[{entry.name}] {anchor!r} -> {ref!r}")
    return broken


def iter_reference_entries(
    value: object, seen: set[int]
) -> Generator[BaseKBEntry, None, None]:
    obj_id = id(value)
    if obj_id in seen:
        return
    seen.add(obj_id)

    if isinstance(value, BaseKBEntry):
        yield value
        for field_name in type(value).model_fields:
            yield from iter_reference_entries(getattr(value, field_name), seen)
    elif isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            yield from iter_reference_entries(getattr(value, field_name), seen)
    elif isinstance(value, list):
        for item in value:
            yield from iter_reference_entries(item, seen)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_reference_entries(item, seen)


def _resolve_modules(modules: list[ModuleType] | None) -> list[ModuleType]:
    return modules if modules is not None else load_knowledge_base_modules()


def _module_name_from_path(path: Path) -> str:
    return ".".join(path.relative_to(_PACKAGE_PARENT).with_suffix("").parts)


def _models_from_value(value: object) -> list[BaseKBEntry]:
    if isinstance(value, BaseKBEntry):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return [item for item in value if isinstance(item, BaseKBEntry)]
    return []
