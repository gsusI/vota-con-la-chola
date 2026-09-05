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
- Shared-link dates are validated as real calendar dates; impossible dates restore initial bounds, reversed bounds are normalized. Browser check of `2025-99-99` and `2025-02-30` restores January and all 120 results.
- Immutable data release and source-label identity rules unchanged.

## Publication

Source commits: `854a39fff7`, `922f533ee0`, `764db7e938`. Public branch: `95586e58ca`. [Pages deployment](https://github.com/gsusI/vota-con-la-chola/actions/runs/33964827634) completed successfully. Scoped overlay preserved 15151 unrelated files exactly, deleted zero files, and found zero privacy issues.

Public browser verification on the canonical domain:
- `/spending/`: searchable supplier and recovery of invalid shared dates pass.
- `/spending/index.html`: TRAGSA search returns 1 row / 186000 cents. Selecting January 1 then 2 keeps the dialog open after the first click, closes after the second, and returns 98 rows / 481341417 cents. Share/reload preserves this range; zero captured JavaScript errors.
- Final deployment checked at `/spending/?v=95586e58ca` to avoid the preceding cached response: first click on January 5 highlights only day 5; second click on January 3 commits January 3–5. The `v` parameter is a deployment verification marker, not a preference input.

Status: published and verified. Next: external alpha usability feedback under the existing launch tracker.
