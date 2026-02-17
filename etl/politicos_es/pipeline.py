from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import SOURCE_CONFIG
from .connectors.base import BaseConnector
from .db import (
    close_missing_mandates,
    finish_run,
    start_run,
    upsert_admin_level,
    upsert_gender,
    upsert_institution,
    upsert_party,
    upsert_person,
    upsert_person_identifier,
    upsert_role,
    upsert_source_record,
    upsert_territory,
    upsert_mandate,
    normalize_gender_code,
    normalize_territory_code,
)
from .util import canonical_key, normalize_key_part, normalize_ws, now_utc_iso, sha256_bytes


def ingest_one_source(
    conn: sqlite3.Connection,
    connector: BaseConnector,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    url_override: str | None,
    snapshot_date: str | None,
    strict_network: bool,
) -> tuple[int, int, str]:
    source_id = connector.source_id
    ingest_mode = getattr(connector, "ingest_mode", "mandates")
    if ingest_mode not in {"mandates", "source_records_only"}:
        raise RuntimeError(f"ingest_mode no soportado para {source_id}: {ingest_mode}")
    resolved_url = f"file://{from_file.resolve()}" if from_file else connector.resolve_url(url_override, timeout)
    run_id = start_run(conn, source_id, resolved_url)
    try:
        extracted = connector.extract(
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=from_file,
            url_override=url_override,
            strict_network=strict_network,
        )

        now_iso = now_utc_iso()

        # Keep per-run fetch metadata (used by ops dashboards).
        conn.execute(
            """
            INSERT INTO run_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              fetched_at=excluded.fetched_at,
              raw_path=excluded.raw_path,
              content_sha256=excluded.content_sha256,
              content_type=excluded.content_type,
              bytes=excluded.bytes
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )

        conn.execute(
            """
            INSERT INTO raw_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, content_sha256) DO NOTHING
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )

        seen_ids: list[str] = []
        loaded = 0
        records_seen = 0
        admin_level_cache: dict[str, int | None] = {}
        role_cache: dict[str, int | None] = {}
        territory_cache: dict[str, int | None] = {}
        gender_cache: dict[str, int | None] = {}
        party_cache: dict[str, int | None] = {}
        institution_cache: dict[tuple[str, str, str], int] = {}
        person_cache: dict[str, int] = {}
        source_record_cache: dict[str, int] = {}

        def cached_admin_level(level: str | None) -> int | None:
            key = normalize_key_part(level or "")
            if not key:
                return None
            if key in admin_level_cache:
                return admin_level_cache[key]
            value = upsert_admin_level(conn, level or "", now_iso)
            admin_level_cache[key] = value
            return value

        def cached_role(role_title: str | None) -> int | None:
            key = normalize_key_part(role_title or "")
            if not key:
                return None
            if key in role_cache:
                return role_cache[key]
            value = upsert_role(conn, role_title or "", now_iso)
            role_cache[key] = value
            return value

        def cached_territory(raw_code: str | None) -> int | None:
            code, _ = normalize_territory_code(raw_code)
            if not code:
                return None
            if code in territory_cache:
                return territory_cache[code]
            value = upsert_territory(conn, raw_code, now_iso)
            territory_cache[code] = value
            return value

        def cached_gender(raw_gender: str | None) -> int | None:
            if raw_gender is None:
                return None
            code = normalize_gender_code(raw_gender)
            if code in gender_cache:
                return gender_cache[code]
            value = upsert_gender(conn, raw_gender, now_iso)
            gender_cache[code] = value
            return value

        def cached_party(party_name: str | None) -> int | None:
            if not party_name:
                return None
            key = normalize_ws(party_name)
            if not key:
                return None
            if key in party_cache:
                return party_cache[key]
            value = upsert_party(conn, key, now_iso)
            party_cache[key] = value
            return value

        def cached_institution(
            institution_name: str,
            level: str,
            territory_code: str,
            admin_level_id: int | None,
            territory_id: int | None,
        ) -> int:
            key = (normalize_ws(institution_name), normalize_key_part(level), normalize_ws(territory_code))
            if key in institution_cache:
                return institution_cache[key]
            value = upsert_institution(
                conn=conn,
                institution_name=institution_name,
                level=level,
                territory_code=territory_code,
                admin_level_id=admin_level_id,
                territory_id=territory_id,
                now_iso=now_iso,
            )
            institution_cache[key] = value
            return value

        def cached_person(
            normalized: dict[str, Any],
            territory_id: int | None,
            gender_id: int | None,
        ) -> int:
            ckey = canonical_key(
                normalized["full_name"],
                normalized.get("birth_date"),
                normalized.get("territory_code"),
            )
            if ckey in person_cache:
                return person_cache[ckey]
            value = upsert_person(
                conn=conn,
                row=normalized,
                territory_id=territory_id,
                gender_id=gender_id,
                now_iso=now_iso,
            )
            person_cache[ckey] = value
            return value

        def cached_source_record(normalized: dict[str, Any]) -> int:
            key = str(normalized["source_record_id"])
            if key in source_record_cache:
                return source_record_cache[key]
            raw_payload = normalized["raw_payload"]
            value = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=key,
                snapshot_date=normalized.get("source_snapshot_date"),
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            source_record_cache[key] = value
            return value

        def assert_foreign_key_integrity() -> None:
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if not violations:
                return
            sample = ", ".join(
                f"{row['table']}.{row['rowid']} -> {row['parent']}[{row['fkid']}]"
                for row in violations[:10]
            )
            extra = f", ... (+{len(violations)-10} more)" if len(violations) > 10 else ""
            raise RuntimeError(
                f"foreign key check fallado en {source_id}: {len(violations)} violaciones "
                f"(ej: {sample}{extra})"
            )

        for record in extracted.records:
            records_seen += 1
            normalized = connector.normalize(record, snapshot_date)
            if normalized is None:
                continue

            if ingest_mode == "source_records_only":
                # Traceability-only ingest path: persist canonical source records without person/mandate writes.
                # This is used for non-representative sources that are mapped later (for example policy_events).
                _ = cached_source_record(normalized)
                seen_ids.append(normalized["source_record_id"])
                loaded += 1
                continue

            source_record_pk = cached_source_record(normalized)
            role_id = cached_role(normalized["role_title"])
            admin_level_id = cached_admin_level(normalized["level"])
            person_territory_id = cached_territory(normalized.get("territory_code"))
            institution_territory_id = cached_territory(normalized.get("institution_territory_code"))
            gender_id = cached_gender(normalized.get("gender"))
            party_id = cached_party(normalized.get("party_name"))
            institution_id = cached_institution(
                institution_name=normalized["institution_name"],
                level=normalized["level"],
                territory_code=normalized.get("institution_territory_code", ""),
                admin_level_id=admin_level_id,
                territory_id=institution_territory_id,
            )
            person_id = cached_person(
                normalized=normalized,
                territory_id=person_territory_id,
                gender_id=gender_id,
            )
            upsert_person_identifier(conn, person_id, source_id, normalized["source_record_id"], now_iso)
            upsert_mandate(
                conn=conn,
                source_id=source_id,
                row=normalized,
                person_id=person_id,
                institution_id=institution_id,
                party_id=party_id,
                role_id=role_id,
                admin_level_id=admin_level_id,
                territory_id=person_territory_id,
                source_record_pk=source_record_pk,
                now_iso=now_iso,
            )
            seen_ids.append(normalized["source_record_id"])
            loaded += 1

        if records_seen > 0 and loaded == 0:
            raise RuntimeError(
                "abortado: registros extraídos pero sin cargas válidas "
                f"({source_id}: seen={records_seen}, loaded={loaded})"
            )

        min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
        note = extracted.note or ""
        # Strict network threshold must also apply to partial network successes
        # (for example "network-with-partial-errors (...)"), not only pure "network".
        network_strict_candidate = note == "network" or note.startswith("network-with-partial-errors")
        if (
            strict_network
            and network_strict_candidate
            and isinstance(min_loaded, int)
            and loaded < min_loaded
        ):
            raise RuntimeError(
                f"strict-network abortado: records_loaded < min_records_loaded_strict "
                f"({source_id}: loaded={loaded}, min={min_loaded})"
            )

        if ingest_mode == "mandates":
            close_missing_mandates(conn, source_id, seen_ids, snapshot_date, now_iso)
        assert_foreign_key_integrity()
        conn.commit()

        message = f"Ingesta completada: {loaded}/{records_seen} registros validos"
        if note and note != "network":
            message = f"{message} ({note})"

        finish_run(
            conn=conn,
            run_id=run_id,
            status="ok",
            message=message,
            records_seen=records_seen,
            records_loaded=loaded,
            fetched_at=extracted.fetched_at,
            raw_path=extracted.raw_path,
        )
        return records_seen, loaded, note
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        finish_run(
            conn=conn,
            run_id=run_id,
            status="error",
            message=f"Error: {exc}",
            records_seen=0,
            records_loaded=0,
        )
        raise


