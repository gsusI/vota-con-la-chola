# AI-OPS-213 - Packet-fix compact parity digest-heartbeat continuity compaction-window digest heartbeat window lane over AI-OPS-212 continuity

## Objective
Add strict last-N window gating over the AI-OPS-212 digest-heartbeat continuity stream so Scenario A gets temporal fail/degraded guardrails at the next depth.

## What Was Delivered
- New heartbeat-window script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py`
- New heartbeat-window test coverage (short alias to avoid filesystem filename-length limits):
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_ai_ops_213_heartbeat_window.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window`
  - Strict check integrated into `parl-sanction-data-catalog-pipeline`.
- Regression pack update:
  - `parl-test-sanction-data-catalog` includes the AI-OPS-213 window test.

## Validation (`20260224T145439Z`)

### 1. Heartbeat-window lane
- `status=ok`
- `strict=true`
- `strict_fail_reasons=[]`
- `entries_total=2`
- `entries_in_window=2`
- `status_counts={ok:2,degraded:0,failed:0}`
- `risk_level_counts={green:2,amber:0,red:0}`
- `latest.status=ok`

### 2. Regression + pipeline + tracker
- `just parl-test-sanction-data-catalog`: `Ran 128 tests`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-213 strict window check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate` post-doc rerun: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now enforces strict windowed continuity checks over the AI-OPS-212 digest-heartbeat stream, keeping fail/degraded drift auditable and bounded at AI-OPS-213 depth.

## Evidence
- `docs/etl/sprints/AI-OPS-213/evidence/ai_ops_213_heartbeat_window_20260224T145439Z.json`
- `docs/etl/sprints/AI-OPS-213/evidence/ai_ops_213_heartbeat_window_latest.json`
- `docs/etl/sprints/AI-OPS-213/evidence/just_parl_report_ai_ops_213_20260224T145439Z.txt`
- `docs/etl/sprints/AI-OPS-213/evidence/just_parl_check_ai_ops_213_20260224T145439Z.txt`
- `docs/etl/sprints/AI-OPS-213/evidence/just_parl_test_sanction_data_catalog_20260224T145439Z.txt`
- `docs/etl/sprints/AI-OPS-213/evidence/just_parl_sanction_data_catalog_pipeline_20260224T145439Z.txt`
- `docs/etl/sprints/AI-OPS-213/evidence/just_etl_tracker_gate_20260224T145439Z.txt`
- `docs/etl/sprints/AI-OPS-213/evidence/just_etl_tracker_gate_post_docs_20260224T145439Z.txt`
