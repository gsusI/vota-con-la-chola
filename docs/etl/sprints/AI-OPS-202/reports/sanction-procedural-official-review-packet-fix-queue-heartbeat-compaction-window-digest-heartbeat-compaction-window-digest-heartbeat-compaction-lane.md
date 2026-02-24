# AI-OPS-202 - Packet-fix compact parity digest-heartbeat compaction lane

## Objective
Add deterministic retention and strict parity checks for the AI-OPS-200/201 compact parity digest-heartbeat stream so Scenario A keeps long-run observability without losing incidents.

## What Was Delivered
- New compaction script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
- New compaction-window strict parity script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- `justfile` integration:
  - New variables:
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_*`
    - `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW_*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window`
  - Both lanes integrated in `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T133440Z`)

### 1. Digest-heartbeat compaction
- `status=degraded` (expected with short history and `dropped_entries=0`)
- `strict_fail_reasons=[]`
- `entries_total=3`
- `selected_entries=3`
- `dropped_entries=0`
- `incidents_total=0`
- `incidents_dropped=0`
- `latest_selected_ok=true`

### 2. Digest-heartbeat compaction-window strict parity
- `status=ok`
- `strict_fail_reasons=[]`
- `window_raw_entries=3`
- `present_in_compacted_in_window=3`
- `missing_in_compacted_in_window=0`
- `latest_present_ok=true`
- `incident_parity_ok=true`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 93`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with AI-OPS-202 lanes included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now preserves and validates long-run continuity for the compact parity digest-heartbeat stream with deterministic retention and strict last-N parity guarantees.

## Evidence
- `docs/etl/sprints/AI-OPS-202/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T133440Z.json`
- `docs/etl/sprints/AI-OPS-202/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T133440Z.json`
- `docs/etl/sprints/AI-OPS-202/evidence/just_parl_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T133440Z.txt`
- `docs/etl/sprints/AI-OPS-202/evidence/just_parl_check_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T133440Z.txt`
- `docs/etl/sprints/AI-OPS-202/evidence/just_parl_test_sanction_data_catalog_20260224T133440Z.txt`
- `docs/etl/sprints/AI-OPS-202/evidence/just_parl_sanction_data_catalog_pipeline_20260224T133440Z.txt`
- `docs/etl/sprints/AI-OPS-202/evidence/just_etl_tracker_gate_20260224T133440Z.txt`
