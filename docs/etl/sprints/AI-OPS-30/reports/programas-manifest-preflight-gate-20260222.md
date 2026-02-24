# Programas Manifest Preflight Gate (AI-OPS-30)

Date:
- 2026-02-22

Objective:
- Block bad `programas_partidos` manifests before ingest/backfill.

Shipped:
- `scripts/validate_programas_manifest.py`
  - validates required columns, row-level required fields, URL/path requirements, date format, format hints, and duplicate `(election_cycle, party_id, kind)` keys.
  - deterministic JSON summary with `valid`, counts, and row-level errors.
  - exit code contract: `0` valid, `1` invalid.
- `tests/test_validate_programas_manifest.py`
  - valid manifest case
  - duplicate key + missing local file case
  - malformed row case (`party_id`, URL, date, format_hint, missing source/local)
- `justfile`
  - new target: `parl-validate-programas-manifest`
  - `parl-programas-pipeline` now runs validation first.
- extended regression sweep:
  - `python3 -m unittest tests.test_validate_programas_manifest tests.test_parl_programas_partidos tests.test_report_declared_source_status tests.test_parl_declared_stance tests.test_parl_quality tests.test_cli_quality_report -q`
  - result: `Ran 27 tests ... OK`

Validation:
- sample preflight:
  - `PROGRAMAS_MANIFEST=etl/data/raw/samples/programas_partidos_sample.csv PROGRAMAS_MANIFEST_VALIDATE_OUT=docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_20260222T193103Z.json just parl-validate-programas-manifest`
  - result: `valid=true`, `rows_total=3`, `rows_valid=3`, `errors_count=0`
- full pipeline with preflight:
  - `SNAPSHOT_DATE=2026-02-17 PROGRAMAS_MANIFEST=etl/data/raw/samples/programas_partidos_sample.csv PROGRAMAS_MANIFEST_VALIDATE_OUT=docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_pipeline_20260222T193242Z.json PROGRAMAS_STATUS_OUT=docs/etl/sprints/AI-OPS-30/evidence/programas_status_pipeline_20260222T193242Z.json just parl-programas-pipeline`
  - result: preflight `valid=true`; post-pipeline `review_pending=0`, `declared_positions_total=5`
  - operational note: one initial attempt failed due local Docker snapshot cache error (`parent snapshot ... does not exist`), then immediate retry succeeded with same inputs.

Evidence:
- `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_20260222T193103Z.json`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_gate_tests_20260222T193141Z.txt`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_manifest_validate_pipeline_20260222T193242Z.json`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_pipeline_with_validate_20260222T193242Z.txt`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_pipeline_with_validate_20260222T193147Z.txt`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_status_pipeline_20260222T193242Z.json`
- `docs/etl/sprints/AI-OPS-30/evidence/programas_preflight_and_quality_tests_20260222T193437Z.txt`

Outcome:
- `programas_partidos` now fails fast on invalid manifests and keeps the stable rerun behavior delivered in AI-OPS-29.
