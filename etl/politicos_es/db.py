from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from publicdata_sqlite import ensure_column, open_db, seed_sources_from_config
from publicdata_sqlite import table_columns, table_create_sql, table_exists
from publicdata_sqlite import upsert_source_record as _upsert_source_record

from .config import SOURCE_CONFIG
from .util import canonical_key, normalize_key_part, normalize_ws, now_utc_iso


_UNIQUE_SOURCE_URL_RE = re.compile(
    r"UNIQUE\s*\(\s*source_id\s*,\s*source_url\s*\)", re.I
)


def ensure_indicator_observations_allow_ree(conn: sqlite3.Connection) -> None:
    """Upgrade the legacy indicator-observation source constraint in place."""
    table = "indicator_observation_records"
    if not table_exists(conn, table):
        return
    sql = table_create_sql(conn, table)
    if "source_id LIKE 'ree_%'" in sql:
        return
    backup = "indicator_observation_records_legacy_source_check"
    if table_exists(conn, backup):
        raise RuntimeError(
            f"Schema migration blocked: found unexpected table '{backup}'"
        )
    if conn.in_transaction:
        conn.commit()
    fk_on = int(conn.execute("PRAGMA foreign_keys").fetchone()[0] or 0)
    if fk_on:
        conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN;")
        conn.execute(f'ALTER TABLE "{table}" RENAME TO "{backup}";')
        conn.execute(
            """
            CREATE TABLE indicator_observation_records (
              observation_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
              indicator_series_id INTEGER REFERENCES indicator_series(indicator_series_id) ON DELETE SET NULL,
              source_id TEXT NOT NULL REFERENCES sources(source_id)
                  CHECK (
                    source_id LIKE 'eurostat_%'
                    OR source_id LIKE 'bde_%'
                    OR source_id LIKE 'aemet_%'
                    OR source_id LIKE 'ree_%'
                  ),
              source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
              source_record_id TEXT,
              source_snapshot_date TEXT,
              source_url TEXT,
              series_code TEXT NOT NULL,
              point_date TEXT NOT NULL,
              value REAL,
              value_text TEXT,
              unit TEXT,
              frequency TEXT,
              dimensions_json TEXT,
              methodology_version TEXT,
              raw_payload TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (source_id, series_code, point_date, source_record_id)
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO indicator_observation_records (
              observation_record_id, indicator_series_id, source_id,
              source_record_pk, source_record_id, source_snapshot_date,
              source_url, series_code, point_date, value, value_text, unit,
              frequency, dimensions_json, methodology_version, raw_payload,
              created_at, updated_at
            )
            SELECT
              observation_record_id, indicator_series_id, source_id,
              source_record_pk, source_record_id, source_snapshot_date,
              source_url, series_code, point_date, value, value_text, unit,
              frequency, dimensions_json, methodology_version, raw_payload,
              created_at, updated_at
            FROM "{backup}"
            """
        )
        conn.execute(f'DROP TABLE "{backup}";')
        conn.execute(
            "CREATE INDEX idx_indicator_observation_records_source_series "
            "ON indicator_observation_records(source_id, series_code)"
        )
        conn.execute(
            "CREATE INDEX idx_indicator_observation_records_point_date "
            "ON indicator_observation_records(point_date)"
        )
        conn.execute(
            "CREATE INDEX idx_indicator_observation_records_series_date "
            "ON indicator_observation_records(indicator_series_id, point_date)"
        )
        conn.execute(
            """
            CREATE INDEX idx_indicator_observation_records_partition
            ON indicator_observation_records(
              source_id,
              substr(point_date, 1, 4),
              point_date,
              series_code,
              COALESCE(source_snapshot_date, ''),
              COALESCE(source_record_id, ''),
              observation_record_id
            )
            """
        )
        conn.execute("COMMIT;")
    except Exception:
        try:
            conn.execute("ROLLBACK;")
        except sqlite3.Error:
            pass
        raise
    finally:
        if fk_on:
            conn.execute("PRAGMA foreign_keys = ON;")


