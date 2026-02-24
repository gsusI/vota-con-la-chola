# AI-OPS-92 Kickoff

Date:
- 2026-02-23

Primary objective:
- Make explainability adoption measurable in `/citizen` by tracking glossary/help-copy interactions and shipping a strict outcomes digest contract.

Definition of done:
- `/citizen` emits explainability interaction telemetry for glossary open, glossary term interaction, and help-copy interaction.
- Telemetry is exportable via local debug APIs for reproducible checks.
- Reporter contract emits strict `ok|degraded|failed` with adoption completeness thresholds.
- Tests + `just` lanes are green and integrated into release regression.
- Sprint evidence/docs are published under `docs/etl/sprints/AI-OPS-92/`.
