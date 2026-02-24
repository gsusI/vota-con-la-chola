# AI-OPS-54 Kickoff

Date:
- 2026-02-22

Objective:
- Add a rolling window reporter for digest-heartbeat NDJSON (`last N`) with strict thresholds and first/last failed/red timestamps for fast alerting.

Why now:
- AI-OPS-53 added append-only heartbeat NDJSON.
- We still needed a lightweight strict summary over that stream to avoid client-side scans and enable deterministic alert checks.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js` + tests + just/CI wiring + sprint evidence/docs.

Acceptance gates:
- New heartbeat-window report includes:
  - `status_counts`, `risk_level_counts`
  - `failed_in_window`, `failed_rate_pct`
  - `first_failed_run_at`/`last_failed_run_at`
  - `first_red_risk_run_at`/`last_red_risk_run_at`
  - `latest`, `checks`, `strict_fail_reasons`
- `--strict` fails on threshold breaches, malformed rows, empty window, or latest failed status.
- `just citizen-test-preset-codec` remains green.
- CI publishes `citizen-preset-contract-bundle-history-slo-digest-heartbeat-window` artifact.
