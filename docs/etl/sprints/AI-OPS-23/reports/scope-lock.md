# AI-OPS-23 Scope Lock (Citizen Onboarding v1)

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Where We Are Now (baseline truth)

- We already have a static citizen webapp on GH Pages (`/citizen`) powered by bounded JSON artifacts (`<= 5MB` each).
- Views exist: `detail`, `dashboard` (multi-concern), `coherence` (votes vs declared comparability), `alignment` (local preferences -> match/mismatch/unknown).
- Shareable URL state exists for non-sensitive view params (concerns, method, view, party focus).
- Preferences are local-first: stored in `localStorage`, share opt-in via URL fragment only.

## Objective (what we will ship)

Make first-time use citizen-proof: from landing to a defensible, auditable answer in ~60 seconds, without adding servers or collecting user preferences.

Definition:
- “Onboarding v1” is a guided start path that sets:
  - 1-3 concerns
  - method (`combined|votes|declared`)
  - destination view (`dashboard|coherence|alignment`)
- It must be shareable/restorable via URL for *non-sensitive* state.
- It must never leak preferences by default.

## Primary User Journeys (max 3)

1. First visit -> “Start here” -> Dashboard answer
- Citizen lands on `/citizen/` with no prior state.
- They pick 2-3 concerns and (optionally) method.
- They land on `view=dashboard` with a party summary.
- They can click a party and drill down to items with audit links (Temas + Explorer SQL).

2. First visit -> “Start here” -> Coherence (honesty-first)
- Citizen picks 1-2 concerns and selects `view=coherence`.
- They see coverage + comparable/match/mismatch counts per party (no pretending).
- They can drill to comparables and audit.

3. Share link -> restores view state (no preferences)
- Citizen opens a shared URL and sees the same selected concerns + view + party focus + method.
- If a shared URL includes a preference fragment, it is treated as explicit opt-in and must not be written back to query params.

## Non-Goals (to prevent scope creep)

- No accounts, no analytics, no server-side persistence.
- No inferred “values” or psychographic profile.
- No new upstream data connectors or new ETL surfaces.
- No “magic rank” that hides coverage/unknown; unknown is a valid output.

## Privacy Contract (hard rules)

Allowed in URL query params (shareable):
- `concern_ids` (selected concerns)
- `view` (`detail|dashboard|coherence|alignment|start`)
- `party_id`
- `method` (`combined|votes|declared`)

Forbidden in URL query params:
- Any citizen preference payload (topic-level support/oppose) or anything derived from it.

Preference persistence + sharing:
- Default persistence is `localStorage`.
- Share preferences only via explicit user action and URL fragment (`#prefs=...`), never automatically.

## Must-Pass Gates (G1-G6)

G1 Visible product delta (PASS/FAIL)
- PASS if a new citizen can follow a single obvious “Start here” path from empty state to a useful destination view in <= ~60 seconds.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/reports/citizen-onboarding-ux-spec.md`
  - `docs/etl/sprints/AI-OPS-23/reports/citizen-walkthrough.md`

G2 Auditability (PASS/FAIL)
- PASS if onboarding does not bypass auditability: every stance shown remains drill-down auditable via Temas/Explorer SQL links.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/evidence/link-check.json` with `missing_required_links_total=0` and `missing_targets_total=0`

G3 Honesty + Privacy (PASS/FAIL)
- PASS if unknown/coverage remain explicit and preferences do not leak into query params.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/evidence/privacy-grep.txt`
  - `docs/etl/sprints/AI-OPS-23/reports/url-contract.md`

G4 Static budgets (PASS/FAIL)
- PASS if citizen JSON artifacts remain `<= 5MB` each and onboarding does not force downloading extra artifacts by default.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/evidence/citizen-json-budget.txt`
  - `docs/etl/sprints/AI-OPS-23/evidence/perf-budget.txt`

G5 Reproducibility (PASS/FAIL)
- PASS if `just explorer-gh-pages-build` still builds and validates citizen artifacts with exit code 0.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/evidence/gh-pages-build.exit` = `0`
  - `docs/etl/sprints/AI-OPS-23/evidence/citizen-validate-post.log`

G6 Strict gate/parity (PASS/FAIL)
- PASS if strict tracker gate stays green and status parity remains `overall_match=true`.
- Evidence (required):
  - `docs/etl/sprints/AI-OPS-23/evidence/tracker-gate-postrun.exit` = `0`
  - `docs/etl/sprints/AI-OPS-23/evidence/status-parity-postrun.txt` contains `overall_match=true`

## Next Step

Write the onboarding UX spec and URL contract, then implement `view=start` (or equivalent start panel) in `ui/citizen/index.html`.

