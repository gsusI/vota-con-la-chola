# AI-OPS-105 Report: Concern-Pack Outcomes Heartbeat Retention v1

Date:
- 2026-02-23

## Where we are now

- Concern-pack outcomes already had digest + heartbeat + heartbeat-window lanes (`AI-OPS-100`).
- Missing piece: bounded retention for long-running heartbeat history while preserving incident traceability.

## What was delivered

- Added compaction lane for concern-pack heartbeat:
  - `scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction.py`
  - Preserves `failed/degraded/strict/malformed`, `contract_complete=false`, and threshold violations (`weak_pack_followthrough`, `unknown_pack_select_share`).
- Added raw-vs-compacted parity lane:
  - `scripts/report_citizen_concern_pack_outcomes_heartbeat_compaction_window.py`
  - Enforces latest-row presence and incident-class parity in strict mode.
- Wired `just` lanes:
  - `citizen-report/check-concern-pack-outcomes-heartbeat-compact`
  - `citizen-report/check-concern-pack-outcomes-heartbeat-compact-window`
- Expanded concern-pack heartbeat test gate:
  - `citizen-test-concern-pack-outcomes-heartbeat` now includes compaction/parity tests.

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-105/evidence/just_citizen_test_concern_pack_outcomes_heartbeat_20260223T154953Z.txt`
  - `docs/etl/sprints/AI-OPS-105/evidence/just_citizen_check_concern_pack_outcomes_heartbeat_compact_20260223T154953Z.txt`
  - `docs/etl/sprints/AI-OPS-105/evidence/just_citizen_check_concern_pack_outcomes_heartbeat_compact_window_20260223T154953Z.txt`
- JSON artifacts:
  - `docs/etl/sprints/AI-OPS-105/evidence/citizen_concern_pack_outcomes_heartbeat_compaction_20260223T154953Z.json`
  - `docs/etl/sprints/AI-OPS-105/evidence/citizen_concern_pack_outcomes_heartbeat_compaction_window_20260223T154953Z.json`

## What is next

- AI-OPS-106: apply the same retention/parity hardening pattern to trust-action nudges heartbeat.
