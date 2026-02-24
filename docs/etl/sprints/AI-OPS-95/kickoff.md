# AI-OPS-95 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add retention hardening for the mobile observability heartbeat using incident-preserving compaction plus strict raw-vs-compacted window parity.

Definition of done:
- Compaction reporter writes compacted JSONL with strict incident preservation checks.
- Compaction-window parity reporter enforces latest-row + incident parity in last-N window.
- Tests and `just` lanes are green and wired into release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-95/`.
