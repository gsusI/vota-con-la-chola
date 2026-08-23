"""Parse source-scoped candidate proclamations from official BOE XML."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

SOURCE_ID = "boe_election_candidates"
PARSER_VERSION = "boe_election_candidates_v2"
_BOE_ID = re.compile(r"BOE-A-[0-9]{4}-[0-9]+")
_NUMBERED = re.compile(r"^([0-9]+)[.]\s*(.+?)[.]?$")
_SUBSTITUTE = re.compile(r"^Suplente\s+([0-9]+):\s*(.+?)[.]?$", re.IGNORECASE)
_EUROPEAN_CANDIDACY = re.compile(r"^CANDIDATURA\s+N[ÚU]MERO\s+([0-9]+)$", re.IGNORECASE)


class BoeCandidateParseError(RuntimeError):
    """Raised when a BOE candidate document violates the explicit contract."""


@dataclass(frozen=True)
class BoeCandidateDocument:
    document_id: str
    title: str
    publication_date: str
    correction_refs: tuple[str, ...]
    profile: str


@dataclass(frozen=True)
class BoeCandidacy:
    candidacy_id: str
    electoral_board: str
    electoral_district: str
    chamber_code: str
    candidacy_number: int
    candidacy_name: str
    source_text_exact: str
    proclamation_status: str
    source_paragraph_number: int


@dataclass(frozen=True)
class BoeCandidateOccurrence:
    candidate_occurrence_id: str
    candidacy_id: str
    electoral_board: str
    electoral_district: str
    chamber_code: str
    candidacy_number: int
    candidate_order: int
    candidate_type_code: str
    substitute_for_candidate_order: int | None
    full_name: str
    source_text_exact: str
    source_paragraph_number: int


@dataclass(frozen=True)
class BoeCandidateParseResult:
    document: BoeCandidateDocument
    candidacies: tuple[BoeCandidacy, ...]
    candidates: tuple[BoeCandidateOccurrence, ...]


@dataclass(frozen=True)
class BoeCandidateCorrectionDocument:
    document_id: str
    title: str
    publication_date: str
    base_document_refs: tuple[str, ...]


@dataclass(frozen=True)
class BoeCandidateCorrectionParagraph:
    correction_paragraph_id: str
    source_paragraph_number: int
    source_css_class: str
    source_text_exact: str
    normalized_text: str
    semantic_marker: str
    electoral_board: str
    electoral_district: str
    chamber_code: str
    candidacy_number: int | None


@dataclass(frozen=True)
class BoeCandidateCorrectionParseResult:
    document: BoeCandidateCorrectionDocument
    paragraphs: tuple[BoeCandidateCorrectionParagraph, ...]


def _normalized_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _exact_text(element: ET.Element) -> str:
    return "".join(element.itertext())


def _date(value: str, *, field: str) -> str:
    token = str(value or "").strip()
    if not re.fullmatch(r"[0-9]{8}", token):
        raise BoeCandidateParseError(f"BOE XML has invalid {field}: {token!r}")
    return f"{token[:4]}-{token[4:6]}-{token[6:8]}"


def _identity(prefix: str, *parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _profile(title: str) -> str:
    lowered = title.lower()
    if "proclamaci" not in lowered and "candidaturas proclamadas" not in lowered:
        raise BoeCandidateParseError("BOE document is not a candidate proclamation")
    if "parlamento europeo" in lowered:
        return "european_parliament"
    if "congreso de los diputados" in lowered and "senado" in lowered:
        return "general_election"
    raise BoeCandidateParseError("unsupported BOE candidate proclamation profile")


def _metadata(root: ET.Element) -> BoeCandidateDocument:
    metadata = root.find("metadatos")
    if metadata is None:
        raise BoeCandidateParseError("BOE XML is missing metadata")
    document_id = (
        _normalized_text(metadata.find("identificador"))
        if metadata.find("identificador") is not None
        else ""
    )
    if _BOE_ID.fullmatch(document_id) is None:
        raise BoeCandidateParseError(
            f"invalid BOE document identifier: {document_id!r}"
        )
    title_node = metadata.find("titulo")
    title = _normalized_text(title_node) if title_node is not None else ""
    if not title:
        raise BoeCandidateParseError("BOE candidate document has no title")
    publication_node = metadata.find("fecha_publicacion")
    publication_date = _date(
        _normalized_text(publication_node) if publication_node is not None else "",
        field="publication date",
    )
    correction_refs = tuple(
        sorted(
            {
                str(node.attrib.get("referencia") or "").strip()
                for node in root.findall("./analisis/referencias/posteriores/posterior")
                if _BOE_ID.fullmatch(str(node.attrib.get("referencia") or "").strip())
            }
        )
    )
    return BoeCandidateDocument(
        document_id=document_id,
        title=title,
        publication_date=publication_date,
        correction_refs=correction_refs,
        profile=_profile(title),
    )


def _candidate_name(match: re.Match[str]) -> str:
    name = match.group(2).strip()
    if name.endswith("."):
        name = name[:-1].rstrip()
    if not name:
        raise BoeCandidateParseError("candidate paragraph has an empty public name")
    return name


def _parse_european(
    document: BoeCandidateDocument,
    paragraphs: list[ET.Element],
) -> tuple[list[BoeCandidacy], list[BoeCandidateOccurrence]]:
    mutable: dict[str, dict[str, object]] = {}
    rows: list[BoeCandidateOccurrence] = []
    current_number: int | None = None
    current_candidacy_id: str | None = None
    candidate_kind = "titular"
    seen_slots: set[tuple[str, str, int, int | None]] = set()

    for paragraph_number, element in enumerate(paragraphs, start=1):
        normalized = _normalized_text(element)
        exact = _exact_text(element)
        css_class = str(element.attrib.get("class") or "")
        heading = _EUROPEAN_CANDIDACY.fullmatch(normalized)
        if heading is not None:
            current_number = int(heading.group(1))
            current_candidacy_id = None
            candidate_kind = "titular"
            continue
        if (
            current_number is not None
            and current_candidacy_id is None
            and css_class == "centro_redonda"
        ):
            current_candidacy_id = _identity(
                "boe-candidacy",
                document.document_id,
                "",
                "",
                "EUROPEAN_PARLIAMENT",
                current_number,
            )
            mutable[current_candidacy_id] = {
                "candidacy_id": current_candidacy_id,
                "electoral_board": "",
                "electoral_district": "",
                "chamber_code": "EUROPEAN_PARLIAMENT",
                "candidacy_number": current_number,
                "candidacy_name": normalized,
                "source_text_exact": exact,
                "proclamation_status": "proclaimed",
                "source_paragraph_number": paragraph_number,
            }
            continue
        if current_candidacy_id is None:
            continue
        if normalized.casefold() == "suplentes":
            candidate_kind = "suplente"
            continue
        numbered = _NUMBERED.fullmatch(normalized)
        if not css_class.startswith("parrafo") or numbered is None:
            continue
        candidate_order = int(numbered.group(1))
        slot = (current_candidacy_id, candidate_kind, candidate_order, None)
        if slot in seen_slots:
            raise BoeCandidateParseError(f"duplicate BOE candidate slot: {slot}")
        seen_slots.add(slot)
        occurrence_id = _identity("boe-candidate", document.document_id, *slot)
        candidacy = mutable[current_candidacy_id]
        rows.append(
            BoeCandidateOccurrence(
                candidate_occurrence_id=occurrence_id,
                candidacy_id=current_candidacy_id,
                electoral_board="",
                electoral_district="",
                chamber_code="EUROPEAN_PARLIAMENT",
                candidacy_number=int(candidacy["candidacy_number"]),
                candidate_order=candidate_order,
                candidate_type_code=candidate_kind,
                substitute_for_candidate_order=None,
                full_name=_candidate_name(numbered),
                source_text_exact=exact,
                source_paragraph_number=paragraph_number,
            )
        )

    candidacies = [BoeCandidacy(**row) for row in mutable.values()]
    if not candidacies or not rows:
        raise BoeCandidateParseError("BOE European candidate parser produced no rows")
    titular_counts = {
        candidacy.candidacy_id: sum(
            row.candidacy_id == candidacy.candidacy_id
            and row.candidate_type_code == "titular"
            for row in rows
        )
        for candidacy in candidacies
    }
    if len(set(titular_counts.values())) != 1 or min(titular_counts.values()) < 1:
        raise BoeCandidateParseError(
            "BOE European candidacies do not have a reconciled titular count"
        )
    return candidacies, rows


def _parse_general(
    document: BoeCandidateDocument,
    paragraphs: list[ET.Element],
) -> tuple[list[BoeCandidacy], list[BoeCandidateOccurrence]]:
    mutable: dict[str, dict[str, object]] = {}
    rows: list[BoeCandidateOccurrence] = []
    electoral_board = ""
    electoral_district = ""
    chamber_code = ""
    current_candidacy_id: str | None = None
    candidate_kind = "titular"
    current_titular_order: int | None = None
    seen_slots: set[tuple[str, str, int, int | None]] = set()

    for paragraph_number, element in enumerate(paragraphs, start=1):
        normalized = _normalized_text(element)
        exact = _exact_text(element)
        css_class = str(element.attrib.get("class") or "")
        next_element = (
            paragraphs[paragraph_number] if paragraph_number < len(paragraphs) else None
        )
        next_numbered = (
            _NUMBERED.fullmatch(_normalized_text(next_element))
            if next_element is not None
            else None
        )
        next_is_empty_candidacy = next_element is not None and _normalized_text(
            next_element
        ).casefold() in {
            "no proclamada.",
            "no se proclama.",
            "la candidatura no tiene candidatos asociados.",
        }
        if css_class == "centro_negrita" and normalized.startswith(
            "JUNTA ELECTORAL DE "
        ):
            electoral_board = normalized
            electoral_district = ""
            chamber_code = ""
            current_candidacy_id = None
            continue
        if css_class == "centro_negrita" and normalized.startswith(
            "Circunscripción electoral:"
        ):
            electoral_district = normalized
            current_candidacy_id = None
            continue
        if css_class in {"centro_cursiva", "centro_negrita"} and normalized in {
            "CONGRESO DE LOS DIPUTADOS",
            "SENADO",
        }:
            chamber_code = (
                "CONGRESS" if normalized == "CONGRESO DE LOS DIPUTADOS" else "SENATE"
            )
            current_candidacy_id = None
            continue
        numbered = _NUMBERED.fullmatch(normalized)
        malformed_heading_class = (
            css_class in {"parrafo_2", "subseccion"}
            and numbered is not None
            and next_element is not None
            and str(next_element.attrib.get("class") or "").startswith("parrafo")
            and (
                (next_numbered is not None and int(next_numbered.group(1)) == 1)
                or next_is_empty_candidacy
            )
        )
        missing_number_heading = (
            css_class == "centro_redonda"
            and numbered is None
            and next_element is not None
            and str(next_element.attrib.get("class") or "").startswith("parrafo")
            and next_numbered is not None
            and int(next_numbered.group(1)) == 1
        )
        if missing_number_heading:
            raise BoeCandidateParseError(
                f"BOE candidacy heading has no official number at paragraph {paragraph_number}"
            )
        if (
            electoral_board
            and chamber_code
            and (
                (css_class == "centro_redonda" and numbered is not None)
                or malformed_heading_class
            )
        ):
            if numbered is None:
                raise BoeCandidateParseError(
                    f"unrecognized BOE candidacy heading at paragraph {paragraph_number}"
                )
            candidacy_number = int(numbered.group(1))
            current_candidacy_id = _identity(
                "boe-candidacy",
                document.document_id,
                electoral_board,
                electoral_district,
                chamber_code,
                candidacy_number,
            )
            mutable[current_candidacy_id] = {
                "candidacy_id": current_candidacy_id,
                "electoral_board": electoral_board,
                "electoral_district": electoral_district,
                "chamber_code": chamber_code,
                "candidacy_number": candidacy_number,
                "candidacy_name": _candidate_name(numbered),
                "source_text_exact": exact,
                "proclamation_status": "proclaimed",
                "source_paragraph_number": paragraph_number,
            }
            candidate_kind = "titular"
            current_titular_order = None
            continue
        if current_candidacy_id is None:
            continue
        if normalized.casefold().rstrip(".:") == "suplentes":
            candidate_kind = "suplente"
            current_titular_order = None
            continue
        if normalized.casefold() in {
            "no proclamada.",
            "no se proclama.",
            "la candidatura no tiene candidatos asociados.",
        }:
            mutable[current_candidacy_id]["proclamation_status"] = "not_proclaimed"
            continue

        substitute = _SUBSTITUTE.fullmatch(normalized)
        substitute_for: int | None = None
        if substitute is not None:
            if current_titular_order is None:
                raise BoeCandidateParseError(
                    f"orphan Senate substitute at paragraph {paragraph_number}"
                )
            numbered = substitute
            row_kind = "suplente"
            substitute_for = current_titular_order
        else:
            numbered = _NUMBERED.fullmatch(normalized)
            if not css_class.startswith("parrafo") or numbered is None:
                continue
            row_kind = candidate_kind
            if row_kind == "titular":
                current_titular_order = int(numbered.group(1))
        candidate_order = int(numbered.group(1))
        slot = (
            current_candidacy_id,
            row_kind,
            candidate_order,
            substitute_for,
        )
        if slot in seen_slots:
            raise BoeCandidateParseError(f"duplicate BOE candidate slot: {slot}")
        seen_slots.add(slot)
        candidacy = mutable[current_candidacy_id]
        occurrence_id = _identity("boe-candidate", document.document_id, *slot)
        rows.append(
            BoeCandidateOccurrence(
                candidate_occurrence_id=occurrence_id,
                candidacy_id=current_candidacy_id,
                electoral_board=electoral_board,
                electoral_district=electoral_district,
                chamber_code=chamber_code,
                candidacy_number=int(candidacy["candidacy_number"]),
                candidate_order=candidate_order,
                candidate_type_code=row_kind,
                substitute_for_candidate_order=substitute_for,
                full_name=_candidate_name(numbered),
                source_text_exact=exact,
                source_paragraph_number=paragraph_number,
            )
        )

    candidacies = [BoeCandidacy(**row) for row in mutable.values()]
    if not candidacies or not rows:
        raise BoeCandidateParseError("BOE general candidate parser produced no rows")
    for candidacy in candidacies:
        count = sum(row.candidacy_id == candidacy.candidacy_id for row in rows)
        if candidacy.proclamation_status == "not_proclaimed" and count != 0:
            raise BoeCandidateParseError(
                "not-proclaimed candidacy unexpectedly contains candidate rows"
            )
        if candidacy.proclamation_status == "proclaimed" and count == 0:
            raise BoeCandidateParseError(
                "proclaimed candidacy contains no candidate rows"
            )
    return candidacies, rows


def parse_boe_candidate_document(path: Path) -> BoeCandidateParseResult:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise BoeCandidateParseError(f"cannot parse BOE candidate XML: {exc}") from exc
    if root.tag != "documento":
        raise BoeCandidateParseError(f"unexpected BOE XML root: {root.tag}")
    document = _metadata(root)
    text = root.find("texto")
    if text is None:
        raise BoeCandidateParseError("BOE candidate XML has no text body")
    paragraphs = list(text)
    if document.profile == "european_parliament":
        candidacies, candidates = _parse_european(document, paragraphs)
    else:
        candidacies, candidates = _parse_general(document, paragraphs)
    return BoeCandidateParseResult(
        document=document,
        candidacies=tuple(candidacies),
        candidates=tuple(candidates),
    )


def _correction_marker(
    normalized: str,
    css_class: str,
    *,
    is_board: bool,
    is_district: bool,
    is_chamber: bool,
    is_candidacy: bool,
) -> str:
    lowered = normalized.casefold()
    if is_board:
        return "electoral_board_heading"
    if is_district:
        return "electoral_district_heading"
    if is_chamber:
        return "chamber_heading"
    if is_candidacy:
        return "candidacy_heading"
    if "donde dice" in lowered:
        return "before_value"
    if lowered.startswith("debe decir") or "debe decir:" in lowered:
        return "after_value"
    if "se sustituye" in lowered or "se sustituyen" in lowered:
        return "replacement_instruction"
    if lowered.rstrip(".:") in {"suplentes", "no proclamada"}:
        return "list_state"
    if _SUBSTITUTE.fullmatch(normalized) is not None:
        return "candidate_row"
    if css_class.startswith("parrafo") and _NUMBERED.fullmatch(normalized) is not None:
        return "candidate_row"
    return "context"


def parse_boe_candidate_correction(
    path: Path,
) -> BoeCandidateCorrectionParseResult:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise BoeCandidateParseError(f"cannot parse BOE correction XML: {exc}") from exc
    if root.tag != "documento":
        raise BoeCandidateParseError(f"unexpected BOE correction XML root: {root.tag}")
    metadata = root.find("metadatos")
    if metadata is None:
        raise BoeCandidateParseError("BOE correction XML is missing metadata")
    identifier_node = metadata.find("identificador")
    document_id = (
        _normalized_text(identifier_node) if identifier_node is not None else ""
    )
    if _BOE_ID.fullmatch(document_id) is None:
        raise BoeCandidateParseError(
            f"invalid BOE correction identifier: {document_id!r}"
        )
    title_node = metadata.find("titulo")
    title = _normalized_text(title_node) if title_node is not None else ""
    lowered_title = title.casefold()
    if "candidat" not in lowered_title or "corr" not in lowered_title:
        raise BoeCandidateParseError("BOE document is not a candidate correction")
    publication_node = metadata.find("fecha_publicacion")
    publication_date = _date(
        _normalized_text(publication_node) if publication_node is not None else "",
        field="correction publication date",
    )
    base_refs = tuple(
        sorted(
            {
                str(node.attrib.get("referencia") or "").strip()
                for node in root.findall("./analisis/referencias/anteriores/anterior")
                if _BOE_ID.fullmatch(str(node.attrib.get("referencia") or "").strip())
            }
        )
    )
    if not base_refs:
        raise BoeCandidateParseError("BOE candidate correction has no base reference")
    text = root.find("texto")
    if text is None:
        raise BoeCandidateParseError("BOE candidate correction has no text body")

    electoral_board = ""
    electoral_district = ""
    chamber_code = ""
    candidacy_number: int | None = None
    paragraphs: list[BoeCandidateCorrectionParagraph] = []
    for paragraph_number, element in enumerate(list(text), start=1):
        exact = _exact_text(element)
        normalized = _normalized_text(element)
        css_class = str(element.attrib.get("class") or "")
        is_board = css_class == "centro_negrita" and normalized.startswith(
            "JUNTA ELECTORAL DE "
        )
        is_district = css_class == "centro_negrita" and normalized.startswith(
            "Circunscripción electoral:"
        )
        is_chamber = css_class == "centro_cursiva" and normalized in {
            "CONGRESO DE LOS DIPUTADOS",
            "SENADO",
        }
        european_heading = _EUROPEAN_CANDIDACY.fullmatch(normalized)
        general_heading = (
            _NUMBERED.fullmatch(normalized) if css_class == "centro_redonda" else None
        )
        is_candidacy = european_heading is not None or general_heading is not None
        if is_board:
            electoral_board = normalized
            electoral_district = ""
            chamber_code = ""
            candidacy_number = None
        elif is_district:
            electoral_district = normalized
            candidacy_number = None
        elif is_chamber:
            chamber_code = (
                "CONGRESS" if normalized == "CONGRESO DE LOS DIPUTADOS" else "SENATE"
            )
            candidacy_number = None
        elif european_heading is not None:
            chamber_code = "EUROPEAN_PARLIAMENT"
            candidacy_number = int(european_heading.group(1))
        elif general_heading is not None:
            candidacy_number = int(general_heading.group(1))
        paragraphs.append(
            BoeCandidateCorrectionParagraph(
                correction_paragraph_id=_identity(
                    "boe-candidate-correction-paragraph",
                    document_id,
                    paragraph_number,
                    exact,
                ),
                source_paragraph_number=paragraph_number,
                source_css_class=css_class,
                source_text_exact=exact,
                normalized_text=normalized,
                semantic_marker=_correction_marker(
                    normalized,
                    css_class,
                    is_board=is_board,
                    is_district=is_district,
                    is_chamber=is_chamber,
                    is_candidacy=is_candidacy,
                ),
                electoral_board=electoral_board,
                electoral_district=electoral_district,
                chamber_code=chamber_code,
                candidacy_number=candidacy_number,
            )
        )
    if not paragraphs:
        raise BoeCandidateParseError("BOE candidate correction has no paragraphs")
    return BoeCandidateCorrectionParseResult(
        document=BoeCandidateCorrectionDocument(
            document_id=document_id,
            title=title,
            publication_date=publication_date,
            base_document_refs=base_refs,
        ),
        paragraphs=tuple(paragraphs),
    )


__all__ = [
    "PARSER_VERSION",
    "SOURCE_ID",
    "BoeCandidacy",
    "BoeCandidateCorrectionDocument",
    "BoeCandidateCorrectionParagraph",
    "BoeCandidateCorrectionParseResult",
    "BoeCandidateDocument",
    "BoeCandidateOccurrence",
    "BoeCandidateParseError",
    "BoeCandidateParseResult",
    "parse_boe_candidate_correction",
    "parse_boe_candidate_document",
]
