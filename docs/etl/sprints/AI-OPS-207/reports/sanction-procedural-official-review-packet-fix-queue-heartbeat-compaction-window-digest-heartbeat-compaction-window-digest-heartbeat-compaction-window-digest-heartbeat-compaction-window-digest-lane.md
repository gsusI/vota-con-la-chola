# AI-OPS-207 - Packet-fix compact parity digest-heartbeat continuity compaction-window digest lane

## Objective
Add a compact strict digest over the AI-OPS-206 continuity compaction-window parity layer so Scenario A can track this deeper continuity contract with a low-noise operational signal.

## What Was Delivered
- New continuity compaction-window digest script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- `justfile` integration:
  - New variable:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
  - Strict check integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T140703Z`)

### 1. Continuity compaction-window digest
- `status=ok`
- `risk_level=green`
- `strict_fail_reasons=[]`
- `entries_total_raw=5`
- `entries_total_compacted=5`
- `window_raw_entries=5`
- `missing_in_compacted_in_window=0`
- `raw_window_coverage_pct=100.0`

### 2. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 109`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-207 check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has a compact strict digest contract over the AI-OPS-206 continuity compaction-window parity layer, preserving auditable low-noise gating as continuity depth increases.

## Evidence
- `docs/etl/sprints/AI-OPS-207/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T140703Z.json`
- `docs/etl/sprints/AI-OPS-207/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T140703Z.txt`
- `docs/etl/sprints/AI-OPS-207/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T140703Z.txt`
- `docs/etl/sprints/AI-OPS-207/evidence/just_parl_test_sanction_data_catalog_20260224T140703Z.txt`
- `docs/etl/sprints/AI-OPS-207/evidence/just_parl_sanction_data_catalog_pipeline_20260224T140703Z.txt`
- `docs/etl/sprints/AI-OPS-207/evidence/just_etl_tracker_gate_20260224T140703Z.txt`
