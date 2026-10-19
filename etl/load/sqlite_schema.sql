PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,
  default_url TEXT NOT NULL,
  data_format TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_levels (
  admin_level_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
  role_id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  canonical_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genders (
  gender_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS territories (
  territory_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT,
  level TEXT,
  parent_territory_id INTEGER REFERENCES territories(territory_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'error')),
  source_url TEXT NOT NULL,
  raw_path TEXT,
  fetched_at TEXT,
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_loaded INTEGER NOT NULL DEFAULT 0,
  message TEXT
);

CREATE TABLE IF NOT EXISTS raw_fetches (
  fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER REFERENCES ingestion_runs(run_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  content_type TEXT,
  bytes INTEGER NOT NULL,
  UNIQUE (source_id, content_sha256)
);

-- Per-run fetch metadata (one row per ingestion run).
-- raw_fetches is de-duped by (source_id, content_sha256) for traceability of payloads;
-- this table keeps the run_id -> source_url mapping stable for ops dashboards.
CREATE TABLE IF NOT EXISTS run_fetches (
  run_id INTEGER PRIMARY KEY REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  content_type TEXT,
  bytes INTEGER NOT NULL
);

-- Durable, bounded work queue shared by high-volume acquisition and transform
-- pipelines. Payloads contain references only; raw bytes stay outside SQLite.
CREATE TABLE IF NOT EXISTS pipeline_work_items (
  work_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT NOT NULL,
  item_key TEXT NOT NULL,
  partition_key TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
  payload_json TEXT NOT NULL DEFAULT '{}',
  available_at TEXT NOT NULL,
  lease_owner TEXT,
  lease_expires_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE (pipeline_id, item_key)
);

CREATE TABLE IF NOT EXISTS pipeline_work_attempts (
  work_attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_item_id INTEGER NOT NULL
    REFERENCES pipeline_work_items(work_item_id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL,
  worker_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'succeeded', 'retry', 'dead', 'lease_expired')),
  error TEXT,
  UNIQUE (work_item_id, attempt_number)
);

-- Durable request accounting for document fetches. One row records the exact
-- number of network requests performed by one queue attempt, including bounded
-- in-item HTTP retries. This survives worker restarts and supports cumulative
-- telemetry across resumed runs without retaining response bodies in SQLite.
CREATE TABLE IF NOT EXISTS document_fetch_request_events (
  document_fetch_request_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_item_id INTEGER NOT NULL
    REFERENCES pipeline_work_items(work_item_id) ON DELETE CASCADE,
  pipeline_id TEXT NOT NULL,
  queue_attempt_number INTEGER NOT NULL CHECK (queue_attempt_number >= 1),
  worker_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_host TEXT NOT NULL,
  outcome_state TEXT NOT NULL
    CHECK (outcome_state IN ('succeeded', 'failed')),
  network_requests_started INTEGER NOT NULL
    CHECK (network_requests_started >= 0),
  http_status INTEGER,
  failure_class TEXT,
  bytes_received INTEGER NOT NULL DEFAULT 0 CHECK (bytes_received >= 0),
  recorded_at TEXT NOT NULL,
  UNIQUE (work_item_id, queue_attempt_number)
);

CREATE TABLE IF NOT EXISTS persons (
  person_id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name TEXT NOT NULL,
  given_name TEXT,
  family_name TEXT,
  gender TEXT,
  gender_id INTEGER REFERENCES genders(gender_id),
  birth_date TEXT,
  territory_code TEXT NOT NULL DEFAULT '',
  territory_id INTEGER REFERENCES territories(territory_id),
  canonical_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS person_identifiers (
  person_identifier_id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  namespace TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (namespace, value)
);

CREATE TABLE IF NOT EXISTS person_name_aliases (
  person_name_alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  canonical_alias TEXT NOT NULL UNIQUE,
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_kind TEXT NOT NULL DEFAULT 'manual_seed',
  source_url TEXT,
  evidence_date TEXT,
  evidence_quote TEXT,
  confidence REAL,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parties (
  party_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  acronym TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS party_aliases (
  party_alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
  party_id INTEGER NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  canonical_alias TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS institutions (
  institution_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  level TEXT NOT NULL,
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_code TEXT NOT NULL DEFAULT '',
  territory_id INTEGER REFERENCES territories(territory_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (name, level, territory_code)
);

CREATE TABLE IF NOT EXISTS source_records (
  source_record_pk INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id)
);

-- Organigrama público: unidades oficiales y dependencias orgánicas.
-- DIR3 is the source-of-truth backbone; BOE/Transparencia can enrich positions
-- and named office holders without overwriting this structural layer.
CREATE TABLE IF NOT EXISTS government_org_units (
  org_unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  source_record_id TEXT NOT NULL,
  org_unit_code TEXT NOT NULL,
  org_unit_version TEXT,
  name TEXT NOT NULL,
  normalized_name TEXT,
  administration_level TEXT,
  administration_name TEXT,
  ministry_name TEXT,
  entity_type_code TEXT,
  entity_type_label TEXT,
  unit_type_code TEXT,
  unit_type_label TEXT,
  organic_level INTEGER,
  status TEXT,
  valid_from TEXT,
  valid_to TEXT,
  source_url TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, org_unit_code)
);

CREATE TABLE IF NOT EXISTS government_org_relationships (
  org_relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN ('depends_on', 'attached_to', 'reports_to', 'appoints', 'delegates_to', 'audits')
  ),
  subject_org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE CASCADE,
  object_org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE CASCADE,
  subject_org_unit_code TEXT NOT NULL,
  object_org_unit_code TEXT NOT NULL,
  evidence_date TEXT,
  source_url TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, subject_org_unit_code, relationship_type, object_org_unit_code)
);

CREATE TABLE IF NOT EXISTS government_positions (
  position_id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  position_code TEXT,
  title TEXT NOT NULL,
  position_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    position_kind IN ('political_appointee', 'civil_service', 'elected', 'employment', 'unknown')
  ),
  is_top_responsible INTEGER NOT NULL DEFAULT 0 CHECK (is_top_responsible IN (0, 1)),
  source_url TEXT,
  raw_payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (org_unit_id, title, position_kind, position_code)
);

CREATE TABLE IF NOT EXISTS person_org_memberships (
  membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  membership_kind TEXT NOT NULL CHECK (
    membership_kind IN ('public_position', 'public_employment', 'party', 'parliamentary_group', 'other')
  ),
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  position_id INTEGER REFERENCES government_positions(position_id) ON DELETE SET NULL,
  role_label TEXT,
  start_date TEXT,
  end_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  source_kind TEXT NOT NULL DEFAULT 'official_source',
  source_url TEXT,
  evidence_date TEXT,
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (person_id, membership_kind, org_unit_id, party_id, position_id, role_label, start_date, source_url)
);

CREATE TABLE IF NOT EXISTS parliamentary_groups (
  parliamentary_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  legislature TEXT,
  group_code TEXT NOT NULL,
  name TEXT NOT NULL,
  normalized_name TEXT,
  source_url TEXT,
  raw_payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, legislature, group_code)
);

CREATE TABLE IF NOT EXISTS person_parliamentary_group_memberships (
  membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  parliamentary_group_id INTEGER NOT NULL REFERENCES parliamentary_groups(parliamentary_group_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  legislature TEXT,
  start_date TEXT,
  end_date TEXT,
  source_url TEXT,
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (person_id, parliamentary_group_id, source_id, start_date)
);

CREATE TABLE IF NOT EXISTS mandates (
  mandate_id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id),
  institution_id INTEGER NOT NULL REFERENCES institutions(institution_id),
  party_id INTEGER REFERENCES parties(party_id),
  role_title TEXT NOT NULL,
  role_id INTEGER REFERENCES roles(role_id),
  level TEXT NOT NULL,
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_code TEXT NOT NULL DEFAULT '',
  territory_id INTEGER REFERENCES territories(territory_id),
  start_date TEXT,
  end_date TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT NOT NULL,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  raw_payload TEXT NOT NULL,
  UNIQUE (source_id, source_record_id)
);

-- Time-aware actor graph. Source-scoped nodes are the safe default; a
-- cross-source identity requires an exact official identifier or a reviewed,
-- evidence-backed resolution decision. All changes are append-only by release.
CREATE TABLE IF NOT EXISTS actor_graph_releases (
  release_id TEXT PRIMARY KEY,
  snapshot_date TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  source_semantic_sha256 TEXT NOT NULL,
  source_mapping_semantic_sha256 TEXT NOT NULL,
  source_database_sha256 TEXT,
  input_manifest_sha256 TEXT,
  input_releases_json TEXT NOT NULL DEFAULT '{}',
  counts_json TEXT NOT NULL DEFAULT '{}',
  real_data_only INTEGER NOT NULL DEFAULT 1 CHECK (real_data_only IN (0, 1)),
  public_identity_retained INTEGER NOT NULL DEFAULT 1
    CHECK (public_identity_retained IN (0, 1)),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actor_graph_source_mappings (
  source_mapping_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  input_database_key TEXT NOT NULL,
  upstream_source_id TEXT NOT NULL,
  graph_source_id TEXT NOT NULL
    REFERENCES sources(source_id) ON DELETE RESTRICT,
  source_metadata_sha256 TEXT NOT NULL,
  mapping_reason TEXT NOT NULL CHECK (
    mapping_reason IN (
      'unique_upstream_id', 'identical_metadata',
      'metadata_conflict_namespaced'
    )
  ),
  created_at TEXT NOT NULL,
  UNIQUE (release_id, input_database_key, upstream_source_id)
);

CREATE TABLE IF NOT EXISTS actor_graph_nodes (
  actor_id TEXT PRIMARY KEY,
  actor_kind TEXT NOT NULL CHECK (
    actor_kind IN ('person', 'organization', 'office', 'collective', 'unknown')
  ),
  actor_subtype TEXT NOT NULL,
  identity_scope TEXT NOT NULL CHECK (
    identity_scope IN ('source_scoped', 'resolved')
  ),
  source_scope_id TEXT NOT NULL,
  stable_source_key TEXT NOT NULL,
  first_release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  UNIQUE (actor_kind, source_scope_id, stable_source_key)
);

CREATE TABLE IF NOT EXISTS actor_graph_node_versions (
  node_version_id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  canonical_label TEXT NOT NULL,
  normalized_label TEXT,
  identity_state TEXT NOT NULL CHECK (
    identity_state IN (
      'source_scoped', 'resolved', 'disputed', 'superseded', 'unresolved'
    )
  ),
  valid_from TEXT,
  valid_to TEXT,
  observed_at TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  provenance_state TEXT NOT NULL CHECK (
    provenance_state IN (
      'exact_record', 'exact_document', 'source_default',
      'normalized_registry', 'missing'
    )
  ),
  attributes_json TEXT NOT NULL DEFAULT '{}',
  supersedes_node_version_id TEXT
    REFERENCES actor_graph_node_versions(node_version_id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  UNIQUE (actor_id, release_id)
);

CREATE TABLE IF NOT EXISTS actor_graph_identifier_versions (
  identifier_version_id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  namespace TEXT NOT NULL,
  value TEXT NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  observed_at TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_content_sha256 TEXT,
  provenance_state TEXT NOT NULL CHECK (
    provenance_state IN (
      'exact_record', 'exact_document', 'source_default',
      'normalized_registry', 'missing'
    )
  ),
  created_at TEXT NOT NULL,
  UNIQUE (actor_id, release_id, namespace, value)
);

CREATE TABLE IF NOT EXISTS actor_graph_alias_versions (
  alias_version_id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  alias TEXT NOT NULL,
  normalized_alias TEXT NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  observed_at TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  provenance_state TEXT NOT NULL CHECK (
    provenance_state IN (
      'exact_record', 'exact_document', 'source_default',
      'normalized_registry', 'missing'
    )
  ),
  created_at TEXT NOT NULL,
  UNIQUE (actor_id, release_id, normalized_alias, alias)
);

CREATE TABLE IF NOT EXISTS actor_graph_relationships (
  relationship_id TEXT PRIMARY KEY,
  subject_actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN (
      'holds_role_at', 'affiliated_with_party', 'candidate_for',
      'effective_candidate_for', 'elected_in',
      'member_of_parliamentary_group', 'member_of_organization',
      'acts_in_spending_item', 'party_to_agreement',
      'participates_in_meeting', 'acts_in_geopolitical_action',
      'publishes_manifesto', 'member_of_coalition',
      'predecessor_of', 'successor_of'
    )
  ),
  object_actor_id TEXT
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  context_kind TEXT NOT NULL,
  context_id TEXT NOT NULL,
  created_release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  UNIQUE (
    subject_actor_id, relationship_type, object_actor_id,
    context_kind, context_id
  )
);

CREATE TABLE IF NOT EXISTS actor_graph_relationship_versions (
  relationship_version_id TEXT PRIMARY KEY,
  relationship_id TEXT NOT NULL
    REFERENCES actor_graph_relationships(relationship_id) ON DELETE CASCADE,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  role_label TEXT,
  valid_from TEXT,
  valid_to TEXT,
  observed_at TEXT NOT NULL,
  is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1)),
  resolution_state TEXT NOT NULL CHECK (
    resolution_state IN (
      'source_scoped', 'exact_identifier_match', 'reviewed_match',
      'reviewed_no_match', 'conflict', 'unresolved', 'superseded'
    )
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  supersedes_relationship_version_id TEXT
    REFERENCES actor_graph_relationship_versions(relationship_version_id)
    ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  UNIQUE (relationship_id, release_id)
);

