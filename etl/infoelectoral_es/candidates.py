"""Set-based ingestion for source-scoped Infoelectoral candidate occurrences."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable, Iterator
from typing import Any

from publicdata_connectors_es.infoelectoral.candidates import (
    SOURCE_ID,
    CandidateArchiveSpec,
    CandidateRecord,
)

from ..politicos_es.util import now_utc_iso


def _chunks(
    records: Iterable[CandidateRecord], batch_rows: int
) -> Iterator[list[CandidateRecord]]:
    if int(batch_rows) < 1:
        raise ValueError("batch_rows must be >= 1")
    batch: list[CandidateRecord] = []
    for record in records:
        batch.append(record)
        if len(batch) >= int(batch_rows):
            yield batch
            batch = []
    if batch:
        yield batch


def _gender_code(value: str | None) -> str:
    token = str(value or "").strip().upper()
    if token in {"M", "F"}:
        return "female"
    if token in {"H", "V"}:
        return "male"
    return "unknown"


def _territory_code(province_code: str) -> str:
    token = str(province_code or "").strip()
    return "ES" if token in {"", "00", "99"} else f"ES-PROV-{token}"


def _create_stage(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_infoelectoral_candidate_stage (
          candidate_occurrence_id TEXT PRIMARY KEY,
          source_record_id TEXT NOT NULL,
          archive_id TEXT NOT NULL,
          election_date TEXT NOT NULL,
          election_type_code TEXT NOT NULL,
          election_year INTEGER NOT NULL,
          election_month INTEGER NOT NULL,
          election_round TEXT NOT NULL,
          province_code TEXT NOT NULL,
          territory_code TEXT NOT NULL,
          district_code TEXT NOT NULL,
          candidate_scope_code TEXT NOT NULL,
          party_source_code TEXT NOT NULL,
          candidate_order INTEGER NOT NULL,
          candidate_type_code TEXT NOT NULL,
          given_name TEXT NOT NULL,
          surname_1 TEXT NOT NULL,
          surname_2 TEXT,
          family_name TEXT NOT NULL,
          full_name TEXT NOT NULL,
          gender_code TEXT NOT NULL,
          birth_date TEXT,
          birth_date_source TEXT,
          dni TEXT,
          is_elected INTEGER NOT NULL,
          candidacy_name TEXT NOT NULL,
          candidacy_acronym TEXT,
          party_province_code TEXT,
          party_autonomy_code TEXT,
          party_national_code TEXT,
          source_url TEXT NOT NULL,
          source_content_sha256 TEXT NOT NULL,
          source_member_name TEXT NOT NULL,
          source_line_number INTEGER NOT NULL,
          person_canonical_key TEXT NOT NULL,
          raw_payload TEXT NOT NULL,
          row_content_sha256 TEXT NOT NULL
        ) WITHOUT ROWID
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_infoelectoral_candidate_seen (
          candidate_occurrence_id TEXT PRIMARY KEY
        ) WITHOUT ROWID
        """
    )


