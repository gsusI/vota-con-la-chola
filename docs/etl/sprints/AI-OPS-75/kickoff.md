# AI-OPS-75 Kickoff

Date:
- 2026-02-23

Primary objective:
- Reduce user confusion around `unknown` by making causes explicit (`incierto` vs `sin_senal`) and showing a direct next step to reduce uncertainty.

Scope:
- Citizen UI only (static-first, no backend dependency).
- Build/server/test wiring for publish parity and reproducibility.

Out-of-scope:
- New ETL sources or changes to stance computation.
- Telemetry schema changes.

Definition of done:
- Unknown explainability module + UI wiring merged.
- Deterministic tests pass (`just citizen-test-unknown-explainability`).
- Existing first-answer flow remains green.
- Evidence files recorded under `docs/etl/sprints/AI-OPS-75/evidence`.
