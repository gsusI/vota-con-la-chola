# AI-OPS-97 Kickoff

Date:
- 2026-02-23

Primary objective:
- Add heartbeat trend coverage for explainability outcomes so regressions in explainability adoption are detectable via bounded, strict window checks.

Definition of done:
- Heartbeat reporter appends deduped JSONL rows from explainability digest.
- Window reporter validates strict last-N thresholds (`failed`, `degraded`, `contract_incomplete`) and latest-row completeness.
- Dedicated tests and `just` lanes are green and integrated into release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-97/`.
