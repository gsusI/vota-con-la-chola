# AI-OPS-123 - Liberty Coverage Refresh Heartbeat

Date: 2026-02-23

## Scope

Next TODO batch delivered in active `Derechos` focus:

- Add a reproducible periodic refresh routine for liberty coverage/status KPIs.
- Make the routine auditable over time (append-only heartbeat + strict window check).
- Wire the routine into `just` and CI so it is not manual-only.

## What Shipped

- New scripts:
  - `scripts/report_liberty_restrictions_status_heartbeat.py`
  - `scripts/report_liberty_restrictions_status_heartbeat_window.py`
- New tests:
  - `tests/test_report_liberty_restrictions_status_heartbeat.py`
  - `tests/test_report_liberty_restrictions_status_heartbeat_window.py`
- `justfile` wiring:
  - New vars for heartbeat paths/thresholds.
  - New targets:
    - `parl-report-liberty-restrictions-status-heartbeat`
    - `parl-check-liberty-restrictions-status-heartbeat-window`
  - `parl-liberty-restrictions-pipeline` now runs the new heartbeat + window steps after status reporting.
  - `parl-test-liberty-restrictions` now includes both new test files.
- CI integration:
  - `liberty-focus-gate-contract` in `.github/workflows/etl-tracker-gate.yml` now runs:
    - liberty-focus gate unit tests including heartbeat/window tests,
    - heartbeat append from gate output,
    - strict heartbeat-window check,
    - artifact upload including heartbeat/window files.

## Evidence

- Unit tests (new scripts):
  - `docs/etl/sprints/AI-OPS-123/evidence/unittest_liberty_restrictions_heartbeat_20260223T185829Z.txt`
  - Result: `Ran 6 tests ... OK`.
- Full liberty suite:
  - `docs/etl/sprints/AI-OPS-123/evidence/just_parl_test_liberty_restrictions_20260223T185829Z.txt`
  - Result: `Ran 35 tests ... OK`.
- Status baseline (pass):
  - `docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_pass_20260223T185829Z.json`
  - Result: `status=ok`, `focus_gate.passed=true`, coverage KPIs at `1.0`.
- Heartbeat pass path:
  - `docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_pass_20260223T185829Z.json`
  - Result: `status=ok`, `appended=true`, `duplicate_detected=false`.
- Window pass path:
  - `docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_window_pass_20260223T185829Z.json`
  - Result: `status=ok`, all window checks `true`.
- Contract fail path (degraded sample in same heartbeat stream):
  - `docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_window_fail_20260223T185829Z.json`
  - `docs/etl/sprints/AI-OPS-123/evidence/liberty_restrictions_status_heartbeat_window_fail_rc_20260223T185829Z.txt`
  - Result: strict fail (`exit=4`) with reasons:
    - `max_focus_gate_failed_exceeded`
    - `max_focus_gate_failed_rate_exceeded`
    - `max_norms_classified_gate_failed_exceeded`
    - `latest_focus_gate_failed`
    - `latest_norms_classified_gate_failed`
- `just` command evidence:
  - `docs/etl/sprints/AI-OPS-123/evidence/just_parl_report_liberty_restrictions_status_heartbeat_20260223T185829Z.txt`
  - `docs/etl/sprints/AI-OPS-123/evidence/just_parl_check_liberty_restrictions_status_heartbeat_window_20260223T185829Z.txt`
  - `docs/etl/sprints/AI-OPS-123/evidence/just_parl_check_liberty_focus_gate_20260223T185829Z.txt`
- Integrity + workflow parse:
  - `docs/etl/sprints/AI-OPS-123/evidence/sqlite_fk_check_20260223T185829Z.txt` (empty)
  - `docs/etl/sprints/AI-OPS-123/evidence/workflow_yaml_parse_20260223T185829Z.txt` (`ok`)

## Where We Are Now

- Liberty coverage/status now has a periodic append-only run history plus a strict trend gate.
- The routine is executable locally and in CI, so regressions in coverage/gate health are machine-detected.

## Where We Are Going

- Extend from seed-only coverage to real periodic ingestion (State/CCAA/municipal) while keeping the same heartbeat contract.
- Tighten thresholds only after representativeness grows beyond current seed baseline.

## Next

- Feed heartbeat from recurring real ingests (not only seed pipelines).
- Add scope-aware policy checks (future) for representativeness by territory/source family.
