# Spending filter UX — 2026-09-05

- Now: authority and supplier use searchable, clearable React Select comboboxes (Select2-style interaction). Dates use one DayPicker range dialog: first click starts, second commits both endpoints and closes. Escape/cancel leaves the applied range intact.
- Target: fast filtering with keyboard and mobile, preserving exact source labels and downloadable-result parity.
- Next: verify the deployed canonical route after scoped publication; keep external alpha review in the existing launch tracker.

## Verification

- Browser: authority search `tragsa` + ArrowDown/Enter returns 1 row / 186000 cents; supplier `IDCQ` returns 1 row / 350637 cents.
- Range: first click keeps dialog open and result total unchanged; second click applies both dates. Same-day, reversed-order and keyboard Enter/ArrowRight/Enter selections pass. Escape restores trigger focus and preserves the prior range.
- Share/reload restores supplier and dates. CSV for 2025-01-02 matches the immutable source: 90 rows / 286536786 cents.
- Mobile widths 320 and 390: no calendar horizontal overflow. Desktop 1440 verified visually. Reduced motion gives a zero-duration dialog transition.
- Frozen static build, five launch package tests, notFound scan, size budget and public privacy checks pass.
- npm audit reports four high-severity dependencies already present with identical versions in the previous lockfile (next, postcss, nanoid, sharp). No unrelated framework upgrade included in this UI change.
- Immutable data release and source-label identity rules unchanged.

## Publication

Pending canonical-route verification. Use the existing scoped publication command to preserve unrelated public routes.
