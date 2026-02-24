# AI-OPS-107 Report: Product KPI Heartbeat Retention v1

Date:
- 2026-02-23

## Where we are now

- Product KPI already had digest + heartbeat + heartbeat-window lanes (`AI-OPS-98`).
- Missing piece: bounded retention for long-running heartbeat history while preserving incident traceability.

## What was delivered

- Added compaction lane for product KPI heartbeat:
  - `scripts/report_citizen_product_kpis_heartbeat_compaction.py`
  - Preserves `failed/degraded/strict/malformed`, `contract_complete=false`, and threshold violations (`unknown_rate`, `time_to_first_answer`, `drilldown_click_rate`).
- Added raw-vs-compacted parity lane:
  - `scripts/report_citizen_product_kpis_heartbeat_compaction_window.py`
  - Enforces latest-row presence and incident-class parity in strict mode.
- Wired `just` lanes:
  - `citizen-report/check-product-kpis-heartbeat-compact`
  - `citizen-report/check-product-kpis-heartbeat-compact-window`
- Expanded product KPI heartbeat test gate:
  - `citizen-test-product-kpis-heartbeat` now includes compaction/parity tests.

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-107/evidence/just_citizen_test_product_kpis_heartbeat_20260223T160355Z.txt`
  - `docs/etl/sprints/AI-OPS-107/evidence/just_citizen_check_product_kpis_heartbeat_compact_20260223T160355Z.txt`
  - `docs/etl/sprints/AI-OPS-107/evidence/just_citizen_check_product_kpis_heartbeat_compact_window_20260223T160355Z.txt`
- JSON artifacts:
  - `docs/etl/sprints/AI-OPS-107/evidence/citizen_product_kpis_heartbeat_compaction_20260223T160355Z.json`
  - `docs/etl/sprints/AI-OPS-107/evidence/citizen_product_kpis_heartbeat_compaction_window_20260223T160355Z.json`

## What is next

- AI-OPS-108: apply the same retention/parity hardening pattern to Tailwind+MD3 drift heartbeat.
