# AI-OPS-31 Kickoff

Date:
- 2026-02-22

Objective:
- Add a declared-source quality gate to the canonical `quality-report` contract and operationalize it for `programas_partidos`.

Why now:
- Programas pipeline is stable and has manifest preflight, but review-closure/position-coverage checks were not part of the canonical quality gate.
- Need one enforceable, machine-readable gate to avoid silent regressions in declared coverage.

Primary lane (controllable):
- Quality core + CLI + `just` wiring + tests + real evidence run.

Acceptance gates:
- `etl/parlamentario_es/quality.py` exposes declared KPIs + gate evaluator.
- `quality-report` supports `--include-declared` and `--declared-source-ids`.
- `just` has reproducible declared-quality report/enforce commands.
- Real enforce run on `etl/data/staging/politicos-es.db` passes with `programas_partidos` (`review_pending=0`, `declared_positions_coverage_pct=1.0`).
