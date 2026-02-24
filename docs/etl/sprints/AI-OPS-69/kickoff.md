# AI-OPS-69 Kickoff

Date:
- 2026-02-23

Objective:
- Add append-only heartbeat + strict window governance for initdoc compact-window digest and surface trend state in API/UI.

Primary lane (controllable):
- Observability hardening for Senate initiative-doc tail, independent of upstream unblocks.

Acceptance gates:
- Add digest-heartbeat reporter with dedupe and strict fail-on-failed status.
- Add digest-heartbeat-window reporter with strict thresholds.
- Add just report/check targets for both.
- Extend CI `initdoc-actionable-tail-contract` with strict digest-heartbeat fail/pass checks.
- Expose `heartbeat_compaction_window_digest_heartbeat_window` in status payload and explorer-sources card.

DoD:
- Unit tests + py_compile pass.
- `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat*` pass.
- tracker docs + sprint pointer/index updated with evidence.