def ensure_text_documents_allow_duplicate_urls(conn: sqlite3.Connection) -> None:
    """Fix early schema bug: text_documents must allow repeated source_url.

    Some sources (e.g. Congreso interventions) legitimately reuse the same URL for multiple
    records, so UNIQUE(source_id, source_url) breaks backfills.

    We keep the table shape but rebuild it without that UNIQUE constraint.
    """
    if not table_exists(conn, "text_documents"):
        return
    sql = table_create_sql(conn, "text_documents")
    if not _UNIQUE_SOURCE_URL_RE.search(sql or ""):
        return
    # Avoid clobbering if a previous migration failed halfway.
    if table_exists(conn, "text_documents_old"):
        raise RuntimeError(
            "Schema migration blocked: found unexpected table 'text_documents_old'"
        )

    # PRAGMA foreign_keys can't be toggled mid-transaction.
    if conn.in_transaction:
        conn.commit()

    fk_on = int(conn.execute("PRAGMA foreign_keys").fetchone()[0] or 0)
    if fk_on:
        conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN;")
        conn.execute('ALTER TABLE "text_documents" RENAME TO "text_documents_old";')
        conn.execute(
            """
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              source_url TEXT NOT NULL,
              source_record_pk INTEGER UNIQUE REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
              fetched_at TEXT,
              content_type TEXT,
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT,
              text_chars INTEGER,
              text_path TEXT,
              text_sha256 TEXT,
              text_extraction_method TEXT,
              text_extracted_at TEXT,
              text_truncated INTEGER NOT NULL DEFAULT 0 CHECK (text_truncated IN (0, 1)),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO text_documents (
              text_document_id,
              source_id,
              source_url,
              source_record_pk,
              fetched_at,
              content_type,
              content_sha256,
              bytes,
              raw_path,
              text_excerpt,
              text_chars,
              text_path,
              text_sha256,
              text_extraction_method,
              text_extracted_at,
              text_truncated,
              created_at,
              updated_at
            )
            SELECT
              text_document_id,
              source_id,
              source_url,
              source_record_pk,
              fetched_at,
              content_type,
              content_sha256,
              bytes,
              raw_path,
              text_excerpt,
              text_chars,
              text_path,
              text_sha256,
              text_extraction_method,
              text_extracted_at,
              text_truncated,
              created_at,
              updated_at
            FROM text_documents_old
            """
        )
        conn.execute('DROP TABLE "text_documents_old";')
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_documents_source_id ON text_documents(source_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_documents_source_record_pk ON text_documents(source_record_pk);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_documents_source_url ON text_documents(source_url);"
        )
        conn.execute("COMMIT;")
    except Exception:
        try:
            conn.execute("ROLLBACK;")
        except sqlite3.Error:
            pass
        raise
    finally:
        if fk_on:
            conn.execute("PRAGMA foreign_keys = ON;")


def _ensure_single_pk_table(
    conn: sqlite3.Connection,
    table: str,
    create_sql: str,
    copy_columns: list[str],
    index_sqls: list[str] | None = None,
) -> None:
    """Rebuild tables that still use legacy composite PKs into a surrogate ID PK.

    This preserves existing uniqueness constraints and data while making explorer FK
    label resolution reliable for single-column lookups.
    """
    if not table_exists(conn, table):
        return

    pk_columns = [
        row["name"]
        for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        if int(row["pk"]) > 0
    ]
    if len(pk_columns) == 1:
        return

    backup_table = f"{table}_legacy_pk_migrate"
    if table_exists(conn, backup_table):
        raise RuntimeError(
            f"Schema migration blocked: found unexpected table '{backup_table}'"
        )

    if conn.in_transaction:
        conn.commit()

    fk_on = int(conn.execute("PRAGMA foreign_keys").fetchone()[0] or 0)
    if fk_on:
        conn.execute("PRAGMA foreign_keys = OFF;")

    quoted_table = f'"{table}"'
    quoted_backup = f'"{backup_table}"'
    col_sql = ", ".join(f'"{col}"' for col in copy_columns)

    try:
        conn.execute("BEGIN;")
        conn.execute(f"ALTER TABLE {quoted_table} RENAME TO {quoted_backup};")
        conn.execute(create_sql)
        conn.execute(
            f'INSERT INTO "{table}" ({col_sql}) SELECT {col_sql} FROM {quoted_backup};'
        )
        conn.execute(f"DROP TABLE {quoted_backup};")
        for idx_sql in index_sqls or ():
            conn.execute(idx_sql)
        conn.execute("COMMIT;")
    except Exception:
        try:
            conn.execute("ROLLBACK;")
        except sqlite3.Error:
            pass
        raise
    finally:
        if fk_on:
            conn.execute("PRAGMA foreign_keys = ON;")


