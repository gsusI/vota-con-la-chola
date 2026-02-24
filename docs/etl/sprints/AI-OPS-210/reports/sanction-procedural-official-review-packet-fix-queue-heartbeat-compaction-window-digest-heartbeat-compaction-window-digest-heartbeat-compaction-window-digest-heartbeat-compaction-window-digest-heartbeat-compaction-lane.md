# AI-OPS-210 - Packet-fix compact parity digest-heartbeat continuity compaction lane over AI-OPS-209 window

## Objective
Add deterministic retention compaction over the AI-OPS-209 digest-heartbeat continuity stream, plus strict in-window raw-vs-compacted parity checks, so Scenario A preserves long-run continuity without losing recent operational signal.

## What Was Delivered
- New continuity compaction script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
- New continuity compaction-window parity script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_*`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window`
  - Both lanes integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
  - Included in `parl-test-sanction-data-catalog`.

## Validation (`20260224T142419Z`)

### 1. Continuity compaction
- `status=degraded` (expected with short history)
- `strict_fail_reasons=[]`
- `entries_total=3`
- `selected_entries=3`
- `dropped_entries=0`
- `malformed_total=0`
- `failed_total=0`
- `degraded_total=0`

### 2. Continuity compaction-window parity
- `status=ok`
- `strict_fail_reasons=[]`
- `entries_total_raw=3`
- `entries_total_compacted=3`
- `window_raw_entries=3`
- `present_in_compacted_in_window=3`
- `missing_in_compacted_in_window=0`
- `latest_present_ok=true`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 119`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-210 compaction + compaction-window checks included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now extends the continuity loop with deterministic compaction and strict parity verification at the AI-OPS-210 depth, keeping deeper heartbeat continuity auditable and bounded.

## Evidence
- `docs/etl/sprints/AI-OPS-210/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T142419Z.json`
- `docs/etl/sprints/AI-OPS-210/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T142419Z.json`
- `docs/etl/sprints/AI-OPS-210/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T142419Z.txt`
- `docs/etl/sprints/AI-OPS-210/evidence/just_parl_check_ai_ops_210_20260224T142419Z.txt`
- `docs/etl/sprints/AI-OPS-210/evidence/just_parl_test_sanction_data_catalog_20260224T142419Z.txt`
- `docs/etl/sprints/AI-OPS-210/evidence/just_parl_sanction_data_catalog_pipeline_20260224T142419Z.txt`
- `docs/etl/sprints/AI-OPS-210/evidence/just_etl_tracker_gate_20260224T142419Z.txt`
- `docs/etl/sprints/AI-OPS-210/evidence/just_etl_tracker_gate_post_docs_20260224T142419Z.txt`
