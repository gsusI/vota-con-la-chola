# ROADMAP

Status: `canonical`
Updated: `2026-08-12`

## 1. Mission

Build Spain's open, evidence-backed accountability infrastructure.

The system must let a citizen, journalist, researcher, auditor, or public servant answer:

- what was promised,
- what was voted and by whom,
- what rule or executive act was approved,
- who had formal responsibility,
- what money was budgeted, awarded, paid, or withheld,
- what was implemented or enforced,
- what outcome followed,
- what evidence supports each statement,
- what remains unknown, disputed, stale, or blocked,
- and how a published conclusion changed after correction or counterevidence.

Every public claim must drill down to primary evidence. Anomaly detection may create a review signal. It may never publish a corruption verdict by itself.

## 2. Authority And Status

This file owns future direction and sequencing.

- Strategy and model background: `docs/roadmap.md`.
- Near-term engineering execution: `docs/roadmap-tecnico.md`.
- Live source and pipeline status: `docs/etl/e2e-scrape-load-tracker.md`.
- Confirmed official-data access obstruction: `docs/etl/name-and-shame-access-blockers.md`.
- Stable implementation knowledge: `project_kb/README.md`.

Rules:

- Derived documents may refine this roadmap but may not introduce net-new scope.
- A work item is `DONE` only when its exit gate has current evidence.
- Local code, a passing unit test, or a large generated file is not production readiness.
- Missing artifacts, blocked sources, and unverified identities stay open.
- Every non-trivial slice records current state, destination, next action, command, artifact, and definition of done.

## 3. Non-Negotiable Real-Data Policy

Only records captured from identifiable official public sources count toward coverage, capacity, quality, or readiness.

Required for every counted corpus:

- official source identity and allowlisted origin,
- retrieval timestamp and HTTP outcome,
- immutable raw checksum,
- source record identity or explicit source-scoped fallback,
- parser and schema version,
- exact transformation lineage,
- manifest with row, file, byte, and checksum totals,
- independent validation against the materialized artifact,
- public-domain status and provenance classification,
- current limitation and next gate.

Captured official samples may support deterministic tests. They must retain source metadata and checksums. Generated records, invented people, invented transactions, loopback HTTP results, and placeholder origins never count toward a roadmap gate.

Public-domain identity is accountability evidence. Names, public identifiers, birth fields, official contact details, candidacy facts, supplier and beneficiary identities, appointments, donations, and comparable personal information published by an authoritative public source must be retained exactly with source URL, retrieval, checksum, and record/field lineage. Entity classification may describe a person or organization; it may never suppress an official public field. Secrets, credentials, workstation traces, private session state, and information not obtained from a public source remain forbidden in public artifacts.

The machine-enforced registry is `docs/etl/real-corpus-registry.json`. The canonical audit is:

```bash
just etl-scale-readiness
```

## 4. Scale Contract

Scale is an end-to-end operating property. It includes discovery, fetch, preservation, parsing, normalization, identity, enrichment, review, publication, correction, recovery, and cost.

### 4.1 Scale classes

| Class | Real corpus | Required proof |
| --- | ---: | --- |
| `R0 captured` | `1-9,999` official records | provenance, repeatable parse, idempotence, public-field retention, artifact validation |
| `R1 operational` | `100,000+` official records or full smaller universe | bounded memory, resumability, reconciliation, quality sample, bounded publication |
| `R2 million` | `1,000,000+` official items | freshness SLO, recovery, incremental rebuild, durable origin, clean restore, cost report |
| `R3 national history` | `10,000,000+` facts and `1,000,000+` documents | multi-year completeness, revision history, source drift, distributed workers, public release SLO |
| `R4 ecosystem` | `100,000,000+` facts | independent replicas, stable contracts, horizontal operation, audited releases, contributor governance |

Rows alone never promote a lane. Promotion also requires representative scope, source-total reconciliation, durable public origin, clean-room restore, corrections, and a public delivery contract.

### 4.2 Mandatory million-scale SLOs

