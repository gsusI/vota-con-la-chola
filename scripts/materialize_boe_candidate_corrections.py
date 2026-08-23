"""Materialize effective BOE candidate state from exact correction evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.politicos_es.db import apply_schema
from publicdata_sqlite import open_db

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "boe-election-candidate-correction-materialization.json"
)
MATERIALIZER_VERSION = "boe_candidate_correction_materializer_v3"
SOURCE_ID = "boe_election_candidates"

_NUMBERED = re.compile(r"^(\d+)[.]\s*(.+?)[.]?$")
_SUBSTITUTE = re.compile(r"^Suplente\s+(\d+):\s*(.+?)[.]?$", re.IGNORECASE)
_INLINE_REPLACEMENT = re.compile(
    r"donde dice:?\s*[«“](.*?)[»”],?\s*debe decir:?\s*[«“](.*?)[»”]",
    re.IGNORECASE,
)


class CorrectionMaterializationError(RuntimeError):
    """Raised when official correction evidence cannot be proven against base rows."""


@dataclass(frozen=True)
class Selector:
    base_document_id: str
    electoral_board: str
    electoral_district: str | None
    chamber_code: str
    candidacy_number: int


@dataclass(frozen=True)
class SimpleSpec:
    correction_document_id: str
    operation_order: int
    operation_type: str
    selector: Selector
    evidence_paragraphs: tuple[int, ...]
    before_paragraph: int
    after_paragraph: int
    inline: bool = False
    candidate_type_code: str | None = None


@dataclass(frozen=True)
class ListSpec:
    correction_document_id: str
    operation_order: int
    operation_type: str
    selector: Selector
    evidence_paragraphs: tuple[int, ...]
    candidate_paragraphs: tuple[int, ...]
    replacement_scope: str
    initial_candidate_type: str


def _paragraph_range(start: int, end: int) -> tuple[int, ...]:
    return tuple(range(start, end + 1))


SIMPLE_SPECS = (
    SimpleSpec(
        "BOE-A-2023-15548",
        1,
        "replace_candidacy_name",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE BALEARES", "", "CONGRESS", 6),
        _paragraph_range(4, 7),
        5,
        7,
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        2,
        "replace_candidate_slot",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE BALEARES", "", "CONGRESS", 8),
        _paragraph_range(10, 13),
        11,
        13,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        3,
        "replace_candidate_slot",
        Selector(
            "BOE-A-2023-15066",
            "JUNTA ELECTORAL DE BALEARES",
            "Circunscripción electoral: Menorca",
            "SENATE",
            1,
        ),
        _paragraph_range(18, 21),
        19,
        21,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        4,
        "replace_candidacy_name",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE BIZKAIA", "", "CONGRESS", 3),
        _paragraph_range(24, 27),
        25,
        27,
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        5,
        "replace_candidate_slot",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE BIZKAIA", "", "CONGRESS", 7),
        _paragraph_range(30, 33),
        31,
        33,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        6,
        "replace_candidacy_name",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE BIZKAIA", "", "SENATE", 3),
        _paragraph_range(35, 38),
        36,
        38,
    ),
    SimpleSpec(
        "BOE-A-2023-15548",
        7,
        "replace_candidate_slot",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE CUENCA", "", "SENATE", 9),
        _paragraph_range(43, 46),
        44,
        46,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        1,
        "replace_candidate_slot",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 2),
        (5,),
        5,
        5,
        inline=True,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        2,
        "replace_candidate_slot",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 5),
        (8,),
        8,
        8,
        inline=True,
        candidate_type_code="suplente",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        3,
        "replace_candidate_slot",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 10),
        (11,),
        11,
        11,
        inline=True,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        5,
        "replace_candidate_slot",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 24),
        (27,),
        27,
        27,
        inline=True,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        6,
        "replace_candidate_slot",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 25),
        (30,),
        30,
        30,
        inline=True,
        candidate_type_code="titular",
    ),
    SimpleSpec(
        "BOE-A-2024-10569",
        8,
        "replace_candidate_slot",
        Selector("BOE-A-2024-10230", "", "", "EUROPEAN_PARLIAMENT", 34),
        (108,),
        108,
        108,
        inline=True,
        candidate_type_code="titular",
    ),
)

LIST_SPECS = (
    ListSpec(
        "BOE-A-2023-15828",
        1,
        "replace_candidacy_status_and_list",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE TERUEL", "", "CONGRESS", 13),
        _paragraph_range(5, 14),
        _paragraph_range(10, 14),
        "all",
        "titular",
    ),
    ListSpec(
        "BOE-A-2023-15828",
        2,
        "replace_candidacy_status_and_list",
        Selector("BOE-A-2023-15066", "JUNTA ELECTORAL DE TERUEL", "", "SENATE", 12),
        _paragraph_range(18, 25),
        _paragraph_range(23, 25),
        "all",
        "titular",
    ),
    ListSpec(
        "BOE-A-2024-10569",
        4,
        "replace_candidate_list",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 11),
        _paragraph_range(14, 24),
        _paragraph_range(15, 24),
        "suplente",
        "suplente",
    ),
    ListSpec(
        "BOE-A-2024-10569",
        7,
        "replace_candidate_list",
        Selector("BOE-A-2024-9687", "", "", "EUROPEAN_PARLIAMENT", 33),
        _paragraph_range(33, 96),
        _paragraph_range(34, 96),
        "all",
        "titular",
    ),
)

EXPECTED_OPERATION_COUNTS = {
    "BOE-A-2023-15548": 7,
    "BOE-A-2023-15828": 2,
    "BOE-A-2024-10569": 8,
}
REVIEWED_BASE_DOCUMENT_IDS = tuple(
    sorted({spec.selector.base_document_id for spec in (*SIMPLE_SPECS, *LIST_SPECS)})
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--snapshot-date")
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _identity(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(_json(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _semantic(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    for token in "«»“”„‟\"'":
        normalized = normalized.replace(token, "")
    normalized = re.sub(r"\s+", " ", normalized).strip().rstrip(".").strip()
    return normalized


def _clean_quoted(value: str) -> str:
    cleaned = value.strip()
    while cleaned and cleaned[0] in "«“\"'":
        cleaned = cleaned[1:].lstrip()
    while cleaned and cleaned[-1] in "»”\"'":
        cleaned = cleaned[:-1].rstrip()
    cleaned = cleaned.rstrip(".").rstrip()
    while cleaned and cleaned[-1] in "»”\"'":
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def _numbered_value(value: str) -> tuple[int, str]:
    cleaned = _clean_quoted(value)
    match = _NUMBERED.fullmatch(cleaned)
    if match is None:
        raise CorrectionMaterializationError(
            f"official correction value is not numbered: {value!r}"
        )
    return int(match.group(1)), _clean_quoted(match.group(2))


def _paragraphs(
    conn: sqlite3.Connection, correction_document_id: str
) -> dict[int, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
        FROM boe_election_candidate_correction_paragraphs
        WHERE correction_document_id=?
        ORDER BY source_paragraph_number
        """,
        (correction_document_id,),
    ).fetchall()
    if not rows:
        raise CorrectionMaterializationError(
            f"correction paragraphs missing: {correction_document_id}"
        )
    return {int(row["source_paragraph_number"]): row for row in rows}


