# AI-OPS-153 - Liberty person identity review queue actionability gate

## Goal
Keep row `103` operationally honest by separating actionable review work from likely seed placeholders, and provide a strict check for an empty actionable queue.

## Delivered
- Extended `scripts/export_liberty_person_identity_official_upgrade_review_queue.py`:
  - Adds row-level actionability classification:
    - `actionable`
    - `likely_not_actionable_seed_placeholder`
  - Adds row-level fields:
    - `actionability`
    - `actionability_reason`
  - Adds summary counters:
    - `actionable_rows_total`
    - `likely_not_actionable_rows_total`
  - Adds export controls:
    - `--only-actionable`
    - `--strict-empty-actionable` (exit `4` when actionable backlog is non-empty)
  - Keeps previous lookup metrics (`source_record_pk_lookup_*`) and combines both in one queue payload.
- Extended tests in `tests/test_export_liberty_person_identity_official_upgrade_review_queue.py`:
  - Baseline seed queue now asserts actionability classification/counters.
  - Lookup prefill test now asserts actionability for non-placeholder actor.
- Added `justfile` lanes:
  - `parl-export-liberty-person-identity-official-upgrade-review-queue-actionable`
  - `parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-empty`

## Contract results (`20260223T234425Z`)
- Targeted tests: `Ran 5`, `OK`.
- `Derechos` suite: `Ran 94`, `OK (skipped=1)`.
- Real queue status (staging DB):
  - `rows_total=0`
  - `actionable_rows_total=0`
  - `likely_not_actionable_rows_total=0`
  - Strict actionable-empty check passes (`--only-actionable --strict-empty-actionable`).
- Deterministic actionability fixture contract:
  - `rows_total=2`
  - `actionable_rows_total=1`
  - `likely_not_actionable_rows_total=1`
  - Classification split validated (`Persona real demo` actionable, `Persona seed demo` non-actionable placeholder).

## Evidence
- `docs/etl/sprints/AI-OPS-153/evidence/unittest_liberty_person_identity_official_upgrade_actionability_20260223T234425Z.txt`
- `docs/etl/sprints/AI-OPS-153/evidence/just_parl_test_liberty_restrictions_20260223T234425Z.txt`
- `docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_full_20260223T234425Z.json`
- `docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_full_stdout_20260223T234425Z.json`
- `docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_20260223T234425Z.json`
- `docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_stdout_20260223T234425Z.json`
- `docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionability_contract_summary_20260223T234425Z.json`
