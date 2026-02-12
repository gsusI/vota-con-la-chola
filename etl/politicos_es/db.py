from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import SOURCE_CONFIG
from .util import canonical_key, normalize_key_part, normalize_ws, now_utc_iso


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(r["name"]) for r in rows}


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition_sql: str) -> None:
    cols = table_columns(conn, table)
    if column in cols:
        return
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition_sql}')


def ensure_schema_compat(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "persons", "gender_id", "gender_id INTEGER REFERENCES genders(gender_id)")
    ensure_column(conn, "persons", "territory_id", "territory_id INTEGER REFERENCES territories(territory_id)")

    ensure_column(
        conn,
        "institutions",
        "admin_level_id",
        "admin_level_id INTEGER REFERENCES admin_levels(admin_level_id)",
    )
    ensure_column(conn, "institutions", "territory_id", "territory_id INTEGER REFERENCES territories(territory_id)")

    ensure_column(conn, "mandates", "role_id", "role_id INTEGER REFERENCES roles(role_id)")
    ensure_column(
        conn,
        "mandates",
        "admin_level_id",
        "admin_level_id INTEGER REFERENCES admin_levels(admin_level_id)",
    )
    ensure_column(conn, "mandates", "territory_id", "territory_id INTEGER REFERENCES territories(territory_id)")
    ensure_column(
        conn,
        "mandates",
        "source_record_pk",
        "source_record_pk INTEGER REFERENCES source_records(source_record_pk)",
    )


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    try:
        conn.executescript(sql)
    except sqlite3.OperationalError as exc:
        if "no such column" not in str(exc).lower():
            raise
        ensure_schema_compat(conn)
        conn.executescript(sql)
    ensure_schema_compat(conn)
    conn.commit()


def seed_sources(conn: sqlite3.Connection) -> None:
    ts = now_utc_iso()
    for source_id, cfg in SOURCE_CONFIG.items():
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
              name=excluded.name,
              scope=excluded.scope,
              default_url=excluded.default_url,
              data_format=excluded.data_format,
              is_active=1,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                cfg["name"],
                cfg["scope"],
                cfg["default_url"],
                cfg["format"],
                ts,
                ts,
            ),
        )
    conn.commit()


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


def upsert_admin_level(conn: sqlite3.Connection, code: str, now_iso: str) -> int | None:
    code_norm = normalize_key_part(code or "")
    if not code_norm:
        return None
    label = code_norm.capitalize()
    conn.execute(
        """
        INSERT INTO admin_levels (code, label, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          label=excluded.label,
          updated_at=excluded.updated_at
        """,
        (code_norm, label, now_iso, now_iso),
    )
    row = conn.execute("SELECT admin_level_id FROM admin_levels WHERE code = ?", (code_norm,)).fetchone()
    return int(row["admin_level_id"]) if row else None


def upsert_role(conn: sqlite3.Connection, title: str, now_iso: str) -> int | None:
    title_norm = normalize_ws(title or "")
    if not title_norm:
        return None
    ckey = normalize_key_part(title_norm)
    conn.execute(
        """
        INSERT INTO roles (title, canonical_key, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(canonical_key) DO UPDATE SET
          title=excluded.title,
          updated_at=excluded.updated_at
        """,
        (title_norm, ckey, now_iso, now_iso),
    )
    row = conn.execute("SELECT role_id FROM roles WHERE canonical_key = ?", (ckey,)).fetchone()
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


def upsert_territory(conn: sqlite3.Connection, raw_code: str | None, now_iso: str) -> int | None:
    code, name = normalize_territory_code(raw_code)
    if not code:
        return None
    conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=COALESCE(excluded.name, territories.name),
          updated_at=excluded.updated_at
        """,
        (code, name, now_iso, now_iso),
    )
    row = conn.execute("SELECT territory_id FROM territories WHERE code = ?", (code,)).fetchone()
    return int(row["territory_id"]) if row else None


def upsert_party_alias(conn: sqlite3.Connection, party_id: int, alias: str, now_iso: str) -> None:
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
    conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, source_records.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        """,
        (source_id, source_record_id, snapshot_date, raw_payload, content_sha256, now_iso, now_iso),
    )
    row = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (source_id, source_record_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("No se pudo resolver source_record_pk")
    return int(row["source_record_pk"])


def upsert_party(conn: sqlite3.Connection, party_name: str | None, now_iso: str) -> int | None:
    if not party_name:
        return None
    party_name = normalize_ws(party_name)
    if not party_name:
        return None
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        VALUES (?, NULL, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          updated_at=excluded.updated_at
        """,
        (party_name, now_iso, now_iso),
    )
    row = conn.execute("SELECT party_id FROM parties WHERE name = ?", (party_name,)).fetchone()
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
    conn.execute(
        """
        INSERT INTO institutions (
          name, level, admin_level_id, territory_code, territory_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET
          admin_level_id=COALESCE(excluded.admin_level_id, institutions.admin_level_id),
          territory_id=COALESCE(excluded.territory_id, institutions.territory_id),
          updated_at=excluded.updated_at
        """,
        (institution_name, level, admin_level_id, territory_code, territory_id, now_iso, now_iso),
    )
    row = conn.execute(
        """
        SELECT institution_id
        FROM institutions
        WHERE name = ? AND level = ? AND territory_code = ?
        """,
        (institution_name, level, territory_code),
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


def upsert_gender(conn: sqlite3.Connection, raw_gender: str | None, now_iso: str) -> int | None:
    if raw_gender is None:
        return None
    code = normalize_gender_code(raw_gender)
    labels = {"m": "Masculino", "f": "Femenino", "u": "Desconocido"}
    conn.execute(
        """
        INSERT INTO genders (code, label, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (code, labels.get(code, "Desconocido"), now_iso, now_iso),
    )
    row = conn.execute("SELECT gender_id FROM genders WHERE code = ?", (code,)).fetchone()
    return int(row["gender_id"]) if row else None


def upsert_person(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    territory_id: int | None,
    gender_id: int | None,
    now_iso: str,
) -> int:
    ckey = canonical_key(row["full_name"], row.get("birth_date"), row.get("territory_code"))
    conn.execute(
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
    )
    result = conn.execute(
        "SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)
    ).fetchone()
    if result is None:
        raise RuntimeError("No se pudo resolver person_id")
    return int(result["person_id"])


def upsert_person_identifier(
    conn: sqlite3.Connection, person_id: int, source_id: str, source_record_id: str, now_iso: str
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
    conn: sqlite3.Connection, source_id: str, seen_ids: list[str], snapshot_date: str | None, now_iso: str
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

    placeholders = ",".join("?" for _ in seen_ids)
    params: list[Any] = [snapshot_date, now_iso, source_id, *seen_ids]
    conn.execute(
        f"""
        UPDATE mandates
        SET is_active = 0,
            end_date = COALESCE(end_date, ?),
            last_seen_at = ?
        WHERE source_id = ?
          AND is_active = 1
          AND source_record_id NOT IN ({placeholders})
        """,
        tuple(params),
    )


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

