# AI-OPS-104 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add coherence-drilldown heartbeat retention so the replay/contract trend stays bounded via incident-preserving compaction plus strict raw-vs-compacted parity checks.

Definition of done:
- Compaction lane preserves incidents (`failed/degraded/strict/malformed/contract-incomplete/threshold-violations`).
- Compaction-window lane enforces strict last-N parity for latest row and incident classes.
- Deterministic tests and `just` lanes are green.
- Sprint artifacts and evidence are published under `docs/etl/sprints/AI-OPS-104/`.
