# AI-OPS-31 Closeout

Status:
- `PASS`

Date:
- 2026-02-22

Objective result:
- Declared-source quality gating is now part of canonical `quality-report` and operationally available for `programas_partidos`.

Gate adjudication:
- `G1` Declared quality primitives + tests: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-31/evidence/declared_quality_tests_20260222T194349Z.txt`
- `G2` CLI include/enforce wiring: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-31/evidence/declared_quality_tests_20260222T194349Z.txt`
- `G3` Real DB enforce run: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.json`, `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_20260222T194325Z.txt`, `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.json`, `docs/etl/sprints/AI-OPS-31/evidence/quality_declared_gate_enforce_just_20260222T194652Z.txt`
  - key result: `declared.gate.passed=true`, `review_pending=0`, `declared_positions_coverage_pct=1.0`
- `G4` Tracker integrity after reconciliation: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-31/evidence/tracker_gate_20260222T194537Z.txt` (`mismatches=0`, `waivers_active=0`, `done_zero_real=0`)

Shipped files:
- `etl/parlamentario_es/quality.py`
- `etl/parlamentario_es/cli.py`
- `justfile`
- `tests/test_parl_quality.py`
- `tests/test_cli_quality_report.py`
- `docs/etl/sprints/AI-OPS-31/reports/programas-declared-quality-gate-20260222.md`

Next:
- Expand declared-gate usage to additional declared sources (`congreso_intervenciones`) once review debt policy is explicitly set for that lane.
