# Citizen Preset Contract Bundle History SLO Digest Heartbeat Window (AI-OPS-54)

Date:
- 2026-02-22

## What shipped

- New heartbeat-window reporter:
  - `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js`
- Purpose:
  - evaluate last-N heartbeat rows with strict thresholds
  - expose counts and timestamps for failed/red incidents without scanning full history clientside

## Contract behavior

- Input:
  - heartbeat JSONL (`report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js`)
- Output:
  - JSON summary with:
    - `status_counts`, `risk_level_counts`
    - `failed_in_window`, `failed_rate_pct`
    - `first_failed_run_at`, `last_failed_run_at`
    - `first_red_risk_run_at`, `last_red_risk_run_at`
    - `latest`, `failed_streak_latest`, `checks`, `strict_fail_reasons`
- Strict mode fails on:
  - empty window
  - malformed entries
  - failed thresholds exceeded
  - latest failed status

## Pipeline and CI integration

- New just target:
  - `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-window`
- Workflow update:
  - `etl-tracker-gate.yml` now generates strict heartbeat-window report and uploads:
    - `citizen-preset-contract-bundle-history-slo-digest-heartbeat-window`
- Test suite update:
  - `just citizen-test-preset-codec` includes heartbeat-window tests.

## Evidence

- Heartbeat-window report:
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_contract_bundle_history_slo_digest_heartbeat_window_report_20260222T222156Z.json`
  - Result: `entries_in_window=2`, `status_counts={ok:2,degraded:0,failed:0}`, `strict_fail_reasons=[]`
- Validation and gates:
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_codec_tests_20260222T222156Z.txt` (`29/29`)
  - `docs/etl/sprints/AI-OPS-54/evidence/explorer_gh_pages_build_20260222T222156Z.txt`
  - `docs/etl/sprints/AI-OPS-54/evidence/tracker_gate_posttrackeredit_20260222T222156Z.txt`
- CI/just markers:
  - `docs/etl/sprints/AI-OPS-54/evidence/citizen_preset_ci_bundle_history_slo_digest_heartbeat_window_markers_20260222T222156Z.txt`

## Outcome

- Preset monitoring now has strict and lightweight alert surfaces at three levels: SLO report, digest, and heartbeat window summary.
