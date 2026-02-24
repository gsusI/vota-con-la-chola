# AI-OPS-129 - Liberty Focus Scope Guard CI Policy

Date: 2026-02-23 (UTC)

## Scope

Next TODO batch delivered from `docs/roadmap-tecnico.md` / `docs/etl/e2e-scrape-load-tracker.md`:

- Close the pending `Derechos/Foco operativo` item by adding CI scope checks.
- Detect non-`Derechos` lane openings when `focus_gate` is degraded.
- Keep current global blocking gate (`--enforce-gate`) unchanged as fallback safety.

## What Shipped

- New script: `scripts/report_liberty_focus_scope_guard.py`
  - Inputs: liberty status JSON + changed paths file.
  - Behavior:
    - If `focus_gate` is degraded and changed paths include non-`Derechos` scope, emit `strict_fail_reason=non_rights_changes_under_degraded_focus` and fail in strict mode (`exit=4`).
    - If `focus_gate` is `ok`, do not block non-`Derechos` paths (scope guard is conditional).
  - Supports governance allowlist (`docs/roadmap-tecnico.md`, `docs/etl/e2e-scrape-load-tracker.md`, `justfile`, workflow file).
- New tests: `tests/test_report_liberty_focus_scope_guard.py`.
- `justfile` integration:
  - `parl-report-liberty-focus-scope`
  - `parl-check-liberty-focus-scope`
- CI wiring in `.github/workflows/etl-tracker-gate.yml` (`liberty-focus-gate-contract`):
  - checkout with `fetch-depth: 0` for diff-based changed paths.
  - run new unit tests.
  - build changed paths file from PR/push range.
  - assert scope-guard fail path (degraded focus + non-`Derechos` path -> `exit=4`).
  - enforce scope-guard pass path with real changed paths and `focus_gate` pass JSON.

## Reproducible Execution

```bash
python3 -m unittest \
  tests/test_report_liberty_focus_scope_guard.py \
  tests/test_report_liberty_restrictions_status.py \
  tests/test_report_liberty_restrictions_status_heartbeat.py \
  tests/test_report_liberty_restrictions_status_heartbeat_window.py

just parl-test-liberty-restrictions

# Local strict scope guard (requires status json + changed paths file)
LIBERTY_RESTRICTIONS_STATUS_OUT=<status_json> \
LIBERTY_FOCUS_SCOPE_CHANGED_PATHS=<changed_paths.txt> \
just parl-check-liberty-focus-scope
```

## Results

- Unit batch: `Ran 13 tests` -> `OK`.
- Liberty suite: `Ran 51 tests` -> `OK (skipped=1)`.
- Existing global gate fail-path preserved: `exit=2` with impossible threshold.
- New scope guard fail-path works: `exit=4` when degraded focus + non-`Derechos` change.
- New scope guard pass-path works: `status=ok` under `focus_gate` pass.
- Workflow YAML parse: `ok`.

## Evidence

- `docs/etl/sprints/AI-OPS-129/evidence/unittest_liberty_focus_scope_guard_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/just_parl_test_liberty_restrictions_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/init_db_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_seed_import_norms_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_seed_import_restrictions_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_gate_fail_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_gate_fail_rc_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_gate_pass_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_changed_paths_ci_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_scope_fail_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_scope_fail_rc_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/liberty_focus_scope_pass_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/just_parl_check_liberty_focus_scope_20260223T201430Z.txt`
- `docs/etl/sprints/AI-OPS-129/evidence/just_liberty_focus_scope_20260223T201430Z.json`
- `docs/etl/sprints/AI-OPS-129/evidence/workflow_yaml_parse_20260223T201430Z.txt`

## Status

DONE: CI now has a scope-aware guard for focus policy, while keeping the existing global gate block as fallback safety.