def ensure_surrogate_pk_compat(conn: sqlite3.Connection) -> None:
    migrations: list[dict[str, Any]] = [
        {
            "table": "person_identifiers",
            "create_sql": """
            CREATE TABLE person_identifiers (
              person_identifier_id INTEGER PRIMARY KEY AUTOINCREMENT,
              person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
              namespace TEXT NOT NULL,
              value TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
              UNIQUE (namespace, value)
            )
            """,
            "copy_columns": ["person_id", "namespace", "value", "created_at"],
        },
        {
            "table": "parl_vote_event_initiatives",
            "create_sql": """
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
              initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
              link_method TEXT NOT NULL,
              confidence REAL,
              evidence_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (vote_event_id, initiative_id, link_method)
            )
            """,
            "copy_columns": [
                "vote_event_id",
                "initiative_id",
                "link_method",
                "confidence",
                "evidence_json",
                "created_at",
                "updated_at",
            ],
            "index_sqls": [
                "CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_vote ON parl_vote_event_initiatives(vote_event_id);",
                "CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_init ON parl_vote_event_initiatives(initiative_id);",
            ],
        },
        {
            "table": "topic_set_topics",
            "create_sql": """
            CREATE TABLE topic_set_topics (
              topic_set_topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
              topic_set_id INTEGER NOT NULL REFERENCES topic_sets(topic_set_id) ON DELETE CASCADE,
              topic_id INTEGER NOT NULL REFERENCES topics(topic_id) ON DELETE CASCADE,
              stakes_score REAL,
              stakes_rank INTEGER,
              is_high_stakes INTEGER NOT NULL DEFAULT 0 CHECK (is_high_stakes IN (0, 1)),
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (topic_set_id, topic_id)
            )
            """,
            "copy_columns": [
                "topic_set_id",
                "topic_id",
                "stakes_score",
                "stakes_rank",
                "is_high_stakes",
                "notes",
                "created_at",
                "updated_at",
            ],
            "index_sqls": [
                "CREATE INDEX IF NOT EXISTS idx_topic_set_topics_topic_id ON topic_set_topics(topic_id);",
            ],
        },
        {
            "table": "policy_event_axis_scores",
            "create_sql": """
            CREATE TABLE policy_event_axis_scores (
              policy_event_axis_score_id INTEGER PRIMARY KEY AUTOINCREMENT,
              policy_event_id TEXT NOT NULL REFERENCES policy_events(policy_event_id) ON DELETE CASCADE,
              policy_axis_id INTEGER NOT NULL REFERENCES policy_axes(policy_axis_id) ON DELETE CASCADE,
              direction INTEGER CHECK (direction IN (-1, 0, 1)),
              intensity REAL,
              confidence REAL,
              method TEXT NOT NULL,
              notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (policy_event_id, policy_axis_id, method)
            )
            """,
            "copy_columns": [
                "policy_event_id",
                "policy_axis_id",
                "direction",
                "intensity",
                "confidence",
                "method",
                "notes",
                "created_at",
                "updated_at",
            ],
            "index_sqls": [
                "CREATE INDEX IF NOT EXISTS idx_policy_event_axis_scores_axis_id ON policy_event_axis_scores(policy_axis_id);",
            ],
        },
        {
            "table": "intervention_events",
            "create_sql": """
            CREATE TABLE intervention_events (
              intervention_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id) ON DELETE CASCADE,
              policy_event_id TEXT NOT NULL REFERENCES policy_events(policy_event_id) ON DELETE CASCADE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (intervention_id, policy_event_id)
            )
            """,
            "copy_columns": [
                "intervention_id",
                "policy_event_id",
                "created_at",
                "updated_at",
            ],
            "index_sqls": [
                "CREATE INDEX IF NOT EXISTS idx_intervention_events_event_id ON intervention_events(policy_event_id);",
            ],
        },
        {
            "table": "sanction_norm_fragment_links",
            "create_sql": """
            CREATE TABLE sanction_norm_fragment_links (
              sanction_norm_fragment_link_id INTEGER PRIMARY KEY AUTOINCREMENT,
              norm_id TEXT NOT NULL REFERENCES sanction_norm_catalog(norm_id) ON DELETE CASCADE,
              fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
              link_reason TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (norm_id, fragment_id)
            )
            """,
            "copy_columns": [
                "norm_id",
                "fragment_id",
                "link_reason",
                "created_at",
                "updated_at",
            ],
            "index_sqls": [
                "CREATE INDEX IF NOT EXISTS idx_sanction_norm_fragment_links_fragment_id ON sanction_norm_fragment_links(fragment_id);",
            ],
        },
    ]

    for migration in migrations:
        _ensure_single_pk_table(
            conn,
            table=migration["table"],
            create_sql=migration["create_sql"].strip(),
            copy_columns=migration["copy_columns"],
            index_sqls=migration.get("index_sqls", []),
        )


