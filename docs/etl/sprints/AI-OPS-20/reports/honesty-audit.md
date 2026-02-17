# AI-OPS-20 Honesty Audit (Methods + No-Signal)

Date: 2026-02-17  
Sprint: `AI-OPS-20`

Scope:
- Citizen UI: `ui/citizen/index.html`
- Citizen artifacts: `docs/gh-pages/citizen/data/citizen*.json`

## Method Semantics (Must Be Explicit)
Derived from pipeline code:
- `votes`: roll-call votes (revealed action; "hechos").
- `declared`: intervention-derived signal (declared statements; "dichos").
- `combined`: deterministic selector (not a mixer):
  - if `votes` exists for a key, use it
  - else use `declared`
  - source of truth: `etl/parlamentario_es/combined_positions.py`

UI labeling (as shipped):
- Method selector:
  - `combined` -> "Metodo: combinado (prioriza votos)"
  - `votes` -> "Metodo: hechos (votos)"
  - `declared` -> "Metodo: dichos (intervenciones)"
- Footer includes an explicit note:
  - combined prioritizes votes, else declared

## No Silent Imputation
Contract + UI behavior:
- `no_signal` is displayed explicitly as "Sin senal".
- `unclear` is displayed explicitly as "Incierto".
- Filter includes `no_signal` and `unclear` separately.
- Cards show coverage + confidence; low coverage surfaces as uncertainty (no hidden fill).

## Concern Tags Are Navigation, Not Truth
UI copy states concern tagging is deterministic keywords-based and used for navigation, not for claiming correctness.

## Programas Lane (Promesas)
- "Programa" is text-derived and expected to be sparser/more uncertain.
- UI displays "sin evidencia" when no audit link exists, and links out to evidence rows when present.

## Verdict
Verdict: PASS

