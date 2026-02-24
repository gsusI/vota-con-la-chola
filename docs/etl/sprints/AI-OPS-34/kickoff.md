# AI-OPS-34 Kickoff

Date:
- 2026-02-22

Objective:
- Implement a first-run citizen onboarding flow ("Empieza aqui") that guides users to a defensible first answer without server dependencies.

Why now:
- Citizen UX already supports alignment and audit links, but first-time users still need a clear guided path.
- This is fully controllable work that improves user-visible truth while external source blockers remain unchanged.

Primary lane (controllable):
- Add onboarding card/steps/actions in `ui/citizen/index.html` with local-first dismiss state and URL-consistent navigation.

Acceptance gates:
- New onboarding card appears for first-run users (no preferences yet) with step state and CTA buttons.
- Actions work end-to-end: recommended item select, jump to alignment view, local dismiss.
- GH Pages build remains green and includes the onboarding flow in `docs/gh-pages/citizen/index.html`.
- Tracker gate remains strict-green after docs updates.
