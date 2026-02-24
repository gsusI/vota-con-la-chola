# AI-OPS-31 Prompt Pack

Objective:
- Enforce declared-source quality checks (programas lane) through the canonical quality-report pipeline.

Acceptance gates:
- Declared KPI/gate primitives shipped and unit tested.
- CLI quality report exposes declared block and supports enforce mode.
- `just` targets for declared quality report/enforce are available.
- Real DB enforce run succeeds and is captured under sprint evidence.

Status update (2026-02-22):
- Shipped declared quality core:
  - `compute_declared_quality_kpis`
  - `evaluate_declared_quality_gate`
  - defaults in `DEFAULT_DECLARED_QUALITY_THRESHOLDS`
- Shipped CLI wiring:
  - `quality-report --include-declared --declared-source-ids ...`
  - `--enforce-gate` now also fails when `declared.gate.passed=false`.
- Shipped operational commands:
  - `just parl-quality-report-declared`
  - `just parl-quality-report-declared-enforce`
- Validation artifacts:
  - `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.json`
  - `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.txt`
  - `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.json`
  - `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.txt`
  - `docs/etl/sprints/AI-OPS-31/evidence/declared_quality_tests_20260222T194349Z.txt`
