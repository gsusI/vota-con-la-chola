# AI-OPS-29 Prompt Pack

Objective:
- Stabilize `programas_partidos` reruns so review queue state remains closed after adjudication.

Acceptance gates:
- Regression fixed in real DB rerun (`review_pending=0` remains after rerun).
- Deterministic status reporter shipped for declared sources.
- Tests cover evidence-id stability and review-state persistence.
- Tracker + README updated with reproducible command path.

Status update (2026-02-22):
- `scripts/report_declared_source_status.py` shipped.
- `just` now supports source-parameterized declared workflow (`DECLARED_SOURCE_ID`) and `parl-programas-pipeline`.
- `programas` ingest now preserves evidence IDs by natural key across reruns.
- Real DB rerun confirmed queue stability (`review_pending=0`, `review_ignored=6`).
- Evidence/report:
  - `docs/etl/sprints/AI-OPS-29/reports/programas-review-stability-20260222.md`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_before_rerun_20260222T192302Z.json`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_pipeline_rerun_20260222T192302Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_after_rerun_20260222T192302Z.json`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_postcheck_20260222T192302Z.json`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_regression_tests_20260222T192426Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_and_quality_tests_20260222T192616Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/tracker_gate_20260222T192649Z.txt`
