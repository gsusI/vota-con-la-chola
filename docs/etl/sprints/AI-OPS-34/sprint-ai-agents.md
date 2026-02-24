# AI-OPS-34 Prompt Pack

Objective:
- Ship an explicit first-run onboarding path in citizen UI so users reach "first answer" quickly and auditably.

Acceptance gates:
- `ui/citizen/index.html` includes onboarding UI block and styles.
- JS includes onboarding state/actions (`LS_ONBOARD_DISMISSED`, recommended topic CTA, alignment CTA, dismiss CTA).
- Onboarding state updates with existing URL/localStorage flow without server additions.
- GH Pages build + tracker gate evidence are captured.

Status update (2026-02-22):
- `ui/citizen/index.html`:
  - added `.onboard*` UI styles and `<div id="onboard">`
  - added onboarding local state key `LS_ONBOARD_DISMISSED`
  - added onboarding functions (`onboardingDismissed`, `setOnboardingDismissed`, `recommendedOnboardingTopic`, `renderOnboarding`)
  - onboarding appears only for first-run mode (`prefs` empty, not dismissed)
  - actions wired to existing state machine: select recommended item, switch to alignment view, dismiss guide
  - `renderCompare()` now calls `renderOnboarding()` so the guide stays in sync with user actions
- evidence:
  - `docs/etl/sprints/AI-OPS-34/evidence/explorer_gh_pages_build_20260222T200340Z.txt`
  - `docs/etl/sprints/AI-OPS-34/evidence/citizen_onboarding_markers_20260222T200340Z.txt`
  - `docs/etl/sprints/AI-OPS-34/evidence/tracker_gate_20260222T200404Z.txt`
