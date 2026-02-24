# AI-OPS-36 Prompt Pack

Objective:
- Ship privacy-preserving, pack-aware alignment preset sharing and concern explainers in citizen UI.

Acceptance gates:
- `ui/citizen/index.html` implements fragment preset codec/load path (`#preset=v1:...`).
- Share actions exist in pack controls, onboarding, and dashboard (explicit opt-in only).
- `ui/citizen/concerns_v1.json` includes concern-level `description` fields and UI renders them.
- GH Pages build and tracker gate evidence are captured.

Status update (2026-02-22):
- `ui/citizen/index.html`:
  - added preset hash codec (`encodePresetPayload`, `decodePresetPayload`, `readPresetFromHash`, `buildAlignmentPresetShareUrl`)
  - added clipboard helper + share actions:
    - pack controls (`data-pack-share`)
    - onboarding (`data-onboard-pack-share`)
    - dashboard (`data-dashboard-share-preset`)
  - added preset load state (`presetLoadedFrom`, `presetLoadError`, `hashPresetActive`) and fragment-preserving initial URL handling
  - concern descriptions now render in concern rows, dashboard explainer chips, and concern summary header
- `ui/citizen/concerns_v1.json`:
  - added `description` for each concern
- evidence:
  - `docs/etl/sprints/AI-OPS-36/evidence/explorer_gh_pages_build_20260222T201941Z.txt`
  - `docs/etl/sprints/AI-OPS-36/evidence/citizen_alignment_preset_markers_20260222T201941Z.txt`
  - `docs/etl/sprints/AI-OPS-36/evidence/tracker_gate_20260222T201956Z.txt`
