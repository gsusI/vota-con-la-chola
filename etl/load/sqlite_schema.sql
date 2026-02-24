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
  extracted_title TEXT,
  extracted_subject TEXT,
  extracted_excerpt TEXT,
  confidence REAL,
  needs_review INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
  analysis_payload_json TEXT,
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
  norm_id TEXT NOT NULL REFERENCES sanction_norm_catalog(norm_id) ON DELETE CASCADE,
  fragment_id TEXT NOT NULL REFERENCES legal_norm_fragments(fragment_id) ON DELETE CASCADE,
  link_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (norm_id, fragment_id)
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
CREATE INDEX IF NOT EXISTS idx_document_fetches_source_id ON document_fetches(source_id);
CREATE INDEX IF NOT EXISTS idx_document_fetches_fetched_ok ON document_fetches(fetched_ok);
CREATE INDEX IF NOT EXISTS idx_document_fetches_last_http_status ON document_fetches(last_http_status);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_source_id ON parl_initiative_doc_extractions(source_id);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_needs_review ON parl_initiative_doc_extractions(needs_review);
CREATE INDEX IF NOT EXISTS idx_parl_initdoc_extract_sample_initiative_id ON parl_initiative_doc_extractions(sample_initiative_id);

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
