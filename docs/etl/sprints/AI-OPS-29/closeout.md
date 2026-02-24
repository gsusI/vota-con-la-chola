# AI-OPS-29 Closeout

Status:
- `PASS`

Date:
- 2026-02-22

Objective result:
- `programas_partidos` rerun stability shipped: review adjudication persists across ingest/backfill reruns.

Gate adjudication:
- `G1` Declared-source status artifact: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-29/evidence/programas_status_20260222T191935Z.json`
- `G2` Rerun queue stability: `PASS`
  - before: `review_pending=0`, `review_ignored=6`
  - after rerun: `review_pending=0`, `review_ignored=6`
  - evidence: `docs/etl/sprints/AI-OPS-29/evidence/programas_status_before_rerun_20260222T192302Z.json`, `docs/etl/sprints/AI-OPS-29/evidence/programas_status_after_rerun_20260222T192302Z.json`
- `G3` Regression tests: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-29/evidence/programas_regression_tests_20260222T192426Z.txt`, `docs/etl/sprints/AI-OPS-29/evidence/programas_and_quality_tests_20260222T192616Z.txt`
- `G4` Tracker integrity after docs/tracker reconciliation: `PASS`
  - evidence: `docs/etl/sprints/AI-OPS-29/evidence/tracker_gate_20260222T192649Z.txt` (`mismatches=0`, `waivers_active=0`, `done_zero_real=0`)

Shipped files:
- `scripts/report_declared_source_status.py`
- `etl/parlamentario_es/pipeline.py`
- `justfile`
- `tests/test_report_declared_source_status.py`
- `tests/test_parl_programas_partidos.py`
- `docs/etl/sprints/AI-OPS-29/reports/programas-review-stability-20260222.md`

Next:
- Expand `programas_partidos` manifest coverage beyond sample set while preserving this rerun-stability contract.
