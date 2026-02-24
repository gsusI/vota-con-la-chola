# AI-OPS-195 - Packet-fix queue heartbeat compaction lane

## Objective
Harden Scenario A heartbeat operations by adding deterministic history compaction and raw-vs-compacted parity checks for the packet-fix remediation backlog.

## What Was Delivered
- New compaction script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py`
- New compaction-window parity script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window.py`
- `justfile` integration:
  - New variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window`
  - Both lanes integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation

### 1. Heartbeat + raw window (`20260224T124757Z`)
- Heartbeat:
  - `status=degraded`
  - `heartbeat.status=degraded`
  - `queue_rows_total=4`
  - `history_rows_after=6`
- Raw window:
  - `status=ok`
  - `entries_in_window=6`
  - `degraded_in_window=6`
  - `nonempty_queue_runs_in_window=6`
  - `strict_fail_reasons=[]`

### 2. Compaction + compaction-window (`20260224T124757Z`)
- Compaction:
  - `status=degraded` (no rows dropped with current small history)
  - `entries_total=6`
  - `selected_entries=6`
  - `dropped_entries=0`
  - `strict_fail_reasons=[]`
- Compaction-window:
  - `status=ok`
  - `window_raw_entries=6`
  - `missing_in_compacted_in_window=0`
  - `strict_fail_reasons=[]`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 70`, `OK`.
- `just parl-sanction-data-catalog-pipeline`: `PASS` with compaction lanes included.

## Outcome
Scenario A now keeps packet-fix heartbeat history manageable and verifies compaction parity, without breaking deterministic pipeline behavior while backlog remains open.

## Evidence
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_window_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-195/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_20260224T124757Z.json`
- `docs/etl/sprints/AI-OPS-195/evidence/just_parl_test_sanction_data_catalog_20260224T124757Z.txt`
- `docs/etl/sprints/AI-OPS-195/evidence/just_parl_sanction_data_catalog_pipeline_20260224T124757Z.txt`
