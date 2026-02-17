# Programas Partidos: Source Contract (v1)

Date: 2026-02-17  
Sprint: `AI-OPS-19`  
Source ID: `programas_partidos`

## Purpose
Ingest party programs/web statements in a way that is:
- reproducible (manifest-driven; `--from-file` works)
- traceable (`source_records` + `text_documents` with stable keys and content hashes)
- compatible with the declared-evidence review loop (explicit uncertainty, bounded manual work)

This contract defines the **manifest schema** and the **identity/dedupe rules**. Implementation lands in subsequent tasks.

## Manifest Schema (CSV)
File: `etl/data/raw/samples/programas_partidos_sample.csv` (sample + contract baseline)

Required columns:
- `party_id` (int): must exist in SQLite `parties.party_id` for first slice.
- `party_name` (string): human label (redundant but useful for audits).
- `election_cycle` (string): stable cycle key (e.g. `es_generales_2023`, `es_europeas_2024`).
- `source_url` (string): canonical URL (may change; do not use as the only identity key).
- `format_hint` (string): `html|pdf|txt|md` (hint, not a guarantee).
- `language` (string): `es|ca|eu|gl|...`
- `scope` (string): `nacional` (v1); future: `autonomico|municipal|europeo`.
- `snapshot_date` (string): `YYYY-MM-DD` used for reproducible snapshots.

Recommended/optional columns (v1):
- `kind` (string): `programa|resumen|faq|propuestas` (used in identity key).
- `local_path` (string): repo-relative path for reproducible `--from-file` ingestion.
- `notes` (string): free-form operational notes (not used for identity).

## Identity Key Policy (Deterministic)
The `source_records` identity must be stable and **not depend on URLs**.

v1 identity tuple:
- `(party_id, election_cycle, kind)`

v1 `source_record_id` (string):
- `programas_partidos:{election_cycle}:{party_id}:{kind}`

Rules:
- `kind` MUST be present; if unknown, set `kind=programa`.
- If a party publishes multiple documents per cycle, `kind` must disambiguate (or add a stable `doc_id` column later).

## Dedupe Policy
- Primary dedupe is by `source_id + source_record_id` (enforced by `source_records` unique constraint).
- Content changes over time are tracked by:
  - `content_sha256` (on `source_records` and `text_documents`)
  - storing `snapshot_date` so multiple snapshots can coexist deterministically.

## Storage + Traceability
For each manifest row:
- Create a `source_records` row with:
  - `raw_payload`: JSON of the normalized manifest row (plus any extraction metadata)
  - `content_sha256`: sha256 of the fetched document bytes (or extracted text, if that is the canonical raw payload for a given format)
- Create a `text_documents` row linked by `source_record_pk`:
  - `source_url` from manifest
  - `raw_path` pointing to the stored bytes (under `etl/data/raw/` or equivalent)
  - `text_excerpt` and `text_chars`

## Strict-Network Behavior (v1)
- `--from-file` is the default reproducible mode and MUST work from the sample manifest.
- `--strict-network`:
  - MUST fail fast if a URL fetch fails (403/404/timeout) for any manifest row.
  - MUST record failure evidence in logs (and never claim DONE when blocked).

## Known Modeling Issue (Open)
The existing `topic_evidence` schema requires `person_id` (NOT NULL). Party programs are party-level statements.

v1 plan (to be implemented in code tasks):
- Prefer an additive, explicit party-level model (new tables/columns) rather than faking a person.
- If we temporarily map programs to a proxy `person_id`, it must be documented as a stopgap and be reversible.

This contract does **not** force a modeling choice, but requires identity + traceability to be correct regardless.

## Acceptance Checks
- `test -f docs/etl/sprints/AI-OPS-19/reports/programas-source-contract.md`
- `test -f etl/data/raw/samples/programas_partidos_sample.csv`
- Manifest contains required columns and at least 2 rows.
