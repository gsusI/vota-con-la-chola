# AI-OPS-209 - Packet-fix compact parity digest-heartbeat continuity window lane over AI-OPS-208 digest-heartbeat

## Objective
Add a strict `last-N` window guard over the AI-OPS-208 digest-heartbeat continuity stream so Scenario A can fail fast on recent `failed/degraded` drift in this deeper continuity layer.

## What Was Delivered
- New digest-heartbeat window script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_FAILED_RATE_PCT`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_MAX_DEGRADED_RATE_PCT`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_WINDOW_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-window`
  - Strict check integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T141714Z`)

### 1. Digest-heartbeat window
- `status=ok`
- `strict_fail_reasons=[]`
- `entries_total=2`
- `entries_in_window=2`
- `status_counts.ok=2`
- `status_counts.failed=0`
- `status_counts.degraded=0`
- `risk_level_counts.green=2`
- `latest.status=ok`

### 2. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 114`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-209 window check included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has strict temporal guarding over the AI-OPS-208 digest-heartbeat continuity stream, closing the `heartbeat -> window` loop for this continuity depth.

## Evidence
- `docs/etl/sprints/AI-OPS-209/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_20260224T141714Z.json`
- `docs/etl/sprints/AI-OPS-209/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_20260224T141714Z.txt`
- `docs/etl/sprints/AI-OPS-209/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window_20260224T141714Z.txt`
- `docs/etl/sprints/AI-OPS-209/evidence/just_parl_test_sanction_data_catalog_20260224T141714Z.txt`
- `docs/etl/sprints/AI-OPS-209/evidence/just_parl_sanction_data_catalog_pipeline_20260224T141714Z.txt`
- `docs/etl/sprints/AI-OPS-209/evidence/just_etl_tracker_gate_20260224T141714Z.txt`
