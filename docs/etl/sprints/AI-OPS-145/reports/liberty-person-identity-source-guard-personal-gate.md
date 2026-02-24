# AI-OPS-145 - Liberty identity source guard + personal manual-share gate

## Context (where we are now)
- AI-OPS-144 added manual-upgrade backlog visibility in queue lane, but personal scoring did not yet expose/enforce manual alias share explicitly.
- Importer prevented `source_kind` downgrade, but a manual replay could still try to retarget alias->person mappings unless guarded at write-time.

## Goal (where we are going)
- Make personal scoring and queue consistent on provenance quality (`manual_seed` share visibility + enforceable gate).
- Prevent silent retarget of aliases anchored by `official_*` mappings when manual seed is replayed.

## Shipped in this slice
1. Import source-guard hardening (`scripts/import_liberty_person_identity_resolution_seed.py`)
- Added write-time guard in `ON CONFLICT`:
  - if existing alias is `official_*` and incoming is `manual_seed`, keep existing `person_id` and `alias`.
- Added counter:
  - `aliases_retarget_downgrade_prevented`
- Existing `aliases_source_kind_downgrade_prevented` stays as provenance guard.

2. Personal scoring parity with queue (`scripts/report_liberty_personal_accountability_scores.py`)
- Added totals:
  - `aliases_total`, `manual_alias_rows_total`, `manual_alias_rows_with_edge_impact_total`, `manual_alias_edges_with_impact_total`, `official_alias_rows_total`
- Added coverage:
  - `manual_alias_share_pct`, `manual_alias_upgrade_edge_impact_pct`
- Added check/gate:
  - `manual_alias_share_gate`
- Added CLI args:
  - `--manual-alias-share-max`
  - `--min-alias-rows-for-manual-share-gate`

3. `justfile` wiring for personal lane
- New vars:
  - `LIBERTY_PERSONAL_MANUAL_ALIAS_SHARE_MAX`
  - `LIBERTY_PERSONAL_MIN_ALIAS_ROWS_FOR_MANUAL_SHARE_GATE`
- Propagated to:
  - `parl-report-liberty-personal-accountability-scores`
  - `parl-check-liberty-personal-accountability-gate`

4. Tests
- Import contract tests now cover retarget prevention under manual replay over official alias.
- Personal scoring tests now cover manual-share totals/coverage and strict fail-path.

## Reproducible execution and evidence
- Run timestamp: `20260223T223309Z`
- Main DB: `tmp/liberty_person_identity_source_guard_20260223T223309Z.db`
- Contract DB: `tmp/liberty_person_identity_source_guard_contract_20260223T223309Z.db`

Key evidence:
- Main run outputs:
  - `docs/etl/sprints/AI-OPS-145/evidence/liberty_person_identity_import_20260223T223309Z.json`
  - `docs/etl/sprints/AI-OPS-145/evidence/liberty_personal_accountability_scores_20260223T223309Z.json`
  - `docs/etl/sprints/AI-OPS-145/evidence/liberty_person_identity_resolution_queue_20260223T223309Z.json`
- Source-guard contract (official alias survives manual retarget replay):
  - `docs/etl/sprints/AI-OPS-145/evidence/liberty_person_identity_downgrade_retarget_contract_20260223T223309Z.json`
- Fail-path RC summary:
  - `docs/etl/sprints/AI-OPS-145/evidence/liberty_person_identity_source_guard_contract_20260223T223309Z.json`

Contract highlights:
- Personal pass path:
  - `indirect_identity_resolution_pct=1.0`
  - `manual_alias_share_pct=1.0`
  - `manual_alias_share_gate=true` (observability default `max=1.0`)
- Strict fail-paths:
  - personal non-manual gate fail `exit=2`
  - personal manual-share gate fail (`max=0.0`) `exit=2`
  - queue non-manual/manual-share gate fail `exit=2`
- Retarget prevention proof:
  - `manual_retarget_replay.counts.aliases_retarget_downgrade_prevented=1`
  - alias remains `source_kind=official_nombramiento`
  - alias remains attached to `person_full_name=Alicia Martin Gomez`

## Tests
- Focused suite:
  - `Ran 20`, `OK`
  - `docs/etl/sprints/AI-OPS-145/evidence/unittest_liberty_person_identity_source_guard_contract_20260223T223309Z.txt`
- Full rights suite:
  - `Ran 81`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-145/evidence/just_parl_test_liberty_restrictions_20260223T223309Z.txt`

## Next (what is next)
- Start replacing manual aliases by official evidence in priority order from manual-upgrade queue (`edges_total` desc).
- Increase strict thresholds (`manual_alias_share_max` down, `non_manual_alias_resolution_min_pct` up) as official share grows.
