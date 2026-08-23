"""Typed, incremental Parquet publication for official candidate occurrences."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    public_http_url,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

CANDIDATE_OCCURRENCE_CONTRACT = SemanticLaneContract(
    lane="candidate_occurrences",
    transformer_version="candidate_occurrences_public_v3",
    id_column="candidate_occurrence_id",
    year_column="election_year",
    schema=(
        {"name": "candidate_occurrence_id", "type": "string", "nullable": False},
        {"name": "source_system_code", "type": "string", "nullable": False},
        {"name": "archive_id", "type": "string", "nullable": True},
        {"name": "election_id", "type": "string", "nullable": False},
        {"name": "election_date", "type": "string", "nullable": False},
        {"name": "election_type_code", "type": "string", "nullable": False},
        {"name": "election_scope", "type": "string", "nullable": False},
        {"name": "election_year", "type": "int64", "nullable": False},
        {"name": "election_month", "type": "int64", "nullable": False},
        {"name": "election_round", "type": "string", "nullable": True},
        {"name": "province_code", "type": "string", "nullable": True},
        {"name": "district_code", "type": "string", "nullable": True},
        {"name": "candidate_scope_code", "type": "string", "nullable": True},
        {"name": "party_source_code", "type": "string", "nullable": True},
        {"name": "candidate_order", "type": "int64", "nullable": False},
        {"name": "candidate_type_code", "type": "string", "nullable": False},
        {"name": "substitute_for_candidate_order", "type": "int64", "nullable": True},
        {"name": "given_name", "type": "string", "nullable": True},
        {"name": "surname_1", "type": "string", "nullable": True},
        {"name": "surname_2", "type": "string", "nullable": True},
        {"name": "full_name", "type": "string", "nullable": False},
        {"name": "gender_code", "type": "string", "nullable": True},
        {"name": "birth_date", "type": "string", "nullable": True},
        {"name": "birth_date_source", "type": "string", "nullable": True},
        {"name": "dni", "type": "string", "nullable": True},
        {"name": "is_elected", "type": "int64", "nullable": True},
        {"name": "candidacy_id", "type": "string", "nullable": True},
        {"name": "candidacy_name", "type": "string", "nullable": False},
        {"name": "candidacy_acronym", "type": "string", "nullable": True},
        {"name": "party_province_code", "type": "string", "nullable": True},
        {"name": "party_autonomy_code", "type": "string", "nullable": True},
        {"name": "party_national_code", "type": "string", "nullable": True},
        {"name": "electoral_board", "type": "string", "nullable": True},
        {"name": "electoral_district", "type": "string", "nullable": True},
        {"name": "chamber_code", "type": "string", "nullable": True},
        {"name": "candidacy_number", "type": "int64", "nullable": True},
        {"name": "person_id", "type": "int64", "nullable": False},
        {"name": "party_id", "type": "int64", "nullable": False},
        {"name": "territory_id", "type": "int64", "nullable": True},
        {"name": "territory_code", "type": "string", "nullable": True},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_record_id", "type": "string", "nullable": False},
        {"name": "source_record_pk", "type": "int64", "nullable": False},
        {"name": "document_source_record_pk", "type": "int64", "nullable": True},
        {"name": "source_url", "type": "string", "nullable": True},
        {"name": "source_content_sha256", "type": "string", "nullable": False},
        {"name": "source_member_name", "type": "string", "nullable": True},
        {"name": "source_line_number", "type": "int64", "nullable": False},
        {"name": "source_document_id", "type": "string", "nullable": True},
        {"name": "base_document_id", "type": "string", "nullable": True},
        {"name": "base_candidate_occurrence_id", "type": "string", "nullable": True},
        {"name": "correction_operation_id", "type": "string", "nullable": True},
        {"name": "source_text_exact", "type": "string", "nullable": True},
        {"name": "row_content_sha256", "type": "string", "nullable": True},
        {"name": "first_seen_snapshot_date", "type": "string", "nullable": False},
        {"name": "last_seen_snapshot_date", "type": "string", "nullable": False},
        {"name": "is_present", "type": "int64", "nullable": False},
        {"name": "person_identity_state", "type": "string", "nullable": False},
        {"name": "lineage_state", "type": "string", "nullable": False},
    ),
)


CANDIDATE_OCCURRENCE_SQL = """
SELECT
  candidate.candidate_occurrence_id,
  'infoelectoral' AS source_system_code,
  candidate.archive_id,
  archive.election_id,
  candidate.election_date,
  candidate.election_type_code,
  candidate.election_year,
  candidate.election_month,
  candidate.election_round,
  candidate.province_code,
  candidate.district_code,
  candidate.candidate_scope_code,
  candidate.party_source_code,
  candidate.candidate_order,
  candidate.candidate_type_code,
  NULL AS substitute_for_candidate_order,
  candidate.given_name,
  candidate.surname_1,
  candidate.surname_2,
  candidate.full_name,
  candidate.gender_code,
  candidate.birth_date,
  candidate.birth_date_source,
  candidate.dni,
  candidate.is_elected,
  NULL AS candidacy_id,
  candidate.candidacy_name,
  candidate.candidacy_acronym,
  candidate.party_province_code,
  candidate.party_autonomy_code,
  candidate.party_national_code,
  NULL AS electoral_board,
  NULL AS electoral_district,
  NULL AS chamber_code,
  NULL AS candidacy_number,
  candidate.person_id,
  candidate.party_id,
  candidate.territory_id,
  territory.code AS territory_code,
  candidate.source_id,
  source_record.source_record_id,
  candidate.source_record_pk,
  NULL AS document_source_record_pk,
  candidate.source_url,
  candidate.source_content_sha256,
  candidate.source_member_name,
  candidate.source_line_number,
  candidate.archive_id AS source_document_id,
  NULL AS base_document_id,
  NULL AS base_candidate_occurrence_id,
  NULL AS correction_operation_id,
  NULL AS source_text_exact,
  NULL AS row_content_sha256,
  candidate.first_seen_snapshot_date,
  candidate.last_seen_snapshot_date,
  candidate.is_present,
  'source_scoped_official_archive' AS person_identity_state,
  'source_record' AS lineage_state
