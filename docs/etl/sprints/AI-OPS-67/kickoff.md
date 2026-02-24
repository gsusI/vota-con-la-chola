# AI-OPS-67 Kickoff

Date:
- 2026-02-23

Objective:
- Add compaction/parity governance for initdoc heartbeat trends and surface compacted-lane health in explorer-sources.

Primary lane (controllable):
- Observability hardening for Senate initiative-doc tail, independent of upstream network behavior.

Acceptance gates:
- Add heartbeat compaction reporter preserving incidents (`failed/degraded/strict/malformed`).
- Add compaction-window parity reporter for `last N` raw rows.
- Add just report/check targets for both.
- Extend CI `initdoc-actionable-tail-contract` with strict compaction fail/pass checks.
- Expose `heartbeat_compaction_window` in status payload and render compact status pill in UI.

DoD:
- Unit tests + py_compile pass.
- `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact*` pass on current DB.
- explorer snapshot + gh-pages build + tracker gate pass.
- Sprint docs/index/pointer updated with evidence.
