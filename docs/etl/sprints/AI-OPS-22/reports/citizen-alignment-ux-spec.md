# AI-OPS-22 Citizen Alignment UX Spec (v0)

Date: 2026-02-17  
Owner: L2 Specialist Builder

## View
- `view=alignment`
- Purpose: preference capture + transparent party match summary (no black box).

## Layout (Reuse Existing 3-Column Shell)

Column 1: **Preocupacion**
- Use concerns/tags as navigation (not truth classification).
- User can switch concerns to browse more items.

Column 2: **Items**
- Same list as today (high-stakes first + search).
- Each item shows:
  - audit links (`Temas`, `Posiciones (SQL)`)
  - optional chip: current user preference (if set)

Column 3: **Alineamiento**

### State A: No preferences yet
- Message:
  - "Selecciona un item (col 2) y marca tu preferencia aqui."
  - "Esto compara solo estos items. Lo demas es desconocido."
- Controls (visible but may be disabled):
  - clear prefs (disabled)
  - share link (disabled)

### State B: Topic selected (preference editor)
- Show selected topic:
  - label + `Temas` + `SQL` links
  - preference buttons:
    - `Yo: A favor`
    - `Yo: En contra`
    - `Quitar`
- Show current preference if already set.

### State C: Preferences present (party summary)
- Top summary:
  - prefs count `N`
  - counts by preference: `support` vs `oppose`
  - privacy note: stored locally; share is opt-in (fragment)
- Per-party list:
  - `match`, `mismatch`, `unknown`, `coverage`
  - deterministic example audit links:
    - first mismatch topic (if any): `Temas`
    - first match topic (if any): `Temas`
  - button: `Foco` (reuses existing party focus behavior)

### State D: Party focus (drill-down)
- When a party is focused:
  - show a list of preference topics with:
    - user pref chip
    - party stance chip
    - result tag: `match|mismatch|unknown`
    - audit links (`Temas`, `SQL`)

## Copy (Honesty + Privacy)
- Honesty:
  - "Solo sobre estos temas: mostramos coincidencia por partido. Si no hay senal, es desconocido."
- Privacy:
  - "Tus preferencias se guardan solo en tu navegador. Si generas un link, se codifican en el fragmento (#...)."

## Empty/Error States
- Unknown-heavy:
  - show `unknown` explicitly and coverage pct.
- Missing prefs from share link (decode error):
  - show banner with error and fall back to local prefs.

