# AI-OPS-17 Scope Lock (Citizen UI/UX v2)

Date: 2026-02-17  
Decision owner: `L3 Orchestrator`

## Problem Statement
We already have meaningful national-level data and evidence drill-down tools, but the citizen surface does not yet answer the fastest user question:

> "Que hizo cada partido sobre esta preocupacion?"

Today, users must click into many items to infer a concern-level picture. This sprint closes that product gap without adding new sources.

## Single Sprint Objective
Ship a citizen-first GH Pages UI iteration (`/citizen`) that:
- provides **concern-level party summaries** ("hechos" + "programa") without requiring topic-by-topic clicking,
- preserves **auditability** (links to Explorer/Temas for every claim),
- stays **static + bounded** (small JSON, fast load, deterministic exports),
- keeps strict gate/parity green.

## User Journeys (Max 3)

### J1: Quick Answer (Concern -> Party Summary)
1. User picks a concern (e.g. `vivienda`).
2. App immediately shows a list of parties with:
   - **Hechos**: summary stance derived from aggregated positions for the selected concern items.
   - **Cobertura**: what fraction of party members have signal in the underlying items.
   - **Programa**: (if available) declared stance extracted from party program text for that concern.
3. User can sort/filter (by stance / coverage / confidence).

### J2: Drill Down (Party -> Top Items)
1. From a party summary card, user opens "ver top items".
2. App shows the most relevant items for the concern (high-stakes first) and the party stance for each item.
3. User can click an item to enter the existing per-topic compare view.

### J3: Audit (No Black Box)
1. From any stance display (summary, item view, program view), user clicks an audit link.
2. App opens:
   - `Temas` (topic-level context), or
   - `Explorer SQL` filtered to the exact rows (`topic_positions` or `topic_evidence`).
3. User can verify where the stance came from.

## Definitions (Honesty)

### "Hechos"
- Meaning: aggregated stance derived from `topic_positions` for active Congress mandates (party members).
- Default method: `computed_method=combined` when available; fallback `votes`.
- Must be labeled as a derived summary, and always show coverage.

### "Programa"
- Meaning: stance extracted from party program text (`programas_partidos`) for the selected concern.
- Default stance vocabulary: `support|oppose|mixed|unclear|no_signal`.
- Must be labeled as "promesas/texto" and treated as higher-uncertainty by default.

## Non-Goals (Explicit)
- No new upstream connectors or unblock campaigns.
- No server backend requirement; keep GH Pages static.
- No "ranking magico", no personalization weights, no ML-based alignment claims.
- No rewriting core ETL semantics (only additive export/UX improvements).
- No attempt to infer voter preferences beyond selecting a concern.

## Must-Pass Gates (PASS/FAIL)

### G1 Visible UX (Concern-Level Summary)
PASS if `/citizen` supports:
- concern selected + no topic selected => party summary view is shown and usable
- at least one party drill-down to top items works

Evidence:
- walkthrough + screenshots or recorded steps under `docs/etl/sprints/AI-OPS-17/reports/`.

### G2 Audit Drill-Down
PASS if every stance display includes at least one working audit link:
- hechos summary -> Explorer SQL (positions) and/or Temas
- program stance -> Explorer SQL (topic_evidence filtered)

Evidence:
- `docs/etl/sprints/AI-OPS-17/reports/link-check.md` with `broken_targets=0`.

### G3 Honesty
PASS if:
- method labels are accurate (votes vs combined)
- `unclear/no_signal` render explicitly (no silent imputation)
- coverage rule is shown in UI copy (or in a help panel)

Evidence:
- UI copy excerpts + validator outputs.

### G4 Static Budget
PASS if citizen JSON artifact(s) remain bounded:
- target `<= 5MB` each (hard fail if vastly over without an explicit waiver)
- page remains usable on mobile widths

Evidence:
- size report under `docs/etl/sprints/AI-OPS-17/evidence/`.

### G5 Reproducibility
PASS if:
- export + validation are deterministic given `--db` + `--as-of-date` + config
- `just explorer-gh-pages-build` runs exporter + validator successfully

Evidence:
- build log + validator JSON output.

### G6 Strict Gate/Parity
PASS if strict tracker gate + status parity remain green post-change:
- strict tracker gate exit `0`
- parity `overall_match=true`

Evidence:
- gate/parity artifacts under `docs/etl/sprints/AI-OPS-17/evidence/`.

## Out-of-Scope Sources/Rows
All external blockers remain out of scope unless a new lever appears. This sprint's primary objective is fully controllable under repo control.

## Next Step
Write the baseline query pack and UX spec, then implement minimal contract/export changes needed for the concern-level summary view.

