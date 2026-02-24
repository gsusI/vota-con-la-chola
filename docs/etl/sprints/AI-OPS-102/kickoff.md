# AI-OPS-102 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add release-trace heartbeat retention so freshness/staleness incidents remain auditable while heartbeat history stays bounded through reproducible compaction.

Definition of done:
- Release-trace heartbeat compaction is reproducible and strict-checkable with incident-preservation guarantees.
- Compaction-window parity enforces strict raw-vs-compacted checks for latest row and incident parity in `last N`.
- Dedicated tests and `just` lanes are green and integrated in release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-102/`.
