"""Ingest exact public candidate occurrences from supported official BOE XML."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.politicos_es.db import apply_schema
from publicdata_connectors_es.elections.boe_candidates import (
    PARSER_VERSION,
    SOURCE_ID,
    BoeCandidateCorrectionParseResult,
    BoeCandidateParseResult,
    parse_boe_candidate_correction,
    parse_boe_candidate_document,
)
from publicdata_core.util import stable_json
from publicdata_sqlite import open_db

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SCHEMA = Path("etl/load/sqlite_schema.sql")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "boe-election-candidates-latest.json"
)


@dataclass(frozen=True)
class CohortContract:
    election_id: str
    election_date: str
    election_type_code: str
    expected_candidacies: int
    expected_candidates: int
    expected_titular: int
    expected_suplente: int
    expected_not_proclaimed: int
    additional_correction_refs: tuple[str, ...] = ()


COHORTS = {
    "BOE-A-2015-12734": CohortContract(
        election_id="general-cortes-2015-12-20",
        election_date="2015-12-20",
        election_type_code="general_cortes",
        expected_candidacies=1_282,
        expected_candidates=10_498,
        expected_titular=5_830,
        expected_suplente=4_668,
        expected_not_proclaimed=31,
    ),
    "BOE-A-2016-5186": CohortContract(
        election_id="general-cortes-2016-06-26",
        election_date="2016-06-26",
        election_type_code="general_cortes",
        expected_candidacies=1_165,
        expected_candidates=9_258,
        expected_titular=5_134,
        expected_suplente=4_124,
        expected_not_proclaimed=39,
    ),
    "BOE-A-2019-4902": CohortContract(
        election_id="general-cortes-2019-04-28",
        election_date="2019-04-28",
        election_type_code="general_cortes",
        expected_candidacies=1_234,
        expected_candidates=9_578,
        expected_titular=5_425,
        expected_suplente=4_153,
        expected_not_proclaimed=49,
    ),
    "BOE-A-2019-6475": CohortContract(
        election_id="european-parliament-2019-05-26",
        election_date="2019-05-26",
        election_type_code="european_parliament",
        expected_candidacies=32,
        expected_candidates=1_907,
        expected_titular=1_728,
        expected_suplente=179,
        expected_not_proclaimed=0,
    ),
    "BOE-A-2023-15066": CohortContract(
        election_id="general-cortes-2023-07-23",
        election_date="2023-07-23",
        election_type_code="general_cortes",
        expected_candidacies=1_154,
        expected_candidates=8_548,
        expected_titular=4_886,
        expected_suplente=3_662,
        expected_not_proclaimed=66,
    ),
    "BOE-A-2024-9687": CohortContract(
        election_id="european-parliament-2024-06-09",
        election_date="2024-06-09",
        election_type_code="european_parliament",
        expected_candidacies=33,
        expected_candidates=2_206,
        expected_titular=2_013,
        expected_suplente=193,
        expected_not_proclaimed=0,
    ),
    "BOE-A-2024-10230": CohortContract(
        election_id="european-parliament-2024-06-09",
        election_date="2024-06-09",
        election_type_code="european_parliament",
        expected_candidacies=1,
        expected_candidates=61,
        expected_titular=61,
        expected_suplente=0,
        expected_not_proclaimed=0,
        additional_correction_refs=("BOE-A-2024-10569",),
    ),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument(
        "--boe-id",
        action="append",
        choices=sorted(COHORTS),
        help="Supported proclamation document; repeat to ingest multiple cohorts",
    )
    parser.add_argument("--snapshot-date", default="2026-08-13")
    parser.add_argument("--batch-rows", type=int, default=1_000)
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _document_row(conn: sqlite3.Connection, document_id: str) -> sqlite3.Row:
    url = f"https://www.boe.es/diario_boe/xml.php?id={document_id}"
    row = conn.execute(
        """
        SELECT td.source_record_pk, td.source_url, td.content_sha256,
               td.bytes, td.raw_path
        FROM text_documents AS td
        WHERE td.source_id='boe_document_xml' AND td.source_url=?
        """,
        (url,),
    ).fetchone()
    if row is None:
        raise RuntimeError(
            f"official BOE XML has not completed acquisition: {document_id}"
        )
    raw_path = Path(str(row["raw_path"]))
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path
    raw_root = (ROOT / "etl/data/raw").resolve()
    try:
        raw_path.resolve().relative_to(raw_root)
    except ValueError as exc:
        raise RuntimeError("BOE XML raw path escapes the real-data root") from exc
    if not raw_path.is_file():
        raise RuntimeError(f"BOE XML raw object is missing: {_display_path(raw_path)}")
    if raw_path.stat().st_size != int(row["bytes"]):
        raise RuntimeError(f"BOE XML byte count drifted: {document_id}")
    if _sha256(raw_path) != str(row["content_sha256"]):
        raise RuntimeError(f"BOE XML checksum drifted: {document_id}")
    return row


def _validate_contract(
    result: BoeCandidateParseResult,
    contract: CohortContract,
) -> dict[str, bool]:
    candidate_types = Counter(row.candidate_type_code for row in result.candidates)
    candidacy_statuses = Counter(row.proclamation_status for row in result.candidacies)
    checks = {
        "document_profile_matches_contract": (
            result.document.profile
            == (
                "european_parliament"
                if contract.election_type_code == "european_parliament"
                else "general_election"
            )
        ),
        "candidacy_count_matches_exact_contract": (
            len(result.candidacies) == contract.expected_candidacies
        ),
        "candidate_count_matches_exact_contract": (
            len(result.candidates) == contract.expected_candidates
        ),
        "titular_count_matches_exact_contract": (
            candidate_types["titular"] == contract.expected_titular
        ),
        "suplente_count_matches_exact_contract": (
            candidate_types["suplente"] == contract.expected_suplente
        ),
        "not_proclaimed_count_matches_exact_contract": (
            candidacy_statuses["not_proclaimed"] == contract.expected_not_proclaimed
        ),
        "candidate_names_nonempty": all(row.full_name for row in result.candidates),
        "exact_source_paragraphs_retained": all(
            row.source_text_exact for row in result.candidates
        ),
        "candidate_occurrence_ids_unique": (
            len({row.candidate_occurrence_id for row in result.candidates})
            == len(result.candidates)
        ),
        "candidacy_ids_unique": (
            len({row.candidacy_id for row in result.candidacies})
            == len(result.candidacies)
        ),
    }
    return checks


def _create_stage(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_boe_candidacy_stage (
          candidacy_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          electoral_board TEXT NOT NULL,
          electoral_district TEXT NOT NULL,
          chamber_code TEXT NOT NULL,
          candidacy_number INTEGER NOT NULL,
          candidacy_name TEXT NOT NULL,
          source_text_exact TEXT NOT NULL,
          proclamation_status TEXT NOT NULL,
          source_paragraph_number INTEGER NOT NULL
        ) WITHOUT ROWID;

        CREATE TEMP TABLE IF NOT EXISTS ingest_boe_candidate_stage (
          candidate_occurrence_id TEXT PRIMARY KEY,
          candidacy_id TEXT NOT NULL,
          document_id TEXT NOT NULL,
          election_id TEXT NOT NULL,
          election_date TEXT NOT NULL,
          election_type_code TEXT NOT NULL,
          electoral_board TEXT NOT NULL,
          electoral_district TEXT NOT NULL,
          chamber_code TEXT NOT NULL,
          candidacy_number INTEGER NOT NULL,
          candidate_order INTEGER NOT NULL,
          candidate_type_code TEXT NOT NULL,
          substitute_for_candidate_order INTEGER,
          full_name TEXT NOT NULL,
          source_text_exact TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_content_sha256 TEXT NOT NULL,
          source_paragraph_number INTEGER NOT NULL,
          person_canonical_key TEXT NOT NULL,
          source_record_id TEXT NOT NULL,
          raw_payload TEXT NOT NULL,
          row_content_sha256 TEXT NOT NULL
        ) WITHOUT ROWID;
        """
    )


