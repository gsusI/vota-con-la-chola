# AI-OPS-21 Citizen URL State Contract (Coverage + Coherence)

Status:
- `DONE`

Baseline contract:
- `docs/etl/sprints/AI-OPS-20/reports/url-state-contract.md`

This sprint extends the contract with a new `view` mode while preserving backward compatibility.

## Query params

Backward-compat (existing):
- `concern=<id>`: active concern id (detail mode).
- `topic_id=<int>`: active topic id.
- `citizen=<path>`: override dataset path (advanced).
- `concerns=<path>`: override concerns config path (advanced).

v3 (existing):
- `concerns_ids=<csv>`: selected concerns (1-6), comma-separated.
- `party_id=<int>`: party focus (optional).
- `method=<token>`: base dataset selection: `combined|votes|declared`.
- `view=<token>`: view mode.

v4 (AI-OPS-21):
- extend `view` to include:
  - `view=coherence` (Coverage + Coherence view)

## Precedence + fallbacks
- Dataset selection for base views (`detail|dashboard`):
  - If `citizen` is provided, use it (power-user override).
  - Else if `method` is provided:
    - `combined` -> `./data/citizen.json`
    - `votes` -> `./data/citizen_votes.json`
    - `declared` -> `./data/citizen_declared.json`
  - Else use default `./data/citizen.json`.

- Coherence view (`view=coherence`):
  - Always compares `votes` vs `declared` datasets.
  - Recommended implementation: lazy-load both method datasets only when coherence view is active.
  - `method` remains a “base method” preference for other views; coherence ignores it (must be explicit in UI copy).

- Selected concerns:
  - If `concerns_ids` is present, parse + validate ids and use it.
  - Else if `concern` is present, set `concerns_ids=[concern]`.
  - Else fall back to localStorage; else pick a deterministic default.

- Party focus:
  - If `party_id` is present and valid, enable focus; else none.

## History push rules
- Use `pushState` for semantic navigation:
  - changing `view`
  - selecting/removing concerns
  - setting/clearing party focus
  - selecting a topic
- Use `replaceState` for rerenders and internal normalization.

## Examples
- Coverage + coherence:
  - `/citizen/?concerns_ids=vivienda,sanidad&view=coherence`
- Coherence with party focus:
  - `/citizen/?concerns_ids=educacion,seguridad_justicia&view=coherence&party_id=1`
- Backward compatible detail URL:
  - `/citizen/?concern=vivienda&topic_id=12`