| Property | Gate |
| --- | --- |
| Provenance | `100%` of published claims resolve to an official source, retrieval, checksum, parser, and evidence row |
| Source URL | `100%` public URL or a documented immutable official-source replacement |
| Idempotence | replay creates zero duplicate logical facts and emits a reconciled delta |
| Work durability | every item is pending, leased, succeeded, or dead; no silent loss |
| Recovery | killed workers resume from durable state; expired leases are reclaimable |
| Memory | bounded by batch, shard, or document limits, never total corpus size |
| Fetch | `>=99.5%` after bounded retries for reachable in-contract items; every residual failure classified |
| Parse | `>=99%` for supported digital formats; OCR and unsupported formats separated |
| Reconciliation | discovered, fetched, stored, parsed, normalized, and published counts balance per run |
| Freshness | every source has an owner and measured SLA; overdue data is public status |
| Unknowns | missing, disputed, blocked, and `no_signal` remain explicit |
| Publication | manifests and bounded shards; no browser route loads a million-row blob |
| Corrections | accepted corrections appear in the next release with immutable history |
| Recovery drill | raw objects and analytical artifacts restore from a clean environment |
| Publication hygiene/security | official public fields retained exactly; secrets, local traces, and non-public state blocked; dependency and least-privilege checks pass |
| Cost | bytes, requests, CPU, memory, OCR pages, storage, and cost per `1,000` items reported |

### 4.3 Priority lanes

Each lane must reach `R2` independently:

1. actors: people, candidates, mandates, appointments, party offices, identifiers, aliases;
2. parliamentary action: initiatives, versions, amendments, signatories, votes, speeches;
3. documents: PDFs, HTML, attachments, OCR pages, extracted measures, document versions;
4. responsibility: rules, policy events, institutions, competences, delegation, current owner;
5. public money: budgets, execution, contracts, lots, awards, suppliers, subsidies, beneficiaries;
6. implementation: staffing, permits, inspections, sanctions, service delivery, audit findings;
7. outcomes: indicator observations, methodology versions, revisions, confounders;
8. accountability: issue ledgers, evidence edges, claims, counterevidence, corrections, appeals;
9. participation: review tasks, calibration, adjudication, contributor and release evidence.

## 5. Verified Baseline — 2026-08-12

`just etl-scale-readiness` currently validates six materialized official-source corpora:

| Lane | Real rows | Files | Current proof | Promotion blockers |
| --- | ---: | ---: | --- | --- |
| Member votes | `1,809,222` | `8,373` gzip shards | every file, checksum, payload, member count, source record, and public URL audited; one verified official capture sidecar repairs `350` legacy rows | `102,172` URL rows use official HTTP; official-total reconciliation, durable origin, clean restore, representative chamber history |
| Eurostat indicators | `1,755,809` | `37` Parquet files | full provenance, schema/hash/row validation, `26/26` unchanged partitions reused | four-dataset scope is not representative; no second-snapshot revision proof; no durable public origin or clean restore; corrections workflow incomplete |
| PLACSP money facts | `263,302` | `50` Parquet files | v5 exact manifest/file/row/hash validation; all `128,849` source-published counterparty names and identifiers retained, including `8,260` natural-person and `3,058` unclassified rows; `50/50` unchanged partitions reused | incomplete historical universe; awards are not payments; identity resolution and durable restore open |
| BDNS subsidy facts | `1,360,382` | `14` Parquet files | current v6 full-row validation; all `1,360,382` official beneficiary names and all `163,270` source-published identifiers retained; `1,419/1,419` queue/page/version/source/amount totals exact; `89/89` selected daily windows complete; unchanged partition reused through `14/14` hardlinks | no second snapshot, full-history/representative reconciliation, durable origin, or clean restore |
| Accountability ledger | `126,760` | `13` Parquet files | clean real-only rebuild; full source/URL/lineage validation; `13/13` unchanged partitions reused; `26` blank legacy source IDs explicitly inferred from allowlisted BOE URLs | parliamentary-heavy mix; below `R2`; durable origin and clean restore open |
| Actor mandates | `88,031` | `108` Parquet files | official origins, full URL coverage, identity states, `108/108` unchanged partitions reused | below `R1`; uneven jurisdiction mix; external identity precision/recall and durable restore open |

