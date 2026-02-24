# AI-OPS-194 - Packet-fix queue heartbeat observability lane

## Objective
Add append-only observability for the packet-fix remediation queue so Scenario A can track backlog behavior over time without losing deterministic pipeline execution.

## What Was Delivered
- New heartbeat script: `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat.py`.
- New window-check script: `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_window.py`.
- `justfile` wiring:
  - Variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_*`.
  - Lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-window`
  - Both lanes integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation

### 1. Heartbeat lane (`latest`)
- Input: `AI-OPS-193` packet-fix queue output.
- Result:
  - `status=degraded`
  - `heartbeat.status=degraded`
  - `queue_rows_total=4`
  - `packets_ready_total=0`
  - `packets_not_ready_total=4`
  - `strict_fail_reasons=[]`
  - `history_rows_after=2`

### 2. Window lane (`latest`)
- Result:
  - `status=ok`
  - `entries_in_window=2`
  - `failed_in_window=0`
  - `degraded_in_window=2`
  - `nonempty_queue_runs_in_window=2`
  - `strict_fail_reasons=[]`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 63`, `OK`.
- `just parl-sanction-data-catalog-pipeline`: `PASS` with heartbeat lanes included.

## Outcome
Scenario A now has a reproducible heartbeat history and windowed trend check for packet-fix backlog evolution, while keeping the operational dry-run pipeline green and evidence-backed.

## Evidence
- `docs/etl/sprints/AI-OPS-194/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_20260224T123410Z.json`
- `docs/etl/sprints/AI-OPS-194/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_window_20260224T123410Z.json`
- `docs/etl/sprints/AI-OPS-194/evidence/just_parl_test_sanction_data_catalog_20260224T123410Z.txt`
- `docs/etl/sprints/AI-OPS-194/evidence/just_parl_sanction_data_catalog_pipeline_20260224T123410Z.txt`