CREATE TABLE IF NOT EXISTS actor_graph_relationship_evidence (
  relationship_evidence_id TEXT PRIMARY KEY,
  relationship_version_id TEXT NOT NULL
    REFERENCES actor_graph_relationship_versions(relationship_version_id)
    ON DELETE CASCADE,
  evidence_kind TEXT NOT NULL CHECK (
    evidence_kind IN (
      'exact_record', 'exact_document', 'source_default',
      'normalized_registry', 'missing'
    )
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  source_locator TEXT NOT NULL,
  exact_quote TEXT,
  observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (relationship_version_id, source_locator)
);

CREATE TABLE IF NOT EXISTS actor_resolution_decisions (
  resolution_decision_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  source_actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  candidate_actor_id TEXT
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  outcome TEXT NOT NULL CHECK (
    outcome IN (
      'source_scoped', 'exact_identifier_match', 'reviewed_match',
      'reviewed_no_match', 'conflict', 'unresolved', 'superseded'
    )
  ),
  method TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK (
    confidence IN ('not_scored', 'exact', 'reviewed', 'conflict')
  ),
  decided_by_kind TEXT NOT NULL CHECK (
    decided_by_kind IN ('system_exact', 'human_reviewer', 'imported_source')
  ),
  decided_by TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  rationale TEXT NOT NULL,
  supersedes_decision_id TEXT
    REFERENCES actor_resolution_decisions(resolution_decision_id)
    ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  UNIQUE (release_id, source_actor_id, candidate_actor_id, outcome, method)
);

CREATE TABLE IF NOT EXISTS actor_resolution_evidence (
  resolution_evidence_id TEXT PRIMARY KEY,
  resolution_decision_id TEXT NOT NULL
    REFERENCES actor_resolution_decisions(resolution_decision_id)
    ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  source_locator TEXT NOT NULL,
  exact_quote TEXT,
  observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (resolution_decision_id, source_locator)
);

CREATE TABLE IF NOT EXISTS actor_organization_change_events (
  organization_change_event_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL
    REFERENCES actor_graph_releases(release_id) ON DELETE RESTRICT,
  event_type TEXT NOT NULL CHECK (
    event_type IN (
      'renamed', 'merged_into', 'split_into', 'absorbed_by',
      'superseded_by', 'founded', 'dissolved'
    )
  ),
  subject_actor_id TEXT NOT NULL
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  object_actor_id TEXT
    REFERENCES actor_graph_nodes(actor_id) ON DELETE CASCADE,
  effective_date TEXT,
  effective_date_state TEXT NOT NULL CHECK (
    effective_date_state IN ('exact', 'partial', 'unknown')
  ),
  observed_at TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT,
  source_url TEXT,
  source_content_sha256 TEXT,
  supersedes_event_id TEXT
    REFERENCES actor_organization_change_events(organization_change_event_id)
    ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actor_organization_change_evidence (
  organization_change_evidence_id TEXT PRIMARY KEY,
  organization_change_event_id TEXT NOT NULL
    REFERENCES actor_organization_change_events(organization_change_event_id)
    ON DELETE CASCADE,
  source_locator TEXT NOT NULL,
  exact_quote TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (organization_change_event_id, source_locator)
);

CREATE INDEX IF NOT EXISTS idx_actor_graph_nodes_scope
ON actor_graph_nodes(source_scope_id, actor_kind, actor_subtype, stable_source_key);
CREATE INDEX IF NOT EXISTS idx_actor_graph_source_mappings_upstream
ON actor_graph_source_mappings(
  upstream_source_id, input_database_key, release_id
);
CREATE INDEX IF NOT EXISTS idx_actor_graph_source_mappings_graph
ON actor_graph_source_mappings(graph_source_id, release_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_node_versions_release_kind
ON actor_graph_node_versions(release_id, identity_state, actor_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_node_versions_label
ON actor_graph_node_versions(normalized_label, actor_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_identifiers_lookup
ON actor_graph_identifier_versions(namespace, value, release_id, actor_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_aliases_lookup
ON actor_graph_alias_versions(normalized_alias, release_id, actor_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_relationships_subject
ON actor_graph_relationships(subject_actor_id, relationship_type, context_kind, context_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_relationships_object
ON actor_graph_relationships(object_actor_id, relationship_type, context_kind, context_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_relationship_versions_release_time
ON actor_graph_relationship_versions(release_id, source_id, valid_from, valid_to, relationship_id);
CREATE INDEX IF NOT EXISTS idx_actor_graph_resolution_source
ON actor_resolution_decisions(source_actor_id, observed_at, outcome);
CREATE INDEX IF NOT EXISTS idx_actor_graph_resolution_candidate
ON actor_resolution_decisions(candidate_actor_id, observed_at, outcome);
CREATE INDEX IF NOT EXISTS idx_actor_org_change_subject_time
ON actor_organization_change_events(subject_actor_id, effective_date, event_type);

-- Electoral: Infoelectoral (area de descargas)
CREATE TABLE IF NOT EXISTS infoelectoral_convocatoria_tipos (
  tipo_convocatoria TEXT PRIMARY KEY,
  descripcion TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS infoelectoral_convocatorias (
  convocatoria_id TEXT PRIMARY KEY,
  tipo_convocatoria TEXT NOT NULL REFERENCES infoelectoral_convocatoria_tipos(tipo_convocatoria),
  cod TEXT NOT NULL,
  fecha TEXT,
  descripcion TEXT,
  ambito_territorio TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tipo_convocatoria, cod)
);

CREATE TABLE IF NOT EXISTS infoelectoral_archivos_extraccion (
  archivo_id TEXT PRIMARY KEY,
  convocatoria_id TEXT NOT NULL REFERENCES infoelectoral_convocatorias(convocatoria_id) ON DELETE CASCADE,
  tipo_convocatoria TEXT NOT NULL REFERENCES infoelectoral_convocatoria_tipos(tipo_convocatoria),
  id_convocatoria TEXT NOT NULL,
  descripcion TEXT,
  nombre_doc TEXT NOT NULL,
  ambito TEXT,
  download_url TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (convocatoria_id, nombre_doc)
);

CREATE TABLE IF NOT EXISTS infoelectoral_procesos (
  proceso_id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  tipo TEXT,
  ambito TEXT,
  estado TEXT,
  fecha TEXT,
  detalle_url TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS infoelectoral_proceso_resultados (
  proceso_dataset_id TEXT PRIMARY KEY,
  proceso_id TEXT NOT NULL REFERENCES infoelectoral_procesos(proceso_id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  tipo_dato TEXT,
  url TEXT NOT NULL,
  formato TEXT,
  fecha TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (proceso_id, url)
);

-- Electoral: named historical elected officials from official XLSX datasets.
-- Rows are election outcomes. They do not assert current-office status or
-- cross-election person identity.
CREATE TABLE IF NOT EXISTS infoelectoral_elected_officials (
  elected_official_id TEXT PRIMARY KEY,
  election_date TEXT NOT NULL,
  election_code TEXT NOT NULL,
  chamber TEXT NOT NULL CHECK (chamber IN ('congreso', 'senado')),
  province_code TEXT NOT NULL,
  province_name TEXT NOT NULL,
  district TEXT,
  constituency TEXT,
  full_name TEXT NOT NULL,
  candidacy_name TEXT NOT NULL,
  candidacy_acronym TEXT,
  votes INTEGER CHECK (votes IS NULL OR votes >= 0),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk),
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_row_number INTEGER NOT NULL CHECK (source_row_number >= 1),
  person_id INTEGER REFERENCES persons(person_id),
  mandate_id INTEGER REFERENCES mandates(mandate_id),
  party_id INTEGER REFERENCES parties(party_id),
  institution_id INTEGER REFERENCES institutions(institution_id),
  role_id INTEGER REFERENCES roles(role_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  first_seen_snapshot_date TEXT NOT NULL DEFAULT '',
  last_seen_snapshot_date TEXT NOT NULL DEFAULT '',
  is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1)),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Append-only workbook sightings. Stable facts above retain the latest observed
-- payload while this table proves snapshot/content/run history without raw copies.
CREATE TABLE IF NOT EXISTS infoelectoral_elected_official_observations (
  elected_official_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  elected_official_id TEXT NOT NULL
    REFERENCES infoelectoral_elected_officials(elected_official_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk),
  run_id INTEGER REFERENCES ingestion_runs(run_id),
  snapshot_date TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_row_number INTEGER NOT NULL CHECK (source_row_number >= 1),
  row_content_sha256 TEXT NOT NULL,
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  UNIQUE (elected_official_id, snapshot_date, source_content_sha256)
);

-- Electoral: official fixed-width candidate archives discovered through the
-- Infoelectoral download catalog. Public-domain candidate identity fields remain
-- traceable to the exact official archive and source line.
CREATE TABLE IF NOT EXISTS infoelectoral_candidate_archives (
  archive_id TEXT PRIMARY KEY,
  election_id TEXT NOT NULL,
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  source_url TEXT NOT NULL UNIQUE,
  source_content_sha256 TEXT,
  archive_bytes INTEGER CHECK (archive_bytes IS NULL OR archive_bytes >= 0),
  raw_path TEXT,
  candidate_rows INTEGER NOT NULL DEFAULT 0 CHECK (candidate_rows >= 0),
  party_rows INTEGER NOT NULL DEFAULT 0 CHECK (party_rows >= 0),
  status TEXT NOT NULL DEFAULT 'cataloged'
    CHECK (status IN ('cataloged', 'validated', 'loaded', 'failed')),
  last_error TEXT,
  first_seen_snapshot_date TEXT NOT NULL,
  last_seen_snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS infoelectoral_candidate_occurrences (
  candidate_occurrence_id TEXT PRIMARY KEY,
  archive_id TEXT NOT NULL
    REFERENCES infoelectoral_candidate_archives(archive_id),
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  election_year INTEGER NOT NULL CHECK (election_year BETWEEN 1900 AND 2200),
  election_month INTEGER NOT NULL CHECK (election_month BETWEEN 1 AND 12),
  election_round TEXT NOT NULL,
  province_code TEXT NOT NULL,
  district_code TEXT NOT NULL,
  candidate_scope_code TEXT NOT NULL,
  party_source_code TEXT NOT NULL,
  candidate_order INTEGER NOT NULL CHECK (candidate_order >= 0),
  candidate_type_code TEXT NOT NULL,
  given_name TEXT NOT NULL,
  surname_1 TEXT NOT NULL,
  surname_2 TEXT,
  full_name TEXT NOT NULL,
  gender_code TEXT,
  birth_date TEXT,
  birth_date_source TEXT,
  dni TEXT,
  is_elected INTEGER NOT NULL DEFAULT 0 CHECK (is_elected IN (0, 1)),
  candidacy_name TEXT NOT NULL,
  candidacy_acronym TEXT,
  party_province_code TEXT,
  party_autonomy_code TEXT,
  party_national_code TEXT,
  person_id INTEGER NOT NULL REFERENCES persons(person_id),
  party_id INTEGER NOT NULL REFERENCES parties(party_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk),
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_member_name TEXT NOT NULL,
  source_line_number INTEGER NOT NULL CHECK (source_line_number >= 1),
  first_seen_snapshot_date TEXT NOT NULL,
  last_seen_snapshot_date TEXT NOT NULL,
  is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1)),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS infoelectoral_candidate_observations (
  candidate_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_occurrence_id TEXT NOT NULL
    REFERENCES infoelectoral_candidate_occurrences(candidate_occurrence_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk),
  run_id INTEGER REFERENCES ingestion_runs(run_id),
  snapshot_date TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_member_name TEXT NOT NULL,
  source_line_number INTEGER NOT NULL CHECK (source_line_number >= 1),
  row_content_sha256 TEXT NOT NULL,
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  UNIQUE (candidate_occurrence_id, snapshot_date, source_content_sha256)
);

-- Electoral: candidate proclamations published as immutable BOE documents.
-- This lane remains source-scoped. It never infers that a matching name is the
-- same person in another election or source, and it preserves the exact public
-- paragraph alongside the parsed public name.
CREATE TABLE IF NOT EXISTS boe_election_candidate_documents (
  document_id TEXT PRIMARY KEY,
  election_id TEXT NOT NULL,
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  publication_date TEXT NOT NULL,
  title TEXT NOT NULL,
  document_source_record_pk INTEGER NOT NULL UNIQUE
    REFERENCES source_records(source_record_pk),
  source_url TEXT NOT NULL UNIQUE,
  source_content_sha256 TEXT NOT NULL,
  source_bytes INTEGER NOT NULL CHECK (source_bytes > 0),
  raw_path TEXT NOT NULL,
  correction_state TEXT NOT NULL
    CHECK (correction_state IN ('none_declared', 'pending', 'applied')),
  correction_refs_json TEXT NOT NULL DEFAULT '[]',
  candidacy_rows INTEGER NOT NULL DEFAULT 0 CHECK (candidacy_rows >= 0),
  candidate_rows INTEGER NOT NULL DEFAULT 0 CHECK (candidate_rows >= 0),
  parser_version TEXT NOT NULL,
  first_seen_snapshot_date TEXT NOT NULL,
  last_seen_snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boe_election_candidacies (
  candidacy_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  electoral_board TEXT NOT NULL DEFAULT '',
  electoral_district TEXT NOT NULL DEFAULT '',
  chamber_code TEXT NOT NULL,
  candidacy_number INTEGER NOT NULL CHECK (candidacy_number >= 1),
  candidacy_name TEXT NOT NULL,
  source_text_exact TEXT NOT NULL,
  proclamation_status TEXT NOT NULL
    CHECK (proclamation_status IN ('proclaimed', 'not_proclaimed')),
  source_paragraph_number INTEGER NOT NULL
    CHECK (source_paragraph_number >= 1),
  party_id INTEGER REFERENCES parties(party_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    document_id, electoral_board, electoral_district, chamber_code,
    candidacy_number
  )
);

CREATE TABLE IF NOT EXISTS boe_election_candidate_occurrences (
  candidate_occurrence_id TEXT PRIMARY KEY,
  candidacy_id TEXT NOT NULL REFERENCES boe_election_candidacies(candidacy_id),
  document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  election_id TEXT NOT NULL,
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  electoral_board TEXT NOT NULL DEFAULT '',
  electoral_district TEXT NOT NULL DEFAULT '',
  chamber_code TEXT NOT NULL,
  candidacy_number INTEGER NOT NULL CHECK (candidacy_number >= 1),
  candidate_order INTEGER NOT NULL CHECK (candidate_order >= 1),
  candidate_type_code TEXT NOT NULL
    CHECK (candidate_type_code IN ('titular', 'suplente')),
  substitute_for_candidate_order INTEGER
    CHECK (
      substitute_for_candidate_order IS NULL
      OR substitute_for_candidate_order >= 1
    ),
  full_name TEXT NOT NULL,
  source_text_exact TEXT NOT NULL,
  person_id INTEGER NOT NULL REFERENCES persons(person_id),
  party_id INTEGER NOT NULL REFERENCES parties(party_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL UNIQUE REFERENCES source_records(source_record_pk),
  document_source_record_pk INTEGER NOT NULL
    REFERENCES source_records(source_record_pk),
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_paragraph_number INTEGER NOT NULL
    CHECK (source_paragraph_number >= 1),
  row_content_sha256 TEXT NOT NULL,
  first_seen_snapshot_date TEXT NOT NULL,
  last_seen_snapshot_date TEXT NOT NULL,
  is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1)),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    candidacy_id, candidate_type_code, candidate_order,
    substitute_for_candidate_order
  )
);

-- Immutable correction evidence. Paragraphs remain exact and unapplied until a
-- correction materializer proves the affected candidate slots and resulting
-- effective election snapshot.
CREATE TABLE IF NOT EXISTS boe_election_candidate_correction_documents (
  correction_document_id TEXT PRIMARY KEY,
  publication_date TEXT NOT NULL,
  title TEXT NOT NULL,
  document_source_record_pk INTEGER NOT NULL UNIQUE
    REFERENCES source_records(source_record_pk),
  source_url TEXT NOT NULL UNIQUE,
  source_content_sha256 TEXT NOT NULL,
  source_bytes INTEGER NOT NULL CHECK (source_bytes > 0),
  raw_path TEXT NOT NULL,
  paragraph_rows INTEGER NOT NULL CHECK (paragraph_rows >= 1),
  application_state TEXT NOT NULL
    CHECK (application_state IN ('captured_unapplied', 'applied')),
  parser_version TEXT NOT NULL,
  first_seen_snapshot_date TEXT NOT NULL,
  last_seen_snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boe_election_candidate_correction_targets (
  correction_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_correction_documents(
      correction_document_id
    ),
  base_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  relation_basis TEXT NOT NULL
    CHECK (relation_basis IN ('official_metadata', 'correction_body_scope')),
  created_at TEXT NOT NULL,
  PRIMARY KEY (correction_document_id, base_document_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS boe_election_candidate_correction_paragraphs (
  correction_paragraph_id TEXT PRIMARY KEY,
  correction_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_correction_documents(
      correction_document_id
    ),
  source_paragraph_number INTEGER NOT NULL
    CHECK (source_paragraph_number >= 1),
  source_css_class TEXT NOT NULL,
  source_text_exact TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  semantic_marker TEXT NOT NULL,
  electoral_board TEXT NOT NULL DEFAULT '',
  electoral_district TEXT NOT NULL DEFAULT '',
  chamber_code TEXT NOT NULL DEFAULT '',
  candidacy_number INTEGER CHECK (candidacy_number IS NULL OR candidacy_number >= 1),
  created_at TEXT NOT NULL,
  UNIQUE (correction_document_id, source_paragraph_number)
) WITHOUT ROWID;

-- Validated semantic effects derived from immutable official correction text.
-- Base proclamation rows are never updated or deleted. before_value_json and
-- after_value_json make every materialized change independently reconstructable.
CREATE TABLE IF NOT EXISTS boe_election_candidate_correction_operations (
  correction_operation_id TEXT PRIMARY KEY,
  correction_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_correction_documents(
      correction_document_id
    ),
  base_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  candidacy_id TEXT NOT NULL REFERENCES boe_election_candidacies(candidacy_id),
  operation_order INTEGER NOT NULL CHECK (operation_order >= 1),
  operation_type TEXT NOT NULL
    CHECK (operation_type IN (
      'replace_candidacy_name',
      'replace_candidate_slot',
      'replace_candidate_list',
      'replace_candidacy_status_and_list'
    )),
  base_match_state TEXT NOT NULL
    CHECK (base_match_state IN (
      'before_matches',
      'already_effective_after_matches',
      'partial_base_matches',
      'replacement_scope_matches'
    )),
  candidate_type_code TEXT
    CHECK (
      candidate_type_code IS NULL
      OR candidate_type_code IN ('titular', 'suplente', 'all')
    ),
  candidate_order INTEGER
    CHECK (candidate_order IS NULL OR candidate_order >= 1),
  substitute_for_candidate_order INTEGER
    CHECK (
      substitute_for_candidate_order IS NULL
      OR substitute_for_candidate_order >= 1
    ),
  before_value_json TEXT NOT NULL,
  after_value_json TEXT NOT NULL,
  evidence_paragraph_numbers_json TEXT NOT NULL,
  evidence_text_sha256 TEXT NOT NULL,
  materializer_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (correction_document_id, base_document_id, operation_order)
);

-- Current effective candidacy state. Original proclamation state remains in
-- boe_election_candidacies; correction_operation_id points to the last change.
CREATE TABLE IF NOT EXISTS boe_election_effective_candidacies (
  candidacy_id TEXT PRIMARY KEY REFERENCES boe_election_candidacies(candidacy_id),
  base_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  election_id TEXT NOT NULL,
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  electoral_board TEXT NOT NULL DEFAULT '',
  electoral_district TEXT NOT NULL DEFAULT '',
  chamber_code TEXT NOT NULL,
  candidacy_number INTEGER NOT NULL CHECK (candidacy_number >= 1),
  candidacy_name TEXT NOT NULL,
  party_id INTEGER REFERENCES parties(party_id),
  proclamation_status TEXT NOT NULL
    CHECK (proclamation_status IN ('proclaimed', 'not_proclaimed')),
  effective_source_document_id TEXT NOT NULL,
  effective_source_url TEXT NOT NULL,
  effective_source_content_sha256 TEXT NOT NULL,
  source_text_exact TEXT NOT NULL,
  source_paragraph_number INTEGER NOT NULL
    CHECK (source_paragraph_number >= 1),
  correction_operation_id TEXT
    REFERENCES boe_election_candidate_correction_operations(
      correction_operation_id
    ),
  materialized_at TEXT NOT NULL
);

-- Current effective source-scoped candidate slots. Corrected rows remain exact
-- public evidence and do not imply identity equivalence with another source.
CREATE TABLE IF NOT EXISTS boe_election_effective_candidate_occurrences (
  effective_candidate_occurrence_id TEXT PRIMARY KEY,
  candidacy_id TEXT NOT NULL
    REFERENCES boe_election_effective_candidacies(candidacy_id),
  base_candidate_occurrence_id TEXT
    REFERENCES boe_election_candidate_occurrences(candidate_occurrence_id),
  base_document_id TEXT NOT NULL
    REFERENCES boe_election_candidate_documents(document_id),
  election_id TEXT NOT NULL,
  election_date TEXT NOT NULL,
  election_type_code TEXT NOT NULL,
  electoral_board TEXT NOT NULL DEFAULT '',
  electoral_district TEXT NOT NULL DEFAULT '',
  chamber_code TEXT NOT NULL,
  candidacy_number INTEGER NOT NULL CHECK (candidacy_number >= 1),
  candidate_order INTEGER NOT NULL CHECK (candidate_order >= 1),
  candidate_type_code TEXT NOT NULL
    CHECK (candidate_type_code IN ('titular', 'suplente')),
  substitute_for_candidate_order INTEGER
    CHECK (
      substitute_for_candidate_order IS NULL
      OR substitute_for_candidate_order >= 1
    ),
  full_name TEXT NOT NULL,
  person_id INTEGER REFERENCES persons(person_id),
  party_id INTEGER REFERENCES parties(party_id),
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER UNIQUE REFERENCES source_records(source_record_pk),
  document_source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  effective_source_document_id TEXT NOT NULL,
  effective_source_url TEXT NOT NULL,
  effective_source_content_sha256 TEXT NOT NULL,
  source_text_exact TEXT NOT NULL,
  source_paragraph_number INTEGER NOT NULL
    CHECK (source_paragraph_number >= 1),
  correction_operation_id TEXT
    REFERENCES boe_election_candidate_correction_operations(
      correction_operation_id
    ),
  row_content_sha256 TEXT NOT NULL,
  first_seen_snapshot_date TEXT,
  last_seen_snapshot_date TEXT,
  is_present INTEGER CHECK (is_present IN (0, 1)),
  person_identity_state TEXT
    CHECK (
      person_identity_state IS NULL
      OR person_identity_state IN (
        'source_scoped_base_exact',
        'source_scoped_correction_exact'
      )
    ),
  materialized_at TEXT NOT NULL,
  UNIQUE (
    candidacy_id, candidate_type_code, candidate_order,
    substitute_for_candidate_order
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_boe_effective_candidate_source_record
  ON boe_election_effective_candidate_occurrences(source_record_pk)
  WHERE source_record_pk IS NOT NULL;

-- Parlamentario: votaciones (roll-call cuando exista)
CREATE TABLE IF NOT EXISTS parl_vote_events (
  vote_event_id TEXT PRIMARY KEY,
  legislature TEXT,
  session_number INTEGER,
  vote_number INTEGER,
  vote_date TEXT,
  title TEXT,
  expediente_text TEXT,
  subgroup_title TEXT,
  subgroup_text TEXT,
  assentimiento TEXT,
  totals_present INTEGER,
  totals_yes INTEGER,
  totals_no INTEGER,
  totals_abstain INTEGER,
  totals_no_vote INTEGER,
  totals_absent INTEGER,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parl_vote_member_votes (
  member_vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  seat TEXT,
  member_name TEXT,
  member_name_normalized TEXT,
  person_id INTEGER REFERENCES persons(person_id),
  group_code TEXT,
  parliamentary_group_id INTEGER REFERENCES parliamentary_groups(parliamentary_group_id) ON DELETE SET NULL,
  vote_choice TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (vote_event_id, seat)
);

-- Parlamentario: iniciativas (temas/expedientes con identificador estable)
CREATE TABLE IF NOT EXISTS parl_initiatives (
  initiative_id TEXT PRIMARY KEY,
  legislature TEXT,
  expediente TEXT,
  supertype TEXT,
  grouping TEXT,
  type TEXT,
  title TEXT,
  presented_date TEXT,
  qualified_date TEXT,
  author_text TEXT,
  procedure_type TEXT,
  result_text TEXT,
  current_status TEXT,
  competent_committee TEXT,
  deadlines_text TEXT,
  rapporteurs_text TEXT,
  processing_text TEXT,
  related_initiatives_text TEXT,
  links_bocg_json TEXT,
  links_ds_json TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, legislature, expediente)
);

-- Initiative -> document URLs (BOCG / Diario de Sesiones / PDFs / etc).
-- This lets Explorer (and citizen UI exports) enumerate evidence artifacts deterministically.
CREATE TABLE IF NOT EXISTS parl_initiative_documents (
  initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  doc_kind TEXT NOT NULL,
  doc_url TEXT NOT NULL,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (initiative_id, doc_kind, doc_url)
);

-- Versioned initiative texts: explicit snapshots of the bill/dossier text as published.
-- Minimal contract for "what text existed when this vote happened?" reasoning.
CREATE TABLE IF NOT EXISTS parl_initiative_text_versions (
  initiative_text_version_id TEXT PRIMARY KEY,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  chamber TEXT NOT NULL CHECK (chamber IN ('congreso', 'senado', 'boe', 'unknown')),
  doc_kind TEXT NOT NULL,
  document_code TEXT,
  doc_series TEXT,
  doc_number TEXT,
  version_order INTEGER,
  published_date TEXT,
  stage_kind TEXT NOT NULL CHECK (
    stage_kind IN (
      'initial_text',
      'committee_report',
      'senate_amendments',
      'final_text',
      'subsequent_text',
      'convalidation_resolution',
      'derogation_resolution',
      'unknown'
    )
  ),
  stage_label TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  raw_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (initiative_id, source_record_pk),
  UNIQUE (initiative_id, source_url)
);

CREATE TABLE IF NOT EXISTS parl_vote_event_text_versions (
  parl_vote_event_text_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  initiative_text_version_id TEXT NOT NULL REFERENCES parl_initiative_text_versions(initiative_text_version_id) ON DELETE CASCADE,
  link_method TEXT NOT NULL CHECK (
    link_method IN (
      'single_version',
      'initial_version_for_intro_vote',
      'latest_prior_published_version',
      'latest_prior_stage_match',
      'fallback_latest_version',
      'manual'
    )
  ),
  confidence REAL,
  is_primary INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
  raw_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (vote_event_id, initiative_id, is_primary)
);

CREATE TABLE IF NOT EXISTS parl_text_fragments (
  fragment_id TEXT PRIMARY KEY,
  initiative_text_version_id TEXT NOT NULL REFERENCES parl_initiative_text_versions(initiative_text_version_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  fragment_order INTEGER NOT NULL,
  fragment_kind TEXT NOT NULL,
  fragment_label TEXT,
  char_start INTEGER,
  char_end INTEGER,
  fragment_text TEXT NOT NULL,
  text_hash TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parl_fragment_measure_reviews (
  fragment_id TEXT PRIMARY KEY REFERENCES parl_text_fragments(fragment_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  initiative_text_version_id TEXT NOT NULL REFERENCES parl_initiative_text_versions(initiative_text_version_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  status TEXT NOT NULL CHECK (status IN ('pending', 'resolved', 'ignored')) DEFAULT 'pending',
  note TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Link votes to initiatives when we can do it deterministically (or with explicit method+confidence).
CREATE TABLE IF NOT EXISTS parl_vote_event_initiatives (
  parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  link_method TEXT NOT NULL,
  confidence REAL,
  evidence_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (vote_event_id, initiative_id, link_method)
);

-- Analitica: temas (alto impacto por scope) + evidencia + posicionamiento reproducible.
-- Modelo: "position" es una agregacion (por persona + scope + tema + ventana) sobre evidencia auditable.
CREATE TABLE IF NOT EXISTS topic_sets (
  topic_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  -- Scope anchors: cualquier combinacion puede ser NULL (p.ej. set global o set por institucion).
  institution_id INTEGER REFERENCES institutions(institution_id),
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  legislature TEXT,
  valid_from TEXT,
  valid_to TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (name, institution_id, admin_level_id, territory_id, legislature)
);

CREATE TABLE IF NOT EXISTS topics (
  topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT,
  parent_topic_id INTEGER REFERENCES topics(topic_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Which topics are considered (and how "high-stakes" they are) inside a topic_set.
CREATE TABLE IF NOT EXISTS topic_set_topics (
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
);

-- Atomic evidence items supporting a stance (declared or revealed). Must be traceable to raw sources.
CREATE TABLE IF NOT EXISTS topic_evidence (
  evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER REFERENCES topics(topic_id),
  topic_set_id INTEGER REFERENCES topic_sets(topic_set_id),
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  mandate_id INTEGER REFERENCES mandates(mandate_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id),
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  evidence_type TEXT NOT NULL,
  evidence_date TEXT,
  title TEXT,
  excerpt TEXT,
  -- Canonical stance signal produced by the extractor/classifier for this evidence row.
  stance TEXT CHECK (stance IN ('support', 'oppose', 'mixed', 'unclear', 'no_signal')),
  polarity INTEGER CHECK (polarity IN (-1, 0, 1)),
  weight REAL,
  confidence REAL,
  topic_method TEXT,
  stance_method TEXT,
  -- Optional links to canonico parlamentario evidence.
  vote_event_id TEXT REFERENCES parl_vote_events(vote_event_id) ON DELETE SET NULL,
  initiative_id TEXT REFERENCES parl_initiatives(initiative_id) ON DELETE SET NULL,
  -- Provenance.
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Manual review queue for declared evidence rows that remain ambiguous after auto extraction.
-- Keep one row per evidence_id and track status transitions (pending/resolved/ignored).
CREATE TABLE IF NOT EXISTS topic_evidence_reviews (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  evidence_id INTEGER NOT NULL UNIQUE REFERENCES topic_evidence(evidence_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  review_reason TEXT NOT NULL CHECK (review_reason IN ('missing_text', 'no_signal', 'low_confidence', 'conflicting_signal')),
  status TEXT NOT NULL CHECK (status IN ('pending', 'resolved', 'ignored')) DEFAULT 'pending',
  suggested_stance TEXT CHECK (suggested_stance IN ('support', 'oppose', 'mixed', 'unclear', 'no_signal')),
  suggested_polarity INTEGER CHECK (suggested_polarity IN (-1, 0, 1)),
  suggested_confidence REAL,
  extractor_version TEXT,
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Queue of person-level public-data gaps detected by xray diagnostics.
-- One row per (person, gap_code, scope_key), with status transitions for manual/ops closure.
CREATE TABLE IF NOT EXISTS person_public_data_queue (
  person_public_data_queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_key TEXT NOT NULL UNIQUE,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  person_name TEXT NOT NULL,
  gap_code TEXT NOT NULL,
  scope_key TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 50,
  is_publicly_available INTEGER NOT NULL DEFAULT 1 CHECK (is_publicly_available IN (0, 1)),
  status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'resolved', 'ignored')) DEFAULT 'pending',
  rationale TEXT NOT NULL,
  next_action TEXT NOT NULL,
  suggested_source_id TEXT REFERENCES sources(source_id),
  suggested_source_url TEXT,
  detection_payload_json TEXT NOT NULL DEFAULT '{}',
  first_detected_at TEXT NOT NULL,
  last_detected_at TEXT NOT NULL,
  resolved_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (person_id, gap_code, scope_key)
);

-- Aggregated stance snapshot (recomputed deterministically from topic_evidence for a given window).
CREATE TABLE IF NOT EXISTS topic_positions (
  position_id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL REFERENCES topics(topic_id) ON DELETE CASCADE,
  topic_set_id INTEGER REFERENCES topic_sets(topic_set_id) ON DELETE SET NULL,
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  mandate_id INTEGER REFERENCES mandates(mandate_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id),
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  as_of_date TEXT NOT NULL,
  window_days INTEGER,
  stance TEXT NOT NULL CHECK (stance IN ('support', 'oppose', 'mixed', 'unclear', 'no_signal')),
  score REAL,
  confidence REAL,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  last_evidence_date TEXT,
  computed_method TEXT NOT NULL,
  computed_version TEXT NOT NULL,
  computed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (topic_id, person_id, mandate_id, as_of_date, computed_method, computed_version)
);

-- Text documents fetched for declared evidence (HTML/PDF/etc).
-- Keep raw bytes on disk; store only metadata + small excerpts in SQLite.
CREATE TABLE IF NOT EXISTS text_documents (
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
);

-- Canonical manifesto/commitment documents and their page-addressable claims.
-- Raw bytes and full extracted text stay outside SQLite; exact bounded quotes
-- remain here so every published claim is independently auditable.
CREATE TABLE IF NOT EXISTS manifesto_documents (
  manifesto_document_id TEXT PRIMARY KEY,
  text_document_id INTEGER REFERENCES text_documents(text_document_id) ON DELETE SET NULL,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  party_id INTEGER NOT NULL REFERENCES parties(party_id) ON DELETE RESTRICT,
  document_kind TEXT NOT NULL CHECK (document_kind IN (
    'manifesto','coalition_agreement','policy_platform',
    'investiture_agreement','other_official_commitment'
  )),
  title TEXT NOT NULL,
  election_key TEXT,
  jurisdiction TEXT,
  language TEXT,
  published_date TEXT,
  snapshot_date TEXT NOT NULL,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL CHECK (bytes > 0),
  page_count INTEGER CHECK (page_count IS NULL OR page_count > 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (party_id, election_key, source_url, content_sha256)
);

CREATE TABLE IF NOT EXISTS claim_extraction_runs (
  claim_extraction_run_id TEXT PRIMARY KEY,
  manifesto_document_id TEXT NOT NULL
    REFERENCES manifesto_documents(manifesto_document_id) ON DELETE CASCADE,
  pipeline_version TEXT NOT NULL,
  segmentation_version TEXT NOT NULL,
  topic_codebook_version TEXT NOT NULL,
  config_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','ok','error')),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  pages_seen INTEGER NOT NULL DEFAULT 0,
  segments_seen INTEGER NOT NULL DEFAULT 0,
  claims_loaded INTEGER NOT NULL DEFAULT 0,
  promises_loaded INTEGER NOT NULL DEFAULT 0,
  publishable_claims INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  UNIQUE (
    manifesto_document_id, pipeline_version, segmentation_version,
    topic_codebook_version, config_sha256
  )
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  manifesto_document_id TEXT NOT NULL
    REFERENCES manifesto_documents(manifesto_document_id) ON DELETE CASCADE,
  claim_extraction_run_id TEXT NOT NULL
    REFERENCES claim_extraction_runs(claim_extraction_run_id) ON DELETE RESTRICT,
  party_id INTEGER NOT NULL REFERENCES parties(party_id) ON DELETE RESTRICT,
  attributed_actor_label TEXT NOT NULL,
  claim_kind TEXT NOT NULL CHECK (claim_kind IN (
    'explicit_promise','soft_commitment','preference','slogan',
    'coalition_commitment','issue_position','context'
  )),
  exact_text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  language TEXT,
  page_start INTEGER NOT NULL CHECK (page_start > 0),
  page_end INTEGER NOT NULL CHECK (page_end >= page_start),
  section_path TEXT,
  document_ordinal INTEGER NOT NULL CHECK (document_ordinal >= 0),
  extraction_method TEXT NOT NULL,
  extraction_version TEXT NOT NULL,
  extraction_confidence REAL CHECK (
    extraction_confidence IS NULL OR extraction_confidence BETWEEN 0.0 AND 1.0
  ),
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN (
    'pending','rule_confirmed','human_confirmed','rejected','needs_context'
  )),
  review_method TEXT,
  reviewed_at TEXT,
  claim_status TEXT NOT NULL DEFAULT 'active' CHECK (claim_status IN (
    'active','withdrawn','corrected','superseded','disputed'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (manifesto_document_id, page_start, page_end, document_ordinal, exact_text)
);

CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_evidence_id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  text_document_id INTEGER REFERENCES text_documents(text_document_id) ON DELETE SET NULL,
  evidence_role TEXT NOT NULL CHECK (evidence_role IN (
    'primary','context','contradicting','correcting','superseding'
  )),
  source_url TEXT NOT NULL,
  document_sha256 TEXT NOT NULL,
  page_start INTEGER NOT NULL CHECK (page_start > 0),
  page_end INTEGER NOT NULL CHECK (page_end >= page_start),
  char_start INTEGER,
  char_end INTEGER,
  exact_quote TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (claim_id, evidence_role, document_sha256, page_start, page_end, quote_sha256)
);

CREATE TABLE IF NOT EXISTS promises (
  promise_id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL UNIQUE REFERENCES claims(claim_id) ON DELETE CASCADE,
  commitment_strength TEXT NOT NULL CHECK (commitment_strength IN (
    'explicit','strong','conditional','aspirational','unclear'
  )),
  action_text TEXT,
  object_text TEXT,
  target_population TEXT,
  target_territory TEXT,
  deadline_text TEXT,
  conditions_text TEXT,
  measurability_state TEXT NOT NULL CHECK (measurability_state IN (
    'measurable','partially_measurable','not_measurable','unknown'
  )),
  measurable_criteria_json TEXT NOT NULL DEFAULT '[]',
  observation_status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (observation_status IN (
    'not_assessed','unknown','no_evidence','in_progress','fulfilled',
    'partially_fulfilled','not_fulfilled','superseded','not_applicable'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_topics (
  claim_topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  topic_id INTEGER NOT NULL REFERENCES topics(topic_id) ON DELETE CASCADE,
  assignment_method TEXT NOT NULL,
  assignment_version TEXT NOT NULL,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0),
  review_status TEXT NOT NULL DEFAULT 'rule_assigned' CHECK (review_status IN (
    'rule_assigned','human_confirmed','rejected'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (claim_id, topic_id, assignment_method, assignment_version)
);

CREATE INDEX IF NOT EXISTS idx_manifesto_documents_party_election
  ON manifesto_documents(party_id, election_key, published_date);
CREATE INDEX IF NOT EXISTS idx_manifesto_documents_source_hash
  ON manifesto_documents(source_id, content_sha256);
CREATE INDEX IF NOT EXISTS idx_claim_extraction_runs_document_status
  ON claim_extraction_runs(manifesto_document_id, status, finished_at);
CREATE INDEX IF NOT EXISTS idx_claims_document_page
  ON claims(manifesto_document_id, page_start, document_ordinal);
CREATE INDEX IF NOT EXISTS idx_claims_party_kind_review
  ON claims(party_id, claim_kind, review_status, page_start);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_role
  ON claim_evidence(claim_id, evidence_role);
CREATE INDEX IF NOT EXISTS idx_promises_observation_measurability
  ON promises(observation_status, measurability_state);
CREATE INDEX IF NOT EXISTS idx_claim_topics_topic_claim
  ON claim_topics(topic_id, claim_id);

-- Versioned promise/position -> later action comparisons. Source records live
-- in their owning databases; this layer preserves their stable IDs, exact
-- public evidence, and the explicit review that makes a comparison defensible.
CREATE TABLE IF NOT EXISTS comparison_releases (
  comparison_release_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  method_version TEXT NOT NULL,
  mapping_review_version TEXT NOT NULL,
  snapshot_date TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  promises_source_scope_sha256 TEXT NOT NULL,
  actions_source_scope_sha256 TEXT NOT NULL,
  actor_source_scope_sha256 TEXT NOT NULL,
  actor_graph_release_id TEXT NOT NULL,
  reviewed_mappings_sha256 TEXT NOT NULL,
  semantic_sha256 TEXT NOT NULL,
  comparison_count INTEGER NOT NULL CHECK (comparison_count >= 0),
  evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
  status_counts_json TEXT NOT NULL,
  source_manifest_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comparison_mapping_reviews (
  mapping_review_id TEXT PRIMARY KEY,
  comparison_release_id TEXT NOT NULL
    REFERENCES comparison_releases(comparison_release_id) ON DELETE CASCADE,
  claim_id TEXT NOT NULL,
  promise_id TEXT,
  action_kind TEXT NOT NULL CHECK (
    action_kind IN ('roll_call_vote', 'bounded_action_search')
  ),
  action_id TEXT,
  action_search_state TEXT NOT NULL CHECK (action_search_state IN (
    'not_applicable','no_reviewed_action_found'
  )),
  action_search_scope_json TEXT NOT NULL DEFAULT '{}',
  claim_actor_id TEXT NOT NULL,
  action_actor_id TEXT,
  action_registry_actor_id TEXT,
  action_party_actor_id TEXT,
  affiliation_relationship_id TEXT,
  actor_link_state TEXT NOT NULL CHECK (actor_link_state IN (
    'reviewed_official_identity_and_affiliation',
    'claim_actor_only_no_action'
  )),
  review_outcome TEXT NOT NULL CHECK (review_outcome IN (
    'aligned','conflicted','insufficient_evidence','ambiguous_mapping',
    'changed_framing','not_comparable'
  )),
  claim_direction TEXT NOT NULL CHECK (claim_direction IN ('support','oppose','unclear')),
  action_direction TEXT NOT NULL CHECK (action_direction IN (
    'support','oppose','unclear','not_applicable'
  )),
  action_substance_state TEXT NOT NULL CHECK (action_substance_state IN (
    'substantive','procedural','unknown','not_applicable'
  )),
  mapping_basis TEXT NOT NULL CHECK (mapping_basis IN (
    'exact_measure','reviewed_related_measure','broad_topic_only',
    'procedural_near_match','bounded_search_no_reviewed_action'
  )),
  review_method TEXT NOT NULL CHECK (review_method = 'explicit_evidence_review'),
  review_version TEXT NOT NULL,
  review_rationale TEXT NOT NULL,
  directional_countable INTEGER NOT NULL DEFAULT 0 CHECK (directional_countable IN (0, 1)),
  reviewed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (comparison_release_id, claim_id, action_kind, action_id)
);

CREATE TABLE IF NOT EXISTS promise_action_comparisons (
  comparison_id TEXT PRIMARY KEY,
  comparison_release_id TEXT NOT NULL
    REFERENCES comparison_releases(comparison_release_id) ON DELETE CASCADE,
  mapping_review_id TEXT NOT NULL UNIQUE
    REFERENCES comparison_mapping_reviews(mapping_review_id) ON DELETE CASCADE,
  claim_id TEXT NOT NULL,
  promise_id TEXT,
  claim_kind TEXT NOT NULL,
  claim_actor_label TEXT NOT NULL,
  claim_actor_id TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  claim_page_start INTEGER NOT NULL CHECK (claim_page_start > 0),
  claim_page_end INTEGER NOT NULL CHECK (claim_page_end >= claim_page_start),
  claim_published_date TEXT,
  claim_review_status TEXT NOT NULL,
  action_kind TEXT NOT NULL CHECK (
    action_kind IN ('roll_call_vote', 'bounded_action_search')
  ),
  action_id TEXT,
  action_search_state TEXT NOT NULL CHECK (action_search_state IN (
    'not_applicable','no_reviewed_action_found'
  )),
  action_search_scope_json TEXT NOT NULL DEFAULT '{}',
  action_date TEXT,
  action_title TEXT,
  action_member_name TEXT,
  action_vote_choice TEXT,
  action_actor_id TEXT,
  action_party_actor_id TEXT,
  action_source_id TEXT,
  action_source_url TEXT,
  comparison_status TEXT NOT NULL CHECK (comparison_status IN (
    'aligned','conflicted','insufficient_evidence','ambiguous_mapping',
    'changed_framing','not_comparable'
  )),
  directional_countable INTEGER NOT NULL DEFAULT 0 CHECK (directional_countable IN (0, 1)),
  public_summary TEXT NOT NULL,
  caveat TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (comparison_release_id, claim_id, action_kind, action_id)
);

CREATE TABLE IF NOT EXISTS comparison_evidence (
  comparison_evidence_id TEXT PRIMARY KEY,
  comparison_id TEXT NOT NULL
    REFERENCES promise_action_comparisons(comparison_id) ON DELETE CASCADE,
  evidence_side TEXT NOT NULL CHECK (evidence_side IN (
    'claim','action','actor_link','mapping_review'
  )),
  evidence_role TEXT NOT NULL CHECK (evidence_role IN (
    'primary','context','identity','review'
  )),
  source_id TEXT NOT NULL,
  source_record_id TEXT,
  source_url TEXT,
  content_sha256 TEXT,
  exact_quote TEXT,
  observed_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  UNIQUE (comparison_id, evidence_side, evidence_role, source_id, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_comparison_reviews_release_status
  ON comparison_mapping_reviews(comparison_release_id, review_outcome, claim_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_release_status
  ON promise_action_comparisons(comparison_release_id, comparison_status, claim_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_action
  ON promise_action_comparisons(action_kind, action_id, comparison_status);
CREATE INDEX IF NOT EXISTS idx_comparison_evidence_comparison_side
  ON comparison_evidence(comparison_id, evidence_side, evidence_role);

-- Generic fetch status table for large, multi-stage backfills.
-- Used to avoid re-trying permanently blocked URLs (e.g. 403/404) unless explicitly requested.
CREATE TABLE IF NOT EXISTS document_fetches (
  doc_url TEXT PRIMARY KEY,
  source_id TEXT,
  first_attempt_at TEXT,
  last_attempt_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  fetched_ok INTEGER NOT NULL DEFAULT 0 CHECK (fetched_ok IN (0, 1)),
  last_http_status INTEGER,
  last_error TEXT,
  content_type TEXT,
  content_sha256 TEXT,
  bytes INTEGER,
  raw_path TEXT
);

-- Derived semantic extraction over initiative documents ("what was voted").
-- One row per downloaded source_record_pk so repeated URLs/docs are processed idempotently.
CREATE TABLE IF NOT EXISTS parl_initiative_doc_extractions (
  source_record_pk INTEGER PRIMARY KEY REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  sample_initiative_id TEXT REFERENCES parl_initiatives(initiative_id) ON DELETE SET NULL,
  initiatives_count INTEGER NOT NULL DEFAULT 0,
  doc_refs_count INTEGER NOT NULL DEFAULT 0,
  doc_kinds_csv TEXT,
  content_sha256 TEXT,
  doc_format TEXT,
  extractor_version TEXT NOT NULL,
  text_extraction_method TEXT,
  text_quality TEXT,
  needs_ocr INTEGER NOT NULL DEFAULT 0 CHECK (needs_ocr IN (0, 1)),
  full_text_chars INTEGER,
  full_text_path TEXT,
  extracted_title TEXT,
  extracted_subject TEXT,
  extracted_excerpt TEXT,
  confidence REAL,
  needs_review INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
  analysis_payload_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Manual/agent review queue for translating parliamentary vote events into
-- citizen-meaningful implications.
-- One row per review_key, typically vote_event_id + initiative_id when linked.
CREATE TABLE IF NOT EXISTS parl_vote_implication_reviews (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  review_key TEXT NOT NULL UNIQUE,
  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  initiative_id TEXT REFERENCES parl_initiatives(initiative_id) ON DELETE SET NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  review_reason TEXT NOT NULL CHECK (
    review_reason IN (
      'generic_title',
      'split_vote_point',
      'procedural_wrapper',
      'subject_low_specificity',
      'missing_excerpt'
    )
  ),
  status TEXT NOT NULL CHECK (status IN ('pending', 'resolved', 'ignored')) DEFAULT 'pending',
  priority INTEGER NOT NULL DEFAULT 50,
  heuristic_subject TEXT,
  heuristic_implication_kind TEXT CHECK (
    heuristic_implication_kind IN (
      'binding_law',
      'budget_tax',
      'regulation',
      'non_binding_motion',
      'oversight',
      'authorization',
      'procedural',
      'unknown'
    )
  ),
  heuristic_binding_strength TEXT CHECK (
    heuristic_binding_strength IN ('binding', 'non_binding', 'authorization', 'procedural', 'unknown')
  ),
  citizen_title TEXT,
  citizen_question TEXT,
  citizen_summary TEXT,
  impact_if_approved TEXT,
  impact_if_rejected TEXT,
  affected_groups TEXT,
  evidence_quote TEXT,
  final_implication_kind TEXT CHECK (
    final_implication_kind IN (
      'binding_law',
      'budget_tax',
      'regulation',
      'non_binding_motion',
      'oversight',
      'authorization',
      'procedural',
      'unknown'
    )
  ),
  final_binding_strength TEXT CHECK (
    final_binding_strength IN ('binding', 'non_binding', 'authorization', 'procedural', 'unknown')
  ),
  confidence REAL,
  extractor_version TEXT,
  note TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Manual/agent review queue for initiative-document bundles that need to be
-- translated into concrete citizen-facing measures.
-- One row per official initiative with downloaded dossier text.
CREATE TABLE IF NOT EXISTS parl_initiative_measure_review_tasks (
  task_id TEXT PRIMARY KEY,
  initiative_id TEXT NOT NULL UNIQUE REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  review_reason TEXT NOT NULL CHECK (
    review_reason IN (
      'official_docs_bundle',
      'boe_law_bundle',
      'keyword_priority'
    )
  ),
  status TEXT NOT NULL CHECK (status IN ('pending', 'resolved', 'ignored')) DEFAULT 'pending',
  priority INTEGER NOT NULL DEFAULT 50,
  evidence_bundle_dir TEXT,
  note TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Normalized measure points extracted from one initiative review task.
-- A single initiative can yield multiple citizen-searchable measures.
CREATE TABLE IF NOT EXISTS parl_initiative_measure_points (
  measure_point_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES parl_initiative_measure_review_tasks(task_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  measure_rank INTEGER NOT NULL DEFAULT 1,
  measure_title TEXT NOT NULL,
  citizen_summary TEXT NOT NULL,
  affected_groups TEXT,
  policy_area TEXT,
  measure_kind TEXT,
  measure_status TEXT CHECK (
    measure_status IN ('proposed', 'approved', 'rejected', 'derogated', 'pending', 'unknown')
  ),
  search_terms_json TEXT NOT NULL DEFAULT '[]',
  primary_vote_event_ids_json TEXT NOT NULL DEFAULT '[]',
  support_side TEXT CHECK (support_side IN ('yes', 'no', 'mixed', 'unknown')),
  support_explanation TEXT,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (task_id, measure_rank)
);

-- Responsibility explainer benchmark cases and their evidence slices.
CREATE TABLE IF NOT EXISTS responsibility_explainer_cases (
  case_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  short_label TEXT NOT NULL,
  summary TEXT NOT NULL,
  current_scope_note TEXT,
  geography TEXT,
  incident_window_label TEXT,
  incident_start_date TEXT,
  incident_end_date TEXT,
  initiative_ids_json TEXT NOT NULL DEFAULT '[]',
  known_gaps_json TEXT NOT NULL DEFAULT '[]',
  next_lanes_json TEXT NOT NULL DEFAULT '[]',
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_cases_active_sort
ON responsibility_explainer_cases(is_active, sort_order, case_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_questions (
  case_question_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  category TEXT,
  prompt TEXT NOT NULL,
  support_rule TEXT,
  next_evidence_needed_json TEXT NOT NULL DEFAULT '[]',
  question_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_questions_case
ON responsibility_explainer_questions(case_id, question_order, question_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_normative_duties (
  case_duty_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  duty_id TEXT NOT NULL,
  category TEXT,
  actor TEXT,
  actor_scope TEXT,
  duty_summary TEXT,
  why_it_matters TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  duty_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, duty_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_normative_duties_case
ON responsibility_explainer_normative_duties(case_id, duty_order, duty_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_warning_channels (
  case_channel_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL,
  channel_name TEXT,
  operator TEXT,
  scope TEXT,
  signal_summary TEXT,
  why_next TEXT,
  source_title TEXT,
  source_url TEXT,
  source_note TEXT,
  channel_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_warning_channels_case
ON responsibility_explainer_warning_channels(case_id, channel_order, channel_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_warning_timeline_events (
  case_timeline_event_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  event_id TEXT NOT NULL,
  channel_id TEXT,
  channel_name TEXT,
  operator TEXT,
  event_time TEXT,
  event_precision TEXT,
  signal_level TEXT,
  event_summary TEXT,
  why_it_matters TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  event_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_warning_timeline_case
ON responsibility_explainer_warning_timeline_events(case_id, event_order, event_time, event_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_governing_rules (
  case_rule_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  rule_id TEXT NOT NULL,
  rule_kind TEXT,
  title TEXT,
  duty_summary TEXT,
  exposure_mechanism TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  rule_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_governing_rules_case
ON responsibility_explainer_governing_rules(case_id, rule_order, rule_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_official_findings (
  case_finding_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  finding_id TEXT NOT NULL,
  category TEXT,
  entity_name TEXT,
  finding_date TEXT,
  finding_summary TEXT,
  accountability_implication TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  finding_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, finding_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_official_findings_case
ON responsibility_explainer_official_findings(case_id, finding_order, finding_date, finding_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_administrative_acts (
  case_act_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  act_id TEXT NOT NULL,
  act_type TEXT,
  entity_name TEXT,
  act_date TEXT,
  status TEXT,
  act_summary TEXT,
  accountability_implication TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  act_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, act_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_administrative_acts_case
ON responsibility_explainer_administrative_acts(case_id, act_order, act_date, act_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_responsibility_links (
  case_link_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  link_id TEXT NOT NULL,
  actor TEXT,
  actor_scope TEXT,
  linked_object_type TEXT,
  linked_object_id TEXT,
  role_in_chain TEXT,
  obligation_basis TEXT,
  accountability_question TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  link_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, link_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_responsibility_links_case
ON responsibility_explainer_responsibility_links(case_id, link_order, link_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_structural_risk_factors (
  case_factor_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  factor_id TEXT NOT NULL,
  category TEXT,
  title TEXT,
  risk_mechanism TEXT,
  accountability_focus TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  factor_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, factor_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_structural_risk_factors_case
ON responsibility_explainer_structural_risk_factors(case_id, factor_order, factor_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_structural_audit_targets (
  case_target_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  target_id TEXT NOT NULL,
  category TEXT,
  title TEXT,
  geography TEXT,
  why_priority TEXT,
  audit_question TEXT,
  documents_to_audit_json TEXT NOT NULL DEFAULT '[]',
  authority_chain TEXT,
  next_join_needed TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  target_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_structural_audit_targets_case
ON responsibility_explainer_structural_audit_targets(case_id, target_order, target_id);

CREATE TABLE IF NOT EXISTS responsibility_explainer_structural_evidence_rows (
  case_evidence_pk TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES responsibility_explainer_cases(case_id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL,
  target_id TEXT,
  entity_name TEXT,
  signal_type TEXT,
  certainty TEXT,
  signal_title TEXT,
  pre_dana_reading TEXT,
  why_it_matters TEXT,
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_note TEXT,
  evidence_order INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (case_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_responsibility_explainer_structural_evidence_case
ON responsibility_explainer_structural_evidence_rows(case_id, evidence_order, evidence_id);

-- Generic accountability ledger: issue-led actor/action/evidence spine.
-- This is the cross-case layer behind actor dossiers, issue ledgers, and Q&A.
CREATE TABLE IF NOT EXISTS accountability_issues (
  issue_id TEXT PRIMARY KEY,
  case_id TEXT REFERENCES responsibility_explainer_cases(case_id) ON DELETE SET NULL,
  canonical_key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  summary TEXT,
  scope TEXT,
  domain_id INTEGER REFERENCES domains(domain_id),
  topic_id INTEGER REFERENCES topics(topic_id),
  issue_status TEXT NOT NULL DEFAULT 'active' CHECK (
    issue_status IN ('draft', 'active', 'archived')
  ),
  source_kind TEXT NOT NULL DEFAULT 'derived' CHECK (
    source_kind IN ('derived', 'manual_seed', 'official_source', 'mixed')
  ),
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accountability_ledger_entries (
  entry_id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL REFERENCES accountability_issues(issue_id) ON DELETE CASCADE,
  entry_kind TEXT NOT NULL CHECK (
    entry_kind IN (
      'promise',
      'parliamentary_action',
      'rule',
      'appointment',
      'money',
      'implementation',
      'enforcement',
      'audit',
      'outcome',
      'blocker',
      'responsibility_link',
      'other'
    )
  ),
  accountability_role TEXT CHECK (
    accountability_role IN (
      'promised',
      'proposed',
      'sponsored',
      'voted_for',
      'voted_against',
      'abstained',
      'approved',
      'published',
      'appointed',
      'dismissed',
      'delegated_to',
      'implemented',
      'funded',
      'contracted',
      'subsidized',
      'enforced',
      'audited',
      'current_owner',
      'unknown'
    )
  ),
  role_in_chain TEXT,
  actor_label TEXT NOT NULL,
  actor_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    actor_kind IN ('person', 'party', 'institution', 'org_unit', 'position', 'group', 'unknown')
  ),
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  parliamentary_group_id INTEGER REFERENCES parliamentary_groups(parliamentary_group_id) ON DELETE SET NULL,
  mandate_id INTEGER REFERENCES mandates(mandate_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  position_id INTEGER REFERENCES government_positions(position_id) ON DELETE SET NULL,
  linked_object_type TEXT,
  linked_object_id TEXT,
  policy_event_id TEXT REFERENCES policy_events(policy_event_id) ON DELETE SET NULL,
  topic_evidence_id INTEGER REFERENCES topic_evidence(evidence_id) ON DELETE SET NULL,
  legal_fragment_id TEXT REFERENCES legal_norm_fragments(fragment_id) ON DELETE SET NULL,
  event_date TEXT,
  published_date TEXT,
  title TEXT,
  summary TEXT,
  accountability_question TEXT,
  confidence REAL,
  evidence_tier INTEGER CHECK (evidence_tier BETWEEN 0 AND 5),
  source_id TEXT REFERENCES sources(source_id),
  source_title TEXT,
  source_url TEXT,
  source_locator TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  evidence_quote TEXT,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accountability_issues_case
ON accountability_issues(case_id);

CREATE INDEX IF NOT EXISTS idx_accountability_issues_domain_topic
ON accountability_issues(domain_id, topic_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_issue
ON accountability_ledger_entries(issue_id, entry_kind);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_role
ON accountability_ledger_entries(accountability_role);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_actor_label
ON accountability_ledger_entries(actor_label);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_person
ON accountability_ledger_entries(person_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_party
ON accountability_ledger_entries(party_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_parliamentary_group
ON accountability_ledger_entries(parliamentary_group_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_institution
ON accountability_ledger_entries(institution_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_policy_event
ON accountability_ledger_entries(policy_event_id);

CREATE INDEX IF NOT EXISTS idx_accountability_ledger_source
ON accountability_ledger_entries(source_id, source_record_pk);

-- Cover the bounded semantic publisher's source/year/id traversal at scale.
CREATE INDEX IF NOT EXISTS idx_accountability_ledger_partition
ON accountability_ledger_entries(
  COALESCE(NULLIF(source_id, ''), 'unknown'),
  CASE
    WHEN substr(COALESCE(NULLIF(event_date, ''), published_date, ''), 1, 4)
      GLOB '[12][0-9][0-9][0-9]'
    THEN substr(COALESCE(NULLIF(event_date, ''), published_date, ''), 1, 4)
    ELSE 'unknown'
  END,
  entry_id
);

-- Politica publica: dominios, ejes y eventos (accion revelada).
-- Nota: estas tablas son el "hueco" intencional para evolucionar desde temas/votos
-- hacia acciones con efectos (BOE, dinero publico, etc.) sin romper Explorer.

CREATE TABLE IF NOT EXISTS domains (
  domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT,
  tier INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_axes (
  policy_axis_id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_id INTEGER NOT NULL REFERENCES domains(domain_id) ON DELETE CASCADE,
  canonical_key TEXT NOT NULL,
  label TEXT NOT NULL,
  description TEXT,
  axis_order INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (domain_id, canonical_key)
);

CREATE TABLE IF NOT EXISTS policy_instruments (
  policy_instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_events (
  policy_event_id TEXT PRIMARY KEY,
  event_date TEXT,
  published_date TEXT,
  domain_id INTEGER REFERENCES domains(domain_id),
  policy_instrument_id INTEGER REFERENCES policy_instruments(policy_instrument_id),
  title TEXT,
  summary TEXT,
  amount_eur REAL,
  currency TEXT,
  institution_id INTEGER REFERENCES institutions(institution_id),
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  scope TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_event_axis_scores (
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
);

-- Agreements, meetings, public agendas, lobbying disclosures, and influence.
-- Facts stay in the meeting/agreement tables. Any influence interpretation is
-- isolated in influence_assertions and cannot silently become a source fact.
CREATE TABLE IF NOT EXISTS accountability_meetings (
  meeting_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  meeting_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (meeting_ordinal >= 0),
  meeting_kind TEXT NOT NULL CHECK (
    meeting_kind IN (
      'bilateral_meeting', 'public_agenda_meeting', 'lobbying_contact',
      'parliamentary_negotiation', 'coalition_negotiation', 'council_session',
      'committee_session', 'hearing', 'roundtable', 'conference_event',
      'written_contact', 'other'
    )
  ),
  title TEXT NOT NULL,
  summary TEXT,
  scheduled_state TEXT NOT NULL DEFAULT 'unknown' CHECK (
    scheduled_state IN ('scheduled', 'occurred', 'cancelled', 'postponed', 'unknown')
  ),
  attendance_disclosure_state TEXT NOT NULL DEFAULT 'unknown' CHECK (
    attendance_disclosure_state IN ('complete', 'partial', 'not_disclosed', 'unknown')
  ),
  event_date TEXT,
  started_at TEXT,
  ended_at TEXT,
  time_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (
    time_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  timezone TEXT,
  location_name TEXT,
  location_address TEXT,
  territory_id INTEGER REFERENCES territories(territory_id) ON DELETE SET NULL,
  territory_code TEXT,
  published_at TEXT,
  observed_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  fact_state TEXT NOT NULL CHECK (
    fact_state IN ('source_explicit', 'source_summary', 'derived_structure', 'disputed')
  ),
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id, meeting_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_accountability_meetings_source_date
ON accountability_meetings(source_id, event_date, meeting_kind, meeting_id);

CREATE INDEX IF NOT EXISTS idx_accountability_meetings_state
ON accountability_meetings(scheduled_state, attendance_disclosure_state, event_date);

CREATE TABLE IF NOT EXISTS meeting_participants (
  meeting_participant_id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL REFERENCES accountability_meetings(meeting_id) ON DELETE CASCADE,
  participant_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (participant_ordinal >= 0),
  actor_role TEXT NOT NULL CHECK (
    actor_role IN (
      'attendee', 'convener', 'host', 'guest', 'lobbyist', 'public_official',
      'counterparty', 'observer', 'disclosing_body', 'other'
    )
  ),
  attendance_claim_state TEXT NOT NULL DEFAULT 'not_claimed' CHECK (
    attendance_claim_state IN ('source_explicit', 'source_listed', 'not_claimed', 'disputed')
  ),
  actor_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    actor_kind IN ('person', 'organization', 'public_body', 'collective', 'unknown')
  ),
  source_label TEXT NOT NULL,
  source_identifier TEXT,
  source_identifier_scheme TEXT,
  role_title_source TEXT,
  represented_organization_source TEXT,
  identity_state TEXT NOT NULL DEFAULT 'source_scoped' CHECK (
    identity_state IN ('source_scoped', 'resolved', 'disputed', 'unknown')
  ),
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  resolution_method TEXT,
  resolution_confidence REAL CHECK (
    resolution_confidence IS NULL OR resolution_confidence BETWEEN 0 AND 1
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (meeting_id, actor_role, participant_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_meeting_participants_meeting_role
ON meeting_participants(meeting_id, actor_role, participant_ordinal);

CREATE INDEX IF NOT EXISTS idx_meeting_participants_identity
ON meeting_participants(source_identifier_scheme, source_identifier, source_label);

CREATE TABLE IF NOT EXISTS meeting_agenda_items (
  agenda_item_id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL REFERENCES accountability_meetings(meeting_id) ON DELETE CASCADE,
  item_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (item_ordinal >= 0),
  agenda_state TEXT NOT NULL DEFAULT 'unknown' CHECK (
    agenda_state IN (
      'scheduled', 'discussed', 'decided', 'deferred', 'cancelled',
      'source_summary', 'unknown'
    )
  ),
  title TEXT NOT NULL,
  description TEXT,
  external_item_id TEXT,
  source_text_state TEXT NOT NULL CHECK (
    source_text_state IN ('source_explicit', 'source_summary', 'derived_topic', 'unknown')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (meeting_id, item_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_meeting_agenda_items_meeting_state
ON meeting_agenda_items(meeting_id, agenda_state, item_ordinal);

CREATE TABLE IF NOT EXISTS meeting_evidence (
  meeting_evidence_id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL REFERENCES accountability_meetings(meeting_id) ON DELETE CASCADE,
  agenda_item_id TEXT REFERENCES meeting_agenda_items(agenda_item_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN ('announcement', 'agenda', 'attendance', 'minutes', 'outcome', 'context')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  exact_quote TEXT,
  quote_sha256 TEXT CHECK (quote_sha256 IS NULL OR length(quote_sha256) = 64),
  page INTEGER CHECK (page IS NULL OR page >= 1),
  section TEXT,
  selector TEXT,
  evidence_state TEXT NOT NULL CHECK (
    evidence_state IN ('captured_bytes', 'official_url_only', 'missing', 'blocked')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (meeting_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_meeting_evidence_meeting_role
ON meeting_evidence(meeting_id, evidence_role, evidence_ordinal);

CREATE INDEX IF NOT EXISTS idx_meeting_evidence_source
ON meeting_evidence(source_id, source_record_pk);

CREATE TABLE IF NOT EXISTS agreements (
  agreement_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  agreement_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (agreement_ordinal >= 0),
  agreement_kind TEXT NOT NULL CHECK (
    agreement_kind IN (
      'coalition_agreement', 'investiture_agreement', 'parliamentary_pact',
      'executive_decision', 'interinstitutional_agreement',
      'collective_bargaining_agreement', 'memorandum_of_understanding',
      'convention', 'joint_declaration', 'amendment_or_addendum',
      'other_official_agreement'
    )
  ),
  agreement_status TEXT NOT NULL DEFAULT 'unknown' CHECK (
    agreement_status IN (
      'proposed', 'negotiating', 'adopted', 'signed', 'in_force',
      'partially_implemented', 'implemented', 'expired', 'terminated',
      'superseded', 'withdrawn', 'disputed', 'unknown'
    )
  ),
  title TEXT NOT NULL,
  summary TEXT,
  external_agreement_id TEXT,
  meeting_id TEXT REFERENCES accountability_meetings(meeting_id) ON DELETE SET NULL,
  agenda_item_id TEXT REFERENCES meeting_agenda_items(agenda_item_id) ON DELETE SET NULL,
  proposed_on TEXT,
  adopted_on TEXT,
  signed_on TEXT,
  effective_from TEXT,
  effective_to TEXT,
  published_on TEXT,
  observed_at TEXT NOT NULL,
  date_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (
    date_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  fact_state TEXT NOT NULL CHECK (
    fact_state IN ('source_explicit', 'source_summary', 'derived_structure', 'disputed')
  ),
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id, agreement_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_agreements_source_kind_date
ON agreements(source_id, agreement_kind, adopted_on, published_on, agreement_id);

CREATE INDEX IF NOT EXISTS idx_agreements_status
ON agreements(agreement_status, effective_from, effective_to);

CREATE TABLE IF NOT EXISTS agreement_parties (
  agreement_party_id TEXT PRIMARY KEY,
  agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  party_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (party_ordinal >= 0),
  party_role TEXT NOT NULL CHECK (
    party_role IN (
      'proposer', 'negotiating_party', 'adopter', 'signatory', 'counterparty',
      'implementing_body', 'guarantor', 'witness', 'affected_body',
      'publishing_body', 'other'
    )
  ),
  actor_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    actor_kind IN ('person', 'organization', 'public_body', 'collective', 'unknown')
  ),
  source_label TEXT NOT NULL,
  source_identifier TEXT,
  source_identifier_scheme TEXT,
  role_title_source TEXT,
  identity_state TEXT NOT NULL DEFAULT 'source_scoped' CHECK (
    identity_state IN ('source_scoped', 'resolved', 'disputed', 'unknown')
  ),
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  resolution_method TEXT,
  resolution_confidence REAL CHECK (
    resolution_confidence IS NULL OR resolution_confidence BETWEEN 0 AND 1
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (agreement_id, party_role, party_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_agreement_parties_agreement_role
ON agreement_parties(agreement_id, party_role, party_ordinal);

CREATE INDEX IF NOT EXISTS idx_agreement_parties_identity
ON agreement_parties(source_identifier_scheme, source_identifier, source_label);

CREATE TABLE IF NOT EXISTS agreement_evidence (
  agreement_evidence_id TEXT PRIMARY KEY,
  agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN (
      'primary_text', 'official_summary', 'signature', 'publication',
      'amendment', 'implementation', 'termination', 'context'
    )
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  document_url TEXT,
  document_id TEXT,
  document_label TEXT,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  exact_quote TEXT,
  quote_sha256 TEXT CHECK (quote_sha256 IS NULL OR length(quote_sha256) = 64),
  page INTEGER CHECK (page IS NULL OR page >= 1),
  section TEXT,
  selector TEXT,
  evidence_state TEXT NOT NULL CHECK (
    evidence_state IN ('captured_bytes', 'official_url_only', 'missing', 'blocked')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (agreement_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_agreement_evidence_agreement_role
ON agreement_evidence(agreement_id, evidence_role, evidence_ordinal);

CREATE INDEX IF NOT EXISTS idx_agreement_evidence_source
ON agreement_evidence(source_id, source_record_pk);

CREATE TABLE IF NOT EXISTS agreement_topics (
  agreement_topic_id TEXT PRIMARY KEY,
  agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  topic_id INTEGER REFERENCES topics(topic_id) ON DELETE SET NULL,
  topic_key TEXT NOT NULL,
  topic_label TEXT NOT NULL,
  assignment_kind TEXT NOT NULL CHECK (
    assignment_kind IN ('source_explicit', 'reviewed', 'derived_rule', 'derived_model')
  ),
  assignment_method TEXT NOT NULL,
  assignment_version TEXT NOT NULL,
  match_text TEXT,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (agreement_id, topic_key, assignment_method, assignment_version)
);

CREATE INDEX IF NOT EXISTS idx_agreement_topics_topic
ON agreement_topics(topic_key, review_status, agreement_id);

CREATE TABLE IF NOT EXISTS agreement_links (
  agreement_link_id TEXT PRIMARY KEY,
  subject_agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN (
      'amends', 'implements', 'supersedes', 'terminates', 'renews',
      'derived_from', 'related_to', 'other'
    )
  ),
  object_agreement_id TEXT NOT NULL REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  method TEXT NOT NULL,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (subject_agreement_id <> object_agreement_id),
  UNIQUE (subject_agreement_id, relationship_type, object_agreement_id, method)
);

CREATE INDEX IF NOT EXISTS idx_agreement_links_subject
ON agreement_links(subject_agreement_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_agreement_links_object
ON agreement_links(object_agreement_id, relationship_type);

CREATE TABLE IF NOT EXISTS influence_assertions (
  influence_assertion_id TEXT PRIMARY KEY,
  assertion_version INTEGER NOT NULL DEFAULT 1 CHECK (assertion_version >= 1),
  supersedes_assertion_id TEXT REFERENCES influence_assertions(influence_assertion_id) ON DELETE SET NULL,
  meeting_id TEXT REFERENCES accountability_meetings(meeting_id) ON DELETE SET NULL,
  agreement_id TEXT REFERENCES agreements(agreement_id) ON DELETE SET NULL,
  subject_actor_label TEXT,
  subject_actor_kind TEXT CHECK (
    subject_actor_kind IS NULL OR subject_actor_kind IN (
      'person', 'organization', 'public_body', 'collective', 'unknown'
    )
  ),
  subject_person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  subject_party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  subject_institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  assertion_kind TEXT NOT NULL,
  inference_level TEXT NOT NULL CHECK (
    inference_level IN (
      'fact_only', 'temporal_proximity', 'content_alignment',
      'plausible_pathway', 'substantiated_influence',
      'improper_influence_allegation'
    )
  ),
  assertion_text TEXT NOT NULL,
  limitations_text TEXT NOT NULL,
  alternatives_json TEXT NOT NULL DEFAULT '[]',
  window_start TEXT,
  window_end TEXT,
  method TEXT NOT NULL,
  method_version TEXT NOT NULL,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  reviewed_by TEXT,
  reviewed_at TEXT,
  adjudication_text TEXT,
  publication_state TEXT NOT NULL DEFAULT 'private' CHECK (
    publication_state IN ('private', 'review_queue', 'publishable', 'published', 'withdrawn')
  ),
  publication_reason TEXT NOT NULL,
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (meeting_id IS NOT NULL OR agreement_id IS NOT NULL),
  UNIQUE (object_type, object_id, assertion_kind, method, method_version, assertion_version)
);

CREATE INDEX IF NOT EXISTS idx_influence_assertions_review_publication
ON influence_assertions(review_status, publication_state, inference_level);

CREATE INDEX IF NOT EXISTS idx_influence_assertions_meeting_agreement
ON influence_assertions(meeting_id, agreement_id);

CREATE TABLE IF NOT EXISTS influence_assertion_evidence (
  influence_assertion_evidence_id TEXT PRIMARY KEY,
  influence_assertion_id TEXT NOT NULL
    REFERENCES influence_assertions(influence_assertion_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN ('supporting', 'contrary', 'context', 'methodology')
  ),
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  source_url TEXT,
  content_sha256 TEXT CHECK (content_sha256 IS NULL OR length(content_sha256) = 64),
  exact_quote TEXT,
  quote_sha256 TEXT CHECK (quote_sha256 IS NULL OR length(quote_sha256) = 64),
  locator TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (influence_assertion_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_influence_assertion_evidence_assertion_role
ON influence_assertion_evidence(influence_assertion_id, evidence_role, evidence_ordinal);

-- Canonical foreign-policy action layer. Source wording and procedural stages
-- remain explicit so domestic authorization cannot be mistaken for signature,
-- ratification, entry into force, implementation, alignment, or outcome.
CREATE TABLE IF NOT EXISTS geopolitical_actions (
  geopolitical_action_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  action_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (action_ordinal >= 0),
  action_kind TEXT NOT NULL CHECK (
    action_kind IN (
      'treaty_process', 'international_resolution', 'sanction_measure',
      'aid_commitment', 'defence_agreement', 'international_vote',
      'diplomatic_action', 'other_foreign_policy_action'
    )
  ),
  action_status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    action_status IN (
      'announced', 'proposed', 'approved', 'authorized', 'referred',
      'signed', 'ratified', 'published', 'entered_into_force',
      'implemented', 'amended', 'renewed', 'suspended', 'terminated',
      'rejected', 'abstained', 'not_assessed', 'unknown'
    )
  ),
  procedure_stage TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  external_action_id TEXT,
  instrument_name TEXT,
  instrument_identifier TEXT,
  instrument_identifier_scheme TEXT,
  scope_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    scope_kind IN ('bilateral', 'multilateral', 'global', 'domestic_external', 'unknown')
  ),
  scope_assignment_kind TEXT NOT NULL DEFAULT 'source_explicit' CHECK (
    scope_assignment_kind IN ('source_explicit', 'reviewed', 'derived_rule', 'unknown')
  ),
  action_date TEXT,
  published_at TEXT,
  valid_from TEXT,
  valid_to TEXT,
  effective_from TEXT,
  effective_to TEXT,
  observed_at TEXT NOT NULL,
  date_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (
    date_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  binding_state TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    binding_state IN ('explicit_yes', 'explicit_no', 'not_assessed', 'unknown', 'disputed')
  ),
  entry_into_force_state TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    entry_into_force_state IN (
      'explicit_yes', 'explicit_no', 'not_assessed', 'unknown', 'disputed'
    )
  ),
  implementation_state TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    implementation_state IN (
      'not_assessed', 'announced', 'started', 'partial', 'implemented',
      'suspended', 'terminated', 'unknown', 'disputed'
    )
  ),
  outcome_state TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    outcome_state IN ('not_assessed', 'observed', 'unknown', 'disputed')
  ),
  position_state TEXT NOT NULL DEFAULT 'not_assessed' CHECK (
    position_state IN (
      'source_explicit', 'derived', 'not_assessed', 'unknown', 'disputed'
    )
  ),
  related_agreement_id TEXT REFERENCES agreements(agreement_id) ON DELETE SET NULL,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  fact_state TEXT NOT NULL CHECK (
    fact_state IN ('source_explicit', 'source_summary', 'derived_structure', 'disputed')
  ),
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id, action_ordinal, action_kind, procedure_stage)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_actions_source_kind_date
ON geopolitical_actions(
  source_id, action_kind, substr(COALESCE(action_date, ''), 1, 7),
  action_date, geopolitical_action_id
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_actions_stage_status
ON geopolitical_actions(procedure_stage, action_status, action_date);

CREATE INDEX IF NOT EXISTS idx_geopolitical_actions_instrument
ON geopolitical_actions(instrument_identifier_scheme, instrument_identifier, instrument_name);

CREATE TABLE IF NOT EXISTS geopolitical_action_actors (
  geopolitical_action_actor_id TEXT PRIMARY KEY,
  geopolitical_action_id TEXT NOT NULL
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  actor_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (actor_ordinal >= 0),
  actor_role TEXT NOT NULL CHECK (
    actor_role IN (
      'acting_state', 'approving_body', 'authorizing_body', 'publishing_body',
      'parliamentary_recipient', 'counterparty_state',
      'counterparty_organization', 'issuing_organization', 'voting_actor',
      'sanctioning_actor', 'sanction_target', 'aid_provider', 'aid_recipient',
      'implementing_body', 'beneficiary', 'named_official', 'other_named_party'
    )
  ),
  actor_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    actor_kind IN (
      'person', 'state', 'territory', 'international_organization',
      'public_body', 'organization', 'legal_entity', 'unknown'
    )
  ),
  source_label TEXT NOT NULL,
  source_identifier TEXT,
  source_identifier_scheme TEXT,
  jurisdiction_code TEXT,
  identity_state TEXT NOT NULL DEFAULT 'source_scoped' CHECK (
    identity_state IN ('source_scoped', 'resolved', 'disputed', 'unknown')
  ),
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  resolution_method TEXT NOT NULL,
  resolution_confidence REAL CHECK (
    resolution_confidence IS NULL OR resolution_confidence BETWEEN 0 AND 1
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (geopolitical_action_id, actor_role, actor_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_actors_action_role
ON geopolitical_action_actors(geopolitical_action_id, actor_role, actor_ordinal);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_actors_identity
ON geopolitical_action_actors(
  source_identifier_scheme, source_identifier, source_label, actor_role
);

CREATE TABLE IF NOT EXISTS geopolitical_action_evidence (
  geopolitical_action_evidence_id TEXT PRIMARY KEY,
  geopolitical_action_id TEXT NOT NULL
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN (
      'official_action', 'instrument_text', 'actor_identity', 'procedure_stage',
      'amount', 'vote_choice', 'position_statement', 'implementation',
      'correction', 'counterevidence', 'context'
    )
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  capture_path TEXT,
  capture_bytes INTEGER CHECK (capture_bytes IS NULL OR capture_bytes >= 0),
  captured_at TEXT,
  capture_sha256 TEXT CHECK (capture_sha256 IS NULL OR length(capture_sha256) = 64),
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  exact_quote TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL CHECK (length(quote_sha256) = 64),
  page INTEGER CHECK (page IS NULL OR page >= 1),
  section TEXT,
  selector TEXT,
  evidence_state TEXT NOT NULL CHECK (
    evidence_state IN ('captured_bytes', 'official_url_only', 'missing', 'blocked')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (geopolitical_action_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_evidence_action_role
ON geopolitical_action_evidence(geopolitical_action_id, evidence_role, evidence_ordinal);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_evidence_source
ON geopolitical_action_evidence(source_id, source_record_pk, content_sha256);

CREATE TABLE IF NOT EXISTS geopolitical_action_topics (
  geopolitical_action_topic_id TEXT PRIMARY KEY,
  geopolitical_action_id TEXT NOT NULL
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  topic_id INTEGER REFERENCES topics(topic_id) ON DELETE SET NULL,
  topic_key TEXT NOT NULL,
  topic_label TEXT NOT NULL,
  assignment_kind TEXT NOT NULL CHECK (
    assignment_kind IN ('source_explicit', 'reviewed', 'derived_rule', 'derived_model')
  ),
  assignment_method TEXT NOT NULL,
  assignment_version TEXT NOT NULL,
  match_text TEXT,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (geopolitical_action_id, topic_key, assignment_method, assignment_version)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_topics_topic
ON geopolitical_action_topics(topic_key, review_status, geopolitical_action_id);

CREATE TABLE IF NOT EXISTS geopolitical_positions (
  geopolitical_position_id TEXT PRIMARY KEY,
  position_version INTEGER NOT NULL DEFAULT 1 CHECK (position_version >= 1),
  supersedes_position_id TEXT
    REFERENCES geopolitical_positions(geopolitical_position_id) ON DELETE SET NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  actor_kind TEXT NOT NULL CHECK (
    actor_kind IN (
      'person', 'state', 'territory', 'international_organization',
      'public_body', 'organization', 'legal_entity', 'unknown'
    )
  ),
  actor_source_label TEXT NOT NULL,
  actor_source_identifier TEXT,
  actor_source_identifier_scheme TEXT,
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  subject_kind TEXT NOT NULL,
  subject_id TEXT,
  subject_label TEXT NOT NULL,
  position_kind TEXT NOT NULL CHECK (
    position_kind IN (
      'support', 'oppose', 'abstain', 'recognize', 'not_recognize',
      'condemn', 'endorse', 'reserve', 'commit', 'other_explicit'
    )
  ),
  position_text TEXT NOT NULL,
  source_date TEXT NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  date_precision TEXT NOT NULL DEFAULT 'day' CHECK (
    date_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  position_state TEXT NOT NULL DEFAULT 'source_explicit' CHECK (
    position_state IN ('source_explicit', 'reviewed', 'disputed', 'superseded')
  ),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    source_id, source_record_id, actor_source_label, subject_label,
    position_kind, source_date, position_version
  )
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_positions_actor_date
ON geopolitical_positions(actor_source_label, source_date, position_kind);

CREATE INDEX IF NOT EXISTS idx_geopolitical_positions_subject_date
ON geopolitical_positions(subject_kind, subject_id, source_date);

CREATE TABLE IF NOT EXISTS geopolitical_position_evidence (
  geopolitical_position_evidence_id TEXT PRIMARY KEY,
  geopolitical_position_id TEXT NOT NULL
    REFERENCES geopolitical_positions(geopolitical_position_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN ('position_statement', 'correction', 'counterevidence', 'context')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  exact_quote TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL CHECK (length(quote_sha256) = 64),
  locator TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (geopolitical_position_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_position_evidence_position_role
ON geopolitical_position_evidence(
  geopolitical_position_id, evidence_role, evidence_ordinal
);

CREATE TABLE IF NOT EXISTS geopolitical_action_links (
  geopolitical_action_link_id TEXT PRIMARY KEY,
  subject_action_id TEXT NOT NULL
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN (
      'derived_from_agreement', 'amends', 'implements', 'supersedes',
      'renews', 'suspends', 'terminates', 'related_vote',
      'related_spending', 'later_observation', 'other'
    )
  ),
  object_type TEXT NOT NULL CHECK (
    object_type IN (
      'geopolitical_action', 'agreement', 'vote_event', 'spending_item',
      'source_record', 'other'
    )
  ),
  object_id TEXT NOT NULL,
  object_action_id TEXT
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  object_agreement_id TEXT REFERENCES agreements(agreement_id) ON DELETE CASCADE,
  object_vote_event_id TEXT REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  method TEXT NOT NULL,
  method_version TEXT NOT NULL,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (subject_action_id <> COALESCE(object_action_id, '')),
  UNIQUE (subject_action_id, relationship_type, object_type, object_id, method, method_version)
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_links_subject
ON geopolitical_action_links(subject_action_id, relationship_type, object_type);

CREATE INDEX IF NOT EXISTS idx_geopolitical_action_links_object
ON geopolitical_action_links(object_type, object_id, relationship_type);

CREATE TABLE IF NOT EXISTS geopolitical_observations (
  geopolitical_observation_id TEXT PRIMARY KEY,
  geopolitical_action_id TEXT NOT NULL
    REFERENCES geopolitical_actions(geopolitical_action_id) ON DELETE CASCADE,
  observation_kind TEXT NOT NULL CHECK (
    observation_kind IN (
      'legal_stage', 'entry_into_force', 'implementation', 'disbursement',
      'delivery', 'compliance', 'outcome', 'correction', 'other'
    )
  ),
  observation_state TEXT NOT NULL,
  observation_text TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  date_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (
    date_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  exact_quote TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL CHECK (length(quote_sha256) = 64),
  selector TEXT,
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    geopolitical_action_id, observation_kind, observation_state,
    observed_at, source_record_pk
  )
);

CREATE INDEX IF NOT EXISTS idx_geopolitical_observations_action_kind_date
ON geopolitical_observations(
  geopolitical_action_id, observation_kind, observed_at, geopolitical_observation_id
);

-- Dinero publico (staging normalizado, previo al mapeo a policy_events).
-- Contrato explicito AI-OPS-09:
-- - PLACSP nacional: source_id = placsp_sindicacion
-- - PLACSP piloto CCAA: source_id = placsp_autonomico
CREATE TABLE IF NOT EXISTS money_contract_records (
  contract_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id)
      CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  source_url TEXT,
  contract_id TEXT,
  lot_id TEXT,
  notice_type TEXT,
  cpv_code TEXT,
  cpv_label TEXT,
  contracting_authority TEXT,
  procedure_type TEXT,
  territory_code TEXT,
  published_date TEXT,
  awarded_date TEXT,
  amount_eur REAL,
  amount_eur_decimal TEXT,
  amount_semantics TEXT,
  currency TEXT,
  stable_contract_id TEXT,
  entry_updated_at TEXT,
  contract_status_code TEXT,
  authority_identifier TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_pk)
);

-- One contract version can resolve multiple lots/results. Amounts remain exact
-- decimal strings. Officially published supplier names and identifiers remain
-- intact in public accountability artifacts with source provenance.
CREATE TABLE IF NOT EXISTS money_contract_award_results (
  contract_award_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id)
    CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  stable_contract_id TEXT NOT NULL,
  award_ordinal INTEGER NOT NULL CHECK (award_ordinal >= 0),
  lot_id TEXT,
  result_code TEXT,
  result_description TEXT,
  award_date TEXT,
  received_tender_quantity INTEGER,
  supplier_name TEXT,
  supplier_identifier TEXT,
  supplier_identifier_scheme TEXT,
  amount_eur_decimal TEXT,
  payable_amount_eur_decimal TEXT,
  currency TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_record_pk, award_ordinal)
);

-- Bounded document manifest extracted from official CODICE entries. The bytes
-- are downloaded by the separate durable document pipeline.
CREATE TABLE IF NOT EXISTS money_contract_documents (
  contract_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id)
    CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  stable_contract_id TEXT NOT NULL,
  document_ordinal INTEGER NOT NULL CHECK (document_ordinal >= 0),
  document_kind TEXT,
  document_label TEXT,
  source_url TEXT NOT NULL,
  official_document_hash TEXT,
  document_source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_record_pk, document_ordinal),
  UNIQUE (source_record_pk, source_url)
);

-- Canonical monetary event layer. Source-specific money tables above preserve
-- every upstream field; these additive tables make actor -> event -> evidence
-- traversal uniform without collapsing awards, contracts, invoices, payments,
-- delivery, budgets, or subsidies into a false generic "spend" fact.
CREATE TABLE IF NOT EXISTS spending_items (
  spending_item_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  source_url TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  spending_kind TEXT NOT NULL CHECK (
    spending_kind IN (
      'budget_appropriation',
      'budget_amendment',
      'procurement_notice',
      'procurement_award',
      'contract_commitment',
      'contract_modification',
      'recognized_obligation',
      'invoice',
      'payment',
      'delivery_milestone',
      'subsidy_award',
      'subsidy_payment',
      'refund_recovery',
      'other'
    )
  ),
  source_kind_label TEXT,
  stable_object_id TEXT NOT NULL,
  semantic_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (semantic_ordinal >= 0),
  external_contract_id TEXT,
  lot_id TEXT,
  title TEXT,
  description TEXT,
  classification_scheme TEXT,
  classification_code TEXT,
  procedure_code TEXT,
  result_code TEXT,
  amount_decimal TEXT,
  payable_amount_decimal TEXT,
  currency TEXT,
  amount_semantics TEXT NOT NULL,
  tax_semantics TEXT NOT NULL DEFAULT 'unknown' CHECK (
    tax_semantics IN (
      'excluding_tax', 'including_tax', 'tax_only', 'not_applicable', 'unknown'
    )
  ),
  amount_source_text TEXT,
  published_on TEXT,
  decision_on TEXT,
  signed_on TEXT,
  effective_from TEXT,
  effective_to TEXT,
  accrued_on TEXT,
  invoice_on TEXT,
  paid_on TEXT,
  delivered_on TEXT,
  period_start TEXT,
  period_end TEXT,
  date_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (
    date_precision IN ('instant', 'day', 'month', 'year', 'interval', 'unknown')
  ),
  territory_id INTEGER REFERENCES territories(territory_id) ON DELETE SET NULL,
  territory_code TEXT,
  publication_state TEXT NOT NULL DEFAULT 'published' CHECK (
    publication_state IN ('published', 'withdrawn', 'superseded', 'unknown')
  ),
  extractor_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id, spending_kind, semantic_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_spending_items_source_kind_date
ON spending_items(source_id, spending_kind, decision_on, published_on, spending_item_id);

CREATE INDEX IF NOT EXISTS idx_spending_items_stable_object
ON spending_items(source_id, stable_object_id, spending_kind);

CREATE INDEX IF NOT EXISTS idx_spending_items_amount
ON spending_items(currency, amount_semantics, amount_decimal);

CREATE INDEX IF NOT EXISTS idx_spending_items_territory
ON spending_items(territory_id, territory_code, spending_kind);

CREATE TABLE IF NOT EXISTS spending_item_actors (
  spending_item_actor_id TEXT PRIMARY KEY,
  spending_item_id TEXT NOT NULL REFERENCES spending_items(spending_item_id) ON DELETE CASCADE,
  actor_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (actor_ordinal >= 0),
  actor_role TEXT NOT NULL CHECK (
    actor_role IN (
      'appropriating_authority',
      'contracting_authority',
      'payer',
      'supplier',
      'beneficiary',
      'invoice_issuer',
      'payment_recipient',
      'delivery_responsible',
      'auditor',
      'other'
    )
  ),
  actor_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (
    actor_kind IN ('person', 'organization', 'public_body', 'unknown')
  ),
  source_label TEXT NOT NULL,
  source_identifier TEXT,
  source_identifier_scheme TEXT,
  identity_state TEXT NOT NULL DEFAULT 'source_scoped' CHECK (
    identity_state IN ('source_scoped', 'resolved', 'disputed', 'unknown')
  ),
  person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL,
  party_id INTEGER REFERENCES parties(party_id) ON DELETE SET NULL,
  institution_id INTEGER REFERENCES institutions(institution_id) ON DELETE SET NULL,
  org_unit_id INTEGER REFERENCES government_org_units(org_unit_id) ON DELETE SET NULL,
  resolution_method TEXT,
  resolution_confidence REAL CHECK (
    resolution_confidence IS NULL OR resolution_confidence BETWEEN 0 AND 1
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (spending_item_id, actor_role, actor_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_spending_item_actors_item_role
ON spending_item_actors(spending_item_id, actor_role, actor_ordinal);

CREATE INDEX IF NOT EXISTS idx_spending_item_actors_source_identifier
ON spending_item_actors(source_identifier_scheme, source_identifier, actor_role);

CREATE INDEX IF NOT EXISTS idx_spending_item_actors_source_label
ON spending_item_actors(source_label, actor_role);

CREATE TABLE IF NOT EXISTS spending_item_evidence (
  spending_evidence_id TEXT PRIMARY KEY,
  spending_item_id TEXT NOT NULL REFERENCES spending_items(spending_item_id) ON DELETE CASCADE,
  evidence_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (evidence_ordinal >= 0),
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN (
      'primary_record',
      'notice',
      'award_decision',
      'contract',
      'invoice',
      'payment_record',
      'delivery_record',
      'audit',
      'context'
    )
  ),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  contract_document_id INTEGER REFERENCES money_contract_documents(contract_document_id) ON DELETE SET NULL,
  document_id TEXT,
  source_url TEXT NOT NULL,
  document_url TEXT,
  document_label TEXT,
  document_kind TEXT,
  content_sha256 TEXT CHECK (content_sha256 IS NULL OR length(content_sha256) = 64),
  exact_quote TEXT,
  quote_sha256 TEXT CHECK (quote_sha256 IS NULL OR length(quote_sha256) = 64),
  page INTEGER CHECK (page IS NULL OR page >= 1),
  section TEXT,
  selector TEXT,
  evidence_state TEXT NOT NULL CHECK (
    evidence_state IN ('captured_bytes', 'official_url_only', 'missing', 'blocked')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (spending_item_id, evidence_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_spending_item_evidence_item_role
ON spending_item_evidence(spending_item_id, evidence_role, evidence_ordinal);

CREATE INDEX IF NOT EXISTS idx_spending_item_evidence_source
ON spending_item_evidence(source_id, source_record_pk);

CREATE TABLE IF NOT EXISTS spending_item_links (
  spending_item_link_id TEXT PRIMARY KEY,
  subject_spending_item_id TEXT NOT NULL REFERENCES spending_items(spending_item_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN (
      'amends', 'announces', 'awards', 'formalizes', 'invoices', 'pays',
      'delivers', 'refunds', 'supersedes', 'same_procedure_as', 'other'
    )
  ),
  object_spending_item_id TEXT NOT NULL REFERENCES spending_items(spending_item_id) ON DELETE CASCADE,
  method TEXT NOT NULL,
  confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    review_status IN ('unreviewed', 'pending', 'confirmed', 'rejected', 'superseded')
  ),
  source_id TEXT REFERENCES sources(source_id),
  source_record_pk INTEGER REFERENCES source_records(source_record_pk) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (subject_spending_item_id <> object_spending_item_id),
  UNIQUE (subject_spending_item_id, relationship_type, object_spending_item_id, method)
);

CREATE INDEX IF NOT EXISTS idx_spending_item_links_subject
ON spending_item_links(subject_spending_item_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_spending_item_links_object
ON spending_item_links(object_spending_item_id, relationship_type);

-- Detalle estructurado de licitaciones/cpvs/documentos (scrape puntual PLACSP).
-- Guardamos evidencia de la página de detalle por contrato para enriquecer
-- money_contract_records sin forzar una transformación irreversible.
CREATE TABLE IF NOT EXISTS placsp_contract_detail_records (
  detail_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id) CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  source_url TEXT NOT NULL,
  source_url_raw TEXT,
  file_number TEXT,
  contract_id TEXT,
  notice_type TEXT,
  cpv_code TEXT,
  cpv_label TEXT,
  contracting_authority TEXT,
  state TEXT,
  territory_code TEXT,
  procedure_type TEXT,
  processing_type TEXT,
  method_of_presentation TEXT,
  submission_deadline TEXT,
  base_budget_eur REAL,
  estimated_value_eur REAL,
  published_at TEXT,
  awarded_at TEXT,
  tender_title TEXT,
  raw_payload TEXT NOT NULL,
  source_html_sha256 TEXT,
  raw_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_pk)
);

-- Documentos listados en la página de detalle PLACSP (adjudicacion, pliegos, actas).
CREATE TABLE IF NOT EXISTS placsp_contract_detail_documents (
  detail_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id) CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  doc_kind TEXT,
  doc_label TEXT,
  doc_reference_date TEXT,
  content_type_hint TEXT,
  doc_payload_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_record_pk, source_url, doc_kind)
);

-- Contrato explicito AI-OPS-09:
-- - BDNS nacional: source_id = bdns_api_subvenciones
-- - BDNS piloto CCAA: source_id = bdns_autonomico
CREATE TABLE IF NOT EXISTS money_subsidy_records (
  subsidy_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id)
      CHECK (source_id LIKE 'bdns_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT,
  source_url TEXT,
  call_id TEXT,
  grant_id TEXT,
  granting_body TEXT,
  beneficiary_name TEXT,
  beneficiary_identifier TEXT,
  program_code TEXT,
  territory_code TEXT,
  published_date TEXT,
  concession_date TEXT,
  amount_eur REAL,
  currency TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_pk)
);

-- Durable, bounded-page acquisition control for national money registries.
-- One bulk run owns a stable queue namespace. Page payload bytes live in the
-- content-addressed raw store; these tables retain only checkpoints/lineage.
CREATE TABLE IF NOT EXISTS money_bulk_runs (
  money_bulk_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT NOT NULL UNIQUE,
  ingestion_run_id INTEGER REFERENCES ingestion_runs(run_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT NOT NULL,
  snapshot_date TEXT NOT NULL,
  page_size INTEGER NOT NULL CHECK (page_size BETWEEN 1 AND 1000),
  total_elements_discovered INTEGER NOT NULL CHECK (total_elements_discovered >= 0),
  total_pages_discovered INTEGER NOT NULL CHECK (total_pages_discovered >= 0),
  pages_enqueued INTEGER NOT NULL CHECK (pages_enqueued >= 0),
  limited_run INTEGER NOT NULL DEFAULT 0 CHECK (limited_run IN (0, 1)),
  state TEXT NOT NULL DEFAULT 'running'
    CHECK (state IN ('running', 'succeeded', 'partial', 'failed')),
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_loaded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  finished_at TEXT
);

-- Shallow source-side windows avoid deep-offset degradation on very large APIs.
-- Partition discovery is immutable within a run and every fetched page links
-- back to the exact official filter window used to obtain it.
CREATE TABLE IF NOT EXISTS money_bulk_partitions (
  money_bulk_partition_id INTEGER PRIMARY KEY AUTOINCREMENT,
  money_bulk_run_id INTEGER NOT NULL
    REFERENCES money_bulk_runs(money_bulk_run_id) ON DELETE CASCADE,
  partition_key TEXT NOT NULL,
  source_url TEXT NOT NULL,
  filter_json TEXT NOT NULL,
  date_from TEXT,
  date_to TEXT,
  total_elements_discovered INTEGER NOT NULL CHECK (total_elements_discovered >= 0),
  total_pages_discovered INTEGER NOT NULL CHECK (total_pages_discovered >= 0),
  pages_enqueued INTEGER NOT NULL CHECK (pages_enqueued >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (money_bulk_run_id, partition_key)
);

CREATE TABLE IF NOT EXISTS money_bulk_page_fetches (
  money_bulk_page_fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  money_bulk_run_id INTEGER NOT NULL
    REFERENCES money_bulk_runs(money_bulk_run_id) ON DELETE CASCADE,
  work_item_id INTEGER REFERENCES pipeline_work_items(work_item_id) ON DELETE SET NULL,
  page_number INTEGER NOT NULL CHECK (page_number >= 0),
  money_bulk_partition_id INTEGER
    REFERENCES money_bulk_partitions(money_bulk_partition_id) ON DELETE SET NULL,
  source_page_number INTEGER CHECK (source_page_number IS NULL OR source_page_number >= 0),
  source_url TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  content_type TEXT,
  bytes INTEGER NOT NULL CHECK (bytes >= 0),
  raw_path TEXT NOT NULL,
  api_total_elements INTEGER NOT NULL CHECK (api_total_elements >= 0),
  api_total_pages INTEGER NOT NULL CHECK (api_total_pages >= 0),
  records_seen INTEGER NOT NULL CHECK (records_seen >= 0),
  records_loaded INTEGER NOT NULL CHECK (records_loaded >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (money_bulk_run_id, page_number)
);

-- Immutable normalized-record fingerprints. Raw official beneficiary payloads
-- remain in content-addressed page objects exactly as published by the source;
-- version rows avoid duplicating the same payload.
CREATE TABLE IF NOT EXISTS money_source_record_versions (
  money_source_record_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT NOT NULL,
  record_sha256 TEXT NOT NULL CHECK (length(record_sha256) = 64),
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_id, record_sha256)
);

-- One source-record sighting per bulk snapshot/run, linked back to an immutable
-- raw page object plus record ordinal and normalized-record version.
CREATE TABLE IF NOT EXISTS money_bulk_record_sightings (
  money_bulk_record_sighting_id INTEGER PRIMARY KEY AUTOINCREMENT,
  money_bulk_run_id INTEGER NOT NULL
    REFERENCES money_bulk_runs(money_bulk_run_id) ON DELETE CASCADE,
  money_bulk_page_fetch_id INTEGER NOT NULL
    REFERENCES money_bulk_page_fetches(money_bulk_page_fetch_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_record_id TEXT NOT NULL,
  money_source_record_version_id INTEGER NOT NULL
    REFERENCES money_source_record_versions(money_source_record_version_id),
  snapshot_date TEXT NOT NULL,
  record_ordinal INTEGER NOT NULL CHECK (record_ordinal >= 0),
  observed_at TEXT NOT NULL,
  UNIQUE (money_bulk_run_id, source_id, source_record_id),
  UNIQUE (money_bulk_page_fetch_id, record_ordinal)
);

-- Durable archive/member acquisition for PLACSP monthly/yearly ZIP corpora.
-- ZIP bytes stay in content-addressed storage; members are parsed in-place and
-- independently leased so restarts never require corpus-wide extraction.
CREATE TABLE IF NOT EXISTS placsp_bulk_runs (
  placsp_bulk_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT NOT NULL UNIQUE,
  ingestion_run_id INTEGER REFERENCES ingestion_runs(run_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id) CHECK (source_id LIKE 'placsp_%'),
  snapshot_date TEXT NOT NULL,
  archives_enqueued INTEGER NOT NULL CHECK (archives_enqueued >= 0),
  archive_contract_sha256 TEXT CHECK (
    archive_contract_sha256 IS NULL OR length(archive_contract_sha256) = 64
  ),
  state TEXT NOT NULL DEFAULT 'running'
    CHECK (state IN ('running', 'succeeded', 'partial', 'failed')),
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_loaded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS placsp_bulk_archives (
  placsp_bulk_archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
  placsp_bulk_run_id INTEGER NOT NULL
    REFERENCES placsp_bulk_runs(placsp_bulk_run_id) ON DELETE CASCADE,
  work_item_id INTEGER REFERENCES pipeline_work_items(work_item_id) ON DELETE SET NULL,
  period TEXT NOT NULL,
  source_url TEXT NOT NULL,
  transport_security TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  bytes INTEGER NOT NULL CHECK (bytes >= 0),
  raw_path TEXT NOT NULL,
  members_total INTEGER NOT NULL CHECK (members_total >= 0),
  uncompressed_bytes INTEGER NOT NULL CHECK (uncompressed_bytes >= 0),
  status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (placsp_bulk_run_id, source_url),
  UNIQUE (placsp_bulk_run_id, content_sha256)
);

CREATE TABLE IF NOT EXISTS placsp_bulk_members (
  placsp_bulk_member_id INTEGER PRIMARY KEY AUTOINCREMENT,
  placsp_bulk_archive_id INTEGER NOT NULL
    REFERENCES placsp_bulk_archives(placsp_bulk_archive_id) ON DELETE CASCADE,
  work_item_id INTEGER REFERENCES pipeline_work_items(work_item_id) ON DELETE SET NULL,
  member_name TEXT NOT NULL,
  crc32 INTEGER NOT NULL,
  compressed_bytes INTEGER NOT NULL CHECK (compressed_bytes >= 0),
  uncompressed_bytes INTEGER NOT NULL CHECK (uncompressed_bytes >= 0),
  content_sha256 TEXT CHECK (content_sha256 IS NULL OR length(content_sha256) = 64),
  records_seen INTEGER NOT NULL DEFAULT 0 CHECK (records_seen >= 0),
  records_loaded INTEGER NOT NULL DEFAULT 0 CHECK (records_loaded >= 0),
  tombstones_seen INTEGER NOT NULL DEFAULT 0 CHECK (tombstones_seen >= 0),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'ok', 'error')),
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (placsp_bulk_archive_id, member_name)
);

CREATE TABLE IF NOT EXISTS placsp_bulk_record_sightings (
  placsp_bulk_record_sighting_id INTEGER PRIMARY KEY AUTOINCREMENT,
  placsp_bulk_run_id INTEGER NOT NULL
    REFERENCES placsp_bulk_runs(placsp_bulk_run_id) ON DELETE CASCADE,
  placsp_bulk_member_id INTEGER NOT NULL
    REFERENCES placsp_bulk_members(placsp_bulk_member_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(source_id) CHECK (source_id LIKE 'placsp_%'),
  source_record_pk INTEGER NOT NULL REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  source_record_id TEXT NOT NULL,
  stable_contract_id TEXT NOT NULL,
  entry_content_sha256 TEXT NOT NULL CHECK (length(entry_content_sha256) = 64),
  record_ordinal INTEGER NOT NULL CHECK (record_ordinal >= 0),
  observed_at TEXT NOT NULL,
  UNIQUE (placsp_bulk_member_id, record_ordinal),
  UNIQUE (placsp_bulk_run_id, source_id, stable_contract_id, entry_content_sha256)
);

-- Interventions: agrupacion reproducible de eventos en tratamientos evaluables.
CREATE TABLE IF NOT EXISTS interventions (
  intervention_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT,
  domain_id INTEGER REFERENCES domains(domain_id),
  start_date TEXT,
  end_date TEXT,
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intervention_events (
  intervention_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id) ON DELETE CASCADE,
  policy_event_id TEXT NOT NULL REFERENCES policy_events(policy_event_id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (intervention_id, policy_event_id)
);

-- Indicadores (outcomes + confusores) para evaluaciones y contexto.
CREATE TABLE IF NOT EXISTS indicator_series (
  indicator_series_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  unit TEXT,
  frequency TEXT,
  domain_id INTEGER REFERENCES domains(domain_id),
  admin_level_id INTEGER REFERENCES admin_levels(admin_level_id),
  territory_id INTEGER REFERENCES territories(territory_id),
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  dimensions_json TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS indicator_points (
  indicator_point_id INTEGER PRIMARY KEY AUTOINCREMENT,
  indicator_series_id INTEGER NOT NULL REFERENCES indicator_series(indicator_series_id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  value REAL,
  value_text TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (indicator_series_id, date)
);

-- Outcomes/confusores (staging trazable por observacion fuente).
-- Contrato explicito AI-OPS-09:
-- - Eurostat: source_id = eurostat_sdmx
-- - Banco de Espana: source_id = bde_series_api
-- - AEMET: source_id = aemet_opendata_series
CREATE TABLE IF NOT EXISTS indicator_observation_records (
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
);

-- Durable registry acquisitions for large official indicator cubes. Queue rows
-- orchestrate retries; these rows reconcile each immutable raw blob to the
-- versioned source records materialized from it.
CREATE TABLE IF NOT EXISTS indicator_bulk_acquisitions (
  indicator_bulk_acquisition_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT NOT NULL,
  item_key TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  dataset_code TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_snapshot_date TEXT NOT NULL,
  transport_security TEXT NOT NULL
    CHECK (transport_security IN ('verified_ca', 'unverified_tls', 'local_fixture')),
  raw_content_sha256 TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  raw_bytes INTEGER NOT NULL,
  series_loaded INTEGER NOT NULL DEFAULT 0,
  observations_discovered INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'error')),
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (pipeline_id, item_key)
);

CREATE TABLE IF NOT EXISTS indicator_bulk_acquisition_records (
  indicator_bulk_acquisition_id INTEGER NOT NULL
    REFERENCES indicator_bulk_acquisitions(indicator_bulk_acquisition_id) ON DELETE CASCADE,
  source_record_pk INTEGER NOT NULL
    REFERENCES source_records(source_record_pk) ON DELETE CASCADE,
  observations_discovered INTEGER NOT NULL,
  record_sha256 TEXT NOT NULL,
  PRIMARY KEY (indicator_bulk_acquisition_id, source_record_pk)
);

-- Canonical indicator contract v1. These tables sit beside the legacy
-- indicator_series/indicator_observation_records ingestion tables. They keep
-- immutable source releases and observation versions explicit so a later
-- official correction never overwrites what the project previously observed.
CREATE TABLE IF NOT EXISTS indicator_definitions (
  indicator_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  dataset_code TEXT NOT NULL,
  indicator_code TEXT NOT NULL,
  label TEXT NOT NULL,
  definition TEXT,
  domain_key TEXT,
  frequency_code TEXT NOT NULL,
  frequency_label TEXT,
  unit_code TEXT NOT NULL,
  unit_label TEXT,
  methodology_version TEXT,
  methodology_url TEXT,
  revision_policy TEXT NOT NULL,
  license_url TEXT,
  source_url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, dataset_code, indicator_code, frequency_code, unit_code)
);

CREATE TABLE IF NOT EXISTS indicator_releases (
  indicator_release_id TEXT PRIMARY KEY,
  indicator_id TEXT NOT NULL REFERENCES indicator_definitions(indicator_id) ON DELETE CASCADE,
  source_snapshot_date TEXT NOT NULL,
  source_updated_at TEXT,
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  source_bytes INTEGER NOT NULL,
  raw_path TEXT NOT NULL,
  source_metadata_json TEXT NOT NULL,
  comparison_state TEXT NOT NULL
    CHECK (comparison_state IN ('baseline', 'compared')),
  previous_indicator_release_id TEXT REFERENCES indicator_releases(indicator_release_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (indicator_id, source_content_sha256)
);

CREATE TABLE IF NOT EXISTS indicator_series_versions (
  indicator_series_version_id TEXT PRIMARY KEY,
  indicator_id TEXT NOT NULL REFERENCES indicator_definitions(indicator_id) ON DELETE CASCADE,
  indicator_release_id TEXT NOT NULL REFERENCES indicator_releases(indicator_release_id) ON DELETE CASCADE,
  stable_series_key TEXT NOT NULL,
  geography_code TEXT NOT NULL,
  geography_name TEXT,
  geography_system TEXT NOT NULL,
  geography_level TEXT NOT NULL,
  geography_version TEXT,
  territory_id INTEGER REFERENCES territories(territory_id),
  dimensions_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (indicator_release_id, stable_series_key)
);

CREATE TABLE IF NOT EXISTS indicator_observation_versions (
  indicator_observation_version_id TEXT PRIMARY KEY,
  indicator_series_version_id TEXT NOT NULL
    REFERENCES indicator_series_versions(indicator_series_version_id) ON DELETE CASCADE,
  indicator_release_id TEXT NOT NULL
    REFERENCES indicator_releases(indicator_release_id) ON DELETE CASCADE,
  period_label TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  interval_kind TEXT NOT NULL,
  value_decimal TEXT,
  value_text TEXT,
  source_status_code TEXT,
  source_status_labels_json TEXT NOT NULL,
  uncertainty_lower_decimal TEXT,
  uncertainty_upper_decimal TEXT,
  uncertainty_state TEXT NOT NULL
    CHECK (uncertainty_state IN ('provided', 'not_provided', 'not_applicable')),
  revision_ordinal INTEGER NOT NULL CHECK (revision_ordinal >= 1),
  revision_state TEXT NOT NULL
    CHECK (revision_state IN ('baseline', 'unchanged', 'changed', 'superseded', 'deleted', 'corrected')),
  previous_observation_version_id TEXT
    REFERENCES indicator_observation_versions(indicator_observation_version_id),
  source_published_at TEXT,
  raw_cell_index INTEGER NOT NULL CHECK (raw_cell_index >= 0),
  raw_value_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (value_decimal IS NOT NULL OR value_text IS NOT NULL OR revision_state = 'deleted'),
  UNIQUE (indicator_series_version_id, period_label)
);

CREATE TABLE IF NOT EXISTS indicator_observation_evidence (
  indicator_observation_evidence_id TEXT PRIMARY KEY,
  indicator_observation_version_id TEXT NOT NULL
    REFERENCES indicator_observation_versions(indicator_observation_version_id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  value_json_pointer TEXT NOT NULL,
  status_json_pointer TEXT,
  extraction_method TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (indicator_observation_version_id, source_content_sha256)
);

-- Causal estimates: resultados de evaluacion con diagnosticos y trazabilidad.
CREATE TABLE IF NOT EXISTS causal_estimates (
  causal_estimate_id INTEGER PRIMARY KEY AUTOINCREMENT,
  intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id) ON DELETE CASCADE,
  outcome_series_id INTEGER REFERENCES indicator_series(indicator_series_id),
  method TEXT NOT NULL,
  estimate_value REAL,
  estimate_json TEXT,
  diagnostics_json TEXT,
  credibility TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Normativa: desagregacion en fragmentos auditables + cadena de responsabilidad.
-- Slice inicial para roadmap-tecnico (normativa/accountability/sanciones).
CREATE TABLE IF NOT EXISTS legal_norms (
  norm_id TEXT PRIMARY KEY,
  boe_id TEXT UNIQUE,
  title TEXT NOT NULL,
  scope TEXT,
  topic_hint TEXT,
  effective_date TEXT,
  published_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_snapshot_date TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_norm_fragments (
  fragment_id TEXT PRIMARY KEY,
  norm_id TEXT NOT NULL REFERENCES legal_norms(norm_id) ON DELETE CASCADE,
  fragment_type TEXT NOT NULL,
  fragment_order INTEGER,
  fragment_label TEXT NOT NULL,
  fragment_title TEXT,
  fragment_text_excerpt TEXT,
  sanction_conduct TEXT,
  sanction_amount_min_eur REAL,
  sanction_amount_max_eur REAL,
  competent_body TEXT,
  appeal_path TEXT,
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (norm_id, fragment_type, fragment_label)
);

CREATE TABLE IF NOT EXISTS legal_fragment_responsibilities (
  responsibility_id INTEGER PRIMARY KEY AUTOINCREMENT,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('propose', 'approve', 'delegate', 'enforce', 'audit')),
  person_id INTEGER REFERENCES persons(person_id),
  institution_id INTEGER REFERENCES institutions(institution_id),
  actor_label TEXT,
  evidence_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fragment_id, role, actor_label, source_url)
);

CREATE TABLE IF NOT EXISTS legal_fragment_responsibility_evidence (
  responsibility_evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  responsibility_id INTEGER NOT NULL REFERENCES legal_fragment_responsibilities(responsibility_id) ON DELETE CASCADE,
  evidence_type TEXT NOT NULL CHECK (
    evidence_type IN (
      'boe_publicacion',
      'congreso_diario',
      'senado_diario',
      'congreso_vote',
      'senado_vote',
      'other'
    )
  ),
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_date TEXT,
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (responsibility_id, evidence_type, source_url, evidence_date)
);

CREATE TABLE IF NOT EXISTS sanction_norm_catalog (
  norm_id TEXT PRIMARY KEY REFERENCES legal_norms(norm_id) ON DELETE CASCADE,
  scope TEXT,
  organismo_competente TEXT,
  incidence_hypothesis TEXT,
  evidence_required_json TEXT,
  seed_version TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_norm_fragment_links (
  sanction_norm_fragment_link_id INTEGER PRIMARY KEY AUTOINCREMENT,
  norm_id TEXT NOT NULL REFERENCES sanction_norm_catalog(norm_id) ON DELETE CASCADE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  link_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (norm_id, fragment_id)
);

CREATE TABLE IF NOT EXISTS legal_norm_lineage_edges (
  lineage_edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
  norm_id TEXT NOT NULL REFERENCES legal_norms(norm_id) ON DELETE CASCADE,
  related_norm_id TEXT NOT NULL REFERENCES legal_norms(norm_id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL CHECK (relation_type IN ('deroga', 'modifica', 'desarrolla')),
  relation_scope TEXT CHECK (relation_scope IN ('total', 'parcial')),
  evidence_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (norm_id, related_norm_id, relation_type, source_url)
);

-- Size/structure of one version of a norm's text (as published or consolidated at a date), measured
-- from the BOE XML. Feeds complexity series (e.g. words of the income-tax law 1978 -> today).
CREATE TABLE IF NOT EXISTS legal_norm_text_metrics (
  text_metric_id TEXT PRIMARY KEY,
  norm_id TEXT NOT NULL REFERENCES legal_norms(norm_id) ON DELETE CASCADE,
  version_kind TEXT NOT NULL CHECK (version_kind IN ('original', 'consolidated')),
  version_date TEXT NOT NULL,
  words INTEGER,
  words_excl_preamble INTEGER,
  articles INTEGER,
  disp_adicionales INTEGER,
  disp_transitorias INTEGER,
  disp_derogatorias INTEGER,
  disp_finales INTEGER,
  emptied_blocks INTEGER,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT NOT NULL,
  method TEXT NOT NULL,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (norm_id, version_kind, version_date)
);

-- Sanciones ciudadanas: catalogo de fuentes de volumen + tipologias y metrica garantista.
CREATE TABLE IF NOT EXISTS sanction_volume_sources (
  sanction_source_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  organismo TEXT,
  admin_scope TEXT,
  territory_scope TEXT,
  publication_frequency TEXT,
  source_url TEXT NOT NULL,
  source_id TEXT REFERENCES sources(source_id),
  data_contract_json TEXT,
  raw_payload TEXT NOT NULL,
  seed_version TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_infraction_types (
  infraction_type_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  domain TEXT,
  description TEXT,
  canonical_unit TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_infraction_type_mappings (
  mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
  mapping_key TEXT NOT NULL UNIQUE,
  infraction_type_id TEXT NOT NULL
      REFERENCES sanction_infraction_types(infraction_type_id) ON DELETE CASCADE,
  norm_id TEXT REFERENCES legal_norms(norm_id) ON DELETE SET NULL,
  fragment_id TEXT REFERENCES legal_norm_fragments(fragment_id) ON DELETE SET NULL,
  source_system TEXT,
  source_code TEXT,
  source_label TEXT,
  confidence REAL,
  source_url TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_volume_observations (
  observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  observation_key TEXT NOT NULL UNIQUE,
  sanction_source_id TEXT NOT NULL
      REFERENCES sanction_volume_sources(sanction_source_id) ON DELETE CASCADE,
  period_date TEXT NOT NULL,
  period_granularity TEXT NOT NULL,
  territory_id INTEGER REFERENCES territories(territory_id),
  norm_id TEXT REFERENCES legal_norms(norm_id),
  fragment_id TEXT REFERENCES legal_norm_fragments(fragment_id),
  infraction_type_id TEXT REFERENCES sanction_infraction_types(infraction_type_id),
  expediente_count INTEGER,
  importe_total_eur REAL,
  importe_medio_eur REAL,
  recurso_presentado_count INTEGER,
  recurso_estimado_count INTEGER,
  recurso_desestimado_count INTEGER,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_procedural_kpi_definitions (
  kpi_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  metric_formula TEXT NOT NULL,
  interpretation TEXT,
  target_direction TEXT
      CHECK (target_direction IN ('higher_is_better', 'lower_is_better', 'range')),
  source_requirements_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_procedural_metrics (
  metric_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  metric_key TEXT NOT NULL UNIQUE,
  kpi_id TEXT NOT NULL REFERENCES sanction_procedural_kpi_definitions(kpi_id) ON DELETE CASCADE,
  sanction_source_id TEXT REFERENCES sanction_volume_sources(sanction_source_id) ON DELETE SET NULL,
  period_date TEXT NOT NULL,
  period_granularity TEXT NOT NULL,
  territory_id INTEGER REFERENCES territories(territory_id),
  value REAL,
  numerator REAL,
  denominator REAL,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_date TEXT,
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_municipal_ordinances (
  ordinance_id TEXT PRIMARY KEY,
  city_name TEXT NOT NULL,
  province_name TEXT,
  ordinance_label TEXT NOT NULL,
  ordinance_status TEXT NOT NULL CHECK (ordinance_status IN ('identified', 'normalized', 'blocked')),
  ordinance_url TEXT,
  publication_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanction_municipal_ordinance_fragments (
  ordinance_fragment_id TEXT PRIMARY KEY,
  ordinance_id TEXT NOT NULL REFERENCES sanction_municipal_ordinances(ordinance_id) ON DELETE CASCADE,
  fragment_label TEXT NOT NULL,
  conduct TEXT,
  amount_min_eur REAL,
  amount_max_eur REAL,
  competent_body TEXT,
  appeal_path TEXT,
  mapped_norm_id TEXT REFERENCES legal_norms(norm_id),
  mapped_fragment_id TEXT REFERENCES legal_norm_fragments(fragment_id),
  source_url TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (ordinance_id, fragment_label)
);

-- Derechos: indice de restriccion de libertad ciudadana (IRLC) por fragmento.
CREATE TABLE IF NOT EXISTS liberty_irlc_methodologies (
  method_version TEXT PRIMARY KEY,
  method_label TEXT NOT NULL,
  scale_max REAL NOT NULL DEFAULT 100.0,
  weights_json TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_right_categories (
  right_category_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_restriction_assessments (
  assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_key TEXT NOT NULL UNIQUE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  right_category_id TEXT NOT NULL REFERENCES liberty_right_categories(right_category_id) ON DELETE RESTRICT,
  method_version TEXT NOT NULL REFERENCES liberty_irlc_methodologies(method_version) ON DELETE RESTRICT,
  reach_score REAL NOT NULL,
  intensity_score REAL NOT NULL,
  due_process_risk_score REAL NOT NULL,
  reversibility_risk_score REAL NOT NULL,
  discretionality_score REAL NOT NULL,
  compliance_cost_score REAL NOT NULL,
  irlc_score REAL NOT NULL,
  confidence REAL,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fragment_id, right_category_id, method_version)
);

CREATE TABLE IF NOT EXISTS liberty_proportionality_methodologies (
  method_version TEXT PRIMARY KEY,
  method_label TEXT NOT NULL,
  weights_json TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_proportionality_reviews (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  review_key TEXT NOT NULL UNIQUE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  method_version TEXT NOT NULL REFERENCES liberty_proportionality_methodologies(method_version) ON DELETE RESTRICT,
  objective_defined INTEGER NOT NULL CHECK (objective_defined IN (0, 1)),
  objective_text TEXT,
  indicator_defined INTEGER NOT NULL CHECK (indicator_defined IN (0, 1)),
  indicator_text TEXT,
  alternatives_less_restrictive_considered INTEGER NOT NULL CHECK (alternatives_less_restrictive_considered IN (0, 1)),
  alternatives_notes TEXT,
  sunset_review_present INTEGER NOT NULL CHECK (sunset_review_present IN (0, 1)),
  sunset_review_notes TEXT,
  observed_effectiveness_score REAL NOT NULL,
  necessity_score REAL NOT NULL,
  proportionality_score REAL NOT NULL,
  assessment_label TEXT NOT NULL CHECK (assessment_label IN ('supported', 'weak', 'insufficient_evidence')),
  confidence REAL,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fragment_id, method_version)
);

CREATE TABLE IF NOT EXISTS liberty_enforcement_methodologies (
  method_version TEXT PRIMARY KEY,
  method_label TEXT NOT NULL,
  thresholds_json TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_enforcement_observations (
  observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  observation_key TEXT NOT NULL UNIQUE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  method_version TEXT NOT NULL REFERENCES liberty_enforcement_methodologies(method_version) ON DELETE RESTRICT,
  territory_key TEXT NOT NULL,
  territory_label TEXT,
  period_date TEXT NOT NULL,
  sanction_rate_per_1000 REAL,
  annulment_rate REAL,
  resolution_delay_p90_days REAL,
  sample_size INTEGER,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fragment_id, method_version, territory_key, period_date)
);

CREATE TABLE IF NOT EXISTS liberty_indirect_methodologies (
  method_version TEXT PRIMARY KEY,
  method_label TEXT NOT NULL,
  confidence_rules_json TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_indirect_responsibility_edges (
  edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
  edge_key TEXT NOT NULL UNIQUE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  method_version TEXT NOT NULL REFERENCES liberty_indirect_methodologies(method_version) ON DELETE RESTRICT,
  actor_label TEXT NOT NULL,
  actor_person_name TEXT,
  actor_role_title TEXT,
  role TEXT NOT NULL CHECK (role IN ('delegate', 'appoint', 'instruct', 'design')),
  direct_actor_label TEXT,
  appointment_start_date TEXT,
  appointment_end_date TEXT,
  causal_distance INTEGER NOT NULL CHECK (causal_distance >= 1 AND causal_distance <= 5),
  edge_confidence REAL NOT NULL CHECK (edge_confidence >= 0.0 AND edge_confidence <= 1.0),
  evidence_date TEXT,
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fragment_id, method_version, actor_label, role, direct_actor_label, source_url)
);

CREATE TABLE IF NOT EXISTS liberty_delegated_enforcement_methodologies (
  method_version TEXT PRIMARY KEY,
  method_label TEXT NOT NULL,
  rules_json TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS liberty_delegated_enforcement_links (
  link_id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_key TEXT NOT NULL UNIQUE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  method_version TEXT NOT NULL REFERENCES liberty_delegated_enforcement_methodologies(method_version) ON DELETE RESTRICT,
  delegating_actor_label TEXT NOT NULL,
  delegated_institution_label TEXT NOT NULL,
  designated_role_title TEXT,
  designated_actor_label TEXT,
  appointment_start_date TEXT,
  appointment_end_date TEXT,
  enforcement_action_label TEXT,
  enforcement_evidence_date TEXT,
  chain_confidence REAL CHECK (chain_confidence >= 0.0 AND chain_confidence <= 1.0),
  source_id TEXT REFERENCES sources(source_id),
  source_url TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  evidence_quote TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    fragment_id,
    method_version,
    delegating_actor_label,
    delegated_institution_label,
    designated_actor_label,
    source_url
  )
);

CREATE INDEX IF NOT EXISTS idx_runs_source_id ON ingestion_runs(source_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_work_claim
  ON pipeline_work_items (
    pipeline_id,
    state,
    available_at,
    priority DESC,
    work_item_id
  );
CREATE INDEX IF NOT EXISTS idx_pipeline_work_claim_v2
  ON pipeline_work_items (
    pipeline_id,
    state,
    priority DESC,
    work_item_id,
    available_at
  );
CREATE INDEX IF NOT EXISTS idx_pipeline_work_lease
  ON pipeline_work_items (state, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_work_partition
  ON pipeline_work_items (pipeline_id, partition_key, state, work_item_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_work_attempt_item
  ON pipeline_work_attempts (work_item_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_document_fetch_request_events_pipeline
  ON document_fetch_request_events (
    pipeline_id,
    source_host,
    outcome_state,
    document_fetch_request_event_id
  );
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(full_name);
CREATE INDEX IF NOT EXISTS idx_persons_gender_id ON persons(gender_id);
CREATE INDEX IF NOT EXISTS idx_persons_territory_id ON persons(territory_id);
CREATE INDEX IF NOT EXISTS idx_person_identifiers_person_rollup
  ON person_identifiers(person_id, namespace, value, person_identifier_id);
CREATE INDEX IF NOT EXISTS idx_mandates_person ON mandates(person_id);
CREATE INDEX IF NOT EXISTS idx_mandates_institution_id ON mandates(institution_id);
CREATE INDEX IF NOT EXISTS idx_mandates_party_id ON mandates(party_id);
CREATE INDEX IF NOT EXISTS idx_mandates_source ON mandates(source_id);
CREATE INDEX IF NOT EXISTS idx_mandates_actor_partition
  ON mandates(
    source_id,
    level,
    CASE
      WHEN substr(COALESCE(NULLIF(start_date, ''), source_snapshot_date, ''), 1, 4)
        GLOB '[12][0-9][0-9][0-9]'
      THEN substr(COALESCE(NULLIF(start_date, ''), source_snapshot_date, ''), 1, 4)
      ELSE 'unknown'
    END,
    mandate_id
  );

CREATE INDEX IF NOT EXISTS idx_infoelectoral_convocatorias_tipo ON infoelectoral_convocatorias(tipo_convocatoria);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_archivos_convocatoria ON infoelectoral_archivos_extraccion(convocatoria_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_procesos_estado ON infoelectoral_procesos(estado);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_resultados_proceso ON infoelectoral_proceso_resultados(proceso_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_date_chamber
  ON infoelectoral_elected_officials(election_date, chamber, elected_official_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_name
  ON infoelectoral_elected_officials(full_name, election_date);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_party
  ON infoelectoral_elected_officials(candidacy_name, election_date);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_source_record
  ON infoelectoral_elected_officials(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_workbook_row
  ON infoelectoral_elected_officials(source_url, source_row_number);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_presence
  ON infoelectoral_elected_officials(is_present, chamber, election_date);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_person
  ON infoelectoral_elected_officials(person_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_mandate
  ON infoelectoral_elected_officials(mandate_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_party_fk
  ON infoelectoral_elected_officials(party_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_observations_snapshot
  ON infoelectoral_elected_official_observations(snapshot_date, elected_official_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_elected_observations_run
  ON infoelectoral_elected_official_observations(run_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_archives_status
  ON infoelectoral_candidate_archives(status, election_date, archive_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_election
  ON infoelectoral_candidate_occurrences(
    election_date, election_type_code, province_code, candidate_occurrence_id
  );
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_partition
  ON infoelectoral_candidate_occurrences(
    election_type_code, election_year, archive_id, candidate_occurrence_id
  );
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_name
  ON infoelectoral_candidate_occurrences(full_name, election_date);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_party
  ON infoelectoral_candidate_occurrences(party_id, election_date);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_person
  ON infoelectoral_candidate_occurrences(person_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_source_record
  ON infoelectoral_candidate_occurrences(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_occurrence_presence
  ON infoelectoral_candidate_occurrences(archive_id, is_present);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_observations_snapshot
  ON infoelectoral_candidate_observations(snapshot_date, candidate_occurrence_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_candidate_observations_run
  ON infoelectoral_candidate_observations(run_id);
CREATE INDEX IF NOT EXISTS idx_boe_candidate_documents_election
  ON boe_election_candidate_documents(
    election_date, election_type_code, document_id
  );
CREATE INDEX IF NOT EXISTS idx_boe_candidacies_document
  ON boe_election_candidacies(
    document_id, electoral_board, electoral_district, chamber_code,
    candidacy_number
  );
CREATE INDEX IF NOT EXISTS idx_boe_candidate_occurrence_election
  ON boe_election_candidate_occurrences(
    election_date, election_type_code, candidate_occurrence_id
  );
CREATE INDEX IF NOT EXISTS idx_boe_candidate_occurrence_name
  ON boe_election_candidate_occurrences(full_name, election_date);
CREATE INDEX IF NOT EXISTS idx_boe_candidate_occurrence_party
  ON boe_election_candidate_occurrences(party_id, election_date);
CREATE INDEX IF NOT EXISTS idx_boe_candidate_occurrence_person
  ON boe_election_candidate_occurrences(person_id);
CREATE INDEX IF NOT EXISTS idx_boe_candidate_occurrence_source_record
  ON boe_election_candidate_occurrences(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_boe_candidate_correction_target_base
  ON boe_election_candidate_correction_targets(
    base_document_id, correction_document_id
  );
CREATE INDEX IF NOT EXISTS idx_boe_candidate_correction_paragraph_context
  ON boe_election_candidate_correction_paragraphs(
    correction_document_id, electoral_board, electoral_district,
    chamber_code, candidacy_number, source_paragraph_number
  );
CREATE INDEX IF NOT EXISTS idx_boe_candidate_correction_operation_candidacy
  ON boe_election_candidate_correction_operations(
    candidacy_id, correction_document_id, operation_order
  );
CREATE INDEX IF NOT EXISTS idx_boe_effective_candidacy_election
  ON boe_election_effective_candidacies(
    election_date, election_type_code, candidacy_id
  );
CREATE INDEX IF NOT EXISTS idx_boe_effective_candidate_election
  ON boe_election_effective_candidate_occurrences(
    election_date, election_type_code, effective_candidate_occurrence_id
  );
CREATE INDEX IF NOT EXISTS idx_boe_effective_candidate_name
  ON boe_election_effective_candidate_occurrences(full_name, election_date);
CREATE INDEX IF NOT EXISTS idx_boe_effective_candidate_correction
  ON boe_election_effective_candidate_occurrences(correction_operation_id);
CREATE INDEX IF NOT EXISTS idx_mandates_active ON mandates(is_active);
CREATE INDEX IF NOT EXISTS idx_mandates_role_id ON mandates(role_id);
CREATE INDEX IF NOT EXISTS idx_mandates_admin_level_id ON mandates(admin_level_id);
CREATE INDEX IF NOT EXISTS idx_mandates_territory_id ON mandates(territory_id);
CREATE INDEX IF NOT EXISTS idx_mandates_source_record_pk ON mandates(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_source_records_source ON source_records(source_id);
CREATE INDEX IF NOT EXISTS idx_government_org_units_source_id ON government_org_units(source_id);
CREATE INDEX IF NOT EXISTS idx_government_org_units_code ON government_org_units(org_unit_code);
CREATE INDEX IF NOT EXISTS idx_government_org_units_source_record_pk ON government_org_units(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_government_org_units_ministry ON government_org_units(ministry_name);
CREATE INDEX IF NOT EXISTS idx_government_org_units_level ON government_org_units(administration_level);
CREATE INDEX IF NOT EXISTS idx_government_org_relationships_subject
    ON government_org_relationships(subject_org_unit_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_government_org_relationships_object
    ON government_org_relationships(object_org_unit_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_government_org_relationships_codes
    ON government_org_relationships(subject_org_unit_code, object_org_unit_code);
CREATE INDEX IF NOT EXISTS idx_government_positions_org_unit_id ON government_positions(org_unit_id);
CREATE INDEX IF NOT EXISTS idx_person_org_memberships_person_id ON person_org_memberships(person_id);
CREATE INDEX IF NOT EXISTS idx_person_org_memberships_org_unit_id ON person_org_memberships(org_unit_id);
CREATE INDEX IF NOT EXISTS idx_person_org_memberships_party_id ON person_org_memberships(party_id);
CREATE INDEX IF NOT EXISTS idx_person_org_memberships_position_id ON person_org_memberships(position_id);
CREATE INDEX IF NOT EXISTS idx_parliamentary_groups_source
    ON parliamentary_groups(source_id, legislature, group_code);
CREATE INDEX IF NOT EXISTS idx_parliamentary_groups_institution_id
    ON parliamentary_groups(institution_id);
CREATE INDEX IF NOT EXISTS idx_person_parliamentary_group_memberships_person
    ON person_parliamentary_group_memberships(person_id);
CREATE INDEX IF NOT EXISTS idx_person_parliamentary_group_memberships_group
    ON person_parliamentary_group_memberships(parliamentary_group_id);
CREATE INDEX IF NOT EXISTS idx_institutions_admin_level_id ON institutions(admin_level_id);
CREATE INDEX IF NOT EXISTS idx_institutions_territory_id ON institutions(territory_id);
CREATE INDEX IF NOT EXISTS idx_party_aliases_party_id ON party_aliases(party_id);
CREATE INDEX IF NOT EXISTS idx_person_name_aliases_person_id ON person_name_aliases(person_id);
CREATE INDEX IF NOT EXISTS idx_person_name_aliases_person_rollup
  ON person_name_aliases(
    person_id,
    canonical_alias,
    person_name_alias_id,
    alias
  );
CREATE INDEX IF NOT EXISTS idx_person_name_aliases_source_id ON person_name_aliases(source_id);
CREATE INDEX IF NOT EXISTS idx_person_name_aliases_source_record_pk ON person_name_aliases(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_person_name_aliases_source_kind ON person_name_aliases(source_kind);
CREATE INDEX IF NOT EXISTS idx_territories_parent ON territories(parent_territory_id);

CREATE INDEX IF NOT EXISTS idx_parl_vote_events_date ON parl_vote_events(vote_date);
CREATE INDEX IF NOT EXISTS idx_parl_vote_events_source ON parl_vote_events(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_member_votes_event ON parl_vote_member_votes(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_member_votes_person ON parl_vote_member_votes(person_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_member_votes_source_name
    ON parl_vote_member_votes(source_id, member_name_normalized);

CREATE INDEX IF NOT EXISTS idx_parl_initiatives_exp ON parl_initiatives(expediente);
CREATE INDEX IF NOT EXISTS idx_parl_initiatives_leg ON parl_initiatives(legislature);
CREATE INDEX IF NOT EXISTS idx_parl_initiatives_source ON parl_initiatives(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_documents_initiative ON parl_initiative_documents(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_documents_url ON parl_initiative_documents(doc_url);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_documents_source_record_pk ON parl_initiative_documents(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_text_versions_initiative ON parl_initiative_text_versions(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_text_versions_pubdate ON parl_initiative_text_versions(published_date);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_text_versions_source_record_pk ON parl_initiative_text_versions(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_parl_text_fragments_text_version ON parl_text_fragments(initiative_text_version_id);
CREATE INDEX IF NOT EXISTS idx_parl_text_fragments_initiative ON parl_text_fragments(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_text_fragments_kind ON parl_text_fragments(fragment_kind);
CREATE INDEX IF NOT EXISTS idx_parl_fragment_measure_reviews_status ON parl_fragment_measure_reviews(status);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_vote ON parl_vote_event_initiatives(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_init ON parl_vote_event_initiatives(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_text_versions_vote ON parl_vote_event_text_versions(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_text_versions_init ON parl_vote_event_text_versions(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_text_versions_version ON parl_vote_event_text_versions(initiative_text_version_id);

CREATE INDEX IF NOT EXISTS idx_topic_sets_institution_id ON topic_sets(institution_id);
CREATE INDEX IF NOT EXISTS idx_topic_sets_admin_level_id ON topic_sets(admin_level_id);
CREATE INDEX IF NOT EXISTS idx_topic_sets_territory_id ON topic_sets(territory_id);
CREATE INDEX IF NOT EXISTS idx_topics_parent_topic_id ON topics(parent_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_set_topics_topic_id ON topic_set_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_topic_id ON topic_evidence(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_person_id ON topic_evidence(person_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_mandate_id ON topic_evidence(mandate_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_vote_event_id ON topic_evidence(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_initiative_id ON topic_evidence(initiative_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_source_id ON topic_evidence(source_id);
CREATE INDEX IF NOT EXISTS idx_topic_positions_topic_id ON topic_positions(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_positions_person_id ON topic_positions(person_id);
CREATE INDEX IF NOT EXISTS idx_topic_positions_mandate_id ON topic_positions(mandate_id);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_set_topic_person ON topic_evidence(topic_set_id, topic_id, person_id);
CREATE INDEX IF NOT EXISTS idx_topic_positions_set_topic_person ON topic_positions(topic_set_id, topic_id, person_id);
CREATE INDEX IF NOT EXISTS idx_topic_positions_set_topic_stance ON topic_positions(topic_set_id, topic_id, stance);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_reviews_status ON topic_evidence_reviews(status);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_reviews_reason ON topic_evidence_reviews(review_reason);
CREATE INDEX IF NOT EXISTS idx_topic_evidence_reviews_source_id ON topic_evidence_reviews(source_id);
CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_person_id ON person_public_data_queue(person_id);
CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_status ON person_public_data_queue(status);
CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_priority ON person_public_data_queue(priority);
CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_gap_code ON person_public_data_queue(gap_code);
CREATE INDEX IF NOT EXISTS idx_person_public_data_queue_source_id ON person_public_data_queue(suggested_source_id);
CREATE INDEX IF NOT EXISTS idx_text_documents_source_id ON text_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_text_documents_source_record_pk ON text_documents(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_text_documents_source_url ON text_documents(source_url);
CREATE INDEX IF NOT EXISTS idx_text_documents_content_sha256 ON text_documents(content_sha256);
CREATE INDEX IF NOT EXISTS idx_text_documents_text_sha256 ON text_documents(text_sha256);
CREATE INDEX IF NOT EXISTS idx_document_fetches_source_id ON document_fetches(source_id);
CREATE INDEX IF NOT EXISTS idx_document_fetches_fetched_ok ON document_fetches(fetched_ok);
CREATE INDEX IF NOT EXISTS idx_document_fetches_last_http_status ON document_fetches(last_http_status);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_source_id ON parl_initiative_doc_extractions(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_review ON parl_initiative_doc_extractions(needs_review);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_sample_initiative_id ON parl_initiative_doc_extractions(sample_initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_ocr ON parl_initiative_doc_extractions(needs_ocr);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_status ON parl_vote_implication_reviews(status);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_reason ON parl_vote_implication_reviews(review_reason);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_source_id ON parl_vote_implication_reviews(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_priority ON parl_vote_implication_reviews(priority DESC);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_vote_event_id ON parl_vote_implication_reviews(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_implication_reviews_initiative_id ON parl_vote_implication_reviews(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_review_tasks_status ON parl_initiative_measure_review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_review_tasks_source_id ON parl_initiative_measure_review_tasks(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_review_tasks_priority ON parl_initiative_measure_review_tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_points_task_id ON parl_initiative_measure_points(task_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_points_initiative_id ON parl_initiative_measure_points(initiative_id);
CREATE INDEX IF NOT EXISTS idx_parl_initiative_measure_points_support_side ON parl_initiative_measure_points(support_side);

CREATE INDEX IF NOT EXISTS idx_domains_tier ON domains(tier);
CREATE INDEX IF NOT EXISTS idx_policy_axes_domain_id ON policy_axes(domain_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_domain_id ON policy_events(domain_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_instrument_id ON policy_events(policy_instrument_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_source_id ON policy_events(source_id);
CREATE INDEX IF NOT EXISTS idx_policy_event_axis_scores_axis_id ON policy_event_axis_scores(policy_axis_id);
CREATE INDEX IF NOT EXISTS idx_money_contract_records_source_id ON money_contract_records(source_id);
CREATE INDEX IF NOT EXISTS idx_money_contract_records_contract_id ON money_contract_records(contract_id);
CREATE INDEX IF NOT EXISTS idx_money_contract_records_cpv_code ON money_contract_records(cpv_code);
CREATE INDEX IF NOT EXISTS idx_money_contract_records_published_date ON money_contract_records(published_date);
CREATE INDEX IF NOT EXISTS idx_money_contract_records_stable_contract
  ON money_contract_records(source_id, stable_contract_id, entry_updated_at);
CREATE INDEX IF NOT EXISTS idx_money_contract_awards_source_record
  ON money_contract_award_results(source_record_pk, award_ordinal);
CREATE INDEX IF NOT EXISTS idx_money_contract_awards_supplier
  ON money_contract_award_results(supplier_identifier, award_date);
CREATE INDEX IF NOT EXISTS idx_money_contract_awards_amount
  ON money_contract_award_results(amount_eur_decimal);
CREATE INDEX IF NOT EXISTS idx_money_contract_documents_source_record
  ON money_contract_documents(source_record_pk, document_ordinal);
CREATE INDEX IF NOT EXISTS idx_money_contract_documents_url
  ON money_contract_documents(source_url, contract_document_id);
CREATE INDEX IF NOT EXISTS idx_money_contract_documents_download
  ON money_contract_documents(document_source_record_pk, contract_document_id);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_records_source_id ON placsp_contract_detail_records(source_id);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_records_contract_id ON placsp_contract_detail_records(contract_id);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_records_file_number ON placsp_contract_detail_records(file_number);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_records_cpv_code ON placsp_contract_detail_records(cpv_code);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_records_state ON placsp_contract_detail_records(state);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_documents_source_id ON placsp_contract_detail_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_documents_source_record_pk ON placsp_contract_detail_documents(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_placsp_contract_detail_documents_doc_date ON placsp_contract_detail_documents(doc_reference_date);
CREATE INDEX IF NOT EXISTS idx_money_subsidy_records_source_id ON money_subsidy_records(source_id);
CREATE INDEX IF NOT EXISTS idx_money_subsidy_records_call_id ON money_subsidy_records(call_id);
CREATE INDEX IF NOT EXISTS idx_money_subsidy_records_beneficiary_id
    ON money_subsidy_records(beneficiary_identifier);
CREATE INDEX IF NOT EXISTS idx_money_subsidy_records_published_date ON money_subsidy_records(published_date);
CREATE INDEX IF NOT EXISTS idx_money_bulk_runs_source_state
    ON money_bulk_runs(source_id, state, money_bulk_run_id);
CREATE INDEX IF NOT EXISTS idx_money_bulk_partitions_run_key
    ON money_bulk_partitions(money_bulk_run_id, partition_key);
CREATE INDEX IF NOT EXISTS idx_money_bulk_page_fetches_run_page
    ON money_bulk_page_fetches(money_bulk_run_id, page_number);
CREATE INDEX IF NOT EXISTS idx_money_bulk_page_fetches_partition_page
    ON money_bulk_page_fetches(money_bulk_partition_id, source_page_number);
CREATE INDEX IF NOT EXISTS idx_money_bulk_page_fetches_content
    ON money_bulk_page_fetches(content_sha256);
CREATE INDEX IF NOT EXISTS idx_money_source_record_versions_record
    ON money_source_record_versions(source_id, source_record_id, money_source_record_version_id);
CREATE INDEX IF NOT EXISTS idx_money_source_record_versions_hash
    ON money_source_record_versions(record_sha256);
CREATE INDEX IF NOT EXISTS idx_money_bulk_record_sightings_run_page
    ON money_bulk_record_sightings(money_bulk_run_id, money_bulk_page_fetch_id);
CREATE INDEX IF NOT EXISTS idx_money_bulk_record_sightings_version
    ON money_bulk_record_sightings(money_source_record_version_id);
CREATE INDEX IF NOT EXISTS idx_placsp_bulk_archives_run_status
  ON placsp_bulk_archives(placsp_bulk_run_id, status, placsp_bulk_archive_id);
CREATE INDEX IF NOT EXISTS idx_placsp_bulk_members_archive_status
  ON placsp_bulk_members(placsp_bulk_archive_id, status, placsp_bulk_member_id);
CREATE INDEX IF NOT EXISTS idx_placsp_bulk_sightings_run_record
  ON placsp_bulk_record_sightings(placsp_bulk_run_id, source_record_pk);
CREATE INDEX IF NOT EXISTS idx_placsp_bulk_sightings_stable
  ON placsp_bulk_record_sightings(source_id, stable_contract_id, entry_content_sha256);
CREATE INDEX IF NOT EXISTS idx_interventions_domain_id ON interventions(domain_id);
CREATE INDEX IF NOT EXISTS idx_intervention_events_event_id ON intervention_events(policy_event_id);
CREATE INDEX IF NOT EXISTS idx_indicator_series_domain_id ON indicator_series(domain_id);
CREATE INDEX IF NOT EXISTS idx_indicator_points_series_date ON indicator_points(indicator_series_id, date);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_source_series
    ON indicator_observation_records(source_id, series_code);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_point_date
    ON indicator_observation_records(point_date);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_series_date
    ON indicator_observation_records(indicator_series_id, point_date);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_partition
    ON indicator_observation_records(
      source_id,
      substr(point_date, 1, 4),
      point_date,
      series_code,
      COALESCE(source_snapshot_date, ''),
      COALESCE(source_record_id, ''),
      observation_record_id
    );
CREATE INDEX IF NOT EXISTS idx_indicator_definitions_source_dataset
    ON indicator_definitions(source_id, dataset_code);
CREATE INDEX IF NOT EXISTS idx_indicator_releases_indicator_snapshot
    ON indicator_releases(indicator_id, source_snapshot_date);
CREATE INDEX IF NOT EXISTS idx_indicator_series_versions_indicator_geo
    ON indicator_series_versions(indicator_id, geography_code);
CREATE INDEX IF NOT EXISTS idx_indicator_series_versions_stable_key
    ON indicator_series_versions(stable_series_key, indicator_release_id);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_versions_release_period
    ON indicator_observation_versions(indicator_release_id, period_start);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_versions_series_period
    ON indicator_observation_versions(indicator_series_version_id, period_start);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_versions_revision
    ON indicator_observation_versions(revision_state, previous_observation_version_id);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_evidence_observation
    ON indicator_observation_evidence(indicator_observation_version_id);
CREATE INDEX IF NOT EXISTS idx_causal_estimates_intervention_id ON causal_estimates(intervention_id);

CREATE INDEX IF NOT EXISTS idx_legal_norms_scope ON legal_norms(scope);
CREATE INDEX IF NOT EXISTS idx_legal_norms_topic_hint ON legal_norms(topic_hint);
CREATE INDEX IF NOT EXISTS idx_legal_norm_fragments_norm_id ON legal_norm_fragments(norm_id);
CREATE INDEX IF NOT EXISTS idx_legal_norm_fragments_type ON legal_norm_fragments(fragment_type);
CREATE INDEX IF NOT EXISTS idx_legal_norm_fragments_competent_body ON legal_norm_fragments(competent_body);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibilities_fragment_id
    ON legal_fragment_responsibilities(fragment_id);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibilities_role
    ON legal_fragment_responsibilities(role);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibilities_person_id
    ON legal_fragment_responsibilities(person_id);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibilities_institution_id
    ON legal_fragment_responsibilities(institution_id);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibility_evidence_responsibility_id
    ON legal_fragment_responsibility_evidence(responsibility_id);
CREATE INDEX IF NOT EXISTS idx_legal_fragment_responsibility_evidence_type
    ON legal_fragment_responsibility_evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_sanction_norm_catalog_scope ON sanction_norm_catalog(scope);
CREATE INDEX IF NOT EXISTS idx_sanction_norm_fragment_links_fragment_id
    ON sanction_norm_fragment_links(fragment_id);
CREATE INDEX IF NOT EXISTS idx_legal_norm_lineage_edges_norm_id
    ON legal_norm_lineage_edges(norm_id);
CREATE INDEX IF NOT EXISTS idx_legal_norm_lineage_edges_related_norm_id
    ON legal_norm_lineage_edges(related_norm_id);
CREATE INDEX IF NOT EXISTS idx_legal_norm_lineage_edges_relation_type
    ON legal_norm_lineage_edges(relation_type);
CREATE INDEX IF NOT EXISTS idx_sanction_volume_sources_admin_scope
    ON sanction_volume_sources(admin_scope);
CREATE INDEX IF NOT EXISTS idx_sanction_infraction_types_domain
    ON sanction_infraction_types(domain);
CREATE INDEX IF NOT EXISTS idx_sanction_infraction_type_mappings_infraction_type_id
    ON sanction_infraction_type_mappings(infraction_type_id);
CREATE INDEX IF NOT EXISTS idx_sanction_infraction_type_mappings_norm_id
    ON sanction_infraction_type_mappings(norm_id);
CREATE INDEX IF NOT EXISTS idx_sanction_infraction_type_mappings_fragment_id
    ON sanction_infraction_type_mappings(fragment_id);
CREATE INDEX IF NOT EXISTS idx_sanction_volume_observations_source_period
    ON sanction_volume_observations(sanction_source_id, period_date);
CREATE INDEX IF NOT EXISTS idx_sanction_volume_observations_infraction_type_id
    ON sanction_volume_observations(infraction_type_id);
CREATE INDEX IF NOT EXISTS idx_sanction_volume_observations_norm_id
    ON sanction_volume_observations(norm_id);
CREATE INDEX IF NOT EXISTS idx_sanction_volume_observations_fragment_id
    ON sanction_volume_observations(fragment_id);
CREATE INDEX IF NOT EXISTS idx_sanction_procedural_metrics_kpi_period
    ON sanction_procedural_metrics(kpi_id, period_date);
CREATE INDEX IF NOT EXISTS idx_sanction_municipal_ordinances_city_status
    ON sanction_municipal_ordinances(city_name, ordinance_status);
CREATE INDEX IF NOT EXISTS idx_sanction_municipal_ordinance_fragments_ordinance_id
    ON sanction_municipal_ordinance_fragments(ordinance_id);
CREATE INDEX IF NOT EXISTS idx_sanction_municipal_ordinance_fragments_mapped_norm_id
    ON sanction_municipal_ordinance_fragments(mapped_norm_id);
CREATE INDEX IF NOT EXISTS idx_sanction_municipal_ordinance_fragments_mapped_fragment_id
    ON sanction_municipal_ordinance_fragments(mapped_fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_restriction_assessments_fragment_id
    ON liberty_restriction_assessments(fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_restriction_assessments_right_category_id
    ON liberty_restriction_assessments(right_category_id);
CREATE INDEX IF NOT EXISTS idx_liberty_restriction_assessments_irlc_score
    ON liberty_restriction_assessments(irlc_score DESC);
CREATE INDEX IF NOT EXISTS idx_liberty_proportionality_reviews_fragment_id
    ON liberty_proportionality_reviews(fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_proportionality_reviews_assessment_label
    ON liberty_proportionality_reviews(assessment_label);
CREATE INDEX IF NOT EXISTS idx_liberty_proportionality_reviews_proportionality_score
    ON liberty_proportionality_reviews(proportionality_score ASC);
CREATE INDEX IF NOT EXISTS idx_liberty_enforcement_observations_fragment_id
    ON liberty_enforcement_observations(fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_enforcement_observations_territory_key
    ON liberty_enforcement_observations(territory_key);
CREATE INDEX IF NOT EXISTS idx_liberty_enforcement_observations_period_date
    ON liberty_enforcement_observations(period_date);
CREATE INDEX IF NOT EXISTS idx_liberty_indirect_edges_fragment_id
    ON liberty_indirect_responsibility_edges(fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_indirect_edges_role
    ON liberty_indirect_responsibility_edges(role);
CREATE INDEX IF NOT EXISTS idx_liberty_indirect_edges_confidence
    ON liberty_indirect_responsibility_edges(edge_confidence DESC);
CREATE INDEX IF NOT EXISTS idx_liberty_indirect_edges_causal_distance
    ON liberty_indirect_responsibility_edges(causal_distance ASC);
CREATE INDEX IF NOT EXISTS idx_liberty_delegated_links_fragment_id
    ON liberty_delegated_enforcement_links(fragment_id);
CREATE INDEX IF NOT EXISTS idx_liberty_delegated_links_delegated_institution
    ON liberty_delegated_enforcement_links(delegated_institution_label);
CREATE INDEX IF NOT EXISTS idx_liberty_delegated_links_designated_actor
    ON liberty_delegated_enforcement_links(designated_actor_label);
CREATE INDEX IF NOT EXISTS idx_liberty_delegated_links_chain_confidence
    ON liberty_delegated_enforcement_links(chain_confidence DESC);

-- Safety-gated anomaly/integrity review. A signal is not an allegation.
CREATE TABLE IF NOT EXISTS integrity_signals (
  signal_id TEXT PRIMARY KEY,
  detector_id TEXT NOT NULL,
  detector_version TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  jurisdiction TEXT,
  period_start TEXT,
  period_end TEXT,
  state TEXT NOT NULL CHECK (state IN (
    'observed_fact','review_signal','corroborated_risk','official_finding',
    'rejected','superseded'
  )),
  review_priority INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL,
  metrics_json TEXT NOT NULL DEFAULT '{}',
  limitations_json TEXT NOT NULL DEFAULT '[]',
  publication_status TEXT NOT NULL DEFAULT 'internal' CHECK (publication_status IN (
    'internal','approved','published','withdrawn'
  )),
  right_of_reply_status TEXT NOT NULL DEFAULT 'pending' CHECK (right_of_reply_status IN (
    'pending','received','declined','no_response_after_deadline','not_required'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    detector_id, detector_version, signal_type, subject_type, subject_id,
    period_start, period_end
  )
);

CREATE TABLE IF NOT EXISTS integrity_signal_evidence (
  signal_evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  evidence_role TEXT NOT NULL CHECK (evidence_role IN (
    'observed','corroborating','counterevidence','official_finding','context'
  )),
  independent_source_key TEXT NOT NULL,
  source_id TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_url TEXT,
  content_sha256 TEXT,
  excerpt TEXT,
  observed_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (
    signal_id, evidence_role, independent_source_key, source_id,
    source_record_pk, source_url
  )
);

CREATE TABLE IF NOT EXISTS integrity_signal_reviews (
  signal_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  reviewer_id TEXT NOT NULL,
  reviewer_independence_class TEXT NOT NULL DEFAULT 'unknown' CHECK (
    reviewer_independence_class IN ('author','maintainer','independent','unknown')
  ),
  decision TEXT NOT NULL CHECK (decision IN (
    'needs_more_evidence','corroborate','reject','approve_publication','withdraw'
  )),
  rationale TEXT NOT NULL,
  reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_transitions (
  signal_transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  actor_kind TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  transitioned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_responses (
  signal_response_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  response_status TEXT NOT NULL CHECK (response_status IN (
    'received','declined','no_response_after_deadline','not_required'
  )),
  response_source_url TEXT,
  response_content_sha256 TEXT,
  response_summary TEXT,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_corrections (
  signal_correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  correction_type TEXT NOT NULL CHECK (correction_type IN (
    'counterevidence','factual_correction','identity_correction','withdrawal','supersession'
  )),
  rationale TEXT NOT NULL,
  evidence_url TEXT,
  corrected_by TEXT NOT NULL,
  corrected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integrity_signals_state_priority
  ON integrity_signals(state, review_priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signals_subject
  ON integrity_signals(subject_type, subject_id, period_start);
CREATE INDEX IF NOT EXISTS idx_integrity_signals_publication
  ON integrity_signals(publication_status, state, updated_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_evidence_signal_role
  ON integrity_signal_evidence(signal_id, evidence_role, independent_source_key);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_transitions_signal
  ON integrity_signal_transitions(signal_id, transitioned_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_reviews_signal
  ON integrity_signal_reviews(signal_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_money_contract_integrity_group
  ON money_contract_records(
    contracting_authority, cpv_code, awarded_date, published_date, amount_eur
  );
CREATE INDEX IF NOT EXISTS idx_indicator_bulk_acquisitions_pipeline
  ON indicator_bulk_acquisitions(pipeline_id, status, dataset_code);
CREATE INDEX IF NOT EXISTS idx_indicator_bulk_acquisition_records_source
  ON indicator_bulk_acquisition_records(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_source_records_indicator_backfill
  ON source_records(
    source_id,
    COALESCE(source_snapshot_date, ''),
    source_record_id,
    source_record_pk
  );

-- Outcome-context candidate/review/release graph (v1).
-- BEGIN OUTCOME LINKING V1 SCHEMA
CREATE TABLE IF NOT EXISTS outcome_links (
  outcome_link_id TEXT PRIMARY KEY,
  identity_contract_version TEXT NOT NULL,
  link_kind TEXT NOT NULL CHECK (link_kind = 'descriptive_outcome_context'),
  action_id TEXT NOT NULL,
  indicator_id TEXT NOT NULL,
  stable_series_key TEXT NOT NULL,
  geography_code TEXT NOT NULL,
  geography_level TEXT NOT NULL,
  geography_system TEXT NOT NULL,
  identity_sha256 TEXT NOT NULL CHECK (
    length(identity_sha256) = 64 AND identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  identity_canonical_bytes INTEGER NOT NULL CHECK (identity_canonical_bytes > 0),
  identity_preimage_json TEXT NOT NULL CHECK (json_valid(identity_preimage_json)),
  created_at TEXT NOT NULL,
  UNIQUE (identity_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_link_versions (
  outcome_link_version_id TEXT PRIMARY KEY,
  outcome_link_id TEXT NOT NULL
    REFERENCES outcome_links(outcome_link_id) ON DELETE RESTRICT,
  version_identity_sha256 TEXT NOT NULL CHECK (
    length(version_identity_sha256) = 64
    AND version_identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  version_identity_canonical_bytes INTEGER NOT NULL
    CHECK (version_identity_canonical_bytes > 0),
  identity_contract_version TEXT NOT NULL,
  method_version TEXT NOT NULL,
  evidence_package_kind TEXT NOT NULL,
  version_state TEXT NOT NULL CHECK (
    version_state IN ('preproduction_candidate', 'reviewable', 'superseded')
  ),
  evidence_level TEXT NOT NULL CHECK (evidence_level IN ('L0', 'L1', 'L2')),
  candidate_status TEXT NOT NULL CHECK (
    candidate_status IN (
      'pending_human_review', 'human_reviewed', 'rejected', 'superseded'
    )
  ),
  machine_audit_state TEXT NOT NULL CHECK (
    machine_audit_state IN ('pending', 'machine_validated', 'failed')
  ),
  human_review_required INTEGER NOT NULL CHECK (human_review_required IN (0, 1)),
  human_review_completed INTEGER NOT NULL CHECK (human_review_completed IN (0, 1)),
  published INTEGER NOT NULL CHECK (published IN (0, 1)),
  directional_countable INTEGER NOT NULL CHECK (directional_countable IN (0, 1)),
  ranking_eligible INTEGER NOT NULL CHECK (ranking_eligible IN (0, 1)),
  action_id TEXT NOT NULL,
  action_occurred_at TEXT NOT NULL,
  action_source_id TEXT NOT NULL,
  action_source_record_id TEXT NOT NULL,
  action_source_snapshot_date TEXT NOT NULL,
  action_source_record_content_sha256 TEXT NOT NULL,
  initiative_id TEXT NOT NULL,
  initiative_source_id TEXT NOT NULL,
  initiative_source_record_id TEXT NOT NULL,
  initiative_source_record_content_sha256 TEXT NOT NULL,
  original_vote_xml_capture_state TEXT NOT NULL,
  original_vote_xml_content_sha256 TEXT,
  indicator_id TEXT NOT NULL,
  indicator_release_id TEXT NOT NULL,
  indicator_series_version_id TEXT NOT NULL,
  indicator_source_content_sha256 TEXT NOT NULL,
  action_scope_sha256 TEXT NOT NULL,
  action_scope_kind TEXT NOT NULL CHECK (action_scope_kind = 'action'),
  indicator_scope_sha256 TEXT NOT NULL,
  indicator_scope_kind TEXT NOT NULL CHECK (indicator_scope_kind = 'indicator'),
  actor_reference_scope_sha256 TEXT NOT NULL,
  actor_reference_scope_kind TEXT NOT NULL CHECK (
    actor_reference_scope_kind = 'actor_reference'
  ),
  combined_scope_sha256 TEXT NOT NULL,
  combined_scope_kind TEXT NOT NULL CHECK (combined_scope_kind = 'combined'),
  participant_count INTEGER NOT NULL CHECK (participant_count >= 0),
  participant_source_projection_sha256 TEXT NOT NULL,
  participant_export_projection_sha256 TEXT NOT NULL,
  actor_graph_release_id TEXT NOT NULL,
  actor_reference_projection_sha256 TEXT NOT NULL,
  actor_reference_label_mismatch_count INTEGER NOT NULL CHECK (
    actor_reference_label_mismatch_count >= 0
  ),
  version_identity_preimage_json TEXT NOT NULL
    CHECK (json_valid(version_identity_preimage_json)),
  action_json TEXT NOT NULL CHECK (json_valid(action_json)),
  participant_contract_json TEXT NOT NULL CHECK (json_valid(participant_contract_json)),
  indicator_json TEXT NOT NULL CHECK (json_valid(indicator_json)),
  temporal_assessment_json TEXT NOT NULL CHECK (json_valid(temporal_assessment_json)),
  semantic_assessment_json TEXT NOT NULL CHECK (json_valid(semantic_assessment_json)),
  geography_assessment_json TEXT NOT NULL CHECK (json_valid(geography_assessment_json)),
  calculation_json TEXT NOT NULL CHECK (json_valid(calculation_json)),
  claim_policy_json TEXT NOT NULL CHECK (json_valid(claim_policy_json)),
  reason_codes_json TEXT NOT NULL CHECK (json_valid(reason_codes_json)),
  limitations_json TEXT NOT NULL CHECK (json_valid(limitations_json)),
  reader_wording_json TEXT NOT NULL CHECK (json_valid(reader_wording_json)),
  supersedes_outcome_link_version_id TEXT
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  CHECK (
    published = 0 OR (
      evidence_level = 'L2'
      AND human_review_completed = 1
      AND candidate_status = 'human_reviewed'
      AND machine_audit_state = 'machine_validated'
    )
  ),
  FOREIGN KEY (action_scope_sha256, action_scope_kind)
    REFERENCES outcome_link_scope_closures(scope_closure_sha256, scope_kind)
    ON DELETE RESTRICT,
  FOREIGN KEY (indicator_scope_sha256, indicator_scope_kind)
    REFERENCES outcome_link_scope_closures(scope_closure_sha256, scope_kind)
    ON DELETE RESTRICT,
  FOREIGN KEY (actor_reference_scope_sha256, actor_reference_scope_kind)
    REFERENCES outcome_link_scope_closures(scope_closure_sha256, scope_kind)
    ON DELETE RESTRICT,
  FOREIGN KEY (combined_scope_sha256, combined_scope_kind)
    REFERENCES outcome_link_scope_closures(scope_closure_sha256, scope_kind)
    ON DELETE RESTRICT,
  UNIQUE (version_identity_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_link_reviews (
  outcome_link_review_version_id TEXT PRIMARY KEY,
  outcome_link_version_id TEXT NOT NULL
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  review_identity_sha256 TEXT NOT NULL CHECK (
    length(review_identity_sha256) = 64
    AND review_identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  review_identity_contract_version TEXT NOT NULL,
  reviewer_public_id TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  review_method TEXT NOT NULL,
  semantic_decision TEXT NOT NULL CHECK (
    semantic_decision IN (
      'target_outcome_confirmed', 'broad_context_only', 'incompatible',
      'needs_context'
    )
  ),
  geography_decision TEXT NOT NULL CHECK (
    geography_decision IN (
      'exact', 'national_scope_compatible', 'nested_not_equal',
      'crosswalk_versioned', 'incompatible', 'needs_context'
    )
  ),
  level_decision TEXT NOT NULL CHECK (level_decision IN ('L0', 'L1', 'L2')),
  evidence_examined_json TEXT NOT NULL CHECK (json_valid(evidence_examined_json)),
  reason_codes_json TEXT NOT NULL CHECK (json_valid(reason_codes_json)),
  rationale TEXT NOT NULL,
  claim_policy_json TEXT NOT NULL CHECK (json_valid(claim_policy_json)),
  reader_wording_json TEXT NOT NULL CHECK (json_valid(reader_wording_json)),
  signoff TEXT NOT NULL,
  review_identity_preimage_json TEXT NOT NULL CHECK (json_valid(review_identity_preimage_json)),
  supersedes_review_version_id TEXT
    REFERENCES outcome_link_reviews(outcome_link_review_version_id) ON DELETE RESTRICT,
  UNIQUE (review_identity_sha256),
  UNIQUE (outcome_link_review_version_id, outcome_link_version_id),
  UNIQUE (
    outcome_link_review_version_id, outcome_link_version_id,
    semantic_decision, geography_decision, level_decision
  )
);

CREATE TABLE IF NOT EXISTS outcome_link_releases (
  outcome_link_release_id TEXT PRIMARY KEY,
  release_identity_contract_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  method_version TEXT NOT NULL,
  config_sha256 TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  source_release_roots_json TEXT NOT NULL CHECK (json_valid(source_release_roots_json)),
  scope_closure_root_sha256 TEXT NOT NULL,
  membership_semantic_root_sha256 TEXT NOT NULL,
  member_count INTEGER NOT NULL CHECK (member_count >= 0),
  review_count_by_state_json TEXT NOT NULL CHECK (json_valid(review_count_by_state_json)),
  level_counts_json TEXT NOT NULL CHECK (json_valid(level_counts_json)),
  previous_outcome_link_release_id TEXT
    REFERENCES outcome_link_releases(outcome_link_release_id) ON DELETE RESTRICT,
  release_descriptor_sha256 TEXT NOT NULL CHECK (
    length(release_descriptor_sha256) = 64
    AND release_descriptor_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  release_descriptor_json TEXT NOT NULL CHECK (json_valid(release_descriptor_json)),
  UNIQUE (release_descriptor_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_link_release_memberships (
  outcome_link_release_membership_id TEXT PRIMARY KEY,
  outcome_link_release_id TEXT NOT NULL
    REFERENCES outcome_link_releases(outcome_link_release_id) ON DELETE RESTRICT,
  outcome_link_version_id TEXT NOT NULL
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  outcome_link_review_version_id TEXT
    REFERENCES outcome_link_reviews(outcome_link_review_version_id) ON DELETE RESTRICT,
  membership_identity_sha256 TEXT NOT NULL CHECK (
    length(membership_identity_sha256) = 64
    AND membership_identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  membership_state TEXT NOT NULL CHECK (
    membership_state IN ('included', 'excluded', 'withdrawn', 'superseded')
  ),
  selected_level TEXT NOT NULL CHECK (selected_level IN ('L0', 'L1', 'L2')),
  selected_decision TEXT CHECK (
    selected_decision IS NULL OR selected_decision IN (
      'target_outcome_confirmed', 'broad_context_only', 'incompatible',
      'needs_context'
    )
  ),
  selected_semantic_decision TEXT CHECK (
    selected_semantic_decision IS NULL OR selected_semantic_decision IN (
      'target_outcome_confirmed', 'broad_context_only', 'incompatible',
      'needs_context'
    )
  ),
  selected_geography_decision TEXT CHECK (
    selected_geography_decision IS NULL OR selected_geography_decision IN (
      'exact', 'national_scope_compatible', 'nested_not_equal',
      'crosswalk_versioned', 'incompatible', 'needs_context'
    )
  ),
  inclusion_reason TEXT NOT NULL,
  publication_flag INTEGER NOT NULL CHECK (publication_flag IN (0, 1)),
  membership_identity_preimage_json TEXT NOT NULL
    CHECK (json_valid(membership_identity_preimage_json)),
  CHECK (selected_decision IS selected_semantic_decision),
  CHECK (
    outcome_link_review_version_id IS NULL OR (
      selected_semantic_decision IS NOT NULL
      AND selected_geography_decision IS NOT NULL
    )
  ),
  CHECK (
    publication_flag = 0 OR (
      outcome_link_review_version_id IS NOT NULL
      AND selected_level = 'L2'
      AND membership_state = 'included'
      AND selected_decision IS NOT NULL
    )
  ),
  UNIQUE (membership_identity_sha256),
  UNIQUE (outcome_link_release_id, outcome_link_version_id),
  FOREIGN KEY (outcome_link_review_version_id, outcome_link_version_id)
    REFERENCES outcome_link_reviews(
      outcome_link_review_version_id, outcome_link_version_id
    ) ON DELETE RESTRICT,
  FOREIGN KEY (
    outcome_link_review_version_id, outcome_link_version_id,
    selected_semantic_decision, selected_geography_decision, selected_level
  ) REFERENCES outcome_link_reviews(
    outcome_link_review_version_id, outcome_link_version_id,
    semantic_decision, geography_decision, level_decision
  ) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS outcome_link_observation_refs (
  outcome_link_observation_ref_id TEXT PRIMARY KEY,
  outcome_link_version_id TEXT NOT NULL
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  identity_sha256 TEXT NOT NULL CHECK (
    length(identity_sha256) = 64 AND identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  identity_contract_version TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('pre', 'overlap_excluded', 'post')),
  exclusion_reason TEXT,
  indicator_id TEXT NOT NULL,
  indicator_release_id TEXT NOT NULL,
  indicator_series_version_id TEXT NOT NULL,
  indicator_observation_version_id TEXT NOT NULL,
  indicator_observation_evidence_id TEXT NOT NULL,
  period_label TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  value_decimal TEXT,
  value_text TEXT,
  source_status_code TEXT,
  uncertainty_state TEXT NOT NULL,
  revision_ordinal INTEGER NOT NULL,
  revision_state TEXT NOT NULL,
  source_content_sha256 TEXT NOT NULL,
  raw_path TEXT NOT NULL,
  value_json_pointer TEXT NOT NULL,
  status_json_pointer TEXT,
  identity_preimage_json TEXT NOT NULL CHECK (json_valid(identity_preimage_json)),
  CHECK (
    (role = 'overlap_excluded' AND exclusion_reason IS NOT NULL)
    OR (role IN ('pre', 'post') AND exclusion_reason IS NULL)
  ),
  UNIQUE (identity_sha256),
  UNIQUE (
    outcome_link_version_id, role, indicator_observation_version_id
  )
);

CREATE TABLE IF NOT EXISTS outcome_link_participant_refs (
  outcome_link_participant_ref_id TEXT PRIMARY KEY,
  outcome_link_version_id TEXT NOT NULL
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  participant_row_semantic_sha256 TEXT NOT NULL CHECK (
    length(participant_row_semantic_sha256) = 64
    AND participant_row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  identity_contract_version TEXT NOT NULL,
  action_id TEXT NOT NULL,
  seat TEXT NOT NULL,
  official_member_name TEXT NOT NULL,
  upstream_person_id TEXT NOT NULL,
  official_group_code TEXT NOT NULL,
  official_vote_choice TEXT NOT NULL,
  actor_graph_release_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  actor_node_version_id TEXT NOT NULL,
  actor_canonical_label TEXT NOT NULL,
  actor_identity_state TEXT NOT NULL,
  actor_provenance_state TEXT NOT NULL,
  actor_source_record_id TEXT,
  actor_source_url TEXT,
  actor_source_content_sha256 TEXT,
  vote_source_id TEXT NOT NULL,
  vote_source_url TEXT NOT NULL,
  vote_source_snapshot_date TEXT NOT NULL,
  vote_source_record_id TEXT NOT NULL,
  vote_source_record_content_sha256 TEXT NOT NULL,
  vote_source_locator TEXT NOT NULL,
  official_label_authoritative INTEGER NOT NULL CHECK (
    official_label_authoritative = 1
  ),
  actor_label_mismatch INTEGER NOT NULL CHECK (actor_label_mismatch IN (0, 1)),
  identity_preimage_json TEXT NOT NULL CHECK (json_valid(identity_preimage_json)),
  CHECK (actor_label_mismatch = (official_member_name <> actor_canonical_label)),
  UNIQUE (participant_row_semantic_sha256),
  UNIQUE (outcome_link_version_id, action_id, seat, upstream_person_id)
);

CREATE TABLE IF NOT EXISTS outcome_link_evidence (
  outcome_link_evidence_id TEXT PRIMARY KEY,
  outcome_link_version_id TEXT NOT NULL
    REFERENCES outcome_link_versions(outcome_link_version_id) ON DELETE RESTRICT,
  identity_sha256 TEXT NOT NULL CHECK (
    length(identity_sha256) = 64 AND identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  identity_contract_version TEXT NOT NULL,
  evidence_role TEXT NOT NULL CHECK (
    evidence_role IN (
      'normalized_vote_source_record',
      'normalized_initiative_source_record',
      'original_vote_xml_gap',
      'indicator_source_bytes',
      'indicator_observation_pre',
      'indicator_observation_overlap_excluded',
      'indicator_observation_post'
    )
  ),
  entity_version_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_record_id TEXT,
  official_url TEXT,
  content_sha256 TEXT CHECK (
    content_sha256 IS NULL OR (
      length(content_sha256) = 64
      AND content_sha256 NOT GLOB '*[^0-9a-f]*'
    )
  ),
  bytes INTEGER CHECK (bytes IS NULL OR bytes >= 0),
  raw_path TEXT,
  locator TEXT,
  capture_state TEXT NOT NULL CHECK (
    capture_state IN (
      'normalized_source_record_present',
      'original_source_bytes_present',
      'absent_from_current_snapshot'
    )
  ),
  normalized_record_is_original_bytes INTEGER NOT NULL CHECK (
    normalized_record_is_original_bytes IN (0, 1)
  ),
  identity_preimage_json TEXT NOT NULL CHECK (json_valid(identity_preimage_json)),
  CHECK (
    (
      evidence_role IN (
        'normalized_vote_source_record',
        'normalized_initiative_source_record'
      )
      AND capture_state = 'normalized_source_record_present'
      AND source_record_id IS NOT NULL
      AND official_url IS NOT NULL
      AND content_sha256 IS NOT NULL
      AND bytes > 0
      AND raw_path IS NULL
      AND locator IS NOT NULL
      AND normalized_record_is_original_bytes = 0
    ) OR (
      evidence_role = 'original_vote_xml_gap'
      AND capture_state = 'absent_from_current_snapshot'
      AND official_url IS NOT NULL
      AND content_sha256 IS NULL
      AND bytes IS NULL
      AND raw_path IS NULL
      AND locator IS NULL
      AND normalized_record_is_original_bytes = 0
    ) OR (
      evidence_role IN (
        'indicator_source_bytes',
        'indicator_observation_pre',
        'indicator_observation_overlap_excluded',
        'indicator_observation_post'
      )
      AND capture_state = 'original_source_bytes_present'
      AND official_url IS NOT NULL
      AND content_sha256 IS NOT NULL
      AND bytes > 0
      AND raw_path IS NOT NULL
      AND locator IS NOT NULL
      AND normalized_record_is_original_bytes = 0
    )
  ),
  UNIQUE (identity_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_link_scope_closures (
  scope_closure_sha256 TEXT PRIMARY KEY CHECK (
    length(scope_closure_sha256) = 64
    AND scope_closure_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  scope_kind TEXT NOT NULL CHECK (
    scope_kind IN ('action', 'indicator', 'actor_reference', 'combined')
  ),
  closure_contract_version TEXT NOT NULL,
  canonical_preimage_json TEXT NOT NULL CHECK (json_valid(canonical_preimage_json)),
  canonical_bytes INTEGER NOT NULL CHECK (canonical_bytes > 0),
  bounded_scope_complete INTEGER NOT NULL CHECK (bounded_scope_complete IN (0, 1)),
  all_possible_actions_searched INTEGER NOT NULL CHECK (
    all_possible_actions_searched IN (0, 1)
  ),
  all_possible_indicators_searched INTEGER NOT NULL CHECK (
    all_possible_indicators_searched IN (0, 1)
  ),
  all_possible_actor_sources_searched INTEGER NOT NULL CHECK (
    all_possible_actor_sources_searched IN (0, 1)
  ),
  all_possible_action_indicator_pairs_searched INTEGER NOT NULL CHECK (
    all_possible_action_indicator_pairs_searched IN (0, 1)
  ),
  UNIQUE (scope_closure_sha256, scope_kind)
);

CREATE INDEX IF NOT EXISTS idx_outcome_link_versions_link_state
  ON outcome_link_versions(outcome_link_id, version_state, outcome_link_version_id);
CREATE INDEX IF NOT EXISTS idx_outcome_link_versions_action
  ON outcome_link_versions(action_id, action_occurred_at, outcome_link_version_id);
CREATE INDEX IF NOT EXISTS idx_outcome_link_versions_indicator
  ON outcome_link_versions(indicator_id, indicator_release_id, outcome_link_version_id);
CREATE INDEX IF NOT EXISTS idx_outcome_link_reviews_version_time
  ON outcome_link_reviews(outcome_link_version_id, reviewed_at, outcome_link_review_version_id);
CREATE INDEX IF NOT EXISTS idx_outcome_link_memberships_release_state
  ON outcome_link_release_memberships(
    outcome_link_release_id, membership_state, outcome_link_release_membership_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_observation_refs_version_role
  ON outcome_link_observation_refs(
    outcome_link_version_id, role, period_start, outcome_link_observation_ref_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_participant_refs_action_person
  ON outcome_link_participant_refs(
    action_id, upstream_person_id, outcome_link_participant_ref_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_participant_refs_actor
  ON outcome_link_participant_refs(
    actor_graph_release_id, actor_id, outcome_link_participant_ref_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_participant_refs_version_seat
  ON outcome_link_participant_refs(
    outcome_link_version_id, CAST(seat AS INTEGER), seat,
    outcome_link_participant_ref_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_evidence_version_role
  ON outcome_link_evidence(
    outcome_link_version_id, evidence_role, outcome_link_evidence_id
  );
CREATE INDEX IF NOT EXISTS idx_outcome_link_scope_closures_kind_sha
  ON outcome_link_scope_closures(scope_kind, scope_closure_sha256);

CREATE TRIGGER IF NOT EXISTS trg_outcome_links_no_update
BEFORE UPDATE ON outcome_links BEGIN
  SELECT RAISE(ABORT, 'outcome_links is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_links_no_delete
BEFORE DELETE ON outcome_links BEGIN
  SELECT RAISE(ABORT, 'outcome_links is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_versions_no_update
BEFORE UPDATE ON outcome_link_versions BEGIN
  SELECT RAISE(ABORT, 'outcome_link_versions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_versions_no_delete
BEFORE DELETE ON outcome_link_versions BEGIN
  SELECT RAISE(ABORT, 'outcome_link_versions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_reviews_no_update
BEFORE UPDATE ON outcome_link_reviews BEGIN
  SELECT RAISE(ABORT, 'outcome_link_reviews is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_reviews_no_delete
BEFORE DELETE ON outcome_link_reviews BEGIN
  SELECT RAISE(ABORT, 'outcome_link_reviews is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_releases_no_update
BEFORE UPDATE ON outcome_link_releases BEGIN
  SELECT RAISE(ABORT, 'outcome_link_releases is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_releases_no_delete
BEFORE DELETE ON outcome_link_releases BEGIN
  SELECT RAISE(ABORT, 'outcome_link_releases is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_release_memberships_no_update
BEFORE UPDATE ON outcome_link_release_memberships BEGIN
  SELECT RAISE(ABORT, 'outcome_link_release_memberships is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_release_memberships_no_delete
BEFORE DELETE ON outcome_link_release_memberships BEGIN
  SELECT RAISE(ABORT, 'outcome_link_release_memberships is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_observation_refs_no_update
BEFORE UPDATE ON outcome_link_observation_refs BEGIN
  SELECT RAISE(ABORT, 'outcome_link_observation_refs is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_observation_refs_no_delete
BEFORE DELETE ON outcome_link_observation_refs BEGIN
  SELECT RAISE(ABORT, 'outcome_link_observation_refs is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_participant_refs_no_update
BEFORE UPDATE ON outcome_link_participant_refs BEGIN
  SELECT RAISE(ABORT, 'outcome_link_participant_refs is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_participant_refs_no_delete
BEFORE DELETE ON outcome_link_participant_refs BEGIN
  SELECT RAISE(ABORT, 'outcome_link_participant_refs is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_evidence_no_update
BEFORE UPDATE ON outcome_link_evidence BEGIN
  SELECT RAISE(ABORT, 'outcome_link_evidence is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_evidence_no_delete
BEFORE DELETE ON outcome_link_evidence BEGIN
  SELECT RAISE(ABORT, 'outcome_link_evidence is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_scope_closures_no_update
BEFORE UPDATE ON outcome_link_scope_closures BEGIN
  SELECT RAISE(ABORT, 'outcome_link_scope_closures is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_link_scope_closures_no_delete
BEFORE DELETE ON outcome_link_scope_closures BEGIN
  SELECT RAISE(ABORT, 'outcome_link_scope_closures is append-only');
END;
-- END OUTCOME LINKING V1 SCHEMA

-- Bounded C2A discovery-pair plan. This is deliberately outside the C1
-- outcome-linking marker: C1's nine-table release contract remains unchanged.
-- BEGIN OUTCOME PAIR PLANNER C2A SCHEMA
CREATE TABLE IF NOT EXISTS pipeline_keyset_checkpoints (
  pipeline_key TEXT NOT NULL,
  stage TEXT NOT NULL,
  partition_key TEXT NOT NULL DEFAULT '',
  checkpoint_contract_version TEXT NOT NULL,
  config_sha256 TEXT NOT NULL CHECK (
    length(config_sha256) = 64 AND config_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  input_root_sha256 TEXT NOT NULL CHECK (
    length(input_root_sha256) = 64
    AND input_root_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  schema_root_sha256 TEXT NOT NULL CHECK (
    length(schema_root_sha256) = 64
    AND schema_root_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  last_key_json TEXT NOT NULL CHECK (json_valid(last_key_json)),
  rows_written INTEGER NOT NULL DEFAULT 0 CHECK (rows_written >= 0),
  batches_committed INTEGER NOT NULL DEFAULT 0 CHECK (batches_committed >= 0),
  semantic_chain_sha256 TEXT NOT NULL CHECK (
    length(semantic_chain_sha256) = 64
    AND semantic_chain_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (pipeline_key, stage, partition_key)
);

CREATE TABLE IF NOT EXISTS outcome_pair_plan_actions (
  action_plan_pk INTEGER PRIMARY KEY,
  pipeline_key TEXT NOT NULL,
  action_id TEXT NOT NULL,
  action_date TEXT NOT NULL CHECK (date(action_date) IS action_date),
  action_year INTEGER NOT NULL CHECK (
    action_year BETWEEN 1900 AND 2999
    AND action_year = CAST(substr(action_date, 1, 4) AS INTEGER)
  ),
  action_label TEXT NOT NULL,
  source_id TEXT NOT NULL CHECK (source_id = 'senado_votaciones'),
  source_record_pk INTEGER NOT NULL,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT NOT NULL,
  official_action_url TEXT NOT NULL CHECK (
    official_action_url LIKE 'https://www.senado.es/%'
  ),
  source_page_url TEXT NOT NULL CHECK (
    source_page_url LIKE 'https://www.senado.es/%'
  ),
  source_record_content_sha256 TEXT NOT NULL CHECK (
    length(source_record_content_sha256) = 64
    AND source_record_content_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  member_vote_count INTEGER NOT NULL CHECK (member_vote_count > 0),
  official_name_count INTEGER NOT NULL CHECK (official_name_count > 0),
  participant_projection_sha256 TEXT NOT NULL CHECK (
    length(participant_projection_sha256) = 64
    AND participant_projection_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (pipeline_key, action_id),
  UNIQUE (pipeline_key, action_plan_pk),
  UNIQUE (pipeline_key, action_plan_pk, action_year)
);

CREATE TABLE IF NOT EXISTS outcome_pair_plan_series (
  series_plan_pk INTEGER PRIMARY KEY,
  pipeline_key TEXT NOT NULL,
  indicator_series_id INTEGER NOT NULL,
  canonical_key TEXT NOT NULL,
  series_label TEXT NOT NULL,
  dataset_code TEXT NOT NULL CHECK (
    dataset_code = json_extract(dimensions_json, '$.dataset_code')
  ),
  country_code TEXT NOT NULL CHECK (country_code = 'ES'),
  geography_code TEXT NOT NULL CHECK (
    geography_code GLOB 'ES*'
    AND geography_code = json_extract(
      dimensions_json, '$.series_dimensions.geo'
    )
    AND country_code = substr(geography_code, 1, 2)
  ),
  frequency_code TEXT NOT NULL CHECK (frequency_code = 'A'),
  unit_code TEXT NOT NULL,
  dimensions_json TEXT NOT NULL CHECK (json_valid(dimensions_json)),
  source_id TEXT NOT NULL CHECK (source_id = 'eurostat_sdmx'),
  source_record_pk INTEGER NOT NULL,
  source_record_id TEXT NOT NULL,
  source_snapshot_date TEXT NOT NULL,
  official_source_url TEXT NOT NULL CHECK (
    official_source_url LIKE 'https://ec.europa.eu/eurostat/%'
  ),
  source_record_content_sha256 TEXT NOT NULL CHECK (
    length(source_record_content_sha256) = 64
    AND source_record_content_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  origin_capture_sha256 TEXT NOT NULL CHECK (
    length(origin_capture_sha256) = 64
    AND origin_capture_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  observation_count INTEGER NOT NULL CHECK (observation_count > 1),
  observation_years_json TEXT NOT NULL CHECK (json_valid(observation_years_json)),
  observation_projection_sha256 TEXT NOT NULL CHECK (
    length(observation_projection_sha256) = 64
    AND observation_projection_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  first_observation_date TEXT NOT NULL,
  last_observation_date TEXT NOT NULL,
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (pipeline_key, indicator_series_id),
  UNIQUE (pipeline_key, series_plan_pk),
  UNIQUE (pipeline_key, series_plan_pk, dataset_code)
);

CREATE TABLE IF NOT EXISTS outcome_pair_plan_pairs (
  pair_plan_id TEXT PRIMARY KEY,
  pipeline_key TEXT NOT NULL,
  base_partition_key TEXT NOT NULL,
  pair_bucket TEXT NOT NULL CHECK (
    length(pair_bucket) = 2
    AND pair_bucket NOT GLOB '*[^0-9a-f]*'
    AND pair_bucket = substr(pair_plan_id, 24, 2)
  ),
  partition_key TEXT NOT NULL CHECK (
    partition_key = base_partition_key || '/bucket=' || pair_bucket
  ),
  action_plan_pk INTEGER NOT NULL,
  series_plan_pk INTEGER NOT NULL,
  action_year INTEGER NOT NULL,
  dataset_code TEXT NOT NULL,
  strict_pre_latest_date TEXT NOT NULL,
  strict_post_earliest_date TEXT NOT NULL,
  evidence_level TEXT NOT NULL CHECK (evidence_level = 'L0'),
  link_state TEXT NOT NULL CHECK (link_state = 'internal_discovery_pair'),
  association_assessment TEXT NOT NULL CHECK (
    association_assessment = 'not_assessed'
  ),
  causal_assessment TEXT NOT NULL CHECK (causal_assessment = 'not_assessed'),
  effect_estimate_state TEXT NOT NULL CHECK (
    effect_estimate_state = 'not_computed'
  ),
  political_merit_or_blame TEXT NOT NULL CHECK (
    political_merit_or_blame = 'not_assessed'
  ),
  corruption_assessment TEXT NOT NULL CHECK (
    corruption_assessment = 'not_assessed'
  ),
  ranking_eligible INTEGER NOT NULL CHECK (ranking_eligible = 0),
  publication_eligible INTEGER NOT NULL CHECK (publication_eligible = 0),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (pipeline_key, action_plan_pk, series_plan_pk),
  FOREIGN KEY (pipeline_key, action_plan_pk)
    REFERENCES outcome_pair_plan_actions(pipeline_key, action_plan_pk)
    ON DELETE RESTRICT,
  FOREIGN KEY (pipeline_key, action_plan_pk, action_year)
    REFERENCES outcome_pair_plan_actions(
      pipeline_key, action_plan_pk, action_year
    ) ON DELETE RESTRICT,
  FOREIGN KEY (pipeline_key, series_plan_pk)
    REFERENCES outcome_pair_plan_series(pipeline_key, series_plan_pk)
    ON DELETE RESTRICT,
  FOREIGN KEY (pipeline_key, series_plan_pk, dataset_code)
    REFERENCES outcome_pair_plan_series(
      pipeline_key, series_plan_pk, dataset_code
    )
    ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_keyset_checkpoints_state
  ON pipeline_keyset_checkpoints(pipeline_key, completed, stage, partition_key);
CREATE INDEX IF NOT EXISTS idx_outcome_pair_plan_actions_keyset
  ON outcome_pair_plan_actions(pipeline_key, action_date, action_id, action_plan_pk);
CREATE INDEX IF NOT EXISTS idx_outcome_pair_plan_series_keyset
  ON outcome_pair_plan_series(
    pipeline_key, dataset_code, indicator_series_id, series_plan_pk
  );
CREATE INDEX IF NOT EXISTS idx_outcome_pair_plan_pairs_partition
  ON outcome_pair_plan_pairs(
    pipeline_key, base_partition_key, pair_bucket, action_plan_pk, series_plan_pk
  );
CREATE INDEX IF NOT EXISTS idx_outcome_pair_plan_pairs_action
  ON outcome_pair_plan_pairs(pipeline_key, action_plan_pk, series_plan_pk);
CREATE INDEX IF NOT EXISTS idx_outcome_pair_plan_pairs_series
  ON outcome_pair_plan_pairs(pipeline_key, series_plan_pk, action_plan_pk);

CREATE TRIGGER IF NOT EXISTS trg_pipeline_keyset_checkpoints_roots_immutable
BEFORE UPDATE ON pipeline_keyset_checkpoints
WHEN OLD.pipeline_key IS NOT NEW.pipeline_key
  OR OLD.stage IS NOT NEW.stage
  OR OLD.partition_key IS NOT NEW.partition_key
  OR OLD.checkpoint_contract_version IS NOT NEW.checkpoint_contract_version
  OR OLD.config_sha256 IS NOT NEW.config_sha256
  OR OLD.input_root_sha256 IS NOT NEW.input_root_sha256
  OR OLD.schema_root_sha256 IS NOT NEW.schema_root_sha256
BEGIN
  SELECT RAISE(ABORT, 'pipeline checkpoint identity roots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_pipeline_keyset_checkpoints_completed_immutable
BEFORE UPDATE ON pipeline_keyset_checkpoints
WHEN OLD.completed = 1
BEGIN
  SELECT RAISE(ABORT, 'completed pipeline checkpoint is immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_actions_no_update
BEFORE UPDATE ON outcome_pair_plan_actions BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_actions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_actions_no_delete
BEFORE DELETE ON outcome_pair_plan_actions BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_actions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_series_no_update
BEFORE UPDATE ON outcome_pair_plan_series BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_series is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_series_no_delete
BEFORE DELETE ON outcome_pair_plan_series BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_series is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_pairs_no_update
BEFORE UPDATE ON outcome_pair_plan_pairs BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_pairs is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_pair_plan_pairs_no_delete
BEFORE DELETE ON outcome_pair_plan_pairs BEGIN
  SELECT RAISE(ABORT, 'outcome_pair_plan_pairs is append-only');
END;
-- END OUTCOME PAIR PLANNER C2A SCHEMA

-- Real-human-review control plane for the C2C capacity slice. These tables
-- schedule review work only. They never turn an L0 discovery pair into an
-- association, causal, merit/blame, corruption, ranking, or publication claim.
-- BEGIN OUTCOME REVIEW CONTROL C2C SCHEMA
CREATE TABLE IF NOT EXISTS outcome_review_control_meta (
  pipeline_key TEXT NOT NULL PRIMARY KEY,
  contract_version TEXT NOT NULL CHECK (
    contract_version = 'outcome_review_control_c2c_v1'
  ),
  config_sha256 TEXT NOT NULL CHECK (
    length(config_sha256) = 64 AND config_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  source_root_sha256 TEXT NOT NULL CHECK (
    length(source_root_sha256) = 64
    AND source_root_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  schema_root_sha256 TEXT NOT NULL CHECK (
    length(schema_root_sha256) = 64
    AND schema_root_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  artifact_scope TEXT NOT NULL CHECK (
    artifact_scope IN ('capacity_only', 'operational_working')
  ),
  trust_root_contract_sha256 TEXT NOT NULL CHECK (
    length(trust_root_contract_sha256) = 64
    AND trust_root_contract_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  operational_state TEXT NOT NULL CHECK (
    operational_state IN ('not_materialized', 'working_unpublished')
  ),
  control_plane_capacity_status TEXT NOT NULL CHECK (
    control_plane_capacity_status IN ('BUILDING', 'PASS')
  ),
  human_review_status TEXT NOT NULL CHECK (human_review_status = 'OPEN'),
  semantic_promotion_status TEXT NOT NULL CHECK (
    semantic_promotion_status = 'OPEN'
  ),
  public_release_status TEXT NOT NULL CHECK (public_release_status = 'OPEN'),
  real_data_only INTEGER NOT NULL CHECK (real_data_only = 1),
  synthetic_or_mock_decisions INTEGER NOT NULL CHECK (
    synthetic_or_mock_decisions = 0
  ),
  capacity_snapshot_effective_at TEXT NOT NULL CHECK (
    length(capacity_snapshot_effective_at) = 20
    AND strftime(
      '%Y-%m-%dT%H:%M:%SZ', capacity_snapshot_effective_at
    ) = capacity_snapshot_effective_at
    AND unixepoch(capacity_snapshot_effective_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (pipeline_key, config_sha256, source_root_sha256, schema_root_sha256),
  CHECK (
    (artifact_scope = 'capacity_only' AND operational_state = 'not_materialized')
    OR (artifact_scope = 'operational_working'
      AND operational_state = 'working_unpublished')
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_control_checkpoints (
  pipeline_key TEXT NOT NULL REFERENCES outcome_review_control_meta(pipeline_key),
  stage TEXT NOT NULL CHECK (stage = 'discovery_tasks'),
  checkpoint_contract_version TEXT NOT NULL CHECK (
    checkpoint_contract_version = 'outcome_review_control_checkpoint_c2c_v1'
  ),
  config_sha256 TEXT NOT NULL,
  source_root_sha256 TEXT NOT NULL,
  schema_root_sha256 TEXT NOT NULL,
  last_action_plan_pk INTEGER NOT NULL DEFAULT 0 CHECK (last_action_plan_pk >= 0),
  last_series_plan_pk INTEGER NOT NULL DEFAULT 0 CHECK (last_series_plan_pk >= 0),
  tasks_written INTEGER NOT NULL DEFAULT 0 CHECK (tasks_written >= 0),
  slots_written INTEGER NOT NULL DEFAULT 0 CHECK (slots_written >= 0),
  batches_committed INTEGER NOT NULL DEFAULT 0 CHECK (batches_committed >= 0),
  task_chain_sha256 TEXT NOT NULL CHECK (
    length(task_chain_sha256) = 64
    AND task_chain_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  slot_chain_sha256 TEXT NOT NULL CHECK (
    length(slot_chain_sha256) = 64
    AND slot_chain_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  audit_chain_sha256 TEXT NOT NULL CHECK (
    length(audit_chain_sha256) = 64
    AND audit_chain_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
  checkpoint_snapshot_effective_at TEXT NOT NULL CHECK (
    length(checkpoint_snapshot_effective_at) = 20
    AND strftime(
      '%Y-%m-%dT%H:%M:%SZ', checkpoint_snapshot_effective_at
    ) = checkpoint_snapshot_effective_at
    AND unixepoch(checkpoint_snapshot_effective_at) IS NOT NULL
  ),
  PRIMARY KEY (pipeline_key, stage),
  FOREIGN KEY (pipeline_key, config_sha256, source_root_sha256, schema_root_sha256)
    REFERENCES outcome_review_control_meta(
      pipeline_key, config_sha256, source_root_sha256, schema_root_sha256
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_review_control_meta_roots
  ON outcome_review_control_meta(
    pipeline_key, config_sha256, source_root_sha256, schema_root_sha256
  );

CREATE TABLE IF NOT EXISTS outcome_review_cohorts (
  cohort_id TEXT NOT NULL PRIMARY KEY,
  pipeline_key TEXT NOT NULL REFERENCES outcome_review_control_meta(pipeline_key),
  cohort_kind TEXT NOT NULL CHECK (
    cohort_kind IN ('c2b_l0_discovery', 'c1_l1_semantic_canary')
  ),
  source_artifact_path TEXT NOT NULL CHECK (
    source_artifact_path NOT LIKE '/Users/%'
    AND source_artifact_path NOT LIKE '/home/%'
    AND source_artifact_path NOT LIKE 'file://%'
  ),
  source_artifact_sha256 TEXT NOT NULL CHECK (
    length(source_artifact_sha256) = 64
    AND source_artifact_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  source_manifest_sha256 TEXT NOT NULL CHECK (
    length(source_manifest_sha256) = 64
    AND source_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  source_semantic_root_sha256 TEXT NOT NULL CHECK (
    length(source_semantic_root_sha256) = 64
    AND source_semantic_root_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  evidence_level TEXT NOT NULL CHECK (evidence_level IN ('L0', 'L1')),
  expected_task_count INTEGER NOT NULL CHECK (expected_task_count > 0),
  required_slots_per_task INTEGER NOT NULL CHECK (required_slots_per_task IN (1, 2)),
  assignment_eligible INTEGER NOT NULL CHECK (assignment_eligible = 1),
  requires_dual_review INTEGER NOT NULL CHECK (requires_dual_review IN (0, 1)),
  adjudication_on_disagreement INTEGER NOT NULL CHECK (
    adjudication_on_disagreement IN (0, 1)
  ),
  semantic_promotion_requires_review INTEGER NOT NULL CHECK (
    semantic_promotion_requires_review = 1
  ),
  public_release_requires_promotion INTEGER NOT NULL CHECK (
    public_release_requires_promotion = 1
  ),
  eligibility_policy_json TEXT NOT NULL CHECK (json_valid(eligibility_policy_json)),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (cohort_kind = 'c2b_l0_discovery' AND evidence_level = 'L0'
      AND required_slots_per_task = 1 AND requires_dual_review = 0
      AND adjudication_on_disagreement = 0)
    OR
    (cohort_kind = 'c1_l1_semantic_canary' AND evidence_level = 'L1'
      AND expected_task_count = 1 AND required_slots_per_task = 2
      AND requires_dual_review = 1 AND adjudication_on_disagreement = 1)
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_tasks (
  task_pk INTEGER PRIMARY KEY,
  task_id TEXT NOT NULL UNIQUE,
  cohort_id TEXT NOT NULL REFERENCES outcome_review_cohorts(cohort_id),
  task_kind TEXT NOT NULL CHECK (
    task_kind IN ('discovery_triage', 'semantic_canary')
  ),
  source_row_id TEXT NOT NULL,
  source_row_semantic_sha256 TEXT NOT NULL CHECK (
    length(source_row_semantic_sha256) = 64
    AND source_row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  source_action_plan_pk INTEGER,
  source_series_plan_pk INTEGER,
  evidence_level TEXT NOT NULL CHECK (evidence_level IN ('L0', 'L1')),
  task_state TEXT NOT NULL CHECK (task_state = 'pending_human_review'),
  assignment_eligible INTEGER NOT NULL CHECK (assignment_eligible = 1),
  initial_semantic_promotion_eligible INTEGER NOT NULL CHECK (
    initial_semantic_promotion_eligible = 0
  ),
  initial_publication_eligible INTEGER NOT NULL CHECK (
    initial_publication_eligible = 0
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (cohort_id, source_row_id),
  CHECK (
    (task_kind = 'discovery_triage' AND evidence_level = 'L0'
      AND source_action_plan_pk IS NOT NULL AND source_series_plan_pk IS NOT NULL)
    OR
    (task_kind = 'semantic_canary' AND evidence_level = 'L1'
      AND source_action_plan_pk IS NULL AND source_series_plan_pk IS NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_tasks_cohort_keyset
  ON outcome_review_tasks(
    cohort_id, source_action_plan_pk, source_series_plan_pk, task_pk
  );

CREATE TABLE IF NOT EXISTS outcome_review_slots (
  slot_pk INTEGER PRIMARY KEY,
  slot_id TEXT NOT NULL UNIQUE,
  task_pk INTEGER NOT NULL REFERENCES outcome_review_tasks(task_pk) ON DELETE RESTRICT,
  slot_kind TEXT NOT NULL CHECK (
    slot_kind IN ('discovery_primary', 'semantic_primary', 'semantic_secondary')
  ),
  slot_ordinal INTEGER NOT NULL CHECK (slot_ordinal IN (1, 2)),
  review_dimension TEXT NOT NULL CHECK (
    review_dimension IN ('discovery_triage', 'semantic')
  ),
  required_reviewer_role TEXT NOT NULL CHECK (
    required_reviewer_role IN ('discovery_reviewer', 'semantic_reviewer')
  ),
  independent_reviewer_required INTEGER NOT NULL CHECK (
    independent_reviewer_required IN (0, 1)
  ),
  adjudication_rule TEXT NOT NULL CHECK (
    adjudication_rule IN ('not_applicable', 'on_disagreement_after_dual_review')
  ),
  slot_state TEXT NOT NULL CHECK (slot_state = 'pending_unassigned'),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (task_pk, slot_kind),
  UNIQUE (task_pk, slot_ordinal),
  CHECK (
    (slot_kind = 'discovery_primary' AND slot_ordinal = 1
      AND review_dimension = 'discovery_triage'
      AND required_reviewer_role = 'discovery_reviewer'
      AND independent_reviewer_required = 0
      AND adjudication_rule = 'not_applicable')
    OR
    (slot_kind = 'semantic_primary' AND slot_ordinal = 1
      AND review_dimension = 'semantic'
      AND required_reviewer_role = 'semantic_reviewer'
      AND independent_reviewer_required = 1
      AND adjudication_rule = 'on_disagreement_after_dual_review')
    OR
    (slot_kind = 'semantic_secondary' AND slot_ordinal = 2
      AND review_dimension = 'semantic'
      AND required_reviewer_role = 'semantic_reviewer'
      AND independent_reviewer_required = 1
      AND adjudication_rule = 'on_disagreement_after_dual_review')
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_slots_task
  ON outcome_review_slots(task_pk, slot_ordinal, slot_pk);

-- A capacity artifact pins the empty trust-root set. Real trust roots may be
-- introduced only in a separate unpublished operational working database.
-- Its eventual immutable export must bind the exact public authority evidence.
CREATE TABLE IF NOT EXISTS outcome_review_trust_roots (
  trust_root_id TEXT NOT NULL PRIMARY KEY,
  authority_public_id TEXT NOT NULL,
  identity_provider TEXT NOT NULL CHECK (
    length(identity_provider) BETWEEN 1 AND 128
  ),
  provider_subject_sha256 TEXT NOT NULL CHECK (
    length(provider_subject_sha256) = 64
    AND provider_subject_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  evidence_sha256 TEXT NOT NULL CHECK (
    length(evidence_sha256) = 64 AND evidence_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  effective_at TEXT NOT NULL CHECK (
    length(effective_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', effective_at) = effective_at
    AND unixepoch(effective_at) IS NOT NULL
  ),
  expires_at TEXT CHECK (
    expires_at IS NULL OR (
      length(expires_at) = 20
      AND strftime('%Y-%m-%dT%H:%M:%SZ', expires_at) = expires_at
      AND unixepoch(expires_at) IS NOT NULL
      AND expires_at > effective_at
    )
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (identity_provider, provider_subject_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_review_reviewer_identities (
  reviewer_public_id TEXT NOT NULL PRIMARY KEY,
  identity_provider TEXT NOT NULL CHECK (
    length(identity_provider) BETWEEN 1 AND 128
  ),
  provider_subject_sha256 TEXT NOT NULL CHECK (
    length(provider_subject_sha256) = 64
    AND provider_subject_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  human_identity_sha256 TEXT NOT NULL CHECK (
    length(human_identity_sha256) = 64
    AND human_identity_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  verified_by_trust_root_id TEXT NOT NULL REFERENCES outcome_review_trust_roots(
    trust_root_id
  ),
  registered_at TEXT NOT NULL CHECK (
    length(registered_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', registered_at) = registered_at
    AND unixepoch(registered_at) IS NOT NULL
  ),
  identity_state TEXT NOT NULL CHECK (identity_state = 'verified'),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (identity_provider, provider_subject_sha256),
  UNIQUE (human_identity_sha256)
);

CREATE TABLE IF NOT EXISTS outcome_review_auth_events (
  auth_event_pk INTEGER PRIMARY KEY,
  auth_event_id TEXT NOT NULL UNIQUE,
  reviewer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  cohort_id TEXT REFERENCES outcome_review_cohorts(cohort_id),
  reviewer_role TEXT NOT NULL CHECK (
    reviewer_role IN (
      'discovery_reviewer', 'semantic_reviewer', 'adjudicator',
      'claim_coordinator', 'promotion_authority', 'publisher'
    )
  ),
  auth_state TEXT NOT NULL CHECK (auth_state IN ('granted', 'revoked')),
  supersedes_auth_event_id TEXT REFERENCES outcome_review_auth_events(auth_event_id),
  effective_at TEXT NOT NULL CHECK (
    length(effective_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', effective_at) = effective_at
    AND unixepoch(effective_at) IS NOT NULL
  ),
  expires_at TEXT CHECK (
    expires_at IS NULL OR (
      length(expires_at) = 20
      AND strftime('%Y-%m-%dT%H:%M:%SZ', expires_at) = expires_at
      AND unixepoch(expires_at) IS NOT NULL
      AND expires_at > effective_at
    )
  ),
  issuer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  issuer_trust_root_id TEXT NOT NULL REFERENCES outcome_review_trust_roots(
    trust_root_id
  ),
  evidence_sha256 TEXT NOT NULL CHECK (
    length(evidence_sha256) = 64 AND evidence_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (auth_state = 'granted' AND supersedes_auth_event_id IS NULL)
    OR (auth_state = 'revoked' AND supersedes_auth_event_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_auth_current
  ON outcome_review_auth_events(
    reviewer_public_id, cohort_id, reviewer_role, auth_event_pk
  );

CREATE TABLE IF NOT EXISTS outcome_review_conflict_events (
  conflict_event_pk INTEGER PRIMARY KEY,
  conflict_event_id TEXT NOT NULL UNIQUE,
  reviewer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  cohort_id TEXT NOT NULL REFERENCES outcome_review_cohorts(cohort_id),
  task_pk INTEGER REFERENCES outcome_review_tasks(task_pk),
  conflict_kind TEXT NOT NULL CHECK (length(trim(conflict_kind)) BETWEEN 1 AND 128),
  conflict_state TEXT NOT NULL CHECK (conflict_state IN ('declared', 'cleared')),
  supersedes_conflict_event_id TEXT REFERENCES outcome_review_conflict_events(
    conflict_event_id
  ),
  recorded_at TEXT NOT NULL CHECK (
    length(recorded_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', recorded_at) = recorded_at
    AND unixepoch(recorded_at) IS NOT NULL
  ),
  evidence_json TEXT NOT NULL CHECK (
    json_valid(evidence_json)
    AND json_type(evidence_json) = 'object'
    AND json(evidence_json) <> '{}'
    AND length(evidence_json) BETWEEN 2 AND 8192
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (conflict_state = 'declared' AND supersedes_conflict_event_id IS NULL)
    OR (conflict_state = 'cleared' AND supersedes_conflict_event_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_conflict_current
  ON outcome_review_conflict_events(
    reviewer_public_id, cohort_id, task_pk, conflict_event_pk
  );

CREATE TABLE IF NOT EXISTS outcome_review_assignment_events (
  assignment_event_pk INTEGER PRIMARY KEY,
  assignment_event_id TEXT NOT NULL UNIQUE,
  slot_pk INTEGER NOT NULL REFERENCES outcome_review_slots(slot_pk),
  reviewer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  auth_event_id TEXT NOT NULL REFERENCES outcome_review_auth_events(auth_event_id),
  assignment_state TEXT NOT NULL CHECK (assignment_state IN ('assigned', 'released')),
  supersedes_assignment_event_id TEXT REFERENCES outcome_review_assignment_events(
    assignment_event_id
  ),
  recorded_at TEXT NOT NULL CHECK (
    length(recorded_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', recorded_at) = recorded_at
    AND unixepoch(recorded_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (assignment_state = 'assigned' AND supersedes_assignment_event_id IS NULL)
    OR (assignment_state = 'released' AND supersedes_assignment_event_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_assignment_current
  ON outcome_review_assignment_events(slot_pk, assignment_event_pk);

CREATE INDEX IF NOT EXISTS idx_outcome_review_auth_supersedes
  ON outcome_review_auth_events(
    supersedes_auth_event_id, auth_state, effective_at, auth_event_pk
  );
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_review_auth_one_supersession
  ON outcome_review_auth_events(supersedes_auth_event_id)
  WHERE supersedes_auth_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outcome_review_conflict_supersedes
  ON outcome_review_conflict_events(
    supersedes_conflict_event_id, conflict_state, recorded_at, conflict_event_pk
  );
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_review_conflict_one_supersession
  ON outcome_review_conflict_events(supersedes_conflict_event_id)
  WHERE supersedes_conflict_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outcome_review_assignment_supersedes
  ON outcome_review_assignment_events(
    supersedes_assignment_event_id, assignment_state, recorded_at,
    assignment_event_pk
  );
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_review_assignment_one_supersession
  ON outcome_review_assignment_events(supersedes_assignment_event_id)
  WHERE supersedes_assignment_event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS outcome_review_claim_events (
  claim_event_pk INTEGER PRIMARY KEY,
  claim_event_id TEXT NOT NULL UNIQUE,
  assignment_event_id TEXT NOT NULL REFERENCES outcome_review_assignment_events(
    assignment_event_id
  ),
  slot_pk INTEGER NOT NULL REFERENCES outcome_review_slots(slot_pk),
  reviewer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  actor_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  actor_auth_event_id TEXT REFERENCES outcome_review_auth_events(auth_event_id),
  claim_state TEXT NOT NULL CHECK (
    claim_state IN ('claimed', 'heartbeat', 'released', 'completed', 'reclaimed')
  ),
  supersedes_claim_event_id TEXT REFERENCES outcome_review_claim_events(
    claim_event_id
  ),
  lease_token_sha256 TEXT NOT NULL CHECK (
    length(lease_token_sha256) = 64
    AND lease_token_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  attempt_ordinal INTEGER NOT NULL CHECK (attempt_ordinal BETWEEN 1 AND 100),
  lease_expires_at TEXT NOT NULL CHECK (
    length(lease_expires_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', lease_expires_at) = lease_expires_at
    AND unixepoch(lease_expires_at) IS NOT NULL
  ),
  recorded_at TEXT NOT NULL CHECK (
    length(recorded_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', recorded_at) = recorded_at
    AND unixepoch(recorded_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (claim_state = 'claimed'
      AND ((supersedes_claim_event_id IS NULL AND attempt_ordinal = 1)
        OR supersedes_claim_event_id IS NOT NULL)
      AND actor_public_id = reviewer_public_id
      AND actor_auth_event_id IS NULL)
    OR (claim_state IN ('heartbeat', 'released', 'completed')
      AND supersedes_claim_event_id IS NOT NULL
      AND actor_public_id = reviewer_public_id
      AND actor_auth_event_id IS NULL)
    OR (claim_state = 'reclaimed'
      AND supersedes_claim_event_id IS NOT NULL
      AND actor_auth_event_id IS NOT NULL)
  ),
  CHECK (
    (claim_state <> 'reclaimed' AND lease_expires_at > recorded_at)
    OR (claim_state = 'reclaimed' AND lease_expires_at <= recorded_at)
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_claim_current
  ON outcome_review_claim_events(slot_pk, claim_event_pk);
CREATE INDEX IF NOT EXISTS idx_outcome_review_claim_supersedes
  ON outcome_review_claim_events(
    supersedes_claim_event_id, claim_state, recorded_at, claim_event_pk
  );
CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_review_claim_one_supersession
  ON outcome_review_claim_events(supersedes_claim_event_id)
  WHERE supersedes_claim_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outcome_review_claim_expiry
  ON outcome_review_claim_events(claim_state, lease_expires_at, claim_event_pk);

CREATE TABLE IF NOT EXISTS outcome_review_decisions (
  decision_pk INTEGER PRIMARY KEY,
  decision_id TEXT NOT NULL UNIQUE,
  task_pk INTEGER NOT NULL REFERENCES outcome_review_tasks(task_pk),
  slot_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_slots(slot_pk),
  assignment_event_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_assignment_events(
    assignment_event_id
  ),
  claim_event_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_claim_events(
    claim_event_id
  ),
  reviewer_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  decision_value TEXT NOT NULL CHECK (
    decision_value IN (
      'advance_to_semantic_review', 'exclude_from_semantic_review',
      'insufficient_evidence', 'support', 'reject', 'needs_more_evidence'
    )
  ),
  evidence_examined_json TEXT NOT NULL CHECK (
    json_valid(evidence_examined_json)
    AND json_type(evidence_examined_json) = 'array'
    AND json_array_length(evidence_examined_json) BETWEEN 1 AND 128
    AND length(evidence_examined_json) BETWEEN 2 AND 8192
  ),
  rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
  decided_at TEXT NOT NULL CHECK (
    length(decided_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', decided_at) = decided_at
    AND unixepoch(decided_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_decisions_task_reviewer
  ON outcome_review_decisions(
    task_pk, reviewer_public_id, slot_pk, decision_value, decision_pk
  );

CREATE TABLE IF NOT EXISTS outcome_review_adjudications (
  adjudication_pk INTEGER PRIMARY KEY,
  adjudication_id TEXT NOT NULL UNIQUE,
  task_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_tasks(task_pk),
  primary_decision_id TEXT NOT NULL REFERENCES outcome_review_decisions(decision_id),
  secondary_decision_id TEXT NOT NULL REFERENCES outcome_review_decisions(decision_id),
  adjudicator_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  auth_event_id TEXT NOT NULL REFERENCES outcome_review_auth_events(auth_event_id),
  adjudicated_value TEXT NOT NULL CHECK (
    adjudicated_value IN ('support', 'reject', 'needs_more_evidence')
  ),
  evidence_examined_json TEXT NOT NULL CHECK (
    json_valid(evidence_examined_json)
    AND json_type(evidence_examined_json) = 'array'
    AND json_array_length(evidence_examined_json) BETWEEN 1 AND 128
    AND length(evidence_examined_json) BETWEEN 2 AND 8192
  ),
  rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
  adjudicated_at TEXT NOT NULL CHECK (
    length(adjudicated_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', adjudicated_at) = adjudicated_at
    AND unixepoch(adjudicated_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (primary_decision_id <> secondary_decision_id)
);

CREATE TABLE IF NOT EXISTS outcome_review_semantic_eligibility_events (
  eligibility_event_id TEXT NOT NULL PRIMARY KEY,
  task_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_tasks(task_pk),
  eligibility_state TEXT NOT NULL CHECK (eligibility_state = 'eligible'),
  primary_decision_id TEXT REFERENCES outcome_review_decisions(decision_id),
  secondary_decision_id TEXT REFERENCES outcome_review_decisions(decision_id),
  adjudication_id TEXT REFERENCES outcome_review_adjudications(adjudication_id),
  computed_at TEXT NOT NULL CHECK (
    length(computed_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', computed_at) = computed_at
    AND unixepoch(computed_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (primary_decision_id IS NOT NULL AND secondary_decision_id IS NOT NULL
      AND adjudication_id IS NULL AND primary_decision_id <> secondary_decision_id)
    OR
    (primary_decision_id IS NULL AND secondary_decision_id IS NULL
      AND adjudication_id IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_semantic_promotions (
  promotion_id TEXT NOT NULL PRIMARY KEY,
  task_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_tasks(task_pk),
  promotion_authority_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  auth_event_id TEXT NOT NULL REFERENCES outcome_review_auth_events(auth_event_id),
  eligibility_event_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_semantic_eligibility_events(
    eligibility_event_id
  ),
  selected_value TEXT NOT NULL CHECK (selected_value = 'support'),
  selected_evidence_level TEXT NOT NULL CHECK (selected_evidence_level = 'L1'),
  promoted_at TEXT NOT NULL CHECK (
    length(promoted_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', promoted_at) = promoted_at
    AND unixepoch(promoted_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  )
);

-- Cross-artifact binding to a real outcome_link_releases row and one real
-- outcome_link_release_memberships row. A future operational validator must
-- resolve these identifiers against the pinned source database before it can
-- root the operational snapshot.
CREATE TABLE IF NOT EXISTS outcome_review_release_bindings (
  release_binding_id TEXT NOT NULL PRIMARY KEY,
  task_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_tasks(task_pk),
  source_database_sha256 TEXT NOT NULL CHECK (
    length(source_database_sha256) = 64
    AND source_database_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  outcome_link_release_id TEXT NOT NULL,
  outcome_link_release_membership_id TEXT NOT NULL,
  outcome_link_version_id TEXT NOT NULL,
  release_descriptor_sha256 TEXT NOT NULL CHECK (
    length(release_descriptor_sha256) = 64
    AND release_descriptor_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  membership_row_sha256 TEXT NOT NULL CHECK (
    length(membership_row_sha256) = 64
    AND membership_row_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  verified_at TEXT NOT NULL CHECK (
    length(verified_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', verified_at) = verified_at
    AND unixepoch(verified_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (
    source_database_sha256, outcome_link_release_id,
    outcome_link_release_membership_id
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_publication_eligibility_events (
  publication_eligibility_event_id TEXT NOT NULL PRIMARY KEY,
  task_pk INTEGER NOT NULL UNIQUE REFERENCES outcome_review_tasks(task_pk),
  promotion_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_semantic_promotions(
    promotion_id
  ),
  release_binding_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_release_bindings(
    release_binding_id
  ),
  eligibility_state TEXT NOT NULL CHECK (eligibility_state = 'eligible'),
  computed_at TEXT NOT NULL CHECK (
    length(computed_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', computed_at) = computed_at
    AND unixepoch(computed_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_publication_events (
  publication_event_id TEXT NOT NULL PRIMARY KEY,
  task_pk INTEGER NOT NULL REFERENCES outcome_review_tasks(task_pk),
  promotion_id TEXT NOT NULL REFERENCES outcome_review_semantic_promotions(promotion_id),
  publication_eligibility_event_id TEXT NOT NULL UNIQUE
    REFERENCES outcome_review_publication_eligibility_events(
      publication_eligibility_event_id
    ),
  release_binding_id TEXT NOT NULL UNIQUE REFERENCES outcome_review_release_bindings(
    release_binding_id
  ),
  publisher_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  auth_event_id TEXT NOT NULL REFERENCES outcome_review_auth_events(auth_event_id),
  outcome_link_release_id TEXT NOT NULL,
  outcome_link_release_membership_id TEXT NOT NULL,
  published_at TEXT NOT NULL CHECK (
    length(published_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', published_at) = published_at
    AND unixepoch(published_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_operation_requests (
  idempotency_key TEXT NOT NULL PRIMARY KEY CHECK (
    length(idempotency_key) BETWEEN 16 AND 200
  ),
  operation_kind TEXT NOT NULL CHECK (
    operation_kind IN (
      'trust_root', 'reviewer_identity', 'authorization', 'conflict',
      'assignment', 'claim', 'decision', 'adjudication'
    )
  ),
  payload_sha256 TEXT NOT NULL CHECK (
    length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  target_table TEXT NOT NULL CHECK (
    target_table IN (
      'outcome_review_trust_roots', 'outcome_review_reviewer_identities',
      'outcome_review_auth_events', 'outcome_review_conflict_events',
      'outcome_review_assignment_events', 'outcome_review_claim_events',
      'outcome_review_decisions', 'outcome_review_adjudications'
    )
  ),
  target_row_id TEXT NOT NULL CHECK (length(target_row_id) BETWEEN 1 AND 256),
  applied_at TEXT NOT NULL CHECK (
    length(applied_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', applied_at) = applied_at
    AND unixepoch(applied_at) IS NOT NULL
  ),
  row_semantic_sha256 TEXT NOT NULL CHECK (
    length(row_semantic_sha256) = 64
    AND row_semantic_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  CHECK (
    (operation_kind = 'trust_root'
      AND target_table = 'outcome_review_trust_roots')
    OR (operation_kind = 'reviewer_identity'
      AND target_table = 'outcome_review_reviewer_identities')
    OR (operation_kind = 'authorization'
      AND target_table = 'outcome_review_auth_events')
    OR (operation_kind = 'conflict'
      AND target_table = 'outcome_review_conflict_events')
    OR (operation_kind = 'assignment'
      AND target_table = 'outcome_review_assignment_events')
    OR (operation_kind = 'claim'
      AND target_table = 'outcome_review_claim_events')
    OR (operation_kind = 'decision'
      AND target_table = 'outcome_review_decisions')
    OR (operation_kind = 'adjudication'
      AND target_table = 'outcome_review_adjudications')
  )
);

CREATE TABLE IF NOT EXISTS outcome_review_operational_audit_events (
  operational_audit_pk INTEGER PRIMARY KEY,
  operational_audit_id TEXT NOT NULL UNIQUE,
  idempotency_key TEXT NOT NULL UNIQUE REFERENCES outcome_review_operation_requests(
    idempotency_key
  ),
  operation_kind TEXT NOT NULL,
  target_table TEXT NOT NULL,
  target_row_id TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL CHECK (
    length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  previous_event_sha256 TEXT NOT NULL CHECK (
    length(previous_event_sha256) = 64
    AND previous_event_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  actor_public_id TEXT NOT NULL REFERENCES outcome_review_reviewer_identities(
    reviewer_public_id
  ),
  occurred_at TEXT NOT NULL CHECK (
    length(occurred_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', occurred_at) = occurred_at
    AND unixepoch(occurred_at) IS NOT NULL
  ),
  event_sha256 TEXT NOT NULL UNIQUE CHECK (
    length(event_sha256) = 64 AND event_sha256 NOT GLOB '*[^0-9a-f]*'
  )
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_operational_audit_chain
  ON outcome_review_operational_audit_events(
    operational_audit_pk, previous_event_sha256, event_sha256
  );

CREATE TABLE IF NOT EXISTS outcome_review_audit_events (
  audit_event_pk INTEGER PRIMARY KEY,
  audit_event_id TEXT NOT NULL UNIQUE,
  pipeline_key TEXT NOT NULL REFERENCES outcome_review_control_meta(pipeline_key),
  event_kind TEXT NOT NULL CHECK (
    event_kind IN ('control_initialized', 'discovery_batch_committed')
  ),
  batch_ordinal INTEGER NOT NULL CHECK (batch_ordinal >= 0),
  source_rows_committed INTEGER NOT NULL CHECK (source_rows_committed >= 0),
  slots_committed INTEGER NOT NULL CHECK (slots_committed >= 0),
  previous_event_sha256 TEXT NOT NULL CHECK (
    length(previous_event_sha256) = 64
    AND previous_event_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  event_payload_json TEXT NOT NULL CHECK (
    json_valid(event_payload_json)
    AND json_type(event_payload_json) = 'object'
    AND length(event_payload_json) BETWEEN 2 AND 16384
  ),
  actor_kind TEXT NOT NULL CHECK (actor_kind = 'system_materializer'),
  actor_id TEXT NOT NULL CHECK (
    actor_id = 'vclc:outcome-review-control-materializer-c2c-v1'
  ),
  snapshot_effective_at TEXT NOT NULL CHECK (
    length(snapshot_effective_at) = 20
    AND strftime('%Y-%m-%dT%H:%M:%SZ', snapshot_effective_at)
      = snapshot_effective_at
    AND unixepoch(snapshot_effective_at) IS NOT NULL
  ),
  event_sha256 TEXT NOT NULL CHECK (
    length(event_sha256) = 64 AND event_sha256 NOT GLOB '*[^0-9a-f]*'
  ),
  UNIQUE (pipeline_key, batch_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_outcome_review_audit_chain
  ON outcome_review_audit_events(pipeline_key, audit_event_pk);

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_control_checkpoint_roots_immutable
BEFORE UPDATE ON outcome_review_control_checkpoints
WHEN OLD.pipeline_key IS NOT NEW.pipeline_key
  OR OLD.stage IS NOT NEW.stage
  OR OLD.checkpoint_contract_version IS NOT NEW.checkpoint_contract_version
  OR OLD.config_sha256 IS NOT NEW.config_sha256
  OR OLD.source_root_sha256 IS NOT NEW.source_root_sha256
  OR OLD.schema_root_sha256 IS NOT NEW.schema_root_sha256
BEGIN
  SELECT RAISE(ABORT, 'review control checkpoint identity roots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_control_checkpoint_completed_immutable
BEFORE UPDATE ON outcome_review_control_checkpoints
WHEN OLD.completed = 1
BEGIN
  SELECT RAISE(ABORT, 'completed review control checkpoint is immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_control_checkpoint_no_delete
BEFORE DELETE ON outcome_review_control_checkpoints BEGIN
  SELECT RAISE(ABORT, 'review control checkpoints cannot be deleted');
END;

-- The canonical C2C database is a capacity root, not a mutable operational
-- database. Every human or release event therefore requires a separate
-- unpublished operational working database from its first insert.
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_trust_roots_snapshot_guard
BEFORE INSERT ON outcome_review_trust_roots
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'trust roots require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_reviewer_identities_snapshot_guard
BEFORE INSERT ON outcome_review_reviewer_identities
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'reviewer identities require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_auth_events_snapshot_guard
BEFORE INSERT ON outcome_review_auth_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'authorization events require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_conflict_events_snapshot_guard
BEFORE INSERT ON outcome_review_conflict_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'conflict events require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_assignment_events_snapshot_guard
BEFORE INSERT ON outcome_review_assignment_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'assignment events require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_claim_events_snapshot_guard
BEFORE INSERT ON outcome_review_claim_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'claim events require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_decisions_snapshot_guard
BEFORE INSERT ON outcome_review_decisions
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'review decisions require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_adjudications_snapshot_guard
BEFORE INSERT ON outcome_review_adjudications
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'adjudications require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_eligibility_snapshot_guard
BEFORE INSERT ON outcome_review_semantic_eligibility_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'semantic eligibility requires an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_promotions_snapshot_guard
BEFORE INSERT ON outcome_review_semantic_promotions
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'semantic promotion requires an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_release_bindings_snapshot_guard
BEFORE INSERT ON outcome_review_release_bindings
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'release bindings require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_eligibility_snapshot_guard
BEFORE INSERT ON outcome_review_publication_eligibility_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'publication eligibility requires an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_events_snapshot_guard
BEFORE INSERT ON outcome_review_publication_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'publication events require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operation_requests_snapshot_guard
BEFORE INSERT ON outcome_review_operation_requests
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'operation requests require an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operation_request_target_guard
BEFORE INSERT ON outcome_review_operation_requests
BEGIN
  SELECT CASE WHEN NOT (
    (NEW.target_table = 'outcome_review_trust_roots' AND EXISTS (
      SELECT 1 FROM outcome_review_trust_roots target
      WHERE target.trust_root_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_reviewer_identities' AND EXISTS (
      SELECT 1 FROM outcome_review_reviewer_identities target
      WHERE target.reviewer_public_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_auth_events' AND EXISTS (
      SELECT 1 FROM outcome_review_auth_events target
      WHERE target.auth_event_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_conflict_events' AND EXISTS (
      SELECT 1 FROM outcome_review_conflict_events target
      WHERE target.conflict_event_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_assignment_events' AND EXISTS (
      SELECT 1 FROM outcome_review_assignment_events target
      WHERE target.assignment_event_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_claim_events' AND EXISTS (
      SELECT 1 FROM outcome_review_claim_events target
      WHERE target.claim_event_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_decisions' AND EXISTS (
      SELECT 1 FROM outcome_review_decisions target
      WHERE target.decision_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
    OR (NEW.target_table = 'outcome_review_adjudications' AND EXISTS (
      SELECT 1 FROM outcome_review_adjudications target
      WHERE target.adjudication_id = NEW.target_row_id
        AND target.row_semantic_sha256 = NEW.row_semantic_sha256
    ))
  ) THEN RAISE(ABORT, 'operation request does not bind its exact target row') END;
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operational_audit_snapshot_guard
BEFORE INSERT ON outcome_review_operational_audit_events
WHEN NOT EXISTS (
  SELECT 1 FROM outcome_review_control_meta
  WHERE artifact_scope = 'operational_working'
    AND operational_state = 'working_unpublished'
)
BEGIN
  SELECT RAISE(ABORT, 'operational audit requires an unpublished operational working database');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operational_audit_chain_guard
BEFORE INSERT ON outcome_review_operational_audit_events
BEGIN
  SELECT CASE WHEN NEW.operational_audit_pk <> (
    SELECT COALESCE(MAX(operational_audit_pk), 0) + 1
    FROM outcome_review_operational_audit_events
  ) THEN RAISE(ABORT, 'operational audit ordinal is not contiguous') END;
  SELECT CASE WHEN NEW.previous_event_sha256 <> COALESCE(
    (
      SELECT event_sha256 FROM outcome_review_operational_audit_events
      ORDER BY operational_audit_pk DESC LIMIT 1
    ),
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  ) THEN RAISE(ABORT, 'operational audit chain is discontinuous') END;
  SELECT CASE WHEN NEW.occurred_at < COALESCE(
    (
      SELECT occurred_at FROM outcome_review_operational_audit_events
      ORDER BY operational_audit_pk DESC LIMIT 1
    ),
    '0000-01-01T00:00:00Z'
  ) THEN RAISE(ABORT, 'operational audit chronology moved backwards') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_operation_requests request
    WHERE request.idempotency_key = NEW.idempotency_key
      AND request.operation_kind = NEW.operation_kind
      AND request.target_table = NEW.target_table
      AND request.target_row_id = NEW.target_row_id
      AND request.payload_sha256 = NEW.payload_sha256
      AND request.applied_at = NEW.occurred_at
  ) THEN RAISE(ABORT, 'operational audit does not bind its idempotent request') END;
  SELECT CASE WHEN NOT (
    (NEW.target_table = 'outcome_review_claim_events' AND EXISTS (
      SELECT 1 FROM outcome_review_claim_events target
      WHERE target.claim_event_id = NEW.target_row_id
        AND target.actor_public_id = NEW.actor_public_id
    ))
    OR (NEW.target_table = 'outcome_review_decisions' AND EXISTS (
      SELECT 1 FROM outcome_review_decisions target
      WHERE target.decision_id = NEW.target_row_id
        AND target.reviewer_public_id = NEW.actor_public_id
    ))
    OR NEW.target_table NOT IN (
      'outcome_review_claim_events', 'outcome_review_decisions'
    )
  ) THEN RAISE(ABORT, 'operational audit actor does not match the target event') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_reviewer_identity_trust_guard
BEFORE INSERT ON outcome_review_reviewer_identities
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_trust_roots root
    WHERE root.trust_root_id = NEW.verified_by_trust_root_id
      AND root.effective_at <= NEW.registered_at
      AND (root.expires_at IS NULL OR root.expires_at > NEW.registered_at)
  ) THEN RAISE(ABORT, 'reviewer identity lacks an active real trust root') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_auth_grant_guard
BEFORE INSERT ON outcome_review_auth_events
WHEN NEW.auth_state = 'granted'
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_trust_roots root
    JOIN outcome_review_reviewer_identities issuer
      ON issuer.reviewer_public_id = NEW.issuer_public_id
    JOIN outcome_review_reviewer_identities target
      ON target.reviewer_public_id = NEW.reviewer_public_id
    WHERE root.trust_root_id = NEW.issuer_trust_root_id
      AND root.authority_public_id = issuer.reviewer_public_id
      AND root.identity_provider = issuer.identity_provider
      AND root.provider_subject_sha256 = issuer.provider_subject_sha256
      AND issuer.registered_at <= NEW.effective_at
      AND target.registered_at <= NEW.effective_at
      AND root.effective_at <= NEW.effective_at
      AND (root.expires_at IS NULL OR root.expires_at > NEW.effective_at)
      AND (
        root.expires_at IS NULL
        OR (NEW.expires_at IS NOT NULL AND NEW.expires_at <= root.expires_at)
      )
  ) THEN RAISE(ABORT, 'authorization grant lacks pinned trust-root authority') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_auth_supersession_guard
BEFORE INSERT ON outcome_review_auth_events
WHEN NEW.auth_state = 'revoked'
BEGIN
  SELECT CASE WHEN NEW.effective_at < COALESCE((
    SELECT occurred_at FROM outcome_review_operational_audit_events
    ORDER BY operational_audit_pk DESC LIMIT 1
  ), '0000-01-01T00:00:00Z')
    THEN RAISE(ABORT, 'authorization revocation cannot be retroactive') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_trust_roots root
    JOIN outcome_review_reviewer_identities issuer
      ON issuer.reviewer_public_id = NEW.issuer_public_id
    JOIN outcome_review_reviewer_identities target
      ON target.reviewer_public_id = NEW.reviewer_public_id
    WHERE root.trust_root_id = NEW.issuer_trust_root_id
      AND root.authority_public_id = issuer.reviewer_public_id
      AND root.identity_provider = issuer.identity_provider
      AND root.provider_subject_sha256 = issuer.provider_subject_sha256
      AND issuer.registered_at <= NEW.effective_at
      AND target.registered_at <= NEW.effective_at
      AND root.effective_at <= NEW.effective_at
      AND (root.expires_at IS NULL OR root.expires_at > NEW.effective_at)
  ) THEN RAISE(ABORT, 'authorization revocation lacks pinned trust-root authority') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_auth_events granted
    WHERE granted.auth_event_id = NEW.supersedes_auth_event_id
      AND granted.auth_state = 'granted'
      AND granted.reviewer_public_id = NEW.reviewer_public_id
      AND granted.reviewer_role = NEW.reviewer_role
      AND granted.cohort_id IS NEW.cohort_id
      AND granted.effective_at <= NEW.effective_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events prior_revocation
        WHERE prior_revocation.supersedes_auth_event_id = granted.auth_event_id
          AND prior_revocation.auth_state = 'revoked'
      )
  ) THEN RAISE(ABORT, 'authorization revocation must supersede matching active grant') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_conflict_supersession_guard
BEFORE INSERT ON outcome_review_conflict_events
WHEN NEW.conflict_state = 'cleared'
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_conflict_events declared
    WHERE declared.conflict_event_id = NEW.supersedes_conflict_event_id
      AND declared.conflict_state = 'declared'
      AND declared.reviewer_public_id = NEW.reviewer_public_id
      AND declared.cohort_id = NEW.cohort_id
      AND declared.task_pk IS NEW.task_pk
      AND declared.conflict_kind = NEW.conflict_kind
      AND declared.recorded_at <= NEW.recorded_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events prior_clearance
        WHERE prior_clearance.supersedes_conflict_event_id = declared.conflict_event_id
          AND prior_clearance.conflict_state = 'cleared'
      )
  ) THEN RAISE(ABORT, 'conflict clearance must supersede matching active declaration') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_conflict_task_cohort_guard
BEFORE INSERT ON outcome_review_conflict_events
BEGIN
  SELECT CASE WHEN NEW.recorded_at < COALESCE((
    SELECT occurred_at FROM outcome_review_operational_audit_events
    ORDER BY operational_audit_pk DESC LIMIT 1
  ), '0000-01-01T00:00:00Z')
    THEN RAISE(ABORT, 'conflict event cannot be retroactive') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_reviewer_identities reviewer
    WHERE reviewer.reviewer_public_id = NEW.reviewer_public_id
      AND reviewer.registered_at <= NEW.recorded_at
  ) THEN RAISE(ABORT, 'conflict predates reviewer registration') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_tasks task
    WHERE task.task_pk = NEW.task_pk AND task.cohort_id = NEW.cohort_id
  ) AND NEW.task_pk IS NOT NULL
    THEN RAISE(ABORT, 'task-scoped conflict must match the task cohort') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_assignment_release_guard
BEFORE INSERT ON outcome_review_assignment_events
WHEN NEW.assignment_state = 'released'
BEGIN
  SELECT CASE WHEN NEW.recorded_at < COALESCE((
    SELECT occurred_at FROM outcome_review_operational_audit_events
    ORDER BY operational_audit_pk DESC LIMIT 1
  ), '0000-01-01T00:00:00Z')
    THEN RAISE(ABORT, 'assignment release cannot be retroactive') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_assignment_events assigned
    WHERE assigned.assignment_event_id = NEW.supersedes_assignment_event_id
      AND assigned.assignment_state = 'assigned'
      AND assigned.slot_pk = NEW.slot_pk
      AND assigned.reviewer_public_id = NEW.reviewer_public_id
      AND assigned.auth_event_id = NEW.auth_event_id
      AND assigned.recorded_at <= NEW.recorded_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_assignment_events prior_release
        WHERE prior_release.supersedes_assignment_event_id = assigned.assignment_event_id
          AND prior_release.assignment_state = 'released'
      )
  ) THEN RAISE(ABORT, 'assignment release must supersede matching active assignment') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_assignment_guard
BEFORE INSERT ON outcome_review_assignment_events
WHEN NEW.assignment_state = 'assigned'
BEGIN
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM outcome_review_decisions decision
    WHERE decision.slot_pk = NEW.slot_pk
  ) OR EXISTS (
    SELECT 1 FROM outcome_review_claim_events completed
    WHERE completed.slot_pk = NEW.slot_pk
      AND completed.claim_state = 'completed'
  ) THEN RAISE(ABORT, 'completed review slots cannot be reassigned') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_slots s
    JOIN outcome_review_tasks t USING(task_pk)
    JOIN outcome_review_cohorts c USING(cohort_id)
    JOIN outcome_review_auth_events a ON a.auth_event_id = NEW.auth_event_id
    WHERE s.slot_pk = NEW.slot_pk
      AND t.assignment_eligible = 1
      AND a.reviewer_public_id = NEW.reviewer_public_id
      AND a.reviewer_role = s.required_reviewer_role
      AND (a.cohort_id IS NULL OR a.cohort_id = c.cohort_id)
      AND a.auth_state = 'granted'
      AND a.effective_at <= NEW.recorded_at
      AND (a.expires_at IS NULL OR a.expires_at > NEW.recorded_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = a.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'review assignment lacks active scoped authorization') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM outcome_review_conflict_events conflict
    JOIN outcome_review_slots selected_slot ON selected_slot.slot_pk = NEW.slot_pk
    JOIN outcome_review_tasks task ON task.task_pk = selected_slot.task_pk
    WHERE conflict.reviewer_public_id = NEW.reviewer_public_id
      AND conflict.cohort_id = task.cohort_id
      AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
      AND conflict.conflict_state = 'declared'
      AND conflict.recorded_at <= NEW.recorded_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events cleared
        WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
          AND cleared.conflict_state = 'cleared'
          AND cleared.recorded_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'review assignment conflicts with declared interest') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM outcome_review_assignment_events prior
    WHERE prior.slot_pk = NEW.slot_pk
      AND prior.assignment_state = 'assigned'
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_assignment_events released
        WHERE released.supersedes_assignment_event_id = prior.assignment_event_id
          AND released.assignment_state = 'released'
          AND released.recorded_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'review slot already has an active assignment') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM outcome_review_slots requested
    JOIN outcome_review_slots peer ON peer.task_pk = requested.task_pk
    JOIN outcome_review_assignment_events assigned ON assigned.slot_pk = peer.slot_pk
    JOIN outcome_review_reviewer_identities requested_identity
      ON requested_identity.reviewer_public_id = NEW.reviewer_public_id
    JOIN outcome_review_reviewer_identities assigned_identity
      ON assigned_identity.reviewer_public_id = assigned.reviewer_public_id
    WHERE requested.slot_pk = NEW.slot_pk
      AND requested.review_dimension = 'semantic'
      AND peer.slot_pk <> requested.slot_pk
      AND assigned.assignment_state = 'assigned'
      AND requested_identity.human_identity_sha256
        = assigned_identity.human_identity_sha256
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_assignment_events released
        WHERE released.supersedes_assignment_event_id = assigned.assignment_event_id
          AND released.assignment_state = 'released'
          AND released.recorded_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'dual semantic review requires distinct humans') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_claim_guard
BEFORE INSERT ON outcome_review_claim_events
BEGIN
  SELECT CASE WHEN NEW.supersedes_claim_event_id IS NOT NULL
    AND NEW.recorded_at < COALESCE((
      SELECT occurred_at FROM outcome_review_operational_audit_events
      ORDER BY operational_audit_pk DESC LIMIT 1
    ), '0000-01-01T00:00:00Z')
    THEN RAISE(ABORT, 'claim transition cannot be retroactive') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_assignment_events assignment
    WHERE assignment.assignment_event_id = NEW.assignment_event_id
      AND assignment.assignment_state = 'assigned'
      AND assignment.slot_pk = NEW.slot_pk
      AND assignment.reviewer_public_id = NEW.reviewer_public_id
      AND assignment.recorded_at <= NEW.recorded_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_assignment_events released
        WHERE released.supersedes_assignment_event_id = assignment.assignment_event_id
          AND released.assignment_state = 'released'
          AND released.recorded_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'claim transition lacks an active authorized assignment') END;
  SELECT CASE WHEN NEW.claim_state = 'claimed' AND EXISTS (
    SELECT 1 FROM outcome_review_claim_events prior
    WHERE prior.slot_pk = NEW.slot_pk
      AND prior.claim_state IN ('claimed', 'heartbeat')
      AND prior.lease_expires_at > NEW.recorded_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_claim_events successor
        WHERE successor.supersedes_claim_event_id = prior.claim_event_id
          AND successor.recorded_at <= NEW.recorded_at
      )
  ) THEN RAISE(ABORT, 'review slot already has a live claim lease') END;
  SELECT CASE WHEN NEW.claim_state = 'claimed'
    AND NEW.supersedes_claim_event_id IS NULL AND EXISTS (
      SELECT 1 FROM outcome_review_claim_events prior
      WHERE prior.slot_pk = NEW.slot_pk
    ) THEN RAISE(ABORT, 'only the first claim attempt may start a new lineage') END;
  SELECT CASE WHEN NEW.claim_state = 'claimed' AND EXISTS (
    SELECT 1 FROM outcome_review_claim_events completed
    WHERE completed.slot_pk = NEW.slot_pk
      AND completed.claim_state = 'completed'
  ) THEN RAISE(ABORT, 'a completed review slot cannot be reclaimed') END;
  SELECT CASE WHEN NEW.claim_state IN ('claimed', 'heartbeat') AND NOT EXISTS (
    SELECT 1
    FROM outcome_review_assignment_events assignment
    JOIN outcome_review_slots slot ON slot.slot_pk = NEW.slot_pk
    JOIN outcome_review_tasks task ON task.task_pk = slot.task_pk
    JOIN outcome_review_auth_events auth
      ON auth.auth_event_id = assignment.auth_event_id
    WHERE assignment.assignment_event_id = NEW.assignment_event_id
      AND auth.reviewer_public_id = NEW.reviewer_public_id
      AND auth.auth_state = 'granted'
      AND auth.effective_at <= NEW.recorded_at
      AND (auth.expires_at IS NULL OR auth.expires_at > NEW.recorded_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.recorded_at
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events conflict
        WHERE conflict.reviewer_public_id = NEW.reviewer_public_id
          AND conflict.cohort_id = task.cohort_id
          AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
          AND conflict.conflict_state = 'declared'
          AND conflict.recorded_at <= NEW.recorded_at
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_conflict_events cleared
            WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
              AND cleared.conflict_state = 'cleared'
              AND cleared.recorded_at <= NEW.recorded_at
          )
      )
  ) THEN RAISE(ABORT, 'claim lease lacks current authorization or has a conflict') END;
  SELECT CASE WHEN NEW.claim_state = 'claimed'
    AND NEW.supersedes_claim_event_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM outcome_review_claim_events prior
      WHERE prior.claim_event_id = NEW.supersedes_claim_event_id
        AND prior.slot_pk = NEW.slot_pk
        AND prior.claim_state IN ('released', 'reclaimed')
        AND prior.attempt_ordinal + 1 = NEW.attempt_ordinal
        AND prior.lease_token_sha256 <> NEW.lease_token_sha256
        AND prior.recorded_at <= NEW.recorded_at
        AND NOT EXISTS (
          SELECT 1 FROM outcome_review_claim_events later
          WHERE later.supersedes_claim_event_id = prior.claim_event_id
        )
    ) THEN RAISE(ABORT, 'new claim attempt must supersede the current terminal lease') END;
  SELECT CASE WHEN NEW.claim_state <> 'claimed' AND NOT EXISTS (
    SELECT 1 FROM outcome_review_claim_events prior
    WHERE prior.claim_event_id = NEW.supersedes_claim_event_id
      AND prior.assignment_event_id = NEW.assignment_event_id
      AND prior.slot_pk = NEW.slot_pk
      AND prior.reviewer_public_id = NEW.reviewer_public_id
      AND prior.lease_token_sha256 = NEW.lease_token_sha256
      AND prior.attempt_ordinal = NEW.attempt_ordinal
      AND prior.recorded_at <= NEW.recorded_at
      AND prior.claim_state IN ('claimed', 'heartbeat')
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_claim_events later
        WHERE later.supersedes_claim_event_id = prior.claim_event_id
      )
      AND (
        (NEW.claim_state IN ('heartbeat', 'released', 'completed')
          AND prior.lease_expires_at > NEW.recorded_at)
        OR (NEW.claim_state = 'reclaimed'
          AND prior.lease_expires_at <= NEW.recorded_at)
      )
      AND (
        (NEW.claim_state = 'heartbeat'
          AND NEW.lease_expires_at > prior.lease_expires_at)
        OR (NEW.claim_state IN ('released', 'completed', 'reclaimed')
          AND NEW.lease_expires_at = prior.lease_expires_at)
      )
  ) THEN RAISE(ABORT, 'claim transition is not the current authorized lease') END;
  SELECT CASE WHEN NEW.claim_state = 'reclaimed' AND NOT EXISTS (
    SELECT 1
    FROM outcome_review_auth_events auth
    JOIN outcome_review_slots slot ON slot.slot_pk = NEW.slot_pk
    JOIN outcome_review_tasks task ON task.task_pk = slot.task_pk
    WHERE auth.auth_event_id = NEW.actor_auth_event_id
      AND auth.reviewer_public_id = NEW.actor_public_id
      AND auth.reviewer_role = 'claim_coordinator'
      AND (auth.cohort_id IS NULL OR auth.cohort_id = task.cohort_id)
      AND auth.auth_state = 'granted'
      AND auth.effective_at <= NEW.recorded_at
      AND (auth.expires_at IS NULL OR auth.expires_at > NEW.recorded_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.recorded_at
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events conflict
        WHERE conflict.reviewer_public_id = NEW.actor_public_id
          AND conflict.cohort_id = task.cohort_id
          AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
          AND conflict.conflict_state = 'declared'
          AND conflict.recorded_at <= NEW.recorded_at
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_conflict_events cleared
            WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
              AND cleared.conflict_state = 'cleared'
              AND cleared.recorded_at <= NEW.recorded_at
          )
      )
  ) THEN RAISE(ABORT, 'claim reclaim lacks active coordinator authorization') END;
  SELECT CASE WHEN NEW.claim_state = 'completed' AND NOT EXISTS (
    SELECT 1 FROM outcome_review_decisions decision
    WHERE decision.claim_event_id = NEW.supersedes_claim_event_id
      AND decision.assignment_event_id = NEW.assignment_event_id
      AND decision.slot_pk = NEW.slot_pk
      AND decision.reviewer_public_id = NEW.reviewer_public_id
      AND decision.decided_at <= NEW.recorded_at
  ) THEN RAISE(ABORT, 'claim completion requires its committed review decision') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_decision_guard
BEFORE INSERT ON outcome_review_decisions
BEGIN
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.evidence_examined_json) evidence
    WHERE evidence.type <> 'text'
      OR length(trim(CAST(evidence.value AS TEXT))) NOT BETWEEN 1 AND 2048
  ) THEN RAISE(ABORT, 'decision evidence references must be bounded strings') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_assignment_events assignment
    JOIN outcome_review_slots slot ON slot.slot_pk = assignment.slot_pk
    JOIN outcome_review_claim_events claim
      ON claim.claim_event_id = NEW.claim_event_id
    WHERE assignment.assignment_event_id = NEW.assignment_event_id
      AND assignment.assignment_state = 'assigned'
      AND assignment.slot_pk = NEW.slot_pk
      AND assignment.reviewer_public_id = NEW.reviewer_public_id
      AND assignment.recorded_at <= NEW.decided_at
      AND slot.task_pk = NEW.task_pk
      AND claim.assignment_event_id = assignment.assignment_event_id
      AND claim.slot_pk = assignment.slot_pk
      AND claim.reviewer_public_id = NEW.reviewer_public_id
      AND claim.claim_state IN ('claimed', 'heartbeat')
      AND claim.recorded_at <= NEW.decided_at
      AND claim.lease_expires_at > NEW.decided_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_claim_events later_claim
        WHERE later_claim.supersedes_claim_event_id = claim.claim_event_id
          AND later_claim.recorded_at <= NEW.decided_at
      )
      AND EXISTS (
        SELECT 1
        FROM outcome_review_auth_events auth
        WHERE auth.auth_event_id = assignment.auth_event_id
          AND auth.auth_state = 'granted'
          AND auth.effective_at <= NEW.decided_at
          AND (auth.expires_at IS NULL OR auth.expires_at > NEW.decided_at)
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_auth_events revoked
            WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
              AND revoked.auth_state = 'revoked'
              AND revoked.effective_at <= NEW.decided_at
          )
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_assignment_events released
        WHERE released.supersedes_assignment_event_id = assignment.assignment_event_id
          AND released.assignment_state = 'released'
          AND released.recorded_at <= NEW.decided_at
      )
  ) THEN RAISE(ABORT, 'review decision lacks active assignment') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM outcome_review_slots slot
    WHERE slot.slot_pk = NEW.slot_pk
      AND (
        (slot.review_dimension = 'discovery_triage'
          AND NEW.decision_value NOT IN (
            'advance_to_semantic_review', 'exclude_from_semantic_review',
            'insufficient_evidence'
          ))
        OR
        (slot.review_dimension = 'semantic'
          AND NEW.decision_value NOT IN ('support', 'reject', 'needs_more_evidence'))
      )
  ) THEN RAISE(ABORT, 'decision value does not match review dimension') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM outcome_review_slots requested
    JOIN outcome_review_decisions prior ON prior.task_pk = requested.task_pk
    JOIN outcome_review_slots prior_slot ON prior_slot.slot_pk = prior.slot_pk
    JOIN outcome_review_reviewer_identities requested_identity
      ON requested_identity.reviewer_public_id = NEW.reviewer_public_id
    JOIN outcome_review_reviewer_identities prior_identity
      ON prior_identity.reviewer_public_id = prior.reviewer_public_id
    WHERE requested.slot_pk = NEW.slot_pk
      AND requested.review_dimension = 'semantic'
      AND prior_slot.review_dimension = 'semantic'
      AND requested_identity.human_identity_sha256
        = prior_identity.human_identity_sha256
  ) THEN RAISE(ABORT, 'dual semantic decisions require distinct humans') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM outcome_review_slots selected_slot
    JOIN outcome_review_tasks task ON task.task_pk = selected_slot.task_pk
    JOIN outcome_review_conflict_events conflict
      ON conflict.reviewer_public_id = NEW.reviewer_public_id
      AND conflict.cohort_id = task.cohort_id
      AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
    WHERE selected_slot.slot_pk = NEW.slot_pk
      AND conflict.conflict_state = 'declared'
      AND conflict.recorded_at <= NEW.decided_at
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events cleared
        WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
          AND cleared.conflict_state = 'cleared'
          AND cleared.recorded_at <= NEW.decided_at
      )
  ) THEN RAISE(ABORT, 'review decision conflicts with declared interest') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_adjudication_guard
BEFORE INSERT ON outcome_review_adjudications
BEGIN
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM json_each(NEW.evidence_examined_json) evidence
    WHERE evidence.type <> 'text'
      OR length(trim(CAST(evidence.value AS TEXT))) NOT BETWEEN 1 AND 2048
  ) THEN RAISE(ABORT, 'adjudication evidence references must be bounded strings') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_decisions primary_decision
    JOIN outcome_review_slots primary_slot ON primary_slot.slot_pk = primary_decision.slot_pk
    JOIN outcome_review_decisions secondary_decision
      ON secondary_decision.decision_id = NEW.secondary_decision_id
    JOIN outcome_review_slots secondary_slot
      ON secondary_slot.slot_pk = secondary_decision.slot_pk
    JOIN outcome_review_tasks task ON task.task_pk = NEW.task_pk
    JOIN outcome_review_auth_events auth ON auth.auth_event_id = NEW.auth_event_id
    JOIN outcome_review_reviewer_identities primary_identity
      ON primary_identity.reviewer_public_id = primary_decision.reviewer_public_id
    JOIN outcome_review_reviewer_identities secondary_identity
      ON secondary_identity.reviewer_public_id = secondary_decision.reviewer_public_id
    JOIN outcome_review_reviewer_identities adjudicator_identity
      ON adjudicator_identity.reviewer_public_id = NEW.adjudicator_public_id
    WHERE primary_decision.decision_id = NEW.primary_decision_id
      AND primary_decision.task_pk = NEW.task_pk
      AND secondary_decision.task_pk = NEW.task_pk
      AND primary_slot.slot_kind = 'semantic_primary'
      AND secondary_slot.slot_kind = 'semantic_secondary'
      AND primary_decision.decision_value <> secondary_decision.decision_value
      AND primary_decision.reviewer_public_id <> secondary_decision.reviewer_public_id
      AND primary_decision.decided_at <= NEW.adjudicated_at
      AND secondary_decision.decided_at <= NEW.adjudicated_at
      AND EXISTS (
        SELECT 1 FROM outcome_review_claim_events completed_primary
        WHERE completed_primary.supersedes_claim_event_id
          = primary_decision.claim_event_id
          AND completed_primary.claim_state = 'completed'
          AND completed_primary.recorded_at <= NEW.adjudicated_at
      )
      AND EXISTS (
        SELECT 1 FROM outcome_review_claim_events completed_secondary
        WHERE completed_secondary.supersedes_claim_event_id
          = secondary_decision.claim_event_id
          AND completed_secondary.claim_state = 'completed'
          AND completed_secondary.recorded_at <= NEW.adjudicated_at
      )
      AND primary_identity.human_identity_sha256
        <> secondary_identity.human_identity_sha256
      AND adjudicator_identity.human_identity_sha256
        <> primary_identity.human_identity_sha256
      AND adjudicator_identity.human_identity_sha256
        <> secondary_identity.human_identity_sha256
      AND auth.reviewer_public_id = NEW.adjudicator_public_id
      AND auth.reviewer_role = 'adjudicator'
      AND (auth.cohort_id IS NULL OR auth.cohort_id = task.cohort_id)
      AND auth.auth_state = 'granted'
      AND auth.effective_at <= NEW.adjudicated_at
      AND (auth.expires_at IS NULL OR auth.expires_at > NEW.adjudicated_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.adjudicated_at
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events conflict
        WHERE conflict.reviewer_public_id = NEW.adjudicator_public_id
          AND conflict.cohort_id = task.cohort_id
          AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
          AND conflict.conflict_state = 'declared'
          AND conflict.recorded_at <= NEW.adjudicated_at
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_conflict_events cleared
            WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
              AND cleared.conflict_state = 'cleared'
              AND cleared.recorded_at <= NEW.adjudicated_at
          )
      )
  ) THEN RAISE(ABORT, 'adjudication requires a real disagreement and independent authority') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_eligibility_guard
BEFORE INSERT ON outcome_review_semantic_eligibility_events
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_tasks task
    WHERE task.task_pk = NEW.task_pk
      AND task.task_kind = 'semantic_canary'
      AND task.evidence_level = 'L1'
      AND (
        EXISTS (
          SELECT 1
          FROM outcome_review_decisions first
          JOIN outcome_review_slots first_slot ON first_slot.slot_pk = first.slot_pk
          JOIN outcome_review_decisions second ON second.task_pk = first.task_pk
          JOIN outcome_review_slots second_slot ON second_slot.slot_pk = second.slot_pk
          WHERE first.decision_id = NEW.primary_decision_id
            AND second.decision_id = NEW.secondary_decision_id
            AND first.task_pk = task.task_pk
            AND first_slot.slot_kind = 'semantic_primary'
            AND second_slot.slot_kind = 'semantic_secondary'
            AND first.decision_value = 'support'
            AND second.decision_value = 'support'
            AND first.reviewer_public_id <> second.reviewer_public_id
            AND first.decided_at <= NEW.computed_at
            AND second.decided_at <= NEW.computed_at
            AND EXISTS (
              SELECT 1 FROM outcome_review_claim_events completed_first
              WHERE completed_first.supersedes_claim_event_id = first.claim_event_id
                AND completed_first.claim_state = 'completed'
                AND completed_first.recorded_at <= NEW.computed_at
            )
            AND EXISTS (
              SELECT 1 FROM outcome_review_claim_events completed_second
              WHERE completed_second.supersedes_claim_event_id = second.claim_event_id
                AND completed_second.claim_state = 'completed'
                AND completed_second.recorded_at <= NEW.computed_at
            )
        )
        OR EXISTS (
          SELECT 1 FROM outcome_review_adjudications adjudication
          WHERE adjudication.adjudication_id = NEW.adjudication_id
            AND adjudication.task_pk = task.task_pk
            AND adjudication.adjudicated_value = 'support'
            AND adjudication.adjudicated_at <= NEW.computed_at
        )
      )
  ) THEN RAISE(ABORT, 'semantic eligibility requires completed supporting review') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_promotion_guard
BEFORE INSERT ON outcome_review_semantic_promotions
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_tasks task
    JOIN outcome_review_semantic_eligibility_events eligibility
      ON eligibility.eligibility_event_id = NEW.eligibility_event_id
    JOIN outcome_review_auth_events auth ON auth.auth_event_id = NEW.auth_event_id
    WHERE task.task_pk = NEW.task_pk
      AND task.task_kind = 'semantic_canary'
      AND task.evidence_level = 'L1'
      AND eligibility.task_pk = task.task_pk
      AND eligibility.eligibility_state = 'eligible'
      AND eligibility.computed_at <= NEW.promoted_at
      AND auth.reviewer_public_id = NEW.promotion_authority_public_id
      AND auth.reviewer_role = 'promotion_authority'
      AND (auth.cohort_id IS NULL OR auth.cohort_id = task.cohort_id)
      AND auth.auth_state = 'granted'
      AND auth.effective_at <= NEW.promoted_at
      AND (auth.expires_at IS NULL OR auth.expires_at > NEW.promoted_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.promoted_at
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events conflict
        WHERE conflict.reviewer_public_id = NEW.promotion_authority_public_id
          AND conflict.cohort_id = task.cohort_id
          AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
          AND conflict.conflict_state = 'declared'
          AND conflict.recorded_at <= NEW.promoted_at
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_conflict_events cleared
            WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
              AND cleared.conflict_state = 'cleared'
              AND cleared.recorded_at <= NEW.promoted_at
          )
      )
  ) THEN RAISE(ABORT, 'semantic promotion requires computed eligibility and active authority') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_release_binding_guard
BEFORE INSERT ON outcome_review_release_bindings
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM outcome_review_tasks task
    WHERE task.task_pk = NEW.task_pk
      AND task.task_kind = 'semantic_canary'
      AND task.source_row_id = NEW.outcome_link_version_id
  ) THEN RAISE(ABORT, 'release membership must bind the reviewed source version') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_eligibility_guard
BEFORE INSERT ON outcome_review_publication_eligibility_events
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_semantic_promotions promotion
    JOIN outcome_review_release_bindings binding
      ON binding.release_binding_id = NEW.release_binding_id
    WHERE promotion.promotion_id = NEW.promotion_id
      AND promotion.task_pk = NEW.task_pk
      AND binding.task_pk = NEW.task_pk
      AND promotion.promoted_at <= NEW.computed_at
      AND binding.verified_at <= NEW.computed_at
  ) THEN RAISE(ABORT, 'publication eligibility requires promotion and verified release membership') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_guard
BEFORE INSERT ON outcome_review_publication_events
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM outcome_review_semantic_promotions promotion
    JOIN outcome_review_publication_eligibility_events eligibility
      ON eligibility.publication_eligibility_event_id = NEW.publication_eligibility_event_id
    JOIN outcome_review_release_bindings binding
      ON binding.release_binding_id = NEW.release_binding_id
    JOIN outcome_review_tasks task ON task.task_pk = promotion.task_pk
    JOIN outcome_review_auth_events auth ON auth.auth_event_id = NEW.auth_event_id
    WHERE promotion.promotion_id = NEW.promotion_id
      AND promotion.task_pk = NEW.task_pk
      AND eligibility.task_pk = NEW.task_pk
      AND eligibility.promotion_id = promotion.promotion_id
      AND eligibility.release_binding_id = binding.release_binding_id
      AND eligibility.eligibility_state = 'eligible'
      AND binding.task_pk = NEW.task_pk
      AND binding.outcome_link_release_id = NEW.outcome_link_release_id
      AND binding.outcome_link_release_membership_id = NEW.outcome_link_release_membership_id
      AND promotion.promoted_at <= NEW.published_at
      AND eligibility.computed_at <= NEW.published_at
      AND binding.verified_at <= NEW.published_at
      AND auth.reviewer_public_id = NEW.publisher_public_id
      AND auth.reviewer_role = 'publisher'
      AND (auth.cohort_id IS NULL OR auth.cohort_id = task.cohort_id)
      AND auth.auth_state = 'granted'
      AND auth.effective_at <= NEW.published_at
      AND (auth.expires_at IS NULL OR auth.expires_at > NEW.published_at)
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_auth_events revoked
        WHERE revoked.supersedes_auth_event_id = auth.auth_event_id
          AND revoked.auth_state = 'revoked'
          AND revoked.effective_at <= NEW.published_at
      )
      AND NOT EXISTS (
        SELECT 1 FROM outcome_review_conflict_events conflict
        WHERE conflict.reviewer_public_id = NEW.publisher_public_id
          AND conflict.cohort_id = task.cohort_id
          AND (conflict.task_pk IS NULL OR conflict.task_pk = task.task_pk)
          AND conflict.conflict_state = 'declared'
          AND conflict.recorded_at <= NEW.published_at
          AND NOT EXISTS (
            SELECT 1 FROM outcome_review_conflict_events cleared
            WHERE cleared.supersedes_conflict_event_id = conflict.conflict_event_id
              AND cleared.conflict_state = 'cleared'
              AND cleared.recorded_at <= NEW.published_at
          )
      )
  ) THEN RAISE(ABORT, 'public release lacks computed eligibility or bound release membership') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_outcome_review_control_meta_status_transition
BEFORE UPDATE ON outcome_review_control_meta
WHEN NOT (
  OLD.control_plane_capacity_status = 'BUILDING'
  AND NEW.control_plane_capacity_status = 'PASS'
  AND OLD.pipeline_key IS NEW.pipeline_key
  AND OLD.contract_version IS NEW.contract_version
  AND OLD.config_sha256 IS NEW.config_sha256
  AND OLD.source_root_sha256 IS NEW.source_root_sha256
  AND OLD.schema_root_sha256 IS NEW.schema_root_sha256
  AND OLD.artifact_scope IS NEW.artifact_scope
  AND OLD.trust_root_contract_sha256 IS NEW.trust_root_contract_sha256
  AND OLD.operational_state IS NEW.operational_state
  AND OLD.human_review_status IS NEW.human_review_status
  AND OLD.semantic_promotion_status IS NEW.semantic_promotion_status
  AND OLD.public_release_status IS NEW.public_release_status
  AND OLD.real_data_only IS NEW.real_data_only
  AND OLD.synthetic_or_mock_decisions IS NEW.synthetic_or_mock_decisions
  AND OLD.capacity_snapshot_effective_at IS NEW.capacity_snapshot_effective_at
  AND OLD.row_semantic_sha256 IS NOT NEW.row_semantic_sha256
  AND EXISTS (
    SELECT 1 FROM outcome_review_control_checkpoints checkpoint
    WHERE checkpoint.pipeline_key = OLD.pipeline_key
      AND checkpoint.stage = 'discovery_tasks'
      AND checkpoint.completed = 1
  )
)
BEGIN
  SELECT RAISE(ABORT, 'review control meta permits only BUILDING to PASS');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_control_meta_no_delete
BEFORE DELETE ON outcome_review_control_meta BEGIN
  SELECT RAISE(ABORT, 'outcome_review_control_meta is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_cohorts_no_update
BEFORE UPDATE ON outcome_review_cohorts BEGIN
  SELECT RAISE(ABORT, 'outcome_review_cohorts is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_cohorts_no_delete
BEFORE DELETE ON outcome_review_cohorts BEGIN
  SELECT RAISE(ABORT, 'outcome_review_cohorts is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_tasks_no_update
BEFORE UPDATE ON outcome_review_tasks BEGIN
  SELECT RAISE(ABORT, 'outcome_review_tasks is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_tasks_no_delete
BEFORE DELETE ON outcome_review_tasks BEGIN
  SELECT RAISE(ABORT, 'outcome_review_tasks is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_slots_no_update
BEFORE UPDATE ON outcome_review_slots BEGIN
  SELECT RAISE(ABORT, 'outcome_review_slots is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_slots_no_delete
BEFORE DELETE ON outcome_review_slots BEGIN
  SELECT RAISE(ABORT, 'outcome_review_slots is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_trust_roots_no_update
BEFORE UPDATE ON outcome_review_trust_roots BEGIN
  SELECT RAISE(ABORT, 'outcome_review_trust_roots is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_trust_roots_no_delete
BEFORE DELETE ON outcome_review_trust_roots BEGIN
  SELECT RAISE(ABORT, 'outcome_review_trust_roots is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_reviewer_identities_no_update
BEFORE UPDATE ON outcome_review_reviewer_identities BEGIN
  SELECT RAISE(ABORT, 'outcome_review_reviewer_identities is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_reviewer_identities_no_delete
BEFORE DELETE ON outcome_review_reviewer_identities BEGIN
  SELECT RAISE(ABORT, 'outcome_review_reviewer_identities is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_auth_events_no_update
BEFORE UPDATE ON outcome_review_auth_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_auth_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_auth_events_no_delete
BEFORE DELETE ON outcome_review_auth_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_auth_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_conflict_events_no_update
BEFORE UPDATE ON outcome_review_conflict_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_conflict_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_conflict_events_no_delete
BEFORE DELETE ON outcome_review_conflict_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_conflict_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_assignment_events_no_update
BEFORE UPDATE ON outcome_review_assignment_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_assignment_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_assignment_events_no_delete
BEFORE DELETE ON outcome_review_assignment_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_assignment_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_claim_events_no_update
BEFORE UPDATE ON outcome_review_claim_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_claim_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_claim_events_no_delete
BEFORE DELETE ON outcome_review_claim_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_claim_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_decisions_no_update
BEFORE UPDATE ON outcome_review_decisions BEGIN
  SELECT RAISE(ABORT, 'outcome_review_decisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_decisions_no_delete
BEFORE DELETE ON outcome_review_decisions BEGIN
  SELECT RAISE(ABORT, 'outcome_review_decisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_adjudications_no_update
BEFORE UPDATE ON outcome_review_adjudications BEGIN
  SELECT RAISE(ABORT, 'outcome_review_adjudications is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_adjudications_no_delete
BEFORE DELETE ON outcome_review_adjudications BEGIN
  SELECT RAISE(ABORT, 'outcome_review_adjudications is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_eligibility_events_no_update
BEFORE UPDATE ON outcome_review_semantic_eligibility_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_semantic_eligibility_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_eligibility_events_no_delete
BEFORE DELETE ON outcome_review_semantic_eligibility_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_semantic_eligibility_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_promotions_no_update
BEFORE UPDATE ON outcome_review_semantic_promotions BEGIN
  SELECT RAISE(ABORT, 'outcome_review_semantic_promotions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_semantic_promotions_no_delete
BEFORE DELETE ON outcome_review_semantic_promotions BEGIN
  SELECT RAISE(ABORT, 'outcome_review_semantic_promotions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_release_bindings_no_update
BEFORE UPDATE ON outcome_review_release_bindings BEGIN
  SELECT RAISE(ABORT, 'outcome_review_release_bindings is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_release_bindings_no_delete
BEFORE DELETE ON outcome_review_release_bindings BEGIN
  SELECT RAISE(ABORT, 'outcome_review_release_bindings is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_eligibility_events_no_update
BEFORE UPDATE ON outcome_review_publication_eligibility_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_publication_eligibility_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_eligibility_events_no_delete
BEFORE DELETE ON outcome_review_publication_eligibility_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_publication_eligibility_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_events_no_update
BEFORE UPDATE ON outcome_review_publication_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_publication_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_publication_events_no_delete
BEFORE DELETE ON outcome_review_publication_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_publication_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operation_requests_no_update
BEFORE UPDATE ON outcome_review_operation_requests BEGIN
  SELECT RAISE(ABORT, 'outcome_review_operation_requests is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operation_requests_no_delete
BEFORE DELETE ON outcome_review_operation_requests BEGIN
  SELECT RAISE(ABORT, 'outcome_review_operation_requests is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operational_audit_events_no_update
BEFORE UPDATE ON outcome_review_operational_audit_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_operational_audit_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_operational_audit_events_no_delete
BEFORE DELETE ON outcome_review_operational_audit_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_operational_audit_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_audit_events_no_update
BEFORE UPDATE ON outcome_review_audit_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_audit_events is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_outcome_review_audit_events_no_delete
BEFORE DELETE ON outcome_review_audit_events BEGIN
  SELECT RAISE(ABORT, 'outcome_review_audit_events is append-only');
END;
-- END OUTCOME REVIEW CONTROL C2C SCHEMA

-- Supports one bounded actor-release/source scan before bulk participant matching.
CREATE INDEX IF NOT EXISTS idx_actor_graph_node_versions_release_source_actor
  ON actor_graph_node_versions(release_id, source_id, actor_id, node_version_id);
