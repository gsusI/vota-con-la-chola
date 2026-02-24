# AI-OPS-35 Prompt Pack

Objective:
- Ship concern packs (preset multi-concern bundles) in citizen UI with explicit tradeoff messaging and URL-share reproducibility.

Acceptance gates:
- `ui/citizen/concerns_v1.json` includes normalized `packs` contract.
- `ui/citizen/index.html` adds pack controls and active-pack state machine.
- URL state includes `concern_pack` alongside `concerns_ids` for reproducibility.
- Onboarding can apply a recommended pack.
- GH Pages build + tracker gate evidence captured.

Status update (2026-02-22):
- `ui/citizen/concerns_v1.json`:
  - added 4 packs (`hogar_bolsillo`, `servicios_publicos`, `seguridad_estado`, `campo_industria`) with explicit `tradeoff`
- `ui/citizen/index.html`:
  - added concern-pack UI area (`#concernPackTags`, `#concernPackHint`)
  - added pack state fields (`concernPacks`, `activeConcernPackId`)
  - added URL param support (`concern_pack`) in read/write state
  - added pack helpers (`normalizeConcernPackConfig`, `detectConcernPackForSelection`, `applyConcernPack`, `renderConcernPackTags`, `recommendedConcernPack`)
  - onboarding now supports `Aplicar pack rapido`
  - dashboard header now surfaces active pack + tradeoff text
- evidence:
  - `docs/etl/sprints/AI-OPS-35/evidence/explorer_gh_pages_build_20260222T201122Z.txt`
  - `docs/etl/sprints/AI-OPS-35/evidence/citizen_concern_pack_markers_20260222T201122Z.txt`
  - `docs/etl/sprints/AI-OPS-35/evidence/tracker_gate_20260222T201137Z.txt`