def ensure_schema_compat(conn: sqlite3.Connection) -> None:
    compat_columns: dict[str, dict[str, str]] = {
        "person_identifiers": {
            "created_at": "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
        },
        "persons": {
            "gender_id": "gender_id INTEGER REFERENCES genders(gender_id)",
            "territory_id": "territory_id INTEGER REFERENCES territories(territory_id)",
        },
        "source_records": {
            "source_snapshot_date": "source_snapshot_date TEXT",
            "content_sha256": "content_sha256 TEXT",
        },
        "mandates": {
            "role_id": "role_id INTEGER REFERENCES roles(role_id)",
            "admin_level_id": "admin_level_id INTEGER REFERENCES admin_levels(admin_level_id)",
            "territory_id": "territory_id INTEGER REFERENCES territories(territory_id)",
            "source_record_pk": "source_record_pk INTEGER REFERENCES source_records(source_record_pk)",
        },
        "parl_vote_member_votes": {
            "parliamentary_group_id": "parliamentary_group_id INTEGER REFERENCES parliamentary_groups(parliamentary_group_id) ON DELETE SET NULL",
        },
        "parl_vote_events": {
            "totals_absent": "totals_absent INTEGER",
        },
        "accountability_ledger_entries": {
            "parliamentary_group_id": "parliamentary_group_id INTEGER REFERENCES parliamentary_groups(parliamentary_group_id) ON DELETE SET NULL",
        },
        "indicator_observation_records": {
            "indicator_series_id": "indicator_series_id INTEGER REFERENCES indicator_series(indicator_series_id) ON DELETE SET NULL",
        },
        "indicator_series": {
            "dimensions_json": "dimensions_json TEXT",
        },
        "infoelectoral_elected_officials": {
            "person_id": "person_id INTEGER REFERENCES persons(person_id)",
            "mandate_id": "mandate_id INTEGER REFERENCES mandates(mandate_id)",
            "party_id": "party_id INTEGER REFERENCES parties(party_id)",
            "institution_id": (
                "institution_id INTEGER REFERENCES institutions(institution_id)"
            ),
            "role_id": "role_id INTEGER REFERENCES roles(role_id)",
            "territory_id": (
                "territory_id INTEGER REFERENCES territories(territory_id)"
            ),
            "first_seen_snapshot_date": (
                "first_seen_snapshot_date TEXT NOT NULL DEFAULT ''"
            ),
            "last_seen_snapshot_date": (
                "last_seen_snapshot_date TEXT NOT NULL DEFAULT ''"
            ),
            "is_present": (
                "is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1))"
            ),
        },
        "infoelectoral_candidate_occurrences": {
            "birth_date": "birth_date TEXT",
            "birth_date_source": "birth_date_source TEXT",
            "dni": "dni TEXT",
        },
        "money_contract_records": {
            "amount_eur_decimal": "amount_eur_decimal TEXT",
            "amount_semantics": "amount_semantics TEXT",
            "stable_contract_id": "stable_contract_id TEXT",
            "entry_updated_at": "entry_updated_at TEXT",
            "contract_status_code": "contract_status_code TEXT",
            "authority_identifier": "authority_identifier TEXT",
        },
        "money_contract_documents": {
            "document_source_record_pk": (
                "document_source_record_pk INTEGER "
                "REFERENCES source_records(source_record_pk)"
            ),
        },
        "money_bulk_page_fetches": {
            "money_bulk_partition_id": (
                "money_bulk_partition_id INTEGER "
                "REFERENCES money_bulk_partitions(money_bulk_partition_id) "
                "ON DELETE SET NULL"
            ),
            "source_page_number": "source_page_number INTEGER",
        },
        "placsp_bulk_runs": {
            "archive_contract_sha256": "archive_contract_sha256 TEXT",
        },
        "institutions": {
            "admin_level_id": "admin_level_id INTEGER REFERENCES admin_levels(admin_level_id)",
            "territory_id": "territory_id INTEGER REFERENCES territories(territory_id)",
        },
        "parties": {
            "acronym": "acronym TEXT",
        },
        "party_aliases": {
            "created_at": "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
            "updated_at": "updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
        },
        "person_name_aliases": {
            "source_kind": "source_kind TEXT NOT NULL DEFAULT 'manual_seed'",
            "source_record_pk": "source_record_pk INTEGER REFERENCES source_records(source_record_pk)",
            "evidence_date": "evidence_date TEXT",
            "evidence_quote": "evidence_quote TEXT",
        },
        "liberty_indirect_responsibility_edges": {
            "actor_person_name": "actor_person_name TEXT",
            "actor_role_title": "actor_role_title TEXT",
            "appointment_start_date": "appointment_start_date TEXT",
            "appointment_end_date": "appointment_end_date TEXT",
        },
        "sanction_procedural_metrics": {
            "evidence_date": "evidence_date TEXT",
            "evidence_quote": "evidence_quote TEXT",
        },
        "parl_initiative_doc_extractions": {
            "text_extraction_method": "text_extraction_method TEXT",
            "text_quality": "text_quality TEXT",
            "needs_ocr": "needs_ocr INTEGER NOT NULL DEFAULT 0 CHECK (needs_ocr IN (0, 1))",
            "full_text_chars": "full_text_chars INTEGER",
            "full_text_path": "full_text_path TEXT",
        },
        "text_documents": {
            "text_path": "text_path TEXT",
            "text_sha256": "text_sha256 TEXT",
            "text_extraction_method": "text_extraction_method TEXT",
            "text_extracted_at": "text_extracted_at TEXT",
            "text_truncated": "text_truncated INTEGER NOT NULL DEFAULT 0 CHECK (text_truncated IN (0, 1))",
        },
        "integrity_signal_reviews": {
            "reviewer_independence_class": (
                "reviewer_independence_class TEXT NOT NULL DEFAULT 'unknown' "
                "CHECK (reviewer_independence_class IN "
                "('author','maintainer','independent','unknown'))"
            ),
        },
    }

    for table, columns in compat_columns.items():
        for column, definition_sql in columns.items():
            ensure_column(conn, table, column, definition_sql)

    if table_exists(conn, "infoelectoral_elected_officials"):
        conn.execute(
            """
            UPDATE infoelectoral_elected_officials
            SET first_seen_snapshot_date = COALESCE(
                  NULLIF(first_seen_snapshot_date, ''),
                  (SELECT source_snapshot_date FROM source_records
                   WHERE source_records.source_record_pk =
                         infoelectoral_elected_officials.source_record_pk),
                  ''
                ),
                last_seen_snapshot_date = COALESCE(
                  NULLIF(last_seen_snapshot_date, ''),
                  (SELECT source_snapshot_date FROM source_records
                   WHERE source_records.source_record_pk =
                         infoelectoral_elected_officials.source_record_pk),
                  ''
                )
            WHERE first_seen_snapshot_date = '' OR last_seen_snapshot_date = ''
            """
        )

    ensure_indicator_observations_allow_ree(conn)
    ensure_text_documents_allow_duplicate_urls(conn)
    ensure_surrogate_pk_compat(conn)
    conn.commit()