FROM infoelectoral_candidate_occurrences AS candidate
JOIN infoelectoral_candidate_archives AS archive
  ON archive.archive_id = candidate.archive_id
JOIN persons AS person ON person.person_id = candidate.person_id
JOIN parties AS party ON party.party_id = candidate.party_id
JOIN sources AS source ON source.source_id = candidate.source_id
JOIN source_records AS source_record
  ON source_record.source_record_pk = candidate.source_record_pk
LEFT JOIN territories AS territory ON territory.territory_id = candidate.territory_id
UNION ALL
SELECT
  candidate.effective_candidate_occurrence_id AS candidate_occurrence_id,
  'boe' AS source_system_code,
  NULL AS archive_id,
  candidate.election_id,
  candidate.election_date,
  candidate.election_type_code,
  CAST(substr(candidate.election_date, 1, 4) AS INTEGER) AS election_year,
  CAST(substr(candidate.election_date, 6, 2) AS INTEGER) AS election_month,
  NULL AS election_round,
  NULL AS province_code,
  NULL AS district_code,
  NULL AS candidate_scope_code,
  NULL AS party_source_code,
  candidate.candidate_order,
  candidate.candidate_type_code,
  candidate.substitute_for_candidate_order,
  NULL AS given_name,
  NULL AS surname_1,
  NULL AS surname_2,
  candidate.full_name,
  NULL AS gender_code,
  NULL AS birth_date,
  NULL AS birth_date_source,
  NULL AS dni,
  NULL AS is_elected,
  candidate.candidacy_id,
  candidacy.candidacy_name,
  NULL AS candidacy_acronym,
  NULL AS party_province_code,
  NULL AS party_autonomy_code,
  NULL AS party_national_code,
  candidate.electoral_board,
  candidate.electoral_district,
  candidate.chamber_code,
  candidate.candidacy_number,
  candidate.person_id,
  candidate.party_id,
  NULL AS territory_id,
  NULL AS territory_code,
  candidate.source_id,
  source_record.source_record_id,
  candidate.source_record_pk,
  candidate.document_source_record_pk,
  candidate.effective_source_url AS source_url,
  candidate.effective_source_content_sha256 AS source_content_sha256,
  NULL AS source_member_name,
  candidate.source_paragraph_number AS source_line_number,
  candidate.effective_source_document_id AS source_document_id,
  candidate.base_document_id,
  candidate.base_candidate_occurrence_id,
  candidate.correction_operation_id,
  candidate.source_text_exact,
  candidate.row_content_sha256,
  candidate.first_seen_snapshot_date,
  candidate.last_seen_snapshot_date,
  candidate.is_present,
  candidate.person_identity_state,
  CASE WHEN candidate.correction_operation_id IS NULL
       THEN 'source_record'
       ELSE 'effective_correction_source_record'
  END AS lineage_state
