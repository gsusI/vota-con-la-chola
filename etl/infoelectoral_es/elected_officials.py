"""Set-based ingestion for official historical elected-official facts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from publicdata_connectors_es.infoelectoral.elected_officials import (
    ElectedOfficialRecord,
    SOURCE_ID,
)

from ..politicos_es.util import now_utc_iso


def _chunks(
    records: Iterable[ElectedOfficialRecord], batch_rows: int
) -> Iterator[list[ElectedOfficialRecord]]:
    if int(batch_rows) < 1:
        raise ValueError("batch_rows must be >= 1")
    batch: list[ElectedOfficialRecord] = []
    for record in records:
        batch.append(record)
        if len(batch) >= int(batch_rows):
            yield batch
            batch = []
    if batch:
        yield batch


def _create_stage(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_infoelectoral_elected_stage (
          source_record_id TEXT PRIMARY KEY,
          elected_official_id TEXT NOT NULL,
          election_date TEXT NOT NULL,
          election_code TEXT NOT NULL,
          chamber TEXT NOT NULL,
          role_title TEXT NOT NULL,
          institution_name TEXT NOT NULL,
          province_code TEXT NOT NULL,
          province_name TEXT NOT NULL,
          territory_code TEXT NOT NULL,
          district TEXT,
          constituency TEXT,
          full_name TEXT NOT NULL,
          candidacy_name TEXT NOT NULL,
          candidacy_acronym TEXT,
          votes INTEGER,
          source_url TEXT NOT NULL,
          source_content_sha256 TEXT NOT NULL,
          source_row_number INTEGER NOT NULL,
          person_canonical_key TEXT NOT NULL,
          raw_payload TEXT NOT NULL,
          content_sha256 TEXT NOT NULL
        ) WITHOUT ROWID
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_infoelectoral_elected_seen (
          elected_official_id TEXT PRIMARY KEY
        ) WITHOUT ROWID
        """
    )


