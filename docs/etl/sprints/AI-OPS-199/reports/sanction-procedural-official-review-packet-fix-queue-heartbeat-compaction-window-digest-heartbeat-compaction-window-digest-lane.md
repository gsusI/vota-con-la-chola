# AI-OPS-199 - Packet-fix compaction-window digest-heartbeat compaction-window digest lane

## Objective
Add a compact strict digest for digest-heartbeat compaction-window parity so Scenario A gets a low-noise, pipeline-gated risk signal (`status/risk_level/reasons/key_metrics`).

## What Was Delivered
- New digest script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- `justfile` integration:
  - New variable `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
  - Check lane integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T131205Z`)

### 1. Compaction-window digest
- `status=ok`
- `risk_level=green`
- `risk_reasons=[]`
- `strict_fail_reasons=[]`
- `entries_total_raw=5`
- `entries_total_compacted=5`
- `window_raw_entries=5`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`
- `raw_window_coverage_pct=100.0`
- `incident_coverage_pct=0.0`

### 2. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 83`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-199 digest check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has a compact, strict risk digest on top of digest-heartbeat compaction-window parity, reducing operational noise while preserving deterministic parity guarantees.

## Evidence
- `docs/etl/sprints/AI-OPS-199/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T131205Z.json`
- `docs/etl/sprints/AI-OPS-199/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T131205Z.txt`
- `docs/etl/sprints/AI-OPS-199/evidence/just_parl_test_sanction_data_catalog_20260224T131205Z.txt`
- `docs/etl/sprints/AI-OPS-199/evidence/just_parl_sanction_data_catalog_pipeline_20260224T131205Z.txt`
- `docs/etl/sprints/AI-OPS-199/evidence/just_etl_tracker_gate_20260224T131516Z.txt`
