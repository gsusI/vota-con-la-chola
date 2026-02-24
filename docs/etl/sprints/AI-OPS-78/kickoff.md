# AI-OPS-78 Kickoff

Date:
- 2026-02-23

Primary objective:
- Improve concern-pack guidance quality in `/citizen` with explicit, deterministic quality scoring and weak-pack signaling.

Scope:
- `scripts/report_citizen_concern_pack_quality.py`
- `ui/citizen/index.html`
- `justfile` citizen quality targets + GH Pages artifact generation
- script/UI contract tests

Out-of-scope:
- ETL connector/source expansion
- stance computation model changes
- backend/API runtime dependencies

Definition of done:
- Pack-quality report contract exists and passes strict mode on repo artifacts.
- `/citizen` surfaces pack quality/weak signals from published artifact.
- New tests pass and existing citizen regressions stay green.
- Sprint evidence + closeout are published in `docs/etl/sprints/AI-OPS-78/`.
