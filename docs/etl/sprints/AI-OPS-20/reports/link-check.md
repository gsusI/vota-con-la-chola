# AI-OPS-20 Link Check (Citizen Snapshot)

Date: 2026-02-17  
Sprint: `AI-OPS-20`

## Inputs
- `docs/gh-pages/citizen/data/citizen.json`
- `docs/gh-pages/explorer/index.html`
- `docs/gh-pages/explorer-temas/index.html`
- `docs/gh-pages/explorer-politico/index.html`
- Evidence extract: `docs/etl/sprints/AI-OPS-20/evidence/link-check.json`

## Method (Pragmatic)
- For required link fields in:
  - `topics[].links`: `explorer_temas`, `explorer_positions`, `explorer_evidence`
  - `party_topic_positions[].links`: `explorer_temas`, `explorer_positions`
  - `parties[].links`: `explorer_politico_party`
- Check:
  1. link exists and is a non-empty string
  2. link is relative (no `http(s)://`)
  3. base target exists on disk (strip `?query` / `#fragment`, resolve under `docs/gh-pages/`)

Notes:
- `party_concern_programas[].links.explorer_evidence` may be empty when there is no extracted program evidence; UI treats it as "sin evidencia".
- This does not validate that query params return rows; it validates that audit navigation targets exist (static).

## Results (2026-02-17 build)
From `docs/etl/sprints/AI-OPS-20/evidence/link-check.json`:
- links_total: `3937`
- non_relative_total: `0`
- unique_targets_total: `3`
- broken_targets: `0`

## Compatibility Notes (Query Params)
- `../explorer-temas/` now accepts both:
  - `?set=<id>&topic=<id>` (legacy)
  - `?topic_set_id=<id>&topic_id=<id>` (citizen exporter contract)
- `../explorer-politico/` now accepts `?party_id=<id>` as an alias for `?team=<id>` (party focus).

## Verdict
Verdict: PASS

