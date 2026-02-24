# AI-OPS-94 Prompt Pack

Objective:
- Ship coherence drilldown backend parity v2 so `/citizen` coherence links open `explorer-temas` with party-scoped evidence and matching URL semantics.

Acceptance gates:
- Add `party_id` filter support to coherence APIs (at minimum `/api/topics/coherence/evidence`; include summary endpoint for parity).
- Include resolved party metadata (`party_id`, `party_name`) in coherence evidence payload rows.
- Align `ui/graph/explorer-temas.html` URL contract with `/citizen` links (`party_id`, `bucket`, `view=coherence`, `source=citizen_coherence`).
- Auto-open coherence evidence mode from URL intent without requiring manual clicks.
- Add deterministic tests for backend party filter and explorer URL-contract markers.
- Keep `just citizen-release-regression-suite` and `just explorer-gh-pages-build` green.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`coherence_party_filter=pass`, `url_contract=pass`, regression/build green).
