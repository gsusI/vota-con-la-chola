# AI-OPS-198 - Packet-fix compaction-window digest-heartbeat compaction lane

## Objective
Add deterministic retention + strict parity checks for the digest-heartbeat history so Scenario A can keep long-running observability without losing incident traceability.

## What Was Delivered
- New digest-heartbeat-compaction script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction.py`
- New digest-heartbeat-compaction-window script:
  - `scripts/report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
- `justfile` integration:
  - New variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_*`
  - New lanes:
    - `parl-report-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction`
    - `parl-check-sanction-procedural-official-review-packet-fix-queue-heartbeat-compaction-window-digest-heartbeat-compaction-window`
  - Both lanes integrated into `parl-sanction-data-catalog-pipeline`.
- Test coverage:
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction.py`
  - `tests/test_report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window.py`
  - Added to `parl-test-sanction-data-catalog`.

## Validation (`20260224T130421Z`)

### 1. Digest-heartbeat compaction
- `status=degraded`
- `entries_total=3`
- `selected_entries=3`
- `dropped_entries=0`
- `strict_fail_reasons=[]`
- `checks.latest_selected_ok=true`
- `checks.incidents_preserved_ok=true`

### 2. Digest-heartbeat compaction-window parity
- `status=ok`
- `window_raw_entries=3`
- `missing_in_compacted_in_window=0`
- `incident_missing_in_compacted=0`
- `raw_window_coverage_pct=100.0`
- `strict_fail_reasons=[]`

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 80`, `OK`.
- `SNAPSHOT_DATE=2026-02-24 just parl-sanction-data-catalog-pipeline`: `PASS` with new digest-heartbeat compaction lanes included.
- `SNAPSHOT_DATE=2026-02-24 just etl-tracker-gate`: `PASS` (`mismatches=0`, `done_zero_real=0`).

## Outcome
Scenario A now keeps digest-heartbeat history compacted deterministically with strict raw-vs-compacted parity checks in the main sanction pipeline.

## Evidence
- `docs/etl/sprints/AI-OPS-198/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_20260224T130421Z.json`
- `docs/etl/sprints/AI-OPS-198/evidence/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_20260224T130421Z.json`
- `docs/etl/sprints/AI-OPS-198/evidence/just_parl_test_sanction_data_catalog_20260224T130421Z.txt`
- `docs/etl/sprints/AI-OPS-198/evidence/just_parl_sanction_data_catalog_pipeline_20260224T130421Z.txt`
- `docs/etl/sprints/AI-OPS-198/evidence/just_etl_tracker_gate_20260224T130716Z.txt`