def _require_paragraphs(
    rows: dict[int, sqlite3.Row], numbers: tuple[int, ...], correction_id: str
) -> list[sqlite3.Row]:
    missing = [number for number in numbers if number not in rows]
    if missing:
        raise CorrectionMaterializationError(
            f"correction {correction_id} is missing paragraphs {missing}"
        )
    return [rows[number] for number in numbers]


def _evidence_hash(rows: list[sqlite3.Row]) -> str:
    payload = "\n".join(
        f"{int(row['source_paragraph_number'])}\0{row['source_text_exact']}"
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _find_candidacy(conn: sqlite3.Connection, selector: Selector) -> sqlite3.Row:
    conditions = [
        "base_document_id=?",
        "electoral_board=?",
        "chamber_code=?",
        "candidacy_number=?",
    ]
    params: list[object] = [
        selector.base_document_id,
        selector.electoral_board,
        selector.chamber_code,
        selector.candidacy_number,
    ]
    if selector.electoral_district is not None:
        conditions.append("electoral_district=?")
        params.append(selector.electoral_district)
    rows = conn.execute(
        "SELECT * FROM boe_election_effective_candidacies WHERE "
        + " AND ".join(conditions),
        params,
    ).fetchall()
    if len(rows) != 1:
        raise CorrectionMaterializationError(
            f"candidacy selector resolved {len(rows)} rows: {selector}"
        )
    return rows[0]


def _correction_source(conn: sqlite3.Connection, correction_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT correction_document_id, publication_date, source_url,
               source_content_sha256
        FROM boe_election_candidate_correction_documents
        WHERE correction_document_id=?
        """,
        (correction_id,),
    ).fetchone()
    if row is None:
        raise CorrectionMaterializationError(
            f"correction document missing: {correction_id}"
        )
    return row


def _require_target(
    conn: sqlite3.Connection, correction_id: str, base_document_id: str
) -> None:
    row = conn.execute(
        """
        SELECT 1 FROM boe_election_candidate_correction_targets
        WHERE correction_document_id=? AND base_document_id=?
        """,
        (correction_id, base_document_id),
    ).fetchone()
    if row is None:
        raise CorrectionMaterializationError(
            f"correction target is not evidenced: {correction_id} -> {base_document_id}"
        )


def _operation_id(spec: SimpleSpec | ListSpec, evidence_sha256: str) -> str:
    return _identity(
        "boe-candidate-correction-operation",
        spec.correction_document_id,
        spec.selector.base_document_id,
        spec.operation_order,
        spec.operation_type,
        evidence_sha256,
    )


def _insert_operation(
    conn: sqlite3.Connection,
    *,
    operation_id: str,
    spec: SimpleSpec | ListSpec,
    candidacy_id: str,
    base_match_state: str,
    candidate_type_code: str | None,
    candidate_order: int | None,
    substitute_for_candidate_order: int | None,
    before_value: Any,
    after_value: Any,
    evidence_sha256: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO boe_election_candidate_correction_operations (
          correction_operation_id, correction_document_id, base_document_id,
          candidacy_id, operation_order, operation_type, base_match_state,
          candidate_type_code, candidate_order,
          substitute_for_candidate_order, before_value_json,
          after_value_json, evidence_paragraph_numbers_json,
          evidence_text_sha256, materializer_version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operation_id,
            spec.correction_document_id,
            spec.selector.base_document_id,
            candidacy_id,
            spec.operation_order,
            spec.operation_type,
            base_match_state,
            candidate_type_code,
            candidate_order,
            substitute_for_candidate_order,
            _json(before_value),
            _json(after_value),
            _json(list(spec.evidence_paragraphs)),
            evidence_sha256,
            MATERIALIZER_VERSION,
            now_iso,
            now_iso,
        ),
    )


def _extract_simple_values(
    spec: SimpleSpec, rows: dict[int, sqlite3.Row]
) -> tuple[str, str]:
    if spec.inline:
        normalized = str(rows[spec.before_paragraph]["normalized_text"])
        match = _INLINE_REPLACEMENT.search(normalized)
        if match is None:
            raise CorrectionMaterializationError(
                f"inline before/after pair missing: {spec.correction_document_id} "
                f"paragraph {spec.before_paragraph}"
            )
        return match.group(1), match.group(2)
    return (
        str(rows[spec.before_paragraph]["normalized_text"]),
        str(rows[spec.after_paragraph]["normalized_text"]),
    )


def _candidate_row_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "candidate_order": int(row["candidate_order"]),
        "candidate_type_code": str(row["candidate_type_code"]),
        "substitute_for_candidate_order": (
            int(row["substitute_for_candidate_order"])
            if row["substitute_for_candidate_order"] is not None
            else None
        ),
        "full_name": str(row["full_name"]),
    }


def _effective_row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _candidate_name_match(
    current: str, before_value: str, after_value: str
) -> tuple[str | None, str]:
    if _semantic(current) == _semantic(before_value):
        return "before_matches", after_value
    if current.startswith(before_value):
        suffix = current[len(before_value) :]
        if suffix.startswith(" ") and suffix.strip():
            return "before_matches", after_value + suffix
    if _semantic(current) == _semantic(after_value):
        return "already_effective_after_matches", current
    if current.startswith(after_value):
        suffix = current[len(after_value) :]
        if suffix.startswith(" ") and suffix.strip():
            return "already_effective_after_matches", current
    return None, after_value


def _apply_simple(
    conn: sqlite3.Connection,
    spec: SimpleSpec,
    paragraph_rows: dict[int, sqlite3.Row],
    now_iso: str,
) -> dict[str, Any]:
    _require_target(conn, spec.correction_document_id, spec.selector.base_document_id)
    evidence = _require_paragraphs(
        paragraph_rows, spec.evidence_paragraphs, spec.correction_document_id
    )
    evidence_sha256 = _evidence_hash(evidence)
    operation_id = _operation_id(spec, evidence_sha256)
    source = _correction_source(conn, spec.correction_document_id)
    candidacy = _find_candidacy(conn, spec.selector)
    before_raw, after_raw = _extract_simple_values(spec, paragraph_rows)
    before_order, before_value = _numbered_value(before_raw)
    after_order, after_value = _numbered_value(after_raw)
    if spec.operation_type == "replace_candidacy_name":
        if (
            before_order != spec.selector.candidacy_number
            or after_order != before_order
        ):
            raise CorrectionMaterializationError("candidacy correction number drifted")
        current = str(candidacy["candidacy_name"])
        if _semantic(current) == _semantic(before_value):
            match_state = "before_matches"
        elif _semantic(current) == _semantic(after_value):
            match_state = "already_effective_after_matches"
        else:
            raise CorrectionMaterializationError(
                f"candidacy before/after mismatch: {spec.correction_document_id} "
                f"{current!r}"
            )
        _insert_operation(
            conn,
            operation_id=operation_id,
            spec=spec,
            candidacy_id=str(candidacy["candidacy_id"]),
            base_match_state=match_state,
            candidate_type_code=None,
            candidate_order=None,
            substitute_for_candidate_order=None,
            before_value={"candidacy_name": before_value},
            after_value={"candidacy_name": after_value},
            evidence_sha256=evidence_sha256,
            now_iso=now_iso,
        )
        after_row = paragraph_rows[spec.after_paragraph]
        conn.execute(
            """
            UPDATE boe_election_effective_candidacies
            SET candidacy_name=?, effective_source_document_id=?,
                effective_source_url=?, effective_source_content_sha256=?,
                source_text_exact=?, source_paragraph_number=?,
                correction_operation_id=?, materialized_at=?
            WHERE candidacy_id=?
            """,
            (
                after_value,
                spec.correction_document_id,
                str(source["source_url"]),
                str(source["source_content_sha256"]),
                str(after_row["source_text_exact"]),
                int(after_row["source_paragraph_number"]),
                operation_id,
                now_iso,
                str(candidacy["candidacy_id"]),
            ),
        )
        return {"operation_id": operation_id, "base_match_state": match_state}

    candidate_type = str(spec.candidate_type_code or "")
    before_row = conn.execute(
        """
        SELECT * FROM boe_election_effective_candidate_occurrences
        WHERE candidacy_id=? AND candidate_type_code=? AND candidate_order=?
          AND substitute_for_candidate_order IS NULL
        """,
        (str(candidacy["candidacy_id"]), candidate_type, before_order),
    ).fetchone()
    after_row_current = conn.execute(
        """
        SELECT * FROM boe_election_effective_candidate_occurrences
        WHERE candidacy_id=? AND candidate_type_code=? AND candidate_order=?
          AND substitute_for_candidate_order IS NULL
        """,
        (str(candidacy["candidacy_id"]), candidate_type, after_order),
    ).fetchone()
    target: sqlite3.Row
    before_match = (
        _candidate_name_match(str(before_row["full_name"]), before_value, after_value)
        if before_row is not None
        else (None, after_value)
    )
    after_match = (
        _candidate_name_match(
            str(after_row_current["full_name"]), before_value, after_value
        )
        if after_row_current is not None
        else (None, after_value)
    )
    if before_row is not None and before_match[0] == "before_matches":
        match_state = str(before_match[0])
        effective_after_value = before_match[1]
        target = before_row
        if (
            before_order != after_order
            and after_row_current is not None
            and str(after_row_current["effective_candidate_occurrence_id"])
            != str(before_row["effective_candidate_occurrence_id"])
        ):
            raise CorrectionMaterializationError("corrected candidate slot collides")
    elif (
        after_row_current is not None
        and after_match[0] == "already_effective_after_matches"
    ):
        match_state = "already_effective_after_matches"
        effective_after_value = after_match[1]
        target = after_row_current
    elif after_row_current is not None and after_match[0] == "before_matches":
        match_state = "partial_base_matches"
        effective_after_value = after_match[1]
        target = after_row_current
    else:
        raise CorrectionMaterializationError(
            f"candidate before/after mismatch: {spec.correction_document_id} "
            f"candidacy={candidacy['candidacy_id']} slot={candidate_type}:{before_order}"
        )
    correction_paragraph = paragraph_rows[spec.after_paragraph]
    row_payload = {
        "candidacy_id": str(candidacy["candidacy_id"]),
        "candidate_type_code": candidate_type,
        "candidate_order": after_order,
        "substitute_for_candidate_order": None,
        "full_name": effective_after_value,
        "effective_source_document_id": spec.correction_document_id,
        "source_text_exact": str(correction_paragraph["source_text_exact"]),
        "source_paragraph_number": int(correction_paragraph["source_paragraph_number"]),
    }
    _insert_operation(
        conn,
        operation_id=operation_id,
        spec=spec,
        candidacy_id=str(candidacy["candidacy_id"]),
        base_match_state=match_state,
        candidate_type_code=candidate_type,
        candidate_order=after_order,
        substitute_for_candidate_order=None,
        before_value={"candidate_order": before_order, "full_name": before_value},
        after_value={
            "candidate_order": after_order,
            "full_name": effective_after_value,
            "official_after_value": after_value,
        },
        evidence_sha256=evidence_sha256,
        now_iso=now_iso,
    )
    conn.execute(
        """
        UPDATE boe_election_effective_candidate_occurrences
        SET candidate_order=?, full_name=?, effective_source_document_id=?,
            effective_source_url=?, effective_source_content_sha256=?,
            source_text_exact=?, source_paragraph_number=?,
            correction_operation_id=?, row_content_sha256=?, materialized_at=?
        WHERE effective_candidate_occurrence_id=?
        """,
        (
            after_order,
            effective_after_value,
            spec.correction_document_id,
            str(source["source_url"]),
            str(source["source_content_sha256"]),
            str(correction_paragraph["source_text_exact"]),
            int(correction_paragraph["source_paragraph_number"]),
            operation_id,
            _effective_row_hash(row_payload),
            now_iso,
            str(target["effective_candidate_occurrence_id"]),
        ),
    )
    return {"operation_id": operation_id, "base_match_state": match_state}


def _parse_replacement_rows(
    spec: ListSpec, rows: dict[int, sqlite3.Row]
) -> list[dict[str, Any]]:
    current_type = spec.initial_candidate_type
    current_titular_order: int | None = None
    result: list[dict[str, Any]] = []
    for number in spec.candidate_paragraphs:
        row = rows[number]
        normalized = str(row["normalized_text"])
        if normalized.casefold().rstrip(".:") == "suplentes":
            current_type = "suplente"
            continue
        substitute = _SUBSTITUTE.fullmatch(_clean_quoted(normalized))
        if substitute is not None:
            if current_titular_order is None:
                raise CorrectionMaterializationError(
                    f"orphan corrected Senate substitute at paragraph {number}"
                )
            candidate_order = int(substitute.group(1))
            candidate_type = "suplente"
            substitute_for = current_titular_order
            full_name = _clean_quoted(substitute.group(2))
        else:
            numbered = _NUMBERED.fullmatch(_clean_quoted(normalized))
            if numbered is None:
                continue
            candidate_order = int(numbered.group(1))
            candidate_type = current_type
            substitute_for = None
            full_name = _clean_quoted(numbered.group(2))
            if candidate_type == "titular":
                current_titular_order = candidate_order
        result.append(
            {
                "candidate_order": candidate_order,
                "candidate_type_code": candidate_type,
                "substitute_for_candidate_order": substitute_for,
                "full_name": full_name,
                "source_text_exact": str(row["source_text_exact"]),
                "source_paragraph_number": number,
            }
        )
    slots = {
        (
            row["candidate_type_code"],
            row["candidate_order"],
            row["substitute_for_candidate_order"],
        )
        for row in result
    }
    if not result or len(slots) != len(result):
        raise CorrectionMaterializationError(
            f"replacement candidate rows do not reconcile: {spec}"
        )
    return result


def _apply_list(
    conn: sqlite3.Connection,
    spec: ListSpec,
    paragraph_rows: dict[int, sqlite3.Row],
    now_iso: str,
) -> dict[str, Any]:
    _require_target(conn, spec.correction_document_id, spec.selector.base_document_id)
    evidence = _require_paragraphs(
        paragraph_rows, spec.evidence_paragraphs, spec.correction_document_id
    )
    evidence_sha256 = _evidence_hash(evidence)
    operation_id = _operation_id(spec, evidence_sha256)
    source = _correction_source(conn, spec.correction_document_id)
    candidacy = _find_candidacy(conn, spec.selector)
    all_current = conn.execute(
        """
        SELECT * FROM boe_election_effective_candidate_occurrences
        WHERE candidacy_id=?
        ORDER BY candidate_type_code, candidate_order,
                 COALESCE(substitute_for_candidate_order, 0)
        """,
        (str(candidacy["candidacy_id"]),),
    ).fetchall()
    current = [
        row
        for row in all_current
        if spec.replacement_scope == "all"
        or str(row["candidate_type_code"]) == spec.replacement_scope
    ]
    after_rows = _parse_replacement_rows(spec, paragraph_rows)
    if spec.operation_type == "replace_candidacy_status_and_list":
        if str(candidacy["proclamation_status"]) != "not_proclaimed" or current:
            raise CorrectionMaterializationError(
                "status correction base must be not_proclaimed with no candidate rows"
            )
        before_value: dict[str, Any] = {
            "proclamation_status": "not_proclaimed",
            "candidates": [],
        }
        after_value: dict[str, Any] = {
            "proclamation_status": "proclaimed",
            "candidates": [
                {
                    key: value
                    for key, value in row.items()
                    if not key.startswith("source_")
                }
                for row in after_rows
            ],
        }
    else:
        instruction = " ".join(str(row["normalized_text"]) for row in evidence)
        if "se sustitu" not in instruction.casefold():
            raise CorrectionMaterializationError(
                f"replacement instruction missing: {spec.correction_document_id}"
            )
        before_value = {"candidates": [_candidate_row_payload(row) for row in current]}
        after_value = {
            "candidates": [
                {
                    key: value
                    for key, value in row.items()
                    if not key.startswith("source_")
                }
                for row in after_rows
            ]
        }
    _insert_operation(
        conn,
        operation_id=operation_id,
        spec=spec,
        candidacy_id=str(candidacy["candidacy_id"]),
        base_match_state="replacement_scope_matches",
        candidate_type_code=spec.replacement_scope,
        candidate_order=None,
        substitute_for_candidate_order=None,
        before_value=before_value,
        after_value=after_value,
        evidence_sha256=evidence_sha256,
        now_iso=now_iso,
    )
    if spec.replacement_scope == "all":
        conn.execute(
            "DELETE FROM boe_election_effective_candidate_occurrences WHERE candidacy_id=?",
            (str(candidacy["candidacy_id"]),),
        )
    else:
        conn.execute(
            """
            DELETE FROM boe_election_effective_candidate_occurrences
            WHERE candidacy_id=? AND candidate_type_code=?
            """,
            (str(candidacy["candidacy_id"]), spec.replacement_scope),
        )
    for row in after_rows:
        base = conn.execute(
            """
            SELECT candidate_occurrence_id, full_name
            FROM boe_election_candidate_occurrences
            WHERE candidacy_id=? AND candidate_type_code=? AND candidate_order=?
              AND COALESCE(substitute_for_candidate_order, -1)=COALESCE(?, -1)
            """,
            (
                str(candidacy["candidacy_id"]),
                row["candidate_type_code"],
                row["candidate_order"],
                row["substitute_for_candidate_order"],
            ),
        ).fetchone()
        base_id = (
            str(base["candidate_occurrence_id"])
            if base is not None
            and _semantic(str(base["full_name"])) == _semantic(str(row["full_name"]))
            else None
        )
        effective_id = _identity(
            "boe-effective-candidate",
            str(candidacy["candidacy_id"]),
            row["candidate_type_code"],
            row["candidate_order"],
            row["substitute_for_candidate_order"],
        )
        row_payload = {
            "effective_candidate_occurrence_id": effective_id,
            "candidacy_id": str(candidacy["candidacy_id"]),
            "candidate_type_code": row["candidate_type_code"],
            "candidate_order": row["candidate_order"],
            "substitute_for_candidate_order": row["substitute_for_candidate_order"],
            "full_name": row["full_name"],
            "effective_source_document_id": spec.correction_document_id,
            "source_text_exact": row["source_text_exact"],
            "source_paragraph_number": row["source_paragraph_number"],
        }
        conn.execute(
            """
            INSERT INTO boe_election_effective_candidate_occurrences (
              effective_candidate_occurrence_id, candidacy_id,
              base_candidate_occurrence_id, base_document_id, election_id,
              election_date, election_type_code, electoral_board,
              electoral_district, chamber_code, candidacy_number,
              candidate_order, candidate_type_code,
              substitute_for_candidate_order, full_name,
              effective_source_document_id, effective_source_url,
              effective_source_content_sha256, source_text_exact,
              source_paragraph_number, correction_operation_id,
              row_content_sha256, materialized_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                effective_id,
                str(candidacy["candidacy_id"]),
                base_id,
                str(candidacy["base_document_id"]),
                str(candidacy["election_id"]),
                str(candidacy["election_date"]),
                str(candidacy["election_type_code"]),
                str(candidacy["electoral_board"]),
                str(candidacy["electoral_district"]),
                str(candidacy["chamber_code"]),
                int(candidacy["candidacy_number"]),
                int(row["candidate_order"]),
                str(row["candidate_type_code"]),
                row["substitute_for_candidate_order"],
                str(row["full_name"]),
                spec.correction_document_id,
                str(source["source_url"]),
                str(source["source_content_sha256"]),
                str(row["source_text_exact"]),
                int(row["source_paragraph_number"]),
                operation_id,
                _effective_row_hash(row_payload),
                now_iso,
            ),
        )
    if spec.operation_type == "replace_candidacy_status_and_list":
        first = paragraph_rows[spec.evidence_paragraphs[0]]
        conn.execute(
            """
            UPDATE boe_election_effective_candidacies
            SET proclamation_status='proclaimed',
                effective_source_document_id=?, effective_source_url=?,
                effective_source_content_sha256=?, source_text_exact=?,
                source_paragraph_number=?, correction_operation_id=?,
                materialized_at=?
            WHERE candidacy_id=?
            """,
            (
                spec.correction_document_id,
                str(source["source_url"]),
                str(source["source_content_sha256"]),
                "\n".join(str(row["source_text_exact"]) for row in evidence),
                int(first["source_paragraph_number"]),
                operation_id,
                now_iso,
                str(candidacy["candidacy_id"]),
            ),
        )
    return {
        "operation_id": operation_id,
        "base_match_state": "replacement_scope_matches",
        "replacement_rows": len(after_rows),
    }


def _seed_effective_state(conn: sqlite3.Connection, now_iso: str) -> None:
    reviewed_placeholders = ", ".join("?" for _ in REVIEWED_BASE_DOCUMENT_IDS)
    reviewed_filter = (
        "document.correction_state IN ('none_declared', 'applied') "
        f"OR document.document_id IN ({reviewed_placeholders})"
    )
    conn.execute("DELETE FROM boe_election_effective_candidate_occurrences")
    conn.execute("DELETE FROM boe_election_effective_candidacies")
    conn.execute("DELETE FROM boe_election_candidate_correction_operations")
    conn.execute(
        f"""
        INSERT INTO boe_election_effective_candidacies (
          candidacy_id, base_document_id, election_id, election_date,
          election_type_code, electoral_board, electoral_district,
          chamber_code, candidacy_number, candidacy_name, party_id,
          proclamation_status, effective_source_document_id,
          effective_source_url, effective_source_content_sha256,
          source_text_exact, source_paragraph_number,
          correction_operation_id, materialized_at
        )
        SELECT candidacy.candidacy_id, candidacy.document_id,
               document.election_id, document.election_date,
               document.election_type_code, candidacy.electoral_board,
               candidacy.electoral_district, candidacy.chamber_code,
               candidacy.candidacy_number, candidacy.candidacy_name,
               candidacy.party_id,
               candidacy.proclamation_status, document.document_id,
               document.source_url, document.source_content_sha256,
               candidacy.source_text_exact, candidacy.source_paragraph_number,
               NULL, ?
        FROM boe_election_candidacies AS candidacy
        JOIN boe_election_candidate_documents AS document
          ON document.document_id=candidacy.document_id
        WHERE {reviewed_filter}
        """,
        (now_iso, *REVIEWED_BASE_DOCUMENT_IDS),
    )
    conn.execute(
        f"""
        INSERT INTO boe_election_effective_candidate_occurrences (
          effective_candidate_occurrence_id, candidacy_id,
          base_candidate_occurrence_id, base_document_id, election_id,
          election_date, election_type_code, electoral_board,
          electoral_district, chamber_code, candidacy_number,
          candidate_order, candidate_type_code,
          substitute_for_candidate_order, full_name,
          effective_source_document_id, effective_source_url,
          effective_source_content_sha256, source_text_exact,
          source_paragraph_number, correction_operation_id,
          row_content_sha256, materialized_at
        )
        SELECT candidate.candidate_occurrence_id, candidate.candidacy_id,
               candidate.candidate_occurrence_id, candidate.document_id,
               candidate.election_id, candidate.election_date,
               candidate.election_type_code, candidate.electoral_board,
               candidate.electoral_district, candidate.chamber_code,
               candidate.candidacy_number, candidate.candidate_order,
               candidate.candidate_type_code,
               candidate.substitute_for_candidate_order, candidate.full_name,
               candidate.document_id, candidate.source_url,
               candidate.source_content_sha256, candidate.source_text_exact,
               candidate.source_paragraph_number, NULL,
               candidate.row_content_sha256, ?
        FROM boe_election_candidate_occurrences AS candidate
        JOIN boe_election_candidate_documents AS document
          ON document.document_id=candidate.document_id
        WHERE {reviewed_filter}
        """,
        (now_iso, *REVIEWED_BASE_DOCUMENT_IDS),
    )


def _effective_snapshot_date(
    conn: sqlite3.Connection, requested_snapshot_date: str | None
) -> str:
    if requested_snapshot_date:
        return datetime.fromisoformat(str(requested_snapshot_date)).date().isoformat()
    row = conn.execute(
        """
        SELECT MAX(snapshot_date)
        FROM (
          SELECT last_seen_snapshot_date AS snapshot_date
          FROM boe_election_candidate_documents
          UNION ALL
          SELECT last_seen_snapshot_date AS snapshot_date
          FROM boe_election_candidate_correction_documents
        )
        """
    ).fetchone()
    if row is None or not row[0]:
        raise CorrectionMaterializationError(
            "effective candidate snapshot date is unavailable"
        )
    return datetime.fromisoformat(str(row[0])).date().isoformat()


def _materialize_effective_lineage(
    conn: sqlite3.Connection, *, snapshot_date: str, now_iso: str
) -> dict[str, int]:
    """Attach normalized lineage without asserting cross-source person identity."""
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        SELECT candidacy_name, NULL, ?, ?
        FROM boe_election_effective_candidacies
        GROUP BY candidacy_name
        ON CONFLICT(name) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        UPDATE boe_election_effective_candidacies
        SET party_id=(
          SELECT party_id FROM parties
          WHERE parties.name=boe_election_effective_candidacies.candidacy_name
        )
        """
    )

    rows = conn.execute(
        """
        SELECT effective.*, candidacy.party_id AS effective_party_id,
               base.full_name AS base_full_name,
               base.person_id AS base_person_id,
               base.source_record_pk AS base_source_record_pk,
               base.first_seen_snapshot_date AS base_first_seen_snapshot_date,
               base.last_seen_snapshot_date AS base_last_seen_snapshot_date,
               operation.evidence_paragraph_numbers_json,
               operation.before_value_json, operation.after_value_json,
               operation.evidence_text_sha256,
               COALESCE(correction.document_source_record_pk,
                        document.document_source_record_pk)
                 AS effective_document_source_record_pk
        FROM boe_election_effective_candidate_occurrences AS effective
        JOIN boe_election_effective_candidacies AS candidacy
          ON candidacy.candidacy_id=effective.candidacy_id
        LEFT JOIN boe_election_candidate_occurrences AS base
          ON base.candidate_occurrence_id=effective.base_candidate_occurrence_id
        LEFT JOIN boe_election_candidate_correction_operations AS operation
          ON operation.correction_operation_id=effective.correction_operation_id
        LEFT JOIN boe_election_candidate_correction_documents AS correction
          ON correction.correction_document_id=effective.effective_source_document_id
        LEFT JOIN boe_election_candidate_documents AS document
          ON document.document_id=effective.effective_source_document_id
        ORDER BY effective.effective_candidate_occurrence_id
        """
    ).fetchall()
    correction_source_records = 0
    correction_scoped_people = 0
    base_reused_people = 0
    for row in rows:
        corrected = row["correction_operation_id"] is not None
        exact_base_identity = row["base_person_id"] is not None and _semantic(
            str(row["base_full_name"])
        ) == _semantic(str(row["full_name"]))
        if exact_base_identity:
            person_id = int(row["base_person_id"])
            base_reused_people += 1
        else:
            canonical_key = _identity(
                "boe-effective-candidate-person",
                str(row["effective_candidate_occurrence_id"]),
                str(row["full_name"]),
            )
            conn.execute(
                """
                INSERT INTO persons (
                  full_name, given_name, family_name, gender, birth_date,
                  territory_code, canonical_key, created_at, updated_at
                ) VALUES (?, NULL, NULL, NULL, NULL, '', ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET
                  full_name=excluded.full_name, updated_at=excluded.updated_at
                """,
                (str(row["full_name"]), canonical_key, now_iso, now_iso),
            )
            person_id = int(
                conn.execute(
                    "SELECT person_id FROM persons WHERE canonical_key=?",
                    (canonical_key,),
                ).fetchone()[0]
            )
            correction_scoped_people += 1

        if corrected:
            source_record_id = _identity(
                "boe-effective-candidate-source-record",
                str(row["effective_candidate_occurrence_id"]),
                str(row["correction_operation_id"]),
            )
            raw_payload = _json(
                {
                    "record_type": "derived_effective_boe_candidate_occurrence",
                    "candidate_occurrence_id": str(
                        row["effective_candidate_occurrence_id"]
                    ),
                    "base_candidate_occurrence_id": row["base_candidate_occurrence_id"],
                    "full_name": str(row["full_name"]),
                    "candidate_order": int(row["candidate_order"]),
                    "candidate_type_code": str(row["candidate_type_code"]),
                    "substitute_for_candidate_order": row[
                        "substitute_for_candidate_order"
                    ],
                    "correction_operation_id": str(row["correction_operation_id"]),
                    "effective_source_document_id": str(
                        row["effective_source_document_id"]
                    ),
                    "effective_source_url": str(row["effective_source_url"]),
                    "effective_source_content_sha256": str(
                        row["effective_source_content_sha256"]
                    ),
                    "source_paragraph_number": int(row["source_paragraph_number"]),
                    "source_text_exact": str(row["source_text_exact"]),
                    "evidence_paragraph_numbers": json.loads(
                        str(row["evidence_paragraph_numbers_json"])
                    ),
                    "before_value": json.loads(str(row["before_value_json"])),
                    "after_value": json.loads(str(row["after_value_json"])),
                    "evidence_text_sha256": str(row["evidence_text_sha256"]),
                }
            )
            conn.execute(
                """
                INSERT INTO source_records (
                  source_id, source_record_id, source_snapshot_date, raw_payload,
                  content_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, source_record_id) DO UPDATE SET
                  source_snapshot_date=excluded.source_snapshot_date,
                  raw_payload=excluded.raw_payload,
                  content_sha256=excluded.content_sha256,
                  updated_at=excluded.updated_at
                """,
                (
                    SOURCE_ID,
                    source_record_id,
                    snapshot_date,
                    raw_payload,
                    str(row["row_content_sha256"]),
                    now_iso,
                    now_iso,
                ),
            )
            source_record_pk = int(
                conn.execute(
                    """
                    SELECT source_record_pk FROM source_records
                    WHERE source_id=? AND source_record_id=?
                    """,
                    (SOURCE_ID, source_record_id),
                ).fetchone()[0]
            )
            first_seen = snapshot_date
            last_seen = snapshot_date
            correction_source_records += 1
            identity_state = "source_scoped_correction_exact"
        else:
            if row["base_source_record_pk"] is None:
                raise CorrectionMaterializationError(
                    "uncorrected effective candidate lacks base source record: "
                    + str(row["effective_candidate_occurrence_id"])
                )
            source_record_pk = int(row["base_source_record_pk"])
            first_seen = str(row["base_first_seen_snapshot_date"])
            last_seen = str(row["base_last_seen_snapshot_date"])
            identity_state = "source_scoped_base_exact"

        document_source_record_pk = row["effective_document_source_record_pk"]
        if document_source_record_pk is None or row["effective_party_id"] is None:
            raise CorrectionMaterializationError(
                "effective candidate document or party lineage is incomplete: "
                + str(row["effective_candidate_occurrence_id"])
            )
        conn.execute(
            """
            UPDATE boe_election_effective_candidate_occurrences
            SET person_id=?, party_id=?, source_id=?, source_record_pk=?,
                document_source_record_pk=?, first_seen_snapshot_date=?,
                last_seen_snapshot_date=?, is_present=1,
                person_identity_state=?
            WHERE effective_candidate_occurrence_id=?
            """,
            (
                person_id,
                int(row["effective_party_id"]),
                SOURCE_ID,
                source_record_pk,
                int(document_source_record_pk),
                first_seen,
                last_seen,
                identity_state,
                str(row["effective_candidate_occurrence_id"]),
            ),
        )
    return {
        "rows": len(rows),
        "base_reused_people": base_reused_people,
        "correction_scoped_people": correction_scoped_people,
        "correction_source_records": correction_source_records,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    now_iso = utc_now()
    conn = open_db(Path(args.db))
    operations: list[dict[str, Any]] = []
    try:
        apply_schema(conn, Path(args.schema))
        conn.row_factory = sqlite3.Row
        snapshot_date = _effective_snapshot_date(conn, args.snapshot_date)
        _seed_effective_state(conn, now_iso)
        paragraph_cache = {
            correction_id: _paragraphs(conn, correction_id)
            for correction_id in EXPECTED_OPERATION_COUNTS
        }
        specs: list[SimpleSpec | ListSpec] = sorted(
            [*SIMPLE_SPECS, *LIST_SPECS],
            key=lambda spec: (
                spec.correction_document_id,
                spec.selector.base_document_id,
                spec.operation_order,
            ),
        )
        for spec in specs:
            rows = paragraph_cache[spec.correction_document_id]
            if isinstance(spec, SimpleSpec):
                result = _apply_simple(conn, spec, rows, now_iso)
            else:
                result = _apply_list(conn, spec, rows, now_iso)
            operations.append(
                {
                    "correction_document_id": spec.correction_document_id,
                    "base_document_id": spec.selector.base_document_id,
                    "operation_order": spec.operation_order,
                    "operation_type": spec.operation_type,
                    **result,
                }
            )
        lineage = _materialize_effective_lineage(
            conn, snapshot_date=snapshot_date, now_iso=now_iso
        )
        observed_by_document = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                """
                SELECT correction_document_id, COUNT(*)
                FROM boe_election_candidate_correction_operations
                GROUP BY correction_document_id
                """
            )
        }
        if observed_by_document != EXPECTED_OPERATION_COUNTS:
            raise CorrectionMaterializationError(
                f"correction operation totals drifted: {observed_by_document}"
            )
        conn.execute(
            """
            UPDATE boe_election_candidate_correction_documents
            SET application_state='applied', updated_at=?
            WHERE correction_document_id IN (?, ?, ?)
            """,
            (now_iso, *sorted(EXPECTED_OPERATION_COUNTS)),
        )
        conn.execute(
            """
            UPDATE boe_election_candidate_documents
            SET correction_state='applied', updated_at=?
            WHERE document_id IN (
              SELECT DISTINCT base_document_id
              FROM boe_election_candidate_correction_operations
            )
            """,
            (now_iso,),
        )
        captured_base_candidacies = int(
            conn.execute("SELECT COUNT(*) FROM boe_election_candidacies").fetchone()[0]
        )
        captured_base_candidates = int(
            conn.execute(
                "SELECT COUNT(*) FROM boe_election_candidate_occurrences"
            ).fetchone()[0]
        )
        captured_base_documents, declared_candidacies, declared_candidates = (
            int(value)
            for value in conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(candidacy_rows), 0),
                       COALESCE(SUM(candidate_rows), 0)
                FROM boe_election_candidate_documents
                """
            ).fetchone()
        )
        reviewed_placeholders = ", ".join("?" for _ in REVIEWED_BASE_DOCUMENT_IDS)
        reviewed_base_documents, reviewed_base_candidacies, reviewed_base_candidates = (
            int(value)
            for value in conn.execute(
                f"""
                SELECT COUNT(*), COALESCE(SUM(candidacy_rows), 0),
                       COALESCE(SUM(candidate_rows), 0)
                FROM boe_election_candidate_documents
                WHERE correction_state IN ('none_declared', 'applied')
                   OR document_id IN ({reviewed_placeholders})
                """,
                REVIEWED_BASE_DOCUMENT_IDS,
            ).fetchone()
        )
        pending_base_documents = captured_base_documents - reviewed_base_documents
        pending_base_candidacies = captured_base_candidacies - reviewed_base_candidacies
        pending_base_candidates = captured_base_candidates - reviewed_base_candidates
        effective_candidacies = int(
            conn.execute(
                "SELECT COUNT(*) FROM boe_election_effective_candidacies"
            ).fetchone()[0]
        )
        effective_candidates = int(
            conn.execute(
                "SELECT COUNT(*) FROM boe_election_effective_candidate_occurrences"
            ).fetchone()[0]
        )
        corrected_effective_candidates = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE correction_operation_id IS NOT NULL
                """
            ).fetchone()[0]
        )
        corrected_candidacies = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM boe_election_effective_candidacies
                WHERE correction_operation_id IS NOT NULL
                """
            ).fetchone()[0]
        )
        applied_documents = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM boe_election_candidate_correction_documents
                WHERE application_state='applied'
                """
            ).fetchone()[0]
        )
        captured_correction_documents = int(
            conn.execute(
                "SELECT COUNT(*) FROM boe_election_candidate_correction_documents"
            ).fetchone()[0]
        )
        pending_correction_documents = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM boe_election_candidate_correction_documents
                WHERE application_state='captured_unapplied'
                """
            ).fetchone()[0]
        )
        exact_evidence_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE TRIM(full_name)<>'' AND TRIM(source_text_exact)<>''
                  AND effective_source_url LIKE 'https://www.boe.es/%'
                  AND LENGTH(effective_source_content_sha256)=64
                """
            ).fetchone()[0]
        )
        normalized_lineage_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences AS candidate
                JOIN persons AS person ON person.person_id=candidate.person_id
                JOIN parties AS party ON party.party_id=candidate.party_id
                JOIN sources AS source ON source.source_id=candidate.source_id
                JOIN source_records AS source_record
                  ON source_record.source_record_pk=candidate.source_record_pk
                JOIN source_records AS document_source
                  ON document_source.source_record_pk=
                     candidate.document_source_record_pk
                WHERE candidate.source_id=?
                  AND candidate.first_seen_snapshot_date<>''
                  AND candidate.last_seen_snapshot_date<>''
                  AND candidate.is_present=1
                  AND candidate.person_identity_state IN (
                    'source_scoped_base_exact',
                    'source_scoped_correction_exact'
                  )
                """,
                (SOURCE_ID,),
            ).fetchone()[0]
        )
        corrected_source_record_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences AS candidate
                JOIN source_records AS source_record
                  ON source_record.source_record_pk=candidate.source_record_pk
                WHERE candidate.correction_operation_id IS NOT NULL
                  AND source_record.source_record_id LIKE
                      'boe-effective-candidate-source-record:%'
                  AND source_record.raw_payload LIKE
                      '%derived_effective_boe_candidate_occurrence%'
                """
            ).fetchone()[0]
        )
        correction_evidence_person_links = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE person_identity_state='source_scoped_correction_exact'
                """
            ).fetchone()[0]
        )
        already_effective = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_candidate_correction_operations
                WHERE base_match_state='already_effective_after_matches'
                """
            ).fetchone()[0]
        )
        partial_base_matches = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_candidate_correction_operations
                WHERE base_match_state='partial_base_matches'
                """
            ).fetchone()[0]
        )
        captured_correction_paragraphs = int(
            conn.execute(
                "SELECT COUNT(*) FROM boe_election_candidate_correction_paragraphs"
            ).fetchone()[0]
        )
        declared_correction_paragraphs = int(
            conn.execute(
                """
                SELECT COALESCE(SUM(paragraph_rows), 0)
                FROM boe_election_candidate_correction_documents
                """
            ).fetchone()[0]
        )
        reviewed_correction_paragraphs = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_candidate_correction_paragraphs AS paragraph
                JOIN boe_election_candidate_correction_documents AS document
                  ON document.correction_document_id=
                     paragraph.correction_document_id
                WHERE document.application_state='applied'
                """
            ).fetchone()[0]
        )
        pending_correction_paragraphs = (
            captured_correction_paragraphs - reviewed_correction_paragraphs
        )
        referenced_correction_paragraphs = {
            (str(correction_document_id), int(paragraph_number))
            for correction_document_id, paragraph_numbers_json in conn.execute(
                """
                SELECT correction_document_id, evidence_paragraph_numbers_json
                FROM boe_election_candidate_correction_operations
                """
            )
            for paragraph_number in json.loads(str(paragraph_numbers_json))
        }
        correction_paragraphs_referenced = len(referenced_correction_paragraphs)
        reviewed_contextual_correction_paragraphs = (
            reviewed_correction_paragraphs - correction_paragraphs_referenced
        )
        pending_effective_candidacies = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidacies AS effective
                JOIN boe_election_candidate_documents AS document
                  ON document.document_id=effective.base_document_id
                WHERE document.correction_state='pending'
                """
            ).fetchone()[0]
        )
        pending_effective_candidates = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences AS effective
                JOIN boe_election_candidate_documents AS document
                  ON document.document_id=effective.base_document_id
                WHERE document.correction_state='pending'
                """
            ).fetchone()[0]
        )
        foreign_key_violations = len(
            conn.execute("PRAGMA foreign_key_check").fetchall()
        )
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        checks = {
            "all_reviewed_correction_documents_applied": applied_documents == 3,
            "all_correction_documents_classified": (
                applied_documents + pending_correction_documents
                == captured_correction_documents
            ),
            "all_operations_materialized": len(operations) == 17,
            "captured_base_candidacies_preserved": (
                captured_base_candidacies == declared_candidacies
            ),
            "captured_base_candidates_preserved": (
                captured_base_candidates == declared_candidates
            ),
            "effective_candidacies_reconcile": (
                effective_candidacies == reviewed_base_candidacies
            ),
            "effective_candidates_reconcile": (
                effective_candidates == reviewed_base_candidates + 5
            ),
            "pending_base_documents_excluded_from_effective_state": (
                pending_effective_candidacies == 0 and pending_effective_candidates == 0
            ),
            "all_captured_correction_paragraphs_retained": (
                captured_correction_paragraphs == declared_correction_paragraphs
            ),
            "reviewed_correction_paragraphs_reconcile": (
                reviewed_correction_paragraphs == 180
            ),
            "operative_correction_paragraphs_reconcile": (
                correction_paragraphs_referenced == 127
            ),
            "contextual_correction_paragraphs_reconcile": (
                reviewed_contextual_correction_paragraphs == 53
            ),
            "all_effective_candidate_evidence_exact": (
                exact_evidence_rows == effective_candidates
            ),
            "all_effective_candidate_lineage_normalized": (
                normalized_lineage_rows == effective_candidates
            ),
            "all_corrected_rows_have_immutable_effective_source_records": (
                corrected_source_record_rows == corrected_effective_candidates == 88
            ),
            "all_corrected_people_remain_source_scoped": (
                correction_evidence_person_links == corrected_effective_candidates == 88
            ),
            "changed_or_new_person_links_reconcile": (
                lineage["correction_scoped_people"] == 25
            ),
            "hybrid_base_correction_state_classified": partial_base_matches == 1,
            "foreign_key_check_passed": foreign_key_violations == 0,
            "quick_check_passed": quick_check == "ok",
        }
        status = "ok" if all(checks.values()) else "failed"
        report = {
            "schema_version": "boe_candidate_correction_materialization_v2",
            "generated_at": now_iso,
            "snapshot_date": snapshot_date,
            "status": status,
            "materializer_version": MATERIALIZER_VERSION,
            "policy": {
                "base_proclamation_rows_mutated": False,
                "official_public_domain_personal_information_retained": True,
                "identity_fields_removed": 0,
                "cross_source_person_identity_inferred": False,
                "synthetic_or_mock_records_counted": False,
                "pending_official_corrections_explicit": (
                    pending_correction_documents > 0
                ),
                "pending_correction_evidence_excluded_from_effective_state": True,
                "remote_mutation_performed": False,
            },
            "totals": {
                "correction_documents_captured": captured_correction_documents,
                "correction_documents_applied": applied_documents,
                "correction_documents_pending_review": pending_correction_documents,
                "correction_operations": len(operations),
                "correction_paragraphs_retained": captured_correction_paragraphs,
                "reviewed_correction_paragraphs": reviewed_correction_paragraphs,
                "pending_correction_paragraphs": pending_correction_paragraphs,
                "correction_paragraphs_referenced_by_operations": (
                    correction_paragraphs_referenced
                ),
                "contextual_correction_paragraphs_retained": (
                    reviewed_contextual_correction_paragraphs
                ),
                "already_effective_operations": already_effective,
                "partial_base_match_operations": partial_base_matches,
                "captured_base_documents": captured_base_documents,
                "captured_base_candidacies": captured_base_candidacies,
                "captured_base_candidates": captured_base_candidates,
                "reviewed_base_documents": reviewed_base_documents,
                "reviewed_base_candidacies": reviewed_base_candidacies,
                "reviewed_base_candidates": reviewed_base_candidates,
                "pending_base_documents": pending_base_documents,
                "pending_base_candidacies": pending_base_candidacies,
                "pending_base_candidates": pending_base_candidates,
                "base_candidacies": reviewed_base_candidacies,
                "base_candidates": reviewed_base_candidates,
                "effective_candidacies": effective_candidacies,
                "effective_candidates": effective_candidates,
                "effective_candidate_delta": (
                    effective_candidates - reviewed_base_candidates
                ),
                "corrected_effective_candidacies": corrected_candidacies,
                "corrected_effective_candidates": corrected_effective_candidates,
                "exact_effective_candidate_evidence_rows": exact_evidence_rows,
                "normalized_effective_candidate_lineage_rows": (
                    normalized_lineage_rows
                ),
                "base_exact_person_links_reused": lineage["base_reused_people"],
                "correction_evidence_person_links": (correction_evidence_person_links),
                "changed_or_new_source_scoped_people": (
                    lineage["correction_scoped_people"]
                ),
                "corrected_effective_source_records": (corrected_source_record_rows),
                "foreign_key_violations": foreign_key_violations,
            },
            "operations": operations,
            "checks": checks,
        }
        if args.enforce and status != "ok":
            failed = sorted(key for key, value in checks.items() if not value)
            raise CorrectionMaterializationError(
                f"BOE correction materialization checks failed: {failed}"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _write_json(Path(args.report_out), report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
