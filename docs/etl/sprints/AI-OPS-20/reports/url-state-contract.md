# Citizen URL State Contract (AI-OPS-20)

Status:
- `DRAFT`

Goals:
- Shareable citizen views (URL restores state).
- Backward compatible with v2 links.
- Stable, minimal params (avoid encoding ephemeral UI filters unless needed).

## Query params (proposed)

Backward-compat (existing):
- `concern=<id>`: active concern id (detail mode).
- `topic_id=<int>`: active topic id within active concern.
- `citizen=<path>`: override dataset path (advanced; keep).
- `concerns=<path>`: override concerns config path (advanced; keep).

New (v3):
- `concerns_ids=<csv>`: selected concerns (2-6), comma-separated, e.g. `vivienda,sanidad,empleo`.
- `party_id=<int>`: party focus (0 or missing = none).
- `method=<token>`: desired method, e.g. `votes|combined|declared` (only if method artifact exists).
- `view=<token>`: `detail|dashboard` (default: `detail`).

## Precedence + fallbacks
- Dataset selection:
  - If `citizen` is provided, use it (power-user override).
  - Else if `method` is provided:
    - `combined` -> `./data/citizen.json`
    - `votes` -> `./data/citizen_votes.json`
    - `declared` -> `./data/citizen_declared.json`
  - Else use default `./data/citizen.json`.
- Selected concerns:
  - If `concerns_ids` is present, parse + validate ids and use it.
  - Else if `concern` is present, set `concerns_ids=[concern]`.
  - Else fall back to localStorage; else pick a deterministic default (the concern with most tagged topics).
- Active concern:
  - If `concern` is present, use it if valid; otherwise pick the first from `concerns_ids`.
  - Active concern must always be a member of `concerns_ids`.
- Party focus:
  - If `party_id` is present and valid, enable focus; else none.
- Topic:
  - If `topic_id` is present, keep only if it belongs to the active concern’s topic set (else clear).

## History push rules
- Use `replaceState` for "non-semantic" state changes (e.g., internal rerenders).
- Use `pushState` for user navigation events:
  - changing active concern
  - selecting a topic
  - toggling party focus
  - switching method

## Examples

1) Default (no state):
- `/citizen/`

2) Single concern + topic (backward compatible):
- `/citizen/?concern=vivienda&topic_id=12`

3) Multi-concern dashboard + party focus:
- `/citizen/?concerns_ids=vivienda,sanidad&party_id=1`

4) Multi-concern + method toggle:
- `/citizen/?concerns_ids=vivienda,educacion&method=votes`

5) Full state:
- `/citizen/?concerns_ids=vivienda,sanidad&concern=vivienda&topic_id=12&party_id=1&method=combined&view=dashboard`
