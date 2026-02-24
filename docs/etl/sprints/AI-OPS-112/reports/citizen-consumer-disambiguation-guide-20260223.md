# AI-OPS-112 Report: Consumer Disambiguation Guide v1

Date:
- 2026-02-23

## Where we are now

- The consumer alignment experience already included:
  - top-match decision brief
  - party narratives
  - focused mismatch diagnostics.
- Remaining gap: users lacked guidance on which *next* topics would most reduce ambiguity between close parties.

## What was delivered

- Added disambiguation guidance panel in alignment mode:
  - compares `top1` vs `top2`
  - reports current `gap_net`
  - estimates `min_temas_extra` needed to break close ties.
- Added candidate-topic recommendations to reduce ambiguity:
  - ranks up to 3 unopened topics from current concern scope
  - prioritizes direct splits (`partidos en lados opuestos`) and then signal gaps
  - includes one-click `Abrir tema` and direct `Auditar` links.
- Kept interaction consumer-first:
  - opening a suggested topic scrolls to items and nudges user to mark stance immediately.

## Implementation surface

- `ui/citizen/index.html`
- `docs/gh-pages/citizen/index.html` (published parity sync)

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-112/evidence/just_citizen_test_accessibility_readability_20260223T171507Z.txt`
  - `docs/etl/sprints/AI-OPS-112/evidence/just_citizen_test_tailwind_md3_20260223T171507Z.txt`
  - `docs/etl/sprints/AI-OPS-112/evidence/python_unittest_graph_ui_citizen_20260223T171507Z.txt`

## What is next

- AI-OPS-113: “confidence bands” for top-3 ranking so users see when rank order is fragile vs stable.
- AI-OPS-114: one-screen mobile “decision receipt” tuned for copy/share without scrolling.
