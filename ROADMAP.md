# ROADMAP

Status: `canonical`
Updated: `2026-07-25`

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
- what each party, elected official, party official, and direct political appointee has done through time,
- which parties and accountable actors were involved in a specific issue,
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
- `accountability dossiers`
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
- For a specific issue, which parties, elected officials, party officials, appointees, institutions, and implementation bodies touched the chain?
- For a specific actor or party, what is their historical record by issue, with the evidence split between promises, votes, rules, appointments, money, enforcement, and outcomes?

## Data Extraction Roadmap

Purpose:
- Build the evidence spine for accountability across history, by issue, party, politician, appointee, institution, and responsibility role.

Actor scope:
- `Politician` means any publicly accountable actor in one of these evidence-backed categories:
  - elected official,
  - party member or party office-holder when public source data supports the link,
  - person directly appointed by an elected official, party member, party-controlled body, or politically accountable institution.
- Career civil servants and contractors are not treated as politicians by default. They can still appear as implementation or enforcement actors when a public record names them, but attribution must distinguish administrative execution from political accountability.

Where we are now:
- A citizen-first Andalucía slice is live at `/elecciones/andalucia-2026/`: a reviewed `10 KB` `andalucia_water_commitment_receipt_v1` tracks three investiture water commitments as of `2026-07-25`, keeps pre-`2026-07-02` evidence as historical context, records one non-progress reiteration, links official sources/checkpoints/owners/unknowns, and reports zero formal post-investiture milestones without calling any promise late or broken.
- Actor backbone exists: `persons`, `parties`, `mandates`, `institutions`, `government_org_units`, `government_org_relationships`, `government_positions`, and `person_org_memberships`.
- Parliamentary action spine exists: votes, initiatives, documents, text extraction, topic evidence, and topic positions.
- Policy/event scaffolding exists: domains, axes, instruments, `policy_events`, and event axis scores.
- Generic accountability ledger spine now exists: `accountability_issues`, `accountability_ledger_entries`, source-specific backfills, actor-id resolution, shared evidence-tier inference aligned to the source hierarchy, dated/latest public JSON export with issue-led and actor-led summaries, and an actor-resolution queue for unresolved labels.
- Conservative D0 identity bridge now exists for official roll-call labels: distinct Congreso/Senado vote-member names can seed `persons` + `person_name_aliases`, link `parl_vote_member_votes.person_id`, and materialize observed chamber mandates from voting participation. Parliamentary group codes are now materialized separately as `parliamentary_groups` + observed memberships and linked into the generic ledger, including group rollup entries per issue/vote/group/role; they are not treated as one-party affiliation. Where a dated mandate has source-backed `party_id`, the parliamentary backfill now also emits conservative party rollups per issue/vote/party/role, without inferring party from group code. It uses exact normalized labels only and keeps the caveat that external person identifiers, full mandate dates, and formal party affiliation still need verification.
- BOE appointment/title backfill now creates a conservative direct-appointee bridge from real BOE `policy_events`: exact-name `persons`, `person_name_aliases`, `government_positions`, `person_org_memberships`, and ledger `person_id`/`position_id` links for appointment/dismissal rows, with `political_appointee` position kind only for high-office title patterns such as director general or secretario de estado. BOE extraction supports the official OpenData daily-summary endpoint `/datosabiertos/api/boe/sumario/{yyyymmdd}` through `just etl-ingest-boe-sumario-snapshot`, preserving section, department, epigraph, publication date, and legal document URLs. Current rich cut for snapshot `2026-02-12` loads `85/85` BOE records, maps `85` BOE policy events, publishes `85` BOE rule rows and `12` appointment rows, resolves BOE department labels to conservative institution stubs, and adds `12` position-linked appointee rows. The BOE source-issue assignment batch is now applied and the explicit assignment-review queue is `0`.
- Compact accountability dossier export now exists: `accountability-dossiers-<snapshot>.json` / `accountability-dossiers-latest.json` summarize actor history, issue history, issue-actor edges, role counts, and ID coverage without publishing every raw ledger row. A publish gate now validates ledger/dossier schema versions, snapshot dates, count parity, resolved actor coverage, ID coverage floors, and public artifact size before HF packaging. The public ledger export can now cap per-issue evidence rows, actor sample entries, and nested actor/issue summaries while preserving full coverage totals, so richer D1+D2+D3 snapshots fit static publication budgets.
- Static public dossier surface now exists at `/accountability-dossiers/`, backed by `/accountability-dossiers/data/dossiers.json` and `/accountability-dossiers/data/ledger.json`, with coverage metrics, top issue summaries, top actor summaries, direct JSON download links, actor/issue index routes, and generated actor/issue detail routes under `/accountability-dossiers/actors/*` and `/accountability-dossiers/issues/*`. The current rich cut includes parliamentary votes, group rollups, source-backed party rollups, BOE legal-responsibility issues, and sanction competent-body current-owner rows in the same public surface.
- Static Evidence API slice now exists at `/accountability-evidence/`, backed by `/accountability-evidence/data/evidence-api.json` and published as `accountability-evidence-api-<snapshot>.json` / `accountability-evidence-api-latest.json`. Current cut exposes 5 repeatable question templates, 27 deterministic natural-language Q&A answers with shareable static routes under `/accountability-evidence/questions/*`, 929 actor answers, 235 issue answers, 2,351 bounded actor-issue references, 13 citizen issue clusters with reviewed public bucket labels, 235 applied source-issue reviews, 323 issue-cluster links, 13 reviewed cluster items, 0 issue-level assignment review queue items, 9 explicit gap answers, and 1,164 evidence samples, with explicit `partial`/`unanswerable` caveats, source-confidence levels, freshness levels, completeness percentages, and fallback buckets for missing promises, money, implementation, enforcement, audits, and outcomes. The published API uses compact JSON by default so the same coverage fits static/public artifact budgets; `--pretty` remains available for manual inspection. Five reviewed batches are now applied through `scripts/apply_accountability_issue_cluster_assignment_reviews.py` (10 rows, 25 rows, 75 rows, 97-row BOE batch, and the 10-row money batch), moving the reviewed source-issue seed from 18 to 235 rows and keeping the explicit issue-assignment queue at 0.
- Source catalog, scrape queue, obstruction tracking, privacy gates, and static public surfaces already exist.

