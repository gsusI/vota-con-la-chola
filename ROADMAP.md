# ROADMAP

Status: `canonical`
Updated: `2026-04-13`

## Mandate

This file is the single source of truth for the future of the project.

Rules:
- If a future initiative, surface, or expansion is not in this file, it is not prioritized.
- `docs/etl/e2e-scrape-load-tracker.md` remains the source of truth for operational status, connector gates, and blockers already in flight.
- `docs/roadmap.md`, `docs/roadmap-tecnico.md`, and `docs/roadmap/public-roadmap.md` are supporting documents. They may elaborate or operationalize this roadmap, but they must not introduce net-new future scope without updating this file first.
- Other TODO-like docs must be pointers, not parallel planning systems.
- When direction changes, update this file first. Then align derived docs.

## End Goal

Build an evidence-backed public accountability system for Spain that can answer, with explicit caveats:

- what was promised,
- what was done,
- who is responsible,
- who can change it now,
- what changed afterward,
- and what remains unknown or blocked.

The finished system must be able to answer both narrow public questions and hard structural questions with drill-down to primary evidence.

Primary public surfaces:
- `vote explainer`
- `responsibility explainer`
- `source catalog / scrape coverage map`
- `source obstruction tracker`
- `actor dossiers`
- `evidence-backed Q&A`

## Platform Thesis

This project is not meant to scale by having the core team manually build every answer.

It should scale as a shared accountability platform:
- the core team builds and maintains the rails,
- collaborators add bounded evidence-producing components,
- all public answers run through the same evidence and provenance contract.

Core team responsibilities:
- canonical ontology, IDs, and relationship model,
- source registry, scrape coverage publication, and blocker taxonomy,
- jurisdiction, competence, and responsibility framework,
- plugin contracts and SDK,
- provenance, reproducibility, privacy, and review gates,
- Evidence API and canonical public surfaces,
- quality thresholds and publication rules.

Collaborator responsibilities:
- source connectors,
- document and measure extractors,
- topic and domain codebooks,
- review and adjudication workflows,
- dossiers, explainers, and downstream tools built on the Evidence API.

Design rule:
- the core team builds the rails,
- the ecosystem adds modules,
- the public product composes those modules into answerable questions.

## North-Star Questions

The roadmap is complete only when the system can answer questions like these responsibly:

- What exactly was voted, what passed, and who voted how?
- Who created, approved, promulgated, implements, and enforces a given rule?
- Which level of government or institution actually owns a policy constraint?
- Why does a service fail in practice: law, budget, staffing, execution, management, or geography?
- What evidence is strong, what is partial, and what cannot yet be answered?
- In a public failure or disaster case, what warnings existed, who had the duty to act, what was decided or omitted, and what evidence supports attributing preventable harm?

## Strategic Sequence

### P0. Delivery Machine And Repo Boundaries

Objective:
- Stop the repo from behaving like a codebase, archive, publish bucket, and speculative planning dump at the same time.

We need:
- one canonical roadmap,
- explicit separation between source, generated outputs, and published artifacts,
- stable fixture/dev path,
- reproducibility and privacy gates,
- ownership boundaries by layer.

Exit gate:
- future direction is maintained in this file only,
- operational status lives in tracker/docs that do not invent new scope,
- contributors can identify what matters now in minutes.

### P1. Public Product Wedge

Objective:
- Ship a public surface that is immediately useful and evidence-first.

We need:
- canonical vote explainer,
- public source catalog and scrape coverage contract,
- obstruction tracker,
- transparency dashboard,
- explicit freshness/coverage/uncertainty contract.

Exit gate:
- any major vote can produce a shareable explainer with official sources and visible caveats inside one publish cycle.

### P2. State Policy Ledger And Responsibility Chain V1

Objective:
- Move from "votes only" to a national ledger of policy actions with responsibility attribution.

We need:
- `policy_events` and `policy_instruments`,
- BOE and executive/legal instrument ingestion,
- budgets, procurement, and subsidy evidence,
- measure extraction from legal/policy text,
- responsibility roles:
  - `originator`
  - `approver`
  - `promulgator`
  - `implementer`
  - `enforcer`
  - `current_owner`

