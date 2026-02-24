# AI-OPS-103 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add a visual-drift heartbeat lane for Tailwind+MD3 so source/published parity is tracked over time with strict last-N parity guarantees.

Definition of done:
- Visual-drift heartbeat is append-only, deduplicated, and strict-checkable.
- Window lane enforces strict parity thresholds for last-N runs and latest-run parity safety.
- Dedicated tests and `just` lanes are green and integrated in release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-103/`.
