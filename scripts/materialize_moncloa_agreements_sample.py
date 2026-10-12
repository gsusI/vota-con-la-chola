#!/usr/bin/env python3
"""Materialize a deterministic real-only La Moncloa agreements sample.

The source is a checksum-pinned official capture already ingested as
``moncloa_referencias``. Only records whose captured summary explicitly contains
``acuerdo`` are materialized. The script never invents attendees, counterparties,
or influence assertions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/moncloa-aiops04-matrix-20260216.db"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/agreements-moncloa-sample.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/site/public/agreements/data/moncloa-sample.json"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/AGREEMENTS-20260819/evidence/moncloa-agreements-materialization.json"
)

SOURCE_ID = "moncloa_referencias"
EXTRACTOR_METHOD = "moncloa_explicit_agreement_summary_v1"
EXTRACTOR_VERSION = "agreements_moncloa_v1"
TOPIC_METHOD = "moncloa_agreement_keyword_codebook"
TOPIC_VERSION = "agreements_topics_es_v1"
NULL = "\0"

# Release v1 is immutable. These hashes identify the exact global schema and
# extractor bytes used when 6f75ec32... was first published. Additive tables in
# unrelated domains must not rewrite that historical release identity. Current
# executable compatibility is enforced separately by FK/integrity/semantic tests.
FROZEN_RELEASE_SCHEMA_SHA256 = (
    "1d4fbbfb83069298996fb694dcb250c6f9bb7569df93b4deed479cace7a4fbf8"
)
FROZEN_RELEASE_EXTRACTOR_SHA256 = (
    "fbad643a10ccddfbfdd353b7594eab3aa5f8c142be361123cfdb17cf4518da37"
)

CAPTURE_PATH = Path(
    "etl/data/raw/moncloa_referencias/2026/02/16/"
    "moncloa_referencias_20260216T141256Z.json"
)

SOURCE_ROWS_SQL = """
SELECT
  sr.source_record_pk,
  sr.source_id,
  sr.source_record_id,
  sr.source_snapshot_date,
  sr.raw_payload,
  sr.content_sha256 AS source_record_sha256,
  sr.created_at AS source_record_created_at,
  sr.updated_at AS source_record_updated_at,
  json_extract(sr.raw_payload, '$.event_date_iso') AS event_date,
  json_extract(sr.raw_payload, '$.published_at_iso') AS published_at,
  json_extract(sr.raw_payload, '$.title') AS title,
  json_extract(sr.raw_payload, '$.summary_text') AS summary_text,
  json_extract(sr.raw_payload, '$.source_url') AS source_url,
  json_extract(sr.raw_payload, '$.origin_channel') AS origin_channel,
  source.name AS source_name,
  source.default_url AS source_default_url,
  source.data_format AS source_data_format
FROM source_records AS sr
JOIN sources AS source ON source.source_id = sr.source_id
WHERE sr.source_id = ?
  AND NULLIF(TRIM(json_extract(sr.raw_payload, '$.summary_text')), '') IS NOT NULL
  AND LOWER(json_extract(sr.raw_payload, '$.summary_text')) LIKE '%acuerdo%'
  AND json_extract(sr.raw_payload, '$.source_url') LIKE 'https://www.lamoncloa.gob.es/%'