Current truth:

- registered real corpora: `6`;
- real million-scale row lanes: `3`;
- promoted lanes: `0`;
- candidate occurrences: `8,926` official historical elected outcomes; accepted nominal candidate corpus still `0` because official archive access is blocked;
- BDNS: current partitioned durable acquisition and v6 artifact reconcile `1,360,382` official rows, `1,419` page captures, `1,360,382` immutable version sightings, exact official identity retention, and unchanged `14`-file replay; append-only expansion revalidated source totals and completed all `89/89` selected daily windows without retry or dead work;
- accountability ledger: `126,760` real rows are recovered and validated after removing `10` fixture-derived money rows; the mix remains parliamentary-heavy and below `R2`;
- documents: `21,398` real instances / `19,538` content hashes are inventoried; source provenance, extraction quality, and OCR coverage remain below gate;
- corruption-risk publication: `0` promoted representative lanes and therefore no inferred high-risk public verdict is authorized.

Status: `REAL FOUNDATION READY; SOCIETAL SCALE INCOMPLETE`.

## 6. Target Architecture

### 6.1 Control plane

- One durable work contract for discovery, fetch, parse, OCR, normalize, identity, enrich, review, aggregate, and publish.
- Atomic claims, leases, heartbeats, retry classes, dead letters, host budgets, and circuit breakers.
- Stable payload references only; no document bytes inside queue rows.
- SQLite remains the reproducible snapshot and single-node baseline.
- Move operational coordination to a server database only after measured lock/throughput pressure; preserve SQLite export semantics.

### 6.2 Object plane

- Raw and derived bytes keyed by SHA-256.
- Stream to bounded partial files; publish only after checksum and size completion.
- Local disk is disposable cache.
- Versioned S3-compatible public origin is the durable source for public artifacts.
- Metadata includes URL, status, headers allowed by policy, size, checksum, retrieval, attempt, content type, and parser lineage.
- Retention, replication, encryption, lifecycle, and restore are explicit.

### 6.3 Transform plane

- Separate resumable stages with bounded batches.
- Additive schema evolution and stable public IDs.
- Input checksum plus transformer version controls invalidation.
- Unchanged inputs reuse verified partitions.
- Digital text extraction precedes OCR; OCR is page-scoped and cacheable.
- Model-assisted extraction creates evidence candidates, never unreviewed public allegations.

### 6.4 Analytical plane

- SQLite for canonical navigation and integrity constraints.
- Typed Parquet for high-volume immutable facts.
- Partition by bounded source/snapshot/jurisdiction/year keys.
- Manifests contain schema, counts, min/max, checksums, supersession, and source coverage.
- Aggregates rebuild from canonical facts; dashboards are never the only copy.

### 6.5 Public delivery plane

- Static-first citizen surfaces with bounded JSON indexes and drill-down shards.
- Public dataset/object origin for large analytical downloads.
- Stable cursors, content hashes, immutable release IDs, cache headers, and old-link tests.
- Every claim exposes freshness, coverage, uncertainty, evidence, correction state, and shareable state.

### 6.6 Integrity and review plane

- Signals are triage artifacts, not findings.
- High-risk publication requires corroboration, human review, conflict disclosure, counterevidence, right of reply where appropriate, and correction/version history.
- Official court, audit, or control-body findings remain distinct from project inference.
- Reviewer operational credentials and non-public session state follow least-exposure rules. Official public-domain identity evidence remains publishable and traceable.

## 7. Delivery Program

Dependencies are strict. A later wave may prototype, but it cannot claim completion before its inputs pass.

### Wave 0 — Truthful foundation and artifact recovery

