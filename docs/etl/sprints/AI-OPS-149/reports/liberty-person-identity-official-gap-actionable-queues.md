# AI-OPS-149 - Liberty person identity official-gap actionable queues

## Goal
Convert `official_*` alias gate failures in row `103` into actionable, reproducible work queues (not only coverage percentages).

## Delivered
- Extended `scripts/report_liberty_person_identity_resolution_queue.py` with two new remediation queues:
  - `official_alias_evidence_upgrade_queue_rows` (`source_url/evidence_date/evidence_quote` missing).
  - `official_alias_source_record_upgrade_queue_rows` (`source_record_pk` missing).
- Added explicit visibility checks:
  - `official_alias_evidence_backlog_visible`
  - `official_alias_source_record_backlog_visible`
- Added queue totals and previews in JSON contract:
  - `official_alias_evidence_upgrade_queue_rows_total`
  - `official_alias_source_record_upgrade_queue_rows_total`
- Added CSV exporters + CLI flags:
  - `--official-alias-evidence-upgrade-csv-out`
  - `--official-alias-source-record-upgrade-csv-out`
- Wired new CSV outputs into `justfile`:
  - `LIBERTY_PERSON_IDENTITY_OFFICIAL_EVIDENCE_UPGRADE_QUEUE_CSV_OUT`
  - `LIBERTY_PERSON_IDENTITY_OFFICIAL_SOURCE_RECORD_UPGRADE_QUEUE_CSV_OUT`
- Updated tests in `tests/test_report_liberty_person_identity_resolution_queue.py`.

## Contract results (`20260223T231638Z`)
- Pass observability run:
  - `status=ok`, `gate_passed=true`
  - `official_alias_rows_total=0`
  - `official_alias_evidence_upgrade_queue_rows_total=0`
  - `official_alias_source_record_upgrade_queue_rows_total=0`
  - backlog visibility checks: `true/true`
- Fail-path (`--enforce-gate`) with one `official_*` alias degraded on evidence + source-record:
  - `status=degraded`, `gate_passed=false`, `exit=2`
  - `official_alias_rows_total=1`
  - `official_alias_rows_missing_evidence_total=1`
  - `official_alias_rows_missing_source_record_total=1`
  - `official_alias_evidence_upgrade_queue_rows_total=1`
  - `official_alias_source_record_upgrade_queue_rows_total=1`
  - backlog visibility checks: `true/true`

## Evidence
- `docs/etl/sprints/AI-OPS-149/evidence/liberty_person_identity_resolution_queue_20260223T231638Z.json`
- `docs/etl/sprints/AI-OPS-149/evidence/liberty_person_identity_resolution_queue_official_gap_fail_20260223T231638Z.json`
- `docs/etl/sprints/AI-OPS-149/evidence/liberty_person_identity_official_gap_queue_contract_summary_20260223T231638Z.json`
- `docs/etl/sprints/AI-OPS-149/evidence/liberty_person_identity_resolution_queue_official_gap_fail_rc_20260223T231638Z.txt`
- `docs/etl/sprints/AI-OPS-149/evidence/unittest_liberty_person_identity_resolution_queue_20260223T231638Z.txt`
- `docs/etl/sprints/AI-OPS-149/evidence/just_parl_test_liberty_restrictions_20260223T231638Z.txt`
- `docs/etl/sprints/AI-OPS-149/exports/liberty_person_identity_official_alias_evidence_upgrade_queue_20260223T231638Z.csv`
- `docs/etl/sprints/AI-OPS-149/exports/liberty_person_identity_official_alias_source_record_upgrade_queue_20260223T231638Z.csv`
