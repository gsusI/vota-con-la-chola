# AI-OPS-21 Citizen UI v4 Implementation (Coverage + Coherence)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

## What Shipped (Visible)
- New `Vista: coherencia` in the citizen app:
  - Coverage per concern by method (`votes`, `declared`, `combined`) showing `any` and `clear` ratios.
  - Conservative coherence summary (votes vs dichos) per party:
    - comparable only when both are `{support, oppose}`
    - match/mismatch counts + deterministic audit links
- Party focus in coherence view:
  - topic list shows `v:` and `d:` mini chips and highlights `mismatch` when comparable+different.

## Shareability (URL State)
- Coherence view is shareable/restorable via:
  - `view=coherence`
  - `concerns_ids=<csv>`
  - `party_id=<int>` (optional)

## Auditability
- Coherence cards include audit links for an example topic (when comparables exist):
  - Temas focus link (`../explorer-temas/?topic_set_id=...&topic_id=...`)
  - method-specific Explorer SQL links for votes and declared

## Static-First Performance
- Coherence view lazy-loads:
  - `citizen_votes.json`
  - `citizen_declared.json`
  - `citizen.json` (combined) if not already the base dataset
- This keeps default `/citizen/` load unchanged and confines extra downloads to coherence view.

## Control Semantics (Avoid Confusion)
- In `view=coherence`:
  - `Metodo` selector is disabled (coherence always compares votes vs dichos).
  - `Filtro (stance)` is disabled (not applicable to coherence).

## Files Changed
- `ui/citizen/index.html`:
  - added coherence view mode + URL restore support
  - added lazy coherence dataset loader + conservative coherence computations
  - updated topic list focused-party chips for coherence mode

