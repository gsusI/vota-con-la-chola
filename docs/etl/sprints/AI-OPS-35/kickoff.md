# AI-OPS-35 Kickoff

Date:
- 2026-02-22

Objective:
- Add concern-pack onboarding to `/citizen` so users can apply defensible multi-concern bundles quickly and keep URL-reproducible state.

Why now:
- AI-OPS-34 solved first-run guidance but users still had to build multi-concern sets manually.
- Pack presets are fully controllable work that improve time-to-answer without backend complexity.

Primary lane (controllable):
- Extend `ui/citizen/concerns_v1.json` with `packs` and wire pack UI + URL state (`concern_pack`) in `ui/citizen/index.html`.

Acceptance gates:
- Concern packs are defined in config and copied to GH Pages artifacts.
- UI exposes pack buttons with active state and tradeoff hint.
- Applying a pack updates selection, URL state, and dashboard comparators deterministically.
- GH Pages build + strict tracker gate remain green with evidence.
