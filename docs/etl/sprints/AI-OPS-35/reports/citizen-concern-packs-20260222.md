# Citizen Concern Packs (AI-OPS-35)

Date:
- 2026-02-22

Goal:
- Reduce manual setup friction for multi-concern comparison by providing reproducible concern packs.

## What shipped

1. Pack contract in concerns config
- `ui/citizen/concerns_v1.json` now includes `packs` with:
  - `id`
  - `label`
  - `concern_ids`
  - `tradeoff`

2. Pack UI + behavior
- Added pack controls in concern panel:
  - `#concernPackTags`
  - `#concernPackHint`
- Clicking a pack applies a deterministic concern set and switches to dashboard view.
- Active pack auto-syncs with current selection (manual edits become `personalizado`).

3. URL reproducibility
- Added `concern_pack` URL state parameter.
- Existing `concerns_ids` remains canonical for exact selection replay.

4. Onboarding integration
- First-run onboarding now includes `Aplicar pack rapido` using a deterministic recommended pack.

## Validation

- Build + snapshots/validators:
  - `docs/etl/sprints/AI-OPS-35/evidence/explorer_gh_pages_build_20260222T201122Z.txt`
- Marker checks in source and built pages:
  - `docs/etl/sprints/AI-OPS-35/evidence/citizen_concern_pack_markers_20260222T201122Z.txt`
- Tracker integrity:
  - `docs/etl/sprints/AI-OPS-35/evidence/tracker_gate_20260222T201137Z.txt`

Outcome:
- Users can now start from meaningful concern bundles in one click, while preserving auditability and shareable state in a static-only architecture.
