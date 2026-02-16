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
  person_id INTEGER NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
  namespace TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (namespace, value)
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

-- Link votes to initiatives when we can do it deterministically (or with explicit method+confidence).
CREATE TABLE IF NOT EXISTS parl_vote_event_initiatives (
  vote_event_id TEXT NOT NULL REFERENCES parl_vote_events(vote_event_id) ON DELETE CASCADE,
  initiative_id TEXT NOT NULL REFERENCES parl_initiatives(initiative_id) ON DELETE CASCADE,
  link_method TEXT NOT NULL,
  confidence REAL,
  evidence_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (vote_event_id, initiative_id, link_method)
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
  topic_set_id INTEGER NOT NULL REFERENCES topic_sets(topic_set_id) ON DELETE CASCADE,
  topic_id INTEGER NOT NULL REFERENCES topics(topic_id) ON DELETE CASCADE,
  stakes_score REAL,
  stakes_rank INTEGER,
  is_high_stakes INTEGER NOT NULL DEFAULT 0 CHECK (is_high_stakes IN (0, 1)),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (topic_set_id, topic_id)
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
  policy_event_id TEXT NOT NULL REFERENCES policy_events(policy_event_id) ON DELETE CASCADE,
  policy_axis_id INTEGER NOT NULL REFERENCES policy_axes(policy_axis_id) ON DELETE CASCADE,
  direction INTEGER CHECK (direction IN (-1, 0, 1)),
  intensity REAL,
  confidence REAL,
  method TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (policy_event_id, policy_axis_id, method)
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
  intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id) ON DELETE CASCADE,
  policy_event_id TEXT NOT NULL REFERENCES policy_events(policy_event_id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (intervention_id, policy_event_id)
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
CREATE INDEX IF NOT EXISTS idx_institutions_admin_level_id ON institutions(admin_level_id);
CREATE INDEX IF NOT EXISTS idx_institutions_territory_id ON institutions(territory_id);
CREATE INDEX IF NOT EXISTS idx_party_aliases_party_id ON party_aliases(party_id);
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
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_vote ON parl_vote_event_initiatives(vote_event_id);
CREATE INDEX IF NOT EXISTS idx_parl_vote_event_initiatives_init ON parl_vote_event_initiatives(initiative_id);

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
CREATE INDEX IF NOT EXISTS idx_text_documents_source_id ON text_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_text_documents_source_record_pk ON text_documents(source_record_pk);
CREATE INDEX IF NOT EXISTS idx_text_documents_source_url ON text_documents(source_url);

CREATE INDEX IF NOT EXISTS idx_domains_tier ON domains(tier);
CREATE INDEX IF NOT EXISTS idx_policy_axes_domain_id ON policy_axes(domain_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_domain_id ON policy_events(domain_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_instrument_id ON policy_events(policy_instrument_id);
CREATE INDEX IF NOT EXISTS idx_policy_events_source_id ON policy_events(source_id);
CREATE INDEX IF NOT EXISTS idx_policy_event_axis_scores_axis_id ON policy_event_axis_scores(policy_axis_id);
CREATE INDEX IF NOT EXISTS idx_interventions_domain_id ON interventions(domain_id);
CREATE INDEX IF NOT EXISTS idx_intervention_events_event_id ON intervention_events(policy_event_id);
CREATE INDEX IF NOT EXISTS idx_indicator_series_domain_id ON indicator_series(domain_id);
CREATE INDEX IF NOT EXISTS idx_indicator_points_series_date ON indicator_points(indicator_series_id, date);
CREATE INDEX IF NOT EXISTS idx_causal_estimates_intervention_id ON causal_estimates(intervention_id);
