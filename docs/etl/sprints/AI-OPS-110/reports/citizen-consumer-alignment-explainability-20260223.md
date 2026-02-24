# AI-OPS-110 Report: Consumer Alignment Explainability v1

Date:
- 2026-02-23

## Where we are now

- `/citizen` already had consumer-mode onboarding, quick-answer cards, and a decision brief in alignment view.
- Remaining consumer gap: party cards still required manual interpretation and were hard to reuse outside the app.

## What was delivered

- Added plain-language explanations per party in alignment cards:
  - New narrative line per card explains whether the result is high alignment, moderate alignment, tie, desalignment, or low-signal.
  - Uses `match/mismatch/unknown` + coverage to keep explanation auditable and consistent.
- Upgraded decision brief with actionable shortlist:
  - Shows top-3 snapshot (`1)`, `2)`, `3)`) with `net` and `coverage`.
  - Keeps immediate focus/audit actions for top match.
- Added one-click consumer sharing utility:
  - New `Copiar resumen` action in decision brief.
  - Copies a plain-text summary (method, preference counts, top parties with metrics, and share link) to clipboard.

## Implementation surface

- `ui/citizen/index.html`
- `docs/gh-pages/citizen/index.html` (published parity sync)

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-110/evidence/just_citizen_test_accessibility_readability_20260223T171050Z.txt`
  - `docs/etl/sprints/AI-OPS-110/evidence/just_citizen_test_tailwind_md3_20260223T171050Z.txt`
  - `docs/etl/sprints/AI-OPS-110/evidence/python_unittest_graph_ui_citizen_20260223T171050Z.txt`

## What is next

- AI-OPS-111: add explicit “why mismatch” drilldown cards that point to the first contradictory evidence row per topic/party.
- AI-OPS-112: add a mobile-first decision receipt view optimized for one-screen compare/share.
