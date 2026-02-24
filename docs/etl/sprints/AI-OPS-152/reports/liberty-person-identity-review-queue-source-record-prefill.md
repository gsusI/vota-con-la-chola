# AI-OPS-152 - Liberty person identity review queue source-record prefill

## Goal
Reduce manual work in row `103` by pre-filling `source_record_pk` earlier in the review loop (export stage), not only during apply.

## Delivered
- Extended `scripts/export_liberty_person_identity_official_upgrade_review_queue.py`:
  - Loads optional lookup from `source_records` (`source_id + source_record_id -> source_record_pk`).
  - Prefills `source_record_pk` in review rows when lookup is available.
  - Adds per-row trace column `source_record_pk_lookup_status` with values:
    - `existing`
    - `prefilled_from_db`
    - `lookup_miss`
    - `lookup_not_loaded`
    - `not_applicable`
  - Adds summary counters:
    - `source_record_pk_lookup_keys_total`
    - `source_record_pk_lookup_prefilled_total`
    - `source_record_pk_lookup_miss_total`
  - Publishes `source_record_lookup_rows_total` in payload metadata.
- Extended tests in `tests/test_export_liberty_person_identity_official_upgrade_review_queue.py`:
  - Coverage for baseline behavior.
  - New contract test for DB-like prefill path (`prefilled_from_db`).

## Contract results (`20260223T233847Z`)
- Targeted tests: `Ran 5`, `OK`.
- `Derechos` suite: `Ran 94`, `OK (skipped=1)`.
- Lookup prefill contract (synthetic deterministic fixture):
  - `summary.source_record_pk_lookup_keys_total=1`
  - `summary.source_record_pk_lookup_prefilled_total=1`
  - `summary.source_record_pk_lookup_miss_total=0`
  - `row_assertions.source_record_pk=125908`
  - `row_assertions.source_record_pk_lookup_status=prefilled_from_db`

## Evidence
- `docs/etl/sprints/AI-OPS-152/evidence/liberty_person_identity_official_upgrade_review_queue_source_record_lookup_contract_summary_20260223T233847Z.json`
- `docs/etl/sprints/AI-OPS-152/evidence/unittest_liberty_person_identity_official_upgrade_export_apply_20260223T233847Z.txt`
- `docs/etl/sprints/AI-OPS-152/evidence/just_parl_test_liberty_restrictions_20260223T233847Z.txt`