ORDER BY event_date, sr.source_record_id
"""

TOPIC_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "public_finance",
        "Hacienda, presupuestos y deuda pública",
        ("presupuest", "crédito", "deuda", "fondo de contingencia", "gasto"),
    ),
    (
        "transport_mobility",
        "Transportes y movilidad",
        ("transportes", "autopistas", "movilidad"),
    ),
    (
        "social_protection",
        "Protección social",
        ("prestaciones", "bonificaciones", "síndrome tóxico", "seguridad social"),
    ),
    (
        "elections_democracy",
        "Elecciones y calidad democrática",
        ("elecciones", "electoral"),
    ),
    (
        "international_relations",
        "Relaciones internacionales",
        (
            "unión europea",
            "comunidad europea de la energía atómica",
            "sultanato de omán",
            "pasaportes diplomáticos",
        ),
    ),
    (
        "research_innovation",
        "Ciencia, investigación e innovación",
        ("centro común de investigación", "metrología"),
    ),
    (
        "equality_gender_violence",
        "Igualdad y violencia de género",
        ("ministerio de igualdad", "violencia de género"),
    ),
    (
        "public_administration",
        "Administración pública",
        ("administraciones públicas", "administración pública"),
    ),
)

EXPLICIT_ACTOR_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "Ministerio de Transportes y Movilidad Sostenible",
        "affected_body",
        "public_body",
    ),
    (
        "Ministerio de Inclusión, Seguridad Social y Migraciones",
        "affected_body",
        "public_body",
    ),
    ("Cortes Generales", "affected_body", "public_body"),
    ("Centro Español de Metrología", "affected_body", "public_body"),
    ("Correos y Telégrafos S.A.", "affected_body", "organization"),
    ("Unión Europea", "counterparty", "organization"),
    (
        "Comunidad Europea de la Energía Atómica",
        "counterparty",
        "organization",
    ),
    ("Reino de España", "counterparty", "public_body"),
    ("Ministerio de Igualdad", "affected_body", "public_body"),
    ("Sultanato de Omán", "counterparty", "public_body"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--published-out", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part or "") for part in parts)])
    return f"vclc:{kind}:{sha256_text(payload)}"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp_path.write_bytes(data)
    temp_path.replace(path)


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def copy_exact_row(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    where_column: str,
    where_value: object,
) -> None:
    row = source.execute(
        f'SELECT * FROM "{table}" WHERE "{where_column}" = ?', (where_value,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing source row {table}.{where_column}={where_value}")
    columns = list(row.keys())
    column_names = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    target.execute(
        f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders})',
        tuple(row[column] for column in columns),
    )


def source_capture(source: sqlite3.Connection) -> dict[str, Any]:
    row = source.execute(
        """
        SELECT
          fetch.raw_path,
          fetch.content_sha256,
          fetch.bytes,
          fetch.fetched_at,
          fetch.content_type,
          source.default_url AS official_source_url
        FROM raw_fetches AS fetch
        JOIN sources AS source ON source.source_id = fetch.source_id
        WHERE fetch.source_id = ?
        ORDER BY fetch.fetched_at DESC, fetch.fetch_id DESC
        LIMIT 1
        """,
        (SOURCE_ID,),
    ).fetchone()
    if row is None:
        raise RuntimeError("missing official Moncloa capture metadata")
    repo_path = REPO_ROOT / CAPTURE_PATH
    if not repo_path.is_file():
        raise RuntimeError(f"missing captured official bytes: {CAPTURE_PATH.as_posix()}")
    actual_hash = sha256_file(repo_path)
    actual_bytes = repo_path.stat().st_size
    if actual_hash != row["content_sha256"] or actual_bytes != int(row["bytes"]):
        raise RuntimeError("captured Moncloa bytes differ from raw_fetches metadata")
    return {
        "path": CAPTURE_PATH.as_posix(),
        "content_sha256": actual_hash,
        "bytes": actual_bytes,
        "fetched_at": str(row["fetched_at"]),
        "content_type": row["content_type"],
        "source_url": str(row["official_source_url"]),
    }


def load_rows(source: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = [dict(row) for row in source.execute(SOURCE_ROWS_SQL, (SOURCE_ID,))]
    if not rows:
        raise RuntimeError("official capture contains no explicit agreement summaries")
    for row in rows:
        summary = str(row["summary_text"] or "")
        if "acuerdo" not in summary.casefold():
            raise RuntimeError(f"non-explicit agreement selected: {row['source_record_id']}")
    return rows


def topic_assignments(summary: str) -> list[dict[str, Any]]:
    lowered = summary.casefold()
    assignments: list[dict[str, Any]] = []
    for topic_key, topic_label, needles in TOPIC_RULES:
        match = next((needle for needle in needles if needle.casefold() in lowered), None)
        if match is not None:
            assignments.append(
                {
                    "topic_key": topic_key,
                    "topic_label": topic_label,
                    "assignment_kind": "derived_rule",
                    "assignment_method": TOPIC_METHOD,
                    "assignment_version": TOPIC_VERSION,
                    "match_text": match,
                    "review_status": "unreviewed",
                }
            )
    if not assignments:
        assignments.append(
            {
                "topic_key": "other_executive_action",
                "topic_label": "Otra acción ejecutiva",
                "assignment_kind": "derived_rule",
                "assignment_method": TOPIC_METHOD,
                "assignment_version": TOPIC_VERSION,
                "match_text": "acuerdo",
                "review_status": "unreviewed",
            }
        )
    return assignments


def explicit_parties(summary: str) -> list[dict[str, str]]:
    parties: list[dict[str, str]] = [
        {
            "party_role": "adopter",
            "actor_kind": "public_body",
            "source_label": "Consejo de Ministros",
            "resolution_method": "exact_source_subject",
        },
        {
            "party_role": "publishing_body",
            "actor_kind": "public_body",
            "source_label": "Gobierno de España / La Moncloa",
            "resolution_method": "official_source_identity",
        },
    ]
    for label, party_role, actor_kind in EXPLICIT_ACTOR_RULES:
        if label.casefold() not in summary.casefold():
            continue
        parties.append(
            {
                "party_role": party_role,
                "actor_kind": actor_kind,
                "source_label": label,
                "resolution_method": "exact_source_substring_v1",
            }
        )
    return parties


def canonical_record(row: dict[str, Any], capture: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row["source_id"])
    record_id = str(row["source_record_id"])
    event_date = str(row["event_date"])
    summary = str(row["summary_text"])
    title = str(row["title"] or "Referencia del Consejo de Ministros")
    meeting_id = stable_id("meeting", source_id, record_id, 0, "council_session")
    agenda_item_id = stable_id("agenda-item", meeting_id, 0)
    agreement_id = stable_id(
        "agreement", source_id, record_id, 0, "executive_decision"
    )
    quote_hash = sha256_text(summary)
    participants = [
        {
            "meeting_participant_id": stable_id(
                "meeting-participant", meeting_id, "convener", 0
            ),
            "participant_ordinal": 0,
            "actor_role": "convener",
            "attendance_claim_state": "not_claimed",
            "actor_kind": "public_body",
            "source_label": "Consejo de Ministros",
            "identity_state": "source_scoped",
            "resolution_method": "exact_source_subject",
        },
        {
            "meeting_participant_id": stable_id(
                "meeting-participant", meeting_id, "disclosing_body", 1
            ),
            "participant_ordinal": 1,
            "actor_role": "disclosing_body",
            "attendance_claim_state": "not_claimed",
            "actor_kind": "public_body",
            "source_label": "Gobierno de España / La Moncloa",
            "identity_state": "source_scoped",
            "resolution_method": "official_source_identity",
        },
    ]
    parties = []
    for ordinal, party in enumerate(explicit_parties(summary)):
        parties.append(
            {
                "agreement_party_id": stable_id(
                    "agreement-party", agreement_id, party["party_role"], ordinal
                ),
                "party_ordinal": ordinal,
                "identity_state": "source_scoped",
                **party,
            }
        )
    topics = []
    for assignment in topic_assignments(summary):
        topics.append(
            {
                "agreement_topic_id": stable_id(
                    "agreement-topic",
                    agreement_id,
                    assignment["topic_key"],
                    TOPIC_METHOD,
                    TOPIC_VERSION,
                ),
                **assignment,
            }
        )
    provenance = {
        "source_id": source_id,
        "source_record_id": record_id,
        "source_record_sha256": str(row["source_record_sha256"]),
        "source_url": str(row["source_url"]),
        "source_snapshot_date": row["source_snapshot_date"],
        "origin_channel": row["origin_channel"],
        "capture_path": capture["path"],
        "capture_sha256": capture["content_sha256"],
        "capture_bytes": capture["bytes"],
        "captured_at": capture["fetched_at"],
        "extractor_method": EXTRACTOR_METHOD,
        "extractor_version": EXTRACTOR_VERSION,
    }
    meeting_evidence = {
        "meeting_evidence_id": stable_id("meeting-evidence", meeting_id, 0),
        "evidence_ordinal": 0,
        "evidence_role": "outcome",
        "source_url": str(row["source_url"]),
        "content_sha256": str(row["source_record_sha256"]),
        "exact_quote": summary,
        "quote_sha256": quote_hash,
        "selector": "$.summary_text",
        "evidence_state": "captured_bytes",
    }
    agreement_evidence = {
        "agreement_evidence_id": stable_id("agreement-evidence", agreement_id, 0),
        "evidence_ordinal": 0,
        "evidence_role": "official_summary",
        "source_url": str(row["source_url"]),
        "content_sha256": str(row["source_record_sha256"]),
        "exact_quote": summary,
        "quote_sha256": quote_hash,
        "selector": "$.summary_text",
        "evidence_state": "captured_bytes",
    }
    return {
        "meeting": {
            "meeting_id": meeting_id,
            "meeting_kind": "council_session",
            "title": title,
            "summary": summary,
            "scheduled_state": "occurred",
            "attendance_disclosure_state": "not_disclosed",
            "event_date": event_date,
            "time_precision": "day",
            "published_at": row["published_at"],
            "fact_state": "source_summary",
            "participants": participants,
            "agenda_items": [
                {
                    "agenda_item_id": agenda_item_id,
                    "item_ordinal": 0,
                    "agenda_state": "source_summary",
                    "title": title,
                    "description": summary,
                    "source_text_state": "source_summary",
                }
            ],
            "evidence": [meeting_evidence],
        },
        "agreement": {
            "agreement_id": agreement_id,
            "agreement_kind": "executive_decision",
            "agreement_status": "adopted",
            "title": title,
            "summary": summary,
            "meeting_id": meeting_id,
            "agenda_item_id": agenda_item_id,
            "adopted_on": event_date,
            "published_on": row["published_at"],
            "date_precision": "day",
            "fact_state": "source_summary",
            "parties": parties,
            "topics": topics,
            "evidence": [agreement_evidence],
            "influence_state": "not_asserted",
        },
        "provenance": provenance,
    }


def materialize_db(
    source: sqlite3.Connection,
    records: list[dict[str, Any]],
    schema_path: Path,
    out_db: Path,
) -> dict[str, int]:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_db.with_name(f".{out_db.name}.tmp-{os.getpid()}")
    if temp_path.exists():
        temp_path.unlink()
    target = sqlite3.connect(temp_path)
    target.row_factory = sqlite3.Row
    target.execute("PRAGMA foreign_keys = ON")
    try:
        target.executescript(schema_path.read_text(encoding="utf-8"))
        copy_exact_row(source, target, "sources", "source_id", SOURCE_ID)
        copied_source_records: set[int] = set()
        for record in records:
            provenance = record["provenance"]
            source_row = source.execute(
                "SELECT * FROM source_records WHERE source_id = ? AND source_record_id = ?",
                (provenance["source_id"], provenance["source_record_id"]),
            ).fetchone()
            if source_row is None:
                raise RuntimeError("selected source record disappeared")
            source_record_pk = int(source_row["source_record_pk"])
            if source_record_pk not in copied_source_records:
                copy_exact_row(
                    source,
                    target,
                    "source_records",
                    "source_record_pk",
                    source_record_pk,
                )
                copied_source_records.add(source_record_pk)

            meeting = record["meeting"]
            agreement = record["agreement"]
            created_at = str(source_row["created_at"])
            updated_at = str(source_row["updated_at"])
            common = (
                SOURCE_ID,
                source_record_pk,
                provenance["source_record_id"],
                provenance["source_snapshot_date"],
            )
            target.execute(
                """
                INSERT INTO accountability_meetings (
                  meeting_id, source_id, source_record_pk, source_record_id,
                  source_snapshot_date, meeting_ordinal, meeting_kind, title,
                  summary, scheduled_state, attendance_disclosure_state, event_date,
                  time_precision, published_at, observed_at, source_url,
                  content_sha256, fact_state, extractor_method, extractor_version,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting["meeting_id"],
                    *common,
                    meeting["meeting_kind"],
                    meeting["title"],
                    meeting["summary"],
                    meeting["scheduled_state"],
                    meeting["attendance_disclosure_state"],
                    meeting["event_date"],
                    meeting["time_precision"],
                    meeting["published_at"],
                    provenance["captured_at"],
                    provenance["source_url"],
                    provenance["source_record_sha256"],
                    meeting["fact_state"],
                    EXTRACTOR_METHOD,
                    EXTRACTOR_VERSION,
                    canonical_json({"origin_channel": provenance["origin_channel"]}),
                    created_at,
                    updated_at,
                ),
            )
            for participant in meeting["participants"]:
                target.execute(
                    """
                    INSERT INTO meeting_participants (
                      meeting_participant_id, meeting_id, participant_ordinal,
                      actor_role, attendance_claim_state, actor_kind, source_label,
                      identity_state, resolution_method, source_id, source_record_pk,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        participant["meeting_participant_id"],
                        meeting["meeting_id"],
                        participant["participant_ordinal"],
                        participant["actor_role"],
                        participant["attendance_claim_state"],
                        participant["actor_kind"],
                        participant["source_label"],
                        participant["identity_state"],
                        participant["resolution_method"],
                        SOURCE_ID,
                        source_record_pk,
                        created_at,
                        updated_at,
                    ),
                )
            agenda = meeting["agenda_items"][0]
            target.execute(
                """
                INSERT INTO meeting_agenda_items (
                  agenda_item_id, meeting_id, item_ordinal, agenda_state, title,
                  description, source_text_state, source_id, source_record_pk,
                  extractor_method, extractor_version, raw_payload_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                """,
                (
                    agenda["agenda_item_id"],
                    meeting["meeting_id"],
                    agenda["item_ordinal"],
                    agenda["agenda_state"],
                    agenda["title"],
                    agenda["description"],
                    agenda["source_text_state"],
                    SOURCE_ID,
                    source_record_pk,
                    EXTRACTOR_METHOD,
                    EXTRACTOR_VERSION,
                    created_at,
                    updated_at,
                ),
            )
            meeting_evidence = meeting["evidence"][0]
            target.execute(
                """
                INSERT INTO meeting_evidence (
                  meeting_evidence_id, meeting_id, agenda_item_id, evidence_ordinal,
                  evidence_role, source_id, source_record_pk, source_url,
                  content_sha256, exact_quote, quote_sha256, selector,
                  evidence_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_evidence["meeting_evidence_id"],
                    meeting["meeting_id"],
                    agenda["agenda_item_id"],
                    meeting_evidence["evidence_ordinal"],
                    meeting_evidence["evidence_role"],
                    SOURCE_ID,
                    source_record_pk,
                    meeting_evidence["source_url"],
                    meeting_evidence["content_sha256"],
                    meeting_evidence["exact_quote"],
                    meeting_evidence["quote_sha256"],
                    meeting_evidence["selector"],
                    meeting_evidence["evidence_state"],
                    created_at,
                    updated_at,
                ),
            )
            target.execute(
                """
                INSERT INTO agreements (
                  agreement_id, source_id, source_record_pk, source_record_id,
                  source_snapshot_date, agreement_ordinal, agreement_kind,
                  agreement_status, title, summary, meeting_id, agenda_item_id,
                  adopted_on, published_on, observed_at, date_precision, source_url,
                  content_sha256, fact_state, extractor_method, extractor_version,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agreement["agreement_id"],
                    *common,
                    agreement["agreement_kind"],
                    agreement["agreement_status"],
                    agreement["title"],
                    agreement["summary"],
                    meeting["meeting_id"],
                    agenda["agenda_item_id"],
                    agreement["adopted_on"],
                    agreement["published_on"],
                    provenance["captured_at"],
                    agreement["date_precision"],
                    provenance["source_url"],
                    provenance["source_record_sha256"],
                    agreement["fact_state"],
                    EXTRACTOR_METHOD,
                    EXTRACTOR_VERSION,
                    canonical_json({"influence_state": "not_asserted"}),
                    created_at,
                    updated_at,
                ),
            )
            for party in agreement["parties"]:
                target.execute(
                    """
                    INSERT INTO agreement_parties (
                      agreement_party_id, agreement_id, party_ordinal, party_role,
                      actor_kind, source_label, identity_state, resolution_method,
                      source_id, source_record_pk, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        party["agreement_party_id"],
                        agreement["agreement_id"],
                        party["party_ordinal"],
                        party["party_role"],
                        party["actor_kind"],
                        party["source_label"],
                        party["identity_state"],
                        party["resolution_method"],
                        SOURCE_ID,
                        source_record_pk,
                        created_at,
                        updated_at,
                    ),
                )
            agreement_evidence = agreement["evidence"][0]
            target.execute(
                """
                INSERT INTO agreement_evidence (
                  agreement_evidence_id, agreement_id, evidence_ordinal,
                  evidence_role, source_id, source_record_pk, source_url,
                  content_sha256, exact_quote, quote_sha256, selector,
                  evidence_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agreement_evidence["agreement_evidence_id"],
                    agreement["agreement_id"],
                    agreement_evidence["evidence_ordinal"],
                    agreement_evidence["evidence_role"],
                    SOURCE_ID,
                    source_record_pk,
                    agreement_evidence["source_url"],
                    agreement_evidence["content_sha256"],
                    agreement_evidence["exact_quote"],
                    agreement_evidence["quote_sha256"],
                    agreement_evidence["selector"],
                    agreement_evidence["evidence_state"],
                    created_at,
                    updated_at,
                ),
            )
            for topic in agreement["topics"]:
                target.execute(
                    """
                    INSERT INTO agreement_topics (
                      agreement_topic_id, agreement_id, topic_key, topic_label,
                      assignment_kind, assignment_method, assignment_version,
                      match_text, review_status, source_id, source_record_pk,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic["agreement_topic_id"],
                        agreement["agreement_id"],
                        topic["topic_key"],
                        topic["topic_label"],
                        topic["assignment_kind"],
                        topic["assignment_method"],
                        topic["assignment_version"],
                        topic["match_text"],
                        topic["review_status"],
                        SOURCE_ID,
                        source_record_pk,
                        created_at,
                        updated_at,
                    ),
                )
        target.commit()
        fk_errors = list(target.execute("PRAGMA foreign_key_check"))
        if fk_errors:
            raise RuntimeError(f"foreign key violations: {len(fk_errors)}")
        counts = {
            table: int(target.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in (
                "source_records",
                "accountability_meetings",
                "meeting_participants",
                "meeting_agenda_items",
                "meeting_evidence",
                "agreements",
                "agreement_parties",
                "agreement_evidence",
                "agreement_topics",
                "influence_assertions",
            )
        }
    except Exception:
        target.close()
        temp_path.unlink(missing_ok=True)
        raise
    target.close()
    temp_path.replace(out_db)
    return counts


def build_snapshot(
    source: sqlite3.Connection,
    records: list[dict[str, Any]],
    capture: dict[str, Any],
    schema_path: Path,
    script_path: Path,
    db_counts: dict[str, int],
) -> dict[str, Any]:
    source_counts = {
        "source_records_total": int(
            source.execute("SELECT COUNT(*) FROM source_records").fetchone()[0]
        ),
        "moncloa_referencias_records": int(
            source.execute(
                "SELECT COUNT(*) FROM source_records WHERE source_id = ?", (SOURCE_ID,)
            ).fetchone()[0]
        ),
        "explicit_agreement_records": len(records),
    }
    party_roles: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    for record in records:
        for party in record["agreement"]["parties"]:
            role = str(party["party_role"])
            party_roles[role] = party_roles.get(role, 0) + 1
        for topic in record["agreement"]["topics"]:
            key = str(topic["topic_key"])
            topic_counts[key] = topic_counts.get(key, 0) + 1

    release_basis = {
        "contract": "agreements-moncloa-release-v1",
        "source_id": SOURCE_ID,
        "source_capture_sha256": capture["content_sha256"],
        "source_capture_bytes": capture["bytes"],
        "schema_sha256": FROZEN_RELEASE_SCHEMA_SHA256,
        "extractor_sha256": FROZEN_RELEASE_EXTRACTOR_SHA256,
        "records": records,
    }
    release_id = sha256_text(canonical_json(release_basis))
    return {
        "schema_version": "agreements-influence-public-v1",
        "release_id": release_id,
        "generated_at": capture["fetched_at"],
        "real_data_only": True,
        "synthetic_or_mock": False,
        "public_domain_information_policy": "retained_exactly",
        "source": {
            "source_id": SOURCE_ID,
            "name": "La Moncloa - Referencias del Consejo de Ministros",
            "default_url": "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx",
            "official_domain": "www.lamoncloa.gob.es",
            "capture": capture,
            "corpus_counts": source_counts,
        },
        "methodology": {
            "contract": "docs/data-model/agreements-influence-spec-v1.md",
            "selection": "all_captured_moncloa_referencias_with_explicit_acuerdo_in_summary",
            "extractor_method": EXTRACTOR_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
            "topic_assignment": "derived_rule_unreviewed",
            "identity_policy": "retain_exact_official_public_names_and_identifiers",
            "attendance_policy": "no_attendee_claim_without_source_disclosure",
            "influence_policy": "zero_influence_assertions_in_fact_sample",
            "limitations": [
                "captured_reference_summary_is_not_the_full_agreement_text",
                "captured_records_do_not_disclose_a_complete_attendee_list",
                "adopted_does_not_prove_signed_in_force_implemented_or_effective",
                "meeting_or_temporal_proximity_does_not_prove_influence",
                "topic_assignments_are_deterministic_unreviewed_classifications",
            ],
        },
        "counts": {
            "meetings": len(records),
            "agreements": len(records),
            "meeting_participants": sum(
                len(record["meeting"]["participants"]) for record in records
            ),
            "agreement_parties": sum(
                len(record["agreement"]["parties"]) for record in records
            ),
            "agreement_topics": sum(
                len(record["agreement"]["topics"]) for record in records
            ),
            "meeting_evidence": len(records),
            "agreement_evidence": len(records),
            "attendance_claims": 0,
            "influence_assertions": 0,
            "party_roles": dict(sorted(party_roles.items())),
            "topic_counts": dict(sorted(topic_counts.items())),
            "materialized_db": db_counts,
        },
        "records": records,
        "influence_assertions": [],
        "release_basis": {
            key: value for key, value in release_basis.items() if key != "records"
        },
    }


def main() -> int:
    args = parse_args()
    if not args.source_db.is_file():
        raise SystemExit(f"missing source DB: {args.source_db}")
    source = sqlite3.connect(args.source_db)
    source.row_factory = sqlite3.Row
    try:
        capture = source_capture(source)
        source_rows = load_rows(source)
        records = [canonical_record(row, capture) for row in source_rows]
        db_counts = materialize_db(source, records, args.schema, args.out_db)
        snapshot = build_snapshot(
            source,
            records,
            capture,
            args.schema,
            Path(__file__),
            db_counts,
        )
    finally:
        source.close()

    data = (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    atomic_write(args.published_out, data)
    atomic_write(args.public_out, data)
    report = {
        "status": "ok",
        "release_id": snapshot["release_id"],
        "artifact_sha256": sha256_bytes(data),
        "artifact_bytes": len(data),
        "source_capture": snapshot["source"]["capture"],
        "source_counts": snapshot["source"]["corpus_counts"],
        "counts": snapshot["counts"],
        "outputs": {
            "database": report_path(args.out_db),
            "published": report_path(args.published_out),
            "public": report_path(args.public_out),
        },
    }
    atomic_write(
        args.report_out,
        (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