FROM boe_election_effective_candidate_occurrences AS candidate
JOIN boe_election_effective_candidacies AS candidacy
  ON candidacy.candidacy_id=candidate.candidacy_id
JOIN persons AS person ON person.person_id=candidate.person_id
JOIN parties AS party ON party.party_id=candidate.party_id
JOIN sources AS source ON source.source_id=candidate.source_id
JOIN source_records AS source_record
  ON source_record.source_record_pk=candidate.source_record_pk
ORDER BY
  2, 6, 7, 1
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _integer(value: Any) -> int | None:
    return None if value is None else int(value)


def election_scope(election_type_code: str) -> str:
    return {
        "02": "congress",
        "03": "senate",
        "04": "municipal",
        "06": "island-council",
        "07": "european",
        "general_cortes": "general-cortes",
        "european_parliament": "european",
    }.get(str(election_type_code), "type-" + safe_component(str(election_type_code)))


def _public_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "candidate_occurrence_id": str(row["candidate_occurrence_id"]),
        "source_system_code": str(row["source_system_code"]),
        "archive_id": _text(row["archive_id"]),
        "election_id": str(row["election_id"]),
        "election_date": str(row["election_date"]),
        "election_type_code": str(row["election_type_code"]),
        "election_scope": election_scope(str(row["election_type_code"])),
        "election_year": int(row["election_year"]),
        "election_month": int(row["election_month"]),
        "election_round": _text(row["election_round"]),
        "province_code": _text(row["province_code"]),
        "district_code": _text(row["district_code"]),
        "candidate_scope_code": _text(row["candidate_scope_code"]),
        "party_source_code": _text(row["party_source_code"]),
        "candidate_order": int(row["candidate_order"]),
        "candidate_type_code": str(row["candidate_type_code"]),
        "substitute_for_candidate_order": _integer(
            row["substitute_for_candidate_order"]
        ),
        "given_name": _text(row["given_name"]),
        "surname_1": _text(row["surname_1"]),
        "surname_2": _text(row["surname_2"]),
        "full_name": str(row["full_name"]),
        "gender_code": _text(row["gender_code"]),
        "birth_date": _text(row["birth_date"]),
        "birth_date_source": _text(row["birth_date_source"]),
        "dni": _text(row["dni"]),
        "is_elected": _integer(row["is_elected"]),
        "candidacy_id": _text(row["candidacy_id"]),
        "candidacy_name": str(row["candidacy_name"]),
        "candidacy_acronym": _text(row["candidacy_acronym"]),
        "party_province_code": _text(row["party_province_code"]),
        "party_autonomy_code": _text(row["party_autonomy_code"]),
        "party_national_code": _text(row["party_national_code"]),
        "electoral_board": _text(row["electoral_board"]),
        "electoral_district": _text(row["electoral_district"]),
        "chamber_code": _text(row["chamber_code"]),
        "candidacy_number": _integer(row["candidacy_number"]),
        "person_id": int(row["person_id"]),
        "party_id": int(row["party_id"]),
        "territory_id": _integer(row["territory_id"]),
        "territory_code": _text(row["territory_code"]),
        "source_id": str(row["source_id"]),
        "source_record_id": str(row["source_record_id"]),
        "source_record_pk": int(row["source_record_pk"]),
        "document_source_record_pk": _integer(row["document_source_record_pk"]),
        "source_url": public_http_url(row["source_url"]),
        "source_content_sha256": str(row["source_content_sha256"]),
        "source_member_name": _text(row["source_member_name"]),
        "source_line_number": int(row["source_line_number"]),
        "source_document_id": _text(row["source_document_id"]),
        "base_document_id": _text(row["base_document_id"]),
        "base_candidate_occurrence_id": _text(row["base_candidate_occurrence_id"]),
        "correction_operation_id": _text(row["correction_operation_id"]),
        "source_text_exact": _text(row["source_text_exact"]),
        "row_content_sha256": _text(row["row_content_sha256"]),
        "first_seen_snapshot_date": str(row["first_seen_snapshot_date"]),
        "last_seen_snapshot_date": str(row["last_seen_snapshot_date"]),
        "is_present": int(row["is_present"]),
        "person_identity_state": str(row["person_identity_state"]),
        "lineage_state": str(row["lineage_state"]),
    }