def backfill_run_fetches(conn: sqlite3.Connection) -> None:
    """Populate per-run fetch metadata from legacy raw_fetches rows (best-effort).

    raw_fetches is de-duped by (source_id, content_sha256), so it may not contain a row for every run_id.
    This backfill only covers run_ids present in raw_fetches; current pipelines also write run_fetches
    directly for new runs.
    """
    if not table_exists(conn, "run_fetches") or not table_exists(conn, "raw_fetches"):
        return
    try:
        conn.execute(
            """
            INSERT INTO run_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            )
            SELECT
              rf.run_id, rf.source_id, rf.source_url, rf.fetched_at, rf.raw_path, rf.content_sha256, rf.content_type, rf.bytes
            FROM raw_fetches rf
            WHERE rf.run_id IS NOT NULL
            ON CONFLICT(run_id) DO NOTHING
            """
        )
    except sqlite3.Error:
        # Keep apply_schema resilient for old DBs or partial schemas.
        return


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    for _ in range(2):
        try:
            conn.executescript(sql)
            break
        except sqlite3.OperationalError as exc:
            if "no such column" not in str(exc).lower():
                raise
            ensure_schema_compat(conn)
    else:
        conn.executescript(sql)

    ensure_schema_compat(conn)
    backfill_run_fetches(conn)
    conn.commit()


def seed_sources(conn: sqlite3.Connection) -> None:
    seed_sources_from_config(conn, SOURCE_CONFIG)


def seed_dimensions(conn: sqlite3.Connection) -> None:
    ts = now_utc_iso()
    for code, label in (
        ("nacional", "Nacional"),
        ("europeo", "Europeo"),
        ("municipal", "Municipal"),
        ("autonomico", "Autonomico"),
    ):
        conn.execute(
            """
            INSERT INTO admin_levels (code, label, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
            """,
            (code, label, ts, ts),
        )

    for code, label in (("m", "Masculino"), ("f", "Femenino"), ("u", "Desconocido")):
        conn.execute(
            """
            INSERT INTO genders (code, label, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
            """,
            (code, label, ts, ts),
        )
    conn.commit()