Target: two weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W0-001` | Enforce official-real-only registry in local and CI readiness | none | disallowed evidence fails; six current corpora pass actual file and provenance audit |
| `W0-002` | Remove obsolete capacity-only outputs, generators, recipes, and roadmap claims | `W0-001` | repository search and artifact inventory show no such output used for readiness |
| `W0-003` | `DONE 2026-08-12`: regenerate and scale BDNS semantic root from fresh official acquisition | storage preflight | `1,360,382` rows; v6 manifest/full validation; exact source/amount/public-field balance; `1/1` unchanged partition reused through `14/14` hardlinks; validator peak RSS `292.719 MB` via disk-backed exact uniqueness |
| `W0-004` | Regenerate accountability-ledger root from current canonical evidence | BDNS optional; votes required | every ledger edge resolves; actor/issue/role unknowns explicit; full validation |
| `W0-005` | Reconcile live document inventory to actual object/text files | none | instance/object/fetch/extract/OCR totals balance; missing objects classified |
| `W0-006` | Repair the 350 vote rows without public URLs or document a checksum-backed official replacement | official source availability | `DONE 2026-08-12`: verified Congreso capture URL plus official/captured checksums; `0` unexplained missing URL rows |
| `W0-007` | Inventory official HTTP lineage and secure/capture immutable replacements | `W0-006` | zero unclassified insecure-origin rows; promotion policy explicit |
| `W0-008` | Make tracker, technical roadmap, and project knowledge match current artifacts | `W0-001..007` | no absent artifact is `DONE`; commands and next gates current |

Wave exit:

- current real artifacts are complete, named, independently validated, and recoverable locally;
- readiness report contains no stale or missing artifact claim;
- every open gap has owner, next command, input requirement, and exit gate.

### Wave 1 — Durable origin and clean-room recovery

Target: four weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W1-001` | Choose public S3-compatible origin and write bucket/key/version/retention contract | `W0` | ADR, config contract, no credentials committed |
| `W1-002` | Upload immutable raw objects by SHA-256 | `W1-001` | idempotent upload report; remote checksum verified |
| `W1-003` | Upload Parquet/shards/manifests as immutable release | `W1-001` | release manifest balances remote objects and bytes |
| `W1-004` | Add origin-to-cache fetch by checksum | `W1-002` | deleted local sample restores byte-identically |
| `W1-005` | Run full clean-room restore of one million-row lane | `W1-003..004` | new environment validates rows/files/hashes with no local hidden state |
| `W1-006` | Add database rebuild from immutable inputs | `W1-002` | canonical slice rebuilds; FK/integrity and logical totals reconcile |
| `W1-007` | Define RPO/RTO, release rollback, and supersession | `W1-003` | rehearsed rollback and latest-pointer recovery |
| `W1-008` | Publish storage health without secrets or workstation paths | `W1-003` | public status artifact passes publication-hygiene gate |

Wave exit: local disk can be lost without losing published evidence.

### Wave 2 — Real document and OCR factory

Target: six weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W2-001` | Classify every real document by source, MIME, size, language, page count, encryption, and text density | `W0-005` | `100%` classified or explicit unknown |
| `W2-002` | Apply per-host discovery/fetch budgets and politeness | `W1` | host SLO and request budget report |
| `W2-003` | Stream fetch with byte/time limits, checksum, partial cleanup, retries, and dead letters | `W2-002` | every item terminal or reclaimable; zero orphan partials |
| `W2-004` | Extract digital PDF, HTML, and office text by page/section | `W2-001` | page lineage, parser version, character counts, failure reason |
| `W2-005` | Route only text-poor pages to OCR | `W2-004` | route reason and input/engine/version cache key persisted |
| `W2-006` | Build a stratified 100,000-document official cohort | `W2-001..005` | source/format/size/language strata published |
| `W2-007` | Human-review extraction and OCR quality | `W2-006` | precision/recall or character/field accuracy by stratum; disagreements adjudicated |
| `W2-008` | Publish cost and throughput per 1,000 documents/pages | `W2-006` | requests, bytes, CPU, RSS, OCR pages, storage, failures, cost |
| `W2-009` | Scale to one million documents by source cohorts | `W2-006..008` | `R2` SLO, clean restore, bounded delivery, correction path |

Wave exit: one million official documents are preserved and usable, not merely downloaded.

### Wave 3 — Actors, candidates, offices, and identity

Target: eight weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W3-001` | Resolve official Infoelectoral candidate archive access with a reproducible method | external lever | one archive retrieved with official origin/checksum and documented contract |
| `W3-002` | Ingest the queued official election archives in bounded cohorts and retain every official public identity field | `W3-001` | archive/member/candidate/party counts and field-level identity retention reconcile per election |
| `W3-003` | Add official regional and municipal candidacy/result sources | source contracts | jurisdiction/election coverage matrix and source totals |
| `W3-004` | Add party-office and political-appointment history | official registries/bulletins | appointment/dismissal dates and appointing authority traceable |
| `W3-005` | Preserve source identity, deterministic candidate link, reviewed link, conflict, and unresolved states | `W3-002..004` | no forced ambiguous merge |
| `W3-006` | Create stratified adjudicated identity gold set | `W3-005` | dual review, adjudication, precision/recall by source and name pattern |
| `W3-007` | Add immutable merge/split history | `W3-005` | old evidence identities remain reconstructable |
| `W3-008` | Reach one million real actor/candidate/mandate/appointment rows | `W3-002..007` | `R2` manifest, identity quality, restore, public origin, corrections |

