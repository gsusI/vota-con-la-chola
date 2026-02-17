# Citizen UX v2 Spec (Concern-First)

Date: 2026-02-17  
Sprint: `AI-OPS-17`

## Goal
Make the citizen app answer the primary question fast:
- "Que hizo cada partido sobre esta preocupacion?"

Without losing the auditability contract:
- every stance shown must have a path to drill down (Temas/Explorer SQL)
- unknown/no_signal stays explicit
- static GH Pages only, bounded JSON artifacts

## Inputs (Current)
- UI:
  - `ui/citizen/index.html`
  - `ui/citizen/concerns_v1.json`
- Data (built artifact):
  - `docs/gh-pages/citizen/data/citizen.json`

Citizen JSON contract reference:
- `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`

Programas lane reference:
- `docs/etl/sprints/AI-OPS-19/reports/citizen-programas-ui.md`

## Primary Flow (New Default)

### Flow: Concern -> Party Summary -> Party Drill-Down -> Audit
1. User selects a concern (left column).
2. Middle column shows the "items" list for that concern (already exists).
3. Right column, when **no topic is selected**, shows a **party summary view** for the concern:
   - Hechos summary (derived from item stances)
   - Programa stance (if present)
   - At least one audit link (see Audit rules)
4. User clicks "Ver top items" on a party:
   - the middle column list stays, but rows show that party stance inline (party focus)
   - user clicks an item to open the existing per-topic compare view (topic selected)
5. User audits by clicking links that open Temas/Explorer SQL in new tabs.

## UI States

### S0: Loading / Error
- Loading: show chips with "cargando datos..."
- Error: show banner with HTTP error summary.

### S1: Concern Selected, No Topic Selected (New Summary Mode)
- Right column shows concern-level party summary list.
- The summary is computed over **the same items currently listed** in the middle column (respecting `topicLimit` and search filters).
- Each party card contains:
  - Hechos summary stance + supporting counts
  - Programa stance for this concern (existing data)
  - "Ver top items" (party focus)
  - Audit link(s) (see below)

### S2: Concern Selected + Topic Selected (Existing Compare Mode)
- Right column shows existing per-topic party compare cards (keep current UX).
- Each party card still shows Programa stance for the concern (existing).

### S3: Party Focus (Party Drill-Down)
Triggered from S1:
- Middle column item rows display a stance chip for the focused party.
- Provide an explicit "Salir foco partido" action.
- Topic click still opens per-topic compare (S2).

## Summary Computation (Hechos)

Summary window:
- Use exactly the item rows currently in the middle column after filters:
  - active concern filter (required)
  - topic search filter (if set)
  - topic limit (20/40/60)

Per party, compute:
- `items_total`: number of items in the window
- counts by stance over those items:
  - `support`, `oppose`, `mixed`, `unclear`, `no_signal`
- `clear_total`: `support + oppose + mixed`
- `coverage_items_ratio`: `clear_total / items_total` (0..1)
- `confidence_avg`: average of per-item `confidence` for items where stance != `no_signal` (0..1)

Derive `hechos_summary_stance`:
- if `items_total == 0` => `no_signal` (render as "Sin senal")
- else if `clear_total == 0`:
  - if any `unclear > 0` => `unclear`
  - else => `no_signal`
- else:
  - if `support > 0` and `oppose > 0` => `mixed` (conflict across items)
  - else if `support >= oppose` => `support`
  - else => `oppose`

UI must render the distribution (counts) next to the summary stance so users can see ambiguity.

Honesty note in UI:
- "Resumen calculado sobre N items (columna 2). No es un ranking; es un conteo/derivado."

## Method Labeling (Critical Honesty)
The citizen artifact has `meta.computed_method` for the exported party-topic positions.

UI labeling rules:
- If `meta.computed_method == 'votes'`: label lane as `Hechos (votos)`.
- If `meta.computed_method == 'combined'`: label lane as `Posicion (combinada)`, and explain in help text:
  - "Incluye votos + evidencia declarativa cuando existe."
- If `meta.computed_method == 'declared'`: label lane as `Declaraciones`.

Do not use the word "hechos" when method is not `votes`.

## Programas ("Programa") Rules
Programas stance display stays keyed by `(concern_id, party_id)`:
- show stance chip + confidence
- if `links.explorer_evidence` exists, show "Evidencia (programa)" link
- if absent, show "sin evidencia"

## Audit Rules (Must-Pass Gate G2)

### Summary Cards (S1)
Each party summary card MUST provide at least one concrete audit link under repo control.

Implementation rule:
- Always include an "Auditar top item" link that points to the most relevant item in the summary window:
  - pick the first item in the current item list where stance is `support|oppose|mixed` for that party
  - fallback: first item in the list
  - link target: that item's `links.explorer_temas` (or `links.explorer_positions`)

If Programa evidence exists, also include:
- "Evidencia (programa)" link (already available).

### Topic Compare Cards (S2)
Keep existing audit links:
- topic: Temas + Evidencia (SQL)
- party-topic: Ver posiciones

## Concern Keywords (v1)
For AI-OPS-17 v2 UX work, keep `ui/citizen/concerns_v1.json` unchanged unless a measurable regression is found (many concerns with zero items after export changes).

If changes become necessary, update only:
- keywords (additive, small)
- do not change concern ids (stable keys)

## UI Acceptance Checklist (L1 Smoke Test)

Run/build:
1. `just explorer-gh-pages-build`
2. Serve locally:
   - `cd docs/gh-pages && python3 -m http.server 8000`
   - open `http://localhost:8000/citizen/`

Checks:
1. Default concern auto-selects (not blank).
2. With no topic selected:
   - party summary view renders
   - each party card shows hechos summary + distribution counts
   - each party card shows Programa chip (even if no_signal)
3. Click "Ver top items" on a party:
   - topic rows show that party stance inline
   - "Salir foco partido" clears focus
4. Click a topic:
   - switches to per-topic compare mode (existing)
   - audit links open and are not 404:
     - Temas
     - Explorer SQL (positions/evidence)
5. Toggle `topicLimit` 20/40/60:
   - summary recomputes (counts change)
6. Honesty:
   - if computed_method is combined, UI does NOT label as "Hechos (votos)"
   - low coverage / no_signal renders explicitly
7. Mobile width (~390px):
   - no horizontal overflow that blocks use
   - party cards readable and clickable
