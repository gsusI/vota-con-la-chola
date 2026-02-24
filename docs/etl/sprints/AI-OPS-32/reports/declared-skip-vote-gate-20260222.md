# Declared Quality Enforce Decoupling (AI-OPS-32)

Date:
- 2026-02-22

Objective:
- Avoid false failures in declared-only quality enforcement caused by unrelated vote gate state.

Shipped:
- `etl/parlamentario_es/cli.py`
  - Added `--skip-vote-gate` to `quality-report`.
  - Enforce semantics now:
    - `--enforce-gate` checks base vote gate unless `--skip-vote-gate` is present.
    - initiative and declared gates remain enforced when included.
- `justfile`
  - Added `DECLARED_QUALITY_SKIP_VOTE_GATE` (default `1`).
  - `parl-quality-report-declared` and `parl-quality-report-declared-enforce` now include `--skip-vote-gate` by default.
- `tests/test_cli_quality_report.py`
  - Added explicit decoupling test:
    - fails without skip when vote gate is intentionally red and declared gate is green
    - passes with skip under same fixture

Validation:
- Tests:
  - `python3 -m unittest tests.test_cli_quality_report tests.test_parl_quality -q`
  - result: `Ran 22 tests ... OK`
- Real `just` enforce path:
  - `DECLARED_QUALITY_SOURCE_IDS=programas_partidos DECLARED_QUALITY_SKIP_VOTE_GATE=1 DECLARED_QUALITY_OUT=docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.json just parl-quality-report-declared-enforce`
  - key result:
    - `declared.gate.passed=true`
    - `review_pending=0`
    - `declared_positions_coverage_pct=1.0`

Evidence:
- `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.json`
- `docs/etl/sprints/AI-OPS-32/evidence/quality_declared_gate_skip_vote_enforce_20260222T194957Z.txt`
- `docs/etl/sprints/AI-OPS-32/evidence/declared_skip_vote_gate_tests_20260222T195036Z.txt`
- `docs/etl/sprints/AI-OPS-32/evidence/tracker_gate_20260222T195041Z.txt`

Outcome:
- Declared/programas operational quality checks are now resilient and can be enforced independently in CI/cron/manual loops.
