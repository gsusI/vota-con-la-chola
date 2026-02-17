# AI-OPS-18 Task 1: Scope Lock (Citizen-First GH Pages)

Date: 2026-02-17  
Owner: L3 Orchestrator

## Why This Sprint Exists

We already have a lot of national data (Congreso/Senado votes, topic positions, traceable evidence) but the current GH Pages surface is optimized for engineers (explorers), not citizens.

This sprint ships a **citizen-first static webapp** (GH Pages) that answers common concerns with **auditable “dice vs hace”** outputs, without inventing claims or hiding uncertainty.

## Product Scope (MVP)

Deliver a new GH Pages route:
- `/citizen/` (static app)

The MVP lets a citizen:
1. pick a **concern** (e.g. vivienda, empleo, sanidad)
2. see the most relevant **items** (today: high-salience initiatives/topics derived from existing `topic_set_id=1`)
3. compare **party stances** per item with explicit coverage/uncertainty
4. drill down to **evidence** using the existing explorers (no black box)

### What “Concern” Means (Operational Definition)

For this sprint, a “concern” is a **navigation layer** built from deterministic keyword/tag rules over initiative/topic labels.

Non-negotiables:
- it is NOT a substantive classifier and must not be presented as one
- it can be imperfect; the UI must expose that it is a convenience layer

## Non-Goals (Explicit)

- No new upstream connectors.
- No heavyweight backfills or schema rewrites.
- No backend/API requirement (must work as static GH Pages).
- No “alignment ranking” that implies knowing user values.
- No causal impact claims.

## Primary User Journeys (3 max)

### J1: Concern -> Compare Parties
- User selects a concern.
- App shows a curated list of items (high-stakes first).
- For each item, the app shows party stances with coverage signals.

Success = citizen can answer: “¿Qué hicieron los partidos sobre X?”

### J2: Trust -> Drill Down to Evidence
- User clicks a stance card.
- App links to existing explorers (topic/person/evidence) to audit how it was computed.

Success = every displayed claim has a concrete drill-down URL.

### J3: Coverage Honesty
- User sees when data is missing (`no_signal`) and why (coverage/uncertainty).

Success = “no data” is visible, not silently hidden.

## Must-Pass Gates (G1-G6)

### G1 Visible Product (Citizen Route)
PASS when:
- `docs/gh-pages/citizen/index.html` exists after build, and landing links to it.
- The citizen app loads without a local API.

FAIL when:
- route not present, not linked, or requires server runtime.

### G2 Evidence Drill-Down
PASS when:
- every item card includes at least one drill-down URL to:
  - `/explorer-temas` (topic/person filters), and/or
  - `/explorer` (topic_evidence / topic_positions drill-down)

FAIL when:
- stance cards cannot be traced to evidence via links.

### G3 Honesty (No Silent Imputation)
PASS when:
- unknown/no-signal is rendered as unknown
- coverage is shown (counts and/or confidence)

FAIL when:
- UI implies a stance where there is no signal.

### G4 Size/Performance Guardrail
PASS when:
- citizen snapshot JSON is bounded and documented.
- hard limit (initial): `citizen.json <= 5 MB`.

FAIL when:
- export grows unbounded or slows GH Pages load significantly.

### G5 Ops Truth Unchanged (Strict Gate + Parity)
PASS when:
- strict tracker gate remains green (`mismatches=0`, `waivers_expired=0`, `done_zero_real=0`).
- status parity remains `overall_match=true` after GH Pages build.

FAIL when:
- any strict gate regression is introduced by this sprint.

### G6 Reproducibility
PASS when:
- citizen snapshot export is deterministic from `--db` + `--topic-set-id` + `--as-of-date`.
- ordering is stable and output contract is versioned.

FAIL when:
- export is non-deterministic or depends on network without an explicit manifest.

## PASS/FAIL Decision Rule

PASS requires:
- G1, G2, G3, G5, G6 are PASS.
- G4 is PASS (or explicit exception approved in scope-lock addendum; default is NO).

FAIL if:
- any of G1/G2/G3/G5/G6 fails.

## Stop Conditions (Don’t Spin)

Stop and escalate to scope adjustment if any occurs:
- citizen JSON exceeds size guardrail and cannot be reduced by dropping non-MVP fields.
- concern tagging yields near-empty results for common concerns (vivienda/empleo/sanidad) and requires semantic ML/arbitration.
- drill-down links are systematically broken due to explorer constraints.

## Output Artifacts (Sprint Contract)

Citizen app (static):
- `ui/citizen/index.html` -> built to `docs/gh-pages/citizen/index.html`

Citizen data + config:
- `docs/gh-pages/citizen/data/citizen.json`
- `docs/gh-pages/citizen/data/concerns_v1.json`

Evidence packets:
- `docs/etl/sprints/AI-OPS-18/reports/citizen-walkthrough.md`
- `docs/etl/sprints/AI-OPS-18/reports/link-check.md`
- `docs/etl/sprints/AI-OPS-18/reports/a11y-mobile-checklist.md`

Ops invariants:
- strict tracker gate/parity artifacts under `docs/etl/sprints/AI-OPS-18/evidence/`
