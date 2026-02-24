# AI-OPS-81 Prompt Pack

Objective:
- Establish a release-hardening baseline for `/citizen` with a deterministic regression suite and a strict source-vs-published parity checklist.

Acceptance gates:
- Add a machine-readable release-hardening reporter with strict mode.
- Validate parity for core citizen assets between `ui/citizen` and `docs/gh-pages/citizen`.
- Validate published snapshot/config readiness (`citizen.json`, `concerns_v1.json`) in the same checklist.
- Add strict tests for pass/fail parity behavior.
- Add `just` wrappers for tests, report, strict check, and bundled regression suite.
- Produce evidence showing drift detection before build and green strict check after build.
- Publish sprint artifacts under `docs/etl/sprints/AI-OPS-81/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
