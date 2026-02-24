# Citizen Onboarding "Start Here" (AI-OPS-34)

Date:
- 2026-02-22

Goal:
- Reduce first-use friction in `/citizen` by guiding users through a deterministic 3-step path toward an auditable answer.

## What shipped

1. New onboarding card in header
- Added a new `#onboard` block with explicit guidance for first-run users.
- Steps are shown as status tags:
  - concern selected
  - item selected
  - alignment view selected

2. Actionable CTAs
- `Abrir item recomendado`: selects deterministic first topic for current concern.
- `Ir a alineamiento`: switches `viewMode` to `alignment` (and ensures topic selection when available).
- `Ocultar guia`: stores local dismiss flag in `localStorage`.

3. Local-first behavior
- Dismiss state stored in `LS_ONBOARD_DISMISSED`.
- Onboarding is shown only when preferences are still empty (`state.prefs.size === 0`) and not dismissed.
- Existing shareable URL state and local preference behavior remain unchanged.

## Validation

- GH Pages build + snapshot validation passed:
  - `docs/etl/sprints/AI-OPS-34/evidence/explorer_gh_pages_build_20260222T200340Z.txt`
- UI marker checks confirm source + built page include onboarding code:
  - `docs/etl/sprints/AI-OPS-34/evidence/citizen_onboarding_markers_20260222T200340Z.txt`
- Strict tracker gate remains green:
  - `docs/etl/sprints/AI-OPS-34/evidence/tracker_gate_20260222T200404Z.txt`

Outcome:
- First-time users now get a concrete, bounded path to start using citizen alignment/audit flows without adding backend complexity.
