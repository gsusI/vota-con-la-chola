# AI-OPS-197 - Packet-fix compaction-window digest heartbeat lane

## Objective
Add append-only heartbeat + strict window controls for the compaction-window digest so Scenario A can track parity health over time with a stable operational signal.

## What Was Delivered
- New digest-heartbeat script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.py`
- New digest-heartbeat-window script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window.py`
- `justfile` integration:
  - New variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-window`
  - Both lanes integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T125555Z`)

### 1. Digest input (from AI-OPS-196)
- `status=ok`
- `risk_level=green`
- `risk_reasons=[]`
- `strict_fail_reasons=[]`
- `window_raw_entries=8`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`

### 2. Digest heartbeat append
- `heartbeat_status=ok`
- `heartbeat_risk_level=green`
- `appended=true`
- `duplicate_detected=false`
- `history_size_before=1`
- `history_size_after=2`
- `validation_errors=[]`

### 3. Digest heartbeat window
- `status=ok`
- `entries_in_window=2`
- `status_counts={ok:2,degraded:0,failed:0}`
- `risk_level_counts={green:2,amber:0,red:0}`
- `failed_in_window=0`
- `degraded_in_window=0`
- `strict_fail_reasons=[]`

### 4. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 75`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with digest-heartbeat lanes included.

## Outcome
Scenario A now keeps an append-only heartbeat timeline for compaction-window digest quality and enforces strict last-N checks in the main sanction pipeline without breaking reproducibility.

## Evidence
- `docs/etl/sprints/AI-OPS-197/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_20260224T125555Z.json`
- `docs/etl/sprints/AI-OPS-197/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_20260224T125555Z.json`
- `docs/etl/sprints/AI-OPS-197/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_window_20260224T125555Z.json`
- `docs/etl/sprints/AI-OPS-197/evidence/just_parl_test_sanction_data_catalog_20260224T125555Z.txt`
- `docs/etl/sprints/AI-OPS-197/evidence/just_parl_sanction_data_catalog_pipeline_20260224T125555Z.txt`