Exit gate:
- the system can answer formal national-rule questions such as "who is responsible for limiting cash payments to businesses to 1k euro?" with evidence and caveats.

### P3. Jurisdiction And Competence Graph

Objective:
- Know which institution can act, which one cannot, and where responsibility is split.

We need:
- State / CCAA / municipal / regulator / agency / service-operator modeling,
- competence mappings by topic and instrument,
- actor-to-institution and institution-to-jurisdiction relationships,
- "who can change this now?" logic.

Exit gate:
- the system can answer multilevel rule questions such as rural housing expansion or street-vending restrictions without collapsing everything into "the government."

### P4. Implementation And Enforcement Graph

Objective:
- Explain why a rule bites in practice, not only where it was written.

We need:
- permits and licensing workflows,
- inspections and sanctions,
- administrative instructions and guidance,
- execution evidence through procurement, staffing, and operational decisions,
- implementation status over time.

Exit gate:
- the system can distinguish between rule origin and real-world enforcement/administration.

### P5. Outcomes And Service Bottlenecks

Objective:
- Explain service failures and social bottlenecks without pretending pure legal attribution is enough.

We need:
- indicators and revisions,
- waiting-list and capacity data,
- staffing, training slots, budgets, procurement, and geography,
- confounders and context,
- intervention definitions for domains where impact claims may later be defendable.

Exit gate:
- the system can answer questions like public-dermatology wait times with a responsibility chain plus explicit uncertainty about causality and confounders.

### P6. Evidence API, Dossiers, And Q&A

Objective:
- Turn the data model into repeatable, evidence-backed public answers.

We need:
- stable Evidence API,
- question catalog,
- answer renderer with confidence/freshness/unanswerable states,
- actor and institution dossiers,
- shareable public routes for responsibility questions.

Exit gate:
- the system can answer a first set of high-value public questions end-to-end without ad hoc analyst reconstruction.

## Priority Stack

`now`
- `P0. Delivery Machine And Repo Boundaries`
- `P1. Public Product Wedge`
- `P2. State Policy Ledger And Responsibility Chain V1`

`next`
- `P3. Jurisdiction And Competence Graph`
- `P4. Implementation And Enforcement Graph`

`later`
- `P5. Outcomes And Service Bottlenecks`
- `P6. Evidence API, Dossiers, And Q&A`

## Question Readiness Milestones

### M1. Formal Rule Attribution

The system can answer:
- what rule changed,
- who passed it,
- who promulgated it,
- who enforces it formally.

Example class:
- cash payment limits.

### M2. Rule Plus Competence Attribution

The system can answer:
- which level of government owns the rule,
- which institution issues permits or denials,
- who could change it now.

Example class:
- rural housing expansion,
- street sale restrictions.

### M3. Implementation Attribution

The system can answer:
- why something is blocked in practice,
- whether the blocker is law, procedure, permit design, inspection, staffing, or budget.

Example class:
- emergency-management and public-failure cases such as DANA Valencia 2024.

### M4. Service Bottleneck Attribution

The system can answer:
- who owns a service outcome,
- which decisions plausibly contribute,
- which indicators support that reading,
- and where the evidence stops short of a causal claim.

Example class:
- specialist waiting lists in public healthcare.

## Anti-Convolution Rules

- Do not open new product surfaces unless they clearly support one of the programs above.
- Do not expand to new domains just because data exists; expand only when it unlocks answerable question classes.
- Do not build generalized political rankings ahead of responsibility attribution.
- Do not claim causal impact ahead of the outcomes/intervention stack.
- Do not treat ad hoc TODO lists as planning authority.

## Maintenance Protocol

- Update this file first for any change in future direction, scope, or sequencing.
- Keep each program legible in one screen: objective, needed components, exit gate.
- Reflect execution detail elsewhere only after the program exists here.
- Prefer editing this file over adding another planning document.
