# Citizen Preset Contract Bundle History SLO Digest Heartbeat Compaction Window Digest Heartbeat + Window (AI-OPS-58)

Date:
- 2026-02-22

## What shipped

- New compact-window digest heartbeat append reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js`
- New compact-window digest heartbeat window reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js`

## Contract behavior

- Heartbeat reporter:
  - Input: compact-window digest JSON
  - Output: append-dedupe NDJSON row with `status/risk_level`, `missing_in_compacted_in_window`, `incident_missing_in_compacted`, coverage metrics, and strict/risk reason counts.
  - Strict mode fails on invalid row or `status=failed`.
- Heartbeat window reporter:
  - Input: digest heartbeat NDJSON
  - Output: last-N summary with:
    - `status_counts`, `risk_level_counts`
    - `failed_in_window`, `degraded_in_window`
    - `failed_rate_pct`, `degraded_rate_pct`
    - first/last failed/degraded timestamps
    - strict checks + `strict_fail_reasons`
  - Strict thresholds:
    - `max_failed`, `max_failed_rate_pct`
    - `max_degraded`, `max_degraded_rate_pct`

## Pipeline and CI integration

- New just targets:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat`
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window`
- Workflow update:
  - `.github/workflows/etl-tracker-gate.yml` now generates strict compact-window digest heartbeat + window reports and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat`
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat-window`
- Test suite update:
  - `just citizen-test-preset-codec` includes both new test files.

## Evidence

- Digest + heartbeat append:
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_report_20260222T225515Z.json` (`status=ok`, `risk_level=green`)
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_report_20260222T225515Z.json` (`appended=true`, `history_size_after=1`)
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_tail_20260222T225515Z.jsonl`
- Heartbeat window:
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window_report_20260222T225515Z.json`
  - Result: `failed_in_window=0`, `degraded_in_window=0`, `strict_fail_reasons=[]`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-58/evidence/citizen_preset_codec_tests_20260222T225515Z.txt` (`43/43`)
  - `docs/etl/sprints/AI-OPS-58/evidence/explorer_gh_pages_build_20260222T225515Z.txt`
  - `docs/etl/sprints/AI-OPS-58/evidence/tracker_gate_posttrackeredit_20260222T225515Z.txt`

## Outcome

- Compact-window digest lane now has both append-only heartbeat trend and strict last-N health summary, making downstream alert polling simpler and more stable.
