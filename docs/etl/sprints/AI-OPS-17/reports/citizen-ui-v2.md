# AI-OPS-17 Citizen UI/UX v2

Date: 2026-02-17
Status: DONE

## Goal
Turn the existing snapshot data into a citizen-first, audit-first static webapp (GitHub Pages) that starts from *concerns* and makes it easy to drill down into *items* and evidence.

## What Changed (v2)
- New default compare mode: when no `topic_id` is selected, panel (3) shows a **concern-level party summary** over the current items window (panel 2: limit + search).
- Honesty about method: UI labels the snapshot method via `meta.computed_method`:
  - `votes` -> "Hechos (votos)"
  - `combined` -> "Posicion (combinada)"
  - `declared` -> "Declaraciones"
- Auditability in summary cards:
  - Each party card includes **"Auditar top item"** pointing to a concrete `explorer-temas` topic link.
  - Programas remain clearly labeled as promises ("Programa") with an evidence link when present.
- Party focus (drill-down helper):
  - "Ver top items" sets a **party focus** so each item row shows that party's stance as a small chip.
  - Focus can be cleared via "Salir foco partido".

## State + Navigation Contract
- URL state: `?concern=<id>&topic_id=<n>`
  - Concern selection is always encoded.
  - Topic selection is encoded when a concrete item is selected.
  - Party focus is **ephemeral** (not encoded in URL).
- Back/forward:
  - Entering focus from a selected topic pushes history only when it clears `topic_id` (so "Back" returns to the prior topic view).
  - `popstate` clears party focus to avoid stale UI state.

## Data Contract Expectations
- Loads:
  - `./data/citizen.json` (exporter snapshot)
  - `./data/concerns_v1.json` (concern labels + keywords)
- Tagging:
  - Prefers `topics[].concern_ids` (optional v2 field) when present for reproducibility.
  - Falls back to keyword substring matching when `concern_ids` is absent.

## Build/Publish Wiring (GH Pages)
- Build command: `just explorer-gh-pages-build`
- Output:
  - `docs/gh-pages/citizen/index.html`
  - `docs/gh-pages/citizen/data/citizen.json`
  - `docs/gh-pages/citizen/data/concerns_v1.json`

Evidence:
- `docs/etl/sprints/AI-OPS-17/evidence/gh-pages-build.log`

Related:
- Explorer SQL can run on GH Pages (no backend) via HF + DuckDB WASM: `docs/etl/sprints/AI-OPS-17/reports/explorer-sql-hf-browser-mode.md`
