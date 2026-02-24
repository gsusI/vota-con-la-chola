# AI-OPS-30 Prompt Pack

Objective:
- Enforce deterministic manifest preflight for `programas_partidos` and keep rerun stability intact.

Acceptance gates:
- Manifest validator exists and is tested.
- `just parl-programas-pipeline` includes preflight validation step.
- Real DB run emits validation+status artifacts with `valid=true` and `review_pending=0`.
- Tracker/README updated with canonical command path.

Status update (2026-02-22):
- `scripts/validate_programas_manifest.py` shipped.
- `just parl-validate-programas-manifest` added and wired into `parl-programas-pipeline`.
- Regression tests green:
  - `tests.test_validate_programas_manifest`
  - `tests.test_parl_programas_partidos`
  - `tests.test_report_declared_source_status`
- Real preflight evidence (`sample manifest`):
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_20260222T193103Z.json`
- Real pipeline with preflight evidence:
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_pipeline_20260222T193242Z.json`
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_pipeline_with_validate_20260222T193242Z.txt`
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_status_pipeline_20260222T193242Z.json`
- Tracker integrity evidence:
  - `docs/etl/sprints/AI-OPS-30/evidence/tracker_gate_20260222T193502Z.txt`
- Test evidence:
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_gate_tests_20260222T193141Z.txt`
  - `docs/etl/sprints/AI-OPS-30/evidence/programas_preflight_and_quality_tests_20260222T193437Z.txt`
