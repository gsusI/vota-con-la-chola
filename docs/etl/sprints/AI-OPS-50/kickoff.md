# AI-OPS-50 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict SLO gate for citizen preset contract history so CI can enforce regression-rate and clean-streak budgets over a rolling window.

Why now:
- AI-OPS-47 introduced append-only bundle history.
- AI-OPS-48 introduced last-N regression summaries.
- AI-OPS-49 introduced deterministic compaction summaries.
- We still need an explicit, threshold-based SLO contract to avoid drift in long-running history.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_slo.js` + tests + `just` target + CI artifact upload.

Acceptance gates:
- SLO report includes `regressions_in_window`, `regression_rate_pct`, `green_streak_latest`, `latest_entry_clean`, threshold values, and strict check outcomes.
- `--strict` exits non-zero when SLO thresholds are violated.
- `just citizen-test-preset-codec` includes SLO tests.
- CI uploads artifact `citizen-preset-contract-bundle-history-slo`.
- Existing strict report chain remains green.
