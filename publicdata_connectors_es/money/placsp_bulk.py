"""Bounded archive and CODICE Atom parsing for official PLACSP bulk data."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from publicdata_core.util import normalize_ws, stable_json

DEFAULT_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_ARCHIVE_MEMBERS = 2_000
DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 250.0
DEFAULT_MAX_RECORDS_PER_MEMBER = 2_000
DEFAULT_MAX_DOCUMENTS_PER_RECORD = 10_000


@dataclass(frozen=True)
class PlacspArchiveMember:
    member_name: str
    crc32: int
    compressed_bytes: int
    uncompressed_bytes: int


@dataclass(frozen=True)
class PlacspArchiveInspection:
    archive_bytes: int
    members: tuple[PlacspArchiveMember, ...]
    uncompressed_bytes: int


@dataclass(frozen=True)
class PlacspAtomRecord:
    source_record_id: str
    stable_contract_id: str
    entry_content_sha256: str
    tombstone: bool
    record: dict[str, Any]
    awards: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in node if _local_name(child.tag) == name]


def _child(node: ET.Element | None, name: str) -> ET.Element | None:
    values = _children(node, name)
    return values[0] if values else None


def _path(node: ET.Element | None, *names: str) -> ET.Element | None:
    current = node
    for name in names:
        current = _child(current, name)
        if current is None:
            return None
    return current


def _text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = normalize_ws(" ".join(node.itertext()))
    return value or None


def _path_text(node: ET.Element | None, *names: str) -> str | None:
    return _text(_path(node, *names))


def _decimal_text(node: ET.Element | None) -> tuple[str | None, str | None]:
    raw = _text(node)
    if raw is None:
        return None, None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise RuntimeError(f"invalid CODICE decimal: {raw!r}") from exc
    if not value.is_finite() or value < 0:
        raise RuntimeError(f"invalid CODICE monetary amount: {raw!r}")
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0", normalize_ws(str(node.attrib.get("currencyID") or "")) or None


def _safe_member_name(raw_name: str) -> str:
    normalized = raw_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise RuntimeError(f"unsafe PLACSP archive member path: {raw_name!r}")
    if path.suffix.lower() not in {".atom", ".xml"}:
        raise RuntimeError(f"unexpected PLACSP archive member: {raw_name!r}")
    return normalized


def inspect_placsp_archive(
    archive_path: Path,
    *,
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    max_members: int = DEFAULT_MAX_ARCHIVE_MEMBERS,
    max_total_uncompressed_bytes: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> PlacspArchiveInspection:
    """Validate one ZIP without extracting any member."""

    path = Path(archive_path)
    archive_bytes = path.stat().st_size
    if archive_bytes < 1 or archive_bytes > int(max_archive_bytes):
        raise RuntimeError(
            f"PLACSP archive bytes outside bounds: bytes={archive_bytes} max={int(max_archive_bytes)}"
        )
    if not zipfile.is_zipfile(path):
        raise RuntimeError("PLACSP payload is not a ZIP archive")

    members: list[PlacspArchiveMember] = []
    seen: set[str] = set()
    total_uncompressed = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member_name = _safe_member_name(info.filename)
            if member_name in seen:
                raise RuntimeError(f"duplicate PLACSP archive member: {member_name}")
            seen.add(member_name)
            if info.flag_bits & 0x1:
                raise RuntimeError(f"encrypted PLACSP archive member: {member_name}")
            if info.file_size < 1 or info.file_size > int(max_member_bytes):
                raise RuntimeError(
                    "PLACSP member bytes outside bounds: "
                    f"member={member_name} bytes={info.file_size} max={int(max_member_bytes)}"
                )
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > float(max_compression_ratio):
                raise RuntimeError(
                    "PLACSP member compression ratio exceeds cap: "
                    f"member={member_name} ratio={ratio:.3f} max={float(max_compression_ratio):.3f}"
                )
            total_uncompressed += info.file_size
            if total_uncompressed > int(max_total_uncompressed_bytes):
                raise RuntimeError(
                    "PLACSP archive uncompressed bytes exceed cap: "
                    f"received>{int(max_total_uncompressed_bytes)}"
                )
            members.append(
                PlacspArchiveMember(
                    member_name=member_name,
                    crc32=int(info.CRC),
                    compressed_bytes=int(info.compress_size),
                    uncompressed_bytes=int(info.file_size),
                )
            )
            if len(members) > int(max_members):
                raise RuntimeError(
                    f"PLACSP archive members exceed cap: received>{int(max_members)}"
                )
    if not members:
        raise RuntimeError("PLACSP archive has no Atom/XML members")
    return PlacspArchiveInspection(
        archive_bytes=archive_bytes,
        members=tuple(members),
        uncompressed_bytes=total_uncompressed,
    )


def _entry_link(entry: ET.Element) -> str | None:
    links = _children(entry, "link")
    preferred = next(
        (
            link
            for link in links
            if normalize_ws(str(link.attrib.get("rel") or "")).lower()
            in {"", "alternate"}
        ),
        links[0] if links else None,
    )
    if preferred is None:
        return None
    return normalize_ws(str(preferred.attrib.get("href") or "")) or None


def _party_identity(party: ET.Element | None) -> tuple[str | None, str | None, str | None]:
    name = _path_text(party, "PartyName", "Name")
    identifiers = _children(party, "PartyIdentification")
    preferred: tuple[str | None, str | None] = (None, None)
    for identifier in identifiers:
        value_node = _child(identifier, "ID")
        value = _text(value_node)
        scheme = normalize_ws(str((value_node.attrib if value_node is not None else {}).get("schemeName") or "")) or None
        if not value:
            continue
        if preferred[0] is None or str(scheme or "").upper() == "NIF":
            preferred = (value, scheme)
        if str(scheme or "").upper() == "NIF":
            break
    return name, preferred[0], preferred[1]


def _parse_awards(status: ET.Element) -> tuple[dict[str, Any], ...]:
    awards: list[dict[str, Any]] = []
    for ordinal, result in enumerate(_children(status, "TenderResult")):
        winning_party = _child(result, "WinningParty")
        supplier_name, supplier_identifier, supplier_scheme = _party_identity(winning_party)
        awarded_project = _child(result, "AwardedTenderedProject")
        amount_node = _path(awarded_project, "LegalMonetaryTotal", "TaxExclusiveAmount")
        payable_node = _path(awarded_project, "LegalMonetaryTotal", "PayableAmount")
        amount, currency = _decimal_text(amount_node)
        payable_amount, payable_currency = _decimal_text(payable_node)
        received_raw = _path_text(result, "ReceivedTenderQuantity")
        try:
            received = int(received_raw) if received_raw is not None else None
        except ValueError as exc:
            raise RuntimeError(f"invalid ReceivedTenderQuantity: {received_raw!r}") from exc
        awards.append(
            {
                "award_ordinal": ordinal,
                "lot_id": _path_text(awarded_project, "ProcurementProjectLotID"),
                "result_code": _path_text(result, "ResultCode"),
                "result_description": _path_text(result, "Description"),
                "award_date": _path_text(result, "AwardDate"),
                "received_tender_quantity": received,
                "supplier_name": supplier_name,
                "supplier_identifier": supplier_identifier,
                "supplier_identifier_scheme": supplier_scheme,
                "amount_eur_decimal": amount,
                "payable_amount_eur_decimal": payable_amount,
                "currency": currency or payable_currency,
            }
        )
    return tuple(awards)


def _parse_documents(
    status: ET.Element,
    *,
    max_documents: int,
) -> tuple[dict[str, Any], ...]:
    document_container_names = {
        "LegalDocumentReference",
        "TechnicalDocumentReference",
        "AdditionalDocumentReference",
        "GeneralDocument",
    }
    documents: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for container in status.iter():
        kind = _local_name(container.tag)
        if kind not in document_container_names:
            continue
        uri_node = next(
            (node for node in container.iter() if _local_name(node.tag) == "URI" and _text(node)),
            None,
        )
        source_url = _text(uri_node)
        if not source_url or source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        hash_node = next(
            (node for node in container.iter() if _local_name(node.tag) == "DocumentHash"),
            None,
        )
        documents.append(
            {
                "document_ordinal": len(documents),
                "document_kind": kind,
                "document_label": _path_text(container, "ID") or _path_text(container, "Name"),
                "source_url": source_url,
                "official_document_hash": _text(hash_node),
            }
        )
        if len(documents) > int(max_documents):
            raise RuntimeError(
                f"PLACSP entry documents exceed cap: received>{int(max_documents)}"
            )
    return tuple(documents)


def _parse_tombstone(entry: ET.Element, entry_sha256: str) -> PlacspAtomRecord:
    stable_id = normalize_ws(str(entry.attrib.get("ref") or ""))
    if not stable_id:
        raise RuntimeError("PLACSP tombstone lacks ref")
    record = {
        "stable_contract_id": stable_id,
        "entry_updated_at": normalize_ws(str(entry.attrib.get("when") or "")) or None,
        "contract_status_code": _path_text(entry, "comment") or "deleted",
        "tombstone": True,
    }
    source_record_id = hashlib.sha256(f"{stable_id}\n{entry_sha256}".encode()).hexdigest()
    return PlacspAtomRecord(
        source_record_id=source_record_id,
        stable_contract_id=stable_id,
        entry_content_sha256=entry_sha256,
        tombstone=True,
        record=record,
        awards=(),
        documents=(),
    )


def _parse_entry(
    entry: ET.Element,
    entry_sha256: str,
    *,
    max_documents: int,
) -> PlacspAtomRecord:
    stable_id = _path_text(entry, "id")
    status = _child(entry, "ContractFolderStatus")
    contract_id = _path_text(status, "ContractFolderID")
    if not stable_id:
        stable_id = contract_id
    if not stable_id or status is None:
        raise RuntimeError("PLACSP entry lacks stable id or ContractFolderStatus")

    located = _child(status, "LocatedContractingParty")
    authority_name, authority_identifier, _authority_scheme = _party_identity(
        _child(located, "Party")
    )
    project = _child(status, "ProcurementProject")
    estimated_node = _path(project, "BudgetAmount", "EstimatedOverallContractAmount")
    tax_exclusive_node = _path(project, "BudgetAmount", "TaxExclusiveAmount")
    total_node = _path(project, "BudgetAmount", "TotalAmount")
    selected_amount_node = next(
        (
            node
            for node in (estimated_node, tax_exclusive_node, total_node)
            if node is not None
        ),
        None,
    )
    amount, currency = _decimal_text(selected_amount_node)
    amount_semantics = None
    if selected_amount_node is not None:
        amount_semantics = {
            "EstimatedOverallContractAmount": "estimated_overall_contract_amount",
            "TaxExclusiveAmount": "budget_tax_exclusive_amount",
            "TotalAmount": "budget_total_amount",
        }.get(_local_name(selected_amount_node.tag))

    cpv_nodes = (
        [
            node
            for node in project.iter()
            if _local_name(node.tag) == "ItemClassificationCode"
        ]
        if project is not None
        else []
    )
    issue_dates = sorted(
        value
        for node in status.iter()
        if _local_name(node.tag) == "IssueDate"
        for value in [_text(node)]
        if value
    )
    notice_codes = [
        value
        for node in status.iter()
        if _local_name(node.tag) == "NoticeTypeCode"
        for value in [_text(node)]
        if value
    ]
    record = {
        "stable_contract_id": stable_id,
        "contract_id": contract_id,
        "title": _path_text(project, "Name") or _path_text(entry, "title"),
        "summary": _path_text(entry, "summary"),
        "source_url": _entry_link(entry),
        "entry_updated_at": _path_text(entry, "updated"),
        "contract_status_code": _path_text(status, "ContractFolderStatusCode"),
        "notice_type": notice_codes[-1] if notice_codes else None,
        "cpv_code": _text(cpv_nodes[0]) if cpv_nodes else None,
        "contracting_authority": authority_name,
        "authority_identifier": authority_identifier,
        "procedure_type": _path_text(status, "TenderingProcess", "ProcedureCode"),
        "territory_code": _path_text(project, "RealizedLocation", "CountrySubentityCode"),
        "published_date": issue_dates[0] if issue_dates else None,
        "amount_eur_decimal": amount,
        "amount_semantics": amount_semantics,
        "currency": currency,
        "tombstone": False,
    }
    awards = _parse_awards(status)
    documents = _parse_documents(status, max_documents=max_documents)
    source_record_id = hashlib.sha256(f"{stable_id}\n{entry_sha256}".encode()).hexdigest()
    return PlacspAtomRecord(
        source_record_id=source_record_id,
        stable_contract_id=stable_id,
        entry_content_sha256=entry_sha256,
        tombstone=False,
        record=record,
        awards=awards,
        documents=documents,
    )


def iter_placsp_atom_records(
    stream: BinaryIO,
    *,
    max_records: int = DEFAULT_MAX_RECORDS_PER_MEMBER,
    max_documents_per_record: int = DEFAULT_MAX_DOCUMENTS_PER_RECORD,
    progress_callback: Callable[[], None] | None = None,
) -> Iterator[PlacspAtomRecord]:
    """Stream normalized records from one Atom member with bounded cardinality."""

    count = 0
    try:
        for _event, element in ET.iterparse(stream, events=("end",)):
            local = _local_name(element.tag)
            if local not in {"entry", "deleted-entry"}:
                continue
            count += 1
            if count > int(max_records):
                raise RuntimeError(
                    f"PLACSP member records exceed cap: received>{int(max_records)}"
                )
            entry_bytes = ET.tostring(element, encoding="utf-8")
            entry_sha256 = hashlib.sha256(entry_bytes).hexdigest()
            if local == "deleted-entry":
                yield _parse_tombstone(element, entry_sha256)
            else:
                yield _parse_entry(
                    element,
                    entry_sha256,
                    max_documents=int(max_documents_per_record),
                )
            if progress_callback is not None:
                progress_callback()
            element.clear()
    except ET.ParseError as exc:
        raise RuntimeError(f"invalid PLACSP Atom XML: {exc}") from exc


def compact_record_payload(record: PlacspAtomRecord) -> str:
    """Stable compact payload; full original XML stays in archive CAS."""

    return stable_json(
        {
            "entry_content_sha256": record.entry_content_sha256,
            "record": record.record,
            "awards": record.awards,
            "documents": record.documents,
        }
    )
