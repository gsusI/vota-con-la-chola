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

CREATE INDEX IF NOT EXISTS idx_runs_source_id ON ingestion_runs(source_id);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(full_name);
CREATE INDEX IF NOT EXISTS idx_persons_gender_id ON persons(gender_id);
CREATE INDEX IF NOT EXISTS idx_persons_territory_id ON persons(territory_id);
CREATE INDEX IF NOT EXISTS idx_mandates_person ON mandates(person_id);
CREATE INDEX IF NOT EXISTS idx_mandates_institution_id ON mandates(institution_id);
CREATE INDEX IF NOT EXISTS idx_mandates_party_id ON mandates(party_id);
CREATE INDEX IF NOT EXISTS idx_mandates_source ON mandates(source_id);
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
