# AI-OPS-150 - Liberty person identity official-upgrade review/apply loop

## Goal
Close the loop for row `103` by converting identity-upgrade backlogs into a reviewed CSV flow that can be applied reproducibly to the seed.

## Delivered
- Added review-queue exporter:
  - `scripts/export_liberty_person_identity_official_upgrade_review_queue.py`
  - Merges `manual_alias_upgrade_queue_rows`, `official_alias_evidence_upgrade_queue_rows`, and `official_alias_source_record_upgrade_queue_rows`.
  - Exports a single review CSV with decision columns (`decision`, `review_note`).
- Added review apply lane:
  - `scripts/apply_liberty_person_identity_official_upgrade_reviews.py`
  - Applies reviewed decisions to `liberty_person_identity_resolution_seed_v1`.
  - Keeps downgrade guardrail (`official_* -> manual_seed` blocked).
- Added tests:
  - `tests/test_export_liberty_person_identity_official_upgrade_review_queue.py`
  - `tests/test_apply_liberty_person_identity_official_upgrade_reviews.py`
- Added `justfile` recipes:
  - `parl-export-liberty-person-identity-official-upgrade-review-queue`
  - `parl-apply-liberty-person-identity-official-upgrade-reviews`

## Contract results (`20260223T232635Z`)
- Review queue totals:
  - `rows_total=9`
  - `manual_upgrade_rows_total=9`
- Apply round-trip sample:
  - `rows_with_decision=1`
  - `approved_rows=1`
  - `updated_rows=1`
- Post-apply queue delta:
  - `manual_alias_upgrade_queue_rows_total: 9 -> 8`
  - `official_alias_rows_total=1`
  - `official_alias_rows_missing_evidence_total=0`
  - `official_alias_rows_missing_source_record_total=1`

## Evidence
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_official_upgrade_review_queue_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_official_upgrade_apply_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_official_upgrade_review_apply_contract_summary_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_seed_reviewed_validate_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_seed_reviewed_import_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/liberty_person_identity_resolution_queue_after_review_apply_20260223T232635Z.json`
- `docs/etl/sprints/AI-OPS-150/evidence/unittest_liberty_person_identity_official_upgrade_review_apply_20260223T232635Z.txt`
- `docs/etl/sprints/AI-OPS-150/evidence/just_parl_test_liberty_restrictions_20260223T232635Z.txt`
- `docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_official_upgrade_review_queue_20260223T232635Z.csv`
- `docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_official_upgrade_review_decisions_20260223T232635Z.csv`
- `docs/etl/sprints/AI-OPS-150/exports/liberty_person_identity_resolution_seed_reviewed_20260223T232635Z.json`