Wave exit: public actor histories never depend on an unreviewed ambiguous identity merge.

### Wave 4 — Parliamentary decisions and text-at-decision

Target: eight weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W4-001` | Complete Congress/Senate legislature/session discovery | source contracts | official event totals and missing ranges published |
| `W4-002` | Preserve initiative and amendment versions | `W2` | text-at-vote-time distinct from later consolidated text |
| `W4-003` | Ingest signatories, speeches, committee stages, and group/member votes | `W4-001..002` | source totals and FK balance per chamber/legislature |
| `W4-004` | Preserve yes/no/abstain/absence/no-vote as distinct source states | `W4-003` | no fabricated member assignment from aggregate gaps |
| `W4-005` | Repair or classify all vote-total mismatches | `W4-003..004` | each mismatch has a source-supported reason or open incident |
| `W4-006` | Link actors through reviewed source identities | `W3`, `W4-003` | link quality reported; unresolved visible |
| `W4-007` | Publish million-row analytical facts and bounded drill-down shards | `W4-003..006` | `R2` validation, origin, restore, public payload budget |

Wave exit: a vote explainer reproduces the official decision, people, text, totals, provenance, and known gaps.

### Wave 5 — Money, implementation, and enforcement

Target: twelve weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W5-001` | Expand PLACSP through complete bounded official archive cohorts | `W1` storage | gap-free period catalog, version/tombstone balance, one million real facts |
| `W5-002` | `PARTIAL 2026-08-12`: complete BDNS pagination and revision handling | `W0-003` | selected-window pagination is complete at `89/89`; next: second snapshot/revisions, full historical cohorts, durable origin and clean restore |
| `W5-003` | Add budget appropriations and execution | official source contract | budget version, unit, program, territory, and execution semantics preserved |
| `W5-004` | Separate notice, award, modification, invoice, payment, and budget execution | `W5-001..003` | no award represented as payment |
| `W5-005` | Resolve counterparties with reviewed identifiers and merge history | `W3-005..007` | entity precision/recall; official natural-person identifiers retained with provenance |
| `W5-006` | Add inspections, sanctions, permits, staffing, and audit findings | official sources | typed implementation facts with authority and effective dates |
| `W5-007` | Reconcile monetary totals by source, period, currency, tax treatment, and revision | `W5-001..006` | declared discrepancies and no float-induced drift |
| `W5-008` | Publish bounded public-money dossiers | `W5-007` | source-to-entity-to-contract-to-payment evidence chain |

Wave exit: the product distinguishes promised, budgeted, contracted, paid, delivered, inspected, sanctioned, and unknown.

### Wave 6 — Responsibility and issue ledgers