Where we are going:
- Every public accountability answer should resolve to:
  - actors involved,
  - issue/topic/domain,
  - instrument used,
  - role in the chain,
  - date and scope,
  - source record,
  - evidence quality,
  - uncertainty or blocker state.
- Accountability roles should be explicit, not inferred from vague proximity:
  - `promised`
  - `proposed`
  - `sponsored`
  - `voted_for`
  - `voted_against`
  - `abstained`
  - `approved`
  - `published`
  - `appointed`
  - `dismissed`
  - `delegated_to`
  - `implemented`
  - `funded`
  - `contracted`
  - `subsidized`
  - `enforced`
  - `audited`
  - `current_owner`

Source hierarchy:
- Tier 1: primary records with legal or administrative effect: BOE and official bulletins, parliamentary votes and initiatives, budgets, budget execution, PLACSP, BDNS/SNPSAP, official appointment records, sanctions, inspections, court or audit records where applicable.
- Tier 2: official structured data without direct legal effect: open data APIs, catalogs, organigrams, agendas, declarations, transparency portals.
- Tier 3: official communications: Moncloa, ministries, party releases, RSS, press notes. Use for detection and declared position, then validate against Tier 1 when an effect exists.
- Tier 4: reliable reusers: academia, NGOs, watchdogs, journalists with documented data. Use as discovery or cross-check, not as final authority when primary records are available.
- Tier 5: media/social signals. Use only for lead generation unless independently verified.

Extraction sequence:

### D0. Actor And Office History

Objective:
- Build a historical graph of people, parties, elected offices, party offices, direct appointees, institutions, units, and reporting/appointment edges.

Extract:
- elected mandates,
- parliamentary groups and party affiliation,
- party executive/office holders where public and reproducible,
- government structure and direct political appointments,
- appointing authority and reporting chain,
- start/end dates and source evidence.

Exit gate:
- an actor dossier can show "who this person is, which party/institution they were attached to, who appointed them, who they reported to, and during which dates" with source links.

### D1. Legislative And Parliamentary Action

Objective:
- Capture what elected actors and parties did in parliament, not just how they describe themselves.

Extract:
- votes,
- initiatives,
- amendments where available,
- sponsorship/signatories,
- committee activity,
- interventions,
- official text version at time of vote,
- initiative documents and reviewed citizen-facing measure points.

