# AI-OPS-206 - Packet-fix digest-heartbeat continuity compaction lane

## Objective
Add deterministic compaction + strict raw-vs-compacted window parity over the AI-OPS-204/205 digest-heartbeat continuity stream so Scenario A keeps low-noise long-run observability without losing incident fidelity.

## What Was Delivered
- New continuity compaction scripts:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_PATH`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_RECENT`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_SPAN`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MID_EVERY`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OLD_EVERY`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_MIN_RAW`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_OUT`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_LAST`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window`
  - Both integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T135943Z`)

### 1. Continuity compaction
- `status=degraded` (expected short-history behavior)
- `strict_fail_reasons=[]`
- `entries_total=4`
- `selected_entries=4`
- `dropped_entries=0`
- `checks.latest_selected_ok=true`
- `checks.incidents_preserved_ok=true`

### 2. Continuity compaction-window parity
- `status=ok`
- `strict_fail_reasons=[]`
- `window_raw_entries=4`
- `present_in_compacted_in_window=4`
- `missing_in_compacted_in_window=0`
- `checks.latest_present_ok=true`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 106`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-206 lanes included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has deterministic retention and strict in-window parity over the AI-OPS-204/205 digest-heartbeat continuity layer, extending the compact observability chain without relaxing fail-fast guarantees.

## Evidence
- `docs/etl/sprints/AI-OPS-206/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T135943Z.json`
- `docs/etl/sprints/AI-OPS-206/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T135943Z.json`
- `docs/etl/sprints/AI-OPS-206/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T135943Z.txt`
- `docs/etl/sprints/AI-OPS-206/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T135943Z.txt`
- `docs/etl/sprints/AI-OPS-206/evidence/just_parl_test_sanction_data_catalog_20260224T135943Z.txt`
- `docs/etl/sprints/AI-OPS-206/evidence/just_parl_sanction_data_catalog_pipeline_20260224T135943Z.txt`
- `docs/etl/sprints/AI-OPS-206/evidence/just_etl_tracker_gate_20260224T135943Z.txt`