def _iter_rows(db_path: Path) -> Iterator[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(CANDIDATE_OCCURRENCE_SQL):
            yield _public_row(row)
    finally:
        conn.close()


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["source_system_code"]),
        str(row["election_type_code"]),
        str(row["election_year"]),
    )


def _partition_id(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str]) -> Path:
    source_system, election_type, year = key
    return Path(
        f"lane={CANDIDATE_OCCURRENCE_CONTRACT.lane}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"source_system={safe_component(source_system)}",
        f"election_type={safe_component(election_type)}",
        f"year={safe_component(year)}",
    )


def _new_partition(snapshot_date: str, key: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(key),
        "values": {
            "snapshot_date": snapshot_date,
            "source_system": key[0],
            "election_type": key[1],
            "year": key[2],
        },
        "relative_dir": _partition_dir(snapshot_date, key).as_posix(),
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "source_url_rows": 0,
        "source_record_rows": 0,
        "elected_rows": 0,
        "present_rows": 0,
        "birth_date_rows": 0,
        "birth_date_source_rows": 0,
        "dni_rows": 0,
        "infoelectoral_rows": 0,
        "boe_rows": 0,
        "correction_backed_rows": 0,
        "exact_public_name_rows": 0,
        "exact_source_text_rows": 0,
        "document_source_record_rows": 0,
        "outcome_known_rows": 0,
        "private_token_findings": 0,
        "_digest": hashlib.sha256(),
    }