def _stage(
    conn: sqlite3.Connection,
    *,
    result: BoeCandidateParseResult,
    contract: CohortContract,
    source_url: str,
    source_content_sha256: str,
    batch_rows: int,
) -> None:
    conn.execute("DELETE FROM ingest_boe_candidacy_stage")
    conn.execute("DELETE FROM ingest_boe_candidate_stage")
    conn.executemany(
        """
        INSERT INTO ingest_boe_candidacy_stage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.candidacy_id,
                result.document.document_id,
                row.electoral_board,
                row.electoral_district,
                row.chamber_code,
                row.candidacy_number,
                row.candidacy_name,
                row.source_text_exact,
                row.proclamation_status,
                row.source_paragraph_number,
            )
            for row in result.candidacies
        ],
    )
    values: list[tuple[Any, ...]] = []
    for row in result.candidates:
        public_payload = {
            **asdict(row),
            "document_id": result.document.document_id,
            "election_id": contract.election_id,
            "election_date": contract.election_date,
            "election_type_code": contract.election_type_code,
            "source_url": source_url,
            "source_content_sha256": source_content_sha256,
            "synthetic_or_mock": False,
            "official_public_domain_personal_information_retained": True,
        }
        raw_payload = stable_json(public_payload)
        values.append(
            (
                row.candidate_occurrence_id,
                row.candidacy_id,
                result.document.document_id,
                contract.election_id,
                contract.election_date,
                contract.election_type_code,
                row.electoral_board,
                row.electoral_district,
                row.chamber_code,
                row.candidacy_number,
                row.candidate_order,
                row.candidate_type_code,
                row.substitute_for_candidate_order,
                row.full_name,
                row.source_text_exact,
                source_url,
                source_content_sha256,
                row.source_paragraph_number,
                f"boe-election-candidate-occurrence:{row.candidate_occurrence_id}",
                row.candidate_occurrence_id,
                raw_payload,
                hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
            )
        )
        if len(values) >= batch_rows:
            conn.executemany(
                "INSERT INTO ingest_boe_candidate_stage VALUES ("
                + ",".join("?" for _ in range(22))
                + ")",
                values,
            )
            values = []
    if values:
        conn.executemany(
            "INSERT INTO ingest_boe_candidate_stage VALUES ("
            + ",".join("?" for _ in range(22))
            + ")",
            values,
        )


def _existing_identity_guard(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    source_content_sha256: str,
) -> None:
    existing = conn.execute(
        """
        SELECT source_content_sha256
        FROM boe_election_candidate_documents
        WHERE document_id=?
        """,
        (document_id,),
    ).fetchone()
    if existing is not None and str(existing[0]) != source_content_sha256:
        raise RuntimeError(f"immutable BOE candidate document changed: {document_id}")
    existing_candidate_ids = {
        str(row[0])
        for row in conn.execute(
            """
            SELECT candidate_occurrence_id
            FROM boe_election_candidate_occurrences
            WHERE document_id=?
            """,
            (document_id,),
        )
    }
    staged_candidate_ids = {
        str(row[0])
        for row in conn.execute(
            "SELECT candidate_occurrence_id FROM ingest_boe_candidate_stage"
        )
    }
    if existing_candidate_ids and existing_candidate_ids != staged_candidate_ids:
        raise RuntimeError(f"BOE candidate occurrence identity drift: {document_id}")


def _ingest_staged(
    conn: sqlite3.Connection,
    *,
    result: BoeCandidateParseResult,
    contract: CohortContract,
    document_source_record_pk: int,
    source_url: str,
    source_content_sha256: str,
    source_bytes: int,
    raw_path: str,
    snapshot_date: str,
    correction_refs: tuple[str, ...],
) -> None:
    now_iso = utc_now()
    _existing_identity_guard(
        conn,
        document_id=result.document.document_id,
        source_content_sha256=source_content_sha256,
    )
    conn.execute(
        """
        INSERT INTO sources (
          source_id, name, scope, default_url, data_format,
          is_active, created_at, updated_at
        ) VALUES (?, ?, 'nacional', ?, 'xml', 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          is_active=1,
          updated_at=excluded.updated_at
        """,
        (
            SOURCE_ID,
            "Candidaturas electorales proclamadas en el BOE",
            "https://www.boe.es/diario_boe/xml.php",
            now_iso,
            now_iso,
        ),
    )
    conn.execute(
        """
        INSERT INTO boe_election_candidate_documents (
          document_id, election_id, election_date, election_type_code,
          publication_date, title, document_source_record_pk, source_url,
          source_content_sha256, source_bytes, raw_path, correction_state,
          correction_refs_json, candidacy_rows, candidate_rows, parser_version,
          first_seen_snapshot_date, last_seen_snapshot_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id) DO UPDATE SET
          election_id=excluded.election_id,
          election_date=excluded.election_date,
          election_type_code=excluded.election_type_code,
          publication_date=excluded.publication_date,
          title=excluded.title,
          document_source_record_pk=excluded.document_source_record_pk,
          source_url=excluded.source_url,
          source_content_sha256=excluded.source_content_sha256,
          source_bytes=excluded.source_bytes,
          raw_path=excluded.raw_path,
          correction_state=CASE
            WHEN boe_election_candidate_documents.correction_state='applied'
             AND excluded.correction_state='pending'
            THEN 'applied'
            ELSE excluded.correction_state
          END,
          correction_refs_json=excluded.correction_refs_json,
          candidacy_rows=excluded.candidacy_rows,
          candidate_rows=excluded.candidate_rows,
          parser_version=excluded.parser_version,
          last_seen_snapshot_date=excluded.last_seen_snapshot_date,
          updated_at=excluded.updated_at
        """,
        (
            result.document.document_id,
            contract.election_id,
            contract.election_date,
            contract.election_type_code,
            result.document.publication_date,
            result.document.title,
            document_source_record_pk,
            source_url,
            source_content_sha256,
            source_bytes,
            raw_path,
            "pending" if correction_refs else "none_declared",
            stable_json(list(correction_refs)),
            len(result.candidacies),
            len(result.candidates),
            PARSER_VERSION,
            snapshot_date,
            snapshot_date,
            now_iso,
            now_iso,
        ),
    )
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        SELECT candidacy_name, NULL, ?, ?
        FROM ingest_boe_candidacy_stage
        GROUP BY candidacy_name
        ON CONFLICT(name) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload,
          content_sha256, created_at, updated_at
        )
        SELECT ?, source_record_id, ?, raw_payload, row_content_sha256, ?, ?
        FROM ingest_boe_candidate_stage
        WHERE 1
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=excluded.source_snapshot_date,
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        """,
        (SOURCE_ID, snapshot_date, now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO persons (
          full_name, given_name, family_name, gender, birth_date,
          territory_code, canonical_key, created_at, updated_at
        )
        SELECT full_name, NULL, NULL, NULL, NULL, '', person_canonical_key, ?, ?
        FROM ingest_boe_candidate_stage
        WHERE 1
        ON CONFLICT(canonical_key) DO UPDATE SET
          full_name=excluded.full_name,
          updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO boe_election_candidacies (
          candidacy_id, document_id, electoral_board, electoral_district,
          chamber_code, candidacy_number, candidacy_name, source_text_exact,
          proclamation_status, source_paragraph_number, party_id,
          created_at, updated_at
        )
        SELECT stage.candidacy_id, stage.document_id, stage.electoral_board,
               stage.electoral_district, stage.chamber_code,
               stage.candidacy_number, stage.candidacy_name,
               stage.source_text_exact, stage.proclamation_status,
               stage.source_paragraph_number, party.party_id, ?, ?
        FROM ingest_boe_candidacy_stage AS stage
        JOIN parties AS party ON party.name=stage.candidacy_name
        WHERE 1
        ON CONFLICT(candidacy_id) DO UPDATE SET
          candidacy_name=excluded.candidacy_name,
          source_text_exact=excluded.source_text_exact,
          proclamation_status=excluded.proclamation_status,
          source_paragraph_number=excluded.source_paragraph_number,
          party_id=excluded.party_id,
          updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO boe_election_candidate_occurrences (
          candidate_occurrence_id, candidacy_id, document_id, election_id,
          election_date, election_type_code, electoral_board,
          electoral_district, chamber_code, candidacy_number, candidate_order,
          candidate_type_code, substitute_for_candidate_order, full_name,
          source_text_exact, person_id, party_id, source_id, source_record_pk,
          document_source_record_pk, source_url, source_content_sha256,
          source_paragraph_number, row_content_sha256,
          first_seen_snapshot_date, last_seen_snapshot_date, is_present,
          raw_payload, created_at, updated_at
        )
        SELECT stage.candidate_occurrence_id, stage.candidacy_id,
               stage.document_id, stage.election_id, stage.election_date,
               stage.election_type_code, stage.electoral_board,
               stage.electoral_district, stage.chamber_code,
               stage.candidacy_number, stage.candidate_order,
               stage.candidate_type_code,
               stage.substitute_for_candidate_order, stage.full_name,
               stage.source_text_exact, person.person_id, party.party_id, ?,
               source.source_record_pk, ?, stage.source_url,
               stage.source_content_sha256, stage.source_paragraph_number,
               stage.row_content_sha256, ?, ?, 1, stage.raw_payload, ?, ?
        FROM ingest_boe_candidate_stage AS stage
        JOIN persons AS person ON person.canonical_key=stage.person_canonical_key
        JOIN ingest_boe_candidacy_stage AS candidacy
          ON candidacy.candidacy_id=stage.candidacy_id
        JOIN parties AS party ON party.name=candidacy.candidacy_name
        JOIN source_records AS source
          ON source.source_id=? AND source.source_record_id=stage.source_record_id
        WHERE 1
        ON CONFLICT(candidate_occurrence_id) DO UPDATE SET
          full_name=excluded.full_name,
          source_text_exact=excluded.source_text_exact,
          person_id=excluded.person_id,
          party_id=excluded.party_id,
          source_record_pk=excluded.source_record_pk,
          document_source_record_pk=excluded.document_source_record_pk,
          source_url=excluded.source_url,
          source_content_sha256=excluded.source_content_sha256,
          source_paragraph_number=excluded.source_paragraph_number,
          row_content_sha256=excluded.row_content_sha256,
          last_seen_snapshot_date=excluded.last_seen_snapshot_date,
          is_present=1,
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            SOURCE_ID,
            document_source_record_pk,
            snapshot_date,
            snapshot_date,
            now_iso,
            now_iso,
            SOURCE_ID,
        ),
    )


def _database_checks(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    expected_candidacies: int,
    expected_candidates: int,
) -> dict[str, bool]:
    candidacies = int(
        conn.execute(
            "SELECT COUNT(*) FROM boe_election_candidacies WHERE document_id=?",
            (document_id,),
        ).fetchone()[0]
    )
    candidates = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM boe_election_candidate_occurrences
            WHERE document_id=?
            """,
            (document_id,),
        ).fetchone()[0]
    )
    exact_source_text = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM boe_election_candidate_occurrences
            WHERE document_id=? AND source_text_exact<>''
            """,
            (document_id,),
        ).fetchone()[0]
    )
    source_rows = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM boe_election_candidate_occurrences AS candidate
            JOIN source_records AS source
              ON source.source_record_pk=candidate.source_record_pk
            WHERE candidate.document_id=?
              AND source.source_id=?
              AND source.content_sha256=candidate.row_content_sha256
            """,
            (document_id, SOURCE_ID),
        ).fetchone()[0]
    )
    return {
        "database_candidacies_reconcile": candidacies == expected_candidacies,
        "database_candidates_reconcile": candidates == expected_candidates,
        "database_exact_source_text_complete": exact_source_text == candidates,
        "database_source_record_lineage_complete": source_rows == candidates,
    }


def _ingest_correction_evidence(
    conn: sqlite3.Connection,
    *,
    base_document_id: str,
    parsed: BoeCandidateCorrectionParseResult,
    source: sqlite3.Row,
    raw_path: Path,
    snapshot_date: str,
) -> dict[str, Any]:
    now_iso = utc_now()
    source_sha = str(source["content_sha256"])
    existing = conn.execute(
        """
        SELECT source_content_sha256, application_state
        FROM boe_election_candidate_correction_documents
        WHERE correction_document_id=?
        """,
        (parsed.document.document_id,),
    ).fetchone()
    if existing is not None and str(existing["source_content_sha256"]) != source_sha:
        raise RuntimeError(
            "immutable BOE candidate correction changed: " + parsed.document.document_id
        )
    conn.execute(
        """
        INSERT INTO boe_election_candidate_correction_documents (
          correction_document_id, publication_date, title,
          document_source_record_pk, source_url, source_content_sha256,
          source_bytes, raw_path, paragraph_rows, application_state,
          parser_version, first_seen_snapshot_date, last_seen_snapshot_date,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'captured_unapplied', ?, ?, ?, ?, ?)
        ON CONFLICT(correction_document_id) DO UPDATE SET
          publication_date=excluded.publication_date,
          title=excluded.title,
          document_source_record_pk=excluded.document_source_record_pk,
          source_url=excluded.source_url,
          source_content_sha256=excluded.source_content_sha256,
          source_bytes=excluded.source_bytes,
          raw_path=excluded.raw_path,
          paragraph_rows=excluded.paragraph_rows,
          parser_version=excluded.parser_version,
          last_seen_snapshot_date=excluded.last_seen_snapshot_date,
          updated_at=excluded.updated_at
        """,
        (
            parsed.document.document_id,
            parsed.document.publication_date,
            parsed.document.title,
            int(source["source_record_pk"]),
            str(source["source_url"]),
            source_sha,
            int(source["bytes"]),
            _display_path(raw_path),
            len(parsed.paragraphs),
            PARSER_VERSION,
            snapshot_date,
            snapshot_date,
            now_iso,
            now_iso,
        ),
    )
    relation_basis = (
        "official_metadata"
        if base_document_id in parsed.document.base_document_refs
        else "correction_body_scope"
    )
    conn.execute(
        """
        INSERT INTO boe_election_candidate_correction_targets (
          correction_document_id, base_document_id, relation_basis, created_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(correction_document_id, base_document_id) DO UPDATE SET
          relation_basis=excluded.relation_basis
        """,
        (
            parsed.document.document_id,
            base_document_id,
            relation_basis,
            now_iso,
        ),
    )
    conn.executemany(
        """
        INSERT INTO boe_election_candidate_correction_paragraphs (
          correction_paragraph_id, correction_document_id,
          source_paragraph_number, source_css_class, source_text_exact,
          normalized_text, semantic_marker, electoral_board,
          electoral_district, chamber_code, candidacy_number, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(correction_paragraph_id) DO UPDATE SET
          source_css_class=excluded.source_css_class,
          source_text_exact=excluded.source_text_exact,
          normalized_text=excluded.normalized_text,
          semantic_marker=excluded.semantic_marker,
          electoral_board=excluded.electoral_board,
          electoral_district=excluded.electoral_district,
          chamber_code=excluded.chamber_code,
          candidacy_number=excluded.candidacy_number
        """,
        [
            (
                row.correction_paragraph_id,
                parsed.document.document_id,
                row.source_paragraph_number,
                row.source_css_class,
                row.source_text_exact,
                row.normalized_text,
                row.semantic_marker,
                row.electoral_board,
                row.electoral_district,
                row.chamber_code,
                row.candidacy_number,
                now_iso,
            )
            for row in parsed.paragraphs
        ],
    )
    stored_paragraphs = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM boe_election_candidate_correction_paragraphs
            WHERE correction_document_id=?
            """,
            (parsed.document.document_id,),
        ).fetchone()[0]
    )
    if stored_paragraphs != len(parsed.paragraphs):
        raise RuntimeError(
            "BOE candidate correction paragraph count did not reconcile: "
            + parsed.document.document_id
        )
    return {
        "document_id": parsed.document.document_id,
        "publication_date": parsed.document.publication_date,
        "title": parsed.document.title,
        "base_document_refs": list(parsed.document.base_document_refs),
        "relation_basis": relation_basis,
        "source_url": str(source["source_url"]),
        "source_content_sha256": source_sha,
        "source_bytes": int(source["bytes"]),
        "raw_path": _display_path(raw_path),
        "paragraphs": len(parsed.paragraphs),
        "application_state": (
            str(existing["application_state"])
            if existing is not None
            else "captured_unapplied"
        ),
        "exact_paragraph_text_retained": all(
            row.source_text_exact for row in parsed.paragraphs
        ),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if int(args.batch_rows) < 1:
        raise RuntimeError("--batch-rows must be >= 1")
    snapshot_date = datetime.fromisoformat(str(args.snapshot_date)).date().isoformat()
    requested = list(dict.fromkeys(args.boe_id or sorted(COHORTS)))
    started = time.monotonic()
    cpu_started = time.process_time()
    conn = open_db(Path(args.db))
    try:
        apply_schema(conn, Path(args.schema))
        conn.row_factory = sqlite3.Row
        _create_stage(conn)
        reports: list[dict[str, Any]] = []
        all_checks: dict[str, bool] = {}
        for document_id in requested:
            contract = COHORTS[document_id]
            source = _document_row(conn, document_id)
            raw_path = Path(str(source["raw_path"]))
            if not raw_path.is_absolute():
                raw_path = ROOT / raw_path
            parsed = parse_boe_candidate_document(raw_path)
            if parsed.document.document_id != document_id:
                raise RuntimeError(f"BOE candidate identifier mismatch: {document_id}")
            parse_checks = _validate_contract(parsed, contract)
            correction_refs = tuple(
                sorted(
                    set(parsed.document.correction_refs)
                    | set(contract.additional_correction_refs)
                )
            )
            correction_documents: list[dict[str, Any]] = []
            parsed_corrections: list[
                tuple[BoeCandidateCorrectionParseResult, sqlite3.Row, Path]
            ] = []
            for correction_ref in correction_refs:
                correction = _document_row(conn, correction_ref)
                correction_path = Path(str(correction["raw_path"]))
                if not correction_path.is_absolute():
                    correction_path = ROOT / correction_path
                correction_documents.append(
                    {
                        "document_id": correction_ref,
                        "source_url": str(correction["source_url"]),
                        "source_content_sha256": str(correction["content_sha256"]),
                        "source_bytes": int(correction["bytes"]),
                        "raw_path": _display_path(correction_path),
                    }
                )
                parsed_corrections.append(
                    (
                        parse_boe_candidate_correction(correction_path),
                        correction,
                        correction_path,
                    )
                )
            parse_checks["all_official_correction_documents_captured"] = len(
                correction_documents
            ) == len(correction_refs)
            if not all(parse_checks.values()):
                failed = sorted(key for key, value in parse_checks.items() if not value)
                raise RuntimeError(
                    f"BOE candidate exact-count contract failed for {document_id}: {failed}"
                )
            source_url = str(source["source_url"])
            source_sha = str(source["content_sha256"])
            _stage(
                conn,
                result=parsed,
                contract=contract,
                source_url=source_url,
                source_content_sha256=source_sha,
                batch_rows=int(args.batch_rows),
            )
            _ingest_staged(
                conn,
                result=parsed,
                contract=contract,
                document_source_record_pk=int(source["source_record_pk"]),
                source_url=source_url,
                source_content_sha256=source_sha,
                source_bytes=int(source["bytes"]),
                raw_path=_display_path(raw_path),
                snapshot_date=snapshot_date,
                correction_refs=correction_refs,
            )
            correction_evidence = [
                _ingest_correction_evidence(
                    conn,
                    base_document_id=document_id,
                    parsed=correction_parsed,
                    source=correction_source,
                    raw_path=correction_path,
                    snapshot_date=snapshot_date,
                )
                for correction_parsed, correction_source, correction_path in parsed_corrections
            ]
            parse_checks["all_correction_paragraphs_retained_exactly"] = all(
                item["exact_paragraph_text_retained"] for item in correction_evidence
            )
            database_checks = _database_checks(
                conn,
                document_id=document_id,
                expected_candidacies=len(parsed.candidacies),
                expected_candidates=len(parsed.candidates),
            )
            checks = {**parse_checks, **database_checks}
            all_checks.update(
                {f"{document_id}:{key}": value for key, value in checks.items()}
            )
            reports.append(
                {
                    "document_id": document_id,
                    "source_url": source_url,
                    "source_content_sha256": source_sha,
                    "source_bytes": int(source["bytes"]),
                    "raw_path": _display_path(raw_path),
                    "publication_date": parsed.document.publication_date,
                    "title": parsed.document.title,
                    "profile": parsed.document.profile,
                    "correction_state": (
                        "none_declared"
                        if not correction_refs
                        else (
                            "applied"
                            if all(
                                item["application_state"] == "applied"
                                for item in correction_evidence
                            )
                            else "pending"
                        )
                    ),
                    "correction_refs": list(correction_refs),
                    "correction_documents": correction_documents,
                    "correction_evidence": correction_evidence,
                    "contract": asdict(contract),
                    "totals": {
                        "candidacies": len(parsed.candidacies),
                        "candidates": len(parsed.candidates),
                        "titular": sum(
                            row.candidate_type_code == "titular"
                            for row in parsed.candidates
                        ),
                        "suplente": sum(
                            row.candidate_type_code == "suplente"
                            for row in parsed.candidates
                        ),
                        "not_proclaimed_candidacies": sum(
                            row.proclamation_status == "not_proclaimed"
                            for row in parsed.candidacies
                        ),
                    },
                    "checks": checks,
                }
            )
        conn.commit()
        fk_violations = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    elapsed = max(0.000001, time.monotonic() - started)
    cpu_seconds = max(0.0, time.process_time() - cpu_started)
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    total_candidates = sum(item["totals"]["candidates"] for item in reports)
    correction_by_id: dict[str, dict[str, Any]] = {}
    correction_target_relations = 0
    for item in reports:
        for correction in item["correction_evidence"]:
            correction_target_relations += 1
            correction_by_id[str(correction["document_id"])] = correction
    all_checks["foreign_key_check_passed"] = not fk_violations
    all_checks["quick_check_passed"] = quick_check == "ok"
    status = "ok" if all(all_checks.values()) else "failed"
    corrections_pending = any(
        item["application_state"] != "applied" for item in correction_by_id.values()
    )
    return {
        "schema_version": "boe_election_candidates_run_v1",
        "status": status,
        "source_id": SOURCE_ID,
        "snapshot_date": snapshot_date,
        "parser_version": PARSER_VERSION,
        "documents": reports,
        "totals": {
            "documents": len(reports),
            "candidacies": sum(item["totals"]["candidacies"] for item in reports),
            "candidates": total_candidates,
            "titular": sum(item["totals"]["titular"] for item in reports),
            "suplente": sum(item["totals"]["suplente"] for item in reports),
            "not_proclaimed_candidacies": sum(
                item["totals"]["not_proclaimed_candidacies"] for item in reports
            ),
            "distinct_correction_documents": len(correction_by_id),
            "correction_target_relations": correction_target_relations,
            "correction_paragraphs": sum(
                int(item["paragraphs"]) for item in correction_by_id.values()
            ),
            "corrections_applied": sum(
                item["application_state"] == "applied"
                for item in correction_by_id.values()
            ),
        },
        "performance": {
            "elapsed_seconds": round(elapsed, 6),
            "cpu_seconds": round(cpu_seconds, 6),
            "peak_rss_bytes": peak_rss_bytes,
            "candidates_per_second": round(total_candidates / elapsed, 6),
        },
        "database": {
            "path": _display_path(Path(args.db)),
            "quick_check": quick_check,
            "foreign_key_violations": len(fk_violations),
        },
        "checks": all_checks,
        "policy": {
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "identity_fields_removed": 0,
            "cross_source_person_identity_inferred": False,
            "official_corrections_explicit": True,
            "pending_official_corrections_explicit": corrections_pending,
            "remote_mutation_performed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
        _write_json(Path(args.report_out), report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        if args.enforce and report["status"] != "ok":
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