Exit gate:
- a vote or initiative explainer can show text, stage, party/person behavior, issue tags, and caveats without mixing later text into earlier votes.

### D2. Rules, Executive Acts, And Appointments

Objective:
- Capture acts with formal effects outside parliamentary roll calls.

Extract:
- BOE and official bulletin norms,
- decrees, orders, resolutions, circulars, plans, and appointments,
- Consejo de Ministros references as detection signals,
- appointment/dismissal chains,
- competence and delegation clauses,
- affected issue/domain and responsibility role.

Exit gate:
- a rule or appointment can be traced to originator, approving/publishing institution, appointer, appointee, effective dates, issue, and current owner.

### D3. Money, Implementation, And Enforcement

Objective:
- Capture whether policy became resources, contracts, subsidies, staffing, permits, inspections, sanctions, or administrative execution.

Extract:
- budgets and execution,
- contracts and procurement documents,
- grants/subsidies,
- staffing/organization where public,
- permits/licenses,
- inspections and sanctions,
- service capacity and delivery records.

Exit gate:
- an issue dossier can distinguish "rule passed" from "funded, contracted, staffed, enforced, ignored, blocked, or delegated."

### D4. Issue-Led Accountability Ledgers

Objective:
- Make each issue answerable end-to-end, across all involved parties and actors.

Extract by issue, not only by source:
- all relevant promises, votes, rules, appointments, money flows, implementation acts, enforcement acts, audits, outcomes, and blockers.

Priority issue method:
- choose one issue,
- define source families and gate,
- extract enough to answer who did what,
- publish the issue ledger,
- expose unknowns instead of filling gaps with assumptions.

Exit gate:
- a citizen can open an issue and see all involved parties/politicians/appointees, their role, evidence, timeline, and missing evidence.

### D5. Outcomes, Audit, And Causality Guardrail

Objective:
- Connect actions to observed results only when evidence supports the connection.

Extract:
- official indicators,
- audit findings,
- court/control-body findings,
- inspection outcomes,
- service outputs,
- confounders and context.

Exit gate:
- the product can say "this happened after these decisions" separately from "this decision plausibly caused this outcome", with causal claims held back until methodology supports them.

What is next:
- Publish the second Andalucía water snapshot, generate a commitment-level diff, and run a five-user comprehension test before expanding the receipt beyond this issue.
- Close D0+D1 enough for national accountability: actor/office history, Congress/Senate votes, initiatives, text versions, sponsors, reviewed measure points, and party/person behavior.
- Start D2 with BOE rules and appointments because it unlocks responsibility chains and direct appointee accountability.
- Then add D3 money and enforcement for the same issues already visible in D1/D2, rather than opening unrelated source lanes.

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
- reusable library boundaries for source contracts, fetch/provenance, connectors, document extraction, evidence modeling, quality gates, and publishing.
- a thin Vota con La Chola app layer that keeps product/UI/orchestration while generic public-data logic can be reused by other open-source projects.
- first installable package boundary via `pyproject.toml`, limited to `publicdata_*` namespaces: `publicdata_core`, `publicdata_sqlite`, `publicdata_connectors_es`, `publicdata_policy_es`, `publicdata_ops`, `publicdata_docs`, `publicdata_evidence`, and `publicdata_publish`.

Exit gate:
- future direction is maintained in this file only,
- operational status lives in tracker/docs that do not invent new scope,
- contributors can identify what matters now in minutes.
- generic library seams are documented in `docs/reusable-library-architecture.md`, and the first extraction slice can run without changing public source IDs or UI behavior.

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

Partial shipped:
- `accountability_evidence_api_v1` exports a bounded static JSON API from the ledger/dossier artifacts, validates question count and byte budget before publish packaging, and powers `/accountability-evidence/`.
- Covered now: issue-involved actors, actor historical records, actor-issue record refs, visible actor-issue cards, first actor-issue Q&A routes, citizen issue clusters with reviewed public bucket labels, first reviewed issue-level cluster assignments for fallback issues, bounded issue-cluster review queue, bounded deterministic natural-language Q&A answers, shareable static Q&A routes, missing-evidence gap answers, confidence/freshness/completeness metadata, and explicit `unanswerable` state for dimensions absent in the current D1+D2+D3-rich cut.
- Not complete yet: maintaining issue-level cluster adjudication as new source issues enter, richer user-composed responsibility-question routes, full appointee/party identity enrichment, and outcome/causality evidence.

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
