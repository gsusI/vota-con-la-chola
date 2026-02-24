# AI-OPS-73 Kickoff

Date:
- 2026-02-23

Objective:
- Onboarding funnel hardening (`Empieza aqui`) with strict contract tests and direct jump to the best next action.

Primary lane (controllable):
- Static `/citizen` UX contract improvements independent of upstream ETL blockers.

Acceptance gates:
- G1 Introduce explicit onboarding funnel state machine contract.
- G2 Add direct CTA for best next action.
- G3 Add strict tests for funnel order + UI integration markers.
- G4 Ensure local server route and GH Pages build include onboarding module.

DoD:
- `just citizen-test-onboarding-funnel` passes.
- Compile checks pass for touched Python/JS files.
- Sprint evidence recorded under `docs/etl/sprints/AI-OPS-73/evidence/`.
