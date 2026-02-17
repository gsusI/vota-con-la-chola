# AI-OPS-20 Scope Lock (Citizen Dashboard v3)

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

Links (source of truth, do not duplicate):
- Strategy: `docs/roadmap.md`
- Near-term execution: `docs/roadmap-tecnico.md`
- Operational truth: `docs/etl/e2e-scrape-load-tracker.md`
- Operating policy: `AGENTS.md` (**Anti-Loop Sprint Policy** + **Citizen-First Product Rules**)

## Objective (single)
Ship a **citizen-first**, **static GH Pages** webapp iteration that:
- lets a person select and keep **multiple concerns**,
- compares parties across those concerns in one view (transparent aggregation + coverage),
- supports **shareable URLs** that restore state,
- stays bounded and auditable (evidence-first, no silent imputation).

## User Journeys (max 3)

Journey 1: Multi-concern onboarding (no server)
- Pick 2-6 concerns (e.g., `vivienda`, `sanidad`, `empleo`).
- Land on “Mi dashboard” and immediately see per-party summary + coverage.

Journey 2: Drill down + audit
- From the dashboard, focus a party, then drill down to a concern and a topic.
- Every stance shown has an audit link to an existing Explorer page (GH Pages-safe).

Journey 3: Share + restore
- Copy the URL.
- Open in a fresh tab and see the same: selected concerns, active concern/topic, party focus, and method.

## Scope (in)
- `/citizen` UI (`ui/citizen/index.html`) changes:
  - Multi-concern selection (local-first; URL-shareable).
  - “Mi dashboard” multi-concern synthesis view.
  - Shareable URL state (restore on load) including:
    - selected concerns
    - active concern + optional `topic_id`
    - party focus
    - method selection (at least `votes` vs `combined`; `declared` optional only if export supports it)
  - Method toggle is **honest** (labels reflect data).
- Packaging/build changes to keep it static and bounded:
  - Multi-method citizen JSON artifacts (one per method) + default alias, each `<= 5MB`.
  - Keep `just explorer-gh-pages-build` the primary reproducible build.
- Evidence packet for gates (logs/reports under `docs/etl/sprints/AI-OPS-20/`).

## Non-Goals (explicit)
- No new upstream connectors.
- No backend services beyond GH Pages.
- No black-box personalization, ranking, or opaque scoring.
- No change to the tracker’s blocked-source truth unless there is a new lever (anti-loop policy).

## Must-Pass Gates (PASS/FAIL)

`G1 Visible product delta`
- PASS if `/citizen` supports multi-concern selection (>=2 concerns) and a dashboard summary view.
- PASS if URLs restore the full view state (selected concerns, active concern/topic, party focus, method).
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/reports/citizen-walkthrough.md`
  - `docs/etl/sprints/AI-OPS-20/reports/shareable-url-matrix.md`

`G2 Auditability (GH Pages-safe)`
- PASS if every stance card / summary view includes at least one audit link and link-check reports `broken_targets=0`.
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/reports/link-check.md`

`G3 Honesty`
- PASS if method labels are accurate and `no_signal/unclear` remain explicit (no silent imputation).
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/reports/honesty-audit.md`

`G4 Static budgets`
- PASS if each citizen JSON artifact is `<= 5MB` and mobile usability is acceptable.
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/evidence/citizen-json-budget.txt`
  - `docs/etl/sprints/AI-OPS-20/reports/citizen-mobile-a11y-smoke.md`

`G5 Reproducibility`
- PASS if build/export/validate is deterministic from `--db` and succeeds via `just explorer-gh-pages-build`.
- PASS if `just etl-test` passes.
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.log`
  - `docs/etl/sprints/AI-OPS-20/evidence/tests.exit`

`G6 Strict gate/parity`
- PASS if strict tracker gate exit is `0` and status parity reports `overall_match=true`.
- Evidence:
  - `docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.exit`
  - `docs/etl/sprints/AI-OPS-20/evidence/status-parity-postrun.txt`

## Definition Of Done (sprint)
- All must-pass gates `G1..G6` are `PASS` and evidence artifacts exist in the sprint folder.
- `docs/etl/sprints/AI-OPS-20/closeout.md` is filled with an evidence-backed verdict.

