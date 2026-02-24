# AI-OPS-78 Prompt Pack

Objective:
- Ship a concern-pack quality loop for `/citizen` with deterministic heuristics, weak-pack flags, and strict machine-checkable gates.

Acceptance gates:
- Add a machine-readable pack-quality report script with `quality_score`, `weak`, and `weak_reasons`.
- Wire strict gate support (`--strict`) with thresholded weak-pack budget.
- Publish optional static artifact `citizen/data/concern_pack_quality.json` in GH Pages build.
- Expose pack-quality/weak markers in `/citizen` UI without breaking share/onboarding flows.
- Add strict tests for script and UI contract.
- Keep preset/mobile/first-answer citizen regression checks green.
- Publish sprint evidence and closeout under `docs/etl/sprints/AI-OPS-78/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
