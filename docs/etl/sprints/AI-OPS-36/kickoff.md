# AI-OPS-36 Kickoff

Date:
- 2026-02-22

Objective:
- Add pack-aware alignment preset sharing via URL fragment plus concern-level explainers to improve interpretability and privacy-preserving shareability.

Why now:
- AI-OPS-35 introduced concern packs, but reusable alignment entry links were still ad-hoc.
- We need explicit opt-in sharing that avoids leaking preference-like state in query params.

Primary lane (controllable):
- Extend citizen UI with `#preset=...` share/load flow and render concern descriptions from config in key decision surfaces.

Acceptance gates:
- Citizen UI can generate alignment preset links as fragment (`#preset=...`) from pack/dashboard/onboarding actions.
- App can load preset state from hash deterministically (`view/method/pack/concerns/active concern`).
- Concern descriptions render in concern list and comparison summaries.
- GH Pages build + tracker gate remain green with evidence.
