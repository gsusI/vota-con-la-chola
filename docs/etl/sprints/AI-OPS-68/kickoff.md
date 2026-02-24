# AI-OPS-68 Kickoff

Date:
- 2026-02-23

Objective:
- Ship compaction-window digest governance for initdoc actionable-tail parity and expose it in API/UI/CI contracts.

Primary lane (controllable):
- Observability hardening for Senate initiative-doc tail without depending on upstream network changes.

Acceptance gates:
- Add compaction-window digest reporter (`ok/degraded/failed`, `risk_level`, `risk_reasons`, `strict_fail_reasons`).
- Add just report/check targets for digest lane.
- Extend CI `initdoc-actionable-tail-contract` with strict digest fail/pass checks.
- Expose `heartbeat_compaction_window_digest` in status payload and explorer-sources card.

DoD:
- Unit tests + py_compile pass.
- `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest` passes on current DB.
- tracker docs + sprint index/pointer updated with evidence.
