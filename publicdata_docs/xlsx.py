"""Bounded, deterministic text extraction for real XLSX workbooks."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import struct
from collections import OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryFile
from typing import BinaryIO
from xml.etree.ElementTree import Element, TreeBuilder
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile, ZipInfo

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
DEFAULT_MAX_WORKBOOK_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 1_000
DEFAULT_MAX_MEMBERS = 1_024
DEFAULT_MAX_WORKSHEETS = 256
DEFAULT_MAX_ROWS = 1_000_000
DEFAULT_MAX_CELLS = 10_000_000
DEFAULT_MAX_CELLS_PER_ROW = 16_384
DEFAULT_MAX_ROW_NUMBER = 1_048_576
DEFAULT_MAX_COLUMN_INDEX = 16_384
DEFAULT_MAX_SHARED_STRINGS = 5_000_000
DEFAULT_SHARED_STRING_CACHE_ITEMS = 4_096
DEFAULT_SHARED_STRING_CACHE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 32 * 1024 * 1024
DEFAULT_MAX_XML_DEPTH = 64
DEFAULT_MAX_XML_ELEMENTS = 50_000_000

_MAIN_NS_URI = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS_URI = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOCUMENT_REL_NS_URI = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_MAIN_NS = "{" + _MAIN_NS_URI + "}"
_RELATIONSHIP_EXPAT_NAME = _REL_NS_URI + "}Relationship"
_SHEET_EXPAT_NAME = _MAIN_NS_URI + "}sheet"
_DOCUMENT_REL_ID_EXPAT_NAME = _DOCUMENT_REL_NS_URI + "}id"
_WORKBOOK_PATH = "xl/workbook.xml"
_WORKBOOK_RELS_PATH = "xl/_rels/workbook.xml.rels"
_SHARED_STRINGS_PATH = "xl/sharedStrings.xml"
_CELL_REF_RE = re.compile(r"^[A-Z]{1,7}[1-9][0-9]*$")
_WORKSHEET_REL_TYPE_SUFFIX = "/worksheet"
_SHARED_STRING_OFFSET = struct.Struct("<QQ")
_XML_READ_CHUNK_BYTES = 64 * 1024


class XlsxExtractionError(RuntimeError):
    """Raised when an XLSX violates the bounded extraction contract."""


@dataclass(frozen=True)
class XlsxTextRow:
    sheet_index: int
    sheet_name: str
    row_number: int
    text_start_char: int
    text_end_char: int


@dataclass(frozen=True)
class XlsxExtraction:
    text: str
    text_chars: int
    canonical_text_sha256: str
    worksheet_count: int
    worksheet_rows: int
    nonempty_worksheet_rows: int
    nonempty_cells: int
    formula_cells: int
    rows: tuple[XlsxTextRow, ...]


@dataclass(frozen=True)
class _Sheet:
    name: str
    path: str


@dataclass(frozen=True)
class _SharedStringValue:
    value: str
    phonetic_annotations: str


XlsxRowCallback = Callable[[XlsxTextRow, str], None]


class _SharedStringTable:
    """Disk-backed UTF-8 values and offsets with a strictly bounded LRU cache."""

    def __init__(self, *, cache_items: int, cache_bytes: int) -> None:
        self._values = TemporaryFile(mode="w+b")
        self._offsets = TemporaryFile(mode="w+b")
        self._count = 0
        self._cache_items = cache_items
        self._cache_bytes_limit = cache_bytes
        self._cache_bytes = 0
        self._cache: OrderedDict[int, tuple[_SharedStringValue, int]] = OrderedDict()

    def __enter__(self) -> _SharedStringTable:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def __len__(self) -> int:
        return self._count

    def close(self) -> None:
        self._cache.clear()
        self._cache_bytes = 0
        self._offsets.close()
        self._values.close()

    def append(self, value: _SharedStringValue) -> None:
        payload = json.dumps(
            [value.value, value.phonetic_annotations],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self._values.seek(0, 2)
        offset = self._values.tell()
        self._values.write(payload)
        self._offsets.seek(0, 2)
        self._offsets.write(_SHARED_STRING_OFFSET.pack(offset, len(payload)))
        self._count += 1

    def get(self, index: int) -> _SharedStringValue:
        if index < 0 or index >= self._count:
            raise XlsxExtractionError("XLSX shared-string index outside table")
        cached = self._cache.pop(index, None)
        if cached is not None:
            self._cache[index] = cached
            return cached[0]

        self._offsets.seek(index * _SHARED_STRING_OFFSET.size)
        record = self._offsets.read(_SHARED_STRING_OFFSET.size)
        if len(record) != _SHARED_STRING_OFFSET.size:
            raise XlsxExtractionError("XLSX shared-string offset table is incomplete")
        offset, payload_bytes = _SHARED_STRING_OFFSET.unpack(record)
        self._values.seek(offset)
        payload = self._values.read(payload_bytes)
        if len(payload) != payload_bytes:
            raise XlsxExtractionError("XLSX shared-string value table is incomplete")
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise XlsxExtractionError("XLSX shared-string UTF-8 replay failed") from exc
        if (
            not isinstance(decoded, list)
            or len(decoded) != 2
            or not all(isinstance(item, str) for item in decoded)
        ):
            raise XlsxExtractionError("XLSX shared-string replay contract drifted")
        value = _SharedStringValue(decoded[0], decoded[1])

        if payload_bytes <= self._cache_bytes_limit:
            self._cache[index] = (value, payload_bytes)
            self._cache_bytes += payload_bytes
            while (
                len(self._cache) > self._cache_items
                or self._cache_bytes > self._cache_bytes_limit
            ):
                _evicted_index, (_evicted_value, evicted_bytes) = (
                    self._cache.popitem(last=False)
                )
                self._cache_bytes -= evicted_bytes
        return value


def is_xlsx_path(path: Path, content_type: str = "") -> bool:
    normalized_type = str(content_type or "").casefold()
    return path.suffix.casefold() == ".xlsx" or "spreadsheetml.sheet" in normalized_type


def _safe_archive_member_name(value: str) -> str:
    raw = str(value).replace("\\", "/")
    if raw.startswith("/"):
        raise XlsxExtractionError(f"unsafe XLSX member path: {value!r}")
    normalized = posixpath.normpath(raw)
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized == "."
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise XlsxExtractionError(f"unsafe XLSX member path: {value!r}")
    return normalized


def _validate_members(
    archive: ZipFile,
    *,
    max_uncompressed_bytes: int,
    max_member_bytes: int,
    max_compression_ratio: int,
    max_members: int,
) -> dict[str, ZipInfo]:
    infos = archive.infolist()
    if not infos or len(infos) > max_members:
        raise XlsxExtractionError("XLSX member count outside bounded contract")
    members: dict[str, ZipInfo] = {}
    total = 0
    for info in infos:
        name = _safe_archive_member_name(info.filename)
        if name in members:
            raise XlsxExtractionError(f"duplicate XLSX member path: {name}")
        if info.is_dir():
            members[name] = info
            continue
        size = int(info.file_size)
        compressed = int(info.compress_size)
        if size < 0 or size > max_member_bytes:
            raise XlsxExtractionError("XLSX member bytes exceed bounded contract")
        total += size
        if total > max_uncompressed_bytes:
            raise XlsxExtractionError("XLSX uncompressed bytes exceed bounded contract")
        if size and (compressed <= 0 or size > compressed * max_compression_ratio):
            raise XlsxExtractionError("XLSX compression ratio exceeds bounded contract")
        members[name] = info
    if _WORKBOOK_PATH not in members or _WORKBOOK_RELS_PATH not in members:
        raise XlsxExtractionError("XLSX workbook metadata is incomplete")
    return members


def _stream_start_elements(
    handle: BinaryIO,
    *,
    expanded_name: str,
    callback: Callable[[dict[str, str]], None],
    max_depth: int,
    max_elements: int,
) -> None:
    """Read selected XML start tags without materializing an Element tree."""

    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    depth = 0
    elements = 0

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal depth, elements
        depth += 1
        elements += 1
        if depth > max_depth:
            raise XlsxExtractionError("XLSX XML depth exceeds bounded contract")
        if elements > max_elements:
            raise XlsxExtractionError("XLSX XML element count exceeds bounded contract")
        if name == expanded_name:
            callback(attributes)

    def end_element(_name: str) -> None:
        nonlocal depth
        if depth < 1:
            raise XlsxExtractionError("XLSX XML depth drifted")
        depth -= 1

    def reject_doctype(
        _name: str,
        _system_id: str | None,
        _public_id: str | None,
        _has_internal_subset: bool,
    ) -> None:
        raise XlsxExtractionError("XLSX metadata must not contain a doctype")

    def reject_external_entity(
        _context: str,
        _base: str,
        _system_id: str,
        _public_id: str,
    ) -> int:
        raise XlsxExtractionError("XLSX metadata external entities are forbidden")

    def reject_entity_declaration(*_args: object) -> None:
        raise XlsxExtractionError("XLSX XML entity declarations are forbidden")

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.EntityDeclHandler = reject_entity_declaration
    try:
        while True:
            chunk = handle.read(_XML_READ_CHUNK_BYTES)
            if not chunk:
                parser.Parse(b"", True)
                break
            parser.Parse(chunk, False)
    except expat.ExpatError as exc:
        raise XlsxExtractionError("invalid XLSX metadata XML") from exc
    if depth != 0:
        raise XlsxExtractionError("XLSX XML depth did not return to zero")


def _expat_to_element_name(name: str) -> str:
    if "}" not in name:
        return name
    namespace, local_name = name.split("}", 1)
    return f"{{{namespace}}}{local_name}"


def _element_to_expat_name(name: str) -> str:
    if name.startswith("{") and "}" in name:
        namespace, local_name = name[1:].split("}", 1)
        return f"{namespace}}}{local_name}"
    return name


def _iter_group_elements(
    handle: BinaryIO,
    *,
    tag: str,
    direct_child_tag: str | None = None,
    max_direct_children: int | None = None,
    max_depth: int,
    max_elements: int,
    max_group_text_chars: int,
) -> Iterator[Element]:
    """Yield bounded row-like trees while never retaining surrounding XML."""

    if (direct_child_tag is None) != (max_direct_children is None):
        raise ValueError("direct-child tag and bound must be provided together")
    if min(max_depth, max_elements, max_group_text_chars) < 1:
        raise ValueError("XML parser bounds must be positive")
    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    expanded_tag = _element_to_expat_name(tag)
    expanded_direct_child_tag = (
        _element_to_expat_name(direct_child_tag)
        if direct_child_tag
        else direct_child_tag
    )
    depth = 0
    elements = 0
    active_depth = 0
    active_builder: TreeBuilder | None = None
    direct_children = 0
    group_text_chars = 0
    completed: list[Element] = []

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal depth, elements, active_depth, active_builder
        nonlocal direct_children, group_text_chars
        depth += 1
        elements += 1
        if depth > max_depth:
            raise XlsxExtractionError("XLSX XML depth exceeds bounded contract")
        if elements > max_elements:
            raise XlsxExtractionError("XLSX XML element count exceeds bounded contract")
        if name == expanded_tag:
            if active_builder is not None:
                raise XlsxExtractionError("nested XLSX row-like elements")
            active_depth = depth
            active_builder = TreeBuilder()
            direct_children = 0
            group_text_chars = 0
        if active_builder is None:
            return
        if (
            depth == active_depth + 1
            and name == expanded_direct_child_tag
        ):
            direct_children += 1
            if direct_children > int(max_direct_children or 0):
                raise XlsxExtractionError(
                    "XLSX cells per row exceed bounded contract"
                )
        active_builder.start(
            _expat_to_element_name(name),
            {
                _expat_to_element_name(key): value
                for key, value in attributes.items()
            },
        )

    def end_element(name: str) -> None:
        nonlocal depth, active_depth, active_builder
        if depth < 1:
            raise XlsxExtractionError("XLSX XML depth drifted")
        if active_builder is not None:
            active_builder.end(_expat_to_element_name(name))
            if depth == active_depth:
                completed.append(active_builder.close())
                active_builder = None
                active_depth = 0
        depth -= 1

    def characters(value: str) -> None:
        nonlocal group_text_chars
        if active_builder is None:
            return
        group_text_chars += len(value)
        if group_text_chars > max_group_text_chars:
            raise XlsxExtractionError(
                "XLSX XML group text exceeds bounded contract"
            )
        active_builder.data(value)

    def reject_doctype(
        _name: str,
        _system_id: str | None,
        _public_id: str | None,
        _has_internal_subset: bool,
    ) -> None:
        raise XlsxExtractionError("XLSX XML must not contain a doctype")

    def reject_external_entity(*_args: object) -> int:
        raise XlsxExtractionError("XLSX XML external entities are forbidden")

    def reject_entity_declaration(*_args: object) -> None:
        raise XlsxExtractionError("XLSX XML entity declarations are forbidden")

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = characters
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.EntityDeclHandler = reject_entity_declaration
    try:
        while True:
            chunk = handle.read(_XML_READ_CHUNK_BYTES)
            parser.Parse(chunk, not chunk)
            while completed:
                yield completed.pop(0)
            if not chunk:
                break
    except expat.ExpatError as exc:
        raise XlsxExtractionError("invalid XLSX worksheet XML") from exc
    if depth != 0 or active_builder is not None:
        raise XlsxExtractionError("XLSX XML parser ended with active elements")


def _worksheets(
    archive: ZipFile,
    members: dict[str, ZipInfo],
    *,
    max_worksheets: int,
    max_xml_depth: int,
    max_xml_elements: int,
) -> list[_Sheet]:
    relationships: dict[str, tuple[str, str]] = {}

    def add_relationship(attributes: dict[str, str]) -> None:
        relation_id = str(attributes.get("Id") or "")
        target = str(attributes.get("Target") or "")
        relation_type = str(attributes.get("Type") or "")
        if relation_id:
            if relation_id in relationships:
                raise XlsxExtractionError("duplicate XLSX workbook relationship id")
            if len(relationships) >= len(members):
                raise XlsxExtractionError(
                    "XLSX workbook relationship count exceeds archive bound"
                )
            relationships[relation_id] = (target, relation_type)

    with archive.open(_WORKBOOK_RELS_PATH) as handle:
        _stream_start_elements(
            handle,
            expanded_name=_RELATIONSHIP_EXPAT_NAME,
            callback=add_relationship,
            max_depth=max_xml_depth,
            max_elements=max_xml_elements,
        )

    sheets: list[_Sheet] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()

    def add_sheet(attributes: dict[str, str]) -> None:
        name = str(attributes.get("name") or "")
        relation_id = str(attributes.get(_DOCUMENT_REL_ID_EXPAT_NAME) or "")
        target_and_type = relationships.get(relation_id)
        if not name or target_and_type is None:
            raise XlsxExtractionError("XLSX worksheet metadata is incomplete")
        target, relation_type = target_and_type
        if not relation_type.endswith(_WORKSHEET_REL_TYPE_SUFFIX):
            return
        normalized_path = _safe_archive_member_name(
            posixpath.join("xl", target)
            if not target.startswith("/")
            else target.lstrip("/")
        )
        if normalized_path not in members:
            raise XlsxExtractionError(
                f"XLSX worksheet member is missing: {normalized_path}"
            )
        if name in seen_names or normalized_path in seen_paths:
            raise XlsxExtractionError("duplicate XLSX worksheet name or target")
        if len(sheets) >= max_worksheets:
            raise XlsxExtractionError("XLSX worksheet count exceeds bounded contract")
        seen_names.add(name)
        seen_paths.add(normalized_path)
        sheets.append(_Sheet(name=name, path=normalized_path))

    with archive.open(_WORKBOOK_PATH) as handle:
        _stream_start_elements(
            handle,
            expanded_name=_SHEET_EXPAT_NAME,
            callback=add_sheet,
            max_depth=max_xml_depth,
            max_elements=max_xml_elements,
        )
    if not sheets:
        raise XlsxExtractionError("XLSX contains no worksheets")
    return sheets


def _shared_strings(
    archive: ZipFile,
    members: dict[str, ZipInfo],
    *,
    max_shared_strings: int,
    max_value_chars: int,
    cache_items: int,
    cache_bytes: int,
    max_xml_depth: int,
    max_xml_elements: int,
) -> _SharedStringTable:
    values = _SharedStringTable(cache_items=cache_items, cache_bytes=cache_bytes)
    if _SHARED_STRINGS_PATH not in members:
        return values
    try:
        with archive.open(_SHARED_STRINGS_PATH) as handle:
            for element in _iter_group_elements(
                handle,
                tag=_MAIN_NS + "si",
                max_depth=max_xml_depth,
                max_elements=max_xml_elements,
                max_group_text_chars=max_value_chars,
            ):
                if len(values) >= max_shared_strings:
                    raise XlsxExtractionError(
                        "XLSX shared-string count exceeds bounded contract"
                    )
                value, phonetic_annotations = _public_string_parts(element)
                if len(value) + len(phonetic_annotations) > max_value_chars:
                    raise XlsxExtractionError(
                        "XLSX shared-string value exceeds text bound"
                    )
                values.append(
                    _SharedStringValue(
                        value=value,
                        phonetic_annotations=phonetic_annotations,
                    )
                )
    except Exception:
        values.close()
        raise
    return values


def _public_string_parts(container: Element) -> tuple[str, str]:
    """Return displayed text plus typed public phonetic annotations."""

    parts: list[str] = []
    phonetic: list[dict[str, object]] = []
    for child in container:
        if child.tag == _MAIN_NS + "t":
            parts.append(child.text or "")
        elif child.tag == _MAIN_NS + "r":
            for run_child in child:
                if run_child.tag == _MAIN_NS + "t":
                    parts.append(run_child.text or "")
        elif child.tag == _MAIN_NS + "rPh":
            phonetic.append(
                {
                    "text": "".join(
                        node.text or ""
                        for node in child.iter(_MAIN_NS + "t")
                    ),
                    "attributes": sorted(
                        (str(key), str(value))
                        for key, value in child.attrib.items()
                    ),
                }
            )
    return (
        "".join(parts),
        (
            json.dumps(phonetic, ensure_ascii=False, separators=(",", ":"))
            if phonetic
            else ""
        ),
    )


def _column_index(column_letters: str) -> int:
    index = 0
    for character in column_letters:
        index = index * 26 + (ord(character) - ord("A") + 1)
    return index


def _cell_coordinate(
    raw_reference: str,
    *,
    expected_row_number: int,
    max_column_index: int,
) -> tuple[str, int]:
    reference = raw_reference.upper()
    if not _CELL_REF_RE.fullmatch(reference):
        raise XlsxExtractionError(f"invalid XLSX cell reference: {reference!r}")
    match = re.fullmatch(r"(?P<column>[A-Z]+)(?P<row>[1-9][0-9]*)", reference)
    if match is None:
        raise XlsxExtractionError(f"invalid XLSX cell reference: {reference!r}")
    coordinate_row = int(match.group("row"))
    column_index = _column_index(match.group("column"))
    if coordinate_row != expected_row_number:
        raise XlsxExtractionError(
            "XLSX cell reference row does not match containing row"
        )
    if column_index < 1 or column_index > max_column_index:
        raise XlsxExtractionError("XLSX cell column exceeds bounded contract")
    return reference, column_index


def _cell_payload(
    cell: Element,
    shared_strings: _SharedStringTable,
    *,
    expected_row_number: int,
    max_column_index: int,
) -> tuple[tuple[str, ...], int]:
    reference, column_index = _cell_coordinate(
        str(cell.get("r") or ""),
        expected_row_number=expected_row_number,
        max_column_index=max_column_index,
    )
    cell_type = str(cell.get("t") or "n")
    formula_node = cell.find(_MAIN_NS + "f")
    formula = ""
    if formula_node is not None:
        formula = json.dumps(
            {
                "text": formula_node.text or "",
                "attributes": sorted(formula_node.attrib.items()),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if cell_type == "inlineStr":
        inline_string = cell.find(_MAIN_NS + "is")
        value, phonetic_annotations = (
            _public_string_parts(inline_string)
            if inline_string is not None
            else ("", "")
        )
    else:
        phonetic_annotations = ""
        value_node = cell.find(_MAIN_NS + "v")
        raw_value = (
            value_node.text if value_node is not None and value_node.text is not None else ""
        )
        if cell_type == "s" and raw_value:
            try:
                index = int(raw_value)
            except ValueError as exc:
                raise XlsxExtractionError("invalid XLSX shared-string index") from exc
            if index < 0 or index >= len(shared_strings):
                raise XlsxExtractionError("XLSX shared-string index outside table")
            shared_value = shared_strings.get(index)
            value = shared_value.value
            phonetic_annotations = shared_value.phonetic_annotations
        else:
            value = raw_value
    payload: tuple[str, ...] = (reference, cell_type, value, formula)
    if phonetic_annotations:
        payload += (phonetic_annotations,)
    return payload, column_index


def _row_text(
    sheet_name: str, row_number: int, cells: list[tuple[str, ...]]
) -> str:
    return json.dumps(
        {"sheet": sheet_name, "row": row_number, "cells": cells},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def extract_xlsx_path(
    path: Path,
    *,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    retain_text: bool = True,
    retain_rows: bool = True,
    row_callback: XlsxRowCallback | None = None,
    max_workbook_bytes: int = DEFAULT_MAX_WORKBOOK_BYTES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_compression_ratio: int = DEFAULT_MAX_COMPRESSION_RATIO,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_worksheets: int = DEFAULT_MAX_WORKSHEETS,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_cells: int = DEFAULT_MAX_CELLS,
    max_cells_per_row: int = DEFAULT_MAX_CELLS_PER_ROW,
    max_row_number: int = DEFAULT_MAX_ROW_NUMBER,
    max_column_index: int = DEFAULT_MAX_COLUMN_INDEX,
    max_shared_strings: int = DEFAULT_MAX_SHARED_STRINGS,
    shared_string_cache_items: int = DEFAULT_SHARED_STRING_CACHE_ITEMS,
    shared_string_cache_bytes: int = DEFAULT_SHARED_STRING_CACHE_BYTES,
    max_xml_depth: int = DEFAULT_MAX_XML_DEPTH,
    max_xml_elements: int = DEFAULT_MAX_XML_ELEMENTS,
) -> XlsxExtraction:
    """Extract all observed cell values/formulas with deterministic row coordinates.

    ``row_callback`` receives each :class:`XlsxTextRow` plus its exact canonical
    fragment. Every fragment after the first starts with the canonical newline,
    so writing fragments in callback order reproduces ``text`` byte-for-byte.
    Callers can set both retention flags false for bounded streaming operation;
    the canonical SHA-256 is still returned.
    """

    bounded_values = (
        max_text_chars,
        max_workbook_bytes,
        max_uncompressed_bytes,
        max_member_bytes,
        max_compression_ratio,
        max_members,
        max_worksheets,
        max_rows,
        max_cells,
        max_cells_per_row,
        max_row_number,
        max_column_index,
        max_shared_strings,
        shared_string_cache_items,
        shared_string_cache_bytes,
        max_xml_depth,
        max_xml_elements,
    )
    if any(int(value) < 1 for value in bounded_values):
        raise ValueError("XLSX extraction bounds must be positive")
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > max_workbook_bytes:
        raise XlsxExtractionError("XLSX workbook bytes exceed bounded contract")

    text_parts: list[str] = []
    text_rows: list[XlsxTextRow] = []
    text_chars = 0
    worksheet_rows = 0
    nonempty_rows = 0
    nonempty_cells = 0
    formula_cells = 0
    canonical_hasher = hashlib.sha256()
    try:
        with ZipFile(path) as archive:
            members = _validate_members(
                archive,
                max_uncompressed_bytes=max_uncompressed_bytes,
                max_member_bytes=max_member_bytes,
                max_compression_ratio=max_compression_ratio,
                max_members=max_members,
            )
            sheets = _worksheets(
                archive,
                members,
                max_worksheets=max_worksheets,
                max_xml_depth=max_xml_depth,
                max_xml_elements=max_xml_elements,
            )
            shared_strings = _shared_strings(
                archive,
                members,
                max_shared_strings=max_shared_strings,
                max_value_chars=max_text_chars,
                cache_items=shared_string_cache_items,
                cache_bytes=shared_string_cache_bytes,
                max_xml_depth=max_xml_depth,
                max_xml_elements=max_xml_elements,
            )
            with shared_strings:
                for sheet_index, sheet in enumerate(sheets, start=1):
                    previous_row_number = 0
                    with archive.open(sheet.path) as handle:
                        for element in _iter_group_elements(
                            handle,
                            tag=_MAIN_NS + "row",
                            direct_child_tag=_MAIN_NS + "c",
                            max_direct_children=max_cells_per_row,
                            max_depth=max_xml_depth,
                            max_elements=max_xml_elements,
                            max_group_text_chars=max_text_chars,
                        ):
                            try:
                                row_number = int(element.get("r") or 0)
                            except ValueError as exc:
                                raise XlsxExtractionError(
                                    "invalid XLSX worksheet row number"
                                ) from exc
                            if (
                                row_number < 1
                                or row_number > max_row_number
                                or row_number <= previous_row_number
                            ):
                                raise XlsxExtractionError(
                                    "XLSX worksheet rows are not strictly ordered"
                                )
                            previous_row_number = row_number
                            worksheet_rows += 1
                            if worksheet_rows > max_rows:
                                raise XlsxExtractionError(
                                    "XLSX worksheet row count exceeds bounded contract"
                                )

                            cells: list[tuple[str, ...]] = []
                            seen_references: set[str] = set()
                            row_cell_elements = 0
                            previous_column_index = 0
                            for cell_element in element:
                                if cell_element.tag != _MAIN_NS + "c":
                                    continue
                                row_cell_elements += 1
                                if row_cell_elements > max_cells_per_row:
                                    raise XlsxExtractionError(
                                        "XLSX cells per row exceed bounded contract"
                                    )
                                cell, column_index = _cell_payload(
                                    cell_element,
                                    shared_strings,
                                    expected_row_number=row_number,
                                    max_column_index=max_column_index,
                                )
                                if cell[0] in seen_references:
                                    raise XlsxExtractionError(
                                        "duplicate XLSX cell reference in row"
                                    )
                                seen_references.add(cell[0])
                                if column_index <= previous_column_index:
                                    raise XlsxExtractionError(
                                        "XLSX cell columns are not strictly ordered"
                                    )
                                previous_column_index = column_index
                                if (
                                    cell[2] == ""
                                    and cell[3] == ""
                                    and len(cell) == 4
                                ):
                                    continue
                                if nonempty_cells + len(cells) + 1 > max_cells:
                                    raise XlsxExtractionError(
                                        "XLSX non-empty cell count exceeds bounded contract"
                                    )
                                cells.append(cell)
                            if not cells:
                                continue

                            row_text = _row_text(sheet.name, row_number, cells)
                            canonical_fragment = (
                                ("\n" if nonempty_rows else "") + row_text
                            )
                            row_start = text_chars
                            next_text_chars = text_chars + len(canonical_fragment)
                            if next_text_chars > max_text_chars:
                                raise XlsxExtractionError(
                                    "XLSX extracted text exceeds max_text_chars; refusing truncation"
                                )
                            row = XlsxTextRow(
                                sheet_index=sheet_index,
                                sheet_name=sheet.name,
                                row_number=row_number,
                                text_start_char=row_start,
                                text_end_char=next_text_chars,
                            )
                            canonical_hasher.update(canonical_fragment.encode("utf-8"))
                            if row_callback is not None:
                                row_callback(row, canonical_fragment)
                            if retain_text:
                                text_parts.append(canonical_fragment)
                            if retain_rows:
                                text_rows.append(row)
                            text_chars = next_text_chars
                            nonempty_rows += 1
                            nonempty_cells += len(cells)
                            formula_cells += sum(bool(cell[3]) for cell in cells)
    except BadZipFile as exc:
        raise XlsxExtractionError("invalid XLSX ZIP archive") from exc

    text = "".join(text_parts) if retain_text else ""
    if retain_text and len(text) != text_chars:
        raise XlsxExtractionError("XLSX deterministic text length drifted")
    return XlsxExtraction(
        text=text,
        text_chars=text_chars,
        canonical_text_sha256=canonical_hasher.hexdigest(),
        worksheet_count=len(sheets),
        worksheet_rows=worksheet_rows,
        nonempty_worksheet_rows=nonempty_rows,
        nonempty_cells=nonempty_cells,
        formula_cells=formula_cells,
        rows=tuple(text_rows),
    )


__all__ = [
    "DEFAULT_MAX_CELLS",
    "DEFAULT_MAX_CELLS_PER_ROW",
    "DEFAULT_MAX_COLUMN_INDEX",
    "DEFAULT_MAX_COMPRESSION_RATIO",
    "DEFAULT_MAX_MEMBER_BYTES",
    "DEFAULT_MAX_MEMBERS",
    "DEFAULT_MAX_ROWS",
    "DEFAULT_MAX_ROW_NUMBER",
    "DEFAULT_MAX_SHARED_STRINGS",
    "DEFAULT_MAX_UNCOMPRESSED_BYTES",
    "DEFAULT_MAX_TEXT_CHARS",
    "DEFAULT_MAX_WORKBOOK_BYTES",
    "DEFAULT_MAX_WORKSHEETS",
    "DEFAULT_MAX_XML_DEPTH",
    "DEFAULT_MAX_XML_ELEMENTS",
    "DEFAULT_SHARED_STRING_CACHE_BYTES",
    "DEFAULT_SHARED_STRING_CACHE_ITEMS",
    "XLSX_CONTENT_TYPE",
    "XlsxExtraction",
    "XlsxExtractionError",
    "XlsxRowCallback",
    "XlsxTextRow",
    "extract_xlsx_path",
    "is_xlsx_path",
]
