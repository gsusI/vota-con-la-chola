# AI-OPS-144 - Liberty identity manual-upgrade backlog gate

## Context (where we are now)
- Row `103` had identity resolution at `100%` but provenance remained mostly `manual_seed`.
- AI-OPS-143 made provenance explicit (`manual_seed` vs `official_*`) but did not yet expose a concrete upgrade backlog lane for replacing manual aliases.

## Goal (where we are going)
- Keep the existing identity-resolution contract while surfacing a reproducible, prioritized backlog to migrate manual aliases to official evidence.
- Prevent provenance regressions on reruns (manual replay should not downgrade prior official provenance).

## Shipped in this slice
1. Import hardening against provenance downgrade
- `scripts/import_liberty_person_identity_resolution_seed.py` now avoids downgrading `source_kind` when an existing alias is `official_*` and the incoming mapping is `manual_seed`.
- New counter: `aliases_source_kind_downgrade_prevented`.

2. Queue lane extended with manual-upgrade backlog
- `scripts/report_liberty_person_identity_resolution_queue.py` now emits:
  - `manual_alias_upgrade_queue_rows` (+ dedicated CSV output)
  - totals: `aliases_total`, `manual_alias_rows_total`, `manual_alias_rows_with_edge_impact_total`, `manual_alias_edges_with_impact_total`, `official_alias_rows_total`, `manual_alias_upgrade_queue_rows_total`
  - coverage: `manual_alias_share_pct`, `manual_alias_upgrade_edge_impact_pct`
  - checks: `manual_alias_upgrade_backlog_visible`, `manual_alias_share_gate`.

3. `justfile` integration
- New queue outputs and thresholds:
  - `LIBERTY_PERSON_IDENTITY_MANUAL_UPGRADE_QUEUE_CSV_OUT`
  - `LIBERTY_PERSON_IDENTITY_MANUAL_ALIAS_SHARE_MAX`
  - `LIBERTY_PERSON_IDENTITY_MIN_ALIAS_ROWS_FOR_MANUAL_SHARE_GATE`
- Wired into `parl-report/check-liberty-person-identity-resolution-gate`.

## Reproducible execution and evidence
- Run timestamp: `20260223T222707Z`
- Temp DB: `tmp/liberty_person_identity_provenance_upgrade_20260223T222707Z.db`

Key evidence:
- Contract summary + fail RCs:
  - `docs/etl/sprints/AI-OPS-144/evidence/liberty_person_identity_provenance_upgrade_contract_20260223T222707Z.json`
- Queue pass-path with manual backlog:
  - `docs/etl/sprints/AI-OPS-144/evidence/liberty_person_identity_resolution_queue_20260223T222707Z.json`
  - `docs/etl/sprints/AI-OPS-144/exports/liberty_person_identity_manual_upgrade_queue_20260223T222707Z.csv`
- Queue manual-share fail-path (`manual_alias_share_max=0.0`):
  - `docs/etl/sprints/AI-OPS-144/evidence/liberty_person_identity_resolution_queue_manual_alias_share_fail_20260223T222707Z.json`
  - `docs/etl/sprints/AI-OPS-144/evidence/just_parl_check_liberty_person_identity_manual_alias_share_fail_rc_20260223T222707Z.txt`
- Personal/queue non-manual fail-paths (`non_manual_alias_min_pct=1.0`):
  - `docs/etl/sprints/AI-OPS-144/evidence/liberty_personal_accountability_non_manual_alias_fail_20260223T222707Z.json`
  - `docs/etl/sprints/AI-OPS-144/evidence/liberty_person_identity_resolution_queue_non_manual_alias_fail_20260223T222707Z.json`
  - `docs/etl/sprints/AI-OPS-144/evidence/just_parl_check_liberty_personal_accountability_non_manual_alias_fail_rc_20260223T222707Z.txt`
  - `docs/etl/sprints/AI-OPS-144/evidence/just_parl_check_liberty_person_identity_non_manual_alias_fail_rc_20260223T222707Z.txt`

Contract summary:
- Pass path: `indirect_identity_resolution_pct=1.0`, `manual_alias_share_pct=1.0`, queue backlog visible (`manual_alias_upgrade_queue_rows_total=9`).
- Strict fail paths: non-manual and manual-share gates return `status=degraded` with `exit=2`.

## Tests
- Focused suite:
  - `Ran 22`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-144/evidence/unittest_liberty_person_identity_provenance_upgrade_contract_20260223T222707Z.txt`
- Full rights suite:
  - `Ran 80`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-144/evidence/just_parl_test_liberty_restrictions_20260223T222707Z.txt`

## Next (what is next)
- Replace high-impact manual aliases with `official_*` evidence first (ordered by `manual_alias_edges_with_impact_total`).
- Keep strict fail-path checks in place while raising non-manual thresholds progressively as official coverage increases.
