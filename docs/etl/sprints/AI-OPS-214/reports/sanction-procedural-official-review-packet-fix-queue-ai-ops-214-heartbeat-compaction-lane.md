# AI-OPS-214 — Heartbeat Compaction + Parity Window (Scenario A)

## Objective
Add deterministic compaction and strict in-window raw-vs-compacted parity checks over the AI-OPS-212/213 heartbeat continuity stream, preserving traceability while keeping operational signal bounded.

## Delivered
- Added `scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction.py`.
- Added `scripts/report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction_window.py`.
- Added tests:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_214_heartbeat_compaction_window.py`
- Extended `justfile` with AI-OPS-214 vars/lanes and integrated lanes into `parl-sanction-data-catalog-pipeline`.
- Extended `parl-test-sanction-data-catalog` to include both AI-OPS-214 tests.

## Validation
- `just parl-test-sanction-data-catalog`: `Ran 133 tests`, `OK`.
- AI-OPS-214 report lane (`strict`):
  - `status=degraded` (expected on short history)
  - `entries_total=3`, `selected_entries=3`, `dropped_entries=0`
  - `strict_fail_reasons=[]`
- AI-OPS-214 check lane (`strict`):
  - `status=ok`
  - `entries_total_raw=3`, `entries_total_compacted=3`, `window_raw_entries=3`
  - `missing_in_compacted_in_window=0`, `latest_present_ok=true`
  - `strict_fail_reasons=[]`
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: pass.

## Notes
- Short script/test aliases were required due per-filename length limits on the host filesystem.
- Output artifacts for AI-OPS-214 use short filenames to remain portable and reproducible.

## Evidence
- `docs/etl/sprints/AI-OPS-214/evidence/just_parl_test_sanction_data_catalog_20260224T150303Z.txt`
- `docs/etl/sprints/AI-OPS-214/evidence/just_parl_report_ai_ops_214_20260224T150319Z.txt`
- `docs/etl/sprints/AI-OPS-214/evidence/just_parl_check_ai_ops_214_20260224T150319Z.txt`
- `docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_latest.json`
- `docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_window_latest.json`
- `docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_20260224T150343Z.json`
- `docs/etl/sprints/AI-OPS-214/evidence/ai_ops_214_heartbeat_compaction_window_20260224T150343Z.json`
- `docs/etl/sprints/AI-OPS-214/evidence/just_parl_sanction_data_catalog_pipeline_20260224T150329Z.txt`
- `docs/etl/sprints/AI-OPS-214/evidence/just_etl_tracker_gate_post_docs_tracker_20260224T150601Z.txt`