Target: ten weeks. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W6-001` | Ingest BOE and official bulletin rules, decrees, orders, resolutions, and appointments | `W2` | originator, approver, publisher, effective date, version, repeal state |
| `W6-002` | Model competence, delegation, transfer, oversight, and current owner | official legal sources | time-bounded responsibility edge with evidence |
| `W6-003` | Define controlled issue taxonomy and versioned codebook | domain review | inclusion/exclusion examples and change history |
| `W6-004` | Extract measures and obligations from official text | `W2`, `W6-003` | evidence span, extractor version, confidence, review state |
| `W6-005` | Link promises, decisions, rules, money, implementation, enforcement, audits, and outcomes | `W4..006`, `W5` | every edge typed and traceable; unknown edges explicit |
| `W6-006` | Rebuild the accountability ledger to one million representative facts | `W6-001..005` | domain/source/role mix, actor quality, `R2` origin/restore/corrections |
| `W6-007` | Publish three complete issue-led dossiers | `W6-006` | citizen can see who did what, who owns it now, and what is missing |

Wave exit: responsibility attribution is temporal, sourced, and separable from political rhetoric.

### Wave 7 — Outcomes and causal discipline

Target: eight weeks. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W7-001` | Approve representative indicator codebook | domain review | unit, geography, frequency, methodology, known breaks, intended use |
| `W7-002` | Add official national, regional, and municipal outcome sources | `W7-001` | source contracts and coverage matrix |
| `W7-003` | Capture second and later snapshots with revisions/deletions | `W7-002` | unchanged/changed/deleted observations version correctly |
| `W7-004` | Reach one million representative outcome observations | `W7-002..003` | `R2` validation, origin, restore, correction workflow |
| `W7-005` | Define descriptive, associational, quasi-experimental, and causal claim levels | methodology review | UI language and publication gate per level |
| `W7-006` | Record confounders, comparison group, sensitivity, and caveats | `W7-005` | causal claim cannot publish without method evidence |
| `W7-007` | Link observed outcomes to issue ledgers conservatively | `W6`, `W7-006` | chronology shown separately from causality |

Wave exit: the product can say what changed without implying unsupported causation.

### Wave 8 — Integrity signals, review, and corrections

Target: eight weeks. Priority: `P0` before any high-risk public inference.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W8-001` | Version review task, evidence, confidence, disagreement, and adjudication contracts | `W0` | append-only review history |
| `W8-002` | Create real historical review calibration set from official findings | legal/editorial review | gold labels cite court/audit/control-body sources |
| `W8-003` | Define signal thresholds and minimum cohorts | `W5`, `W8-002` | small-cohort and missing-data suppression tested |
| `W8-004` | Require corroboration and conflict disclosure | `W8-003` | no single weak signal can become public high-risk claim |
| `W8-005` | Implement counterevidence, appeal, right-of-reply, and correction queues | `W8-001` | each path reaches public supersession state |
| `W8-006` | Measure agreement, reversal, drift, correction latency, and queue age | `W8-002..005` | release scorecard |
| `W8-007` | Publish only reviewed signals with evidence cards and limitations | `W8-003..006` | legal/editorial/publication-hygiene gate and immutable claim version |

Wave exit: a disputed claim can be audited and corrected without erasing history.

### Wave 9 — Public product and open-source scale

Target: continuous after Wave 1; promotion gate after Waves 3-8. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W9-001` | Publish source coverage and obstruction map | `W0` | freshness, completeness, last run, blocker evidence per source |
| `W9-002` | Publish vote, actor, issue, money, and responsibility explainers | corresponding lanes | primary evidence within three meaningful interactions |
| `W9-003` | Publish stable Evidence API and schema compatibility policy | `W1`, analytical contracts | versioned endpoints, pagination, changelog, deprecation window |
| `W9-004` | Provide source-adapter SDK and one-command validation | pipeline contracts | new contributor runs capture-to-artifact without private state |
| `W9-005` | Create bounded starter issues and maintainer ownership map | `W9-004` | no critical lane has one undocumented owner |
| `W9-006` | Require two-person review for schema, identity, publication, and allegation-policy changes | governance | protected ownership and review evidence |
| `W9-007` | Publish contributor, review, data-correction, security, and citation paths | none | response SLO and templates visible |
| `W9-008` | Measure first-contribution time, review latency, retention, bus factor, and source adoption | `W9-004..007` | quarterly community scorecard |
| `W9-009` | Support independent snapshot replicas and reproducibility attestations | `W1`, `W9-003` | external maintainer reproduces and signs release manifest |

