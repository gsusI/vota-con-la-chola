# AI-OPS-21 Honesty Audit (Coverage + Coherence)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

Scope:
- Citizen UI: `ui/citizen/index.html`
- Citizen artifacts: `docs/gh-pages/citizen/data/citizen*.json`

## Method Semantics (Truth-First)
- `votes`: roll-call votes ("hechos").
- `declared`: intervention-derived signal ("dichos").
- `combined`: selector, not mixer:
  - prefers `votes`, else `declared`
  - source of truth: `etl/parlamentario_es/combined_positions.py`

## Coherence Definition (Conservative)
Coherence compares `votes` vs `declared` only when both are comparable:
- comparable ONLY if both stances are in `{support, oppose}`
- match if equal
- mismatch if different
- everything else is `not comparable` (`mixed`, `unclear`, `no_signal`)

UI behavior:
- coherence view header explicitly states the comparable rule
- coherence view shows `comparables` counts so a small sample is obvious

## Coverage (Make Gaps Visible)
Coverage is displayed per concern and method as:
- `any`: stance != `no_signal`
- `clear`: stance in `{support, oppose, mixed}`

Declared sparsity is expected in the current snapshot; coherence UI must treat “no comparables” as a valid outcome, not an error.

## No Silent Imputation
- `no_signal` stays explicit (never filled).
- `unclear` stays explicit (not collapsed into support/oppose).
- coherence does not invent comparisons for mixed/unclear rows.

## Verdict
Verdict: PASS

