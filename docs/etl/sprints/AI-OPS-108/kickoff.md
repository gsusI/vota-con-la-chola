# AI-OPS-108 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add Tailwind+MD3 visual-drift heartbeat retention so trend history stays bounded via incident-preserving compaction and strict raw-vs-compacted parity checks.

Definition of done:
- Compaction lane preserves incidents (`failed/degraded/strict/malformed/contract/parity-mismatch` classes).
- Compaction-window lane enforces strict parity on last-N rows and latest-row presence.
- Deterministic tests + `just` lanes are green.
- Sprint artifacts/evidence are published under `docs/etl/sprints/AI-OPS-108/`.
