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
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

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
  currency TEXT,
  raw_payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, source_record_pk)
);

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
  source_id TEXT NOT NULL REFERENCES sources(source_id)
      CHECK (
        source_id LIKE 'eurostat_%'
        OR source_id LIKE 'bde_%'
        OR source_id LIKE 'aemet_%'
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
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(full_name);
CREATE INDEX IF NOT EXISTS idx_persons_gender_id ON persons(gender_id);
CREATE INDEX IF NOT EXISTS idx_persons_territory_id ON persons(territory_id);
CREATE INDEX IF NOT EXISTS idx_mandates_person ON mandates(person_id);
CREATE INDEX IF NOT EXISTS idx_mandates_institution_id ON mandates(institution_id);
CREATE INDEX IF NOT EXISTS idx_mandates_party_id ON mandates(party_id);
CREATE INDEX IF NOT EXISTS idx_mandates_source ON mandates(source_id);

CREATE INDEX IF NOT EXISTS idx_infoelectoral_convocatorias_tipo ON infoelectoral_convocatorias(tipo_convocatoria);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_archivos_convocatoria ON infoelectoral_archivos_extraccion(convocatoria_id);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_procesos_estado ON infoelectoral_procesos(estado);
CREATE INDEX IF NOT EXISTS idx_infoelectoral_resultados_proceso ON infoelectoral_proceso_resultados(proceso_id);
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
CREATE INDEX IF NOT EXISTS idx_interventions_domain_id ON interventions(domain_id);
CREATE INDEX IF NOT EXISTS idx_intervention_events_event_id ON intervention_events(policy_event_id);
CREATE INDEX IF NOT EXISTS idx_indicator_series_domain_id ON indicator_series(domain_id);
CREATE INDEX IF NOT EXISTS idx_indicator_points_series_date ON indicator_points(indicator_series_id, date);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_source_series
    ON indicator_observation_records(source_id, series_code);
CREATE INDEX IF NOT EXISTS idx_indicator_observation_records_point_date
    ON indicator_observation_records(point_date);
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
