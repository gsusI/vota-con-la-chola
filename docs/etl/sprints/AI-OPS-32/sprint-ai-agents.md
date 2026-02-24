# AI-OPS-32 Prompt Pack

Objective:
- Make declared/programas quality enforcement robust when vote KPIs are out-of-scope for the run.

Acceptance gates:
- `quality-report` has `--skip-vote-gate`.
- Declared `just` targets are decoupled by default (`DECLARED_QUALITY_SKIP_VOTE_GATE=1`).
- Tests cover decoupling behavior end-to-end in CLI.
- Real enforce run with `just` produces `declared.gate.passed=true` evidence.

Status update (2026-02-22):
- `etl/parlamentario_es/cli.py`:
  - added `--skip-vote-gate`
  - `--enforce-gate` now ignores base vote-gate when that flag is active
- `justfile`:
  - new var `DECLARED_QUALITY_SKIP_VOTE_GATE` (default `1`)
  - `parl-quality-report-declared` and `parl-quality-report-declared-enforce` now pass `--skip-vote-gate` when enabled
- tests:
  - new CLI test proves `enforce` fails without skip and passes with skip on declared-only fixture
- evidence:
  - `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.json`
  - `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.txt`
  - `docs/etl/sprints/AI-OPS-32/evidence/declared_skip_vote_gate_tests_20260222T195036Z.txt`
  - `docs/etl/sprints/AI-OPS-32/evidence/tracker_gate_20260222T195041Z.txt`
