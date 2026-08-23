#!/usr/bin/env python3
"""Materialize the first time-aware actor graph from real official-source data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator


CONTRACT_VERSION = "actor_graph_v1"
EXTRACTOR_VERSION = "actor_graph_real_projection_v2"
DEFAULT_SNAPSHOT_DATE = "2026-08-20"
DEFAULT_GENERATED_AT = "2026-08-20T00:00:00Z"


SOURCE_COLUMNS = (
    "source_id",
    "name",
    "scope",
    "default_url",
    "data_format",
    "is_active",
    "created_at",
    "updated_at",
)
SOURCE_METADATA_COLUMNS = SOURCE_COLUMNS[1:]

ACTOR_GRAPH_SECONDARY_INDEXES = {
    "idx_actor_graph_source_mappings_upstream": """
        CREATE INDEX idx_actor_graph_source_mappings_upstream
        ON actor_graph_source_mappings(
          upstream_source_id, input_database_key, release_id
        )
    """,
    "idx_actor_graph_source_mappings_graph": """
        CREATE INDEX idx_actor_graph_source_mappings_graph
        ON actor_graph_source_mappings(graph_source_id, release_id)
    """,
    "idx_actor_graph_nodes_scope": """
        CREATE INDEX idx_actor_graph_nodes_scope
        ON actor_graph_nodes(
          source_scope_id, actor_kind, actor_subtype, stable_source_key
        )
    """,
    "idx_actor_graph_node_versions_release_kind": """
        CREATE INDEX idx_actor_graph_node_versions_release_kind
        ON actor_graph_node_versions(release_id, identity_state, actor_id)
    """,
    "idx_actor_graph_node_versions_label": """
        CREATE INDEX idx_actor_graph_node_versions_label
        ON actor_graph_node_versions(normalized_label, actor_id)
    """,
    "idx_actor_graph_identifiers_lookup": """
        CREATE INDEX idx_actor_graph_identifiers_lookup
        ON actor_graph_identifier_versions(namespace, value, release_id, actor_id)
    """,
    "idx_actor_graph_aliases_lookup": """
        CREATE INDEX idx_actor_graph_aliases_lookup
        ON actor_graph_alias_versions(normalized_alias, release_id, actor_id)
    """,
    "idx_actor_graph_relationships_subject": """
        CREATE INDEX idx_actor_graph_relationships_subject
        ON actor_graph_relationships(
          subject_actor_id, relationship_type, context_kind, context_id
        )
    """,
    "idx_actor_graph_relationships_object": """
        CREATE INDEX idx_actor_graph_relationships_object
        ON actor_graph_relationships(
          object_actor_id, relationship_type, context_kind, context_id
        )
    """,
    "idx_actor_graph_relationship_versions_release_time": """
        CREATE INDEX idx_actor_graph_relationship_versions_release_time
        ON actor_graph_relationship_versions(
          release_id, source_id, valid_from, valid_to, relationship_id
        )
    """,
    "idx_actor_graph_resolution_source": """
        CREATE INDEX idx_actor_graph_resolution_source
        ON actor_resolution_decisions(source_actor_id, observed_at, outcome)
    """,
    "idx_actor_graph_resolution_candidate": """
        CREATE INDEX idx_actor_graph_resolution_candidate
        ON actor_resolution_decisions(candidate_actor_id, observed_at, outcome)
    """,
    "idx_actor_org_change_subject_time": """
        CREATE INDEX idx_actor_org_change_subject_time
        ON actor_organization_change_events(
          subject_actor_id, effective_date, event_type
        )
    """,
}


MANDATE_SQL = """
SELECT
  m.mandate_id, m.source_id, m.source_record_id, m.source_snapshot_date,
  m.start_date, m.end_date, m.is_active, m.role_title, m.level,
  m.territory_code, m.first_seen_at, m.last_seen_at,
  p.person_id, p.canonical_key AS person_key, p.full_name,
  p.given_name, p.family_name, p.birth_date,
  i.institution_id, i.name AS institution_name, i.level AS institution_level,
  i.territory_code AS institution_territory_code,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym,
  role.canonical_key AS role_code,
  source.default_url AS source_url,
  sr.content_sha256 AS source_content_sha256
FROM mandates AS m
JOIN persons AS p ON p.person_id = m.person_id
JOIN institutions AS i ON i.institution_id = m.institution_id
JOIN sources AS source ON source.source_id = m.source_id
LEFT JOIN parties AS party ON party.party_id = m.party_id
LEFT JOIN roles AS role ON role.role_id = m.role_id
LEFT JOIN source_records AS sr ON sr.source_record_pk = m.source_record_pk
ORDER BY m.source_id, m.source_record_id, m.mandate_id
"""

BOE_CANDIDATE_SQL = """
SELECT
  c.candidate_occurrence_id, c.candidacy_id, c.election_id, c.election_date,
  c.election_type_code, c.electoral_board, c.electoral_district,
  c.chamber_code, c.candidacy_number, c.candidate_order,
  c.candidate_type_code, c.substitute_for_candidate_order, c.full_name,
  c.source_text_exact, c.source_id, c.source_url,
  c.source_content_sha256, c.source_paragraph_number,
  c.first_seen_snapshot_date, c.last_seen_snapshot_date, c.is_present,
  sr.source_record_id,
  p.person_id, p.canonical_key AS person_key,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym
FROM boe_election_candidate_occurrences AS c
JOIN persons AS p ON p.person_id = c.person_id
JOIN parties AS party ON party.party_id = c.party_id
JOIN source_records AS sr ON sr.source_record_pk = c.source_record_pk
ORDER BY c.source_id, c.candidate_occurrence_id
"""

BOE_EFFECTIVE_SQL = """
SELECT
  c.effective_candidate_occurrence_id, c.candidacy_id,
  c.base_candidate_occurrence_id, c.election_id, c.election_date,
  c.election_type_code, c.electoral_board, c.electoral_district,
  c.chamber_code, c.candidacy_number, c.candidate_order,
  c.candidate_type_code, c.substitute_for_candidate_order, c.full_name,
  c.effective_source_url AS source_url,
  c.effective_source_content_sha256 AS source_content_sha256,
  c.source_text_exact, c.source_paragraph_number, c.correction_operation_id,
  c.first_seen_snapshot_date, c.last_seen_snapshot_date, c.is_present,
  COALESCE(c.source_id, base.source_id) AS source_id,
  COALESCE(sr.source_record_id, base_sr.source_record_id) AS source_record_id,
  p.person_id, p.canonical_key AS person_key,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym
FROM boe_election_effective_candidate_occurrences AS c
LEFT JOIN boe_election_candidate_occurrences AS base
  ON base.candidate_occurrence_id = c.base_candidate_occurrence_id
JOIN persons AS p ON p.person_id = c.person_id
JOIN parties AS party ON party.party_id = c.party_id
LEFT JOIN source_records AS sr ON sr.source_record_pk = c.source_record_pk
LEFT JOIN source_records AS base_sr ON base_sr.source_record_pk = base.source_record_pk
ORDER BY source_id, c.effective_candidate_occurrence_id
"""

ELECTED_SQL = """
SELECT
  e.elected_official_id, e.election_date, e.election_code, e.chamber,
  e.province_code, e.province_name, e.full_name, e.candidacy_name,
  e.candidacy_acronym, e.votes, e.source_id, e.source_url,
  e.source_content_sha256, e.source_row_number,
  e.first_seen_snapshot_date, e.last_seen_snapshot_date, e.is_present,
  sr.source_record_id,
  p.person_id, p.canonical_key AS person_key,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym,
  i.institution_id, i.name AS institution_name, i.level AS institution_level,
  i.territory_code AS institution_territory_code
FROM infoelectoral_elected_officials AS e
JOIN persons AS p ON p.person_id = e.person_id
LEFT JOIN parties AS party ON party.party_id = e.party_id
LEFT JOIN institutions AS i ON i.institution_id = e.institution_id
JOIN source_records AS sr ON sr.source_record_pk = e.source_record_pk
ORDER BY e.source_id, e.elected_official_id
"""

PARLIAMENTARY_MEMBERSHIP_SQL = """
SELECT
  membership.membership_id, membership.source_id, membership.legislature,
  membership.start_date, membership.end_date, membership.source_url,
  membership.evidence_quote,
  p.person_id, p.canonical_key AS person_key, p.full_name,
  pg.parliamentary_group_id, pg.source_id AS group_source_id,
  pg.group_code, pg.name AS group_name, pg.legislature AS group_legislature,
  source.default_url AS source_default_url
FROM person_parliamentary_group_memberships AS membership
JOIN persons AS p ON p.person_id = membership.person_id
JOIN parliamentary_groups AS pg
  ON pg.parliamentary_group_id = membership.parliamentary_group_id
JOIN sources AS source ON source.source_id = membership.source_id
ORDER BY membership.source_id, membership.membership_id
"""

ORG_MEMBERSHIP_SQL = """
SELECT
  membership.membership_id, membership.source_id, membership.source_record_pk,
  membership.membership_kind, membership.role_label,
  membership.start_date, membership.end_date, membership.source_kind,
  membership.source_url, membership.evidence_date, membership.evidence_quote,
  p.person_id, p.canonical_key AS person_key, p.full_name,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym,
  position.position_id, position.position_code, position.title AS position_title,
  source.default_url AS source_default_url,
  sr.source_record_id, sr.content_sha256 AS source_content_sha256
FROM person_org_memberships AS membership
JOIN persons AS p ON p.person_id = membership.person_id
LEFT JOIN parties AS party ON party.party_id = membership.party_id
LEFT JOIN government_positions AS position
  ON position.position_id = membership.position_id
LEFT JOIN sources AS source ON source.source_id = membership.source_id
LEFT JOIN source_records AS sr
  ON sr.source_record_pk = membership.source_record_pk
