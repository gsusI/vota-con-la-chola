# AI-OPS-215 — Compact Strict Digest Over AI-OPS-214 Parity (Scenario A)

## Objective
Add a compact strict digest layer on top of the AI-OPS-214 compaction-window parity output so the sanction pipeline keeps a low-noise, reproducible health signal.

## Delivered
- Added `scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py`.
- Added test `tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py`.
- Extended `justfile` with:
  - vars `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_AI_OPS_215_DIGEST_IN` and `..._OUT`
  - lanes `parl-report-sanction-procedural-official-review-packet-fix-queue-ai-ops-215-digest` and `parl-check-sanction-procedural-official-review-packet-fix-queue-ai-ops-215-digest`
  - pipeline integration in `parl-sanction-data-catalog-pipeline`
  - test-pack integration in `parl-test-sanction-data-catalog`

## Validation
- `python3 -m unittest tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_215_digest.py`: `Ran 3`, `OK`.
- `just parl-test-sanction-data-catalog`: `Ran 136 tests`, `OK`.
- AI-OPS-215 report/check lanes:
  - `status=ok`
  - `risk_level=green`
  - `risk_reasons=[]`
  - `strict_fail_reasons=[]`
  - `entries_total_raw=4` (first lane run), `entries_total_raw=5` (pipeline-integrated replay)
  - `entries_total_compacted=4` (first lane run), `entries_total_compacted=5` (pipeline-integrated replay)
  - `window_raw_entries=4` (first lane run), `window_raw_entries=5` (pipeline-integrated replay)
  - `missing_in_compacted_in_window=0`
  - `raw_window_coverage_pct=100.0`
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: pass.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: pass (`mismatches=0`, `done_zero_real=0`).

## Notes
- Kept short-alias naming to avoid host filename-length limits while preserving deterministic contracts.
- Digest logic is intentionally reused from the base compaction-window digest builder to avoid semantic drift.

## Evidence
- `docs/etl/sprints/AI-OPS-215/evidence/just_parl_test_sanction_data_catalog_20260224T151152Z.txt`
- `docs/etl/sprints/AI-OPS-215/evidence/just_parl_report_ai_ops_215_20260224T151207Z.txt`
- `docs/etl/sprints/AI-OPS-215/evidence/just_parl_check_ai_ops_215_20260224T151207Z.txt`
- `docs/etl/sprints/AI-OPS-215/evidence/ai_ops_215_digest_latest.json`
- `docs/etl/sprints/AI-OPS-215/evidence/ai_ops_215_digest_20260224T151207Z.json`
- `docs/etl/sprints/AI-OPS-215/evidence/ai_ops_215_digest_20260224T151217Z.json`
- `docs/etl/sprints/AI-OPS-215/evidence/just_parl_sanction_data_catalog_pipeline_20260224T151217Z.txt`
- `docs/etl/sprints/AI-OPS-215/evidence/just_etl_tracker_gate_20260224T151217Z.txt`
- `docs/etl/sprints/AI-OPS-215/evidence/just_etl_tracker_gate_post_docs_tracker_20260224T151733Z.txt`
