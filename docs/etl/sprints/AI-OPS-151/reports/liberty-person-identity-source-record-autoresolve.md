# AI-OPS-151 - Liberty person identity source-record auto-resolve

## Goal
Reduce manual friction in row `103` by auto-resolving `source_record_pk` when review decisions provide `source_id + source_record_id`.

## Delivered
- Extended `scripts/apply_liberty_person_identity_official_upgrade_reviews.py`:
  - New optional `--db` input.
  - Loads lookup from `source_records`.
  - Auto-fills `source_record_pk` for approved `official_*` mappings when missing.
  - Adds counters:
    - `source_record_pk_auto_resolved`
    - `source_record_pk_auto_resolve_missed`
    - `source_record_pk_auto_resolve_skipped_missing_keys`
  - Emits `source_record_lookup` meta in JSON output.
- Updated `justfile`:
  - `parl-apply-liberty-person-identity-official-upgrade-reviews` now passes `--db {{db_path}}`.
- Extended tests:
  - `tests/test_apply_liberty_person_identity_official_upgrade_reviews.py` now covers auto-resolve behavior.

## Contract results (`20260223T232954Z`)
- Targeted tests: `Ran 4`, `OK`.
- `Derechos` suite: `Ran 93`, `OK (skipped=1)`.
- Dry-run contract with real DB lookup:
  - `source_record_lookup.loaded=true`
  - `source_record_lookup.rows_total=173070`
  - `source_record_pk_auto_resolved=1`
  - `source_record_pk_auto_resolve_missed=0`
  - `validation.valid=true`

## Evidence
- `docs/etl/sprints/AI-OPS-151/evidence/liberty_person_identity_official_upgrade_apply_autoresolve_20260223T232954Z.json`
- `docs/etl/sprints/AI-OPS-151/evidence/liberty_person_identity_official_upgrade_apply_autoresolve_stdout_20260223T232954Z.json`
- `docs/etl/sprints/AI-OPS-151/evidence/liberty_person_identity_official_upgrade_source_record_autoresolve_contract_summary_20260223T232954Z.json`
- `docs/etl/sprints/AI-OPS-151/evidence/unittest_liberty_person_identity_official_upgrade_review_apply_20260223T232954Z.txt`
- `docs/etl/sprints/AI-OPS-151/evidence/just_parl_test_liberty_restrictions_20260223T232954Z.txt`
- `docs/etl/sprints/AI-OPS-151/exports/liberty_person_identity_official_upgrade_review_decisions_autoresolve_20260223T232954Z.csv`