ORDER BY membership.source_id, membership.membership_id
"""

PERSON_IDENTIFIER_SQL = """
WITH person_refs(source_id, person_id) AS (
  SELECT source_id, person_id FROM mandates
  UNION SELECT source_id, person_id FROM boe_election_candidate_occurrences
  UNION SELECT COALESCE(source_id, 'boe_election_candidates'), person_id
    FROM boe_election_effective_candidate_occurrences WHERE person_id IS NOT NULL
  UNION SELECT source_id, person_id FROM infoelectoral_elected_officials
    WHERE person_id IS NOT NULL
  UNION SELECT source_id, person_id FROM person_org_memberships
    WHERE source_id IS NOT NULL
  UNION SELECT source_id, person_id FROM person_parliamentary_group_memberships
)
SELECT refs.source_id, p.person_id, p.canonical_key AS person_key, p.full_name,
  identifier.namespace, identifier.value, source.default_url AS source_url
FROM person_refs AS refs
JOIN persons AS p ON p.person_id = refs.person_id
JOIN person_identifiers AS identifier ON identifier.person_id = p.person_id
JOIN sources AS source ON source.source_id = refs.source_id
ORDER BY refs.source_id, p.canonical_key, identifier.namespace, identifier.value
"""

PERSON_ALIAS_SQL = """
WITH person_refs(source_id, person_id) AS (
  SELECT source_id, person_id FROM mandates
  UNION SELECT source_id, person_id FROM boe_election_candidate_occurrences
  UNION SELECT COALESCE(source_id, 'boe_election_candidates'), person_id
    FROM boe_election_effective_candidate_occurrences WHERE person_id IS NOT NULL
  UNION SELECT source_id, person_id FROM infoelectoral_elected_officials
    WHERE person_id IS NOT NULL
  UNION SELECT source_id, person_id FROM person_org_memberships
    WHERE source_id IS NOT NULL
  UNION SELECT source_id, person_id FROM person_parliamentary_group_memberships
)
SELECT refs.source_id, p.person_id, p.canonical_key AS person_key, p.full_name,
  alias.alias, alias.canonical_alias, alias.source_record_pk,
  alias.source_url, alias.evidence_date, alias.evidence_quote,
  source.default_url AS source_default_url,
  sr.source_record_id, sr.content_sha256 AS source_content_sha256
FROM person_refs AS refs
JOIN persons AS p ON p.person_id = refs.person_id
JOIN person_name_aliases AS alias ON alias.person_id = p.person_id
JOIN sources AS source ON source.source_id = refs.source_id
LEFT JOIN source_records AS sr ON sr.source_record_pk = alias.source_record_pk
ORDER BY refs.source_id, p.canonical_key, alias.canonical_alias, alias.alias
"""

PARTY_ALIAS_SQL = """
WITH party_refs(source_id, party_id) AS (
  SELECT source_id, party_id FROM mandates WHERE party_id IS NOT NULL
  UNION SELECT source_id, party_id FROM boe_election_candidate_occurrences
  UNION SELECT COALESCE(source_id, 'boe_election_candidates'), party_id
    FROM boe_election_effective_candidate_occurrences WHERE party_id IS NOT NULL
  UNION SELECT source_id, party_id FROM infoelectoral_elected_officials
    WHERE party_id IS NOT NULL
  UNION SELECT source_id, party_id FROM person_org_memberships
    WHERE source_id IS NOT NULL AND party_id IS NOT NULL
)
SELECT refs.source_id, party.party_id, party.name AS party_name,
  party.acronym AS party_acronym, alias.alias, alias.canonical_alias,
  source.default_url AS source_url
FROM party_refs AS refs
JOIN parties AS party ON party.party_id = refs.party_id
JOIN party_aliases AS alias ON alias.party_id = party.party_id
JOIN sources AS source ON source.source_id = refs.source_id
ORDER BY refs.source_id, party.name, alias.canonical_alias, alias.alias
"""

SPENDING_ACTOR_SQL = """
SELECT
  actor.spending_item_actor_id, actor.actor_ordinal, actor.actor_role,
  actor.actor_kind, actor.source_label, actor.source_identifier,
  actor.source_identifier_scheme, actor.identity_state,
  actor.resolution_method, actor.resolution_confidence, actor.source_id,
  item.spending_item_id, item.source_record_id, item.source_snapshot_date,
  item.source_url, item.content_sha256 AS source_content_sha256,
  item.spending_kind, item.published_on, item.decision_on,
  item.effective_from, item.effective_to, item.title
FROM spending_item_actors AS actor
JOIN spending_items AS item ON item.spending_item_id = actor.spending_item_id
ORDER BY actor.source_id, actor.spending_item_actor_id
"""

AGREEMENT_ACTOR_SQL = """
SELECT
  party.agreement_party_id, party.party_ordinal, party.party_role,
  party.actor_kind, party.source_label, party.source_identifier,
  party.source_identifier_scheme, party.role_title_source,
  party.identity_state, party.resolution_method, party.resolution_confidence,
  party.source_id, agreement.agreement_id, agreement.source_record_id,
  agreement.source_snapshot_date, agreement.source_url,
  agreement.content_sha256 AS source_content_sha256,
  agreement.agreement_kind, agreement.agreement_status,
  agreement.adopted_on, agreement.effective_from, agreement.effective_to,
  agreement.observed_at, agreement.title
FROM agreement_parties AS party
JOIN agreements AS agreement ON agreement.agreement_id = party.agreement_id
ORDER BY party.source_id, party.agreement_party_id
"""

MEETING_ACTOR_SQL = """
SELECT
  participant.meeting_participant_id, participant.participant_ordinal,
  participant.actor_role, participant.attendance_claim_state,
  participant.actor_kind, participant.source_label,
  participant.source_identifier, participant.source_identifier_scheme,
  participant.role_title_source, participant.represented_organization_source,
  participant.identity_state, participant.resolution_method,
  participant.resolution_confidence, participant.source_id,
  meeting.meeting_id, meeting.source_record_id, meeting.source_snapshot_date,
  meeting.source_url, meeting.content_sha256 AS source_content_sha256,
  meeting.meeting_kind, meeting.scheduled_state,
  meeting.attendance_disclosure_state, meeting.event_date,
  meeting.observed_at, meeting.title
FROM meeting_participants AS participant
JOIN accountability_meetings AS meeting ON meeting.meeting_id = participant.meeting_id
ORDER BY participant.source_id, participant.meeting_participant_id
"""

GEOPOLITICS_ACTOR_SQL = """
SELECT
  actor.geopolitical_action_actor_id, actor.actor_ordinal, actor.actor_role,
  actor.actor_kind, actor.source_label, actor.source_identifier,
  actor.source_identifier_scheme, actor.jurisdiction_code,
  actor.identity_state, actor.resolution_method, actor.resolution_confidence,
  actor.source_id, action.geopolitical_action_id, action.source_record_id,
  action.source_snapshot_date, action.source_url,
  action.content_sha256 AS source_content_sha256,
  action.action_kind, action.action_status, action.procedure_stage,
  action.action_date, action.valid_from, action.valid_to,
  action.observed_at, action.title
FROM geopolitical_action_actors AS actor
JOIN geopolitical_actions AS action
  ON action.geopolitical_action_id = actor.geopolitical_action_id
ORDER BY actor.source_id, actor.geopolitical_action_actor_id
"""

MANIFESTO_ACTOR_SQL = """
SELECT
  document.manifesto_document_id, document.source_id,
  document.source_record_pk, document.document_kind, document.title,
  document.election_key, document.jurisdiction, document.published_date,
  document.snapshot_date, document.source_url,
  document.content_sha256 AS source_content_sha256,
  party.party_id, party.name AS party_name, party.acronym AS party_acronym,
  sr.source_record_id
