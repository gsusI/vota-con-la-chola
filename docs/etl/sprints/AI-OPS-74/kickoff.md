# AI-OPS-74 Kickoff

Date:
- 2026-02-23

Objective:
- First-answer accelerator ranking (recommended concern/item) with explicit evidence links and deterministic fallback.

Primary lane (controllable):
- Static citizen UX contract and ranking logic; no dependency on upstream source unblock.

Acceptance gates:
- G1 Add first-answer accelerator module with deterministic scoring + fallback.
- G2 Add onboarding and inline CTA to apply recommendation in one action.
- G3 Include evidence links (`Temas` / `Evidencia`) in recommendation surfaces.
- G4 Add strict tests for module behavior and UI integration markers.
- G5 Wire local server and GH pages build for new module.

DoD:
- `just citizen-test-first-answer-accelerator` passes.
- JS/Python compile checks pass for touched files.
- Sprint evidence and report published under `docs/etl/sprints/AI-OPS-74/`.
