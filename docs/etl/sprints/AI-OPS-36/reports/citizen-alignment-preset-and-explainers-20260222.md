# Citizen Alignment Preset + Explainers (AI-OPS-36)

Date:
- 2026-02-22

Goal:
- Improve first-answer reproducibility with shareable alignment presets while preserving privacy defaults, and increase readability with concern-level explainers.

## What shipped

1. Fragment-based preset sharing (`#preset=...`)
- Added hash preset encoding/decoding in citizen app.
- Preset payload supports:
  - `view`
  - `method`
  - `pack`
  - `concerns`
  - `concern`
- Links are generated only on explicit user action.

2. Pack-aware share actions
- Added “Link alineamiento” in pack controls.
- Added “Link pack” in onboarding.
- Added “Compartir preset” in dashboard header.

3. Preset load path
- On load, app now parses `#preset=v1:...` and applies state before concern normalization.
- Initial replace-state preserves fragment mode (no forced query rewrite) to keep sharing privacy intent intact.

4. Concern explainers
- Added `description` field for all concerns in `ui/citizen/concerns_v1.json`.
- Rendered explainers in:
  - concern list row metadata
  - dashboard selected-concern chips
  - single-concern summary header

## Validation

- Build + strict validators:
  - `docs/etl/sprints/AI-OPS-36/evidence/explorer_gh_pages_build_20260222T201941Z.txt`
- Marker checks (source + built page + copied config):
  - `docs/etl/sprints/AI-OPS-36/evidence/citizen_alignment_preset_markers_20260222T201941Z.txt`
- Tracker integrity:
  - `docs/etl/sprints/AI-OPS-36/evidence/tracker_gate_20260222T201956Z.txt`

Outcome:
- Citizen now supports cleaner alignment preset sharing and richer context for concern selection without adding backend requirements.
