# AI-OPS-111 Report: Consumer Mismatch Diagnostics v1

Date:
- 2026-02-23

## Where we are now

- Alignment cards already provided party-level narratives and summary sharing.
- Remaining user friction: once a party is focused, users still needed manual scanning to understand *why* mismatches happen.

## What was delivered

- Added focused mismatch diagnostics panel in party-focus mode (`alignment`):
  - Shows `match/mismatch/unknown` counters for the focused party.
  - Renders top mismatch reasons (first three topics) in plain language:
    - your stance vs party stance
    - direct `Auditar` link per mismatch topic.
- Added one-click `Copiar diagnostico` action:
  - Copies a concise, reusable summary with mismatch drivers and share link.
- Preserved auditability:
  - No hidden inference; explanations are built from existing per-topic `match/mismatch/unknown` decisions.

## Implementation surface

- `ui/citizen/index.html`
- `docs/gh-pages/citizen/index.html` (published parity sync)

## Evidence

- Command/test logs:
  - `docs/etl/sprints/AI-OPS-111/evidence/just_citizen_test_accessibility_readability_20260223T171255Z.txt`
  - `docs/etl/sprints/AI-OPS-111/evidence/just_citizen_test_tailwind_md3_20260223T171255Z.txt`
  - `docs/etl/sprints/AI-OPS-111/evidence/python_unittest_graph_ui_citizen_20260223T171255Z.txt`

## What is next

- AI-OPS-112: add “what would change my ranking” guidance (minimum additional topics needed to disambiguate close parties).
- AI-OPS-113: add mobile-first condensed mismatch card with one-tap copy/share.
