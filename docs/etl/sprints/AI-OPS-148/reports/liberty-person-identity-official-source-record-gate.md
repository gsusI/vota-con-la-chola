# AI-OPS-148 - Liberty identity official source-record gate

## Context (where we are now)
- AI-OPS-146/147 already enforce that `official_*` aliases have quote-level evidence and measurable share.
- Remaining gap: an `official_*` alias could still be detached from reproducible DB lineage (`source_records`), reducing auditability.

## Goal (where we are going)
- Add a traceability contract for `official_*` aliases linked to `source_record_pk`.
- Keep parity between personal scoring and identity queue lanes, and make the import lane expose resolution/miss counters.

## Shipped in this slice
1. Schema + compatibility
- `person_name_aliases` adds `source_record_pk INTEGER REFERENCES source_records(source_record_pk)`.
- Added index `idx_person_name_aliases_source_record_pk`.
- `ensure_schema_compat()` backfills the new column on existing DBs.

2. Identity seed validation/import hardening
- `validate_liberty_person_identity_resolution_seed.py`:
  - validates optional `source_record_pk` format,
  - requires `source_id` when `source_record_id` is provided,
  - emits warning when official mappings omit source-record reference.
- `import_liberty_person_identity_resolution_seed.py`:
  - accepts `source_record_pk` or (`source_id` + `source_record_id`) and resolves to `source_record_pk`,
  - persists `source_record_pk` in aliases,
  - exposes counters:
    - `official_mappings_with_source_record_total`
    - `official_mappings_missing_source_record_total`
    - `source_record_pk_resolved_total`
    - `source_record_pk_unresolved_total`
  - reports totals:
    - `official_aliases_with_source_record_total`
    - `official_aliases_missing_source_record_total`

3. Personal scoring + identity queue gates
- `report_liberty_personal_accountability_scores.py` and `report_liberty_person_identity_resolution_queue.py` add:
  - totals:
    - `official_alias_rows_with_source_record_total`
    - `official_alias_rows_missing_source_record_total`
  - coverage:
    - `official_alias_source_record_coverage_pct`
  - check:
    - `official_alias_source_record_gate`
  - CLI args:
    - `--official-alias-source-record-min-pct`
    - `--min-official-alias-rows-for-source-record-gate`

4. `justfile` propagation
- New personal vars:
  - `LIBERTY_PERSONAL_OFFICIAL_ALIAS_SOURCE_RECORD_MIN_PCT`
  - `LIBERTY_PERSONAL_MIN_OFFICIAL_ALIAS_ROWS_FOR_SOURCE_RECORD_GATE`
- New queue vars:
  - `LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_SOURCE_RECORD_MIN_PCT`
  - `LIBERTY_PERSON_IDENTITY_MIN_OFFICIAL_ALIAS_ROWS_FOR_SOURCE_RECORD_GATE`
- Wired to `parl-report/check-liberty-personal-accountability-*` and `parl-report/check-liberty-person-identity-resolution-*`.

## Reproducible execution and evidence
- Run timestamp: `20260223T230526Z`
- Main DB: `tmp/liberty_person_identity_source_record_20260223T230526Z.db`
- Contract DB: `tmp/liberty_person_identity_source_record_contract_20260223T230526Z.db`

Key evidence:
- Pass path:
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_personal_accountability_scores_20260223T230526Z.json`
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_person_identity_resolution_queue_20260223T230526Z.json`
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_person_identity_import_20260223T230526Z.json`
- Strict fail-path (official alias without source-record link):
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_person_identity_import_official_no_source_record_20260223T230526Z.json`
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_personal_accountability_official_alias_source_record_fail_20260223T230526Z.json`
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_person_identity_resolution_queue_official_alias_source_record_fail_20260223T230526Z.json`
  - `docs/etl/sprints/AI-OPS-148/evidence/liberty_person_identity_official_source_record_contract_summary_20260223T230526Z.json`

Contract highlights:
- Pass path (manual-only seed):
  - personal/queue `status=ok`,
  - `official_alias_rows_total=0`,
  - `official_alias_source_record_coverage_pct=1.0`,
  - `official_alias_source_record_gate=true`.
- Strict fail-path:
  - with one `official_*` alias lacking `source_record_pk`, both lanes degrade,
  - `official_alias_rows_total=1`,
  - `official_alias_rows_with_source_record_total=0`,
  - `official_alias_source_record_coverage_pct=0.0`,
  - `official_alias_source_record_gate=false`,
  - `--enforce-gate` exits with `2` in personal and queue.

## Tests
- Focused suite:
  - `Ran 28`, `OK`
  - `docs/etl/sprints/AI-OPS-148/evidence/unittest_liberty_person_identity_source_record_contract_20260223T230526Z.txt`
- Full rights suite:
  - `Ran 89`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-148/evidence/just_parl_test_liberty_restrictions_20260223T230526Z.txt`

## Next (what is next)
- Start replacing `manual_seed` aliases with `official_*` mappings that include both quote-level evidence and `source_record_pk`.
- Raise source-record thresholds (`personal` + `queue`) from observability to enforcement as official mappings are onboarded.
