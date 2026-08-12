"""Bounded parser for official Infoelectoral elected-official workbooks."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree.ElementTree import iterparse
from zipfile import BadZipFile, ZipFile

from publicdata_core.util import normalize_ws

from .config import INFOELECTORAL_DATASET_BASE

SOURCE_ID = "infoelectoral_elected_officials"
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
DEFAULT_MAX_WORKBOOK_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_ROWS = 1_000_000
DEFAULT_MAX_MEMBERS = 128
_SHEET_PATH = "xl/worksheets/sheet1.xml"
_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_CELL_REF = re.compile(r"^([A-Z]+)[1-9][0-9]*$")


@dataclass(frozen=True)
class ElectedWorkbookSpec:
    chamber: str
    role_title: str
    institution_name: str
    source_url: str


@dataclass(frozen=True)
class ElectedOfficialRecord:
    elected_official_id: str
    source_record_id: str
    election_date: str
    election_code: str
    chamber: str
    role_title: str
    institution_name: str
    province_code: str
    province_name: str
    territory_code: str
    district: str | None
    constituency: str | None
    full_name: str
    candidacy_name: str
    candidacy_acronym: str | None
    votes: int | None
    source_url: str
    source_content_sha256: str
    source_row_number: int

    def raw_payload(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True, sort_keys=True)


WORKBOOKS: tuple[ElectedWorkbookSpec, ...] = (
    ElectedWorkbookSpec(
        chamber="congreso",
        role_title="Diputado electo",
        institution_name="Congreso de los Diputados",
        source_url=(
            INFOELECTORAL_DATASET_BASE
            + "resultados_electorales/Elecciones-Congreso-cargos-electos.xlsx"
        ),
    ),
    ElectedWorkbookSpec(
        chamber="senado",
        role_title="Senador electo",
        institution_name="Senado de España",
        source_url=(
            INFOELECTORAL_DATASET_BASE
            + "resultados_electorales/Elecciones-Senado-cargos-electos.xlsx"
        ),
    ),
)


def _normalized_header(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _column_index(cell_reference: str) -> int:
    match = _CELL_REF.fullmatch(str(cell_reference or ""))
    if match is None:
        raise RuntimeError(f"invalid XLSX cell reference: {cell_reference!r}")
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - 64
    return index - 1


def _xlsx_members(archive: ZipFile, *, max_uncompressed_bytes: int) -> None:
    infos = archive.infolist()
    if not infos or len(infos) > DEFAULT_MAX_MEMBERS:
        raise RuntimeError("XLSX member count outside bounded contract")
    names: set[str] = set()
    total = 0
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or info.filename in names:
            raise RuntimeError("unsafe or duplicate XLSX member path")
        names.add(info.filename)
        total += int(info.file_size)
        if total > int(max_uncompressed_bytes):
            raise RuntimeError("XLSX uncompressed bytes exceed bounded contract")
    if _SHEET_PATH not in names:
        raise RuntimeError(f"XLSX missing required worksheet: {_SHEET_PATH}")


def _shared_strings(archive: ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    values: list[str] = []
    with archive.open(path) as handle:
        for _event, element in iterparse(handle, events=("end",)):
            if element.tag == _MAIN_NS + "si":
                values.append(
                    "".join(
                        node.text or ""
                        for node in element.findall(".//" + _MAIN_NS + "t")
                    )
                )
                element.clear()
    return values


def _cell_value(cell: Any, shared_strings: list[str]) -> str:
    cell_type = str(cell.get("t") or "")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.findall(".//" + _MAIN_NS + "t")
        )
    value = cell.find(_MAIN_NS + "v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw:
        index = int(raw)
        if index < 0 or index >= len(shared_strings):
            raise RuntimeError("XLSX shared-string index outside table")
        return shared_strings[index]
    return raw


def _iter_rows(archive: ZipFile) -> Iterator[tuple[int, dict[int, str]]]:
    shared_strings = _shared_strings(archive)
    with archive.open(_SHEET_PATH) as handle:
        for _event, element in iterparse(handle, events=("end",)):
            if element.tag != _MAIN_NS + "row":
                continue
            row_number = int(element.get("r") or 0)
            values: dict[int, str] = {}
            for cell in element.findall(_MAIN_NS + "c"):
                values[_column_index(str(cell.get("r") or ""))] = _cell_value(
                    cell, shared_strings
                )
            yield row_number, values
            element.clear()


def _excel_date(raw: str) -> str:
    try:
        serial = int(float(str(raw).strip()))
    except ValueError as exc:
        raise RuntimeError(f"invalid Excel election date: {raw!r}") from exc
    if serial < 1 or serial > 1_000_000:
        raise RuntimeError(f"Excel election date outside contract: {serial}")
    return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()


def _optional_integer(raw: str | None) -> int | None:
    token = normalize_ws(str(raw or ""))
    if not token:
        return None
    try:
        value = int(float(token))
    except ValueError as exc:
        raise RuntimeError(f"invalid integer in official workbook: {raw!r}") from exc
    if value < 0:
        raise RuntimeError("official workbook integer cannot be negative")
    return value


def _required_columns(header: dict[int, str], spec: ElectedWorkbookSpec) -> dict[str, int]:
    by_name = {_normalized_header(value): index for index, value in header.items()}
    aliases = {
        "election_date": ("fecha",),
        "election_code": ("codigo eleccion",),
        "chamber": ("tipo eleccion",),
        "province_code": ("codigo provincia",),
        "province_name": ("provincia",),
        "full_name": ("cargos electos",),
        "candidacy_name": ("candidatura",),
        "candidacy_acronym": ("siglas candidatura",),
    }
    if spec.chamber == "senado":
        aliases.update(
            {
                "district": ("distrito electoral",),
                "constituency": ("circunscripcion",),
                "votes": ("votos",),
            }
        )
    columns: dict[str, int] = {}
    for field, names in aliases.items():
        index = next((by_name[name] for name in names if name in by_name), None)
        if index is None:
            raise RuntimeError(
                f"official {spec.chamber} workbook missing column: {field}"
            )
        columns[field] = index
    return columns


def _record(
    values: dict[int, str],
    *,
    columns: dict[str, int],
    spec: ElectedWorkbookSpec,
    source_content_sha256: str,
    row_number: int,
) -> ElectedOfficialRecord:
    def get(field: str) -> str:
        return normalize_ws(values.get(columns[field], ""))

    election_date = _excel_date(get("election_date"))
    election_code = get("election_code")
    workbook_chamber = _normalized_header(get("chamber"))
    if workbook_chamber != spec.chamber:
        raise RuntimeError(
            f"workbook chamber mismatch: expected={spec.chamber} actual={workbook_chamber}"
        )
    province_code = get("province_code")
    province_name = get("province_name")
    full_name = get("full_name")
    candidacy_name = get("candidacy_name")
    if not all(
        (election_code, province_code, province_name, full_name, candidacy_name)
    ):
        raise RuntimeError(f"official workbook row {row_number} has required blanks")
    district = (get("district") or None) if "district" in columns else None
    constituency = (
        (get("constituency") or None) if "constituency" in columns else None
    )
    acronym = get("candidacy_acronym") or None
    votes = (
        _optional_integer(values.get(columns["votes"]))
        if "votes" in columns
        else None
    )
    identity_payload = "\n".join(
        (
            spec.chamber,
            election_date,
            election_code,
            province_code,
            district or "",
            constituency or "",
            _normalized_header(full_name),
            _normalized_header(candidacy_name),
            _normalized_header(acronym or ""),
        )
    )
    digest = hashlib.sha256(identity_payload.encode("utf-8")).hexdigest()
    source_record_id = f"elected:{spec.chamber}:{election_date}:{digest}"
    try:
        territory_code = f"ES-PROV-{int(province_code):02d}"
    except ValueError as exc:
        raise RuntimeError(
            f"invalid province code in official workbook row {row_number}: "
            f"{province_code!r}"
        ) from exc
    return ElectedOfficialRecord(
        elected_official_id=source_record_id,
        source_record_id=source_record_id,
        election_date=election_date,
        election_code=election_code,
        chamber=spec.chamber,
        role_title=spec.role_title,
        institution_name=spec.institution_name,
        province_code=province_code,
        province_name=province_name,
        territory_code=territory_code,
        district=district,
        constituency=constituency,
        full_name=full_name,
        candidacy_name=candidacy_name,
        candidacy_acronym=acronym,
        votes=votes,
        source_url=spec.source_url,
        source_content_sha256=source_content_sha256,
        source_row_number=row_number,
    )


def iter_elected_officials(
    path: Path,
    *,
    spec: ElectedWorkbookSpec,
    source_content_sha256: str,
    max_workbook_bytes: int = DEFAULT_MAX_WORKBOOK_BYTES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> Iterator[ElectedOfficialRecord]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > int(max_workbook_bytes):
        raise RuntimeError("XLSX exceeds max_workbook_bytes")
    try:
        with ZipFile(path) as archive:
            _xlsx_members(
                archive, max_uncompressed_bytes=int(max_uncompressed_bytes)
            )
            header: dict[int, str] | None = None
            columns: dict[str, int] | None = None
            yielded = 0
            seen_ids: set[str] = set()
            for row_number, values in _iter_rows(archive):
                normalized = {
                    _normalized_header(value) for value in values.values() if value
                }
                if header is None and "cargos electos" in normalized:
                    header = values
                    columns = _required_columns(header, spec)
                    continue
                if header is None or columns is None:
                    continue
                if not any(normalize_ws(value) for value in values.values()):
                    continue
                record = _record(
                    values,
                    columns=columns,
                    spec=spec,
                    source_content_sha256=source_content_sha256,
                    row_number=row_number,
                )
                if record.source_record_id in seen_ids:
                    raise RuntimeError(
                        f"duplicate elected-official identity in workbook: {record.source_record_id}"
                    )
                seen_ids.add(record.source_record_id)
                yielded += 1
                if yielded > int(max_rows):
                    raise RuntimeError("official workbook exceeds max_rows")
                yield record
            if header is None:
                raise RuntimeError("official workbook header not found")
            if yielded == 0:
                raise RuntimeError("official workbook contains no elected officials")
    except BadZipFile as exc:
        raise RuntimeError("official workbook is not a valid XLSX archive") from exc


__all__ = [
    "DEFAULT_MAX_ROWS",
    "DEFAULT_MAX_UNCOMPRESSED_BYTES",
    "DEFAULT_MAX_WORKBOOK_BYTES",
    "ElectedOfficialRecord",
    "ElectedWorkbookSpec",
    "SOURCE_ID",
    "WORKBOOKS",
    "XLSX_CONTENT_TYPE",
    "iter_elected_officials",
]
