# AI-OPS-203 - Packet-fix compact parity digest-heartbeat compaction-window digest lane

## Objective
Add a strict compact digest over the AI-OPS-202 compact-parity compaction-window report so Scenario A keeps a low-noise contract (`status/risk_level/reasons/key_metrics`) on top of long-run continuity checks.

## What Was Delivered
- New compact-window digest script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- `justfile` integration:
  - New variable:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
  - Strict check integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T133909Z`)

### 1. Compact-window digest
- `status=ok`
- `risk_level=green`
- `risk_reasons=[]`
- `strict_fail_reasons=[]`
- `entries_total_raw=4`
- `entries_total_compacted=4`
- `window_raw_entries=4`
- `missing_in_compacted_in_window=0`
- `raw_window_coverage_pct=100.0`

### 2. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 96`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-203 digest check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has a compact strict digest contract on top of the AI-OPS-202 compaction-window parity layer, preserving low-noise operational observability as the heartbeat history grows.

## Evidence
- `docs/etl/sprints/AI-OPS-203/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T133909Z.json`
- `docs/etl/sprints/AI-OPS-203/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T133909Z.txt`
- `docs/etl/sprints/AI-OPS-203/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T133909Z.txt`
- `docs/etl/sprints/AI-OPS-203/evidence/just_parl_test_sanction_data_catalog_20260224T133909Z.txt`
- `docs/etl/sprints/AI-OPS-203/evidence/just_parl_sanction_data_catalog_pipeline_20260224T133909Z.txt`
- `docs/etl/sprints/AI-OPS-203/evidence/just_etl_tracker_gate_20260224T133909Z.txt`
