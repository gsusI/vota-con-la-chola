# AI-OPS-70 Kickoff

Date:
- 2026-02-23

Objective:
- Add bounded retention + strict raw-vs-compacted parity for the new initdoc `cd-trend` heartbeat lane and publish resulting `cd-compact` status in API/UI.

Primary lane (controllable):
- Observability hardening for Senado initiative-doc tail, independent of upstream unblocks.

Acceptance gates:
- Add digest-heartbeat compaction reporter with incident-preserving retention.
- Add digest-heartbeat compaction-window parity reporter.
- Add just report/check targets for both.
- Extend CI `initdoc-actionable-tail-contract` with strict fail/pass checks for both.
- Expose `heartbeat_compaction_window_digest_heartbeat_compaction_window` in status payload and explorer-sources card.

DoD:
- Unit tests + py_compile pass.
- `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact*` pass.
- tracker docs + sprint pointer/index updated with evidence.
