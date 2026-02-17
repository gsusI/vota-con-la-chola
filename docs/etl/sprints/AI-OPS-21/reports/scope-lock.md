# AI-OPS-21 Scope Lock (Citizen Coverage + Coherence v1)

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

Status:
- `DONE`

Source of truth (do not duplicate roadmaps):
- Strategy: `docs/roadmap.md`
- Near-term execution: `docs/roadmap-tecnico.md`
- Operational backlog/status: `docs/etl/e2e-scrape-load-tracker.md`
- Previous sprint closeout (baseline): `docs/etl/sprints/AI-OPS-20/closeout.md`

## Baseline (what is true now)
- Citizen app is static GH Pages-first and already ships:
  - multi-concern selection (`concerns_ids`) + dashboard view (`view=dashboard`)
  - shareable party focus (`party_id`)
  - method toggle with bounded artifacts (`method=votes|declared|combined`)
  - audit drill-down links to Explorer/Temas/Politico
- Declared signal is sparse in the current snapshot; this sprint must treat “no signal” as first-class (no pretending).

## Single Sprint Objective
Make the citizen app answer two citizen questions *honestly* and *shareably*:
1. “Que sabemos (y que no) sobre esta preocupacion?” (coverage by method)
2. “Donde hay tension ‘dice vs hace’ cuando ambos existen?” (conservative coherence only when comparable)

Constraints (non-negotiable):
- Static-only (GH Pages). No backend required.
- Bounded artifacts (each `<= 5MB`) validated via `just explorer-gh-pages-build`.
- Audit-first: every coherence/mismatch claim must link to drill-down evidence routes.
- Honesty: `no_signal/unclear/mixed` are not collapsed.

## User Journeys (max 3)

### J1 Coverage Map (Expectation Setting)
Citizen selects 1+ concerns and sees, per concern:
- how many topics exist for that concern
- how much signal exists for each method (`votes`, `declared`, `combined`)
- explicit empty-state when declared has near-zero comparable signal

### J2 Coherence (“Dice vs Hace”, Conservative)
Citizen opens a “Coherencia” view and sees per party (for selected concerns):
- comparable cells count (where both `votes` and `declared` are clear)
- match vs mismatch counts
- a deterministic “audit example” link for at least one mismatch (when present)

Coherence definition (must be explicit in UI copy and docs):
- Comparable ONLY when both stances are in `{support, oppose}`.
- Match when equal, mismatch when different.
- Everything else is “not comparable” (includes `mixed`, `unclear`, `no_signal`).

### J3 Share + Restore
Citizen shares a link and the receiver sees the same view restored:
- selected concerns
- party focus (optional)
- coherence vs detail/dashboard view
- method selection (and any coherence-specific params)

## In-Scope Surfaces
- UI:
  - `ui/citizen/index.html` (ship to `docs/gh-pages/citizen/index.html`)
- Build/export (only if required; prefer zero changes):
  - `justfile` target `explorer-gh-pages-build`
  - existing artifacts: `docs/gh-pages/citizen/data/citizen_votes.json`, `citizen_declared.json`, `citizen.json`
- Docs/evidence:
  - `docs/etl/sprints/AI-OPS-21/` reports + evidence pack

## Non-Goals (explicit)
- No new upstream connectors or scraping work.
- No change to stance computation semantics.
- No opaque ranking/personalization/ML.
- No claims of coherence when comparable pairs are not present (must show “insufficient declared signal” instead).
- No embedding raw evidence rows into citizen JSON (keep audit links, not blobs).

## Must-Pass Gates (AI-OPS-21)

| Gate | PASS Criteria | Required Evidence Artifacts |
|---|---|---|
| G1 Visible product delta | New Coverage+Coherence view works on GH Pages and is discoverable (not hidden behind dev flags). | `docs/etl/sprints/AI-OPS-21/reports/citizen-walkthrough.md` |
| G2 Auditability | Coherence view provides drill-down links for at least one example topic (match/mismatch) and link targets exist in GH Pages build. | `docs/etl/sprints/AI-OPS-21/reports/link-check.md`; `docs/etl/sprints/AI-OPS-21/evidence/link-check.json` |
| G3 Honesty | Mismatch definition is conservative and documented; declared sparsity is surfaced as coverage (no empty charts implying certainty). | `docs/etl/sprints/AI-OPS-21/reports/honesty-audit.md` |
| G4 Static budgets | All citizen JSON artifacts used remain `<= 5MB`. Coherence view does not require downloading > ~3MB by default (lazy-load allowed). | `docs/etl/sprints/AI-OPS-21/evidence/citizen-json-budget.txt`; `docs/etl/sprints/AI-OPS-21/evidence/perf-budget.txt` |
| G5 Reproducibility | `just explorer-gh-pages-build` succeeds and strict validation passes; tests remain green. | `docs/etl/sprints/AI-OPS-21/evidence/gh-pages-build.exit`; `docs/etl/sprints/AI-OPS-21/evidence/tests.exit` |
| G6 Strict gate/parity | Strict tracker gate exit `0` and status parity `overall_match=true`. | `docs/etl/sprints/AI-OPS-21/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-21/evidence/status-parity-postrun.txt` |

## Escalation Rules (stop-the-line)
- If coherence requires a backend service, stop and escalate (out of scope).
- If any single JSON artifact exceeds `5MB`, stop and fix budgets before proceeding.
- If coherence/mismatch cannot be audited with stable links, stop and revise definition or UI output (no “hand-wavy” mismatches).
