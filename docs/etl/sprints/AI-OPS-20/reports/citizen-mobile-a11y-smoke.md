# AI-OPS-20 Mobile + A11y Smoke (Pragmatic)

Date: 2026-02-17  
Sprint: `AI-OPS-20`

Scope:
- `ui/citizen/index.html` as shipped to `docs/gh-pages/citizen/index.html`.

Note:
- This is a pragmatic checklist based on code inspection + static-server smoke.
- It is not a full browser audit with screenshots.

## Viewports (Target)
- Mobile: `390x844`
- Desktop: `1440x900`

## Checklist (PASS/FAIL)
- Responsive layout exists via media queries (`max-width: 1180px`, `max-width: 760px`): **PASS (code-level)**
- No obvious horizontal overflow risks in main panels (grid + `min-width: 0` patterns): **PASS (code-level)**
- Interactive controls have accessible labels:
  - selects include `aria-label` (`viewMode`, `methodSelect`, `stanceFilter`, `partySort`, `topicLimit`): **PASS**
- Keyboard focus affordance exists for buttons/links (browser default + consistent button styling): **PASS (expected)**
- Touch targets reasonable on mobile (buttons/tags have padding): **PASS (expected)**
- Evidence drill-down uses real links (`<a href=...>`), not JS-only navigation: **PASS**

## Follow-ups (Optional)
- Do a real-browser pass with DevTools device emulation and keyboard-only navigation to confirm:
  - no overflow regressions on small widths
  - focus order is intuitive for tags + lists

