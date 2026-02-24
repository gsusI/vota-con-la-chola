# AI-OPS-122 - Liberty Focus Gate CI Policy

Date: 2026-02-23

## Scope

Next TODO batch delivered in active `Derechos` focus:

- Close row 106 by enforcing the liberty-focus gate as a blocking CI policy.
- Keep enforcement reproducible with a deterministic fixture DB and explicit fail/pass contract.
- Wire evidence artifacts so CI outputs are auditable.

## What Shipped

- Workflow hardening in `.github/workflows/etl-tracker-gate.yml`:
  - New job: `liberty-focus-gate-contract`
  - Steps include:
    - unit test run for `tests.test_report_liberty_restrictions_status`
    - fixture DB bootstrap (`init-db` + sanction/liberty seeds)
    - strict fail-path assertion (`--enforce-gate` + impossible threshold -> exit code `2`)
    - strict pass-path enforcement (`--enforce-gate` with default thresholds)
    - artifact upload (`liberty-focus-gate-contract`)
- Test hardening:
  - `tests/test_report_liberty_restrictions_status.py` adds `test_focus_gate_degrades_with_stricter_threshold` to verify degraded mode when thresholds exceed current coverage.

## Evidence

- Unit tests:
  - `docs/etl/sprints/AI-OPS-122/evidence/unittest_report_liberty_restrictions_status_20260223T184906Z.txt`
  - Result: `Ran 3 tests ... OK`.
- Full liberty restrictions suite:
  - `docs/etl/sprints/AI-OPS-122/evidence/just_parl_test_liberty_restrictions_20260223T184906Z.txt`
  - Result: `Ran 29 tests ... OK`.
- Fixture DB + seed imports:
  - `docs/etl/sprints/AI-OPS-122/evidence/init_db_20260223T184906Z.txt`
  - `docs/etl/sprints/AI-OPS-122/evidence/liberty_focus_seed_import_norms_20260223T184906Z.json`
  - `docs/etl/sprints/AI-OPS-122/evidence/liberty_focus_seed_import_restrictions_20260223T184906Z.json`
- Gate fail-path (contract):
  - `docs/etl/sprints/AI-OPS-122/evidence/liberty_focus_gate_fail_20260223T184906Z.json`
  - `docs/etl/sprints/AI-OPS-122/evidence/liberty_focus_gate_fail_rc_20260223T184906Z.txt`
  - Result: `status=degraded`, `focus_gate.passed=false`, process `exit=2`.
- Gate pass-path (policy):
  - `docs/etl/sprints/AI-OPS-122/evidence/liberty_focus_gate_pass_20260223T184906Z.json`
  - Result: `status=ok`, `focus_gate.passed=true`.
- `just` contract parity:
  - `docs/etl/sprints/AI-OPS-122/evidence/just_parl_check_liberty_focus_gate_20260223T184906Z.txt`
  - `docs/etl/sprints/AI-OPS-122/evidence/just_liberty_focus_gate_20260223T184906Z.json`
- Workflow syntax parse:
  - `docs/etl/sprints/AI-OPS-122/evidence/workflow_yaml_parse_20260223T184906Z.txt`
  - Result: `ok`.

## Where We Are Now

- The liberty-focus gate is no longer best-effort local only; it is now wired as a dedicated CI contract.
- If the gate drops below thresholds, CI fails and blocks merges by default.

## Where We Are Going

- Keep thresholds conservative while coverage is seed-heavy, then tighten as real ingestion grows.
- Add optional scoped policy checks (future) to detect non-`Derechos` lane openings under degraded gate state.

## Next

- Run the new CI job on the next PR/push and archive the first remote artifact bundle.
- Revisit gate thresholds once CCAA/municipal restrictions move from seed to periodic ingestion.
