# AI-OPS-51 Kickoff

Date:
- 2026-02-22

Objective:
- Extend preset history SLO reporting with previous-window deltas and a deterministic risk-level enum for lightweight dashboard consumption.

Why now:
- AI-OPS-50 introduced strict SLO checks.
- We still need trend context and a compact severity signal to triage regressions quickly without manual interpretation.

Primary lane (controllable):
- Upgrade `scripts/report_citizen_preset_contract_bundle_history_slo.js` + tests + docs/evidence.

Acceptance gates:
- Report includes previous-window summary (`available`, core metrics) and `deltas` (`regressions`, `regression_rate_pct`, `green_streak_latest`).
- Report emits `risk_level` in `{green, amber, red}` with `risk_reasons`.
- Strict behavior remains unchanged (`strict_fail_reasons` governs non-zero exit).
- `just citizen-test-preset-codec` stays green.
- CI SLO artifact remains machine-readable and backward-compatible for strict consumers.