def _stage_rows(records: list[ElectedOfficialRecord]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for record in records:
        raw_payload = record.raw_payload()
        rows.append(
            (
                record.source_record_id,
                record.elected_official_id,
                record.election_date,
                record.election_code,
                record.chamber,
                record.role_title,
                record.institution_name,
                record.province_code,
                record.province_name,
                record.territory_code,
                record.district,
                record.constituency,
                record.full_name,
                record.candidacy_name,
                record.candidacy_acronym,
                record.votes,
                record.source_url,
                record.source_content_sha256,
                record.source_row_number,
                "infoelectoral-elected:" + record.source_record_id,
                raw_payload,
                hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
            )
        )
    return rows


def _ingest_batch(
    conn: sqlite3.Connection,
    records: list[ElectedOfficialRecord],
    *,
    snapshot_date: str,
    now_iso: str,
    run_id: int | None,
) -> None:
    conn.execute("DELETE FROM ingest_infoelectoral_elected_stage")
    conn.executemany(
        """
        INSERT INTO ingest_infoelectoral_elected_stage (
          source_record_id, elected_official_id, election_date, election_code,
          chamber, role_title, institution_name, province_code, province_name,
          territory_code, district, constituency, full_name, candidacy_name,
          candidacy_acronym, votes, source_url, source_content_sha256,
          source_row_number, person_canonical_key, raw_payload, content_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _stage_rows(records),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO ingest_infoelectoral_elected_seen (
          elected_official_id
        )
        SELECT elected_official_id
        FROM ingest_infoelectoral_elected_stage
        """
    )
    conn.execute(
        """
        INSERT INTO territories (
          code, name, level, parent_territory_id, created_at, updated_at
        )
        SELECT DISTINCT territory_code, province_name, 'province', NULL, ?, ?
        FROM ingest_infoelectoral_elected_stage
        WHERE 1
        ON CONFLICT(code) DO UPDATE SET
          name=excluded.name,
          level=COALESCE(territories.level, excluded.level),
          updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        SELECT candidacy_name, MAX(NULLIF(candidacy_acronym, '')), ?, ?
        FROM ingest_infoelectoral_elected_stage
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
        SELECT ?, source_record_id, ?, raw_payload, content_sha256, ?, ?
        FROM ingest_infoelectoral_elected_stage
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
        SELECT
          full_name, NULL, NULL, NULL, NULL, NULL, territory_code,
          territory.territory_id, person_canonical_key, ?, ?
        FROM ingest_infoelectoral_elected_stage stage
        JOIN territories territory ON territory.code = stage.territory_code
        WHERE 1
        ON CONFLICT(canonical_key) DO UPDATE SET
          full_name=excluded.full_name,
          territory_code=excluded.territory_code,
          territory_id=excluded.territory_id,
          updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO infoelectoral_elected_officials (
          elected_official_id, election_date, election_code, chamber,
          province_code, province_name, district, constituency, full_name,
          candidacy_name, candidacy_acronym, votes, source_id,
          source_record_pk, source_url, source_content_sha256,
          source_row_number, first_seen_snapshot_date,
          last_seen_snapshot_date, is_present, raw_payload, created_at,
          updated_at
        )
        SELECT
          stage.elected_official_id, stage.election_date, stage.election_code,
          stage.chamber, stage.province_code, stage.province_name,
          stage.district, stage.constituency, stage.full_name,
          stage.candidacy_name, stage.candidacy_acronym, stage.votes, ?,
          source_record.source_record_pk, stage.source_url,
          stage.source_content_sha256, stage.source_row_number, ?, ?, 0,
          stage.raw_payload, ?, ?
        FROM ingest_infoelectoral_elected_stage stage
        JOIN source_records source_record
          ON source_record.source_id = ?
         AND source_record.source_record_id = stage.source_record_id
        WHERE 1
        ON CONFLICT(elected_official_id) DO UPDATE SET
          election_date=excluded.election_date,
          election_code=excluded.election_code,
          chamber=excluded.chamber,
          province_code=excluded.province_code,
          province_name=excluded.province_name,
          district=excluded.district,
          constituency=excluded.constituency,
          full_name=excluded.full_name,
          candidacy_name=excluded.candidacy_name,
          candidacy_acronym=excluded.candidacy_acronym,
          votes=excluded.votes,
          source_record_pk=excluded.source_record_pk,
          source_url=excluded.source_url,
          source_content_sha256=excluded.source_content_sha256,
          source_row_number=excluded.source_row_number,
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
        INSERT INTO infoelectoral_elected_official_observations (
          elected_official_id, source_record_pk, run_id, snapshot_date,
          source_url, source_content_sha256, source_row_number,
          row_content_sha256, first_observed_at, last_observed_at
        )
        SELECT
          fact.elected_official_id, fact.source_record_pk, ?, ?,
          stage.source_url, stage.source_content_sha256,
          stage.source_row_number, stage.content_sha256, ?, ?
        FROM ingest_infoelectoral_elected_stage stage
        JOIN infoelectoral_elected_officials fact
          ON fact.elected_official_id = stage.elected_official_id
        WHERE 1
        ON CONFLICT(
          elected_official_id, snapshot_date, source_content_sha256
        ) DO UPDATE SET
          source_record_pk=excluded.source_record_pk,
          run_id=COALESCE(excluded.run_id,
                          infoelectoral_elected_official_observations.run_id),
          source_url=excluded.source_url,
          source_row_number=excluded.source_row_number,
          row_content_sha256=excluded.row_content_sha256,
          last_observed_at=excluded.last_observed_at
        """,
        (run_id, snapshot_date, now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO mandates (
          person_id, institution_id, party_id, role_title, role_id, level,
          admin_level_id, territory_code, territory_id, start_date, end_date,
          is_active, source_id, source_record_id, source_record_pk,
          source_snapshot_date, first_seen_at, last_seen_at, raw_payload
        )
        SELECT
          person.person_id, institution.institution_id, party.party_id,
          stage.role_title, role.role_id, 'Nacional', admin.admin_level_id,
          stage.territory_code, territory.territory_id, stage.election_date,
          NULL, 0, ?, stage.source_record_id, source_record.source_record_pk,
          ?, ?, ?, stage.raw_payload
        FROM ingest_infoelectoral_elected_stage stage
        JOIN persons person ON person.canonical_key = stage.person_canonical_key
        JOIN institutions institution
          ON institution.name = stage.institution_name
         AND institution.level = 'Nacional'
         AND institution.territory_code = ''
        JOIN parties party ON party.name = stage.candidacy_name
        JOIN roles role ON role.title = stage.role_title
        JOIN admin_levels admin ON admin.code = 'nacional'
        JOIN territories territory ON territory.code = stage.territory_code
        JOIN source_records source_record
          ON source_record.source_id = ?
         AND source_record.source_record_id = stage.source_record_id
        WHERE 1
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          person_id=excluded.person_id,
          institution_id=excluded.institution_id,
          party_id=excluded.party_id,
          role_title=excluded.role_title,
          role_id=excluded.role_id,
          level=excluded.level,
          admin_level_id=excluded.admin_level_id,
          territory_code=excluded.territory_code,
          territory_id=excluded.territory_id,
          start_date=excluded.start_date,
          end_date=NULL,
          is_active=0,
          source_record_pk=excluded.source_record_pk,
          source_snapshot_date=excluded.source_snapshot_date,
          last_seen_at=excluded.last_seen_at,
          raw_payload=excluded.raw_payload
        """,
        (
            SOURCE_ID,
            snapshot_date,
            now_iso,
            now_iso,
            SOURCE_ID,
        ),
    )
    conn.execute(
        """
        UPDATE infoelectoral_elected_officials AS fact
        SET person_id = mandate.person_id,
            mandate_id = mandate.mandate_id,
            party_id = mandate.party_id,
            institution_id = mandate.institution_id,
            role_id = mandate.role_id,
            territory_id = mandate.territory_id,
            updated_at = ?
        FROM mandates AS mandate
        WHERE fact.source_id = ?
          AND mandate.source_id = ?
          AND mandate.source_record_pk = fact.source_record_pk
          AND EXISTS (
            SELECT 1 FROM ingest_infoelectoral_elected_stage AS stage
            WHERE stage.elected_official_id = fact.elected_official_id
          )
        """,
        (now_iso, SOURCE_ID, SOURCE_ID),
    )


def _seed_dimensions(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.execute(
        """
        INSERT INTO admin_levels (code, label, created_at, updated_at)
        VALUES ('nacional', 'Nacional', ?, ?)
        ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (now_iso, now_iso),
    )
    for role_title in ("Diputado electo", "Senador electo"):
        canonical = role_title.lower().replace(" ", "-")
        conn.execute(
            """
            INSERT INTO roles (title, canonical_key, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
              title=excluded.title,
              updated_at=excluded.updated_at
            """,
            (role_title, canonical, now_iso, now_iso),
        )
    for institution_name in ("Congreso de los Diputados", "Senado de España"):
        conn.execute(
            """
            INSERT INTO institutions (
              name, level, admin_level_id, territory_code, territory_id,
              created_at, updated_at
            )
            SELECT ?, 'Nacional', admin_level_id, '', NULL, ?, ?
            FROM admin_levels WHERE code = 'nacional'
            ON CONFLICT(name, level, territory_code) DO UPDATE SET
              admin_level_id=excluded.admin_level_id,
              updated_at=excluded.updated_at
            """,
            (institution_name, now_iso, now_iso),
        )


def _finalize_presence(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        UPDATE infoelectoral_elected_officials AS fact
        SET is_present = CASE WHEN EXISTS (
              SELECT 1 FROM ingest_infoelectoral_elected_seen AS seen
              WHERE seen.elected_official_id = fact.elected_official_id
            ) THEN 1 ELSE 0 END,
            last_seen_snapshot_date = CASE WHEN EXISTS (
              SELECT 1 FROM ingest_infoelectoral_elected_seen AS seen
              WHERE seen.elected_official_id = fact.elected_official_id
            ) THEN ? ELSE last_seen_snapshot_date END,
            updated_at = ?
        WHERE fact.source_id = ?
        """,
        (snapshot_date, now_iso, SOURCE_ID),
    )


def ingest_elected_officials(
    conn: sqlite3.Connection,
    records: Iterable[ElectedOfficialRecord],
    *,
    snapshot_date: str,
    batch_rows: int = 5_000,
    run_id: int | None = None,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    _create_stage(conn)
    conn.execute("DELETE FROM ingest_infoelectoral_elected_seen")
    with conn:
        _seed_dimensions(conn, now_iso)
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
        raise RuntimeError("elected-official ingest requires at least one record")
    with conn:
        _finalize_presence(
            conn,
            snapshot_date=snapshot_date,
            now_iso=now_iso,
        )
    conn.execute("DELETE FROM ingest_infoelectoral_elected_stage")
    conn.execute("DELETE FROM ingest_infoelectoral_elected_seen")
    return {"processed": processed, "batches": batches, "batch_rows": int(batch_rows)}


def elected_officials_report(conn: sqlite3.Connection) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          COUNT(*) AS elected_officials,
          SUM(is_present) AS present_elected_officials,
          SUM(CASE WHEN is_present = 0 THEN 1 ELSE 0 END)
            AS absent_elected_officials,
          COUNT(DISTINCT full_name) AS distinct_official_labels,
          COUNT(DISTINCT election_date) AS elections,
          COUNT(DISTINCT candidacy_name) AS candidacies,
          COUNT(DISTINCT source_content_sha256) AS workbook_versions,
          MIN(election_date) AS first_election_date,
          MAX(election_date) AS last_election_date,
          SUM(CASE WHEN source_record_pk IS NOT NULL THEN 1 ELSE 0 END)
            AS source_record_rows,
          SUM(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END)
            AS person_link_rows,
          SUM(CASE WHEN mandate_id IS NOT NULL THEN 1 ELSE 0 END)
            AS mandate_link_rows,
          SUM(CASE WHEN party_id IS NOT NULL THEN 1 ELSE 0 END)
            AS party_link_rows,
          SUM(CASE WHEN institution_id IS NOT NULL THEN 1 ELSE 0 END)
            AS institution_link_rows,
          SUM(CASE WHEN role_id IS NOT NULL THEN 1 ELSE 0 END)
            AS role_link_rows,
          SUM(CASE WHEN territory_id IS NOT NULL THEN 1 ELSE 0 END)
            AS territory_link_rows,
          SUM(CASE WHEN first_seen_snapshot_date != ''
                    AND last_seen_snapshot_date != '' THEN 1 ELSE 0 END)
            AS snapshot_state_rows
        FROM infoelectoral_elected_officials
        WHERE source_id = ?
        """,
        (SOURCE_ID,),
    ).fetchone()
    chambers = {
        str(row["chamber"]): int(row["rows"])
        for row in conn.execute(
            """
            SELECT chamber, COUNT(*) AS rows
            FROM infoelectoral_elected_officials
            WHERE source_id = ? AND is_present = 1
            GROUP BY chamber ORDER BY chamber
            """,
            (SOURCE_ID,),
        )
    }
    elected_total = int(totals["elected_officials"] or 0)
    present_total = int(totals["present_elected_officials"] or 0)
    absent_total = int(totals["absent_elected_officials"] or 0)
    mandates = int(
        conn.execute(
            "SELECT COUNT(*) FROM mandates WHERE source_id = ?", (SOURCE_ID,)
        ).fetchone()[0]
    )
    source_records = int(
        conn.execute(
            "SELECT COUNT(*) FROM source_records WHERE source_id = ?", (SOURCE_ID,)
        ).fetchone()[0]
    )
    occurrence_people = int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT person_id)
            FROM mandates WHERE source_id = ?
            """,
            (SOURCE_ID,),
        ).fetchone()[0]
    )
    exact_duplicate_groups = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT election_date, chamber, province_code, full_name,
                     candidacy_name, COUNT(*) AS rows
              FROM infoelectoral_elected_officials
              WHERE source_id = ?
              GROUP BY election_date, chamber, province_code, district,
                       constituency, full_name, candidacy_name,
                       candidacy_acronym
              HAVING COUNT(*) > 1
            )
            """,
            (SOURCE_ID,),
        ).fetchone()[0]
    )
    observations = conn.execute(
        """
        SELECT COUNT(*) AS rows,
               COUNT(DISTINCT elected_official_id) AS elected_officials,
               COUNT(DISTINCT source_content_sha256) AS workbook_versions,
               COUNT(DISTINCT snapshot_date) AS snapshots,
               COUNT(DISTINCT run_id) AS runs
        FROM infoelectoral_elected_official_observations
        """
    ).fetchone()
    checks = {
        "nonzero": elected_total > 0,
        "source_records_reconcile": source_records == elected_total,
        "mandates_reconcile": mandates == elected_total,
        "occurrence_people_reconcile": occurrence_people == elected_total,
        "source_record_fk_complete": int(totals["source_record_rows"] or 0)
        == elected_total,
        "direct_person_links_complete": int(totals["person_link_rows"] or 0)
        == elected_total,
        "direct_mandate_links_complete": int(totals["mandate_link_rows"] or 0)
        == elected_total,
        "direct_party_links_complete": int(totals["party_link_rows"] or 0)
        == elected_total,
        "direct_institution_links_complete": int(
            totals["institution_link_rows"] or 0
        )
        == elected_total,
        "direct_role_links_complete": int(totals["role_link_rows"] or 0)
        == elected_total,
        "direct_territory_links_complete": int(totals["territory_link_rows"] or 0)
        == elected_total,
        "snapshot_state_complete": int(totals["snapshot_state_rows"] or 0)
        == elected_total,
        "observation_coverage_complete": int(observations["elected_officials"] or 0)
        == elected_total,
        "presence_balance": present_total + absent_total == elected_total,
        "both_chambers_present": set(chambers) == {"congreso", "senado"},
        "no_exact_duplicate_outcomes": exact_duplicate_groups == 0,
    }
    return {
        "schema_version": "infoelectoral_elected_officials_ingest_v2",
        "source_id": SOURCE_ID,
        "status": "ok" if all(checks.values()) else "failed",
        "identity_assurance": (
            "source_scoped_election_occurrence; cross-election person resolution "
            "not asserted"
        ),
        "publication_status": "local_official_not_published",
        "totals": {
            "elected_officials": elected_total,
            "present_elected_officials": present_total,
            "absent_elected_officials": absent_total,
            "distinct_official_labels": int(totals["distinct_official_labels"] or 0),
            "elections": int(totals["elections"] or 0),
            "candidacies": int(totals["candidacies"] or 0),
            "workbook_versions": int(totals["workbook_versions"] or 0),
            "first_election_date": totals["first_election_date"],
            "last_election_date": totals["last_election_date"],
            "source_records": source_records,
            "mandates": mandates,
            "occurrence_people": occurrence_people,
            "observations": int(observations["rows"] or 0),
            "observed_officials": int(observations["elected_officials"] or 0),
            "observation_snapshots": int(observations["snapshots"] or 0),
            "observation_runs": int(observations["runs"] or 0),
            "observation_workbook_versions": int(
                observations["workbook_versions"] or 0
            ),
            "exact_duplicate_groups": exact_duplicate_groups,
        },
        "by_chamber": chambers,
        "checks": checks,
    }


def records_from_sample(path: str) -> list[ElectedOfficialRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("elected-official sample must be a JSON list")
    return [ElectedOfficialRecord(**dict(row)) for row in payload]


__all__ = [
    "elected_officials_report",
    "ingest_elected_officials",
    "records_from_sample",
]
