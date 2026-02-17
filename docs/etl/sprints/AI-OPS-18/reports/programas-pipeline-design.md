# Programas Partidos: Pipeline Design (v1)

Date: 2026-02-17  
Sprint: `AI-OPS-18`  
Source ID: `programas_partidos`

## Goal (v1)
Ship the first reproducible ingestion slice for party programs:
- manifest-driven extraction (`--from-file` works with sample CSV)
- traceability via `source_records` + `text_documents`
- declared-evidence rows created in `topic_evidence` so existing stance + review loop can run

This is a thin vertical slice, not a final modeling decision.

## Inputs
- Manifest CSV (contract v1): `etl/data/raw/samples/programas_partidos_sample.csv`
- Program docs (for sample): `etl/data/raw/samples/programas_partidos/*.html`
- Concern taxonomy (reused for program topics): `ui/citizen/concerns_v1.json`

## Storage Model (v1)
For each manifest row (document identity):
1. `source_records`
  - `source_record_id`: `programas_partidos:{election_cycle}:{party_id}:{kind}`
  - `raw_payload`: stable JSON of the manifest row + extraction metadata
  - `content_sha256`: sha256 of the document bytes (not the manifest)
2. `text_documents`
  - keyed by `source_record_pk` (unique)
  - stores doc metadata + a plain-text excerpt (<= 4000 chars)
  - raw bytes are stored on disk under: `etl/data/raw/text_documents/programas_partidos/<sha>.<ext>`
3. `topic_evidence`
  - `evidence_type='declared:programa'`
  - one row per `(party, election_cycle, concern_topic)` when the concern matches the document text
  - `excerpt` is topic-scoped (section text when available); stance classification uses this excerpt first

## Topic Set Strategy (v1)
Party programs need their own `topic_set` because existing `topic_sets` are initiative/vote-derived.

v1 chooses:
- `topic_sets.name = 'Programas de partidos'`
- `topic_sets.institution_id` anchored to a stable institution row:
  - `institutions(name='Programas de partidos', level='editorial', territory_code='')`
- `topic_sets.admin_level_id` = `admin_levels.code='nacional'`
- `topic_sets.territory_id` = `territories.code='ES'`
- `topic_sets.legislature = <election_cycle>` (e.g. `es_generales_2023`)
- `topics` are created from `ui/citizen/concerns_v1.json`:
  - `topics.canonical_key = concern:v1:<concern_id>`
  - `topic_set_topics` rebuilt deterministically on each ingest for that cycle

This makes the program lane user-first: topics correspond directly to citizen concerns.

## Modeling Mismatch: Party vs Person (Stopgap)
`topic_evidence.person_id` is `NOT NULL`, but programs are party-level.

v1 stopgap (explicit + reversible):
- Create one proxy row in `persons` per party:
  - `persons.canonical_key = party:<party_id>`
- Add mapping:
  - `person_identifiers(namespace='party_id', value='<party_id>') -> person_id`

This allows reusing the existing declared stance + position aggregation machinery without destructive schema changes.

## Stance Extraction Behavior (v1)
Existing extractor: `etl/parlamentario_es/declared_stance.py` (`declared:regex_v3`)

To keep stance inference topic-scoped for programs, v1 adjusts the backfill query:
- for `evidence_type='declared:programa'`, prefer `topic_evidence.excerpt` over `text_documents.text_excerpt`
- for other evidence types, preserve existing behavior

## Idempotence Policy (v1)
Programs are treated as derived/refreshable rows for now:
- On ingest, delete and rebuild `topic_evidence` rows for:
  - `source_id=programas_partidos`, `topic_set_id=<cycle set>`, `evidence_type='declared:programa'`

Note: this will delete any review decisions for those evidence rows (CASCADE). Preserving manual review state across re-ingests requires a future explicit stable identity constraint for evidence rows.

## Known Gaps / Next Steps
- Improve parsing beyond `<h2>` sections; add better snippet extraction per concern for real-world docs.
- Add a proper party-level stance/position model (preferred), then migrate away from proxy-person stopgap.
- Add deterministic tests:
  - manifest validation
  - idempotence for `source_records` / `text_documents`
  - minimal stance signal fixture