def scan_candidate_occurrence_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    totals = {
        "rows": 0,
        "source_url_rows": 0,
        "source_record_rows": 0,
        "elected_rows": 0,
        "present_rows": 0,
        "birth_date_rows": 0,
        "birth_date_source_rows": 0,
        "dni_rows": 0,
        "infoelectoral_rows": 0,
        "boe_rows": 0,
        "correction_backed_rows": 0,
        "exact_public_name_rows": 0,
        "exact_source_text_rows": 0,
        "document_source_record_rows": 0,
        "outcome_known_rows": 0,
        "private_token_findings": 0,
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str] | None = None
    previous_id: str | None = None
    for row in _iter_rows(db_path):
        key = _partition_key(row)
        if current_key != key:
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(snapshot_date, key)
            previous_id = None
        assert current is not None
        row_id = str(row["candidate_occurrence_id"])
        if previous_id is not None and row_id <= previous_id:
            raise RuntimeError(
                "candidate-occurrence input is not ordered within partition"
            )
        previous_id = row_id
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(current["min_id"], row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(current["max_id"], row_id)
        )
        if row["source_url"]:
            current["source_url_rows"] += 1
            totals["source_url_rows"] += 1
        if row["source_record_pk"]:
            current["source_record_rows"] += 1
            totals["source_record_rows"] += 1
        if row["is_elected"] is not None:
            current["outcome_known_rows"] += 1
            totals["outcome_known_rows"] += 1
            if int(row["is_elected"]):
                current["elected_rows"] += 1
                totals["elected_rows"] += 1
        if int(row["is_present"]):
            current["present_rows"] += 1
            totals["present_rows"] += 1
        for metric, field in (
            ("birth_date_rows", "birth_date"),
            ("birth_date_source_rows", "birth_date_source"),
            ("dni_rows", "dni"),
        ):
            if row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        source_metric = str(row["source_system_code"]) + "_rows"
        current[source_metric] += 1
        totals[source_metric] += 1
        if row["correction_operation_id"]:
            current["correction_backed_rows"] += 1
            totals["correction_backed_rows"] += 1
        if str(row["full_name"] or "").strip():
            current["exact_public_name_rows"] += 1
            totals["exact_public_name_rows"] += 1
        if str(row["source_text_exact"] or "").strip():
            current["exact_source_text_rows"] += 1
            totals["exact_source_text_rows"] += 1
        if row["document_source_record_pk"]:
            current["document_source_record_rows"] += 1
            totals["document_source_record_rows"] += 1
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        current["_digest"].update(
            CANDIDATE_OCCURRENCE_CONTRACT.canonical_row_bytes(row)
        )
        totals["rows"] += 1
    if current is not None:
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    return partitions, totals


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:

        def scalar(sql: str) -> int:
            return int(conn.execute(sql).fetchone()[0])

        info_rows = scalar("SELECT COUNT(*) FROM infoelectoral_candidate_occurrences")
        boe_rows = scalar(
            "SELECT COUNT(*) FROM boe_election_effective_candidate_occurrences"
        )
        return {
            "occurrence_rows": info_rows + boe_rows,
            "infoelectoral_rows": info_rows,
            "boe_rows": boe_rows,
            "distinct_occurrence_ids": scalar(
                """
                SELECT COUNT(DISTINCT candidate_occurrence_id) FROM (
                  SELECT candidate_occurrence_id
                  FROM infoelectoral_candidate_occurrences
                  UNION ALL
                  SELECT effective_candidate_occurrence_id
                  FROM boe_election_effective_candidate_occurrences
                )
                """
            ),
            "distinct_people": scalar(
                """
                SELECT COUNT(DISTINCT person_id) FROM (
                  SELECT person_id FROM infoelectoral_candidate_occurrences
                  UNION ALL
                  SELECT person_id
                  FROM boe_election_effective_candidate_occurrences
                )
                """
            ),
            "distinct_parties": scalar(
                """
                SELECT COUNT(DISTINCT party_id) FROM (
                  SELECT party_id FROM infoelectoral_candidate_occurrences
                  UNION ALL
                  SELECT party_id
                  FROM boe_election_effective_candidate_occurrences
                )
                """
            ),
            "distinct_archives": scalar(
                "SELECT COUNT(DISTINCT archive_id) "
                "FROM infoelectoral_candidate_occurrences"
            ),
            "distinct_elections": scalar(
                """
                SELECT COUNT(DISTINCT election_id) FROM (
                  SELECT archive.election_id
                  FROM infoelectoral_candidate_occurrences AS candidate
                  JOIN infoelectoral_candidate_archives AS archive
                    ON archive.archive_id=candidate.archive_id
                  UNION ALL
                  SELECT election_id
                  FROM boe_election_effective_candidate_occurrences
                )
                """
            ),
            "joined_rows": scalar(
                """
                SELECT COUNT(*) FROM (
                  SELECT candidate.candidate_occurrence_id
                  FROM infoelectoral_candidate_occurrences AS candidate
                  JOIN infoelectoral_candidate_archives AS archive
                    ON archive.archive_id=candidate.archive_id
                  JOIN persons AS person ON person.person_id=candidate.person_id
                  JOIN parties AS party ON party.party_id=candidate.party_id
                  JOIN sources AS source ON source.source_id=candidate.source_id
                  JOIN source_records AS source_record
                    ON source_record.source_record_pk=candidate.source_record_pk
                  UNION ALL
                  SELECT candidate.effective_candidate_occurrence_id
                  FROM boe_election_effective_candidate_occurrences AS candidate
                  JOIN boe_election_effective_candidacies AS candidacy
                    ON candidacy.candidacy_id=candidate.candidacy_id
                  JOIN persons AS person ON person.person_id=candidate.person_id
                  JOIN parties AS party ON party.party_id=candidate.party_id
                  JOIN sources AS source ON source.source_id=candidate.source_id
                  JOIN source_records AS source_record
                    ON source_record.source_record_pk=candidate.source_record_pk
                )
                """
            ),
            "source_birth_date_rows": scalar(
                "SELECT COUNT(*) FROM infoelectoral_candidate_occurrences "
                "WHERE NULLIF(TRIM(birth_date), '') IS NOT NULL"
            ),
            "source_birth_date_source_rows": scalar(
                "SELECT COUNT(*) FROM infoelectoral_candidate_occurrences "
                "WHERE NULLIF(TRIM(birth_date_source), '') IS NOT NULL"
            ),
            "source_dni_rows": scalar(
                "SELECT COUNT(*) FROM infoelectoral_candidate_occurrences "
                "WHERE NULLIF(TRIM(dni), '') IS NOT NULL"
            ),
            "source_public_name_rows": scalar(
                """
                SELECT COUNT(*) FROM (
                  SELECT full_name FROM infoelectoral_candidate_occurrences
                  UNION ALL
                  SELECT full_name
                  FROM boe_election_effective_candidate_occurrences
                ) WHERE NULLIF(TRIM(full_name), '') IS NOT NULL
                """
            ),
            "source_exact_text_rows": scalar(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE NULLIF(TRIM(source_text_exact), '') IS NOT NULL
                """
            ),
            "source_correction_backed_rows": scalar(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE correction_operation_id IS NOT NULL
                """
            ),
            "source_boe_document_lineage_rows": scalar(
                """
                SELECT COUNT(*)
                FROM boe_election_effective_candidate_occurrences
                WHERE document_source_record_pk IS NOT NULL
                """
            ),
        }
    finally:
        conn.close()


