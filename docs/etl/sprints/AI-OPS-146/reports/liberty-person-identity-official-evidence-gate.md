# AI-OPS-146 - Liberty identity official-alias evidence gate

## Context (where we are now)
- AI-OPS-145 aligned manual-share and non-manual provenance gates across personal scoring and identity queue lanes.
- `official_*` aliases were contract-validated at seed/import time, but scoring/queue outputs did not yet enforce evidence completeness when official aliases already existed in DB.

## Goal (where we are going)
- Add an explicit quality gate so every alias marked `official_*` is backed by `source_url`, `evidence_date`, and `evidence_quote` in both lanes.
- Keep current behavior reproducible and strict-failable with dedicated thresholds in `justfile`.

## Shipped in this slice
1. Personal scoring gate hardening (`scripts/report_liberty_personal_accountability_scores.py`)
- Added totals:
  - `official_alias_rows_with_evidence_total`
  - `official_alias_rows_missing_evidence_total`
- Added coverage:
  - `official_alias_evidence_coverage_pct`
- Added check:
  - `official_alias_evidence_gate`
- Added CLI args:
  - `--official-alias-evidence-min-pct`
  - `--min-official-alias-rows-for-evidence-gate`

2. Identity queue gate hardening (`scripts/report_liberty_person_identity_resolution_queue.py`)
- Added totals:
  - `official_alias_rows_with_evidence_total`
  - `official_alias_rows_missing_evidence_total`
- Added coverage:
  - `official_alias_evidence_coverage_pct`
- Added check:
  - `official_alias_evidence_gate`
- Added CLI args:
  - `--official-alias-evidence-min-pct`
  - `--min-official-alias-rows-for-evidence-gate`

3. `justfile` threshold propagation
- New personal vars:
  - `LIBERTY_PERSONAL_OFFICIAL_ALIAS_EVIDENCE_MIN_PCT`
  - `LIBERTY_PERSONAL_MIN_OFFICIAL_ALIAS_ROWS_FOR_EVIDENCE_GATE`
- New queue vars:
  - `LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_EVIDENCE_MIN_PCT`
  - `LIBERTY_PERSON_IDENTITY_MIN_OFFICIAL_ALIAS_ROWS_FOR_EVIDENCE_GATE`
- Wired into:
  - `parl-report/check-liberty-personal-accountability-*`
  - `parl-report/check-liberty-person-identity-resolution-*`

4. Tests
- Added official-evidence fail-path regression tests for both lanes.
- Existing lane tests now assert official-evidence totals/coverage/checks in pass path.

## Reproducible execution and evidence
- Run timestamp: `20260223T224358Z`
- Main DB: `tmp/liberty_person_identity_official_evidence_20260223T224358Z.db`
- Contract DB: `tmp/liberty_person_identity_official_evidence_contract_20260223T224358Z.db`

Key evidence:
- Main run outputs:
  - `docs/etl/sprints/AI-OPS-146/evidence/liberty_person_identity_import_20260223T224358Z.json`
  - `docs/etl/sprints/AI-OPS-146/evidence/liberty_personal_accountability_scores_20260223T224358Z.json`
  - `docs/etl/sprints/AI-OPS-146/evidence/liberty_person_identity_resolution_queue_20260223T224358Z.json`
- Official-alias drift contract:
  - `docs/etl/sprints/AI-OPS-146/evidence/liberty_person_identity_official_alias_evidence_contract_20260223T224358Z.json`
- Fail-path RC matrix:
  - `docs/etl/sprints/AI-OPS-146/evidence/liberty_person_identity_official_evidence_contract_summary_20260223T224358Z.json`

Contract highlights:
- Pass path:
  - personal `status=ok`, `official_alias_evidence_gate=true`
  - queue `status=ok`, `official_alias_evidence_gate=true`
  - current base has `official_alias_rows_total=0` (coverage reported as `1.0` by design for zero-row observability mode)
- Drift contract:
  - before: `official_aliases_total=1`, `official_aliases_with_evidence_total=1`
  - after drift: `official_aliases_total=1`, `official_aliases_with_evidence_total=0`
- Strict fail-paths:
  - personal official-evidence gate fail -> `exit=2`
  - queue official-evidence gate fail -> `exit=2`
  - existing strict fail-paths (non-manual/manual-share) stay enforced (`exit=2`)

## Tests
- Focused suite:
  - `Ran 22`, `OK`
  - `docs/etl/sprints/AI-OPS-146/evidence/unittest_liberty_person_identity_official_evidence_contract_20260223T224358Z.txt`
- Full rights suite:
  - `Ran 83`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-146/evidence/just_parl_test_liberty_restrictions_20260223T224358Z.txt`

## Next (what is next)
- Migrate highest-impact aliases from `manual_seed` to `official_*` using the existing manual-upgrade queue ordering.
- Raise strict thresholds progressively once official aliases appear (`*_OFFICIAL_ALIAS_EVIDENCE_MIN_PCT`, `*_MIN_OFFICIAL_ALIAS_ROWS_FOR_EVIDENCE_GATE`).
