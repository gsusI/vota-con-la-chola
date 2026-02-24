# AI-OPS-196 - Packet-fix queue compaction-window digest lane

## Objective
Add a compact, reproducible digest over compaction-window parity so Scenario A can track packet-fix heartbeat retention quality with a stable `ok/degraded/failed` contract.

## What Was Delivered
- New digest script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_IN`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest`
  - Digest strict check integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T124757Z`)

### 1. Compaction-window digest
- `status=ok`
- `risk_level=green`
- `risk_reasons=[]`
- `strict_fail_reasons=[]`
- `entries_total_raw=6`
- `entries_total_compacted=6`
- `window_raw_entries=6`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`
- `raw_window_coverage_pct=100.0`
- `incident_coverage_pct=100.0`

### 2. Upstream parity context (for digest input)
- Compaction-window parity:
  - `status=ok`
  - `window_raw_entries=6`
  - `missing_in_compacted_in_window=0`
  - `strict_fail_reasons=[]`
- Compaction:
  - `status=degraded` (expected with short history/no dropped rows yet)
  - `entries_total=6`
  - `selected_entries=6`
  - `dropped_entries=0`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 70`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with digest strict check included.

## Outcome
Scenario A now has a stable digest artifact for heartbeat compaction parity, making retention-quality trend tracking easier to consume while preserving strict pipeline guardrails.

## Evidence
- `docs/etl/sprints/AI-OPS-196/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-196/evidence/just_parl_test_sanction_data_catalog_20260224T124757Z.txt`
- `docs/etl/sprints/AI-OPS-196/evidence/just_parl_sanction_data_catalog_pipeline_20260224T124757Z.txt`
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_20260224T124757Z.json`