def _previous_partitions(
    manifest_path: Path | None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == CANDIDATE_OCCURRENCE_CONTRACT.lane
        and payload.get("transformer_version")
        == CANDIDATE_OCCURRENCE_CONTRACT.transformer_version
        and payload.get("schema_sha256") == CANDIDATE_OCCURRENCE_CONTRACT.schema_sha256
    )
    partitions = (
        {
            str(item["partition_id"]): item
            for item in list(payload.get("partitions") or [])
        }
        if valid
        else {}
    )
    return partitions, sha256_file(manifest_path)


def export_candidate_occurrence_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if row_group_rows <= 0 or max_file_rows <= 0:
        raise ValueError("row-group-rows and max-file-rows must be positive")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError(
            "previous-manifest and previous-root must be provided together"
        )

    started = time.monotonic()
    scan_started = time.monotonic()
    partitions, scan_totals = scan_candidate_occurrence_partitions(
        db_path, snapshot_date=snapshot_date
    )
    scan_seconds = time.monotonic() - scan_started
    database_counts = _database_counts(db_path)
    previous_by_id, previous_sha256 = _previous_partitions(previous_manifest_path)
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        previous = previous_by_id.get(str(partition["partition_id"]))
        eligible = reusable_partition(
            partition=partition,
            previous=previous,
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    partition_by_id = {str(item["partition_id"]): item for item in partitions}
    hardlinks = 0
    copies = 0
    try:
        for partition_id, previous in reusable.items():
            partition = partition_by_id[partition_id]
            files, modes = reuse_partition_files(
                previous=previous,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        active_id: str | None = None
        active_writer: PartitionWriter | None = None
        if len(reusable) < len(partitions):
            for row in _iter_rows(db_path):
                partition_id = _partition_id(_partition_key(row))
                if partition_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)]["files"] = active_writer.close()
                        partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                    active_id = partition_id
                    if partition_id in reusable:
                        active_writer = None
                    else:
                        active_writer = PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[partition_id],
                            contract=CANDIDATE_OCCURRENCE_CONTRACT,
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                        )
                if active_writer is not None:
                    active_writer.append(row)
            if active_writer is not None:
                partition_by_id[str(active_id)]["files"] = active_writer.close()
                partition_by_id[str(active_id)]["materialization"] = "rebuilt"
        export_seconds = time.monotonic() - export_started

        rows = int(scan_totals["rows"])
        files = sum(len(list(item.get("files") or [])) for item in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for item in partitions
            for file_meta in list(item.get("files") or [])
        )
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_join_balance": database_counts["occurrence_rows"]
            == database_counts["joined_rows"]
            == rows,
            "distinct_occurrence_ids": database_counts["distinct_occurrence_ids"]
            == rows,
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "source_record_complete": scan_totals["source_record_rows"] == rows,
            "raw_payload_excluded": "raw_payload"
            not in CANDIDATE_OCCURRENCE_CONTRACT.columns,
            "public_birth_dates_retained_exactly": scan_totals["birth_date_rows"]
            == database_counts["source_birth_date_rows"],
            "public_source_birth_dates_retained_exactly": scan_totals[
                "birth_date_source_rows"
            ]
            == database_counts["source_birth_date_source_rows"],
            "public_dni_retained_exactly": scan_totals["dni_rows"]
            == database_counts["source_dni_rows"],
            "public_names_retained_exactly": scan_totals["exact_public_name_rows"]
            == database_counts["source_public_name_rows"]
            == rows,
            "boe_exact_source_text_retained": scan_totals["exact_source_text_rows"]
            == database_counts["source_exact_text_rows"]
            == scan_totals["boe_rows"],
            "boe_correction_lineage_retained": scan_totals["correction_backed_rows"]
            == database_counts["source_correction_backed_rows"],
            "boe_document_source_records_complete": scan_totals[
                "document_source_record_rows"
            ]
            == database_counts["source_boe_document_lineage_rows"]
            == scan_totals["boe_rows"],
            "boe_election_outcomes_not_inferred": scan_totals["outcome_known_rows"]
            == scan_totals["infoelectoral_rows"],
            "no_private_tokens": scan_totals["private_token_findings"] == 0,
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "bounded_file_rows": all(
                int(file_meta["rows"]) <= int(max_file_rows)
                for item in partitions
                for file_meta in list(item.get("files") or [])
            ),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "representative_100k_real_rows": rows >= 100_000,
            "million_real_rows": rows >= 1_000_000,
            "cross_election_identity_quality_verified": False,
            "durable_public_origin_verified": False,
        }
        if rows >= 1_000_000:
            capacity_class = "s2_1m"
        elif rows >= 100_000:
            capacity_class = "s1_100k"
        else:
            capacity_class = "below_s1_100k"
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": CANDIDATE_OCCURRENCE_CONTRACT.lane,
            "transformer_version": CANDIDATE_OCCURRENCE_CONTRACT.transformer_version,
            "schema": CANDIDATE_OCCURRENCE_CONTRACT.schema,
            "schema_sha256": CANDIDATE_OCCURRENCE_CONTRACT.schema_sha256,
            "partition_contract": {
                "strategy": "semantic_hive_source_election_type_year",
                "keys": [
                    "snapshot_date",
                    "source_system",
                    "election_type",
                    "year",
                ],
                "ordering": [
                    "source_system_code",
                    "election_type_code",
                    "election_year",
                    "candidate_occurrence_id",
                ],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
                "archive_id_retained_as_column": True,
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_public_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                ],
                "previous_manifest_sha256": previous_sha256,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(partitions) - len(reusable),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "source": {
                "database_file": db_path.name,
                "database_bytes": int(db_path.stat().st_size),
                "tables": [
                    "infoelectoral_candidate_occurrences",
                    "boe_election_effective_candidate_occurrences",
                ],
                "evidence_tables": [
                    "infoelectoral_candidate_archives",
                    "boe_election_candidate_occurrences",
                    "boe_election_candidate_correction_operations",
                ],
                "raw_payload_published": False,
                "official_archive_publication": "publishable_with_source_provenance",
                "public_domain_identity_fields": [
                    "full_name",
                    "birth_date",
                    "birth_date_source",
                    "dni",
                    "source_text_exact",
                ],
            },
            "source_database": database_counts,
            "totals": {
                **scan_totals,
                "partitions": len(partitions),
                "files": files,
                "parquet_bytes": parquet_bytes,
            },
            "coverage": {
                "source_url": round(scan_totals["source_url_rows"] / rows, 8)
                if rows
                else 0.0,
                "source_record": round(scan_totals["source_record_rows"] / rows, 8)
                if rows
                else 0.0,
                "present": round(scan_totals["present_rows"] / rows, 8)
                if rows
                else 0.0,
                "elected": round(scan_totals["elected_rows"] / rows, 8)
                if rows
                else 0.0,
                "birth_date": round(scan_totals["birth_date_rows"] / rows, 8)
                if rows
                else 0.0,
                "birth_date_source": round(
                    scan_totals["birth_date_source_rows"] / rows, 8
                )
                if rows
                else 0.0,
                "dni": round(scan_totals["dni_rows"] / rows, 8) if rows else 0.0,
                "public_name": round(scan_totals["exact_public_name_rows"] / rows, 8)
                if rows
                else 0.0,
                "exact_source_text": round(
                    scan_totals["exact_source_text_rows"] / rows, 8
                )
                if rows
                else 0.0,
                "document_source_record": round(
                    scan_totals["document_source_record_rows"] / rows, 8
                )
                if rows
                else 0.0,
                "known_election_outcome": round(
                    scan_totals["outcome_known_rows"] / rows, 8
                )
                if rows
                else 0.0,
            },
            "identity_assurance": "source_scoped_election_occurrence_not_cross_election_identity",
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "capacity_class": capacity_class,
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
            },
            "partitions": partitions,
            "limitations": [
                "All official public names are retained. Public-domain DNI and birth-date fields remain exact when Infoelectoral provides them; null means the source did not provide that field.",
                "BOE effective rows retain exact proclamation or correction text, official document, checksum, paragraph, normalized person and party links, and immutable base or correction lineage.",
                "BOE proclamation documents do not establish election outcomes, so is_elected remains null instead of being guessed.",
                "Candidate occurrences remain source-scoped; cross-election person equivalence is not asserted.",
                "Local materialization does not prove durable public-origin publication or restore.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError("analytical partition gate failed: " + ", ".join(failed))
        (staging_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_root.rename(output_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return manifest


__all__ = [
    "CANDIDATE_OCCURRENCE_CONTRACT",
    "election_scope",
    "export_candidate_occurrence_partitions",
    "scan_candidate_occurrence_partitions",
]
