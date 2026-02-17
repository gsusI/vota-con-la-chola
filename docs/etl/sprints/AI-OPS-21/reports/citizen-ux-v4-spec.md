# AI-OPS-21 Citizen UX v4 Spec (Coverage + Coherence)

Date:
- `2026-02-17`

Sprint:
- `AI-OPS-21`

Scope lock:
- `docs/etl/sprints/AI-OPS-21/reports/scope-lock.md`

## Problem (Citizen-First)
We already ship:
- a static citizen app on GH Pages
- method toggles (`votes|declared|combined`)
- multi-concern dashboard + shareable URL state

But a citizen still cannot quickly answer:
1. “Que sabemos (y que no)?” (coverage gaps by method)
2. “Dice vs hace” (only when comparable, without pretending declared coverage is high)

## Goals (v1)
- Add a new view that makes **coverage** explicit and treats sparsity as first-class.
- Add a conservative **coherence** summary:
  - only when `votes` and `declared` are both clear (`support|oppose`)
  - show match/mismatch counts + audit links
- Keep everything static and auditable.

## Non-Goals
- No new connectors.
- No backend.
- No ranking/personalization.
- No “coherence score” when the comparable sample is too small; show “insufficient signal” instead.

## UX Entry Points
In panel (3) “Comparar por partido” add a new view mode:
- `Vista: coherencia` (in addition to `detalle` and `mi dashboard`).

This view is shareable via URL and restores state on load.

## Data Plumbing (Preferred)
- Coherence view needs both datasets:
  - `./data/citizen_votes.json`
  - `./data/citizen_declared.json`
- Load them lazily:
  - only when `view=coherence` is active (or when user switches to coherence view)
- Join in-browser on `(topic_id, party_id)` (full grid expected).

Budget expectation:
- ~2 MB total for votes+declared; acceptable when lazy-loaded.

## Definitions (Honesty Contract)

### Coverage
For a given concern (set of topics) and method:
- `cells_total = topics_total * parties_total`
- `any_signal = stance != no_signal`
- `clear = stance in {support, oppose, mixed}`
Report both:
- `any_signal_pct`
- `clear_pct`

### Coherence (votes vs declared)
For each `(topic_id, party_id)`:
- comparable ONLY when:
  - `votes_stance in {support, oppose}` AND
  - `declared_stance in {support, oppose}`
- `match` when equal
- `mismatch` when different
- otherwise: `not comparable` (includes `mixed`, `unclear`, `no_signal`)

## Coherence View Layout (v1)

### Section A: Coverage Map (Expectation Setting)
Show a compact per-concern table for selected concerns:
- concern label + topics_total
- votes `any_signal_pct` + `clear_pct`
- declared `any_signal_pct` + `clear_pct`
- coherence comparable cells (count) and mismatch count (optional)

Empty-state rules:
- If declared `any_signal_pct` is near-zero, show a prominent note:
  - “Dichos: cobertura baja en este snapshot. Esta vista muestra huecos de evidencia, no certezas.”

### Section B: Party Coherence Summary
For each party:
- `comparable` count (and percent of topics)
- `match` and `mismatch` counts
- `not comparable` count
- Deterministic audit links:
  - If `mismatch > 0`: link to the first mismatch topic (sorted by high-stakes, rank, topic_id)
  - Else if `comparable > 0`: link to the first comparable match topic
  - Else: show “sin comparables”

Audit links per example topic (must be real links):
- Temas: `../explorer-temas/?topic_set_id=...&topic_id=...`
- Votos (SQL): `../explorer/?t=topic_positions...computed_method=votes...`
- Dichos (SQL): `../explorer/?t=topic_positions...computed_method=declared...`

### Section C: Party Focus (Optional, v1)
If `party_id` is set (focus), show the focused party first and optionally collapse the rest.
This preserves existing shareable “party focus” behavior.

## Controls Behavior
- `Metodo` selector:
  - stays relevant for `detalle`/`dashboard` views
  - in `coherence` view, disable it or show a clear note that coherence compares votes vs dichos regardless of selected base method
- `concerns_ids`:
  - coherence view should work with 1+ selected concerns (but is most meaningful with >=2)

## URL State (Shareability)
Extend `view=`:
- `view=detail|dashboard|coherence`

Keep existing params unchanged:
- `concerns_ids`, `concern`, `topic_id`, `party_id`, `method`

## Definition Of Done (UX)
- Citizen can open `/citizen/?concerns_ids=vivienda,sanidad&view=coherence` and see:
  - coverage table
  - party coherence cards
  - at least one audit link when a comparable exists (otherwise explicit empty-state)
- Switching views updates URL and Back/Forward restores state.
- Coherence view does not download votes+declared unless the view is active.

