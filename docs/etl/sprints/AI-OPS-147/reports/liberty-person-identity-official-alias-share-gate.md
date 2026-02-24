# AI-OPS-147 - Liberty identity official-alias share gate

## Context (where we are now)
- AI-OPS-146 added evidence completeness gates for aliases already marked `official_*`.
- Personal and queue lanes could still stay green with `official_alias_rows_total=0` (all aliases still `manual_seed`), so migration progress was observable but not enforceable.

## Goal (where we are going)
- Add an explicit share gate so the rollout from `manual_seed` to `official_*` can be enforced with thresholds, not only tracked.
- Keep parity between personal scoring and identity queue lanes.

## Shipped in this slice
1. Personal scoring gate extension (`scripts/report_liberty_personal_accountability_scores.py`)
- Added coverage:
  - `official_alias_share_pct`
- Added check:
  - `official_alias_share_gate`
- Added args:
  - `--official-alias-share-min-pct`
  - `--min-alias-rows-for-official-share-gate`

2. Identity queue gate extension (`scripts/report_liberty_person_identity_resolution_queue.py`)
- Added coverage:
  - `official_alias_share_pct`
- Added check:
  - `official_alias_share_gate`
- Added args:
  - `--official-alias-share-min-pct`
  - `--min-alias-rows-for-official-share-gate`

3. `justfile` threshold propagation
- New personal vars:
  - `LIBERTY_PERSONAL_OFFICIAL_ALIAS_SHARE_MIN_PCT`
  - `LIBERTY_PERSONAL_MIN_ALIAS_ROWS_FOR_OFFICIAL_SHARE_GATE`
- New queue vars:
  - `LIBERTY_PERSON_IDENTITY_OFFICIAL_ALIAS_SHARE_MIN_PCT`
  - `LIBERTY_PERSON_IDENTITY_MIN_ALIAS_ROWS_FOR_OFFICIAL_SHARE_GATE`
- Wired into:
  - `parl-report/check-liberty-personal-accountability-*`
  - `parl-report/check-liberty-person-identity-resolution-*`

4. Tests
- Added strict fail-path tests in both lanes for official-alias share.
- Existing pass-path tests now assert `official_alias_share_pct` and `official_alias_share_gate`.

## Reproducible execution and evidence
- Run timestamp: `20260223T225159Z`
- Main DB: `tmp/liberty_person_identity_official_share_20260223T225159Z.db`
- Contract DB: `tmp/liberty_person_identity_official_share_contract_20260223T225159Z.db`

Key evidence:
- Main lane outputs:
  - `docs/etl/sprints/AI-OPS-147/evidence/liberty_personal_accountability_scores_20260223T225159Z.json`
  - `docs/etl/sprints/AI-OPS-147/evidence/liberty_person_identity_resolution_queue_20260223T225159Z.json`
- Strict fail-path outputs:
  - `docs/etl/sprints/AI-OPS-147/evidence/liberty_personal_accountability_official_alias_share_fail_20260223T225159Z.json`
  - `docs/etl/sprints/AI-OPS-147/evidence/liberty_person_identity_resolution_queue_official_alias_share_fail_20260223T225159Z.json`
  - `docs/etl/sprints/AI-OPS-147/evidence/liberty_person_identity_official_share_contract_summary_20260223T225159Z.json`

Contract highlights:
- Pass path:
  - personal `status=ok`, `official_alias_share_pct=0.0`, `official_alias_share_gate=true` (observability default threshold `0.0`)
  - queue `status=ok`, `official_alias_share_pct=0.0`, `official_alias_share_gate=true` (observability default threshold `0.0`)
- Strict fail-path:
  - with `official_alias_share_min_pct=0.1` and `min_alias_rows_for_official_share_gate=1`, both lanes degrade and return `exit=2`.

## Tests
- Focused suite:
  - `Ran 17`, `OK`
  - `docs/etl/sprints/AI-OPS-147/evidence/unittest_liberty_person_identity_official_share_contract_20260223T225159Z.txt`
- Full rights suite:
  - `Ran 85`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-147/evidence/just_parl_test_liberty_restrictions_20260223T225159Z.txt`

## Next (what is next)
- Start tightening official-share thresholds over time (personal + queue) as aliases are migrated to `official_*`.
- Keep evidence gate and share gate together so official coverage means both presence and traceability.
