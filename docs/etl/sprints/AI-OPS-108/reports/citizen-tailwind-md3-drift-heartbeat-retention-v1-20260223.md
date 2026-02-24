# AI-OPS-108 Report: Tailwind+MD3 Drift Heartbeat Retention v1

Date:
- 2026-02-23

## Where we are now

- Tailwind+MD3 drift already had digest + heartbeat + heartbeat-window lanes (`AI-OPS-103`).
- Missing piece: bounded retention for long-running drift heartbeat history while preserving incident traceability.

## What was delivered

- Added compaction lane for Tailwind+MD3 drift heartbeat:
  - `scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction.py`
  - Preserves `failed/degraded/strict/malformed`, contract failures, and parity mismatches (`source_published`, `marker`, `tokens`, `tokens_data`, `css`, `ui_html`, `parity_fail`).
- Added raw-vs-compacted parity lane:
  - `scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window.py`
  - Enforces latest-row presence and incident-class parity in strict mode.
- Wired `just` lanes:
  - `citizen-report/check-tailwind-md3-drift-heartbeat-compact`
  - `citizen-report/check-tailwind-md3-drift-heartbeat-compact-window`
- Expanded Tailwind+MD3 test gate:
  - `citizen-test-tailwind-md3` now includes compaction/parity tests.

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-108/evidence/just_citizen_test_tailwind_md3_20260223T161317Z.txt`
  - `docs/etl/sprints/AI-OPS-108/evidence/just_citizen_check_tailwind_md3_drift_heartbeat_compact_20260223T161317Z.txt`
  - `docs/etl/sprints/AI-OPS-108/evidence/just_citizen_check_tailwind_md3_drift_heartbeat_compact_window_20260223T161317Z.txt`
- JSON artifacts:
  - `docs/etl/sprints/AI-OPS-108/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_20260223T161317Z.json`
  - `docs/etl/sprints/AI-OPS-108/evidence/citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window_20260223T161317Z.json`

## What is next

- AI-OPS-109: explainability outcomes heartbeat retention v1 (incident-preserving compaction + strict raw-vs-compacted parity).
