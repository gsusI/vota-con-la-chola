# Programas Declared Quality Gate (AI-OPS-31)

Date:
- 2026-02-22

Objective:
- Make declared/programas review closure and positions coverage enforceable in the canonical quality gate.

Shipped:
- `etl/parlamentario_es/quality.py`
  - Added `DEFAULT_DECLARED_QUALITY_THRESHOLDS`:
    - `topic_evidence_with_nonempty_stance_pct >= 0.99`
    - `review_closed_pct >= 0.95`
    - `declared_positions_coverage_pct >= 0.95`
  - Added `compute_declared_quality_kpis(...)` with per-source + aggregate KPIs.
  - Added `evaluate_declared_quality_gate(...)`.
  - Coverage semantics are conservative and deterministic:
    - `unclear/no_signal` are valid outputs.
    - `declared_positions_coverage_pct` denominator only includes actionable stances (`support/oppose/mixed`).
- `etl/parlamentario_es/cli.py`
  - Added `quality-report --include-declared --declared-source-ids`.
  - Added declared gate enforcement under existing `--enforce-gate`.
- `justfile`
  - Added `parl-quality-report-declared`.
  - Added `parl-quality-report-declared-enforce`.
- Tests:
  - `tests/test_parl_quality.py` (declared KPI/gate coverage)
  - `tests/test_cli_quality_report.py` (CLI include/enforce fail+pass paths)

Validation:
- Unit tests:
  - `python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report -q`
  - result: `Ran 21 tests ... OK`
- Real enforce run:
  - `python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --source-ids congreso_votaciones,senado_votaciones --include-initiatives --initiative-source-ids congreso_iniciativas,senado_iniciativas --include-declared --declared-source-ids programas_partidos --enforce-gate --json-out docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.json`
  - key result:
    - `gate.passed=true`
    - `initiatives.gate.passed=true`
    - `declared.gate.passed=true`
    - declared KPIs (`programas_partidos`):
      - `topic_evidence_total=11`
      - `review_pending=0`
      - `review_closed_pct=1.0`
      - `declared_positions_scope_total=5`
      - `declared_positions_total=5`
      - `declared_positions_coverage_pct=1.0`
- Operational `just` path:
  - `DECLARED_QUALITY_SOURCE_IDS=programas_partidos DECLARED_QUALITY_OUT=docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.json just parl-quality-report-declared-enforce`
  - result: `exit=0` with `declared.gate.passed=true`

Evidence:
- `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.json`
- `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.txt`
- `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.json`
- `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.txt`
- `docs/etl/sprints/AI-OPS-31/evidence/declared_quality_tests_20260222T194349Z.txt`

Outcome:
- Programas declared quality is now protected by an enforceable gate in the same contract used for votaciones/iniciativas quality reporting.
