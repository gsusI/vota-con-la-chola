# AI-OPS-71 Kickoff

Date:
- 2026-02-23

Objective:
- Add compact digest (`status` + `risk_level`) over the `cd-compact` parity lane and publish it in API/UI for lightweight polling and triage.

Primary lane (controllable):
- Observability contract hardening for Senado initiative-doc tail, independent of upstream unblocks.

Acceptance gates:
- Add compaction-window digest reporter for the `cd-compact` lane.
- Add just report/check targets for that digest.
- Extend CI `initdoc-actionable-tail-contract` with strict fail/pass checks for this digest.
- Expose `heartbeat_compaction_window_digest_heartbeat_compaction_window_digest` in status payload and explorer-sources card.

DoD:
- Unit tests + py_compile pass.
- `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest` passes.
- tracker docs + sprint pointer/index updated with evidence.
