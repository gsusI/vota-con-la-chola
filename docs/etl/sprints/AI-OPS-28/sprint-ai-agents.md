# AI-OPS-28 Prompt Pack

Objective:
- Bootstrap a deterministic offline extraction queue for `text_documents` (PDF/HTML/XML), deduped by checksum, and persist first-pass semantic initiative-doc extractions in SQLite so subagents can process review batches without upstream network dependency.

Acceptance gates:
- Queue exporter script committed with tests.
- `just` shortcuts available for full and missing-only queue exports.
- Real DB evidence artifact generated under `docs/etl/sprints/AI-OPS-28/evidence/` and `exports/`.
- Semantic extraction table + backfill + review queue export shipped with reproducible metrics.
- Review adjudication round-trip (CSV -> SQLite apply) shipped with dry-run evidence.
- Tracker/README updated with reproducible command paths.

Primary lane (controllable):
- Queue generation + documentation + evidence.

Secondary lane (optional):
- No new external blocker probes in this slice.

Latest status update (2026-02-22):
- `heuristic_subject_v2` + `title_hint_strong` shipped and rerun on `etl/data/staging/politicos-es.db`.
- `extraction_needs_review` dropped from `4096` to `592` doc-links (`45.43% -> 6.57%`).
- Remaining review queue: `590` unique docs (`source_record_pk`).
- Batch packet queued for parallel review (deterministic paging):
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0001_of_0003_20260222T151410Z.csv`
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0002_of_0003_20260222T151410Z.csv`
  - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_batch_0003_of_0003_20260222T151410Z.csv`
- Evidence:
  - `docs/etl/sprints/AI-OPS-28/reports/initiative-doc-extractions-title-hint-strong-20260222.md`
  - `docs/etl/sprints/AI-OPS-28/evidence/initdoc_extractions_backfill_title_hint_strong_20260222T151026Z.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_after_title_hint_strong_20260222T151026Z.json`
- Refinement iteration:
  - heuristics + review loop now fully closed for current snapshot:
    - `extraction_needs_review=0` (`0.0%`)
    - review queue rows: `0`
  - canonical quality gate now includes extraction KPIs and passes on real DB:
    - `extraction_coverage_pct=1.0`
    - `extraction_review_closed_pct=1.0`
    - `initiatives.gate.passed=true`
  - enforce/pipeline hardening:
    - `quality-report --include-initiatives --enforce-gate` covered with fail/pass CLI tests
    - `parl-quality-pipeline` now includes initiatives gate by default
  - closeout evidence:
    - `docs/etl/sprints/AI-OPS-28/reports/initiative-doc-extraction-zero-queue-20260222.md`
    - `docs/etl/sprints/AI-OPS-28/evidence/initiative_doc_status_with_extraction_post_singleton_apply_20260222T152337Z.json`
    - `docs/etl/sprints/AI-OPS-28/exports/initdoc_extraction_review_queue_post_singleton_apply_20260222T152337Z.csv`
    - `docs/etl/sprints/AI-OPS-28/reports/initiative-quality-extraction-gate-20260222.md`
    - `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_extraction_kpis_20260222T152859Z.json`
  - HF publish hardening:
    - snapshot packager now propagates quality summary (`votaciones-kpis`) to `manifest.json`, `latest.json` and generated dataset `README.md`
    - validated with real dry-run bundle and preserved evidence under `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_bundle_20260222T184311Z/`
    - real publish executed (`just etl-publish-hf`) and remote verification confirms propagation:
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_run_summary_20260222T184712Z.txt`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_latest_post_publish_20260222T184735Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_manifest_post_publish_20260222T184743Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_readme_post_publish_20260222T184749Z.md`
    - report: `docs/etl/sprints/AI-OPS-28/reports/hf-publish-quality-summary-propagation-20260222.md`
  - HF remote verification gate:
    - shipped `scripts/verify_hf_snapshot_quality.py` + `just etl-verify-hf-quality` (exit-code contract for CI)
    - added `just etl-publish-hf-verify` to chain publish + remote verification
    - validates consistency of `quality_report` across remote `latest.json`, snapshot `manifest.json` and dataset `README.md`
    - evidence:
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_20260222T185350Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_20260222T185350Z.txt`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_ci_local_20260222T190143Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_ci_local_20260222T190143Z.txt`
    - CI job `hf-quality-contract` added to `.github/workflows/etl-tracker-gate.yml` (push `main`) to run HF tests + verifier and upload JSON artifact
    - report: `docs/etl/sprints/AI-OPS-28/reports/hf-remote-quality-verifier-20260222.md`
  - HF publish preflight guard:
    - `scripts/publicar_hf_snapshot.py` now supports `--require-quality-report`
    - `just etl-publish-hf` and `just etl-publish-hf-dry-run` enforce this by default (`HF_REQUIRE_QUALITY_REPORT=1`)
    - successful dry-run evidence:
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_require_quality_20260222T185920Z.txt`
    - regression suite evidence:
      - `docs/etl/sprints/AI-OPS-28/evidence/hf_quality_hardening_tests_20260222T190403Z.txt`
    - report: `docs/etl/sprints/AI-OPS-28/reports/hf-publish-require-quality-guard-20260222.md`
  - Initiative actionable gate tightening:
    - initiative gate now enforces `actionable_doc_links_closed_pct >= 1.0` in canonical `quality-report --include-initiatives --enforce-gate`
    - real DB enforce runs on `etl/data/staging/politicos-es.db` confirm:
      - `initiatives.gate.passed=true`
      - `actionable_doc_links_closed_pct=1.0`
      - `missing_doc_links_actionable=0`
    - regression suite rerun:
      - `python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report -q` -> `Ran 15 tests ... OK`
    - evidence:
      - `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T190825Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T191055Z.json`
      - `docs/etl/sprints/AI-OPS-28/evidence/initiative_quality_gate_tests_20260222T191055Z.txt`
    - report:
      - `docs/etl/sprints/AI-OPS-28/reports/initiative-quality-actionable-gate-20260222.md`
  - Operational integrity check:
    - `just etl-tracker-gate` rerun after AI-OPS-28 updates
    - result: `mismatches=0`, `waivers_active=0`, `done_zero_real=0`
    - evidence:
      - `docs/etl/sprints/AI-OPS-28/evidence/tracker_gate_20260222T191229Z.txt`
