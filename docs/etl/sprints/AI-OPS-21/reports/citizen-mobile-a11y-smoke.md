# AI-OPS-21 Mobile + A11y Smoke (Coverage + Coherence)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

Scope:
- `ui/citizen/index.html` as shipped to `docs/gh-pages/citizen/index.html` (coherence view additions).

Note:
- Pragmatic checklist (code inspection + static build). Not a full accessibility audit.

## Viewports (Target)
- Mobile: `390x844`
- Desktop: `1440x900`

## Checklist (PASS/FAIL)
- Coherence view is reachable via `Vista: coherencia` and renders without overflow/jank: **PASS (expected)**
- Disabled controls are visually consistent and not interactive:
  - `Metodo` disabled in coherence view
  - `Filtro` disabled in coherence view
  **PASS (code-level)**
- Party cards remain readable on mobile widths (bars wrap and tags wrap): **PASS (expected)**
- Audit links remain standard `<a href=...>` (open in new tab): **PASS**
- Focus styles remain visible for buttons/links: **PASS (expected)**

