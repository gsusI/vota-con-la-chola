# Programas Review Stability (AI-OPS-29)

Date:
- 2026-02-22

Objective:
- Prevent `programas_partidos` reruns from reopening previously adjudicated review rows.

Problem observed:
- Re-running `ingest programas_partidos` + `backfill-declared-stance` recreated `topic_evidence` rows and reopened queue debt (`review_pending=6`) despite prior manual closeout.

Root cause:
- `_ingest_programas_partidos` deleted cycle-scoped `topic_evidence` rows before reinserting them.
- `topic_evidence_reviews` references `evidence_id`; deleting evidence triggered review-row churn and lost status continuity.

Shipped:
- `etl/parlamentario_es/pipeline.py`
  - `programas_partidos` ingest now preserves stable `evidence_id` when natural keys are unchanged:
    - key: `(source_record_pk, topic_id, evidence_type)`
  - replaced destructive cycle-wide delete with keyed upsert/update + stale-row cleanup.
  - duplicate key rows are deduped deterministically (`ORDER BY evidence_id`, keep first).
- `justfile`
  - declared-evidence ops are now source-parameterized via `DECLARED_SOURCE_ID`.
  - new targets:
    - `parl-programas-pipeline`
    - `parl-programas-status`
    - `parl-report-declared-source-status`
- New script:
  - `scripts/report_declared_source_status.py`
  - deterministic JSON status for declared sources (`source_records`, `text_documents`, evidence stance split, review split, declared positions split/date, party proxy count).
- Tests:
  - `tests/test_report_declared_source_status.py` (new)
  - `tests/test_parl_programas_partidos.py` extended with regression checks:
    - stable `evidence_id` across reingest
    - ignored review decisions stay ignored after rerun

Validation:
- Unit tests:
  - `python3 -m unittest tests.test_parl_programas_partidos tests.test_report_declared_source_status -q`
  - result: `Ran 3 tests ... OK`
  - extended regression sweep:
    - `python3 -m unittest tests.test_parl_programas_partidos tests.test_report_declared_source_status tests.test_parl_declared_stance tests.test_parl_quality tests.test_cli_quality_report -q`
    - result: `Ran 24 tests ... OK`
- Real DB rerun (`etl/data/staging/politicos-es.db`):
  1. close pending queue to ignored (`review_pending -> 0`)
  2. rerun `just parl-programas-pipeline`
  3. verify status remains closed
- Result on rerun:
  - `review_pending=0`
  - `review_ignored=6`
  - `declared_positions_total=5`
  - `declared_positions_latest_as_of_date=2026-02-17`

Evidence:
- Baseline + rerun:
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_before_rerun_20260222T192302Z.json`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_pipeline_rerun_20260222T192302Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_after_rerun_20260222T192302Z.json`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_postcheck_20260222T192302Z.json`
- Initial pipeline/status artifacts:
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_pipeline_run_20260222T191945Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_status_post_pipeline_20260222T191945Z.json`
- Test evidence:
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_regression_tests_20260222T192426Z.txt`
  - `docs/etl/sprints/AI-OPS-29/evidence/programas_and_quality_tests_20260222T192616Z.txt`

Outcome:
- `programas_partidos` reruns are now operationally stable for review workflow: manual decisions are preserved across ingest/backfill reruns instead of being reintroduced as pending debt.
