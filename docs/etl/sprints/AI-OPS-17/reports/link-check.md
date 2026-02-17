# AI-OPS-17 Link Check (Citizen Snapshot)

Date: 2026-02-17  
Sprint: `AI-OPS-17`

## Inputs
- `docs/gh-pages/citizen/data/citizen.json`
- `docs/gh-pages/explorer/index.html`
- `docs/gh-pages/explorer-temas/index.html`

## Method (Pragmatic)
- For required link fields in:
  - `topics[].links`: `explorer_temas`, `explorer_positions`, `explorer_evidence`
  - `party_topic_positions[].links`: `explorer_temas`, `explorer_positions`
- Check:
  1. link exists and is a non-empty string
  2. link base target exists on disk (strip `?query` / `#fragment`, resolve relative to `docs/gh-pages/citizen/`)

Notes:
- `party_concern_programas[].links.explorer_evidence` may be empty when there is no extracted program evidence; UI treats it as "sin evidencia".
- This does not validate that query params return rows; it validates that audit navigation targets exist (static).

## Results (2026-02-17 build)
- topics: `111`
- party_topic_positions: `1776`
- missing_required_links: `0`
- broken_targets: `0`

## Verdict
Verdict: PASS