def print_stats(conn: sqlite3.Connection) -> None:
    queries = {
        "sources": "SELECT COUNT(*) AS c FROM sources",
        "persons": "SELECT COUNT(*) AS c FROM persons",
        "parties": "SELECT COUNT(*) AS c FROM parties",
        "institutions": "SELECT COUNT(*) AS c FROM institutions",
        "mandates_total": "SELECT COUNT(*) AS c FROM mandates",
        "mandates_active": "SELECT COUNT(*) AS c FROM mandates WHERE is_active = 1",
        "ingestion_runs": "SELECT COUNT(*) AS c FROM ingestion_runs",
        "raw_fetches": "SELECT COUNT(*) AS c FROM raw_fetches",
    }
    for label, query in queries.items():
        row = conn.execute(query).fetchone()
        count = row["c"] if row else 0
        print(f"{label}: {count}")

    print("\\nMandatos activos por fuente:")
    for row in conn.execute(
        """
        SELECT source_id, COUNT(*) AS total
        FROM mandates
        WHERE is_active = 1
        GROUP BY source_id
        ORDER BY source_id
        """
    ):
        print(f"- {row['source_id']}: {row['total']}")

    print("\\nUltimas ejecuciones:")
    for row in conn.execute(
        """
        SELECT run_id, source_id, status, started_at, finished_at, records_loaded, message
        FROM ingestion_runs
        ORDER BY run_id DESC
        LIMIT 10
        """
    ):
        print(
            f"- run={row['run_id']} source={row['source_id']} status={row['status']} "
            f"loaded={row['records_loaded']} started={row['started_at']} msg={row['message']}"
        )
