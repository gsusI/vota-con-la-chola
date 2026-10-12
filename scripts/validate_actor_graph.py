#!/usr/bin/env python3
"""Independently validate the real, source-scoped actor graph release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAIN_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_SPENDING_DB = REPO_ROOT / "etl/data/staging/spending-placsp-mvp.db"
DEFAULT_AGREEMENTS_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
DEFAULT_GEOPOLITICS_DB = REPO_ROOT / "etl/data/staging/geopolitics-moncloa-mvp.db"
DEFAULT_PROMISES_DB = REPO_ROOT / "etl/data/staging/promises-bng-2023.db"
DEFAULT_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "etl/data/published/actor-mandate-semantic-partition-manifest-latest.json"
)
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/actor-graph-v1.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/site/public/actor-graph/data/graph.json"
DEFAULT_MATERIALIZATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-materialization.json"
)
DEFAULT_VALIDATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-validation.json"
)
DEFAULT_INPUT_ARTIFACTS = (
    REPO_ROOT / "etl/data/published/promises-bng-2023.json",
    REPO_ROOT / "etl/data/published/spending-placsp-sample.json",
    REPO_ROOT / "etl/data/published/agreements-moncloa-sample.json",
    REPO_ROOT / "etl/data/published/geopolitics-moncloa-sample.json",
    REPO_ROOT / "etl/data/published/indicators-eurostat-gdp-es.json",
)
CONTRACT_VERSION = "actor_graph_v1"
EXTRACTOR_VERSION = "actor_graph_real_projection_v2"
PUBLIC_SCHEMA_VERSION = "actor_graph_public_v1"
VALIDATION_SCHEMA_VERSION = "actor_graph_validation_v1"
URN_RE = re.compile(r"^urn:vclc:[a-z0-9-]+:[0-9a-f]{64}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# These queries are copied as an independent statement of the published input
# contract. This validator never imports producer code or trusts producer counts.
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

GRAPH_TABLE_IDS = {
    "actor_graph_releases": "release_id",
    "actor_graph_source_mappings": "source_mapping_id",
    "actor_graph_nodes": "actor_id",
    "actor_graph_node_versions": "node_version_id",
    "actor_graph_identifier_versions": "identifier_version_id",
    "actor_graph_alias_versions": "alias_version_id",
    "actor_graph_relationships": "relationship_id",
    "actor_graph_relationship_versions": "relationship_version_id",
    "actor_graph_relationship_evidence": "relationship_evidence_id",
    "actor_resolution_decisions": "resolution_decision_id",
    "actor_resolution_evidence": "resolution_evidence_id",
    "actor_organization_change_events": "organization_change_event_id",
    "actor_organization_change_evidence": "organization_change_evidence_id",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_GRAPH_DB)
    parser.add_argument("--main-db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--spending-db", type=Path, default=DEFAULT_SPENDING_DB)
    parser.add_argument("--agreements-db", type=Path, default=DEFAULT_AGREEMENTS_DB)
    parser.add_argument("--geopolitics-db", type=Path, default=DEFAULT_GEOPOLITICS_DB)
    parser.add_argument("--promises-db", type=Path, default=DEFAULT_PROMISES_DB)
    parser.add_argument("--actor-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument(
        "--materialization-report", type=Path, default=DEFAULT_MATERIALIZATION_REPORT
    )
    parser.add_argument(
        "--input-artifact",
        action="append",
        type=Path,
        default=None,
        help="Repeat to override the five canonical real input artifacts.",
    )
    parser.add_argument("--idempotence-reference", type=Path)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_VALIDATION_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(value)
    temporary.replace(path)


def stable_id(kind: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part if part is not None else "") for part in parts)
    return f"urn:vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))}"


def normalized_label(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        "".join(character for character in folded if not unicodedata.combining(character)).split()
    )


def connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def iter_dicts(connection: sqlite3.Connection, sql: str) -> Iterator[dict[str, Any]]:
    for row in connection.execute(sql):
        yield dict(row)


def provenance_state(record_id: Any, content_sha256: Any, source_url: Any) -> str:
    if record_id and content_sha256:
        return "exact_record"
    if content_sha256 and source_url:
        return "exact_document"
    if source_url:
        return "source_default"
    return "missing"


def actor_kind_from_source(value: str | None) -> tuple[str, str]:
    actor_kind = (value or "unknown").strip().lower()
    if actor_kind == "person":
        return "person", "person"
    if actor_kind in {"public_body", "organization", "legal_entity"}:
        return "organization", actor_kind
    if actor_kind in {"state", "territory", "international_organization"}:
        return "organization", actor_kind
    if actor_kind == "collective":
        return "collective", "collective"
    return "unknown", "unknown"


class MultisetDigest:
    """Order-independent, duplicate-sensitive digest for exact fact comparison."""

    MODULUS = 1 << 256

    def __init__(self) -> None:
        self.count = 0
        self.xor = 0
        self.total = 0

    def add(self, value: dict[str, Any]) -> None:
        item = int(sha256_bytes(canonical_json(value).encode("utf-8")), 16)
        self.count += 1
        self.xor ^= item
        self.total = (self.total + item) % self.MODULUS

    def value(self) -> str:
        return f"{self.count}:{self.xor:064x}:{self.total:064x}"


@dataclass
class ActorExpectation:
    actor_kind: str
    actor_subtype: str
    source_id: str
    stable_source_key: str
    canonical_label: str
    labels: set[str] = field(default_factory=set)


SOURCE_METADATA_COLUMNS = (
    "name",
    "scope",
    "default_url",
    "data_format",
    "is_active",
    "created_at",
    "updated_at",
)
SOURCE_TABLE_COLUMNS = ("source_id", *SOURCE_METADATA_COLUMNS)


@dataclass(frozen=True)
class SourceOriginExpectation:
    input_database_key: str
    upstream_source_id: str
    graph_source_id: str
    metadata: dict[str, Any]
    metadata_sha256: str
    mapping_reason: str


def reconstruct_source_origins(
    connections: dict[str, sqlite3.Connection],
) -> tuple[
    list[SourceOriginExpectation],
    dict[tuple[str, str], str],
    set[str],
    str,
    dict[str, int],
]:
    raw_origins: list[tuple[str, str, dict[str, Any], str]] = []
    hashes_by_source: dict[str, set[str]] = {}
    for database_key, connection in connections.items():
        for row in iter_dicts(
            connection,
            """
            SELECT source_id, name, scope, default_url, data_format,
                   is_active, created_at, updated_at
            FROM sources ORDER BY source_id
            """,
        ):
            upstream_source_id = str(row.pop("source_id"))
            metadata = {column: row[column] for column in SOURCE_METADATA_COLUMNS}
            metadata_sha256 = sha256_bytes(canonical_json(metadata).encode("utf-8"))
            raw_origins.append(
                (database_key, upstream_source_id, metadata, metadata_sha256)
            )
            hashes_by_source.setdefault(upstream_source_id, set()).add(metadata_sha256)

    conflicting_source_ids = {
        source_id for source_id, hashes in hashes_by_source.items() if len(hashes) > 1
    }
    origins: list[SourceOriginExpectation] = []
    graph_ids: dict[tuple[str, str], str] = {}
    graph_metadata: dict[str, dict[str, Any]] = {}
    for database_key, upstream_source_id, metadata, metadata_sha256 in raw_origins:
        if upstream_source_id in conflicting_source_ids:
            graph_source_id = f"{upstream_source_id}@{database_key}"
            reason = "metadata_conflict_namespaced"
        elif sum(
            1
            for _, candidate_source_id, _, _ in raw_origins
            if candidate_source_id == upstream_source_id
        ) > 1:
            graph_source_id = upstream_source_id
            reason = "identical_metadata"
        else:
            graph_source_id = upstream_source_id
            reason = "unique_upstream_id"
        mapped_metadata = dict(metadata)
        mapped_metadata["source_id"] = graph_source_id
        existing = graph_metadata.setdefault(graph_source_id, mapped_metadata)
        if existing != mapped_metadata:
            raise ValueError(f"graph source metadata collision: {graph_source_id}")
        graph_ids[(database_key, upstream_source_id)] = graph_source_id
        origins.append(
            SourceOriginExpectation(
                input_database_key=database_key,
                upstream_source_id=upstream_source_id,
                graph_source_id=graph_source_id,
                metadata=metadata,
                metadata_sha256=metadata_sha256,
                mapping_reason=reason,
            )
        )
    semantic_origins = sorted(
        origins, key=lambda item: (item.upstream_source_id, item.input_database_key)
    )
    semantic_payload = [
        {
            "graph_source_id": item.graph_source_id,
            "input_database_key": item.input_database_key,
            "mapping_reason": item.mapping_reason,
            "metadata": item.metadata,
            "source_metadata_sha256": item.metadata_sha256,
            "upstream_source_id": item.upstream_source_id,
        }
        for item in semantic_origins
    ]
    summary = {
        "mapping_rows": len(origins),
        "upstream_source_ids": len(hashes_by_source),
        "graph_source_ids": len(graph_metadata),
        "conflicting_upstream_source_ids": len(conflicting_source_ids),
        "namespaced_mapping_rows": sum(
            item.mapping_reason == "metadata_conflict_namespaced" for item in origins
        ),
        "identical_metadata_mapping_rows": sum(
            item.mapping_reason == "identical_metadata" for item in origins
        ),
        "unique_mapping_rows": sum(
            item.mapping_reason == "unique_upstream_id" for item in origins
        ),
    }
    origins.sort(
        key=lambda item: (item.input_database_key, item.upstream_source_id)
    )
    return (
        origins,
        graph_ids,
        conflicting_source_ids,
        sha256_bytes(canonical_json(semantic_payload).encode("utf-8")),
        summary,
    )


class ExpectationBuilder:
    def __init__(self, *, release_id: str, snapshot_date: str) -> None:
        self.release_id = release_id
        self.snapshot_date = snapshot_date
        self.actors: dict[str, ActorExpectation] = {}
        self.alias_ids: set[str] = set()
        self.identifier_ids: set[str] = set()
        self.relationship_ids: set[str] = set()
        self.relationship_version_ids: set[str] = set()
        self.relationship_evidence_ids: set[str] = set()
        self.resolution_decision_ids: set[str] = set()
        self.resolution_evidence_ids: set[str] = set()
        self.relationship_counts: Counter[str] = Counter()
        self.actor_counts: Counter[str] = Counter()
        self.subtype_counts: Counter[str] = Counter()
        self.selected_label_occurrences = 0
        self.relationship_facts = MultisetDigest()

    def add_actor(
        self,
        *,
        source_id: str,
        actor_kind: str,
        actor_subtype: str,
        stable_source_key: str,
        label: str,
        source_record_id: str | None = None,
    ) -> str:
        source_id = str(source_id)
        stable_source_key = str(stable_source_key)
        label = str(label)
        if not source_id or not stable_source_key or not label:
            raise ValueError("official actor source, key, and label must be non-empty")
        self.selected_label_occurrences += 1
        actor_id = stable_id("actor", actor_kind, source_id, stable_source_key)
        actor = self.actors.get(actor_id)
        if actor is None:
            actor = ActorExpectation(
                actor_kind=actor_kind,
                actor_subtype=actor_subtype,
                source_id=source_id,
                stable_source_key=stable_source_key,
                canonical_label=label,
                labels={label},
            )
            self.actors[actor_id] = actor
            self.actor_counts[actor_kind] += 1
            self.subtype_counts[actor_subtype] += 1
            decision_id = stable_id("resolution-decision", actor_id, self.release_id)
            evidence_id = stable_id(
                "resolution-evidence",
                decision_id,
                source_id,
                source_record_id or stable_source_key,
            )
            self.resolution_decision_ids.add(decision_id)
            self.resolution_evidence_ids.add(evidence_id)
        else:
            actual_spec = (
                actor.actor_kind,
                actor.actor_subtype,
                actor.source_id,
                actor.stable_source_key,
            )
            expected_spec = (actor_kind, actor_subtype, source_id, stable_source_key)
            if actual_spec != expected_spec:
                raise ValueError(f"actor identity collision: {actor_id}")
            if label not in actor.labels:
                self.add_alias(actor_id, label, normalized_label(label))
                actor.labels.add(label)
        return actor_id

    def add_alias(self, actor_id: str, alias: str, canonical_alias: str) -> None:
        self.alias_ids.add(
            stable_id(
                "actor-alias", actor_id, self.release_id, canonical_alias, alias
            )
        )

    def add_identifier(self, actor_id: str, namespace: str, value: str) -> None:
        self.identifier_ids.add(
            stable_id(
                "actor-identifier", actor_id, self.release_id, namespace, value
            )
        )

    def add_relationship(
        self,
        *,
        subject_actor_id: str,
        relationship_type: str,
        object_actor_id: str | None,
        context_kind: str,
        context_id: Any,
        role_label: Any,
        valid_from: Any,
        valid_to: Any,
        observed_at: Any,
        is_present: int,
        source_id: str,
        source_record_id: Any,
        source_url: Any,
        source_content_sha256: Any,
        source_locator: str,
        exact_quote: Any = None,
        attributes: dict[str, Any] | None = None,
        evidence_kind: str | None = None,
    ) -> None:
        context_id = str(context_id)
        source_id = str(source_id)
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
        evidence_id = stable_id(
            "actor-relationship-evidence", version_id, source_locator
        )
        if relationship_id in self.relationship_ids:
            raise ValueError(f"duplicate expected relationship: {relationship_id}")
        self.relationship_ids.add(relationship_id)
        self.relationship_version_ids.add(version_id)
        self.relationship_evidence_ids.add(evidence_id)
        self.relationship_counts[relationship_type] += 1
        observed = observed_at or self.snapshot_date
        kind = evidence_kind or provenance_state(
            source_record_id, source_content_sha256, source_url
        )
        self.relationship_facts.add(
            {
                "attributes_json": canonical_json(attributes or {}),
                "context_id": context_id,
                "context_kind": context_kind,
                "evidence_kind": kind,
                "exact_quote": exact_quote,
                "is_present": int(is_present),
                "object_actor_id": object_actor_id,
                "observed_at": observed,
                "relationship_evidence_id": evidence_id,
                "relationship_id": relationship_id,
                "relationship_type": relationship_type,
                "relationship_version_id": version_id,
                "resolution_state": "source_scoped",
                "role_label": role_label,
                "source_content_sha256": source_content_sha256,
                "source_id": source_id,
                "source_locator": source_locator,
                "source_record_id": source_record_id,
                "source_url": source_url,
                "subject_actor_id": subject_actor_id,
                "valid_from": valid_from,
                "valid_to": valid_to,
            }
        )


def person_actor(
    builder: ExpectationBuilder, row: dict[str, Any], *, source_id: str
) -> str:
    return builder.add_actor(
        source_id=source_id,
        actor_kind="person",
        actor_subtype="person_registry",
        stable_source_key=str(row["person_key"]),
        label=str(row["full_name"]),
        source_record_id=row.get("source_record_id"),
    )


def party_actor(
    builder: ExpectationBuilder, row: dict[str, Any], *, source_id: str
) -> str:
    return builder.add_actor(
        source_id=source_id,
        actor_kind="organization",
        actor_subtype="party",
        stable_source_key=str(row["party_name"]),
        label=str(row["party_name"]),
        source_record_id=row.get("source_record_id"),
    )


def institution_actor(
    builder: ExpectationBuilder, row: dict[str, Any], *, source_id: str
) -> str:
    key = "|".join(
        (
            str(row.get("institution_level") or ""),
            str(row.get("institution_territory_code") or ""),
            str(row["institution_name"]),
        )
    )
    return builder.add_actor(
        source_id=source_id,
        actor_kind="organization",
        actor_subtype="institution",
        stable_source_key=key,
        label=str(row["institution_name"]),
        source_record_id=row.get("source_record_id"),
    )


def contextual_key(row: dict[str, Any], row_id: str) -> str:
    if row.get("source_identifier") and row.get("source_identifier_scheme"):
        return f"{row['source_identifier_scheme']}:{row['source_identifier']}"
    return str(row_id)


def build_expectations(
    connections: dict[str, sqlite3.Connection],
    *,
    release_id: str,
    snapshot_date: str,
    source_graph_ids: dict[tuple[str, str], str],
) -> ExpectationBuilder:
    builder = ExpectationBuilder(release_id=release_id, snapshot_date=snapshot_date)
    main = connections["main"]

    def mapped(database_key: str, source_id: Any) -> str:
        return source_graph_ids[(database_key, str(source_id))]

    for row in iter_dicts(main, MANDATE_SQL):
        source_id = mapped("main", row["source_id"])
        observed = row["source_snapshot_date"] or row["last_seen_at"]
        person = person_actor(builder, row, source_id=source_id)
        institution = institution_actor(builder, row, source_id=source_id)
        context_id = f"{source_id}:{row['source_record_id']}"
        common = {
            "valid_from": row["start_date"],
            "valid_to": row["end_date"],
            "observed_at": observed,
            "is_present": int(row["is_active"]),
            "source_id": source_id,
            "source_record_id": row["source_record_id"],
            "source_url": row["source_url"],
            "source_content_sha256": row["source_content_sha256"],
        }
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="holds_role_at",
            object_actor_id=institution,
            context_kind="mandate",
            context_id=context_id,
            role_label=row["role_title"],
            source_locator=f"mandates:{row['mandate_id']}",
            attributes={
                "level": row["level"],
                "territory_code": row["territory_code"],
                "role_code": row["role_code"],
                "legacy_mandate_id": row["mandate_id"],
            },
            **common,
        )
        if row["party_id"] is not None:
            party = party_actor(builder, row, source_id=source_id)
            builder.add_relationship(
                subject_actor_id=person,
                relationship_type="affiliated_with_party",
                object_actor_id=party,
                context_kind="mandate",
                context_id=context_id,
                role_label="mandate_party",
                source_locator=f"mandates:{row['mandate_id']}:party",
                **common,
            )

    for row in iter_dicts(main, BOE_CANDIDATE_SQL):
        source_id = mapped("main", row["source_id"])
        person = person_actor(builder, row, source_id=source_id)
        party = party_actor(builder, row, source_id=source_id)
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="candidate_for",
            object_actor_id=party,
            context_kind="candidate_occurrence",
            context_id=row["candidate_occurrence_id"],
            role_label=row["candidate_type_code"],
            valid_from=row["election_date"],
            valid_to=row["election_date"],
            observed_at=row["last_seen_snapshot_date"],
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

    for row in iter_dicts(main, BOE_EFFECTIVE_SQL):
        source_id = mapped("main", row["source_id"])
        person = person_actor(builder, row, source_id=source_id)
        party = party_actor(builder, row, source_id=source_id)
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="effective_candidate_for",
            object_actor_id=party,
            context_kind="effective_candidate_occurrence",
            context_id=row["effective_candidate_occurrence_id"],
            role_label=row["candidate_type_code"],
            valid_from=row["election_date"],
            valid_to=row["election_date"],
            observed_at=row["last_seen_snapshot_date"],
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

    for row in iter_dicts(main, ELECTED_SQL):
        source_id = mapped("main", row["source_id"])
        person = person_actor(builder, row, source_id=source_id)
        institution = (
            institution_actor(builder, row, source_id=source_id)
            if row["institution_id"] is not None
            else None
        )
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="elected_in",
            object_actor_id=institution,
            context_kind="election_result",
            context_id=row["elected_official_id"],
            role_label=row["chamber"],
            valid_from=row["election_date"],
            valid_to=None,
            observed_at=row["last_seen_snapshot_date"],
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

    for row in iter_dicts(main, PARLIAMENTARY_MEMBERSHIP_SQL):
        source_id = mapped("main", row["source_id"])
        person = person_actor(builder, row, source_id=source_id)
        group = builder.add_actor(
            source_id=mapped("main", row["group_source_id"]),
            actor_kind="organization",
            actor_subtype="parliamentary_group",
            stable_source_key=f"{row['group_legislature'] or ''}|{row['group_code']}",
            label=str(row["group_name"]),
        )
        source_url = row["source_url"] or row["source_default_url"]
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="member_of_parliamentary_group",
            object_actor_id=group,
            context_kind="parliamentary_group_membership",
            context_id=f"{source_id}:{row['membership_id']}",
            role_label="member",
            valid_from=row["start_date"],
            valid_to=row["end_date"],
            observed_at=snapshot_date,
            is_present=1,
            source_id=source_id,
            source_record_id=None,
            source_url=source_url,
            source_content_sha256=None,
            source_locator=f"person_parliamentary_group_memberships:{row['membership_id']}",
            exact_quote=row["evidence_quote"],
        )

    for row in iter_dicts(main, ORG_MEMBERSHIP_SQL):
        source_id = mapped("main", row["source_id"])
        person = person_actor(builder, row, source_id=source_id)
        source_url = row["source_url"] or row["source_default_url"]
        object_actor = None
        if row["party_id"] is not None:
            object_actor = party_actor(builder, row, source_id=source_id)
        elif row["position_id"] is not None:
            object_actor = builder.add_actor(
                source_id=source_id,
                actor_kind="office",
                actor_subtype="government_position",
                stable_source_key=(
                    row["position_code"] or f"position:{row['position_id']}"
                ),
                label=str(row["position_title"]),
                source_record_id=row["source_record_id"],
            )
        builder.add_relationship(
            subject_actor_id=person,
            relationship_type="member_of_organization",
            object_actor_id=object_actor,
            context_kind="organization_membership",
            context_id=f"{source_id}:{row['membership_id']}",
            role_label=row["role_label"] or row["membership_kind"],
            valid_from=row["start_date"],
            valid_to=row["end_date"],
            observed_at=row["evidence_date"] or snapshot_date,
            is_present=1,
            source_id=source_id,
            source_record_id=row["source_record_id"],
            source_url=source_url,
            source_content_sha256=row["source_content_sha256"],
            source_locator=f"person_org_memberships:{row['membership_id']}",
            exact_quote=row["evidence_quote"],
            attributes={"membership_kind": row["membership_kind"]},
        )

    for row in iter_dicts(main, PERSON_IDENTIFIER_SQL):
        actor = person_actor(builder, row, source_id=mapped("main", row["source_id"]))
        builder.add_identifier(actor, str(row["namespace"]), str(row["value"]))

    for row in iter_dicts(main, PERSON_ALIAS_SQL):
        actor = person_actor(builder, row, source_id=mapped("main", row["source_id"]))
        builder.add_alias(actor, str(row["alias"]), str(row["canonical_alias"]))

    for row in iter_dicts(main, PARTY_ALIAS_SQL):
        actor = party_actor(builder, row, source_id=mapped("main", row["source_id"]))
        builder.add_alias(actor, str(row["alias"]), str(row["canonical_alias"]))

    for row in iter_dicts(connections["spending"], SPENDING_ACTOR_SQL):
        source_id = mapped("spending", row["source_id"])
        actor_kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = builder.add_actor(
            source_id=source_id,
            actor_kind=actor_kind,
            actor_subtype=subtype,
            stable_source_key=contextual_key(row, row["spending_item_actor_id"]),
            label=str(row["source_label"]),
            source_record_id=row["source_record_id"],
        )
        if row["source_identifier"]:
            builder.add_identifier(
                actor,
                str(row["source_identifier_scheme"]),
                str(row["source_identifier"]),
            )
        builder.add_relationship(
            subject_actor_id=actor,
            relationship_type="acts_in_spending_item",
            object_actor_id=None,
            context_kind="spending_item",
            context_id=row["spending_item_id"],
            role_label=row["actor_role"],
            valid_from=(
                row["effective_from"] or row["decision_on"] or row["published_on"]
            ),
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

    for row in iter_dicts(connections["agreements"], AGREEMENT_ACTOR_SQL):
        source_id = mapped("agreements", row["source_id"])
        actor_kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = builder.add_actor(
            source_id=source_id,
            actor_kind=actor_kind,
            actor_subtype=subtype,
            stable_source_key=contextual_key(row, row["agreement_party_id"]),
            label=str(row["source_label"]),
            source_record_id=row["source_record_id"],
        )
        builder.add_relationship(
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

    for row in iter_dicts(connections["agreements"], MEETING_ACTOR_SQL):
        source_id = mapped("agreements", row["source_id"])
        actor_kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = builder.add_actor(
            source_id=source_id,
            actor_kind=actor_kind,
            actor_subtype=subtype,
            stable_source_key=contextual_key(row, row["meeting_participant_id"]),
            label=str(row["source_label"]),
            source_record_id=row["source_record_id"],
        )
        builder.add_relationship(
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

    for row in iter_dicts(connections["geopolitics"], GEOPOLITICS_ACTOR_SQL):
        source_id = mapped("geopolitics", row["source_id"])
        actor_kind, subtype = actor_kind_from_source(row["actor_kind"])
        actor = builder.add_actor(
            source_id=source_id,
            actor_kind=actor_kind,
            actor_subtype=subtype,
            stable_source_key=contextual_key(row, row["geopolitical_action_actor_id"]),
            label=str(row["source_label"]),
            source_record_id=row["source_record_id"],
        )
        builder.add_relationship(
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

    for row in iter_dicts(connections["promises"], MANIFESTO_ACTOR_SQL):
        source_id = mapped("promises", row["source_id"])
        actor = party_actor(builder, row, source_id=source_id)
        builder.add_relationship(
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
    return builder


def source_semantic_digest(
    connections: dict[str, sqlite3.Connection],
) -> tuple[str, dict[str, int]]:
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    for database_key, category, sql in INPUT_QUERIES:
        digest.update(f"{database_key}:{category}\n".encode("utf-8"))
        count = 0
        for row in iter_dicts(connections[database_key], sql):
            digest.update(canonical_json(row).encode("utf-8"))
            digest.update(b"\n")
            count += 1
        counts[category] = count
    return digest.hexdigest(), counts


def grouped_counts(connection: sqlite3.Connection, sql: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in connection.execute(sql)}


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in GRAPH_TABLE_IDS
    }


def id_set(connection: sqlite3.Connection, table: str, column: str) -> set[str]:
    return {str(row[0]) for row in connection.execute(f'SELECT "{column}" FROM "{table}"')}


def table_id_fingerprints(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for table, column in GRAPH_TABLE_IDS.items():
        digest = hashlib.sha256()
        count = 0
        for row in connection.execute(
            f'SELECT "{column}" FROM "{table}" ORDER BY "{column}"'
        ):
            digest.update(str(row[0]).encode("utf-8"))
            digest.update(b"\n")
            count += 1
        result[table] = {"count": count, "ids_sha256": digest.hexdigest()}
    return result


def actual_relationship_digest(connection: sqlite3.Connection) -> MultisetDigest:
    digest = MultisetDigest()
    sql = """
    SELECT
      version.attributes_json, relationship.context_id, relationship.context_kind,
      evidence.evidence_kind, evidence.exact_quote, version.is_present,
      relationship.object_actor_id, version.observed_at,
      evidence.relationship_evidence_id, relationship.relationship_id,
      relationship.relationship_type, version.relationship_version_id,
      version.resolution_state, version.role_label,
      version.source_content_sha256, version.source_id, evidence.source_locator,
      version.source_record_id, version.source_url,
      relationship.subject_actor_id, version.valid_from, version.valid_to
    FROM actor_graph_relationships AS relationship
    JOIN actor_graph_relationship_versions AS version
      ON version.relationship_id = relationship.relationship_id
    JOIN actor_graph_relationship_evidence AS evidence
      ON evidence.relationship_version_id = version.relationship_version_id
    ORDER BY relationship.relationship_id
    """
    for row in iter_dicts(connection, sql):
        digest.add(row)
    return digest


def artifact_input_manifest(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest[path.name] = {
            "sha256": sha256_file(path),
            "release_id": payload.get("release_id")
            or payload.get("meta", {}).get("release_id"),
            "schema_version": payload.get("schema_version")
            or payload.get("meta", {}).get("schema_version"),
        }
    return manifest


def nested_values(value: Any, key: str) -> Iterator[Any]:
    if isinstance(value, dict):
        for candidate_key, candidate_value in value.items():
            if candidate_key == key:
                yield candidate_value
            yield from nested_values(candidate_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from nested_values(item, key)


def main() -> int:
    args = parse_args()
    input_artifacts = tuple(args.input_artifact or DEFAULT_INPUT_ARTIFACTS)
    required = (
        args.db,
        args.main_db,
        args.spending_db,
        args.agreements_db,
        args.geopolitics_db,
        args.promises_db,
        args.actor_manifest,
        args.published,
        args.public,
        args.materialization_report,
        *input_artifacts,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing required real actor-graph inputs: {missing}")

    source_paths = {
        "main": args.main_db,
        "spending": args.spending_db,
        "agreements": args.agreements_db,
        "geopolitics": args.geopolitics_db,
        "promises": args.promises_db,
    }
    connections = {
        key: connect_readonly(path) for key, path in source_paths.items()
    }
    checks: dict[str, bool] = {}
    metrics: dict[str, Any] = {}
    try:
        (
            source_origins,
            source_graph_ids,
            conflicting_source_ids,
            source_mapping_semantic_sha256,
            source_mapping_summary,
        ) = reconstruct_source_origins(connections)
        semantic_sha256, input_counts = source_semantic_digest(connections)
        artifact_manifest = artifact_input_manifest(input_artifacts)
        input_artifact_policy_safe = True
        for input_artifact in input_artifacts:
            input_bytes = input_artifact.read_bytes()
            input_text = input_bytes.decode("utf-8", errors="replace").casefold()
            input_payload = json.loads(input_bytes)
            input_artifact_policy_safe = input_artifact_policy_safe and not any(
                marker in input_text
                for marker in (
                    "example.test",
                    "fixture data",
                    "generated person",
                    "placeholder person",
                )
            )
            input_artifact_policy_safe = input_artifact_policy_safe and all(
                value is False
                for value in nested_values(input_payload, "synthetic_or_mock")
            )
            real_only_values = list(nested_values(input_payload, "real_data_only"))
            input_artifact_policy_safe = input_artifact_policy_safe and all(
                value is True for value in real_only_values
            )
        actor_manifest_sha256 = sha256_file(args.actor_manifest)
        published_bytes = args.published.read_bytes()
        public_bytes = args.public.read_bytes()
        artifact_sha256 = sha256_bytes(published_bytes)
        artifact = json.loads(published_bytes)
        materialization = json.loads(
            args.materialization_report.read_text(encoding="utf-8")
        )
        meta = artifact.get("meta", {})
        snapshot_date = str(meta.get("snapshot_date") or "")
        release_contract = {
            "contract_version": CONTRACT_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "snapshot_date": snapshot_date,
            "source_semantic_sha256": semantic_sha256,
            "source_mapping_semantic_sha256": source_mapping_semantic_sha256,
            "actor_manifest_sha256": actor_manifest_sha256,
            "input_artifacts": artifact_manifest,
        }
        expected_release_id = sha256_bytes(
            canonical_json(release_contract).encode("utf-8")
        )
        release_id = str(meta.get("release_id") or "")
        expectations = build_expectations(
            connections,
            release_id=expected_release_id,
            snapshot_date=snapshot_date,
            source_graph_ids=source_graph_ids,
        )
    finally:
        for connection in connections.values():
            connection.close()

    checks["published_public_byte_parity"] = published_bytes == public_bytes
    checks["artifact_hash_matches_materialization"] = (
        artifact_sha256 == materialization.get("public_artifact", {}).get("sha256")
    )
    checks["artifact_bytes_match_materialization"] = (
        len(published_bytes) == materialization.get("public_artifact", {}).get("bytes")
    )
    checks["public_schema_version"] = meta.get("schema_version") == PUBLIC_SCHEMA_VERSION
    checks["contract_version"] = meta.get("contract_version") == CONTRACT_VERSION
    checks["source_semantic_sha256"] = (
        meta.get("source_semantic_sha256") == semantic_sha256
        == materialization.get("source_semantic_sha256")
    )
    checks["source_mapping_semantic_sha256"] = (
        meta.get("source_mapping_semantic_sha256")
        == source_mapping_semantic_sha256
        == materialization.get("source_mapping_semantic_sha256")
    )
    checks["input_manifest_sha256"] = (
        meta.get("input_manifest_sha256") == actor_manifest_sha256
        == materialization.get("actor_manifest", {}).get("sha256")
    )
    checks["input_artifact_manifest"] = (
        materialization.get("input_artifacts") == artifact_manifest
    )
    checks["release_id_reconstructed"] = (
        release_id == expected_release_id == materialization.get("release_id")
    )
    checks["release_id_is_sha256"] = HEX_SHA256_RE.fullmatch(release_id) is not None
    checks["real_data_only_policy"] = meta.get("real_data_only") is True
    checks["input_artifacts_real_data_only"] = input_artifact_policy_safe
    checks["no_fake_data_policy"] = meta.get("synthetic_or_mock") is False
    checks["official_public_identity_retained_policy"] = (
        meta.get("official_public_domain_information_retained") is True
    )
    policy = artifact.get("policy", {})
    checks["public_identity_redaction_forbidden"] = (
        policy.get("public_identity_redaction")
        == "forbidden_for_official_public_fields"
    )
    checks["name_only_cross_source_merge_forbidden"] = (
        policy.get("name_only_cross_source_merge") == "forbidden"
    )
    checks["causal_graph_inference_forbidden"] = (
        policy.get("causal_inference_from_graph_path") == "forbidden"
    )
    checks["cross_source_merges_declared_zero"] = (
        policy.get("cross_source_merges_published") == 0
    )
    serialized = published_bytes.decode("utf-8", errors="replace").casefold()
    checks["no_fake_data_markers"] = not any(
        marker in serialized
        for marker in ("example.test", "fixture data", "generated person", "placeholder person")
    )
    checks["no_private_workstation_paths"] = not any(
        marker in serialized for marker in ("/users/", "file:///", "/home/")
    )

    graph = connect_readonly(args.db)
    try:
        graph_counts = table_counts(graph)
        graph_counts.update(
            {
                "source_mapping_upstream_source_ids": int(
                    graph.execute(
                        "SELECT COUNT(DISTINCT upstream_source_id) FROM actor_graph_source_mappings"
                    ).fetchone()[0]
                ),
                "source_mapping_graph_source_ids": int(
                    graph.execute(
                        "SELECT COUNT(DISTINCT graph_source_id) FROM actor_graph_source_mappings"
                    ).fetchone()[0]
                ),
                "source_mapping_conflicting_upstream_source_ids": int(
                    graph.execute(
                        """
                        SELECT COUNT(DISTINCT upstream_source_id)
                        FROM actor_graph_source_mappings
                        WHERE mapping_reason = 'metadata_conflict_namespaced'
                        """
                    ).fetchone()[0]
                ),
                "source_mapping_namespaced_rows": int(
                    graph.execute(
                        """
                        SELECT COUNT(*) FROM actor_graph_source_mappings
                        WHERE mapping_reason = 'metadata_conflict_namespaced'
                        """
                    ).fetchone()[0]
                ),
            }
        )
        release_rows = [dict(row) for row in graph.execute("SELECT * FROM actor_graph_releases")]
        release_row = release_rows[0] if len(release_rows) == 1 else {}
        actual_actor_ids = id_set(graph, "actor_graph_nodes", "actor_id")
        expected_source_mappings = {
            stable_id(
                "actor-source-mapping",
                expected_release_id,
                origin.input_database_key,
                origin.upstream_source_id,
            ): (
                expected_release_id,
                origin.input_database_key,
                origin.upstream_source_id,
                origin.graph_source_id,
                origin.metadata_sha256,
                origin.mapping_reason,
            )
            for origin in source_origins
        }
        actual_source_mappings = {
            str(row[0]): tuple(row[1:])
            for row in graph.execute(
                """
                SELECT source_mapping_id, release_id, input_database_key,
                       upstream_source_id, graph_source_id,
                       source_metadata_sha256, mapping_reason
                FROM actor_graph_source_mappings
                """
            )
        }
        expected_graph_sources: dict[str, tuple[Any, ...]] = {}
        for origin in source_origins:
            metadata = dict(origin.metadata)
            metadata["source_id"] = origin.graph_source_id
            expected_graph_sources[origin.graph_source_id] = tuple(
                metadata[column] for column in SOURCE_TABLE_COLUMNS
            )
        actual_graph_sources = {
            str(row[0]): tuple(row)
            for row in graph.execute(
                f"SELECT {', '.join(SOURCE_TABLE_COLUMNS)} FROM sources"
            )
        }
        actual_node_version_ids = id_set(
            graph, "actor_graph_node_versions", "node_version_id"
        )
        actual_identifier_ids = id_set(
            graph, "actor_graph_identifier_versions", "identifier_version_id"
        )
        actual_alias_ids = id_set(
            graph, "actor_graph_alias_versions", "alias_version_id"
        )
        actual_relationship_ids = id_set(
            graph, "actor_graph_relationships", "relationship_id"
        )
        actual_relationship_version_ids = id_set(
            graph, "actor_graph_relationship_versions", "relationship_version_id"
        )
        actual_relationship_evidence_ids = id_set(
            graph,
            "actor_graph_relationship_evidence",
            "relationship_evidence_id",
        )
        actual_decision_ids = id_set(
            graph, "actor_resolution_decisions", "resolution_decision_id"
        )
        actual_resolution_evidence_ids = id_set(
            graph, "actor_resolution_evidence", "resolution_evidence_id"
        )
        actual_canonical_labels = {
            str(row[0]): str(row[1])
            for row in graph.execute(
                "SELECT actor_id, canonical_label FROM actor_graph_node_versions"
            )
        }
        actual_labels: dict[str, set[str]] = {
            actor_id: {label} for actor_id, label in actual_canonical_labels.items()
        }
        for row in graph.execute("SELECT actor_id, alias FROM actor_graph_alias_versions"):
            actual_labels.setdefault(str(row[0]), set()).add(str(row[1]))

        node_formula_errors = 0
        node_scope_errors = 0
        node_urn_errors = 0
        canonical_label_errors = 0
        missing_label_pairs: list[dict[str, str]] = []
        retained_label_pairs = 0
        for row in graph.execute(
            "SELECT actor_id, actor_kind, source_scope_id, stable_source_key, identity_scope FROM actor_graph_nodes"
        ):
            actor_id = str(row[0])
            expected_id = stable_id("actor", row[1], row[2], row[3])
            node_formula_errors += actor_id != expected_id
            node_scope_errors += row[4] != "source_scoped"
            node_urn_errors += URN_RE.fullmatch(actor_id) is None
        for actor_id, expected in expectations.actors.items():
            canonical_label_errors += (
                actual_canonical_labels.get(actor_id) != expected.canonical_label
            )
            actor_labels = actual_labels.get(actor_id, set())
            for label in expected.labels:
                if label in actor_labels:
                    retained_label_pairs += 1
                elif len(missing_label_pairs) < 20:
                    missing_label_pairs.append({"actor_id": actor_id, "label": label})

        expected_node_version_ids = {
            stable_id("actor-version", actor_id, expected_release_id)
            for actor_id in expectations.actors
        }
        relationship_formula_errors = 0
        for row in graph.execute(
            """
            SELECT relationship.relationship_id,
                   relationship.subject_actor_id,
                   relationship.relationship_type,
                   relationship.object_actor_id,
                   relationship.context_kind,
                   relationship.context_id,
                   version.source_id
            FROM actor_graph_relationships AS relationship
            JOIN actor_graph_relationship_versions AS version
              ON version.relationship_id = relationship.relationship_id
            """
        ):
            expected_id = stable_id(
                "actor-relationship",
                row[6],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
            )
            relationship_formula_errors += str(row[0]) != expected_id

        actual_relation_facts = actual_relationship_digest(graph)
        foreign_keys = [tuple(row) for row in graph.execute("PRAGMA foreign_key_check")]
        integrity = str(graph.execute("PRAGMA integrity_check").fetchone()[0])
        relationship_counts = grouped_counts(
            graph,
            "SELECT relationship_type, COUNT(*) FROM actor_graph_relationships GROUP BY relationship_type ORDER BY relationship_type",
        )
        actor_counts = grouped_counts(
            graph,
            "SELECT actor_kind, COUNT(*) FROM actor_graph_nodes GROUP BY actor_kind ORDER BY actor_kind",
        )
        subtype_counts = grouped_counts(
            graph,
            "SELECT actor_subtype, COUNT(*) FROM actor_graph_nodes GROUP BY actor_subtype ORDER BY actor_subtype",
        )
        evidence_counts = grouped_counts(
            graph,
            "SELECT evidence_kind, COUNT(*) FROM actor_graph_relationship_evidence GROUP BY evidence_kind ORDER BY evidence_kind",
        )
        resolution_counts = grouped_counts(
            graph,
            "SELECT outcome, COUNT(*) FROM actor_resolution_decisions GROUP BY outcome ORDER BY outcome",
        )
        evidence_contract_violations = int(
            graph.execute(
                """
                SELECT COUNT(*) FROM (
                  SELECT version.relationship_version_id
                  FROM actor_graph_relationship_versions AS version
                  LEFT JOIN actor_graph_relationship_evidence AS evidence
                    ON evidence.relationship_version_id = version.relationship_version_id
                  GROUP BY version.relationship_version_id
                  HAVING COUNT(evidence.relationship_evidence_id) <> 1
                )
                """
            ).fetchone()[0]
        )
        evidence_source_mismatches = int(
            graph.execute(
                """
                SELECT COUNT(*)
                FROM actor_graph_relationship_versions AS version
                JOIN actor_graph_relationship_evidence AS evidence
                  ON evidence.relationship_version_id = version.relationship_version_id
                WHERE evidence.source_id <> version.source_id
                   OR COALESCE(evidence.source_record_id, '') <> COALESCE(version.source_record_id, '')
                   OR COALESCE(evidence.source_url, '') <> COALESCE(version.source_url, '')
                   OR COALESCE(evidence.source_content_sha256, '') <> COALESCE(version.source_content_sha256, '')
                   OR TRIM(evidence.source_locator) = ''
                """
            ).fetchone()[0]
        )
        bad_content_hashes = int(
            graph.execute(
                """
                SELECT COUNT(*) FROM actor_graph_relationship_evidence
                WHERE source_content_sha256 IS NOT NULL
                  AND (
                    length(source_content_sha256) <> 64
                    OR source_content_sha256 GLOB '*[^0-9a-f]*'
                  )
                """
            ).fetchone()[0]
        )
        person_identity_validity_violations = int(
            graph.execute(
                """
                SELECT COUNT(*)
                FROM actor_graph_nodes AS node
                JOIN actor_graph_node_versions AS version
                  ON version.actor_id = node.actor_id
                WHERE node.actor_kind = 'person'
                  AND node.identity_scope = 'source_scoped'
                  AND (
                    version.valid_from IS NOT NULL
                    OR version.valid_to IS NOT NULL
                  )
                """
            ).fetchone()[0]
        )
        actor_identity_validity_violations = int(
            graph.execute(
                """
                SELECT COUNT(*) FROM actor_graph_node_versions
                WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL
                """
            ).fetchone()[0]
        )
        resolution_identity_validity_violations = int(
            graph.execute(
                """
                SELECT COUNT(*) FROM actor_resolution_decisions
                WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL
                """
            ).fetchone()[0]
        )
        unsafe_identity_rows = int(
            graph.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM actor_graph_nodes
                   WHERE identity_scope <> 'source_scoped')
                + (SELECT COUNT(*) FROM actor_graph_node_versions
                   WHERE identity_state <> 'source_scoped')
                + (SELECT COUNT(*) FROM actor_resolution_decisions
                   WHERE outcome <> 'source_scoped' OR candidate_actor_id IS NOT NULL
                      OR lower(method) LIKE '%name%')
                + (SELECT COUNT(*) FROM actor_graph_relationship_versions
                   WHERE resolution_state <> 'source_scoped')
                """
            ).fetchone()[0]
        )
        node_source_scope_mismatches = int(
            graph.execute(
                """
                SELECT COUNT(*)
                FROM actor_graph_nodes AS node
                JOIN actor_graph_node_versions AS version
                  ON version.actor_id = node.actor_id
                WHERE node.source_scope_id <> version.source_id
                """
            ).fetchone()[0]
        )
        cross_source_same_label_groups = int(
            graph.execute(
                """
                SELECT COUNT(*) FROM (
                  SELECT version.normalized_label
                  FROM actor_graph_nodes AS node
                  JOIN actor_graph_node_versions AS version
                    ON version.actor_id = node.actor_id
                  GROUP BY version.normalized_label
                  HAVING COUNT(DISTINCT node.source_scope_id) > 1
                )
                """
            ).fetchone()[0]
        )
        organization_change_events = int(
            graph.execute(
                "SELECT COUNT(*) FROM actor_organization_change_events"
            ).fetchone()[0]
        )
        id_fingerprints = table_id_fingerprints(graph)

        sample_node_errors = 0
        for sample in artifact.get("sample_nodes", []):
            row = graph.execute(
                """
                SELECT node.actor_kind, node.actor_subtype, node.identity_scope,
                       node.source_scope_id, version.canonical_label,
                       version.identity_state, version.observed_at,
                       version.source_url, version.provenance_state
                FROM actor_graph_nodes AS node
                JOIN actor_graph_node_versions AS version
                  ON version.actor_id = node.actor_id
                WHERE node.actor_id = ? AND version.release_id = ?
                """,
                (sample.get("actor_id"), release_id),
            ).fetchone()
            expected_sample = (
                sample.get("actor_kind"),
                sample.get("actor_subtype"),
                sample.get("identity_scope"),
                sample.get("source_scope_id"),
                sample.get("canonical_label"),
                sample.get("identity_state"),
                sample.get("observed_at"),
                sample.get("source_url"),
                sample.get("provenance_state"),
            )
            sample_node_errors += row is None or tuple(row) != expected_sample
        expected_sample_node_ids = [
            str(row[0])
            for row in graph.execute(
                """
                WITH ranked AS (
                  SELECT node.actor_id,
                         ROW_NUMBER() OVER (
                           PARTITION BY node.actor_kind, node.actor_subtype
                           ORDER BY node.source_scope_id,
                                    version.canonical_label, node.actor_id
                         ) AS rank_in_type
                  FROM actor_graph_nodes AS node
                  JOIN actor_graph_node_versions AS version
                    ON version.actor_id = node.actor_id
                  WHERE version.release_id = ?
                )
                SELECT actor_id FROM ranked
                WHERE rank_in_type <= 3
                ORDER BY actor_id
                """,
                (release_id,),
            )
        ]
        actual_sample_node_ids = sorted(
            str(sample.get("actor_id")) for sample in artifact.get("sample_nodes", [])
        )
        sample_relationship_errors = 0
        for sample in artifact.get("sample_relationships", []):
            row = graph.execute(
                """
                SELECT relationship.relationship_type, relationship.context_kind,
                       relationship.context_id, subject.canonical_label,
                       object.canonical_label, version.role_label,
                       version.valid_from, version.valid_to, version.observed_at,
                       version.is_present, version.resolution_state,
                       version.source_id, version.source_url,
                       evidence.evidence_kind, evidence.source_locator
                FROM actor_graph_relationships AS relationship
                JOIN actor_graph_relationship_versions AS version
                  ON version.relationship_id = relationship.relationship_id
                JOIN actor_graph_node_versions AS subject
                  ON subject.actor_id = relationship.subject_actor_id
                 AND subject.release_id = version.release_id
                LEFT JOIN actor_graph_node_versions AS object
                  ON object.actor_id = relationship.object_actor_id
                 AND object.release_id = version.release_id
                JOIN actor_graph_relationship_evidence AS evidence
                  ON evidence.relationship_version_id = version.relationship_version_id
                WHERE relationship.relationship_id = ? AND version.release_id = ?
                """,
                (sample.get("relationship_id"), release_id),
            ).fetchone()
            expected_sample = (
                sample.get("relationship_type"),
                sample.get("context_kind"),
                sample.get("context_id"),
                sample.get("subject_label"),
                sample.get("object_label"),
                sample.get("role_label"),
                sample.get("valid_from"),
                sample.get("valid_to"),
                sample.get("observed_at"),
                sample.get("is_present"),
                sample.get("resolution_state"),
                sample.get("source_id"),
                sample.get("source_url"),
                sample.get("evidence_kind"),
                sample.get("source_locator"),
            )
            sample_relationship_errors += row is None or tuple(row) != expected_sample
        expected_sample_relationship_ids = [
            str(row[0])
            for row in graph.execute(
                """
                WITH ranked AS (
                  SELECT relationship.relationship_id,
                         ROW_NUMBER() OVER (
                           PARTITION BY relationship.relationship_type
                           ORDER BY version.source_id, relationship.context_id,
                                    relationship.relationship_id
                         ) AS rank_in_type
                  FROM actor_graph_relationships AS relationship
                  JOIN actor_graph_relationship_versions AS version
                    ON version.relationship_id = relationship.relationship_id
                  WHERE version.release_id = ?
                )
                SELECT relationship_id FROM ranked
                WHERE rank_in_type <= 3
                ORDER BY relationship_id
                """,
                (release_id,),
            )
        ]
        actual_sample_relationship_ids = sorted(
            str(sample.get("relationship_id"))
            for sample in artifact.get("sample_relationships", [])
        )
    finally:
        graph.close()

    expected_actor_ids = set(expectations.actors)
    checks["source_database_sha256"] = (
        sha256_file(args.main_db) == release_row.get("source_database_sha256")
        == materialization.get("source_database", {}).get("sha256")
    )
    checks["single_release_row"] = len(release_rows) == 1
    checks["source_mapping_rows_complete"] = (
        actual_source_mappings == expected_source_mappings
    )
    checks["source_mapping_summary_reconciled"] = (
        artifact.get("coverage", {}).get("source_mapping")
        == source_mapping_summary
        == {
            key: materialization.get("source_mapping", {}).get(key)
            for key in source_mapping_summary
        }
        and materialization.get("source_mapping", {}).get(
            "conflicting_upstream_ids"
        )
        == sorted(conflicting_source_ids)
    )
    checks["source_mapping_metadata_exact"] = (
        actual_graph_sources == expected_graph_sources
    )
    checks["source_conflicts_deterministically_namespaced"] = all(
        (
            origin.graph_source_id
            == f"{origin.upstream_source_id}@{origin.input_database_key}"
            and origin.mapping_reason == "metadata_conflict_namespaced"
        )
        for origin in source_origins
        if origin.upstream_source_id in conflicting_source_ids
    )
    checks["database_release_contract"] = (
        release_row.get("release_id") == release_id
        and release_row.get("contract_version") == CONTRACT_VERSION
        and release_row.get("extractor_version") == EXTRACTOR_VERSION
        and release_row.get("source_semantic_sha256") == semantic_sha256
        and release_row.get("source_mapping_semantic_sha256")
        == source_mapping_semantic_sha256
        and release_row.get("input_manifest_sha256") == actor_manifest_sha256
        and json.loads(release_row.get("input_releases_json") or "{}")
        == artifact_manifest
        and release_row.get("real_data_only") == 1
        and release_row.get("public_identity_retained") == 1
    )
    checks["database_counts_reconciled"] = (
        graph_counts == artifact.get("coverage", {}).get("database_counts")
        == materialization.get("database_counts")
        == json.loads(release_row.get("counts_json") or "{}")
    )
    checks["input_counts_reconciled"] = (
        input_counts == artifact.get("coverage", {}).get("input_counts")
        == materialization.get("input_counts")
    )
    checks["relationship_counts_reconciled"] = (
        dict(sorted(expectations.relationship_counts.items()))
        == relationship_counts
        == artifact.get("coverage", {}).get("relationships_by_type")
        == materialization.get("relationships_by_type")
    )
    checks["actor_kind_counts_reconciled"] = (
        dict(sorted(expectations.actor_counts.items()))
        == actor_counts
        == artifact.get("coverage", {}).get("actors_by_kind")
    )
    checks["actor_subtype_counts_reconciled"] = (
        dict(sorted(expectations.subtype_counts.items()))
        == subtype_counts
        == artifact.get("coverage", {}).get("actors_by_subtype")
    )
    checks["evidence_counts_reconciled"] = (
        evidence_counts == artifact.get("coverage", {}).get("evidence_by_kind")
        == materialization.get("evidence_by_kind")
    )
    checks["resolution_counts_reconciled"] = (
        resolution_counts == {"source_scoped": len(expectations.actors)}
        == artifact.get("coverage", {}).get("resolution_outcomes")
        == materialization.get("resolution_outcomes")
    )
    checks["expected_actor_ids_exact"] = actual_actor_ids == expected_actor_ids
    checks["actor_id_formulas"] = node_formula_errors == 0 and node_urn_errors == 0
    checks["actor_scope_source_scoped"] = node_scope_errors == 0
    checks["node_version_ids_exact"] = (
        actual_node_version_ids == expected_node_version_ids
    )
    checks["identifier_ids_exact"] = (
        actual_identifier_ids == expectations.identifier_ids
    )
    checks["alias_ids_exact"] = actual_alias_ids == expectations.alias_ids
    checks["relationship_ids_exact"] = (
        actual_relationship_ids == expectations.relationship_ids
    )
    checks["relationship_id_formulas"] = relationship_formula_errors == 0
    checks["relationship_version_ids_exact"] = (
        actual_relationship_version_ids == expectations.relationship_version_ids
    )
    checks["relationship_evidence_ids_exact"] = (
        actual_relationship_evidence_ids == expectations.relationship_evidence_ids
    )
    checks["resolution_decision_ids_exact"] = (
        actual_decision_ids == expectations.resolution_decision_ids
    )
    checks["resolution_evidence_ids_exact"] = (
        actual_resolution_evidence_ids == expectations.resolution_evidence_ids
    )
    checks["relationship_fact_parity"] = (
        actual_relation_facts.value() == expectations.relationship_facts.value()
    )
    checks["official_public_labels_retained"] = (
        not missing_label_pairs and canonical_label_errors == 0
    )
    checks["person_identity_validity_not_inherited_from_context"] = (
        person_identity_validity_violations == 0
    )
    checks["actor_identity_validity_not_inherited_from_context"] = (
        actor_identity_validity_violations == 0
        and resolution_identity_validity_violations == 0
    )
    checks["no_cross_source_or_name_only_merges"] = (
        unsafe_identity_rows == 0
        and node_source_scope_mismatches == 0
        and actual_actor_ids == expected_actor_ids
    )
    checks["relationship_evidence_complete"] = (
        evidence_contract_violations == 0
        and evidence_source_mismatches == 0
        and "missing" not in evidence_counts
    )
    checks["evidence_content_hashes_well_formed"] = bad_content_hashes == 0
    checks["organization_change_events_evidence_safe"] = organization_change_events == 0
    checks["foreign_key_check"] = not foreign_keys
    checks["integrity_check"] = integrity == "ok"
    checks["bounded_public_samples_match_database"] = (
        sample_node_errors == 0
        and sample_relationship_errors == 0
        and actual_sample_node_ids == expected_sample_node_ids
        and actual_sample_relationship_ids == expected_sample_relationship_ids
    )

    deterministic_fingerprint = sha256_bytes(
        canonical_json(
            {
                "release_id": release_id,
                "table_ids": id_fingerprints,
                "relationship_facts": actual_relation_facts.value(),
            }
        ).encode("utf-8")
    )
    checks["deterministic_content_addressed_ids"] = all(
        (row["count"] == 0 or HEX_SHA256_RE.fullmatch(row["ids_sha256"]) is not None)
        for row in id_fingerprints.values()
    )
    idempotence_reference_compared = False
    if args.idempotence_reference:
        reference = json.loads(args.idempotence_reference.read_text(encoding="utf-8"))
        idempotence_reference_compared = True
        checks["idempotent_rerun_reference"] = (
            reference.get("release_id") == release_id
            and reference.get("deterministic_fingerprint")
            == deterministic_fingerprint
            and reference.get("database_counts") == graph_counts
        )

    metrics.update(
        {
            "actors": len(actual_actor_ids),
            "relationships": len(actual_relationship_ids),
            "relationship_evidence": len(actual_relationship_evidence_ids),
            "identifiers": len(actual_identifier_ids),
            "aliases": len(actual_alias_ids),
            "source_mapping_rows": len(actual_source_mappings),
            "source_mapping_semantic_sha256": source_mapping_semantic_sha256,
            "source_mapping_summary": source_mapping_summary,
            "conflicting_upstream_source_ids": sorted(conflicting_source_ids),
            "selected_public_label_occurrences": expectations.selected_label_occurrences,
            "unique_actor_label_pairs_expected": sum(
                len(actor.labels) for actor in expectations.actors.values()
            ),
            "unique_actor_label_pairs_retained": retained_label_pairs,
            "missing_public_label_pairs": len(missing_label_pairs),
            "canonical_label_errors": canonical_label_errors,
            "person_identity_validity_violations": person_identity_validity_violations,
            "actor_identity_validity_violations": actor_identity_validity_violations,
            "resolution_identity_validity_violations": resolution_identity_validity_violations,
            "cross_source_same_label_groups_preserved": cross_source_same_label_groups,
            "unsafe_identity_rows": unsafe_identity_rows,
            "relationship_evidence_contract_violations": evidence_contract_violations,
            "evidence_source_mismatches": evidence_source_mismatches,
            "foreign_key_violations": len(foreign_keys),
            "integrity_check": integrity,
            "relationship_fact_multiset_digest": actual_relation_facts.value(),
            "idempotence_reference_compared": idempotence_reference_compared,
        }
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    report = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": "passed" if not failed else "failed",
        "release_id": release_id,
        "artifact_sha256": artifact_sha256,
        "source_semantic_sha256": semantic_sha256,
        "deterministic_fingerprint": deterministic_fingerprint,
        "database_counts": graph_counts,
        "input_counts": input_counts,
        "relationship_counts": relationship_counts,
        "checks": checks,
        "failed_checks": failed,
        "metrics": metrics,
        "missing_public_label_examples": missing_label_pairs,
        "id_fingerprints": id_fingerprints,
    }
    atomic_write(args.report_out, (canonical_json(report) + "\n").encode("utf-8"))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
