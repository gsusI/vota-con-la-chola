# AI-OPS-81 Kickoff

Date:
- 2026-02-23

Primary objective:
- Harden `/citizen` release readiness by making regressions + publish parity machine-checkable in one repeatable lane.

Scope:
- `scripts/report_citizen_release_hardening.js`
- `tests/test_report_citizen_release_hardening.js`
- `justfile` release hardening targets
- sprint evidence for pre-build drift and post-build strict-green state

Out-of-scope:
- changes to stance logic or ETL ingestion behavior
- new UI feature surfaces
- backend runtime dependencies

Definition of done:
- Release hardening report exists with strict fail/pass behavior.
- Core citizen asset parity is checked deterministically.
- Citizen regression suite target exists and passes.
- `explorer-gh-pages-build` + strict release check produce `release_ready=true`.
- Sprint evidence + closeout are published in `docs/etl/sprints/AI-OPS-81/`.
