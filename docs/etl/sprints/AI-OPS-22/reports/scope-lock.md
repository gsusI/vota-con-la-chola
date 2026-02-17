# AI-OPS-22 Scope Lock (Citizen Alignment + Onboarding v0)

Date: 2026-02-17  
Owner: L3 Orchestrator

## Problem Statement (Bottleneck)
We already have bounded, auditable stance grids (`party_topic_positions`) powering `/citizen`, but citizens still cannot:
- express their own preferences on concrete items (topics) quickly
- see a transparent match/mismatch/unknown summary per party without a black-box score

This is a **product bottleneck**: the data exists, but the user loop is missing.

## Primary Citizen Journeys (Max 3)

1. **Fast alignment (2 minutes)**
   - Pick a concern (col 1) and browse items (col 2).
   - For 5-10 items, mark: `Yo: A favor` or `Yo: En contra`.
   - See party summary: `match / mismatch / unknown` with explicit coverage.

2. **Audit a claim**
   - From a party row (match or mismatch), open:
     - `Temas` for the topic, and/or
     - `Explorer SQL` for the exact method/as_of rows.
   - Confirm the stance is derived from evidence rows (no hidden inference).

3. **Share/import preferences (opt-in)**
   - Preferences are local-first by default.
   - A user can optionally generate a share link that encodes preferences in the URL **fragment** (`#...`), not query (`?...`).
   - Opening the link restores the preferences and stores them locally.

## Non-Goals (Hard No)
- No backend/server, no accounts, no analytics, no preference collection.
- No “magic number” ranking that hides unknowns/coverage.
- No new upstream connectors, no ETL backfills required for this sprint.
- No silent imputation: `mixed/unclear/no_signal` remain **unknown** for alignment.

## Must-Pass Gates (G1-G6)

| Gate | PASS Criteria | Evidence (expected paths) |
|---|---|---|
| G1 Visible product delta | `view=alignment` exists in `/citizen`, usable on GH Pages output | walkthrough: `docs/etl/sprints/AI-OPS-22/reports/citizen-alignment-walkthrough.md` |
| G2 Auditability | From alignment view you can drill down to concrete evidence via existing explorer links | link check: `docs/etl/sprints/AI-OPS-22/evidence/link-check.json` |
| G3 Honesty + Privacy | unknowns explicit; prefs local-first; share-link is opt-in and uses fragment; prefs never auto-written to query params | privacy audit: `docs/etl/sprints/AI-OPS-22/reports/privacy-audit.md`; URL matrix: `docs/etl/sprints/AI-OPS-22/exports/url-matrix.csv` |
| G4 Performance budgets | no new JSON artifacts; existing artifacts remain `<= 5MB` each; alignment view does not require > ~3MB extra downloads by default | budget: `docs/etl/sprints/AI-OPS-22/evidence/perf-budget.txt` |
| G5 Reproducibility | `just explorer-gh-pages-build` still works as single build command | build: `docs/etl/sprints/AI-OPS-22/evidence/gh-pages-build.exit` |
| G6 Strict gate/parity | `just etl-tracker-gate` exit `0` and status parity `overall_match=true` | `docs/etl/sprints/AI-OPS-22/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-22/evidence/status-parity-postrun.txt` |

## Definition Of Done (DoD)
- A citizen can create at least 5 preferences and see a party summary with:
  - `match`, `mismatch`, `unknown`, `coverage` (comparable/total)
- At least one match and one mismatch case are auditable via explorer links.
- Privacy contract is enforced and evidenced.

