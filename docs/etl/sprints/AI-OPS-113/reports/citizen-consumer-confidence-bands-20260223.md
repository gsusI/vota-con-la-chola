# AI-OPS-113 Report: Consumer Confidence Bands v1

Date:
- 2026-02-23

## Where we are now

- The alignment experience already surfaced top match, mismatch diagnostics, and tie-break guidance.
- Remaining gap: rank order looked equally definitive even when coverage/gap signals were weak.

## What was delivered

- Added ranking confidence bands for consumer alignment:
  - `estable`
  - `intermedia`
  - `fragil`
- Band logic now uses:
  - coverage/comparable depth
  - net gap vs next party
  - unknown pressure.
- Exposed bands across user-facing outputs:
  - `Decision provisional` panel (`banda_top1` + reason)
  - top-3 tags (`banda=...`)
  - disambiguation guide (`banda_top1`)
  - party cards in alignment list (`banda=...`)
  - copied consumer summary (`banda=...` in top rows).

## Implementation surface

- `ui/citizen/index.html`
- `docs/gh-pages/citizen/index.html` (published parity sync)

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-113/evidence/just_citizen_test_accessibility_readability_20260223T172114Z.txt`
  - `docs/etl/sprints/AI-OPS-113/evidence/just_citizen_test_tailwind_md3_20260223T172114Z.txt`
  - `docs/etl/sprints/AI-OPS-113/evidence/python_unittest_graph_ui_citizen_20260223T172114Z.txt`

## What is next

- AI-OPS-114: convert confidence signal into an explicit next-action plan (how to raise confidence in 2-3 clicks).
