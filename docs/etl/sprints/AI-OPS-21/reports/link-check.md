# AI-OPS-21 Link Check (Citizen Artifacts)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

## Inputs
- Citizen datasets:
  - `docs/gh-pages/citizen/data/citizen.json`
  - `docs/gh-pages/citizen/data/citizen_votes.json`
  - `docs/gh-pages/citizen/data/citizen_declared.json`
- GH Pages targets:
  - `docs/gh-pages/explorer/index.html`
  - `docs/gh-pages/explorer-temas/index.html`
  - `docs/gh-pages/explorer-politico/index.html`
- Evidence extract:
  - `docs/etl/sprints/AI-OPS-21/evidence/link-check.json`

## Method (Pragmatic)
- For required link fields in:
  - `topics[].links`: `explorer_temas`, `explorer_positions`, `explorer_evidence`
  - `party_topic_positions[].links`: `explorer_temas`, `explorer_positions`
  - `parties[].links`: `explorer_politico_party`
- Check:
  1. link exists and is non-empty
  2. link is relative (no `http(s)://`)
  3. base target exists on disk (strip `?query` / `#fragment`, resolve under `docs/gh-pages/`)

Notes:
- `party_concern_programas[].links.explorer_evidence` is optional and may be empty when there is no extracted program evidence; UI treats it as "sin evidencia".

## Results
From `docs/etl/sprints/AI-OPS-21/evidence/link-check.json`:
- datasets: `3`
- missing_required_links_total: `0`
- non_relative_total: `0`
- missing_targets_total: `0`

## Verdict
Verdict: PASS