Wave exit: three independent maintainers can ship a connector or review batch, and an external party can reproduce a release.

## 8. Critical Path

Strict order:

1. `W0`: truthful artifact inventory and recovery.
2. `W1`: durable public origin and clean restore.
3. `W2`: 100,000-document quality gate, then document `R2`.
4. `W3` and `W4`: actor identity and parliamentary completeness.
5. `W5`: money, implementation, and enforcement.
6. `W6`: responsibility and issue ledgers.
7. `W7`: representative outcomes and causal guardrails.
8. `W8`: high-risk review/correction machinery.
9. `W9`: public product, API, and contributor replication throughout, with final promotion after upstream gates.

Parallelism allowed:

- W1 storage contract can start while W0 artifact recovery finishes.
- W2 document inventory can start from current real objects while W1 origin is prepared.
- W3 official-source discovery and W4 reconciliation can proceed independently.
- W9 documentation, source catalog, and safe public explainers can ship continuously.

Parallelism forbidden:

- no public inferred integrity signal before W8;
- no identity merge before adjudicated identity evidence;
- no causal claim before W7 methodology gate;
- no lane promotion from row count alone;
- no source marked complete while official totals or time ranges remain unknown.

## 9. Release And Accountability Cadence

Every ingestion run emits:

- source and snapshot identity,
- discovered/fetched/stored/parsed/normalized/published counts,
- bytes and checksums,
- attempts, retries, dead items, and blocker classes,
- elapsed time, CPU, RSS, and storage delta,
- parser/schema versions,
- freshness and source-total reconciliation,
- publication-hygiene findings,
- current limitations and next action.

Every weekly closeout:

- update the tracker from generated evidence,
- publish visible progress under repository control,
- close or reclassify stale work,
- run publication hygiene, integrity, readiness, and relevant tests,
- list newly observed blockers and owners.

Every public release:

- immutable release manifest,
- schema and method changelog,
- source coverage and freshness report,
- validation and publication-hygiene reports,
- known limitations,
- corrections and superseded claims,
- restore attestation,
- rollback pointer.

Every quarter:

- coverage matrix by jurisdiction, time, source, and lane,
- SLO and cost scorecard,
- correction and reversal analysis,
- identity and extraction quality sample,
- community health and bus-factor scorecard,
- roadmap re-prioritization based on public impact and evidence gaps.

## 10. Success Metrics

Data:

- real rows/documents by lane and scale class;
- official universe coverage by source and period;
- provenance, public URL, and source-record coverage;
- source-total and monetary reconciliation;
- identity precision/recall and unresolved rate;
- extraction/OCR quality by stratum;
- freshness and source-drift incidents.

Operations:

- successful unattended refreshes;
- queue age, retry rate, dead rate, recovery time;
- throughput, peak RSS, storage growth, and cost per `1,000`;
- clean restore time and checksum success;
- release rollback time.

Public value:

- evidence drill-down completion;
- explainers used and shared;
- correction response and publication latency;
- citations by journalists, researchers, civil society, and public bodies;
- documented decisions improved or errors corrected because evidence was available.

Community:

- active maintainers and reviewers;
- first-contribution time and review latency;
- contributor retention;
- independently maintained source adapters;
- independent release reproductions;
- critical-lane bus factor.

## 11. Definition Of Societal-Scale Done

The goal is achieved only when all are true:

- every priority lane reaches `R2` with official real records or the complete documented official universe when smaller;
- at least the core vote, actor, document, money, responsibility, outcome, and correction lanes have durable public origins and clean-room restores;
- national-history lanes operate incrementally with declared freshness and cost SLOs;
- public routes remain bounded, accessible, evidence-first, and reproducible;
- identity, extraction, and review quality are measured on adjudicated official evidence;
- integrity signals cannot bypass corroboration, human review, counterevidence, and correction;
- releases are auditable, reversible, retain official public-domain identity, exclude secrets/non-public state, and are independently reproducible;
- at least three independent maintainers can operate critical paths;
- no known missing evidence or blocked source is mislabeled as complete.

Until then, the system may be useful and impactful, but the societal-scale goal remains open.
