# AI-OPS-96 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add strict visual drift digest coverage for Tailwind+MD3 so source/published parity regressions are detected immediately in reproducible artifacts.

Definition of done:
- Drift digest reporter writes machine-readable parity/marker status JSON and supports strict fail mode.
- Dedicated deterministic tests cover strict pass and strict fail paths.
- `just` lanes are green and integrated with the existing release regression flow.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-96/`.
