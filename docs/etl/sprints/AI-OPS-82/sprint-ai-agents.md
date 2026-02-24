# AI-OPS-82 Prompt Pack

Objective:
- Ship a cross-method answer stability panel in `/citizen` coherence mode (`votes`, `declared`, `combined`) with explicit uncertainty attribution.

Acceptance gates:
- Add a deterministic stability module (`cross_method_stability_v1`) with pairwise mismatch/comparable metrics.
- Render stability status + uncertainty markers in coherence view without backend dependency.
- Wire module into GH Pages build, local server routes, and mobile/perf asset contract.
- Add strict tests for module logic and UI contract markers.
- Keep citizen regression lanes green (trust/accessibility/mobile/first-answer/unknown/pack-quality/release-hardening).
- Produce evidence for strict release readiness after GH Pages build.
- Publish sprint artifacts under `docs/etl/sprints/AI-OPS-82/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.
