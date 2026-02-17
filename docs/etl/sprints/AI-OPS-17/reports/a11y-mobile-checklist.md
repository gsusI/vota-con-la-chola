# AI-OPS-17 A11y + Mobile Checklist

Date: 2026-02-17

Scope: `ui/citizen/index.html` as shipped to `docs/gh-pages/citizen/index.html`.

Note: this is a pragmatic checklist based on code inspection + static-server smoke fetch. It is **not** a full manual browser audit with screenshots.

## Viewports (Target)
- Mobile: `390x844`
- Desktop: `1440x900`

## Checklist (PASS/FAIL)
- No horizontal scroll in primary layout: **PASS (code-level)**  
  Rationale: layout uses responsive grid + `minmax(0, 1fr)` patterns; lists/panels set `min-width: 0`.
- Keyboard focus visible for interactive elements: **PASS (code-level)**  
  Rationale: `.pill:focus`/hover styles exist; clickable rows have `tabindex="0"` and `keydown` handling.
- Headings structure exists (`h1`, section headers): **PASS**
- Links are real URLs (no JS-only navigation) for evidence drill-down: **PASS**
- Contrast acceptable for primary interactions (buttons/chips): **PASS (expected)**  
  Rationale: dark ink on light panels; accent colors are saturated; no low-contrast gray-on-gray for primary CTAs.
- Touch targets reasonable on mobile (list rows/pills): **PASS (expected)**  
  Rationale: rows/pills have padding and are block-level.

## Follow-ups (Optional)
- Do a quick real-browser pass with DevTools device emulation and keyboard-only navigation to confirm focus and no overflow regressions.