def _stage_rows(records: list[CandidateRecord]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for record in records:
        raw_payload = record.public_source_payload()
        family_name = " ".join(
            value for value in (record.surname_1, record.surname_2) if value
        )
        rows.append(
            (
                record.candidate_occurrence_id,
                record.source_record_id,
                record.archive_id,
                record.election_date,
                record.election_type_code,
                record.election_year,
                record.election_month,
                record.election_round,
                record.province_code,
                _territory_code(record.province_code),
                record.district_code,
                record.candidate_scope_code,
                record.party_source_code,
                record.candidate_order,
                record.candidate_type_code,
                record.given_name,
                record.surname_1,
                record.surname_2,
                family_name,
                record.full_name,
                _gender_code(record.gender_code),
                record.birth_date,
                record.birth_date_source,
                record.dni,
                record.is_elected,
                record.candidacy_name,
                record.candidacy_acronym,
                record.party_province_code,
                record.party_autonomy_code,
                record.party_national_code,
                record.source_url,
                record.source_content_sha256,
                record.source_member_name,
                record.source_line_number,
                "infoelectoral-candidate-occurrence:"
                + record.candidate_occurrence_id,
                raw_payload,
                hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
            )
        )
    return rows


def upsert_candidate_archive_catalog(
    conn: sqlite3.Connection,
    *,
    spec: CandidateArchiveSpec,
    snapshot_date: str,
) -> None:
    now_iso = now_utc_iso()
    conn.execute(
        """
        INSERT INTO infoelectoral_candidate_archives (
          archive_id, election_id, election_date, election_type_code,
          source_url, first_seen_snapshot_date, last_seen_snapshot_date,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(archive_id) DO UPDATE SET
          election_id=excluded.election_id,
          election_date=excluded.election_date,
          election_type_code=excluded.election_type_code,
          source_url=excluded.source_url,
          last_seen_snapshot_date=excluded.last_seen_snapshot_date,
          updated_at=excluded.updated_at
        """,
        (
            spec.archive_id,
            spec.election_id,
            spec.election_date,
            spec.election_type_code,
            spec.source_url,
            snapshot_date,
            snapshot_date,
            now_iso,
            now_iso,
        ),
    )
    conn.commit()


def _ingest_batch(
    conn: sqlite3.Connection,
    records: list[CandidateRecord],
    *,
    snapshot_date: str,
    now_iso: str,
    run_id: int | None,
) -> None:
    conn.execute("DELETE FROM ingest_infoelectoral_candidate_stage")
    conn.executemany(
        """
        INSERT INTO ingest_infoelectoral_candidate_stage (
          candidate_occurrence_id, source_record_id, archive_id, election_date,
          election_type_code, election_year, election_month, election_round,
          province_code, territory_code, district_code, candidate_scope_code,
          party_source_code, candidate_order, candidate_type_code, given_name,
          surname_1, surname_2, family_name, full_name, gender_code,
          birth_date, birth_date_source, dni, is_elected,
          candidacy_name, candidacy_acronym, party_province_code,
          party_autonomy_code, party_national_code, source_url,
          source_content_sha256, source_member_name, source_line_number,
          person_canonical_key, raw_payload, row_content_sha256
        ) VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        _stage_rows(records),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO ingest_infoelectoral_candidate_seen (
          candidate_occurrence_id
        )
        SELECT candidate_occurrence_id FROM ingest_infoelectoral_candidate_stage
        """
    )
    conn.execute(
        """
        INSERT INTO territories (
          code, name, level, parent_territory_id, created_at, updated_at
        )
        SELECT DISTINCT
          territory_code,
          CASE WHEN territory_code = 'ES' THEN 'España'
               ELSE 'Provincia ' || province_code END,
          CASE WHEN territory_code = 'ES' THEN 'country' ELSE 'province' END,
          NULL, ?, ?
        FROM ingest_infoelectoral_candidate_stage
        WHERE 1
        ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO genders (code, label, created_at, updated_at)
        SELECT gender_code,
               CASE gender_code WHEN 'female' THEN 'Mujer'
                                WHEN 'male' THEN 'Hombre'
                                ELSE 'Desconocido' END,
               ?, ?
        FROM ingest_infoelectoral_candidate_stage
        GROUP BY gender_code
        ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        SELECT candidacy_name, MAX(NULLIF(candidacy_acronym, '')), ?, ?
        FROM ingest_infoelectoral_candidate_stage
        GROUP BY candidacy_name
        ON CONFLICT(name) DO UPDATE SET
          acronym=COALESCE(parties.acronym, excluded.acronym),
          updated_at=excluded.updated_at
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
        FROM ingest_infoelectoral_candidate_stage
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
          full_name, given_name, family_name, gender, gender_id, birth_date,
          territory_code, territory_id, canonical_key, created_at, updated_at
        )
        SELECT stage.full_name, stage.given_name, stage.family_name,
               stage.gender_code, gender.gender_id, stage.birth_date,
               stage.territory_code, territory.territory_id,
               stage.person_canonical_key, ?, ?
        FROM ingest_infoelectoral_candidate_stage AS stage
        JOIN genders AS gender ON gender.code = stage.gender_code
        JOIN territories AS territory ON territory.code = stage.territory_code
        WHERE 1
        ON CONFLICT(canonical_key) DO UPDATE SET
          full_name=excluded.full_name,
          given_name=excluded.given_name,
          family_name=excluded.family_name,
          gender=excluded.gender,
          gender_id=excluded.gender_id,
          birth_date=excluded.birth_date,
          territory_code=excluded.territory_code,
          territory_id=excluded.territory_id,
          updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO infoelectoral_candidate_occurrences (
          candidate_occurrence_id, archive_id, election_date,
          election_type_code, election_year, election_month, election_round,
          province_code, district_code, candidate_scope_code,
          party_source_code, candidate_order, candidate_type_code, given_name,
          surname_1, surname_2, full_name, gender_code,
          birth_date, birth_date_source, dni, is_elected,
          candidacy_name, candidacy_acronym, party_province_code,
          party_autonomy_code, party_national_code, person_id, party_id,
          territory_id, source_id, source_record_pk, source_url,
          source_content_sha256, source_member_name, source_line_number,
          first_seen_snapshot_date, last_seen_snapshot_date, is_present,
          raw_payload, created_at, updated_at
        )
        SELECT
          stage.candidate_occurrence_id, stage.archive_id, stage.election_date,
          stage.election_type_code, stage.election_year, stage.election_month,
          stage.election_round, stage.province_code, stage.district_code,
          stage.candidate_scope_code, stage.party_source_code,
          stage.candidate_order, stage.candidate_type_code, stage.given_name,
          stage.surname_1, stage.surname_2, stage.full_name, stage.gender_code,
          stage.birth_date, stage.birth_date_source, stage.dni, stage.is_elected,
          stage.candidacy_name, stage.candidacy_acronym,
          stage.party_province_code, stage.party_autonomy_code,
          stage.party_national_code, person.person_id, party.party_id,
          territory.territory_id, ?, source_record.source_record_pk,
          stage.source_url, stage.source_content_sha256,
          stage.source_member_name, stage.source_line_number, ?, ?, 0,
          stage.raw_payload, ?, ?
        FROM ingest_infoelectoral_candidate_stage AS stage
        JOIN persons AS person
          ON person.canonical_key = stage.person_canonical_key
        JOIN parties AS party ON party.name = stage.candidacy_name
        JOIN territories AS territory ON territory.code = stage.territory_code
        JOIN source_records AS source_record
          ON source_record.source_id = ?
         AND source_record.source_record_id = stage.source_record_id
        WHERE 1
        ON CONFLICT(candidate_occurrence_id) DO UPDATE SET
          election_date=excluded.election_date,
          given_name=excluded.given_name,
          surname_1=excluded.surname_1,
          surname_2=excluded.surname_2,
          full_name=excluded.full_name,
          gender_code=excluded.gender_code,
          birth_date=excluded.birth_date,
          birth_date_source=excluded.birth_date_source,
          dni=excluded.dni,
          is_elected=excluded.is_elected,
          candidacy_name=excluded.candidacy_name,
          candidacy_acronym=excluded.candidacy_acronym,
          party_province_code=excluded.party_province_code,
          party_autonomy_code=excluded.party_autonomy_code,
          party_national_code=excluded.party_national_code,
          person_id=excluded.person_id,
          party_id=excluded.party_id,
          territory_id=excluded.territory_id,
          source_record_pk=excluded.source_record_pk,
          source_url=excluded.source_url,
          source_content_sha256=excluded.source_content_sha256,
          source_member_name=excluded.source_member_name,
          source_line_number=excluded.source_line_number,
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            SOURCE_ID,
            snapshot_date,
            snapshot_date,
            now_iso,
            now_iso,
            SOURCE_ID,
        ),
    )
    conn.execute(
        """
        INSERT INTO infoelectoral_candidate_observations (
          candidate_occurrence_id, source_record_pk, run_id, snapshot_date,
          source_url, source_content_sha256, source_member_name,
          source_line_number, row_content_sha256, first_observed_at,
          last_observed_at
        )
        SELECT fact.candidate_occurrence_id, fact.source_record_pk, ?, ?,
               stage.source_url, stage.source_content_sha256,
               stage.source_member_name, stage.source_line_number,
               stage.row_content_sha256, ?, ?
        FROM ingest_infoelectoral_candidate_stage AS stage
        JOIN infoelectoral_candidate_occurrences AS fact
          ON fact.candidate_occurrence_id = stage.candidate_occurrence_id
        WHERE 1
        ON CONFLICT(
          candidate_occurrence_id, snapshot_date, source_content_sha256
        ) DO UPDATE SET
          source_record_pk=excluded.source_record_pk,
          run_id=COALESCE(excluded.run_id,
                          infoelectoral_candidate_observations.run_id),
          source_url=excluded.source_url,
          source_member_name=excluded.source_member_name,
          source_line_number=excluded.source_line_number,
          row_content_sha256=excluded.row_content_sha256,
          last_observed_at=excluded.last_observed_at
        """,
        (run_id, snapshot_date, now_iso, now_iso),
    )


def ingest_candidate_archive(
    conn: sqlite3.Connection,
    records: Iterable[CandidateRecord],
    *,
    spec: CandidateArchiveSpec,
    snapshot_date: str,
    source_content_sha256: str,
    archive_bytes: int,
    raw_path: str,
    party_rows: int,
    batch_rows: int = 10_000,
    run_id: int | None = None,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    _create_stage(conn)
    conn.execute("DELETE FROM ingest_infoelectoral_candidate_seen")
    processed = 0
    batches = 0
    for batch in _chunks(records, int(batch_rows)):
        with conn:
            _ingest_batch(
                conn,
                batch,
                snapshot_date=snapshot_date,
                now_iso=now_iso,
                run_id=run_id,
            )
        processed += len(batch)
        batches += 1
    if processed == 0:
        raise RuntimeError("candidate archive ingest requires at least one record")
    with conn:
        conn.execute(
            """
            UPDATE infoelectoral_candidate_occurrences AS fact
            SET is_present = CASE WHEN EXISTS (
                  SELECT 1 FROM ingest_infoelectoral_candidate_seen AS seen
                  WHERE seen.candidate_occurrence_id = fact.candidate_occurrence_id
                ) THEN 1 ELSE 0 END,
                last_seen_snapshot_date = CASE WHEN EXISTS (
                  SELECT 1 FROM ingest_infoelectoral_candidate_seen AS seen
                  WHERE seen.candidate_occurrence_id = fact.candidate_occurrence_id
                ) THEN ? ELSE last_seen_snapshot_date END,
                updated_at = ?
            WHERE fact.archive_id = ?
            """,
            (snapshot_date, now_iso, spec.archive_id),
        )
        conn.execute(
            """
            UPDATE infoelectoral_candidate_archives
            SET source_content_sha256=?, archive_bytes=?, raw_path=?,
                candidate_rows=?, party_rows=?, status='loaded', last_error=NULL,
                last_seen_snapshot_date=?, updated_at=?
            WHERE archive_id=?
            """,
            (
                source_content_sha256,
                int(archive_bytes),
                raw_path,
                processed,
                int(party_rows),
                snapshot_date,
                now_iso,
                spec.archive_id,
            ),
        )
    conn.execute("DELETE FROM ingest_infoelectoral_candidate_stage")
    conn.execute("DELETE FROM ingest_infoelectoral_candidate_seen")
    return {
        "processed": processed,
        "batches": batches,
        "batch_rows": int(batch_rows),
        "archive_id": spec.archive_id,
        "party_rows": int(party_rows),
    }


def candidate_report(conn: sqlite3.Connection) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT COUNT(*) AS rows,
               SUM(is_present) AS present_rows,
               SUM(CASE WHEN is_present=0 THEN 1 ELSE 0 END) AS absent_rows,
               COUNT(DISTINCT person_id) AS people,
               COUNT(DISTINCT archive_id) AS archives,
               COUNT(DISTINCT election_date) AS elections,
               COUNT(DISTINCT party_id) AS parties,
               SUM(CASE WHEN source_record_pk IS NOT NULL THEN 1 ELSE 0 END)
                 AS source_record_rows,
               SUM(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END)
                 AS person_rows,
               SUM(CASE WHEN party_id IS NOT NULL THEN 1 ELSE 0 END)
                 AS party_rows
        FROM infoelectoral_candidate_occurrences
        WHERE source_id=?
        """,
        (SOURCE_ID,),
    ).fetchone()
    rows = int(totals["rows"] or 0)
    source_records = int(
        conn.execute(
            "SELECT COUNT(*) FROM source_records WHERE source_id=?", (SOURCE_ID,)
        ).fetchone()[0]
    )
    observations = int(
        conn.execute(
            "SELECT COUNT(*) FROM infoelectoral_candidate_observations"
        ).fetchone()[0]
    )
    loaded_archives = int(
        conn.execute(
            "SELECT COUNT(*) FROM infoelectoral_candidate_archives WHERE status='loaded'"
        ).fetchone()[0]
    )
    archive_totals = conn.execute(
        """
        SELECT COALESCE(SUM(candidate_rows), 0) AS candidate_rows,
               COALESCE(SUM(party_rows), 0) AS party_rows,
               SUM(CASE WHEN party_rows > 0 THEN 1 ELSE 0 END)
                 AS archives_with_party_rows
        FROM infoelectoral_candidate_archives
        WHERE status='loaded'
        """
    ).fetchone()
    checks = {
        "source_records_reconcile": source_records == rows,
        "occurrence_people_reconcile": int(totals["people"] or 0) == rows,
        "source_record_links_complete": int(totals["source_record_rows"] or 0)
        == rows,
        "person_links_complete": int(totals["person_rows"] or 0) == rows,
        "party_links_complete": int(totals["party_rows"] or 0) == rows,
        "observation_coverage_complete": observations >= rows,
        "presence_balance": int(totals["present_rows"] or 0)
        + int(totals["absent_rows"] or 0)
        == rows,
        "archive_candidate_rows_reconcile": int(
            archive_totals["candidate_rows"] or 0
        )
        == int(totals["present_rows"] or 0),
        "loaded_archives_have_party_rows": int(
            archive_totals["archives_with_party_rows"] or 0
        )
        == loaded_archives,
    }
    return {
        "schema_version": "infoelectoral_candidates_report_v1",
        "source_id": SOURCE_ID,
        "status": "ok" if rows > 0 and all(checks.values()) else "not_ready",
        "public_domain_identity": {
            "official_archive_retained": True,
            "normalized_birth_date_persisted": True,
            "source_birth_date_persisted": True,
            "dni_persisted": True,
        },
        "identity_assurance": (
            "source_scoped_election_occurrence; cross-election person resolution "
            "not asserted"
        ),
        "totals": {
            "candidate_occurrences": rows,
            "present_candidate_occurrences": int(totals["present_rows"] or 0),
            "absent_candidate_occurrences": int(totals["absent_rows"] or 0),
            "occurrence_people": int(totals["people"] or 0),
            "cataloged_archives": int(
                conn.execute(
                    "SELECT COUNT(*) FROM infoelectoral_candidate_archives"
                ).fetchone()[0]
            ),
            "loaded_archives": loaded_archives,
            "latest_archive_candidate_rows": int(
                archive_totals["candidate_rows"] or 0
            ),
            "source_party_rows": int(archive_totals["party_rows"] or 0),
            "archives_with_facts": int(totals["archives"] or 0),
            "elections": int(totals["elections"] or 0),
            "parties": int(totals["parties"] or 0),
            "source_records": source_records,
            "observations": observations,
        },
        "checks": checks,
    }


__all__ = [
    "candidate_report",
    "ingest_candidate_archive",
    "upsert_candidate_archive_catalog",
]
