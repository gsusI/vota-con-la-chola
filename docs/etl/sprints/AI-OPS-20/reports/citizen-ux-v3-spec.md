# Citizen UX v3 Spec (AI-OPS-20)

Status:
- `DRAFT` (owned by sprint; keep changes minimal and implementable)

Non-negotiables:
- Static-first (GH Pages), no backend dependencies.
- Evidence-first: drill-down links are mandatory wherever we assert a stance.
- Honesty-first: show `no_signal/unclear` explicitly; do not silently impute.
- Performance budgets: bounded JSON artifacts (target `<= 5MB` each).

## Product intent (citizen-first)
The citizen UI should answer these questions fast:
1. "Que hicieron los partidos sobre lo que me importa?"
2. "Que dijeron / que prometen (programa) sobre lo que me importa?"
3. "Como lo audito?"

## IA-OPS-20 UI Modes (3)

Mode A: "Mi dashboard" (multi-concern)
- Inputs:
  - Multi-select 2-6 concerns (default from URL or localStorage).
  - Method selector (at least `votes` vs `combined`; `declared` optional if exported).
  - Optional party focus.
- Output:
  - Per-party summary across the union of topics for the selected concerns:
    - stance summary (support/oppose/mixed/unclear/no_signal)
    - coverage ratio (clear/total) and confidence avg
    - transparent counts by stance
    - at least one audit link (deterministic representative topic link)
  - Programs lane per party:
    - summary across selected concerns (counts by stance)
    - show evidence link if available (otherwise "sin evidencia")

Mode B: "Concern drill-down" (single concern detail)
- Keep current layout (concern -> topic list -> compare), but:
  - selected concerns remain visible (so switching is cheap)
  - party focus is shareable (URL state), not ephemeral
  - summary calculations should be stable (avoid depending on ephemeral list filters unless explicitly labeled)

Mode C: "Topic drill-down" (single topic)
- Current compare view per topic remains:
  - show per-party stance + coverage + confidence
  - links to Explorer positions + Temas
  - include the program stance chip for the active concern

## Interaction rules
- A click on a concern does:
  - set `active_concern` (detail mode),
  - ensure it is in `selected_concerns` (dashboard set).
- Party focus:
  - is set via a button from dashboard or concern summary,
  - should persist across reload via URL state,
  - should never force a topic selection (focus means: show stance chips in topic list).
- Method toggle:
  - changes the citizen dataset loaded (per-method JSON),
  - updates the URL so it is shareable,
  - updates the top chips (as_of, method, topic_set, version).

## Copy rules (honesty)
- Labels must match data:
  - `votes` => "Hechos (votos)"
  - `combined` => "Posicion (combinada)"
  - `declared` => "Dichos (intervenciones)" (only if shipped)
- Explain uncertainty:
  - `no_signal` => "Sin senal"
  - `unclear` => "Incierto"
- Never "smooth" missing evidence into support/oppose.

## URL + local persistence (high-level)
- URL is the primary share mechanism.
- localStorage is convenience only (used when URL doesn't specify state).
- Backward compat: accept existing `?concern` and `?topic_id` params.

## Acceptance checklist (UX)
- Multi-concern dashboard works with >=2 concerns selected.
- URL restores: concerns, active concern/topic, party focus, method.
- Every stance card shows audit links; link-check passes.
- Mobile layout remains usable (no horizontal scroll traps).