def upsert_domain(
    conn: sqlite3.Connection,
    *,
    canonical_key_value: str,
    label: str,
    description: str | None,
    tier: int | None,
    now_iso: str,
) -> int:
    key = normalize_ws(canonical_key_value)
    if not key:
        raise ValueError("canonical_key_value is required")

    row = conn.execute(
        """
        INSERT INTO domains (canonical_key, label, description, tier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
          label=excluded.label,
          description=excluded.description,
          tier=excluded.tier,
          updated_at=excluded.updated_at
        RETURNING domain_id
        """,
        (
            key,
            normalize_ws(label) or key,
            description,
            tier,
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver domain_id")
    return int(row["domain_id"])


def upsert_policy_axis(
    conn: sqlite3.Connection,
    *,
    domain_id: int,
    canonical_key_value: str,
    label: str,
    description: str | None,
    axis_order: int | None,
    now_iso: str,
) -> int:
    key = normalize_ws(canonical_key_value)
    if not key:
        raise ValueError("canonical_key_value is required")
    axis_label = normalize_ws(label) or key

    row = conn.execute(
        """
        INSERT INTO policy_axes (domain_id, canonical_key, label, description, axis_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain_id, canonical_key) DO UPDATE SET
          label=excluded.label,
          description=excluded.description,
          axis_order=excluded.axis_order,
          updated_at=excluded.updated_at
        RETURNING policy_axis_id
        """,
        (
            domain_id,
            key,
            axis_label,
            description,
            axis_order,
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver policy_axis_id")
    return int(row["policy_axis_id"])


def upsert_admin_level(conn: sqlite3.Connection, code: str, now_iso: str) -> int | None:
    code_norm = normalize_key_part(code or "")
    if not code_norm:
        return None
    label = code_norm.capitalize()
    row = conn.execute(
        """
        INSERT INTO admin_levels (code, label, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          label=excluded.label,
          updated_at=excluded.updated_at
        RETURNING admin_level_id
        """,
        (code_norm, label, now_iso, now_iso),
    ).fetchone()
    return int(row["admin_level_id"]) if row else None


def upsert_role(conn: sqlite3.Connection, title: str, now_iso: str) -> int | None:
    title_norm = normalize_ws(title or "")
    if not title_norm:
        return None
    ckey = normalize_key_part(title_norm)
    row = conn.execute(
        """
        INSERT INTO roles (title, canonical_key, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
          title=excluded.title,
          updated_at=excluded.updated_at
        RETURNING role_id
        """,
        (title_norm, ckey, now_iso, now_iso),
    ).fetchone()
    return int(row["role_id"]) if row else None


def normalize_territory_code(raw: str | None) -> tuple[str, str | None]:
    if not raw:
        return "", None
    name = normalize_ws(str(raw))
    if not name:
        return "", None
    if name.upper() == "ES":
        return "ES", "ES"
    if name.isdigit():
        return name, name
    return normalize_key_part(name), name


def upsert_territory(
    conn: sqlite3.Connection, raw_code: str | None, now_iso: str
) -> int | None:
    code, name = normalize_territory_code(raw_code)
    if not code:
        return None
    row = conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=COALESCE(excluded.name, territories.name),
          updated_at=excluded.updated_at
        RETURNING territory_id
        """,
        (code, name, now_iso, now_iso),
    ).fetchone()
    return int(row["territory_id"]) if row else None


def upsert_party_alias(
    conn: sqlite3.Connection, party_id: int, alias: str, now_iso: str
) -> None:
    alias_norm = normalize_ws(alias)
    if not alias_norm:
        return
    canonical_alias = normalize_key_part(alias_norm)
    conn.execute(
        """
        INSERT INTO party_aliases (party_id, alias, canonical_alias, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(canonical_alias) DO UPDATE SET
          party_id=excluded.party_id,
          alias=excluded.alias,
          updated_at=excluded.updated_at
        """,
        (party_id, alias_norm, canonical_alias, now_iso, now_iso),
    )


def upsert_source_record(
    conn: sqlite3.Connection,
    source_id: str,
    source_record_id: str,
    snapshot_date: str | None,
    raw_payload: str,
    content_sha256: str,
    now_iso: str,
) -> int:
    return _upsert_source_record(
        conn,
        source_id,
        source_record_id,
        snapshot_date,
        raw_payload,
        content_sha256,
        now_iso,
    )


def upsert_party(
    conn: sqlite3.Connection, party_name: str | None, now_iso: str
) -> int | None:
    if not party_name:
        return None
    party_name = normalize_ws(party_name)
    if not party_name:
        return None
    row = conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        VALUES (?, NULL, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          updated_at=excluded.updated_at
        RETURNING party_id
        """,
        (party_name, now_iso, now_iso),
    ).fetchone()
    party_id = int(row["party_id"]) if row else None
    if party_id is not None:
        upsert_party_alias(conn, party_id, party_name, now_iso)
    return party_id


def upsert_institution(
    conn: sqlite3.Connection,
    institution_name: str,
    level: str,
    territory_code: str,
    admin_level_id: int | None,
    territory_id: int | None,
    now_iso: str,
) -> int:
    row = conn.execute(
        """
        INSERT INTO institutions (
          name, level, admin_level_id, territory_code, territory_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET
          admin_level_id=COALESCE(excluded.admin_level_id, institutions.admin_level_id),
          territory_id=COALESCE(excluded.territory_id, institutions.territory_id),
          updated_at=excluded.updated_at
        RETURNING institution_id
        """,
        (
            institution_name,
            level,
            admin_level_id,
            territory_code,
            territory_id,
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver institution_id")
    return int(row["institution_id"])


def normalize_gender_code(raw_gender: str | None) -> str:
    key = normalize_key_part(raw_gender or "")
    if key in {"m", "masculino", "male", "hombre", "man"}:
        return "m"
    if key in {"f", "femenino", "female", "mujer", "woman"}:
        return "f"
    return "u"


def upsert_gender(
    conn: sqlite3.Connection, raw_gender: str | None, now_iso: str
) -> int | None:
    if raw_gender is None:
        return None
    code = normalize_gender_code(raw_gender)
    labels = {"m": "Masculino", "f": "Femenino", "u": "Desconocido"}
    row = conn.execute(
        """
        INSERT INTO genders (code, label, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
        RETURNING gender_id
        """,
        (code, labels.get(code, "Desconocido"), now_iso, now_iso),
    ).fetchone()
    return int(row["gender_id"]) if row else None


def upsert_person(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    territory_id: int | None,
    gender_id: int | None,
    now_iso: str,
) -> int:
    ckey = canonical_key(
        row["full_name"], row.get("birth_date"), row.get("territory_code")
    )
    result = conn.execute(
        """
        INSERT INTO persons (
          full_name, given_name, family_name, gender, gender_id, birth_date, territory_code,
          territory_id, canonical_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
          full_name=excluded.full_name,
          given_name=COALESCE(excluded.given_name, persons.given_name),
          family_name=COALESCE(excluded.family_name, persons.family_name),
          gender=COALESCE(excluded.gender, persons.gender),
          gender_id=COALESCE(excluded.gender_id, persons.gender_id),
          birth_date=COALESCE(excluded.birth_date, persons.birth_date),
          territory_code=CASE
            WHEN excluded.territory_code != '' THEN excluded.territory_code
            ELSE persons.territory_code
          END,
          territory_id=COALESCE(excluded.territory_id, persons.territory_id),
          updated_at=excluded.updated_at
        RETURNING person_id
        """,
        (
            row["full_name"],
            row.get("given_name"),
            row.get("family_name"),
            normalize_ws(str(row.get("gender") or "")) or None,
            gender_id,
            row.get("birth_date"),
            row.get("territory_code") or "",
            territory_id,
            ckey,
            now_iso,
            now_iso,
        ),
    ).fetchone()
    if result is None:
        raise RuntimeError("No se pudo resolver person_id")
    return int(result["person_id"])


def upsert_person_identifier(
    conn: sqlite3.Connection,
    person_id: int,
    source_id: str,
    source_record_id: str,
    now_iso: str,
) -> None:
    namespace = f"{source_id}:source_record_id"
    conn.execute(
        """
        INSERT INTO person_identifiers (person_id, namespace, value, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(namespace, value) DO UPDATE SET
          person_id=excluded.person_id
        """,
        (person_id, namespace, source_record_id, now_iso),
    )


def upsert_mandate(
    conn: sqlite3.Connection,
    source_id: str,
    row: dict[str, Any],
    person_id: int,
    institution_id: int,
    party_id: int | None,
    role_id: int | None,
    admin_level_id: int | None,
    territory_id: int | None,
    source_record_pk: int | None,
    now_iso: str,
) -> None:
    is_active = 1 if row.get("is_active", True) else 0
    conn.execute(
        """
        INSERT INTO mandates (
          person_id, institution_id, party_id, role_title, role_id, level, admin_level_id, territory_code,
          territory_id,
          start_date, end_date, is_active, source_id, source_record_id,
          source_record_pk, source_snapshot_date, first_seen_at, last_seen_at, raw_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          person_id=excluded.person_id,
          institution_id=excluded.institution_id,
          party_id=excluded.party_id,
          role_title=excluded.role_title,
          role_id=COALESCE(excluded.role_id, mandates.role_id),
          level=excluded.level,
          admin_level_id=COALESCE(excluded.admin_level_id, mandates.admin_level_id),
          territory_code=excluded.territory_code,
          territory_id=COALESCE(excluded.territory_id, mandates.territory_id),
          start_date=COALESCE(excluded.start_date, mandates.start_date),
          end_date=excluded.end_date,
          is_active=excluded.is_active,
          source_record_pk=COALESCE(excluded.source_record_pk, mandates.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, mandates.source_snapshot_date),
          last_seen_at=excluded.last_seen_at,
          raw_payload=excluded.raw_payload
        """,
        (
            person_id,
            institution_id,
            party_id,
            row["role_title"],
            role_id,
            row["level"],
            admin_level_id,
            row.get("territory_code") or "",
            territory_id,
            row.get("start_date"),
            row.get("end_date"),
            is_active,
            source_id,
            row["source_record_id"],
            source_record_pk,
            row.get("source_snapshot_date"),
            now_iso,
            now_iso,
            row["raw_payload"],
        ),
    )


def close_missing_mandates(
    conn: sqlite3.Connection,
    source_id: str,
    seen_ids: list[str],
    snapshot_date: str | None,
    now_iso: str,
) -> None:
    if not seen_ids:
        conn.execute(
            """
            UPDATE mandates
            SET is_active = 0,
                end_date = COALESCE(end_date, ?),
                last_seen_at = ?
            WHERE source_id = ? AND is_active = 1
            """,
            (snapshot_date, now_iso, source_id),
        )
        return

    # Do not build a NOT IN (?, ... x N) statement. SQLite variable limits make
    # that fail far below million-row sources. A connection-local indexed temp
    # table keeps SQL size and peak parameter memory bounded.
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ingest_seen_mandate_ids (
          source_record_id TEXT PRIMARY KEY
        ) WITHOUT ROWID
        """
    )
    conn.execute("DELETE FROM ingest_seen_mandate_ids")
    conn.executemany(
        "INSERT OR IGNORE INTO ingest_seen_mandate_ids (source_record_id) VALUES (?)",
        ((str(source_record_id),) for source_record_id in seen_ids),
    )
    conn.execute(
        """
        UPDATE mandates
        SET is_active = 0,
            end_date = COALESCE(end_date, ?),
            last_seen_at = ?
        WHERE source_id = ?
          AND is_active = 1
          AND NOT EXISTS (
            SELECT 1
            FROM ingest_seen_mandate_ids seen
            WHERE seen.source_record_id = mandates.source_record_id
          )
        """,
        (snapshot_date, now_iso, source_id),
    )
    conn.execute("DELETE FROM ingest_seen_mandate_ids")


def start_run(conn: sqlite3.Connection, source_id: str, source_url: str) -> int:
    started_at = now_utc_iso()
    cur = conn.execute(
        """
        INSERT INTO ingestion_runs (
          source_id, started_at, status, source_url
        ) VALUES (?, ?, 'running', ?)
        """,
        (source_id, started_at, source_url),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    message: str,
    records_seen: int,
    records_loaded: int,
    fetched_at: str | None = None,
    raw_path: Path | None = None,
) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET finished_at = ?,
            status = ?,
            message = ?,
            records_seen = ?,
            records_loaded = ?,
            fetched_at = COALESCE(?, fetched_at),
            raw_path = COALESCE(?, raw_path)
        WHERE run_id = ?
        """,
        (
            now_utc_iso(),
            status,
            message,
            records_seen,
            records_loaded,
            fetched_at,
            str(raw_path) if raw_path else None,
            run_id,
        ),
    )
    conn.commit()


def backfill_normalized_dimensions(conn: sqlite3.Connection) -> None:
    # Keep behavior identical to legacy script; imported lazily to avoid circular imports.
    from .util import normalize_key_part as _normalize_key_part  # noqa: PLC0415

    now_iso = now_utc_iso()
    for row in conn.execute(
        """
        SELECT DISTINCT level
        FROM mandates
        WHERE level IS NOT NULL AND TRIM(level) != ''
        """
    ):
        upsert_admin_level(conn, str(row["level"]), now_iso)

    for row in conn.execute(
        """
        SELECT DISTINCT role_title
        FROM mandates
        WHERE role_title IS NOT NULL AND TRIM(role_title) != ''
        """
    ):
        upsert_role(conn, str(row["role_title"]), now_iso)

    for row in conn.execute(
        """
        SELECT territory_code AS code FROM persons
        UNION
        SELECT territory_code AS code FROM institutions
        UNION
        SELECT territory_code AS code FROM mandates
        """
    ):
        upsert_territory(conn, str(row["code"] or ""), now_iso)

    for row in conn.execute(
        """
        SELECT DISTINCT gender
        FROM persons
        WHERE gender IS NOT NULL AND TRIM(gender) != ''
        """
    ):
        upsert_gender(conn, str(row["gender"]), now_iso)

    conn.execute(
        """
        INSERT OR IGNORE INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
        )
        SELECT
          m.source_id,
          m.source_record_id,
          m.source_snapshot_date,
          m.raw_payload,
          lower(hex(randomblob(16))),
          m.first_seen_at,
          m.last_seen_at
        FROM mandates m
        """
    )

    conn.execute(
        """
        UPDATE persons
        SET territory_id = (
              SELECT t.territory_id
              FROM territories t
              WHERE t.code = CASE
                WHEN TRIM(persons.territory_code) = '' THEN ''
                WHEN UPPER(TRIM(persons.territory_code)) = 'ES' THEN 'ES'
                WHEN TRIM(persons.territory_code) GLOB '[0-9]*' THEN TRIM(persons.territory_code)
                ELSE lower(TRIM(persons.territory_code))
              END
            ),
            gender_id = (
              SELECT g.gender_id
              FROM genders g
              WHERE g.code = CASE
                WHEN lower(TRIM(COALESCE(persons.gender, ''))) IN ('m', 'masculino', 'male', 'hombre', 'man') THEN 'm'
                WHEN lower(TRIM(COALESCE(persons.gender, ''))) IN ('f', 'femenino', 'female', 'mujer', 'woman') THEN 'f'
                ELSE 'u'
              END
            )
        WHERE territory_id IS NULL OR (gender IS NOT NULL AND gender_id IS NULL)
        """
    )

    conn.execute(
        """
        UPDATE institutions
        SET admin_level_id = (
              SELECT a.admin_level_id
              FROM admin_levels a
              WHERE a.code = lower(TRIM(institutions.level))
            ),
            territory_id = (
              SELECT t.territory_id
              FROM territories t
              WHERE t.code = CASE
                WHEN TRIM(institutions.territory_code) = '' THEN ''
                WHEN UPPER(TRIM(institutions.territory_code)) = 'ES' THEN 'ES'
                WHEN TRIM(institutions.territory_code) GLOB '[0-9]*' THEN TRIM(institutions.territory_code)
                ELSE lower(TRIM(institutions.territory_code))
              END
            )
        WHERE admin_level_id IS NULL OR territory_id IS NULL
        """
    )

    conn.execute(
        """
        UPDATE mandates
        SET role_id = (
              SELECT r.role_id
              FROM roles r
              WHERE r.canonical_key = lower(TRIM(mandates.role_title))
            ),
            admin_level_id = (
              SELECT a.admin_level_id
              FROM admin_levels a
              WHERE a.code = lower(TRIM(mandates.level))
            ),
            territory_id = (
              SELECT t.territory_id
              FROM territories t
              WHERE t.code = CASE
                WHEN TRIM(mandates.territory_code) = '' THEN ''
                WHEN UPPER(TRIM(mandates.territory_code)) = 'ES' THEN 'ES'
                WHEN TRIM(mandates.territory_code) GLOB '[0-9]*' THEN TRIM(mandates.territory_code)
                ELSE lower(TRIM(mandates.territory_code))
              END
            ),
            source_record_pk = (
              SELECT sr.source_record_pk
              FROM source_records sr
              WHERE sr.source_id = mandates.source_id
                AND sr.source_record_id = mandates.source_record_id
            )
        WHERE role_id IS NULL OR admin_level_id IS NULL OR territory_id IS NULL OR source_record_pk IS NULL
        """
    )

    missing_roles = conn.execute(
        """
        SELECT mandate_id, role_title
        FROM mandates
        WHERE role_id IS NULL
          AND role_title IS NOT NULL
          AND TRIM(role_title) != ''
        """
    ).fetchall()
    for row in missing_roles:
        role_id = upsert_role(conn, str(row["role_title"]), now_iso)
        if role_id is None:
            continue
        conn.execute(
            "UPDATE mandates SET role_id = ? WHERE mandate_id = ?",
            (role_id, row["mandate_id"]),
        )

    conn.execute(
        """
        INSERT OR IGNORE INTO party_aliases (party_id, alias, canonical_alias, created_at, updated_at)
        SELECT
          p.party_id,
          p.name,
          lower(TRIM(p.name)),
          p.created_at,
          p.updated_at
        FROM parties p
        """
    )
    conn.commit()
