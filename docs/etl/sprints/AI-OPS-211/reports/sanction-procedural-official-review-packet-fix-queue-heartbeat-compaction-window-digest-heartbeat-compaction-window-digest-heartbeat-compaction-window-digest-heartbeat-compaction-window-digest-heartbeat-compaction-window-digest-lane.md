# AI-OPS-211 - Packet-fix compact parity digest-heartbeat continuity compaction-window digest lane over AI-OPS-210 window

## Objective
Add a compact strict digest over the AI-OPS-210 continuity compaction-window parity layer so Scenario A gets a low-noise contract (`status/risk_level/key_metrics`) for deeper continuity depth.

## What Was Delivered
- New compact digest script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- New digest test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py`
- `justfile` integration:
  - New variable:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest`
  - Check lane integrated into `parl-sanction-data-catalog-pipeline`.
- Stability hardening while validating AI-OPS-211:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py` now avoids false strict failures when `entries_total >= min_raw_for_dropped_check` but all rows are mandatory-preserved (`incident` and non-incident anchors), by gating drop enforcement on `drop_candidates_total > 0`.
  - Regression case added:
    - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py` (`test_compaction_all_incidents_can_keep_all_without_drop_failure`)

## Validation (`20260224T143642Z`)

### 1. Compact digest lane
- `status=ok`
- `risk_level=green`
- `strict_fail_reasons=[]`
- `entries_total_raw=4`
- `entries_total_compacted=4`
- `window_raw_entries=4`
- `missing_in_compacted_in_window=0`
- `raw_window_coverage_pct=100.0`

### 2. Regression + pipeline + tracker
- `just parl-test-sanction-data-catalog`: `Ran 123 tests`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` after compaction false-fail guard fix (`no_entries_dropped_above_threshold` no longer triggers when drop candidates are zero by design).
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate` post-doc rerun: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now has a strict compact digest contract at AI-OPS-211 continuity depth, and the underlying continuity compaction guardrail is hardened against a false-fail edge case without loosening strict incident preservation.

## Evidence
- `docs/etl/sprints/AI-OPS-211/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_20260224T143642Z.json`
- `docs/etl/sprints/AI-OPS-211/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_latest.json`
- `docs/etl/sprints/AI-OPS-211/evidence/just_parl_report_ai_ops_211_20260224T143642Z.txt`
- `docs/etl/sprints/AI-OPS-211/evidence/just_parl_check_ai_ops_211_20260224T143642Z.txt`
- `docs/etl/sprints/AI-OPS-211/evidence/just_parl_test_sanction_data_catalog_20260224T143642Z_rerun2.txt`
- `docs/etl/sprints/AI-OPS-211/evidence/just_parl_sanction_data_catalog_pipeline_20260224T143642Z_rerun1.txt`
- `docs/etl/sprints/AI-OPS-211/evidence/just_etl_tracker_gate_20260224T143642Z.txt`
- `docs/etl/sprints/AI-OPS-211/evidence/just_etl_tracker_gate_post_docs_20260224T143642Z.txt`
