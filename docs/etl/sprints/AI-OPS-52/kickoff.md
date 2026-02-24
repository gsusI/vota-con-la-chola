# AI-OPS-52 Kickoff

Date:
- 2026-02-22

Objective:
- Add a standalone, strict SLO digest artifact for citizen preset bundle-history checks so dashboards/agents can poll a compact status without parsing the full SLO payload.

Why now:
- AI-OPS-51 added trend-aware SLO semantics (`previous_window`, `deltas`, `risk_level`).
- We still lacked a tiny machine-readable envelope that standardizes health as `ok|degraded|failed` for low-cost polling and alerting.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_slo_digest.js` + tests + just/CI wiring + sprint evidence/docs.

Acceptance gates:
- Digest report emits a compact contract:
  - `status`, `risk_level`, `risk_reasons`, `strict_fail_reasons`
  - `key_metrics`, `key_checks`, `thresholds`, `previous_window`, `deltas`
- `--strict` exits non-zero for invalid digest or failed status.
- `just citizen-test-preset-codec` remains green.
- CI publishes a dedicated `citizen-preset-contract-bundle-history-slo-digest` artifact.
