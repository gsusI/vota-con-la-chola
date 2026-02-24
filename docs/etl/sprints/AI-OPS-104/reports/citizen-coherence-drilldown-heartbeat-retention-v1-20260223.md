# AI-OPS-104 Report: Coherence Heartbeat Retention v1

Date:
- 2026-02-23

## Where we are now

- Coherence drilldown outcomes already had digest + heartbeat + heartbeat-window lanes (`AI-OPS-99`).
- Missing piece: bounded retention for long-running heartbeat histories without losing incident rows needed for auditability.

## What was delivered

- Added compaction lane for coherence heartbeat:
  - `scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction.py`
  - Preserves `failed/degraded/strict/malformed`, `contract_complete=false`, and replay/contract/failure threshold violations.
- Added raw-vs-compacted parity lane:
  - `scripts/report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window.py`
  - Enforces latest-row presence and incident-class parity in strict mode.
- Wired `just` lanes:
  - `citizen-report/check-coherence-drilldown-outcomes-heartbeat-compact`
  - `citizen-report/check-coherence-drilldown-outcomes-heartbeat-compact-window`
- Expanded coherence test gate:
  - `citizen-test-coherence-drilldown-outcomes` now includes compaction/parity unit tests.

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-104/evidence/just_citizen_test_coherence_drilldown_outcomes_20260223T154042Z.txt`
  - `docs/etl/sprints/AI-OPS-104/evidence/just_citizen_check_coherence_drilldown_outcomes_heartbeat_compact_20260223T154042Z.txt`
  - `docs/etl/sprints/AI-OPS-104/evidence/just_citizen_check_coherence_drilldown_outcomes_heartbeat_compact_window_20260223T154042Z.txt`
- JSON artifacts:
  - `docs/etl/sprints/AI-OPS-104/evidence/citizen_coherence_drilldown_outcomes_heartbeat_compaction_20260223T154042Z.json`
  - `docs/etl/sprints/AI-OPS-104/evidence/citizen_coherence_drilldown_outcomes_heartbeat_compaction_window_20260223T154042Z.json`

## What is next

- AI-OPS-105: apply the same retention/parity hardening pattern to concern-pack outcomes heartbeat.
