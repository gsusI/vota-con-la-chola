# AI-OPS-106 Report: Trust-Action Nudges Heartbeat Retention v1

Date:
- 2026-02-23

## Where we are now

- Trust-action nudges already had digest + heartbeat + heartbeat-window lanes (`AI-OPS-101`).
- Missing piece: bounded retention for long-running heartbeat history while preserving incident traceability.

## What was delivered

- Added compaction lane for trust-action heartbeat:
  - `scripts/report_citizen_trust_action_nudges_heartbeat_compaction.py`
  - Preserves `failed/degraded/strict/malformed`, `contract_complete=false`, and `nudge_clickthrough` threshold violations.
- Added raw-vs-compacted parity lane:
  - `scripts/report_citizen_trust_action_nudges_heartbeat_compaction_window.py`
  - Enforces latest-row presence and incident-class parity in strict mode.
- Wired `just` lanes:
  - `citizen-report/check-trust-action-nudges-heartbeat-compact`
  - `citizen-report/check-trust-action-nudges-heartbeat-compact-window`
- Expanded trust-action heartbeat test gate:
  - `citizen-test-trust-action-nudges-heartbeat` now includes compaction/parity tests.

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-106/evidence/just_citizen_test_trust_action_nudges_heartbeat_20260223T155645Z.txt`
  - `docs/etl/sprints/AI-OPS-106/evidence/just_citizen_check_trust_action_nudges_heartbeat_compact_20260223T155645Z.txt`
  - `docs/etl/sprints/AI-OPS-106/evidence/just_citizen_check_trust_action_nudges_heartbeat_compact_window_20260223T155645Z.txt`
- JSON artifacts:
  - `docs/etl/sprints/AI-OPS-106/evidence/citizen_trust_action_nudges_heartbeat_compaction_20260223T155645Z.json`
  - `docs/etl/sprints/AI-OPS-106/evidence/citizen_trust_action_nudges_heartbeat_compaction_window_20260223T155645Z.json`

## What is next

- AI-OPS-107: apply the same retention/parity hardening pattern to citizen product KPI heartbeat.