FROM manifesto_documents AS document
JOIN parties AS party ON party.party_id = document.party_id
LEFT JOIN source_records AS sr ON sr.source_record_pk = document.source_record_pk
ORDER BY document.source_id, document.manifesto_document_id
"""


INPUT_QUERIES = (
    ("main", "mandates", MANDATE_SQL),
    ("main", "boe_candidates", BOE_CANDIDATE_SQL),
    ("main", "boe_effective_candidates", BOE_EFFECTIVE_SQL),
    ("main", "infoelectoral_elected", ELECTED_SQL),
    ("main", "parliamentary_memberships", PARLIAMENTARY_MEMBERSHIP_SQL),
    ("main", "organization_memberships", ORG_MEMBERSHIP_SQL),
    ("main", "person_identifiers", PERSON_IDENTIFIER_SQL),
    ("main", "person_aliases", PERSON_ALIAS_SQL),
    ("main", "party_aliases", PARTY_ALIAS_SQL),
    ("spending", "spending_actors", SPENDING_ACTOR_SQL),
    ("agreements", "agreement_actors", AGREEMENT_ACTOR_SQL),
    ("agreements", "meeting_actors", MEETING_ACTOR_SQL),
    ("geopolitics", "geopolitics_actors", GEOPOLITICS_ACTOR_SQL),
    ("promises", "manifesto_publishers", MANIFESTO_ACTOR_SQL),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="etl/data/staging/politicos-es.db")
    parser.add_argument("--spending-db", default="etl/data/staging/spending-placsp-mvp.db")
    parser.add_argument("--agreements-db", default="etl/data/staging/agreements-moncloa-mvp.db")
    parser.add_argument("--geopolitics-db", default="etl/data/staging/geopolitics-moncloa-mvp.db")
    parser.add_argument("--promises-db", default="etl/data/staging/promises-bng-2023.db")
    parser.add_argument("--schema", default="etl/load/sqlite_schema.sql")
    parser.add_argument(
        "--actor-manifest",
        default="etl/data/published/actor-mandate-semantic-partition-manifest-latest.json",
    )
    parser.add_argument(
        "--input-artifact",
        action="append",
        default=[
            "etl/data/published/promises-bng-2023.json",
            "etl/data/published/spending-placsp-sample.json",
            "etl/data/published/agreements-moncloa-sample.json",
            "etl/data/published/geopolitics-moncloa-sample.json",
            "etl/data/published/indicators-eurostat-gdp-es.json",
        ],
    )
    parser.add_argument("--snapshot-date", default=DEFAULT_SNAPSHOT_DATE)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--out-db", default="etl/data/staging/actor-graph-v1.db")
    parser.add_argument("--published-out", default="etl/data/published/actor-graph-v1.json")
    parser.add_argument("--public-out", default="ui/gh-pages-next/public/actor-graph/data/graph.json")
    parser.add_argument(
        "--report-out",
        default="docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-materialization.json",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(kind: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part if part is not None else "") for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"urn:vclc:{kind}:{digest}"


def normalized_label(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).split())


def connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def iter_rows(connection: sqlite3.Connection, sql: str) -> Iterator[dict[str, Any]]:
    for row in connection.execute(sql):
        yield dict(row)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_row_payload(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {column: row[column] for column in SOURCE_COLUMNS}


def build_source_mapping_plan(
    connections: dict[str, sqlite3.Connection],
) -> dict[str, Any]:
    definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata_by_origin: dict[tuple[str, str], dict[str, Any]] = {}
    select_sql = f"SELECT {', '.join(SOURCE_COLUMNS)} FROM sources ORDER BY source_id"
    for database_key in sorted(connections):
        for row in connections[database_key].execute(select_sql):
            metadata = source_row_payload(row)
            metadata_only = {
                column: metadata[column] for column in SOURCE_METADATA_COLUMNS
            }
            metadata_sha256 = hashlib.sha256(
                canonical_json(metadata_only).encode("utf-8")
            ).hexdigest()
            origin_key = (database_key, str(metadata["source_id"]))
            metadata_by_origin[origin_key] = metadata_only
            definitions[str(metadata["source_id"])].append(
                {
                    "input_database_key": database_key,
                    "upstream_source_id": str(metadata["source_id"]),
                    "source_metadata_sha256": metadata_sha256,
                    "metadata": metadata,
                }
            )

    mapping: dict[tuple[str, str], str] = {}
    mapping_rows: list[dict[str, Any]] = []
    source_rows: dict[str, dict[str, Any]] = {}
    source_upstream_ids: dict[str, str] = {}
    conflicting_upstream_ids: list[str] = []
    for upstream_source_id in sorted(definitions):
        entries = sorted(
            definitions[upstream_source_id],
            key=lambda entry: entry["input_database_key"],
        )
        metadata_hashes = {
            str(entry["source_metadata_sha256"]) for entry in entries
        }
        conflict = len(metadata_hashes) > 1
        if conflict:
            conflicting_upstream_ids.append(upstream_source_id)
        for entry in entries:
            database_key = str(entry["input_database_key"])
            graph_source_id = (
                f"{upstream_source_id}@{database_key}"
                if conflict
                else upstream_source_id
            )
            if conflict:
                mapping_reason = "metadata_conflict_namespaced"
            elif len(entries) > 1:
                mapping_reason = "identical_metadata"
            else:
                mapping_reason = "unique_upstream_id"
            mapping[(database_key, upstream_source_id)] = graph_source_id
            graph_metadata = dict(entry["metadata"])
            graph_metadata["source_id"] = graph_source_id
            previous = source_rows.get(graph_source_id)
            previous_upstream_id = source_upstream_ids.get(graph_source_id)
            if previous_upstream_id not in (None, upstream_source_id):
                raise RuntimeError(
                    "namespaced graph source id collides with an upstream id: "
                    f"{graph_source_id}"
                )
            if previous is not None and previous != graph_metadata:
                raise RuntimeError(
                    "deterministic graph source id collision: "
                    f"{graph_source_id}"
                )
            source_rows[graph_source_id] = graph_metadata
            source_upstream_ids[graph_source_id] = upstream_source_id
            mapping_rows.append(
                {
                    "input_database_key": database_key,
                    "upstream_source_id": upstream_source_id,
                    "graph_source_id": graph_source_id,
                    "source_metadata_sha256": entry["source_metadata_sha256"],
                    "mapping_reason": mapping_reason,
                }
            )

    mapping_rows.sort(
        key=lambda row: (
            row["upstream_source_id"],
            row["input_database_key"],
        )
    )
    semantic_payload = [
        {
            **row,
            "metadata": metadata_by_origin[
                (row["input_database_key"], row["upstream_source_id"])
            ],
        }
        for row in mapping_rows
    ]
    summary = {
        "mapping_rows": len(mapping_rows),
        "upstream_source_ids": len(definitions),
        "graph_source_ids": len(source_rows),
        "conflicting_upstream_source_ids": len(conflicting_upstream_ids),
        "namespaced_mapping_rows": sum(
            1
            for row in mapping_rows
            if row["mapping_reason"] == "metadata_conflict_namespaced"
        ),
        "identical_metadata_mapping_rows": sum(
            1
            for row in mapping_rows
            if row["mapping_reason"] == "identical_metadata"
        ),
        "unique_mapping_rows": sum(
            1
            for row in mapping_rows
            if row["mapping_reason"] == "unique_upstream_id"
        ),
    }
    return {
        "mapping": mapping,
        "mapping_rows": mapping_rows,
        "source_rows": source_rows,
        "conflicting_upstream_ids": conflicting_upstream_ids,
        "summary": summary,
        "semantic_sha256": hashlib.sha256(
            canonical_json(semantic_payload).encode("utf-8")
        ).hexdigest(),
    }


def mapped_source_id(
    plan: dict[str, Any], database_key: str, upstream_source_id: Any
) -> str:
    key = (database_key, str(upstream_source_id))
    try:
        return str(plan["mapping"][key])
    except KeyError as exc:
        raise RuntimeError(
            "source has no deterministic graph mapping: "
            f"database={database_key} upstream_source_id={upstream_source_id}"
        ) from exc


def drop_actor_graph_secondary_indexes(connection: sqlite3.Connection) -> None:
    for index_name in ACTOR_GRAPH_SECONDARY_INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {index_name}")


def create_actor_graph_secondary_indexes(connection: sqlite3.Connection) -> None:
    for sql in ACTOR_GRAPH_SECONDARY_INDEXES.values():
        connection.execute(sql)


def sibling_temp_path(final_path: Path) -> Path:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{final_path.name}.",
        suffix=".tmp",
        dir=final_path.parent,
    )
    os.fchmod(file_descriptor, 0o644)
    os.close(file_descriptor)
    return Path(temp_name)


def input_semantic_digest(
    connections: dict[str, sqlite3.Connection],
) -> tuple[str, dict[str, int]]:
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    for database_key, category, sql in INPUT_QUERIES:
        digest.update(f"{database_key}:{category}\n".encode())
        count = 0
        for row in iter_rows(connections[database_key], sql):
            digest.update(canonical_json(row).encode("utf-8"))
            digest.update(b"\n")
            count += 1
        counts[category] = count
    return digest.hexdigest(), counts


def provenance_state(record_id: Any, content_sha256: Any, source_url: Any) -> str:
    if record_id and content_sha256:
        return "exact_record"
    if content_sha256 and source_url:
        return "exact_document"
    if source_url:
        return "source_default"
    return "missing"


def actor_kind_from_source(value: str) -> tuple[str, str]:
    value = (value or "unknown").strip().lower()
    if value == "person":
        return "person", "person"
    if value in {"public_body", "organization", "legal_entity"}:
        return "organization", value
    if value in {"state", "territory", "international_organization"}:
        return "organization", value
    if value == "collective":
        return "collective", "collective"
    return "unknown", "unknown"


class GraphWriter:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        release_id: str,
        snapshot_date: str,
        generated_at: str,
        source_mapping_plan: dict[str, Any],
    ) -> None:
        self.connection = connection
        self.release_id = release_id
        self.snapshot_date = snapshot_date
        self.generated_at = generated_at
        self.source_mapping_plan = source_mapping_plan
        self.actor_ids: set[str] = set()
        self.actor_labels: dict[str, set[str]] = defaultdict(set)
        self.counts: Counter[str] = Counter()
        self.relationship_types: Counter[str] = Counter()
        self.sources: Counter[str] = Counter()

    def source_id(self, database_key: str, upstream_source_id: Any) -> str:
        return mapped_source_id(
            self.source_mapping_plan,
            database_key,
            upstream_source_id,
        )

    def ensure_actor(
        self,
        *,
        source_id: str,
        actor_kind: str,
        actor_subtype: str,
        stable_source_key: str,
        label: str,
        observed_at: str | None,
        source_record_id: str | None = None,
        source_url: str | None = None,
        source_content_sha256: str | None = None,
        attributes: dict[str, Any] | None = None,
        resolution_method: str = "source_partition_no_cross_source_merge",
    ) -> str:
        if not source_id or not stable_source_key or not label:
            raise ValueError("actor requires source_id, stable_source_key, and label")
        actor_id = stable_id("actor", actor_kind, source_id, stable_source_key)
        observed = observed_at or self.snapshot_date
        if actor_id not in self.actor_ids:
            self.connection.execute(
                """
                INSERT INTO actor_graph_nodes(
                  actor_id, actor_kind, actor_subtype, identity_scope,
                  source_scope_id, stable_source_key, first_release_id, created_at
                ) VALUES (?, ?, ?, 'source_scoped', ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    actor_kind,
                    actor_subtype,
                    source_id,
                    stable_source_key,
                    self.release_id,
                    self.generated_at,
                ),
            )
            node_version_id = stable_id("actor-version", actor_id, self.release_id)
            state = provenance_state(source_record_id, source_content_sha256, source_url)
            self.connection.execute(
                """
                INSERT INTO actor_graph_node_versions(
                  node_version_id, actor_id, release_id, canonical_label,
                  normalized_label, identity_state, valid_from, valid_to,
                  observed_at, source_id, source_record_id, source_url,
                  source_content_sha256, provenance_state, attributes_json,
                  created_at
                ) VALUES (?, ?, ?, ?, ?, 'source_scoped', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_version_id,
                    actor_id,
                    self.release_id,
                    label,
                    normalized_label(label),
                    None,
                    None,
                    observed,
                    source_id,
                    source_record_id,
                    source_url,
                    source_content_sha256,
                    state,
                    canonical_json(attributes or {}),
                    self.generated_at,
                ),
            )
            decision_id = stable_id("resolution-decision", actor_id, self.release_id)
            self.connection.execute(
                """
                INSERT INTO actor_resolution_decisions(
                  resolution_decision_id, release_id, source_actor_id,
                  candidate_actor_id, outcome, method, confidence,
                  decided_by_kind, decided_by, observed_at, valid_from, valid_to,
                  rationale, created_at
                ) VALUES (?, ?, ?, NULL, 'source_scoped', ?, 'not_scored',
                  'system_exact', ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    self.release_id,
                    actor_id,
                    resolution_method,
                    EXTRACTOR_VERSION,
                    observed,
                    None,
                    None,
                    "No cross-source merge asserted; official occurrence remains source-scoped.",
                    self.generated_at,
                ),
            )
            resolution_evidence_id = stable_id(
                "resolution-evidence", decision_id, source_id, source_record_id or stable_source_key
            )
            self.connection.execute(
                """
                INSERT INTO actor_resolution_evidence(
                  resolution_evidence_id, resolution_decision_id, source_id,
                  source_record_id, source_url, source_content_sha256,
                  source_locator, observed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolution_evidence_id,
                    decision_id,
                    source_id,
                    source_record_id,
                    source_url,
                    source_content_sha256,
                    f"actor-source-key:{stable_source_key}",
                    observed,
                    self.generated_at,
                ),
            )
            self.actor_ids.add(actor_id)
            self.counts[f"actor_kind:{actor_kind}"] += 1
            self.counts[f"actor_subtype:{actor_subtype}"] += 1
            self.sources[source_id] += 1

        if label not in self.actor_labels[actor_id]:
            if self.actor_labels[actor_id]:
                self.add_alias(
                    actor_id=actor_id,
                    source_id=source_id,
                    alias=label,
                    canonical_alias=normalized_label(label),
                    observed_at=observed,
                    source_record_id=source_record_id,
                    source_url=source_url,
                    source_content_sha256=source_content_sha256,
                    provenance=provenance_state(
                        source_record_id, source_content_sha256, source_url
                    ),
                )
            self.actor_labels[actor_id].add(label)
        return actor_id

    def add_identifier(
        self,
        *,
        actor_id: str,
        source_id: str,
        namespace: str,
        value: str,
        observed_at: str,
        source_url: str | None,
        source_content_sha256: str | None = None,
        provenance: str = "normalized_registry",
    ) -> None:
        identifier_id = stable_id(
            "actor-identifier", actor_id, self.release_id, namespace, value
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO actor_graph_identifier_versions(
              identifier_version_id, actor_id, release_id, namespace, value,
              observed_at, source_id, source_url, source_content_sha256,
              provenance_state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier_id,
                actor_id,
                self.release_id,
                namespace,
                value,
                observed_at,
                source_id,
                source_url,
                source_content_sha256,
                provenance,
                self.generated_at,
            ),
        )

    def add_alias(
        self,
        *,
        actor_id: str,
        source_id: str,
        alias: str,
        canonical_alias: str,
        observed_at: str,
        source_record_id: str | None,
        source_url: str | None,
        source_content_sha256: str | None,
        provenance: str,
    ) -> None:
        alias_id = stable_id(
            "actor-alias", actor_id, self.release_id, canonical_alias, alias
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO actor_graph_alias_versions(
              alias_version_id, actor_id, release_id, alias, normalized_alias,
              observed_at, source_id, source_record_id, source_url,
              source_content_sha256, provenance_state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alias_id,
                actor_id,
                self.release_id,
                alias,
                canonical_alias,
                observed_at,
                source_id,
                source_record_id,
                source_url,
                source_content_sha256,
                provenance,
                self.generated_at,
            ),
        )

    def add_relationship(
        self,
        *,
        subject_actor_id: str,
        relationship_type: str,
        object_actor_id: str | None,
        context_kind: str,
        context_id: str,
        role_label: str | None,
        valid_from: str | None,
        valid_to: str | None,
        observed_at: str | None,
        is_present: int,
        source_id: str,
        source_record_id: str | None,
        source_url: str | None,
        source_content_sha256: str | None,
        source_locator: str,
        exact_quote: str | None = None,
        attributes: dict[str, Any] | None = None,
        resolution_state: str = "source_scoped",
        evidence_kind: str | None = None,
    ) -> None:
        relationship_id = stable_id(
            "actor-relationship",
            source_id,
            subject_actor_id,
            relationship_type,
            object_actor_id,
            context_kind,
            context_id,
        )
        version_id = stable_id(
            "actor-relationship-version", relationship_id, self.release_id
        )
        observed = observed_at or self.snapshot_date
        self.connection.execute(
            """
            INSERT INTO actor_graph_relationships(
              relationship_id, subject_actor_id, relationship_type,
              object_actor_id, context_kind, context_id,
              created_release_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relationship_id,
                subject_actor_id,
                relationship_type,
                object_actor_id,
                context_kind,
                context_id,
                self.release_id,
                self.generated_at,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO actor_graph_relationship_versions(
              relationship_version_id, relationship_id, release_id, role_label,
              valid_from, valid_to, observed_at, is_present, resolution_state,
              source_id, source_record_id, source_url, source_content_sha256,
              attributes_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                relationship_id,
                self.release_id,
                role_label,
                valid_from,
                valid_to,
                observed,
                is_present,
                resolution_state,
                source_id,
                source_record_id,
                source_url,
                source_content_sha256,
                canonical_json(attributes or {}),
                self.generated_at,
            ),
        )
        evidence_id = stable_id(
            "actor-relationship-evidence", version_id, source_locator
        )
        kind = evidence_kind or provenance_state(
            source_record_id, source_content_sha256, source_url
        )
        self.connection.execute(
            """
            INSERT INTO actor_graph_relationship_evidence(
              relationship_evidence_id, relationship_version_id, evidence_kind,
              source_id, source_record_id, source_url, source_content_sha256,
              source_locator, exact_quote, observed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                version_id,
                kind,
                source_id,
                source_record_id,
                source_url,
                source_content_sha256,
                source_locator,
                exact_quote,
                observed,
                self.generated_at,
            ),
        )
        self.relationship_types[relationship_type] += 1


def materialize_source_mapping(
    out: sqlite3.Connection,
    *,
    plan: dict[str, Any],
    release_id: str,
    created_at: str,
) -> None:
    for graph_source_id in sorted(plan["source_rows"]):
        metadata = plan["source_rows"][graph_source_id]
        out.execute(
            """
            INSERT INTO sources(
              source_id, name, scope, default_url, data_format,
              is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(metadata[column] for column in SOURCE_COLUMNS),
        )
    for row in plan["mapping_rows"]:
        mapping_id = stable_id(
            "actor-source-mapping",
            release_id,
            row["input_database_key"],
            row["upstream_source_id"],
        )
        out.execute(
            """
            INSERT INTO actor_graph_source_mappings(
              source_mapping_id, release_id, input_database_key,
              upstream_source_id, graph_source_id, source_metadata_sha256,
              mapping_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping_id,
                release_id,
                row["input_database_key"],
                row["upstream_source_id"],
                row["graph_source_id"],
                row["source_metadata_sha256"],
                row["mapping_reason"],
                created_at,
            ),
        )


def party_actor(
    writer: GraphWriter,
    row: dict[str, Any],
    *,
    source_id: str,
    observed_at: str | None,
    source_record_id: str | None,
    source_url: str | None,
    source_content_sha256: str | None,
) -> str:
    return writer.ensure_actor(
        source_id=source_id,
        actor_kind="organization",
        actor_subtype="party",
        stable_source_key=str(row["party_name"]),
        label=str(row["party_name"]),
        observed_at=observed_at,
        source_record_id=source_record_id,
        source_url=source_url,
        source_content_sha256=source_content_sha256,
        attributes={
            "acronym": row.get("party_acronym"),
            "legacy_party_id": row.get("party_id"),
        },
    )


def person_actor(
    writer: GraphWriter,
    row: dict[str, Any],
    *,
    source_id: str,
    observed_at: str | None,
    source_record_id: str | None,
    source_url: str | None,
    source_content_sha256: str | None,
) -> str:
    return writer.ensure_actor(
        source_id=source_id,
        actor_kind="person",
        actor_subtype="person_registry",
        stable_source_key=str(row["person_key"]),
        label=str(row["full_name"]),
        observed_at=observed_at,
        source_record_id=source_record_id,
        source_url=source_url,
        source_content_sha256=source_content_sha256,
        attributes={"legacy_person_id": row.get("person_id")},
    )


def institution_actor(
    writer: GraphWriter,
    row: dict[str, Any],
    *,
    source_id: str,
    observed_at: str | None,
    source_record_id: str | None,
    source_url: str | None,
    source_content_sha256: str | None,
) -> str:
    stable_key = "|".join(
        [
            str(row.get("institution_level") or ""),
            str(row.get("institution_territory_code") or ""),
            str(row["institution_name"]),
        ]
    )
    return writer.ensure_actor(
        source_id=source_id,
        actor_kind="organization",
        actor_subtype="institution",
        stable_source_key=stable_key,
        label=str(row["institution_name"]),
        observed_at=observed_at,
        source_record_id=source_record_id,
        source_url=source_url,
        source_content_sha256=source_content_sha256,
        attributes={
            "level": row.get("institution_level"),
            "territory_code": row.get("institution_territory_code"),
            "legacy_institution_id": row.get("institution_id"),
        },
    )


def materialize_main(writer: GraphWriter, connection: sqlite3.Connection) -> None:
    for row in iter_rows(connection, MANDATE_SQL):
        source_id = writer.source_id("main", row["source_id"])
        observed = row["source_snapshot_date"] or row["last_seen_at"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        institution = institution_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        context_id = f"{source_id}:{row['source_record_id']}"
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="holds_role_at",
            object_actor_id=institution,
            context_kind="mandate",
            context_id=context_id,
            role_label=row["role_title"],
            valid_from=row["start_date"],
            valid_to=row["end_date"],
            observed_at=observed,
            is_present=int(row["is_active"]),
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"mandates:{row['mandate_id']}",
            attributes={
                "level": row["level"],
                "territory_code": row["territory_code"],
                "role_code": row["role_code"],
                "legacy_mandate_id": row["mandate_id"],
            },
        )
        if row["party_id"] is not None:
            party = party_actor(
                writer,
                row,
                source_id=source_id,
                observed_at=observed,
                source_record_id=row["source_record_id"],
                source_url=row["source_url"],
                source_content_sha256=row["source_content_sha256"],
            )
            writer.add_relationship(
                subject_actor_id=person,
                relationship_type="affiliated_with_party",
                object_actor_id=party,
                context_kind="mandate",
                context_id=context_id,
                role_label="mandate_party",
                valid_from=row["start_date"],
                valid_to=row["end_date"],
                observed_at=observed,
                is_present=int(row["is_active"]),
                source_id=source_id,
                source_record_id=row["source_record_id"],
                source_url=row["source_url"],
                source_content_sha256=row["source_content_sha256"],
                source_locator=f"mandates:{row['mandate_id']}:party",
            )

    for row in iter_rows(connection, BOE_CANDIDATE_SQL):
        source_id = writer.source_id("main", row["source_id"])
        observed = row["last_seen_snapshot_date"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        party = party_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="candidate_for",
            object_actor_id=party,
            context_kind="candidate_occurrence",
            context_id=row["candidate_occurrence_id"],
            role_label=row["candidate_type_code"],
            valid_from=row["election_date"],
            valid_to=row["election_date"],
            observed_at=observed,
            is_present=int(row["is_present"]),
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=(
                f"boe_election_candidate_occurrences:{row['candidate_occurrence_id']}:"
                f"paragraph:{row['source_paragraph_number']}"
            ),
            exact_quote=row["source_text_exact"],
            attributes={
                "candidacy_id": row["candidacy_id"],
                "election_id": row["election_id"],
                "electoral_district": row["electoral_district"],
                "chamber_code": row["chamber_code"],
                "candidate_order": row["candidate_order"],
            },
            evidence_kind="exact_document",
        )

    for row in iter_rows(connection, BOE_EFFECTIVE_SQL):
        source_id = writer.source_id("main", row["source_id"])
        observed = row["last_seen_snapshot_date"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        party = party_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="effective_candidate_for",
            object_actor_id=party,
            context_kind="effective_candidate_occurrence",
            context_id=row["effective_candidate_occurrence_id"],
            role_label=row["candidate_type_code"],
            valid_from=row["election_date"],
            valid_to=row["election_date"],
            observed_at=observed,
            is_present=int(row["is_present"]),
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=(
                "boe_election_effective_candidate_occurrences:"
                f"{row['effective_candidate_occurrence_id']}:"
                f"paragraph:{row['source_paragraph_number']}"
            ),
            exact_quote=row["source_text_exact"],
            attributes={
                "base_candidate_occurrence_id": row["base_candidate_occurrence_id"],
                "correction_operation_id": row["correction_operation_id"],
                "candidacy_id": row["candidacy_id"],
            },
            evidence_kind="exact_document",
        )

    for row in iter_rows(connection, ELECTED_SQL):
        source_id = writer.source_id("main", row["source_id"])
        observed = row["last_seen_snapshot_date"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=observed,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        institution = None
        if row["institution_id"] is not None:
            institution = institution_actor(
                writer,
                row,
                source_id=source_id,
                observed_at=observed,
                source_record_id=row["source_record_id"],
                source_url=row["source_url"],
                source_content_sha256=row["source_content_sha256"],
            )
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="elected_in",
            object_actor_id=institution,
            context_kind="election_result",
            context_id=row["elected_official_id"],
            role_label=row["chamber"],
            valid_from=row["election_date"],
            valid_to=None,
            observed_at=observed,
            is_present=int(row["is_present"]),
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=(
                f"infoelectoral_elected_officials:{row['elected_official_id']}:"
                f"row:{row['source_row_number']}"
            ),
            attributes={
                "election_code": row["election_code"],
                "province_code": row["province_code"],
                "candidacy_name": row["candidacy_name"],
                "votes": row["votes"],
            },
            evidence_kind="exact_document",
        )

    for row in iter_rows(connection, PARLIAMENTARY_MEMBERSHIP_SQL):
        source_id = writer.source_id("main", row["source_id"])
        source_url = row["source_url"] or row["source_default_url"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=writer.snapshot_date,
            source_record_id=None,
            source_url=source_url,
            source_content_sha256=None,
        )
        group = writer.ensure_actor(
            source_id=writer.source_id("main", row["group_source_id"]),
            actor_kind="organization",
            actor_subtype="parliamentary_group",
            stable_source_key=(
                f"{row['group_legislature'] or ''}|{row['group_code']}"
            ),
            label=row["group_name"],
            observed_at=writer.snapshot_date,
            source_url=source_url,
            attributes={
                "legislature": row["group_legislature"],
                "group_code": row["group_code"],
                "legacy_parliamentary_group_id": row["parliamentary_group_id"],
            },
        )
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="member_of_parliamentary_group",
            object_actor_id=group,
            context_kind="parliamentary_group_membership",
            context_id=f"{source_id}:{row['membership_id']}",
            role_label="member",
            valid_from=row["start_date"],
            valid_to=row["end_date"],
            observed_at=writer.snapshot_date,
            is_present=1,
            source_id=source_id,
            source_record_id=None,
            source_url=source_url,
            source_content_sha256=None,
            source_locator=f"person_parliamentary_group_memberships:{row['membership_id']}",
            exact_quote=row["evidence_quote"],
        )

    for row in iter_rows(connection, ORG_MEMBERSHIP_SQL):
        source_id = writer.source_id("main", row["source_id"])
        source_url = row["source_url"] or row["source_default_url"]
        person = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=row["evidence_date"] or writer.snapshot_date,
            source_record_id=row["source_record_id"],
            source_url=source_url,
            source_content_sha256=row["source_content_sha256"],
        )
        object_actor = None
        if row["party_id"] is not None:
            object_actor = party_actor(
                writer,
                row,
                source_id=source_id,
                observed_at=row["evidence_date"] or writer.snapshot_date,
                source_record_id=row["source_record_id"],
                source_url=source_url,
                source_content_sha256=row["source_content_sha256"],
            )
        elif row["position_id"] is not None:
            key = row["position_code"] or f"position:{row['position_id']}"
            object_actor = writer.ensure_actor(
                source_id=source_id,
                actor_kind="office",
                actor_subtype="government_position",
                stable_source_key=key,
                label=row["position_title"],
                observed_at=row["evidence_date"] or writer.snapshot_date,
                source_record_id=row["source_record_id"],
                source_url=source_url,
                source_content_sha256=row["source_content_sha256"],
                attributes={"legacy_position_id": row["position_id"]},
            )
        writer.add_relationship(
            subject_actor_id=person,
            relationship_type="member_of_organization",
            object_actor_id=object_actor,
            context_kind="organization_membership",
            context_id=f"{source_id}:{row['membership_id']}",
            role_label=row["role_label"] or row["membership_kind"],
            valid_from=row["start_date"],
            valid_to=row["end_date"],
            observed_at=row["evidence_date"] or writer.snapshot_date,
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=source_url,
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"person_org_memberships:{row['membership_id']}",
            exact_quote=row["evidence_quote"],
            attributes={"membership_kind": row["membership_kind"]},
        )

    for row in iter_rows(connection, PERSON_IDENTIFIER_SQL):
        source_id = writer.source_id("main", row["source_id"])
        actor = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=writer.snapshot_date,
            source_record_id=None,
            source_url=row["source_url"],
            source_content_sha256=None,
        )
        writer.add_identifier(
            actor_id=actor,
            source_id=source_id,
            namespace=row["namespace"],
            value=row["value"],
            observed_at=writer.snapshot_date,
            source_url=row["source_url"],
        )

    for row in iter_rows(connection, PERSON_ALIAS_SQL):
        source_id = writer.source_id("main", row["source_id"])
        source_url = row["source_url"] or row["source_default_url"]
        actor = person_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=row["evidence_date"] or writer.snapshot_date,
            source_record_id=row["source_record_id"],
            source_url=source_url,
            source_content_sha256=row["source_content_sha256"],
        )
        writer.add_alias(
            actor_id=actor,
            source_id=source_id,
            alias=row["alias"],
            canonical_alias=row["canonical_alias"],
            observed_at=row["evidence_date"] or writer.snapshot_date,
            source_record_id=row["source_record_id"],
            source_url=source_url,
            source_content_sha256=row["source_content_sha256"],
            provenance=(
                provenance_state(
                    row["source_record_id"],
                    row["source_content_sha256"],
                    source_url,
                )
                if row["source_record_id"]
                else "normalized_registry"
            ),
        )

    for row in iter_rows(connection, PARTY_ALIAS_SQL):
        source_id = writer.source_id("main", row["source_id"])
        actor = party_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=writer.snapshot_date,
            source_record_id=None,
            source_url=row["source_url"],
            source_content_sha256=None,
        )
        writer.add_alias(
            actor_id=actor,
            source_id=source_id,
            alias=row["alias"],
            canonical_alias=row["canonical_alias"],
            observed_at=writer.snapshot_date,
            source_record_id=None,
            source_url=row["source_url"],
            source_content_sha256=None,
            provenance="normalized_registry",
        )


def contextual_actor_key(row: dict[str, Any], row_id: str) -> tuple[str, str]:
    if row.get("source_identifier") and row.get("source_identifier_scheme"):
        return (
            f"{row['source_identifier_scheme']}:{row['source_identifier']}",
            "exact_official_identifier_within_source",
        )
    return row_id, "source_occurrence_no_identifier"


def materialize_spending(writer: GraphWriter, connection: sqlite3.Connection) -> None:
    for row in iter_rows(connection, SPENDING_ACTOR_SQL):
        source_id = writer.source_id("spending", row["source_id"])
        key, method = contextual_actor_key(row, row["spending_item_actor_id"])
        kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = writer.ensure_actor(
            source_id=source_id,
            actor_kind=kind,
            actor_subtype=subtype,
            stable_source_key=key,
            label=row["source_label"],
            observed_at=row["source_snapshot_date"],
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            attributes={"source_actor_kind": row["actor_kind"]},
            resolution_method=method,
        )
        if row["source_identifier"]:
            writer.add_identifier(
                actor_id=actor,
                source_id=source_id,
                namespace=row["source_identifier_scheme"],
                value=row["source_identifier"],
                observed_at=row["source_snapshot_date"] or writer.snapshot_date,
                source_url=row["source_url"],
                source_content_sha256=row["source_content_sha256"],
                provenance="exact_record",
            )
        writer.add_relationship(
            subject_actor_id=actor,
            relationship_type="acts_in_spending_item",
            object_actor_id=None,
            context_kind="spending_item",
            context_id=row["spending_item_id"],
            role_label=row["actor_role"],
            valid_from=row["effective_from"] or row["decision_on"] or row["published_on"],
            valid_to=row["effective_to"],
            observed_at=row["source_snapshot_date"],
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"spending_item_actors:{row['spending_item_actor_id']}",
            attributes={
                "spending_kind": row["spending_kind"],
                "title": row["title"],
                "identity_state": row["identity_state"],
            },
        )


def materialize_agreements(writer: GraphWriter, connection: sqlite3.Connection) -> None:
    for row in iter_rows(connection, AGREEMENT_ACTOR_SQL):
        source_id = writer.source_id("agreements", row["source_id"])
        key, method = contextual_actor_key(row, row["agreement_party_id"])
        kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = writer.ensure_actor(
            source_id=source_id,
            actor_kind=kind,
            actor_subtype=subtype,
            stable_source_key=key,
            label=row["source_label"],
            observed_at=row["observed_at"],
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            resolution_method=method,
        )
        writer.add_relationship(
            subject_actor_id=actor,
            relationship_type="party_to_agreement",
            object_actor_id=None,
            context_kind="agreement",
            context_id=row["agreement_id"],
            role_label=row["party_role"],
            valid_from=row["effective_from"] or row["adopted_on"],
            valid_to=row["effective_to"],
            observed_at=row["observed_at"],
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"agreement_parties:{row['agreement_party_id']}",
            attributes={
                "agreement_kind": row["agreement_kind"],
                "agreement_status": row["agreement_status"],
                "title": row["title"],
                "role_title_source": row["role_title_source"],
            },
        )

    for row in iter_rows(connection, MEETING_ACTOR_SQL):
        source_id = writer.source_id("agreements", row["source_id"])
        key, method = contextual_actor_key(row, row["meeting_participant_id"])
        kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = writer.ensure_actor(
            source_id=source_id,
            actor_kind=kind,
            actor_subtype=subtype,
            stable_source_key=key,
            label=row["source_label"],
            observed_at=row["observed_at"],
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            resolution_method=method,
        )
        writer.add_relationship(
            subject_actor_id=actor,
            relationship_type="participates_in_meeting",
            object_actor_id=None,
            context_kind="meeting",
            context_id=row["meeting_id"],
            role_label=row["actor_role"],
            valid_from=row["event_date"],
            valid_to=row["event_date"],
            observed_at=row["observed_at"],
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"meeting_participants:{row['meeting_participant_id']}",
            attributes={
                "attendance_claim_state": row["attendance_claim_state"],
                "attendance_disclosure_state": row["attendance_disclosure_state"],
                "scheduled_state": row["scheduled_state"],
                "title": row["title"],
            },
        )


def materialize_geopolitics(writer: GraphWriter, connection: sqlite3.Connection) -> None:
    for row in iter_rows(connection, GEOPOLITICS_ACTOR_SQL):
        source_id = writer.source_id("geopolitics", row["source_id"])
        key, method = contextual_actor_key(row, row["geopolitical_action_actor_id"])
        kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = writer.ensure_actor(
            source_id=source_id,
            actor_kind=kind,
            actor_subtype=subtype,
            stable_source_key=key,
            label=row["source_label"],
            observed_at=row["observed_at"],
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            attributes={"jurisdiction_code": row["jurisdiction_code"]},
            resolution_method=method,
        )
        writer.add_relationship(
            subject_actor_id=actor,
            relationship_type="acts_in_geopolitical_action",
            object_actor_id=None,
            context_kind="geopolitical_action",
            context_id=row["geopolitical_action_id"],
            role_label=row["actor_role"],
            valid_from=row["valid_from"] or row["action_date"],
            valid_to=row["valid_to"],
            observed_at=row["observed_at"],
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=(
                f"geopolitical_action_actors:{row['geopolitical_action_actor_id']}"
            ),
            attributes={
                "action_kind": row["action_kind"],
                "action_status": row["action_status"],
                "procedure_stage": row["procedure_stage"],
                "title": row["title"],
            },
        )


def materialize_promises(writer: GraphWriter, connection: sqlite3.Connection) -> None:
    for row in iter_rows(connection, MANIFESTO_ACTOR_SQL):
        source_id = writer.source_id("promises", row["source_id"])
        actor = party_actor(
            writer,
            row,
            source_id=source_id,
            observed_at=row["snapshot_date"],
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
        )
        writer.add_relationship(
            subject_actor_id=actor,
            relationship_type="publishes_manifesto",
            object_actor_id=None,
            context_kind="manifesto_document",
            context_id=row["manifesto_document_id"],
            role_label="publishing_party",
            valid_from=row["published_date"],
            valid_to=None,
            observed_at=row["snapshot_date"],
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=row["source_url"],
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"manifesto_documents:{row['manifesto_document_id']}",
            attributes={
                "document_kind": row["document_kind"],
                "election_key": row["election_key"],
                "jurisdiction": row["jurisdiction"],
                "title": row["title"],
            },
            evidence_kind="exact_document",
        )


def database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "actor_graph_releases",
        "actor_graph_source_mappings",
        "actor_graph_nodes",
        "actor_graph_node_versions",
        "actor_graph_identifier_versions",
        "actor_graph_alias_versions",
        "actor_graph_relationships",
        "actor_graph_relationship_versions",
        "actor_graph_relationship_evidence",
        "actor_resolution_decisions",
        "actor_resolution_evidence",
        "actor_organization_change_events",
        "actor_organization_change_evidence",
    )
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def producer_semantic_checks(
    connection: sqlite3.Connection,
    *,
    source_mapping_plan: dict[str, Any],
    release_id: str,
) -> dict[str, Any]:
    node_contextual_validity_rows = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM actor_graph_node_versions
            WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL
            """
        ).fetchone()[0]
    )
    person_node_contextual_validity_rows = int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM actor_graph_node_versions AS version
            JOIN actor_graph_nodes AS node ON node.actor_id = version.actor_id
            WHERE node.actor_kind = 'person'
              AND (version.valid_from IS NOT NULL OR version.valid_to IS NOT NULL)
            """
        ).fetchone()[0]
    )
    resolution_contextual_validity_rows = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM actor_resolution_decisions
            WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL
            """
        ).fetchone()[0]
    )
    missing_graph_source_ids = [
        str(row[0])
        for row in connection.execute(
            """
            WITH graph_source_refs(source_id) AS (
              SELECT source_scope_id FROM actor_graph_nodes
              UNION SELECT source_id FROM actor_graph_node_versions
              UNION SELECT source_id FROM actor_graph_identifier_versions
              UNION SELECT source_id FROM actor_graph_alias_versions
              UNION SELECT source_id FROM actor_graph_relationship_versions
              UNION SELECT source_id FROM actor_graph_relationship_evidence
              UNION SELECT source_id FROM actor_resolution_evidence
              UNION SELECT source_id FROM actor_organization_change_events
              UNION SELECT graph_source_id FROM actor_graph_source_mappings
            )
            SELECT refs.source_id
            FROM graph_source_refs AS refs
            LEFT JOIN sources AS source ON source.source_id = refs.source_id
            WHERE source.source_id IS NULL
            ORDER BY refs.source_id
            """
        )
    ]

    expected_mappings = sorted(
        (
            release_id,
            row["input_database_key"],
            row["upstream_source_id"],
            row["graph_source_id"],
            row["source_metadata_sha256"],
            row["mapping_reason"],
        )
        for row in source_mapping_plan["mapping_rows"]
    )
    actual_mappings = sorted(
        tuple(row)
        for row in connection.execute(
            """
            SELECT release_id, input_database_key, upstream_source_id,
              graph_source_id, source_metadata_sha256, mapping_reason
            FROM actor_graph_source_mappings
            WHERE release_id = ?
            """,
            (release_id,),
        )
    )
    expected_sources = sorted(
        tuple(metadata[column] for column in SOURCE_COLUMNS)
        for metadata in source_mapping_plan["source_rows"].values()
    )
    actual_sources = sorted(
        tuple(row)
        for row in connection.execute(
            f"SELECT {', '.join(SOURCE_COLUMNS)} FROM sources"
        )
    )
    conflict_mapping_violations = int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM actor_graph_source_mappings
            WHERE release_id = ?
              AND (
                (
                  mapping_reason = 'metadata_conflict_namespaced'
                  AND graph_source_id <>
                    (upstream_source_id || '@' || input_database_key)
                )
                OR (
                  mapping_reason <> 'metadata_conflict_namespaced'
                  AND graph_source_id <> upstream_source_id
                )
              )
            """,
            (release_id,),
        ).fetchone()[0]
    )
    release_mapping_sha256 = str(
        connection.execute(
            """
            SELECT source_mapping_semantic_sha256
            FROM actor_graph_releases WHERE release_id = ?
            """,
            (release_id,),
        ).fetchone()[0]
    )
    checks = {
        "node_contextual_validity_rows": node_contextual_validity_rows,
        "person_node_contextual_validity_rows": (
            person_node_contextual_validity_rows
        ),
        "resolution_contextual_validity_rows": (
            resolution_contextual_validity_rows
        ),
        "missing_graph_source_ids": missing_graph_source_ids,
        "source_mapping_rows_expected": len(expected_mappings),
        "source_mapping_rows_actual": len(actual_mappings),
        "source_mapping_exact": actual_mappings == expected_mappings,
        "source_metadata_exact": actual_sources == expected_sources,
        "conflict_mapping_violations": conflict_mapping_violations,
        "source_mapping_release_digest_exact": (
            release_mapping_sha256 == source_mapping_plan["semantic_sha256"]
        ),
    }
    if (
        node_contextual_validity_rows
        or person_node_contextual_validity_rows
        or resolution_contextual_validity_rows
        or missing_graph_source_ids
        or actual_mappings != expected_mappings
        or actual_sources != expected_sources
        or conflict_mapping_violations
        or release_mapping_sha256 != source_mapping_plan["semantic_sha256"]
    ):
        raise RuntimeError(f"actor graph semantic checks failed: {checks}")
    return checks


def grouped_counts(connection: sqlite3.Connection, sql: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in connection.execute(sql)}


def public_payload(
    connection: sqlite3.Connection,
    *,
    release: dict[str, Any],
    counts: dict[str, int],
    input_counts: dict[str, int],
    source_mapping: dict[str, Any],
) -> dict[str, Any]:
    nodes = [
        dict(row)
        for row in connection.execute(
            """
            WITH ranked_ids AS (
              SELECT n.actor_id,
                ROW_NUMBER() OVER (
                  PARTITION BY n.actor_kind, n.actor_subtype
                  ORDER BY n.source_scope_id, v.canonical_label, n.actor_id
                ) AS rank_in_type
              FROM actor_graph_nodes AS n
              JOIN actor_graph_node_versions AS v ON v.actor_id = n.actor_id
              WHERE v.release_id = ?
            ), sample_ids AS (
              SELECT actor_id FROM ranked_ids WHERE rank_in_type <= 3
            )
            SELECT n.actor_id, n.actor_kind, n.actor_subtype, n.identity_scope,
              n.source_scope_id, v.canonical_label, v.identity_state,
              v.observed_at, v.source_url, v.provenance_state
            FROM sample_ids AS sample
            JOIN actor_graph_nodes AS n ON n.actor_id = sample.actor_id
            JOIN actor_graph_node_versions AS v ON v.actor_id = n.actor_id
            WHERE v.release_id = ?
            ORDER BY n.actor_kind, n.actor_subtype, n.source_scope_id,
              v.canonical_label
            """,
            (release["release_id"], release["release_id"]),
        )
    ]
    relationships = [
        dict(row)
        for row in connection.execute(
            """
            WITH ranked_ids AS (
              SELECT r.relationship_id, version.relationship_version_id,
                ROW_NUMBER() OVER (
                  PARTITION BY r.relationship_type
                  ORDER BY version.source_id, r.context_id, r.relationship_id
                ) AS rank_in_type
              FROM actor_graph_relationships AS r
              JOIN actor_graph_relationship_versions AS version
                ON version.relationship_id = r.relationship_id
              WHERE version.release_id = ?
            ), sample_ids AS (
              SELECT relationship_id, relationship_version_id
              FROM ranked_ids WHERE rank_in_type <= 3
            )
            SELECT r.relationship_id, r.relationship_type, r.context_kind,
              r.context_id, subject.canonical_label AS subject_label,
              object.canonical_label AS object_label,
              version.role_label, version.valid_from, version.valid_to,
              version.observed_at, version.is_present,
              version.resolution_state, version.source_id, version.source_url,
              evidence.evidence_kind, evidence.source_locator
            FROM sample_ids AS sample
            JOIN actor_graph_relationships AS r
              ON r.relationship_id = sample.relationship_id
            JOIN actor_graph_relationship_versions AS version
              ON version.relationship_version_id = sample.relationship_version_id
              JOIN actor_graph_node_versions AS subject
                ON subject.actor_id = r.subject_actor_id
                AND subject.release_id = version.release_id
              LEFT JOIN actor_graph_node_versions AS object
                ON object.actor_id = r.object_actor_id
                AND object.release_id = version.release_id
              JOIN actor_graph_relationship_evidence AS evidence
                ON evidence.relationship_version_id = version.relationship_version_id
                AND evidence.source_locator = (
                  SELECT MIN(candidate.source_locator)
                  FROM actor_graph_relationship_evidence AS candidate
                  WHERE candidate.relationship_version_id =
                    version.relationship_version_id
                )
            ORDER BY r.relationship_type, version.source_id, r.context_id
            """,
            (release["release_id"],),
        )
    ]
    return {
        "meta": {
            "schema_version": "actor_graph_public_v1",
            "release_id": release["release_id"],
            "snapshot_date": release["snapshot_date"],
            "generated_at": release["created_at"],
            "contract_version": release["contract_version"],
            "source_semantic_sha256": release["source_semantic_sha256"],
            "source_mapping_semantic_sha256": release[
                "source_mapping_semantic_sha256"
            ],
            "input_manifest_sha256": release["input_manifest_sha256"],
            "real_data_only": True,
            "synthetic_or_mock": False,
            "official_public_domain_information_retained": True,
        },
        "policy": {
            "default_identity_scope": "source_scoped",
            "name_only_cross_source_merge": "forbidden",
            "cross_source_merges_published": 0,
            "causal_inference_from_graph_path": "forbidden",
            "public_identity_redaction": "forbidden_for_official_public_fields",
            "unknown_dates_remain_unknown": True,
            "append_only_schema_ready": True,
            "operational_append_only_history": "not_yet_proven",
            "next_snapshot_versioning": "required_before_w3_006",
        },
        "coverage": {
            "database_counts": counts,
            "input_counts": input_counts,
            "source_mapping": source_mapping["summary"],
            "actors_by_kind": grouped_counts(
                connection,
                "SELECT actor_kind, COUNT(*) FROM actor_graph_nodes GROUP BY actor_kind ORDER BY actor_kind",
            ),
            "actors_by_subtype": grouped_counts(
                connection,
                "SELECT actor_subtype, COUNT(*) FROM actor_graph_nodes GROUP BY actor_subtype ORDER BY actor_subtype",
            ),
            "relationships_by_type": grouped_counts(
                connection,
                "SELECT relationship_type, COUNT(*) FROM actor_graph_relationships GROUP BY relationship_type ORDER BY relationship_type",
            ),
            "evidence_by_kind": grouped_counts(
                connection,
                "SELECT evidence_kind, COUNT(*) FROM actor_graph_relationship_evidence GROUP BY evidence_kind ORDER BY evidence_kind",
            ),
            "resolution_outcomes": grouped_counts(
                connection,
                "SELECT outcome, COUNT(*) FROM actor_resolution_decisions GROUP BY outcome ORDER BY outcome",
            ),
            "source_scopes": int(
                connection.execute(
                    "SELECT COUNT(DISTINCT source_scope_id) FROM actor_graph_nodes"
                ).fetchone()[0]
            ),
            "known_valid_from": int(
                connection.execute(
                    "SELECT COUNT(*) FROM actor_graph_relationship_versions WHERE valid_from IS NOT NULL AND valid_from <> ''"
                ).fetchone()[0]
            ),
            "known_valid_to": int(
                connection.execute(
                    "SELECT COUNT(*) FROM actor_graph_relationship_versions WHERE valid_to IS NOT NULL AND valid_to <> ''"
                ).fetchone()[0]
            ),
            "organization_change_events": 0,
            "cross_source_resolved_actors": 0,
        },
        "sample_contract": {
            "bounded": True,
            "selection": "first_three_per_actor_subtype_and_relationship_type_in_stable_order",
            "all_rows_materialized_in_sqlite": True,
            "full_graph_not_embedded_in_browser": True,
        },
        "sample_nodes": nodes,
        "sample_relationships": relationships,
        "limitations": [
            "Existing normalized identities are re-scoped by source and are not external identity adjudication.",
            "No name-only cross-source merge is published.",
            "No reviewed coalition, merger, split, rename, or succession event is present in this first release.",
            "An outcome indicator does not identify the actor responsible for that outcome.",
            "A graph path does not prove causation, influence, merit, blame, corruption, or wrongdoing.",
            "Full graph durable-origin publication, second-snapshot versioning, and identity precision/recall remain open.",
            "This standalone builder atomically replaces the current snapshot; operational append-only history is not yet proven.",
            "Relationship shell identity across multiple sources must be resolved before W3-006 cross-source actor merging.",
        ],
        "methodology": {
            "architecture": "docs/architecture/entity-resolution-v1.md",
            "core_ontology": "docs/data-model/core-ontology-v1.md",
            "evidence_sql": "docs/examples/actor-graph-evidence.sql",
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    path.write_bytes(encoded)
    return len(encoded), hashlib.sha256(encoded).hexdigest()


def main() -> int:
    args = parse_args()
    paths = {
        "main": Path(args.db),
        "spending": Path(args.spending_db),
        "agreements": Path(args.agreements_db),
        "geopolitics": Path(args.geopolitics_db),
        "promises": Path(args.promises_db),
    }
    required = [*paths.values(), Path(args.schema), Path(args.actor_manifest)]
    required.extend(Path(path) for path in args.input_artifact)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required real inputs: {missing}")

    connections = {key: connect_readonly(path) for key, path in paths.items()}
    temporary_paths: list[Path] = []
    out: sqlite3.Connection | None = None
    try:
        source_mapping_plan = build_source_mapping_plan(connections)
        semantic_sha256, input_counts = input_semantic_digest(connections)
        artifact_inputs: dict[str, dict[str, Any]] = {}
        for artifact_text in args.input_artifact:
            artifact_path = Path(artifact_text)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            artifact_inputs[artifact_path.name] = {
                "sha256": sha256_file(artifact_path),
                "release_id": payload.get("release_id")
                or payload.get("meta", {}).get("release_id"),
                "schema_version": payload.get("schema_version")
                or payload.get("meta", {}).get("schema_version"),
            }
        actor_manifest_sha256 = sha256_file(Path(args.actor_manifest))
        release_contract = {
            "contract_version": CONTRACT_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "snapshot_date": args.snapshot_date,
            "source_semantic_sha256": semantic_sha256,
            "source_mapping_semantic_sha256": source_mapping_plan[
                "semantic_sha256"
            ],
            "actor_manifest_sha256": actor_manifest_sha256,
            "input_artifacts": artifact_inputs,
        }
        release_id = hashlib.sha256(
            canonical_json(release_contract).encode()
        ).hexdigest()

        out_db = Path(args.out_db)
        published_out = Path(args.published_out)
        public_out = Path(args.public_out)
        report_out = Path(args.report_out)
        out_db_temp = sibling_temp_path(out_db)
        temporary_paths.append(out_db_temp)
        out = sqlite3.connect(out_db_temp)
        out.row_factory = sqlite3.Row
        out.execute("PRAGMA foreign_keys = ON")
        out.execute("PRAGMA journal_mode = WAL")
        out.execute("PRAGMA synchronous = NORMAL")
        out.executescript(Path(args.schema).read_text(encoding="utf-8"))
        drop_actor_graph_secondary_indexes(out)
        out.execute(
            """
            INSERT INTO actor_graph_releases(
              release_id, snapshot_date, contract_version, extractor_version,
              source_semantic_sha256, source_mapping_semantic_sha256,
              source_database_sha256, input_manifest_sha256,
              input_releases_json, counts_json, real_data_only,
              public_identity_retained, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', 1, 1, ?)
            """,
            (
                release_id,
                args.snapshot_date,
                CONTRACT_VERSION,
                EXTRACTOR_VERSION,
                semantic_sha256,
                source_mapping_plan["semantic_sha256"],
                sha256_file(paths["main"]),
                actor_manifest_sha256,
                canonical_json(artifact_inputs),
                args.generated_at,
            ),
        )
        materialize_source_mapping(
            out,
            plan=source_mapping_plan,
            release_id=release_id,
            created_at=args.generated_at,
        )
        writer = GraphWriter(
            out,
            release_id=release_id,
            snapshot_date=args.snapshot_date,
            generated_at=args.generated_at,
            source_mapping_plan=source_mapping_plan,
        )
        materialize_main(writer, connections["main"])
        materialize_spending(writer, connections["spending"])
        materialize_agreements(writer, connections["agreements"])
        materialize_geopolitics(writer, connections["geopolitics"])
        materialize_promises(writer, connections["promises"])
        create_actor_graph_secondary_indexes(out)
        counts = database_counts(out)
        counts.update(
            {
                "source_mapping_upstream_source_ids": source_mapping_plan[
                    "summary"
                ]["upstream_source_ids"],
                "source_mapping_graph_source_ids": source_mapping_plan[
                    "summary"
                ]["graph_source_ids"],
                "source_mapping_conflicting_upstream_source_ids": (
                    source_mapping_plan["summary"][
                        "conflicting_upstream_source_ids"
                    ]
                ),
                "source_mapping_namespaced_rows": source_mapping_plan[
                    "summary"
                ]["namespaced_mapping_rows"],
            }
        )
        out.execute(
            "UPDATE actor_graph_releases SET counts_json = ? WHERE release_id = ?",
            (canonical_json(counts), release_id),
        )
        out.commit()

        semantic_checks = producer_semantic_checks(
            out,
            source_mapping_plan=source_mapping_plan,
            release_id=release_id,
        )
        foreign_key_rows = list(out.execute("PRAGMA foreign_key_check"))
        integrity = str(out.execute("PRAGMA integrity_check").fetchone()[0])
        if foreign_key_rows or integrity != "ok":
            raise RuntimeError(
                f"actor graph database invalid: fk={len(foreign_key_rows)} integrity={integrity}"
            )

        release = dict(
            out.execute(
                "SELECT * FROM actor_graph_releases WHERE release_id = ?",
                (release_id,),
            ).fetchone()
        )
        payload = public_payload(
            out,
            release=release,
            counts=counts,
            input_counts=input_counts,
            source_mapping=source_mapping_plan,
        )
        published_temp = sibling_temp_path(published_out)
        public_temp = sibling_temp_path(public_out)
        report_temp = sibling_temp_path(report_out)
        temporary_paths.extend([published_temp, public_temp, report_temp])
        published_bytes, published_sha256 = write_json(published_temp, payload)
        public_bytes, public_sha256 = write_json(public_temp, payload)
        if (published_bytes, published_sha256) != (public_bytes, public_sha256):
            raise RuntimeError("published/public actor graph byte parity failed")

        report = {
            "schema_version": "actor_graph_materialization_v1",
            "status": "passed",
            "release_id": release_id,
            "contract_version": CONTRACT_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "snapshot_date": args.snapshot_date,
            "source_semantic_sha256": semantic_sha256,
            "source_mapping_semantic_sha256": source_mapping_plan[
                "semantic_sha256"
            ],
            "source_mapping": {
                **source_mapping_plan["summary"],
                "conflicting_upstream_ids": source_mapping_plan[
                    "conflicting_upstream_ids"
                ],
            },
            "source_database": {
                "file": paths["main"].name,
                "bytes": paths["main"].stat().st_size,
                "sha256": release["source_database_sha256"],
            },
            "actor_manifest": {
                "file": Path(args.actor_manifest).name,
                "bytes": Path(args.actor_manifest).stat().st_size,
                "sha256": actor_manifest_sha256,
            },
            "input_artifacts": artifact_inputs,
            "input_counts": input_counts,
            "database_counts": counts,
            "actors_by_kind": payload["coverage"]["actors_by_kind"],
            "actors_by_subtype": payload["coverage"]["actors_by_subtype"],
            "relationships_by_type": payload["coverage"][
                "relationships_by_type"
            ],
            "evidence_by_kind": payload["coverage"]["evidence_by_kind"],
            "resolution_outcomes": payload["coverage"]["resolution_outcomes"],
            "source_scopes": payload["coverage"]["source_scopes"],
            "limitations": payload["limitations"],
            "blocked_before_w3_006": [
                "relationship_cross_source_shell_identity"
            ],
            "public_artifact": {
                "bytes": published_bytes,
                "sha256": published_sha256,
            },
            "checks": {
                **semantic_checks,
                "foreign_key_violations": len(foreign_key_rows),
                "integrity_check": integrity,
                "published_public_byte_parity": True,
                "real_data_only": True,
                "synthetic_or_mock": False,
                "official_public_domain_information_retained": True,
                "cross_source_merges_published": 0,
                "name_only_merges_published": 0,
                "organization_change_events_without_evidence": 0,
                "atomic_snapshot_replacement": True,
                "operational_append_only_history_proven": False,
                "relationship_cross_source_shell_ready": False,
            },
            "outputs": {
                "database": out_db.name,
                "published": str(published_out),
                "public": str(public_out),
            },
        }
        write_json(report_temp, report)
        out.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        out.execute("PRAGMA journal_mode = DELETE")
        out.close()
        out = None

        # A prior WAL-mode snapshot can leave empty/stale sidecars beside the
        # final path. They must never be allowed to attach to the newly replaced
        # database. The validated temp database is already in DELETE mode here.
        Path(f"{out_db}-wal").unlink(missing_ok=True)
        Path(f"{out_db}-shm").unlink(missing_ok=True)
        os.replace(out_db_temp, out_db)
        os.replace(published_temp, published_out)
        os.replace(public_temp, public_out)
        os.replace(report_temp, report_out)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        if out is not None:
            out.close()
        for temp_path in temporary_paths:
            temp_path.unlink(missing_ok=True)
            Path(f"{temp_path}-wal").unlink(missing_ok=True)
            Path(f"{temp_path}-shm").unlink(missing_ok=True)
        for connection in connections.values():
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
