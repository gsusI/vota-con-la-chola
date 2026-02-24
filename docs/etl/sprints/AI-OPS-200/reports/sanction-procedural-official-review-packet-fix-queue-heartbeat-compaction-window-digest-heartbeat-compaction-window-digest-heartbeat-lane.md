# AI-OPS-200 - Packet-fix compaction-window digest heartbeat lane

## Objective
Add append-only heartbeat observability for the AI-OPS-199 compact parity digest so Scenario A can track trend continuity over time with deterministic dedupe.

## What Was Delivered
- New digest-heartbeat script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_DIGEST_JSON`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_PATH`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat`
  - Check lane integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T132030Z`)

### 1. Digest heartbeat
- `status=ok`
- `risk_level=green`
- `strict_fail_reasons=[]`
- `risk_reasons=[]`
- `window_raw_entries=8`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`
- `raw_window_coverage_pct=100.0`
- `history_size_before=1`
- `history_size_after=2`
- `appended=true`
- `duplicate_detected=false`

### 2. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 85`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-200 heartbeat check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now keeps a deduplicated heartbeat history for the compact digest parity signal, enabling trend tracking without growing noise in the main sanction pipeline.

## Evidence
- `docs/etl/sprints/AI-OPS-200/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_20260224T132030Z.json`
- `docs/etl/sprints/AI-OPS-200/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_20260224T132030Z.txt`
- `docs/etl/sprints/AI-OPS-200/evidence/just_parl_test_sanction_data_catalog_20260224T132030Z.txt`
- `docs/etl/sprints/AI-OPS-200/evidence/just_parl_sanction_data_catalog_pipeline_20260224T132030Z.txt`
- `docs/etl/sprints/AI-OPS-200/evidence/just_etl_tracker_gate_20260224T132337Z.txt`
