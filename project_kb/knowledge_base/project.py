"""Vota con La Chola durable project knowledge.

This package is the canonical agent-facing KB. It points to roadmap/backlog
sources without replacing them.
"""

from datetime import date

from project_kb.schema import (
    Decision,
    DomainConcept,
    Evidence,
    Fact,
    Gotcha,
    ReferenceMap,
    Workflow,
)

UPDATED = date(2026, 8, 30)


PROJECT_DECISIONS = [
    Decision(
        name="Use project KB as durable agent memory",
        description=(
            "Use `project KB` for durable agent learning, verified decisions, "
            "gotchas, and reusable workflows. Roadmaps and operational backlog "
            "stay in their existing canonical files."
        ),
        rationale=(
            "Future agents need one validated project-learning artifact without "
            "creating another roadmap or tracker."
        ),
        consequences=[
            "Update existing KB entries before adding near-duplicates.",
            "Use repo-relative evidence paths only.",
            "Keep public roadmap and tracker content in their existing files.",
        ],
        evidence=[
            Evidence(
                source="project_kb package",
                detail="Typed KB scaffold created by project-knowledge-base skill.",
            ),
            Evidence(
                source="AGENTS.md",
                detail="Documentation philosophy defines one source of truth per layer.",
            ),
        ],
        references={"project KB": "decision.Use project KB as durable agent memory"},
        updated_at=UPDATED,
    ),
    Decision(
        name="Keep roadmap hierarchy outside KB",
        description=(
            "Treat `roadmap hierarchy` as external source of truth: future scope "
            "in ROADMAP.md, strategy in docs/roadmap.md, technical execution in "
            "docs/roadmap-tecnico.md, and operational status in "
            "docs/etl/e2e-scrape-load-tracker.md."
        ),
        rationale=(
            "Repo instructions explicitly forbid duplicate roadmaps in random docs. "
            "KB should route agents, not fork planning authority."
        ),
        consequences=[
            "Direction changes update ROADMAP.md first.",
            "Operational state changes update docs/etl/e2e-scrape-load-tracker.md.",
            "KB entries may summarize stable mechanics but not create new priority.",
        ],
        evidence=[
            Evidence(
                source="ROADMAP.md",
                detail="Mandate section defines roadmap authority and derived docs.",
            ),
            Evidence(
                source="docs/README.md",
                detail="Docs index names roadmap and tracker source-of-truth files.",
            ),
            Evidence(
                source="AGENTS.md",
                detail="Documentation philosophy says do not duplicate roadmaps.",
            ),
        ],
        references={"roadmap hierarchy": "reference_map.Canonical document map"},
        updated_at=UPDATED,
    ),
    Decision(
        name="Preserve identities published by official sources",
        description=(
            "`public accountability identity` means names, identifiers, dates of "
            "birth, official contacts, suppliers, beneficiaries, candidates, and "
            "representatives remain exactly as an official public source publishes "
            "them. Publication hygiene removes secrets, session material, workstation "
            "paths, and non-public data; it does not anonymize public evidence."
        ),
        rationale=(
            "The product must let citizens trace public decisions and spending to the "
            "people and organizations named in the underlying official record."
        ),
        consequences=[
            "Do not redact or hash identity fields copied from official public records.",
            "Keep source URL, capture lineage, and observation time beside identity data.",
            "Never use the accountability rule to publish credentials, private session data, or non-public personal data.",
        ],
        evidence=[
            Evidence(
                source="AGENTS.md",
                detail="Publication hygiene distinguishes public-source identity from secrets and workstation data.",
            ),
            Evidence(
                source="tests/test_check_public_privacy_leaks.py",
                detail="Public identity is permitted while local and secret material remains blocked.",
            ),
            Evidence(
                source="docs/etl/sprints/DATA-INTEGRITY-20260812/report.md",
                detail="Real-only correction and public identity-retention policy.",
            ),
        ],
        references={
            "public accountability identity": "gotcha.Public artifact hygiene gate is mandatory"
        },
        updated_at=UPDATED,
    ),
    Decision(
        name="Separate review capacity from reviewer operations",
        description=(
            "`review capacity separation` keeps the immutable C2C capacity snapshot "
            "limited to real source-derived tasks, required review slots, and "
            "machine audit evidence. Reviewer identities, trust roots, "
            "authorizations, conflicts, assignments, claims, decisions, "
            "adjudications, promotions, release bindings, and publications belong "
            "only in a separately versioned operational snapshot."
        ),
        rationale=(
            "Millions of available tasks prove bounded queue capacity, not human "
            "review, semantic validity, publication authority, or societal impact."
        ),
        consequences=[
            "Never bootstrap reviewers, trust roots, decisions, or approvals with invented records.",
            "Reject operational mutation of the canonical capacity database.",
            "Require externally supplied real identity, authority, conflict, assignment, and review evidence before an operational snapshot can advance.",
            "Keep semantic promotion and public release closed until their independent gates pass.",
        ],
        evidence=[
            Evidence(
                source="etl/data/manual/outcome_links/review_control_scope_c2c_v1.json",
                detail="Pinned real capacity scope and explicit empty operational trust state.",
            ),
            Evidence(
                source="etl/load/sqlite_schema.sql",
                detail="Append-only review-control, authorization, lease, decision, eligibility, release, and publication contracts.",
            ),
            Evidence(
                source="scripts/operate_outcome_review_control_c2c.py",
                detail="Fail-closed boundary between read-only capacity status and separately versioned real operations.",
            ),
        ],
        references={
            "review capacity separation": "workflow.Rebuild outcome review capacity"
        },
        updated_at=UPDATED,
    ),
]


PROJECT_REFERENCE_MAPS = [
    ReferenceMap(
        name="Canonical document map",
        description=(
            "`canonical document map` routes future agents to the right source: "
            "ROADMAP.md for future direction, docs/roadmap.md for strategy/model "
            "background, docs/roadmap-tecnico.md for near-term execution, "
            "docs/etl/e2e-scrape-load-tracker.md for operational status, "
            "docs/etl/name-and-shame-access-blockers.md for confirmed access "
            "obstruction, and AGENTS.md for agent operating rules."
        ),
        mappings={
            "future direction": "ROADMAP.md",
            "strategy and model background": "docs/roadmap.md",
            "near-term execution": "docs/roadmap-tecnico.md",
            "operational backlog and status": ("docs/etl/e2e-scrape-load-tracker.md"),
            "public-data obstruction log": (
                "docs/etl/name-and-shame-access-blockers.md"
            ),
            "agent operating rules": "AGENTS.md",
            "documentation index": "docs/README.md",
        },
        evidence=[
            Evidence(source="README.md", detail="Leer primero section."),
            Evidence(source="docs/README.md", detail="Docs source-of-truth index."),
            Evidence(
                source="AGENTS.md",
                detail="Documentation philosophy and working agreement.",
            ),
        ],
        references={"canonical document map": "reference_map.Canonical document map"},
        updated_at=UPDATED,
    )
]


PROJECT_FACTS = [
    Fact(
        name="BOE document and candidate cohorts preserve exact public evidence",
        description=(
            "`BOE accountability cohorts` use the official daily summary API as "
            "discovery evidence and the official per-document XML endpoint as the "
            "immutable payload. The current BOE summary cohort is terminal: 1,166 "
            "official summaries succeeded and 191 exact requested dates returned official "
            "HTTP 404 responses. The document queue contains 100,867 official jobs: "
            "100,051 succeeded, one is dead after three connect timeouts, and 815 remain "
            "unfinished. Current physical promotion therefore fails closed. Its 100,051-row "
            "portable lineage now uses a 7,717-byte manifest-last index plus 11 immutable "
            "content-addressed gzip shards / 16,081,029 compressed bytes. Logical SHA-256 "
            "99739ca6... binds all 234,632,869 uncompressed bytes; independent full validation "
            "rehashes every shard, document, and referenced summary. It references 1,156 of "
            "the 1,166 successful summaries. Exact manifest archives, immutable activation "
            "receipts, predecessor linkage, refusal of ambiguous historical reactivation, and "
            "a no-deletion policy make index changes auditable. The production full-shard "
            "lifecycle audit reports one active generation and zero orphan, unactivated, "
            "interrupted-staging, or deletion state. A test over real BOE captures forces an "
            "interruption before the live switch, proves the prior index remains byte-identical "
            "and valid, then completes a successor while retaining both generations. "
            "Separately, the deterministic 100,000-row acquisition "
            "plan closes its numeric supply gate with selection SHA-256 "
            "c81d3c0a90222122309a259c791cdbb9ffa900f21f96eed5a12d30a71f314185: "
            "98,748 BOE XML, 1,166 BOE summaries, and 86 Parliament of Andalusia files. "
            "That plan is not a claim that all planned bytes have been freshly acquired. "
            "Exact-date and exact-ID acquisition fails closed on missing documents. "
            "The source-scoped election parser derives "
            "42,056 exact public base candidate occurrences across 4,901 candidacies "
            "and seven proclamation documents for six election dates from 2015 to 2024. "
            "Eleven correction documents retain all 956 exact paragraphs. The reviewed "
            "2023/2024 subset contains 10,815 base rows; three applied corrections retain "
            "180 paragraphs, of which 127 support 17 operations and 53 are context. "
            "Those operations produce 10,820 effective rows. Eight corrections and 776 "
            "paragraphs remain captured_unapplied; their 31,241 base candidates are "
            "excluded from effective state. A deterministic 776-task dual-review queue "
            "retains exact BOE text with blank decisions and references one deduplicated "
            "3,713-candidacy / 31,241-candidate public context corpus; readiness rehashes "
            "and reconciles both artifacts. The November 2019 source is captured but "
            "candidate ingestion fails closed because one heading omits its number. "
            "Every effective occurrence has normalized "
            "person, party, source-record, and document-source lineage; unchanged names reuse "
            "10,795 exact base person links, while 25 changed/new names remain source-scoped. "
            "All 88 correction-backed rows have immutable effective source records. The v3 "
            "semantic artifact retains every exact public name and source paragraph in two "
            "validated Parquet partitions and replays both unchanged files by hardlink. It "
            "never infers a missing identifier, cross-source identity, or elected outcome. "
            "The current document inventory contains 122,607 eligible real official "
            "instances and 120,757 distinct contents. Native extraction finishes all "
            "120,757 contents without failure. A content-deduplicated profile rehashes "
            "raw and native CAS bytes, retains 122,288 machine-language candidates and "
            "319 explicit unknown instances, observes encryption for all 1,437 PDFs, "
            "and marks all 120,757 contents unreviewed. Independent full replay has zero "
            "mismatch, and two immutable profile generations retain one exact "
            "predecessor/supersession chain. Machine candidates are sampling evidence, "
            "not human ground truth. Native extraction v7 preserves PDF angle-bracket "
            "content as plain text and produces 2,211,254,429 public characters. Exact "
            "locator v3 covers every content and file instance with 30,634 PDF pages, "
            "782,814 source-derived major XML/HTML sections, and 5,333 exact fallback "
            "spans; independent replay rehashes all raw/native bytes and recomputes "
            "879,104 instance locators with zero mismatch. A depth-3 canary was rejected "
            "because it averaged about 79 locators per document and reached 25,061 on "
            "one BOE file; the major-container design averages 6.780402, caps the "
            "observed maximum at 1,568, projects 6,780,402 content locators at one "
            "million documents, fails generation/replay fast above 2,000, and enforces "
            "a complete-report average gate of 10. The "
            "real profile observes 108,042 XML, 13,128 HTML, 1,437 "
            "PDF, and zero office files, so office extraction support remains explicitly "
            "unclaimed. Locator manifests copy no public text. The bounded OCR lane "
            "finishes all 856 candidates. "
            "The deterministic 40-row human-review packet remains blank and "
            "pending, so no machine label or invented decision is promoted. Incremental "
            "replay reuses checksum-identical rows instead of reparsing unchanged files."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus.json",
                detail="Official date cohort, queue reconciliation, and portable manifest evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus-lineage-validation-20260830.json",
                detail="Independent bounded-shard, raw-capture, summary, logical-order, and public-information validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus-generation-audit-20260830.json",
                detail="Full-shard archive, activation receipt, predecessor, retention, and no-deletion audit.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-election-candidates-latest.json",
                detail="Exact candidate, candidacy, correction, identity-retention, and idempotence totals.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-election-candidate-correction-materialization.json",
                detail="Immutable correction operations, effective-state totals, before/after evidence, and base preservation.",
            ),
            Evidence(
                source="etl/data/published/candidate-occurrence-semantic-partition-manifest-latest.json",
                detail="Exact public identity, official text, normalized lineage, correction, partition, and unchanged-replay contract.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-format-inventory.json",
                detail="Current 100k-plus official inventory and incremental reuse metrics.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-disk-planner-100k-validation-20260830.json",
                detail="Exact 100,000-row real official plan, pinned selection identity, source mix, and zero numeric supply gap.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-source-universe-validation-20260829.json",
                detail="Independent source-universe validation including physical eligibility and public-identity retention.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-access-timeout-20260830.md",
                detail="Bounded reproducible evidence for the current BOE XML connect-timeout blocker.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-validation.json",
                detail="Independent full native-text manifest and CAS validation for the current real corpus.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-locator-validation.json",
                detail="Independent full raw/native replay and exact recomputation of every PDF-page, semantic markup-section, and fallback-span locator.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-language-encryption-validation.json",
                detail="Independent full raw/CAS replay of every machine-language candidate and every PDF encryption observation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-profile-generation-audit.json",
                detail="Two retained profile generations, predecessor linkage, restored state, full shards, and zero lifecycle debris.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-validation.json",
                detail="Independent bounded OCR state, manifest, and CAS validation for all current candidates.",
            ),
        ],
        references={
            "BOE accountability cohorts": "workflow.Ingest official BOE election candidates"
        },
        updated_at=UPDATED,
    ),
    Fact(
        name="Source truth code paths",
        description=(
            "`source truth code paths` are etl/load/sqlite_schema.sql for schema, "
            "scripts/ingestar_politicos_es.py for representatives ETL, "
            "scripts/ingestar_parlamentario_es.py for parliamentary ETL, "
            "scripts/graph_ui_server.py for UI/API, ui/graph/explorer.html for "
            "Explorer, and ui/citizen/index.html for the static Citizen UI."
        ),
        evidence=[
            Evidence(source="AGENTS.md", detail="Working Agreement source of truth."),
            Evidence(source="README.md", detail="Fuente de verdad code section."),
        ],
        references={"source truth code paths": "reference_map.Canonical document map"},
        updated_at=UPDATED,
    ),
    Fact(
        name="Project is static and SQLite first",
        description=(
            "`SQLite first` architecture means one operational SQLite, reproducible "
            "snapshots, raw/source traceability, and static-first public surfaces "
            "unless server requirements are explicitly approved."
        ),
        evidence=[
            Evidence(source="README.md", detail="Repo summary and current MVP."),
            Evidence(
                source="AGENTS.md",
                detail="Operating notes, Citizen-first product rules, and ETL rules.",
            ),
            Evidence(
                source="docs/roadmap-tecnico.md",
                detail="Target architecture keeps monolith lean and one SQLite.",
            ),
        ],
        references={"SQLite first": "domain_concept.Static evidence platform"},
        updated_at=UPDATED,
    ),
    Fact(
        name="Reusable publicdata packages exist",
        description=(
            "`publicdata packages` are extracted reusable libraries under "
            "publicdata_core, publicdata_docs, publicdata_publish, "
            "publicdata_evidence, publicdata_ops, publicdata_policy_es, "
            "publicdata_sqlite, and publicdata_connectors_es."
        ),
        evidence=[
            Evidence(
                source="pyproject.toml", detail="Package metadata and find rules."
            ),
            Evidence(
                source="publicdata_core/README.md",
                detail="Reusable package README exists.",
            ),
            Evidence(
                source="publicdata_connectors_es/README.md",
                detail="Connector package README exists.",
            ),
        ],
        references={"publicdata packages": "workflow.Contributor source onboarding"},
        updated_at=UPDATED,
    ),
    Fact(
        name="Readiness counts only verified official corpora",
        description=(
            "`real-only readiness` means every counted row comes from an identifiable "
            "official source and every artifact is reconciled against its materialized "
            "files, hashes, rows, source IDs, and origin allowlist. The registry currently "
            "validates 1,809,222 member votes in 8,373 shards, 1,755,809 Eurostat "
            "observations in 37 Parquet files, 263,302 PLACSP money facts in 50 files, "
            "1,360,382 BDNS subsidy facts in 14 files, 126,760 accountability-ledger "
            "entries in 13 files, and 88,031 actor mandates in 108 files. Three lanes exceed one million real "
            "rows and zero lanes are promoted. The vote artifact now has 100 percent "
            "public URL/source-record coverage after one checksum-backed official capture "
            "override repaired 350 rows. Its 102,172 historical HTTP rows across 1,166 "
            "Senate URLs are fully classified without rewrite: 33,683 rows across 484 URLs "
            "have local checksum captures and 68,489 rows across 682 URLs lack an immutable "
            "replacement; two bounded HTTPS-equivalence probes returned 403 HTML. "
            "Eurostat, PLACSP, and actor unchanged replays pass. The content-addressed "
            "HF v2 release is remotely verified for all six corpora, with stable artifact, "
            "registry, and readiness parity and no verifier warnings. All six durable-public-origin and clean-room-restore flags are "
            "true after isolated validators full-read every published corpus. Explicit "
            "immutable-release recovery is also proven without reading the mutable latest "
            "pointer: the actor drill restored 114 files and full-validated 88,031 rows. "
            "That restored actor corpus also rebuilds twice into byte-identical SQLite "
            "artifacts with exact logical-row hashing, 88,031 unique mandate IDs, and "
            "integrity checks green; normalized production-schema reconstruction remains open. "
            "Raw-object replication and full-manifest restore now use bounded worker batches; "
            "two local CAS replays deterministically reconcile 6,792 real objects and a full "
            "restore verifies all bytes, while external S3 durability remains unproven. "
            "Representative scope and corrections remain incomplete. "
            "The reusable typed contract also passes the real S1 accountability-"
            "ledger gate: 126,760 entries, 13 partitions/files, exact DB balance, "
            "100 percent public URL and evidence lineage, 126,757 resolved actor "
            "states, three explicit unresolved states, and full incremental reuse. "
            "It remains below one million, parliamentary-dominated, and unpromoted. "
            "The actor-mandate lane also passes the same local analytical contract "
            "at 88,031 mandates and 79,023 distinct people across 108 partitions/files, "
            "with complete public URL and explicit lineage coverage, independently "
            "validated identity states, and 108-partition incremental reuse. The "
            "Infoelectoral cohort adds 8,926 source-scoped historical election "
            "occurrences with direct entity links, versioned observations, explicit "
            "presence state, removal preservation, and a pre-mutation 15 percent "
            "per-chamber drift gate. It remains "
            "below the 100k S1 class; source-scoped identifiers do not prove external "
            "identity, and the output is local and unpublished. "
            "The public-money lane has exact-decimal S0 proof over ten canonical "
            "fallback-derived facts: five contract notices and five subsidy records, "
            "four partitions/files, complete source URL, lineage, amount and EUR "
            "coverage, independently validated semantics and publication hygiene, and full incremental "
            "reuse. That fallback-derived S0 artifact and its suppressive v3 policy are "
            "retired non-evidence. The current v5 contract requires exact retention of "
            "every official-source counterparty name and identifier. "
            "The amounts are published notice or award values, not verified payments "
            "or disbursements. Representative live PLACSP, supplier resolution, "
            "S2, and identity resolution remain open; clean restore passes. "
            "A fresh durable partitioned BDNS queue discovered 28,676,987 live "
            "concessions and completed 1,419 paced official pages without retry or dead "
            "work. It avoids unstable global deep offsets through 89 official daily "
            "windows, all now complete after an append-only expansion of the three "
            "previously truncated windows. It exactly reconciles 1,360,382 source "
            "records, record URLs, immutable version sightings, and raw-page checksum "
            "links over 1,080,788,680 captured bytes; SQLite passes quick_check and FK "
            "validation. The registered v5 semantic contract, exported as the v7 "
            "artifact revision, contains 1,360,382 subsidy facts in 14 Parquet files "
            "with exact total EUR 10,121,196,195.270000, full source URL/lineage/amount "
            "coverage, and independent full-row validation. All 1,360,382 official "
            "beneficiary names and all 163,270 source-published identifiers are retained "
            "exactly; 1,197,112 counterparties remain explicitly unclassified without "
            "field suppression. Unchanged replay reuses one partition through 14 "
            "hardlinks. Exact validation now uses a temporary disk-backed SQLite "
            "distinct index and stays below 293 MB peak RSS. This passes registered real "
            "million-row capacity, not promotion; subsidy awards are not verified "
            "disbursements. The worker now checks capacity before every claim and "
            "reserves raw-object plus SQLite/WAL growth. The first real preflight "
            "failed closed at -968,454,144 bytes of headroom without claiming work; "
            "after temporary artifacts were released, the current check is again "
            "blocked at 5,685,862,400 bytes free against "
            "10,863,247,360 required and -5,177,384,960 bytes of headroom. "
            "Full-history coverage, "
            "second-snapshot revision remain open. An older 146,000-row checkpoint and its v3 semantic roots lack "
            "a current compliant artifact and do not count toward readiness. "
            "Indicator observations now have an additive normalized-series link and "
            "a revision-preserving typed public contract for source lineage, domain, "
            "geography, value state, unit, frequency, methodology, canonical dimensions, "
            "and sole/superseded/latest state. A bounded official Eurostat "
            "registry now passes real indicator S1 and the S2 row-scale analytical "
            "subgate at 1,755,809 observations / 155,435 series across four JSON-stat "
            "datasets fetched with verified TLS and exact acquisition-to-normalization "
            "reconciliation. Keyset backfill plus a covering expression index bounds "
            "WAL growth, and dimensions are normalized once per series. Byte/cube-cell "
            "ceilings fail closed, while download chunks and committed DB batches "
            "renew the durable work lease and reject lost ownership. The semantic "
            "artifact passes independent full-row validation in 26 partitions / 37 "
            "Parquet files, and unchanged replay reuses all 26 partitions by 37 "
            "hardlinks. This remains unpromoted because the four-dataset demographic/"
            "economic mix is not representative and no second-snapshot revision delta "
            "has been measured; clean-environment restore passes. "
            "The HF analytical origin publishes all six corpora as 5,403,506 rows, "
            "8,595 canonical data files, and 498,631,274 bytes. Remote parity passed "
            "for the published release. Two fresh empty caches restore every registered "
            "corpus: BDNS downloads 20 selected files and the other five download 8,601, "
            "with every byte checksum-verified. Isolated no-project validators using only "
            "copied code full-read all 5,403,506 rows and 8,595 data files under bounded "
            "memory, without using canonical corpus input. A separate explicit rollback-"
            "candidate drill restored prior immutable release 623b4a5a... without reading "
            "the mutable pointer: 8,619 files and 504,093,303 bytes checksum-verified in "
            "1,199.614 seconds, followed by full validation of all six corpora and 5,403,506 "
            "rows at 1,007.453 MB peak RSS. A later GET-only plan rechecks live current "
            "5872efaf... and rollback target 623b4a5a..., binds all restore/validation/live "
            "evidence by SHA-256, proves zero row/file/byte delta, fixes compare-and-swap "
            "expectations, preserves both immutable releases, and records authorized=false "
            "and mutation_performed=false. Formal RPO and activation RTO remain open. "
            "A real Senate slice has 6,792 fetched/extracted "
            "XML/HTML documents and a successful local object-restore sample, but "
            "the broader real-only inventory now discovers 122,621 files and counts "
            "122,607 eligible file instances / 120,757 distinct contents after excluding "
            "fixtures/samples and preserved transport-failure captures from successful-"
            "document scale while retaining the latter as obstruction evidence. It includes "
            "1,437 PDFs / 44,927 pages. Page-density routing finds 856 OCR candidates. "
            "Resumable v7 extraction processes all 120,757 distinct contents into 119,338 "
            "checksum-addressed text objects and 2,211,254,429 unsanitized public characters, "
            "with zero failure or truncation; independent validation rehashes every raw "
            "instance and CAS object. Locator v3 covers 30,634 PDF pages, 782,814 "
            "source-derived major markup sections, and 5,333 exact fallback spans, "
            "producing 818,781 content and 879,104 instance locators without copying "
            "public text; full replay reports zero mismatch. The profile observes only "
            "XML, HTML, and PDF, with zero office-format instances; office support is "
            "therefore unclaimed pending a representative real cohort. "
            "Additive OCR processes all 856 candidate pages "
            "across 58 PDFs, producing 89,632 characters on 849 pages, seven explicit "
            "no-text results, 17 material gains, and 131 independently verified OCR CAS "
            "objects. A deterministic 40-page real review packet covers every no-text "
            "and material-gain page with blank human fields; review is 0/40, so semantic "
            "accuracy, scanned/office/language diversity, remote origin, and one-million "
            "scale remain open; the stored-corpus numeric 100k gate passes. A zero-network, "
            "disk-backed audit and independent replay reduce 337,701 real provenance edges "
            "to 115,246 unique official public URLs / 111,600 HTTPS. Exactly 101,303 HTTPS "
            "URLs combine an implemented semantic contract with clean physical proof, so "
            "numeric supply for 100k closes; representativeness remains a separate maintainer "
            "decision. The deterministic plan selects and preflights exactly 100,000 real "
            "official rows: 98,748 BOE documents, 1,166 BOE summaries, and 86 Parliament "
            "of Andalusia files, with zero mock/synthetic rows and public information retained. "
            "Physical BOE acquisition remains incomplete at 100,051 of 100,867 document "
            "successes, one dead network timeout, and 815 unfinished. The v4 "
            "cohort planner now deduplicates and orders through file-backed SQLite, streams "
            "bounded deterministic shards, preserves exact Parliament db-ref/table-name "
            "pairs, locks every output through kernel advisory locks, rehashes immutable "
            "inputs before and after use, and publishes a journaled bundle with its manifest "
            "last. Independent SQL reconciliation finds zero normalized selection/payload "
            "differences against the real 10,000-row baseline. The 100,000-row plan uses the "
            "same bounded path, validates every row and source contract, and has zero blocked "
            "hosts. This proves exact bounded preparation, not completed transport or a "
            "representative 100k run. "
            "Representative 100k transport and the one-million cohort remain open. Monetary cost "
            "remains null and unknown because no real "
            "provider rate, invoice, energy meter, or labor ledger is bound to the runs. "
            "Per-page elapsed time remains in operational state and aggregate reports, "
            "not semantic OCR manifests; two independent real OCR states therefore emit "
            "the same semantic manifest hash. A disk-backed "
            "file/edge audit reconciles all 122,607 eligible inventory rows after the "
            "exclusions and physically removing "
            "three explicitly synthetic program pages plus eight Europarliament captures "
            "that copied an invented fallback sample. A known-non-real sample fingerprint "
            "gate prevents recurrence without rejecting repeated official payloads. The audit "
            "verifies checksum and public URL lineage for 122,539 files with zero conflicts, "
            "and decompressed checksums for all 6,792 "
            "referenced text artifacts with zero conflicts. It recovers 10,326 exact "
            "embedded URLs across official or primary captures, 50 exact PDF relations "
            "from preserved official hrefs plus byte-identical live GETs, 4,516 archived-metadata relations over 3,757 files, "
            "14 official publication-identifier PDF relations, 56 official-path Senate XML relations, one BOE sidecar, and 530 exact "
            "URL-path-checksum relations from the real vote-lineage manifest under "
            "distinct evidence classes. Checksum-verified published JEC and Andalusian "
            "Parliament capture indexes contribute another 124 exact provenance edges, including "
            "32 vote-document links extracted from official initiative captures; two close prior gaps. "
            "They also include six Andalucía "
            "program captures whose three press-hosted copies remain distinct from official-party "
            "origins; exact party-program manifests add 24. URL construction alone never counts: every new identifier/path relation "
            "requires a bounded official GET with exact stored SHA-256 and byte count. The workers "
            "use bounded concurrent streaming, reject every checksum or size non-match, and merge prior immutable "
            "relations instead of replacing them. A disk-backed Wayback worker derives only "
            "the exact Europarliament connector URL and Senate path URL. The current no-network "
            "rebind covers all 68 gaps, groups 26 evidence-derived instances into three real "
            "SHA-256/size targets, leaves 42 unseeded, and checkpoints queries plus replays. Its first "
            "bounded run rehashed five distinct older Europarliament captures, rejected all five "
            "byte mismatches, retained seven failed endpoint variants for explicit retry, and "
            "published zero false lineage relations. An atomic 43-row portable checkpoint preserves "
            "schema, three targets, 26 capture paths, eight queries, and five replay hashes; a "
            "cap-sized archive index result fails closed instead of truncating silently. "
            "Successful index queries and rejected digests "
            "do not repeat without an explicit refresh/retry lever. It leaves 68 files explicitly unlinked "
            "instead of promoting them. A deterministic streaming remediation queue "
            "contains 68 current work items, all missing checksum and "
            "public-URL lineage, with guessed URLs forbidden. The 25 Europarliament rows "
            "require immutable historical archive metadata or an exact source manifest; the "
            "remaining unseeded rows require exact primary-source sidecars/manifests or "
            "checksum-identical archived responses. "
            "Without a new lever, network probes must not repeat. A public-safe storage-health "
            "artifact reconciles the real BDNS and PLACSP preflights without exposing roots "
            "or session state: both remain blocked, requiring another 5,177,384,960 and "
            "66,776,911,872 bytes respectively. Each real lane still needs "
            "its own representative-scope, recovery, correction, and promotion proof."
        ),
        evidence=[
            Evidence(
                source="ROADMAP.md",
                detail="Scale contract separates capacity classes and real-lane gates.",
            ),
            Evidence(
                source="etl/data/published/scale-readiness-latest.json",
                detail="Real-only audit of current materialized official-source corpora and open promotion gates.",
            ),
            Evidence(
                source="etl/data/published/storage-health-latest.json",
                detail="Public-safe real-preflight storage status and exact lane headroom.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-rollback-candidate-full-validation-20260812.json",
                detail="Prior immutable release full restore and six-corpus rollback-candidate validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-rollback-plan-20260812.json",
                detail="GET-only live pointer, target, compare-and-swap, and supersession plan with zero mutation.",
            ),
            Evidence(
                source="docs/etl/real-corpus-registry.json",
                detail="Official source IDs, hosts, roots, manifests, validations, thresholds, and open limitations.",
            ),
            Evidence(
                source="etl/data/published/member-vote-million-audit-latest.json",
                detail="Real member-vote observation and failed promotion gates.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/senado-local-cache-repair-audit.json",
                detail="Offline legislature-isolated Senate repair and before/after vote database audit.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/senado-repaired-db-shard-validation.json",
                detail="Independent SQLite-direct shard checksum, payload, total, lineage, URL, and privacy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/member-vote-semantic-partition-manifest.json",
                detail="Typed real member-vote partition manifest and bounded export performance.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/member-vote-semantic-partition-validation.json",
                detail="Independent full-row schema, checksum, partition, lineage, URL, and privacy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/member-vote-semantic-partition-incremental-manifest.json",
                detail="Unchanged next-snapshot reuse of every real member-vote partition.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/accountability-ledger-semantic-partition-manifest.json",
                detail="Typed real S1 accountability-ledger partition and coverage proof.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/accountability-ledger-semantic-partition-validation.json",
                detail="Independent full-row ledger schema, hash, URL, lineage, and privacy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/accountability-ledger-semantic-partition-incremental-manifest.json",
                detail="Unchanged next-snapshot reuse of every real ledger partition.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-acquisition.json",
                detail="Official Eurostat verified-TLS acquisition, queue, raw-byte, series, observation, SQLite, lineage, and normalization reconciliation proof.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-semantic-validation.json",
                detail="Independent full-row validation of 1,755,809 real indicator observations across 26 partitions and 37 Parquet files.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/eurostat-indicator-real-s2-incremental-manifest.json",
                detail="Unchanged real Eurostat replay reuses all 26 partitions through 37 checksum-verified hardlinks.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/actor-mandate-semantic-partition-manifest.json",
                detail="Typed real actor-mandate schema, partition, identity-state, lineage, and bounded export proof.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/actor-mandate-semantic-partition-validation.json",
                detail="Independent full-row actor schema, list, hash, URL, identity-state, lineage, and privacy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/actor-mandate-semantic-partition-incremental-manifest.json",
                detail="Unchanged next-snapshot reuse of all 93 real actor-mandate partitions.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/public-money-semantic-partition-manifest.json",
                detail="Exact-decimal S0 contract and subsidy partition proof with explicit non-payment semantics.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/public-money-semantic-partition-validation.json",
                detail="Independent full-row decimal, source, semantic, hash, partition, and privacy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/public-money-semantic-partition-incremental-manifest.json",
                detail="Unchanged reuse of all four canonical public-money partitions.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-partitioned-real-s3-run-20260812.json",
                detail="Fresh official BDNS million-row acquisition with bounded daily partitions, exact queue/page/row/version reconciliation, pacing, and public-identity retention evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-partitioned-real-s3-enqueue-20260812.json",
                detail="Official daily-window discovery and the initial complete-versus-truncated partition contract for the million-row cohort.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-partitioned-real-s3-expand-20260812.json",
                detail="Append-only official expansion that completed all 89 selected daily windows while preserving existing global page identities.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-partitioned-real-s3-storage-preflight-20260812.json",
                detail="Latest real storage preflight for raw-object and SQLite/WAL capacity before another BDNS work claim.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-partitioned-real-s3-storage-preflight-blocked-20260812.json",
                detail="Earlier real fail-closed storage preflight that blocked before claim while capacity was below the configured floor.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-public-money-real-s3-v7-validation-20260812.json",
                detail="Independent full-row validation of 1360382 official subsidy facts with exact identity retention, decimals, lineage, hashes, publication hygiene, and bounded disk-backed distinct indexing.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-public-money-real-s3-v7-incremental-manifest-20260812.json",
                detail="Unchanged hardlink reuse of the current million-row BDNS semantic partition across all 14 files.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-bundle-dry-run-20260812.json",
                detail="Fail-closed local HF scale bundle over every registered real corpus, with exact file and byte reconciliation and public-domain identities retained.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-parity-20260812.json",
                detail="Historical fail-closed evidence from before the analytical scale origin was published; retained to show the transition from blocked to verified.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-restore-probe-20260812.json",
                detail="Historical pre-publication restore probe that failed closed before cache creation; retained as negative-path evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/docker-context-storage-blocker-20260812.json",
                detail="Docker context regression remediation and honest containerd storage blocker, with the equivalent host tracker gate green.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-provenance-audit.json",
                detail="Disk-backed file-level reconciliation of the real document inventory against SQLite source URLs, checksums, and derived text artifacts, with unlinked files explicit.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-extraction.json",
                detail="Resumable complete native extraction of every current real document instance and distinct content object with zero truncation and public identity retained.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-validation.json",
                detail="Independent checksum and character-count validation of every raw document instance and native text CAS object.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr.json",
                detail="Complete additive OCR run for every routed empty or sparse real PDF page with durable work state and exact engine configuration.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-validation.json",
                detail="Independent source-PDF, routing, manifest, and OCR CAS validation for all 856 real candidate pages.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/document-factory-economics-validation-20260829.json",
                detail="Independent hashes and per-1,000 math for fresh physical acquisition, cold native/OCR telemetry, storage, failures, and explicit unmeasured monetary cost.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-cohort-20260829.json",
                detail="Deterministic real-only 100-object BOE cohort selected across endpoint and captured-size deciles, with every prior raw checksum revalidated and known blocked rows excluded.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-run-physical-20260829.json",
                detail="Fresh physical acquisition report with exact request, byte, wall, CPU, RSS, host pacing, retry, failure, and content-object telemetry.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-validation-physical-20260829.json",
                detail="Independent 100-file checksum, immutable-byte, host-SLO, request, database-integrity, and per-1,000 reconciliation proof.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-host-health-20260829.json",
                detail="Bounded current-health probes select eligible official hosts, reject strict-TLS and unmodeled dynamic sources, and avoid reprobing known blockers.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-run-physical-20260829.json",
                detail="Preserved first 1,000-object attempt that exposed one transient timeout and one valid BOE content revision, disproving a global immutable-URL assumption.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-cohort-v2-20260829.json",
                detail="Deterministic 1,000-object real multi-host cohort with exact prior checksums, known-blocked exclusion, source-specific contracts, and public identity retention.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-v2-run-physical-20260829.json",
                detail="Fresh cold two-host acquisition of all 1,000 objects with exact request, byte, wall, CPU, RSS, pacing, queue, and failure telemetry.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-v2-validation-physical-20260829.json",
                detail="Independent rehash of 1,000 prior and 1,000 fresh files, 1,000 source-contract checks, and explicit reconciliation of 948 exact objects plus 52 valid official revisions.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-cohort-10k-v1-20260829.json",
                detail="Bounded root manifest for 10,000 real official objects backed by 30 deterministic gzip JSONL partitions and a streaming semantic identity.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-cohort-10k-v1-preflight-validation-20260829.json",
                detail="Pre-network disk-backed validation of every prior checksum, source contract, policy row, partition and pristine queue item.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-cohort-10k-v1-run-physical-20260829.json",
                detail="Fresh cold two-host acquisition of all 10,000 objects with exact request, byte, wall, CPU, RSS, pacing, queue and failure telemetry.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-cohort-10k-v1-validation-physical-20260829.json",
                detail="Independent disk-backed rehash of 10,000 prior and 10,000 fresh files, 10,000 source contracts, and 9,943 exact plus 57 valid revised objects.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-source-universe-20260829.json",
                detail="Zero-network disk-backed census of 304,165 real provenance edges, 104,064 unique official public URLs, 100,418 HTTPS URLs, and the exact contract-plus-health eligibility gap before a numeric 100,000 acquisition.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-source-universe-validation-20260829.json",
                detail="Independent edge replay and hash-bound validation of source, host, eligibility, real-data policy, and target arithmetic without inferring representativeness.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-disk-planner-10k-v1-20260829.json",
                detail="Disk-backed v4 10,000-row cohort with bounded sharded rows, selection/execution identities, exact paired provenance, immutable-input checks and manifest-last publication contract.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-disk-planner-equivalence-validation-20260829.json",
                detail="Independent disk-SQL proof of zero bidirectional normalized selection/payload differences and exact logical-partition parity against the prior real 10,000-row cohort.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-disk-planner-max-validation-20260829.json",
                detail="Independent reconciliation of all 90,121 currently eligible official rows, their exact queue contract, public-information retention, paired provenance and bounded planner RSS.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-validation-physical-20260829.json",
                detail="Cold-run OCR validation bound to the deterministic semantic manifest and every real source/CAS checksum.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-human-review-queue.json",
                detail="Deterministic 40-page real OCR review packet with every no-text and material-gain result selected and no invented human decisions.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-human-review-validation.json",
                detail="Integrity validation separates immutable review assignments from mutable human fields and keeps the 0/40 completion gate explicit.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/document-provenance-gap-queue-20260812.json",
                detail="Deterministic remediation queue for every checksum-lineage or public-URL gap, with exact input hashes and no guessed URLs.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/wayback-document-lineage.json",
                detail="Disk-backed exact-URL archive recovery over 26 real gaps and three content targets; five historical byte mismatches are rejected and zero false relations are published.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/wayback-document-checkpoint.jsonl",
                detail="Portable resumable archive checkpoint containing verified targets, capture paths, CDX query state, and replay hashes with public identity retained.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/archived-document-source-lineage.json",
                detail="Read-only recovery of exact path, byte, checksum, and public-URL lineage from preserved root and nested legacy databases.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/captured-link-document-lineage.json",
                detail="Bounded official GET report for exact links found in preserved official HTML; only byte-identical real gaps enter the cumulative lineage manifest.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/official-document-identifier-lineage.json",
                detail="Fourteen preserved Senate diary PDFs matched exact official publication URLs by byte count and SHA-256; no URL candidate alone was accepted.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/official-path-document-lineage.json",
                detail="Fifty-six aggregate Senate session XML captures matched their exact official paths byte-for-byte; the one changed response remains excluded.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/member-vote-source-url-lineage-20260812.json",
                detail="Full member-vote source URL transport classification, checksum-capture coverage, and bounded HTTPS 403 evidence without silent URL rewriting.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-verify-20260812.json",
                detail="Historical publication-time proof of remote manifest, corpus, registry, readiness, and required-policy parity for the six-corpus analytical release.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-current-metadata-parity-20260812.json",
                detail="Current verifier proof that immutable artifact-contract, registry, and readiness parity pass without warnings.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-clean-restore-remaining-20260812.json",
                detail="Fresh-cache recovery of the five non-BDNS corpora: 8601 downloaded files and 461088883 checksum-verified bytes with a 10 GiB reserve.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-restore-bdns-validation-20260812.json",
                detail="Independent full-row validation of the million-row BDNS lane restored from the public origin into an empty cache.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-clean-room-drill-20260812.json",
                detail="Disposable isolated-environment proof that all 20 BDNS files restore from the public origin and full-validate without canonical corpus input.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-clean-room-all-corpora-20260812.json",
                detail="Aggregate clean-room proof that all six registered corpora restore from fresh caches and full-validate 5403506 real rows across 8595 data files.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-explicit-release-restore-actor-20260812.json",
                detail="Fresh-cache recovery of the actor corpus from an explicit full-SHA immutable release path without consulting the mutable latest pointer.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-explicit-release-actor-validation-20260812.json",
                detail="Full semantic validation of 88031 real actor-mandate rows after explicit immutable-release recovery.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-sqlite-rebuild-actor-20260812.json",
                detail="Atomic bounded SQLite rebuild of the restored actor corpus with exact logical-row, integrity, identity, and memory gates.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-sqlite-rebuild-actor-replay-20260812.json",
                detail="Independent replay proving the rebuilt 88031-row actor SQLite artifact is byte deterministic.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/content-object-parallel-replication-20260812.json",
                detail="Bounded 16-worker local CAS replay of 6792 real linked-text objects with full checksum deduplication and deterministic manifest hash.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/content-object-full-local-restore-20260812.json",
                detail="Streaming full-manifest local restore proof for all 6792 replicated real objects and 133219457 bytes.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/raw-object-remote-origin-config-audit-20260812.json",
                detail="Secret-free configuration audit proving the external S3-compatible origin cannot be exercised until bucket and credential configuration exist.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-s2-partial-run.json",
                detail="Durable million-cohort checkpoint, bounded raw acquisition, timeout circuit, and zero-dead-page evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-public-money-semantic-s2-partial-validation.json",
                detail="Independent full-row schema, decimal, source, semantic, hash, partition, and privacy validation over the 146k checkpoint.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-public-money-semantic-s2-partial-incremental-manifest.json",
                detail="Unchanged reuse of the partial-S2 semantic partition and both Parquet files.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/reports/million-scale-foundation-and-real-document-run.md",
                detail="Real document fetch, extraction, replication, restore, and residual blocker evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-format-inventory.json",
                detail="Bounded real-corpus format, size, pages, text-density, and duplicate inventory.",
            ),
        ],
        references={"real-only readiness": "workflow.Promote one real scale lane"},
        updated_at=UPDATED,
    ),
    Fact(
        name="Outcome C2B delivery separates planning identity and portable rows",
        description=(
            "`outcome C2B layers` are three distinct non-claim artifacts: a "
            "source planner database containing the strict real L0 eligibility "
            "universe, an exact official-public identity companion retaining "
            "Senate member-vote names and action identifiers, and a bounded "
            "content-addressed Parquet package. Materializing, packaging, or "
            "recovering these rows never turns temporal/topic eligibility into a "
            "relationship, association, effect, ranking, merit, blame, corruption "
            "finding, semantic promotion, or public release."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-pair-identity-resolver-audit-v1.json",
                detail="Independent exact-name resolver audit over official Senate evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-pair-discovery-c2b-v1-manifest.json",
                detail="Content-addressed portable package contract and complete physical inventory.",
            ),
            Evidence(
                source="docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-pair-discovery-c2b-v1-validation.json",
                detail="Independent source parity, identity retention, safety, and bounded-resource validation.",
            ),
        ],
        references={
            "outcome C2B layers": "decision.Separate review capacity from reviewer operations"
        },
        updated_at=UPDATED,
    ),
    Fact(
        name="SQLite physical identity requires a pinned runtime",
        description=(
            "`pinned SQLite artifact runtime` is required when a release contract "
            "pins the byte-level SHA-256 of a generated SQLite database. The same "
            "C2C inputs and semantic root produced different physical database "
            "hashes under Python 3.14 and Python 3.12, so canonical materialization, "
            "validation, replay, and tests now use one declared Python 3.12 runtime."
        ),
        evidence=[
            Evidence(
                source="justfile",
                detail="C2C materialization, validation, and tests share the pinned Python and isolated cache variables.",
            ),
            Evidence(
                source="scripts/validate_outcome_review_control_c2c.py",
                detail="Validator independently pins semantic, physical database, and manifest identities.",
            ),
            Evidence(
                source="tests/test_outcome_review_control_c2c_real_pipeline.py",
                detail="Crash/resume reconstruction must be byte-identical with the canonical real capacity database.",
            ),
        ],
        references={
            "pinned SQLite artifact runtime": "workflow.Rebuild outcome review capacity"
        },
        updated_at=UPDATED,
    ),
    Fact(
        name="Abandoned ingestion runs close as explicit errors",
        description=(
            "`stale run reconciliation` is a separate, opt-in repair after a "
            "read-only audit. It mutates a database only when its sole reported "
            'issue is stale ingestion runs, changes "running" to "error", keeps '
            "the observed real row counts, records repair time and reason, and "
            "requires a clean post-audit. It never promotes an interrupted run "
            "to success."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/data-integrity-stale-run-reconciliation-20260829.json",
                detail="Two real abandoned BDNS runs reconciled with original counts preserved and all 101 staging databases passing afterward.",
            ),
            Evidence(
                source="scripts/audit_data_integrity.py",
                detail="Read-only pre-audit, issue-only mutation eligibility, transactional update, and enforced post-audit.",
            ),
        ],
        references={
            "stale run reconciliation": "workflow.Rebuild outcome review capacity"
        },
        updated_at=UPDATED,
    ),
]


PROJECT_DOMAIN_CONCEPTS = [
    DomainConcept(
        name="Static evidence platform",
        description=(
            "`static evidence platform` composes bounded JSON snapshots, "
            "Hugging Face dataset publication, Cloudflare/GH Pages static UI, "
            "and local SQLite/Explorer drill-down into one reproducible public "
            "accountability surface."
        ),
        aliases=["static-first platform", "evidence-backed public surface"],
        evidence=[
            Evidence(source="README.md", detail="Current MVP and public surfaces."),
            Evidence(
                source="ROADMAP.md",
                detail="Primary public surfaces and platform thesis.",
            ),
            Evidence(
                source="docs/roadmap-tecnico.md",
                detail="Publication and public snapshot architecture.",
            ),
        ],
        references={
            "static evidence platform": "fact.Project is static and SQLite first"
        },
        updated_at=UPDATED,
    ),
    DomainConcept(
        name="Accountability ledger spine",
        description=(
            "`accountability ledger spine` is the generic issue actor role source "
            "layer for votes, BOE, appointments, legal responsibilities, money, "
            "enforcement, dossiers, and Evidence API answers."
        ),
        aliases=["generic accountability ledger", "issue actor ledger"],
        evidence=[
            Evidence(
                source="ROADMAP.md",
                detail="Where-we-are-now section describes generic accountability ledger.",
            ),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Rows document D1/D2/D3 ledger backfills and publication.",
            ),
            Evidence(
                source="scripts/export_accountability_ledger_snapshot.py",
                detail="Public ledger snapshot exporter.",
            ),
        ],
        references={
            "accountability ledger spine": (
                "workflow.Accountability ledger refresh and publish"
            )
        },
        updated_at=UPDATED,
    ),
    DomainConcept(
        name="Evidence hierarchy",
        description=(
            "`evidence hierarchy` ranks primary official records above official "
            "structured data, official communications, reliable reusers, and "
            "media/social leads. Accountability outputs must preserve tier and "
            "uncertainty instead of flattening sources."
        ),
        aliases=["source hierarchy", "evidence tiers"],
        evidence=[
            Evidence(source="ROADMAP.md", detail="Source hierarchy Tier 1 through 5."),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Evidence-tier centralization and ledger rows.",
            ),
            Evidence(
                source="scripts/accountability_evidence_tiers.py",
                detail="Central evidence-tier inference.",
            ),
        ],
        references={"evidence hierarchy": "gotcha.Do not flatten source confidence"},
        updated_at=UPDATED,
    ),
    DomainConcept(
        name="Citizen UI",
        description=(
            "`Citizen UI` is the default citizen-facing static surface for what "
            "happened on what a user cares about. Preference inputs stay local "
            "by default, share links are explicit opt-in, and shown stances must "
            "link to concrete evidence drill-down."
        ),
        aliases=["citizen surface", "static citizen product"],
        evidence=[
            Evidence(source="AGENTS.md", detail="Citizen-first product rules."),
            Evidence(source="ui/citizen/index.html", detail="Citizen UI entrypoint."),
            Evidence(
                source="scripts/export_citizen_snapshot.py",
                detail="Citizen snapshot export.",
            ),
        ],
        references={"Citizen UI": "fact.Source truth code paths"},
        updated_at=UPDATED,
    ),
    Fact(
        name="PLACSP bulk corpus is versioned and document heavy",
        description=(
            "`PLACSP bulk scale` uses independent durable queues for ZIP archives, "
            "Atom members, and document URLs. The measured January-June 2025 "
            "cohort completes 6 archives and 667 members, preserving 330,577 "
            "content versions, 121,555 stable contracts, 262,558 award-result "
            "versions, 1,014 tombstone sightings, and 3,190,620 document sightings. Public "
            "money v4 keeps only the latest stable-contract version and separates "
            "121,555 notice facts from 141,747 award facts; 263,302 rows pass full "
            "validation and 50-partition unchanged reuse. This passes the real S1 "
            "contract-count and money-fact row gates, not representative history. "
            "Document sightings deduplicate to 998,392 URLs; a "
            "bounded 20-document sample passes, while the rest stays pending until "
            "a host budget, remote origin, extraction, and 100k quality gate exist. "
            "The revision-aware detector materializes 2,036 internal review signals "
            "with 6,788 evidence links, withdraws superseded revisions, and never "
            "treats them as corruption findings. The live official catalog adds a "
            "gap-free 22-archive history contract for annual 2012-2025 plus monthly "
            "2026 through August; all inputs are durably queued but remain pending "
            "until upstream access and disk/origin budgets are safe. Archive and "
            "member workers enforce a reserve-aware storage floor before claim; "
            "the real history preflight stops with 41,134,141,440 bytes free against "
            "107,911,053,312 required, preserving zero attempts, leases, and network "
            "requests."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-run.json",
                detail="Archive/member queue, version, stable-contract, award, tombstone, and document reconciliation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-archive-catalog-20260811.json",
                detail="Verified, gap-accounted official history archive contract.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-enqueue-20260811.json",
                detail="Idempotent durable enqueue of all 22 selected history archives.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-storage-preflight-20260811.json",
                detail="Reserve-aware blocked-storage proof before queue claim or network.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-validation.json",
                detail="Independent full-row money semantics, decimal, privacy, source, hash, and partition validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-incremental-manifest.json",
                detail="Unchanged reuse of all 50 PLACSP semantic partitions.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-document-fetch-enqueue.json",
                detail="Full deduplicated document queue cardinality.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-document-fetch-sample.json",
                detail="Bounded real-network document fetch sample.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-integrity-signal-run.json",
                detail="Internal-only real review-signal and evidence-link totals.",
            ),
        ],
        references={"PLACSP bulk scale": "workflow.Run a PLACSP scale cohort"},
        updated_at=UPDATED,
    ),
]


PROJECT_WORKFLOWS = [
    Workflow(
        name="Operate the bounded document fetch queue",
        description=(
            "`bounded document fetch operations` claim official document URLs through "
            "durable leases, stream each response into content-addressed storage, pace "
            "every request and retry per host, and publish only reconciled bounded status."
        ),
        steps=[
            "Enqueue exact official URLs idempotently; never substitute generated or sample records for missing source data.",
            "Separate planning gates from acquisition gates: an exact 100,000-row numeric cohort proves selectable official supply, not downloaded bytes or end-to-end promotion.",
            "For a fresh healthy-source scale cohort, select only previously captured official objects, rehash every prior capture, stratify deterministically by host/type/size, bind a source-specific validation contract, and exclude known blocked rows before creating a clean queue database.",
            "For cohorts above embedded compatibility, use partitioned v4: file-backed SQLite selection, deterministic bounded sub-shards, exact selection/execution identities, per-target kernel locks, before/after input hashes, and journaled manifest-last publication; preflight the complete queue before any request.",
            "Set a global claim ceiling plus per-host concurrency, minimum request-start interval, byte/time ceiling, storage reserve, retry delay, circuit threshold, and durable request budget before network work; the current BOE recovery ceiling is 500,000 requests.",
            "Run requests through the per-host slot for every retry; record exact request, outcome, byte, HTTP status, failure class, peak in-flight, throttle wait, and circuit metrics.",
            "Count transport exceptions and timeouts as route failures for the host circuit, not only HTTP status failures.",
            "Persist success only after atomic checksum-addressed publication; delete partial files on every failure and retain retryable or dead queue state explicitly.",
            "Write the first progress checkpoint atomically before long work, then refresh it on a bounded clock; never require a full queue scan after every batch.",
            "Recover expired leases through normal queue claiming. Requeue budget failures or transient failures only through exact, bounded maintenance commands that preserve attempt and request-budget telemetry.",
            "Treat prior checksums as revision baselines, not universal immutability promises: preserve the fresh object when its official URL and source-specific structure validate, then report the exact prior-to-fresh hash delta.",
            "Do not repeat a blocked-host probe without a new lever; publish current queue truth from the read-only database instead.",
            "Run the independent operations validator and require queue/document/host parity, zero overdue leases, zero orphan partials, official-host allowlist, no unsupported million-scale claim, no secrets, and exact public identity retention.",
            "The 100- and 1,000-object gates pass; increase through 10,000 and 100,000 only after the prior cohort's host SLO, revision, and recovery gates pass.",
        ],
        validation=[
            "just document-factory-acquisition-cohort-validate",
            "just document-factory-disk-planner-test",
            "just document-factory-disk-planner-10k-verify",
            "just document-factory-disk-planner-100k-verify",
            "just document-factory-disk-planner-max-verify",
            "just document-factory-source-universe-report",
            "just etl-scale-boe-document-status",
            "just document-fetch-operations-export",
            "just document-factory-economics-export",
            "just transparency-dashboard-export",
            "just privacy-check-public-artifacts",
        ],
        evidence=[
            Evidence(
                source="scripts/run_document_fetch_queue.py",
                detail="Durable streaming worker, exact per-request host pacing, circuits, and per-host SLO report.",
            ),
            Evidence(
                source="scripts/validate_document_fetch_operations.py",
                detail="Independent real-DB reconciliation and public claim gate.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/document-fetch-operations-validation-20260829.json",
                detail="Current real Senate queue validation with zero orphan partials and no unsupported promotion.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-scale-v2-validation-physical-20260829.json",
                detail="Fresh multi-host cohort proves 1,000 successes from 1,000 exact requests, complete prior/fresh rehashing, source-contract parity, revision preservation, host pacing, and zero failures without probing known blockers.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-fetch-disk-planner-100k-validation-20260830.json",
                detail="Exact 100,000-row planning gate with pinned selection identity and no numeric supply gap.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-source-universe-validation-20260829.json",
                detail="Validated real official source universe and physically healthy planning eligibility.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-access-timeout-20260830.md",
                detail="Current bounded BOE acquisition blocker and no-repeat-probe boundary.",
            ),
        ],
        references={
            "bounded document fetch operations": "fact.Readiness counts only verified official corpora"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Ingest official BOE election candidates",
        description=(
            "`BOE candidate ingestion` parses exact immutable proclamation XML, "
            "retains every public identity and source paragraph, then applies official "
            "corrections through an immutable operation ledger and a separate effective "
            "state. It is an alternate official source, not evidence "
            "that the Interior archive is unblocked. Its semantic contract permits only "
            "source-provided fields: BOE election outcomes remain null until separate official "
            "result evidence is linked."
        ),
        steps=[
            "Complete and enforce the BOE document corpus status so every requested document has exact summary-item, URL, checksum, and byte lineage.",
            "Run just etl-scale-boe-election-candidates for the bounded allowlisted proclamation and correction cohort.",
            "Require exact document-profile, candidacy, titular, substitute, non-proclaimed, and correction-paragraph totals before database mutation is accepted.",
            "Preserve full_name and source_text_exact; never parse a matching name into cross-source identity or infer is_elected.",
            "Require every correction operation to retain its exact paragraph evidence, before state, after state, target document, and deterministic operation ID; never mutate proclamation tables.",
            "Require every effective row to carry person, party, source-record, and document-source lineage; changed or new names remain source-scoped instead of being merged across sources.",
            "Run just etl-scale-boe-election-candidate-correction-review-queue to export every pending paragraph as a stable dual-review task and all pending public candidates once in the deduplicated context JSONL; preserve completed decisions only when task fingerprints remain identical.",
            "Export the unified v3 candidate semantic contract, independently validate every row/file/partition and exact public identity/evidence field, then prove an unchanged two-partition hardlink replay.",
            "Require 42,056 immutable captured base occurrences, isolate all 31,241 rows from pending historical cohorts, materialize only the reviewed 10,815-row base through 17 applied operations into 10,820 effective occurrences and 88 correction-backed source records, infer no BOE outcome, and require quick_check=ok, zero FK violations, and current central readiness reconciliation.",
        ],
        validation=[
            "python3 -m unittest tests.test_boe_election_candidates",
            "just etl-scale-boe-document-status",
            "just etl-scale-boe-election-candidates",
            "just etl-scale-boe-election-candidate-correction-review-queue",
            "just etl-scale-export-semantic-candidate-occurrences",
            "just etl-scale-validate-semantic-candidate-occurrences",
            "just etl-scale-replay-semantic-candidate-occurrences",
            "just etl-audit-public-source-records",
            "just etl-scale-readiness",
        ],
        evidence=[
            Evidence(
                source="scripts/ingest_boe_election_candidates.py",
                detail="Set-based idempotent source-scoped ingest and exact correction evidence.",
            ),
            Evidence(
                source="publicdata_connectors_es/elections/boe_candidates.py",
                detail="Strict official BOE proclamation parser and cohort contracts.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-election-candidates-latest.json",
                detail="Current real cohort counts, exact-source checks, and identity-retention policy.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-election-candidate-correction-materialization.json",
                detail="Applied operation ledger, effective rows, evidence linkage, and immutable-base proof.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-candidate-correction-review-queue.json",
                detail="Pending correction task, deduplicated public candidate context, decision-preservation, and no-mutation contract.",
            ),
            Evidence(
                source="publicdata_publish/candidate_occurrence_partitions.py",
                detail="Unified source-specific BOE and Infoelectoral semantic export without invented values.",
            ),
            Evidence(
                source="publicdata_publish/candidate_occurrence_partition_validation.py",
                detail="Independent ID, exact identity/text, correction-lineage, outcome-null, file, and replay validation.",
            ),
        ],
        references={
            "BOE candidate ingestion": "fact.BOE document and candidate cohorts preserve exact public evidence"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Run a PLACSP scale cohort",
        description=(
            "`PLACSP scale cohort` expands official monthly archives through "
            "bounded, resumable stages while preserving version lineage and "
            "keeping document fetch pressure separate from record ingestion."
        ),
        steps=[
            "Discover and hash the bounded official catalog; require gap-free annual/monthly periods.",
            "Lock the selected archive contract by SHA-256 and enqueue it idempotently.",
            "Run reserve-aware storage preflight before every archive/member claim; keep queue attempts at zero when floor plus next-item reserve does not fit.",
            "Preflight upstream access and remote-origin budget before starting history network work.",
            "Fetch archives by streaming to CAS with verified TLS, byte limits, and lease heartbeat.",
            "Inspect ZIP members without filesystem extraction and enqueue each Atom member independently.",
            "Parse members in bounded batches, preserving stable contract, version, award, tombstone, and document sightings.",
            "Require archive/member/stable-version reconciliation, quick_check, and zero FK violations.",
            "Export latest-version notice and award facts; run full validation and unchanged replay.",
            "Deduplicate document URLs into the separate queue and increase cohorts only under an explicit per-host request budget.",
            "Run revision-fingerprinted integrity detection as internal review work only; supersede stale revisions and require human policy gates before publication.",
            "Update the tracker with stable-contract count, not combined notice and award fact count.",
        ],
        validation=[
            "just etl-scale-placsp-report",
            "just etl-scale-placsp-history-archives-work",
            "just etl-scale-placsp-history-members-work",
            "just etl-scale-placsp-validate",
            "just etl-scale-placsp-replay-validate",
            "just etl-scale-readiness",
            "just privacy-check-public-artifacts",
        ],
        evidence=[
            Evidence(
                source="publicdata_connectors_es/money/placsp_bulk.py",
                detail="Bounded ZIP and Atom parser contract.",
            ),
            Evidence(
                source="scripts/ingest_placsp_archives.py",
                detail="Durable archive/member orchestration and reconciliation.",
            ),
            Evidence(
                source="scripts/enqueue_pipeline_work.py",
                detail="Deduplicated PLACSP document queue producer.",
            ),
            Evidence(
                source="scripts/run_document_fetch_queue.py",
                detail="Shared bounded document worker with PLACSP linkage.",
            ),
        ],
        references={
            "PLACSP scale cohort": "fact.PLACSP bulk corpus is versioned and document heavy"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Publish a canonical Eurostat indicator family",
        description=(
            "`canonical indicator publication` starts from one checksum-pinned "
            "official JSON-stat capture, materializes definitions, immutable releases, "
            "territorial series, append-only observation versions, and exact cell "
            "evidence, then publishes only a bounded static projection. The first real "
            "family is Eurostat nama_10r_3gdp for every ES-prefixed geography."
        ),
        steps=[
            "Pin and rehash the exact official raw payload before materialization.",
            "Read JSON-stat dimensions and cell coordinates directly; never seed or hand-select observation values.",
            "Store decimal values as exact text and preserve source status, geography, period, methodology, and uncertainty.",
            "Treat the first observed release as baseline, not as proof that the source has never revised the value.",
            "Validate every published observation independently against the raw cell coordinate, value, and status.",
            "Publish a bounded JSON projection and static evidence drill-down; keep the million-row corpus out of the browser.",
            "Run real-only, public-hygiene, desktop/mobile browser, exact live-byte, official-link, and global route gates.",
            "Keep promotion open until a second real snapshot proves new, unchanged, changed, and deleted version handling and a representative codebook is approved.",
        ],
        validation=[
            "just eurostat-gdp-indicator-check",
            "just privacy-check-public-artifacts",
            "just site-build",
            "just site-publish",
            "just eurostat-gdp-indicator-live-verify",
        ],
        evidence=[
            Evidence(
                source="docs/data-model/indicators-spec-v1.md",
                detail="Indicator, release, revision, geography, uncertainty, provenance, and scale contract.",
            ),
            Evidence(
                source="docs/etl/sprints/INDICATORS-20260820/evidence/eurostat-gdp-validation.json",
                detail="Independent exact raw-cell and database/public-artifact reconciliation.",
            ),
            Evidence(
                source="docs/etl/sprints/INDICATORS-20260820/evidence/live-eurostat-gdp-verification.json",
                detail="Exact live bytes, hashes, release identity, counts, real-only policy, and official links.",
            ),
        ],
        references={
            "canonical indicator publication": "gotcha.Baseline indicator release is not revision proof"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Contributor source onboarding",
        description=(
            "`source onboarding` starts with just add-source, which creates "
            "config, an exact official capture plus provenance sidecar, parser, "
            "strict sample test, and docs hook. Invented fixture data is forbidden. "
            "PRs for new sources should pass just etl-contributor-gates."
        ),
        steps=[
            "Run just add-source with an official HTTPS URL, captured file, SHA-256, capture time, and rights basis.",
            "Implement the parser against the copied official bytes; do not add mock, synthetic, placeholder, or invented records.",
            "Run: just etl-audit-official-samples.",
            "Run: just etl-contributor-gates before treating the source as merge-ready.",
            "Promote from source_records_only only after a stable normalization/backfill contract exists.",
        ],
        validation=[
            "just etl-contributor-gates",
            "just etl-tracker-gate for tracker consistency when source status changes",
        ],
        evidence=[
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Contributor source onboarding scaffold row dated 2026-05-11.",
            ),
            Evidence(
                source="justfile",
                detail="add-source and etl-contributor-gates recipes.",
            ),
            Evidence(
                source="docs/etl/source-onboarding.md",
                detail="Source onboarding docs hook.",
            ),
        ],
        references={"source onboarding": "fact.Reusable publicdata packages exist"},
        updated_at=UPDATED,
    ),
    Workflow(
        name="Accountability ledger refresh and publish",
        description=(
            "`ledger refresh` runs accountability backfills, exact-match actor "
            "resolution, bounded public exports, dossier export, and static "
            "Evidence API export before HF/static publication."
        ),
        steps=[
            "Run just etl-refresh-accountability-ledger with DB_PATH and SNAPSHOT_DATE set.",
            "Validate accountability artifacts before packaging.",
            "Run just etl-publish-hf-dry-run and verify non-zero artifacts before just etl-publish-hf.",
            "If a public UI surface changes, run just site-publish after merge-ready changes.",
        ],
        validation=[
            "just etl-validate-accountability-artifacts",
            "just privacy-check-public-artifacts",
            "just etl-publish-hf-dry-run",
        ],
        evidence=[
            Evidence(
                source="justfile", detail="Accountability and HF publish recipes."
            ),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Ledger, dossiers, Evidence API, and HF publish rows.",
            ),
            Evidence(
                source="AGENTS.md",
                detail="Public artifact gate and frontend publish rule.",
            ),
        ],
        references={"ledger refresh": "domain_concept.Accountability ledger spine"},
        updated_at=UPDATED,
    ),
    Workflow(
        name="Strict network blocker handling",
        description=(
            "`strict network blocker handling` means a blocked official source is "
            "not DONE. Record machine-verifiable failure evidence, update tracker "
            "status, and add a factual name-and-shame entry when obstruction is "
            "confirmed."
        ),
        steps=[
            "Run the source with strict-network where the connector supports it.",
            "Capture status/header/body signature or persistent timeout evidence.",
            "Update docs/etl/e2e-scrape-load-tracker.md with status and next action.",
            "Update docs/etl/name-and-shame-access-blockers.md for confirmed public-data obstruction.",
            "Move to controllable work if there is no new unblock lever.",
        ],
        validation=[
            "just etl-tracker-status",
            "just etl-tracker-gate",
        ],
        evidence=[
            Evidence(
                source="AGENTS.md",
                detail="Name and Shame protocol and anti-loop policy.",
            ),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Tracker rules for DONE and blocker handling.",
            ),
            Evidence(
                source="docs/etl/name-and-shame-access-blockers.md",
                detail="Public obstruction log.",
            ),
        ],
        references={
            "strict network blocker handling": "gotcha.Do not fake blocked sources done"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Publish the public obstruction tracker",
        description=(
            "`obstruction publication` derives one bounded static feed and an "
            "inert evidence bundle from the canonical append-only blocker log, "
            "current source status, and scale-readiness artifact. It retains "
            "official public-domain personal information and removes only secrets, "
            "private-session state, workstation traces, and non-public personal data."
        ),
        steps=[
            "Update the canonical Name and Shame log, source-status snapshot, and scale-readiness artifact; never hand-edit the derived feed.",
            "Run just obstruction-tracker-export to expand repository evidence references into deterministic inert .txt files with source and public bytes plus SHA-256.",
            "Require the exporter and independent validator to reconcile every incident, blocked source, scale corpus, gap, evidence file, and identity-retention policy.",
            "Run the full static build so real-data-only and publication-hygiene gates cover the feed and evidence bundle.",
            "Publish with just site-publish after merge-ready frontend changes.",
            "Run the live route audit and require every route, critical asset, and evidence object to return exact manifest bytes and SHA-256 before marking the roadmap item DONE.",
        ],
        validation=[
            "just obstruction-tracker-export",
            "python3 -m unittest tests.test_obstruction_tracker_snapshot",
            "node --test tests/test_obstruction_tracker_ui_contract.js",
            "just site-build",
            "node scripts/audit_public_routes.js --base-url https://votaconlachola.org",
        ],
        evidence=[
            Evidence(
                source="scripts/export_obstruction_tracker_snapshot.py",
                detail="Canonical feed and inert public evidence-bundle exporter.",
            ),
            Evidence(
                source="scripts/validate_obstruction_tracker_snapshot.py",
                detail="Independent feed, manifest, policy, size, and public-hygiene validator.",
            ),
            Evidence(
                source="docs/release-notes/obstruction-tracker-mvp.md",
                detail="Published contract, current real counts, caveats, and verification commands.",
            ),
            Evidence(
                source="docs/etl/sprints/OBSTRUCTION-TRACKER-20260819/evidence/live-route-audit.json",
                detail="Live route, critical-asset, and exact evidence-object verification.",
            ),
        ],
        references={
            "obstruction publication": "workflow.Strict network blocker handling"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Publish the operational transparency dashboard",
        description=(
            "`transparency publication` derives one bounded static feed from "
            "source health, obstruction, scale readiness, the verified durable "
            "origin, and a real release registry. Every displayed metric carries "
            "its repository path and public audit URL."
        ),
        steps=[
            "Update each owning artifact first; never hand-edit the derived transparency feed.",
            "Register only a real release whose Markdown note, public routes, and non-self-referential evidence paths exist; keep newest entries first in docs/release-notes/releases.json.",
            "Run just transparency-dashboard-export and require metric, source-state, snapshot, release, checksum, freshness, and identity-retention reconciliation.",
            "Run focused Python and Node contract tests, then the full static build with real-only and publication-hygiene gates.",
            "Inspect desktop and mobile rendering, publish with just site-publish, and require the live route audit to pass.",
            "If the operational tracker changed, regenerate the obstruction bundle before transparency because the tracker is itself public obstruction evidence.",
        ],
        validation=[
            "just transparency-dashboard-export",
            "python3 -m unittest tests.test_transparency_dashboard_snapshot",
            "node --test tests/test_transparency_dashboard_ui_contract.js",
            "just site-build",
            "node scripts/audit_public_routes.js --base-url https://votaconlachola.org",
        ],
        evidence=[
            Evidence(
                source="scripts/export_transparency_dashboard_snapshot.py",
                detail="Real-source feed builder with metric-level trace links and release checksums.",
            ),
            Evidence(
                source="scripts/validate_transparency_dashboard_snapshot.py",
                detail="Independent policy, reconciliation, freshness, snapshot, and release validator.",
            ),
            Evidence(
                source="docs/product/transparency-dashboard.md",
                detail="Public contract, source ownership, caveats, and Definition of Done.",
            ),
            Evidence(
                source="docs/release-notes/README.md",
                detail="Lightweight release-note and publication workflow.",
            ),
            Evidence(
                source="docs/etl/sprints/TRANSPARENCY-DASHBOARD-20260819/evidence/live-route-audit.json",
                detail="Live route, asset, and obstruction-evidence audit.",
            ),
        ],
        references={
            "transparency publication": "workflow.Publish the public obstruction tracker"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Evolve the core ontology additively",
        description=(
            "`core ontology v1` fixes the shared vocabulary, public/source-scoped "
            "identity rules, temporal semantics, provenance chain, uncertainty "
            "states, evidence-backed relationships, and scale boundaries without "
            "replacing the current physical schema in one migration."
        ),
        steps=[
            "Read docs/data-model/core-ontology-v1.md and its JSON companion before designing a new domain table or plugin contract.",
            "Keep source facts, document versions, evidence, claims, interpretations, aggregates, and publications as separate immutable or reproducible layers.",
            "Use stable public IDs plus local integer PKs; never resolve a person or organization across sources from a name alone.",
            "Add physical tables, views, and backfills in thin vertical slices; preserve existing tables and public IDs until real-data reconciliation proves the replacement.",
            "Require every derived relationship to link to evidence and method/version; preserve unknown, counterevidence, corrections, and superseded history.",
            "Run just core-ontology-check before accepting ontology, plugin-manifest, Evidence API, or domain-model changes.",
        ],
        validation=[
            "just core-ontology-check",
            "python3 scripts/validate_core_ontology_contract.py",
            "python3 -m unittest tests.test_core_ontology_contract",
            "git diff --check",
        ],
        evidence=[
            Evidence(
                source="docs/data-model/core-ontology-v1.md",
                detail="Normative concepts, relationships, time, identity, provenance, scale, migration, and publication rules.",
            ),
            Evidence(
                source="docs/data-model/core-ontology-v1.json",
                detail="Machine-readable 19-concept and 26-relationship contract.",
            ),
            Evidence(
                source="scripts/validate_core_ontology_contract.py",
                detail="Fail-closed contract, documentation, policy, scale, and current-schema mapping validator.",
            ),
            Evidence(
                source="tests/test_core_ontology_contract.py",
                detail="Regression tests for completeness, mappings, relationships, real-only policy, and official public identity retention.",
            ),
        ],
        references={
            "core ontology v1": "fact.Source truth code paths",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Build and validate a public-data plugin",
        description=(
            "`public-data plugin validation` loads code only after its manifest "
            "passes the v1 contract, replays checksum-pinned official bytes, "
            "preserves public identity and provenance, and proves idempotent output "
            "against the standard schema before a source family migrates."
        ),
        steps=[
            "Validate plugin.json against docs/architecture/plugin-manifest-v1.schema.json before importing its Python entry point.",
            "Register an exact official capture with HTTPS source URL, capture time, byte count, SHA-256, rights basis, and an explicit no-synthetic/no-mock policy.",
            "Implement bounded discover/acquire/parse/normalize lifecycle hooks; use official source IDs or a documented source-scoped stable tuple, never name alone.",
            "Preserve every public personal field emitted by the official source and link each normalized row back to its source record and artifact hash.",
            "Replay the same capture at least twice through the current standard schema and reconcile source records, entities, facts, ingestion runs, hashes, URLs, and foreign keys.",
            "Run global real-only, official-sample, ontology, plugin, and publication-hygiene gates before publishing artifacts.",
            "Migrate one source family at a time only after old/new parity passes; retain the compatibility adapter until reconciliation proves replacement safe.",
        ],
        validation=[
            "just reference-plugin-check",
            "just etl-audit-official-samples",
            "python3 scripts/validate_plugin_architecture.py",
            "python3 scripts/validate_reference_plugin.py",
            "git diff --check",
        ],
        evidence=[
            Evidence(
                source="docs/architecture/plugin-system-v1.md",
                detail="Normative plugin types, lifecycle, scale, security, versioning, failure, and test contracts.",
            ),
            Evidence(
                source="docs/architecture/plugin-manifest-v1.schema.json",
                detail="Machine-readable manifest and official-capture provenance contract.",
            ),
            Evidence(
                source="plugins/congreso_representatives/plugin.py",
                detail="Official Congreso reference plugin and standard-schema compatibility adapter.",
            ),
            Evidence(
                source="docs/etl/sprints/PLUGIN-SYSTEM-20260819/evidence/reference-plugin-validation.json",
                detail="Two-replay reconciliation for exact official public records with identity retained.",
            ),
        ],
        references={
            "public-data plugin validation": "workflow.Evolve the core ontology additively",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Publish and verify a signed scale snapshot",
        description=(
            "`signed scale publication` builds one exact real-data manifest, "
            "places it at a content-addressed immutable path, signs its canonical "
            "attestation with SSH Ed25519, moves latest only after upload, and "
            "verifies the public origin against a trust root outside the dataset."
        ),
        steps=[
            "Build registry and readiness from official real corpora; run the real-only and public-artifact hygiene gates.",
            "Hash every artifact in streaming mode, stamp manifest and artifact-contract schema versions, and derive the immutable path from the manifest SHA-256.",
            "Sign the canonical attestation with an ignored private key or managed CI secret; publish only the attestation, signature, and discovery public key.",
            "Upload the immutable tree before updating scale/latest.json so an interrupted publish leaves the previous release active.",
            "Download latest, manifest, attestation, signature, and discovery key; verify using the repository allowed_signers file, never the bundled key as trust root.",
            "Run local/remote corpus and metadata parity, produce an exact sorted manifest diff, and reconcile all evidence with the reproducibility validator.",
            "Keep W9-009 open until a different maintainer independently rebuilds and signs a second attestation.",
        ],
        validation=[
            "just etl-scale-origin-hf-verify-attestation",
            "just etl-scale-origin-hf-verify",
            "just snapshot-reproducibility-check",
            "just privacy-check-public-artifacts",
        ],
        evidence=[
            Evidence(
                source="docs/ops/reproducibility.md",
                detail="Normative signing, trust-root, publication, diff, rotation, and verification contract.",
            ),
            Evidence(
                source="docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-signed-snapshot-verification.json",
                detail="Trusted live signature verification for the current public release.",
            ),
            Evidence(
                source="docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-scale-origin-parity.json",
                detail="Current live/local corpus, metadata, path, contract, and policy parity.",
            ),
            Evidence(
                source="docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/snapshot-reproducibility-validation.json",
                detail="Fail-closed reconciliation across publish, manifest, live signature, live parity, and diff evidence.",
            ),
        ],
        references={
            "signed scale publication": "workflow.Promote one real scale lane",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Publish the stable Evidence API v1",
        description=(
            "`stable Evidence API publication` turns the current bounded real "
            "accountability exports into immutable, content-addressed pages for "
            "entities, evidence chains, source health, and question results. It "
            "keeps public identities exact and unknown states explicit."
        ),
        steps=[
            "Require the current scale origin and SSH Ed25519 attestation verification to pass before export.",
            "Run just evidence-api-v1-check to derive the API release from source, schema, exporter, page-size, and upstream-release hashes.",
            "Keep page size at or below 500; consumers pin api_release_id and follow opaque seek-cursor next links instead of offsets.",
            "Reconcile every collection to its real source export, verify every page and manifest hash, and compare all public entity labels byte for byte.",
            "Run publication hygiene and the full static build, publish gh-pages, then fetch and validate the current pointer, release index, and representative page from the live origin.",
            "For incompatible changes, create /api/v2/ and keep v1 public for at least 180 days and two parallel public releases.",
        ],
        validation=[
            "just evidence-api-v1-check",
            "just privacy-check-public-artifacts",
            "just site-build",
            "node scripts/audit_public_routes.js --base-url https://votaconlachola.org",
        ],
        evidence=[
            Evidence(
                source="docs/api/evidence-api-v1.md",
                detail="Stable pagination, provenance, compatibility, public-identity, and scale contract.",
            ),
            Evidence(
                source="docs/etl/sprints/EVIDENCE-API-20260819/evidence/evidence-api-v1-validation.json",
                detail="Current collection, page, hash, cursor, identity-retention, and real-source reconciliation.",
            ),
            Evidence(
                source="ui/site/public/api/v1/index.json",
                detail="Current public API pointer to the immutable release.",
            ),
        ],
        references={
            "stable Evidence API publication": "workflow.Publish and verify a signed scale snapshot",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Ingest and publish a real manifesto promise slice",
        description=(
            "`real manifesto promise ingestion` verifies exact official bytes, "
            "segments text by page, stores party claims without proxy people, and "
            "publishes only complete rule- or human-confirmed promises with exact evidence."
        ),
        steps=[
            "Pin the official HTTPS URL, byte count, page count, and SHA-256 before extraction; fail closed on any drift.",
            "Apply the additive canonical schema and preserve raw bytes outside SQLite while storing source records, document metadata, exact bounded quotes, pages, offsets, and hashes.",
            "Segment page-aware document structure, classify claims separately from promises, and leave incomplete or ambiguous fragments pending or needs_context.",
            "Attach the party directly, assign topics with an explicit codebook version, and never create a person proxy for an organization.",
            "Run the same input twice and require stable IDs, counts, release ID, artifact hash, clean foreign keys, and exact quote-to-page offset matches.",
            "Publish only confirmed real rows; state not_assessed for fulfillment until separate implementation evidence exists.",
            "Run public-artifact hygiene, static build, publish, then verify the live page, live JSON, and official PDF bytes independently.",
        ],
        validation=[
            "just manifesto-promises-check",
            "just privacy-check-public-artifacts",
            "just site-build",
            "just manifesto-promises-live-verify",
        ],
        evidence=[
            Evidence(
                source="docs/data-model/promises-spec-v1.md",
                detail="Claim/promise distinctions, ambiguity rules, stable identity, provenance, publication, and scale contract.",
            ),
            Evidence(
                source="docs/etl/sprints/PROMISES-20260819/evidence/promises-bng-2023-validation.json",
                detail="Current real source, database, quote/page/hash, identity-retention, and public sample validation.",
            ),
            Evidence(
                source="ui/site/public/promises/data/bng-2023.json",
                detail="Bounded public sample from the checksum-pinned official BNG 2023 manifesto.",
            ),
        ],
        references={
            "real manifesto promise ingestion": "workflow.Publish the stable Evidence API v1",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Materialize and publish a real public-money slice",
        description=(
            "`real public-money materialization` maps latest official source "
            "versions into canonical actor, spending-item, and evidence rows while "
            "keeping award, contract, invoice, payment, and delivery semantics distinct."
        ),
        steps=[
            "Fix the spending event, exact-decimal, temporal, identity, evidence, and version contract in docs/data-model/spending-spec-v1.md before mapping a source.",
            "Select latest non-tombstone source versions with a deterministic bounded query; do not multiply rows or use fixtures to demonstrate scale.",
            "Preserve source-published authority and counterparty names and identifiers exactly, including natural persons and already-masked source values; keep identity source-scoped until evidence supports resolution.",
            "Materialize one event per semantic phase and ordinal. An award uses procurement_award and award_amount; paid_on and delivered_on remain null without separate evidence.",
            "Attach a captured source-record hash and official URL to every item; mark linked documents official_url_only until exact bytes and SHA-256 are preserved.",
            "Reconcile counts and monetary totals with Decimal, verify the archive bytes/hash, foreign keys, integrity, and unchanged replay, then publish a bounded JSON view rather than the full corpus.",
            "Run real-only and public-artifact hygiene, build and publish the static route, then verify the live page, JSON hash/release, identity strata, and official evidence links.",
        ],
        validation=[
            "just placsp-spending-check",
            "sqlite3 -header -column etl/data/staging/spending-placsp-mvp.db < docs/examples/placsp-actor-spending-evidence.sql",
            "just privacy-check-public-artifacts",
            "just site-build",
            "just placsp-spending-live-verify",
        ],
        evidence=[
            Evidence(
                source="docs/data-model/spending-spec-v1.md",
                detail="Canonical event, amount, actor, provenance, edge-case, publication, and scale contract.",
            ),
            Evidence(
                source="docs/etl/sprints/SPENDING-20260819/evidence/placsp-spending-validation.json",
                detail="Exact source, archive, identity, amount, actor-item-evidence, FK, integrity, and real-only validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SPENDING-20260819/evidence/live-placsp-spending-verification.json",
                detail="Live page, JSON release/hash, identity strata, and official PLACSP link verification.",
            ),
            Evidence(
                source="ui/site/public/spending/data/placsp-sample.json",
                detail="Bounded public view with exact public identities and award-not-payment caveats.",
            ),
        ],
        references={
            "real public-money materialization": "decision.Preserve identities published by official sources",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Materialize and publish real agreements without inventing influence",
        description=(
            "`real agreement materialization` maps checksum-pinned official meeting "
            "or agreement disclosures into meetings, actor roles, agenda items, "
            "agreements, topics, and exact evidence while keeping every influence "
            "interpretation in a separate reviewed assertion layer."
        ),
        steps=[
            "Freeze meeting, agreement, actor-role, evidence, topic, and inference-level semantics in docs/data-model/agreements-influence-spec-v1.md before mapping a source.",
            "Select only real official source records with an explicit agreement or meeting fact; never create sample rows, attendees, counterparties, or positions to fill gaps.",
            "Preserve public personal and institutional names exactly. Mark attendance only when the source explicitly lists it; a convener or publisher is not automatically an attendee.",
            "Materialize adopted, signed, in-force, implemented, and fulfilled states separately. Leave unavailable states unknown.",
            "Store exact excerpt, source-record hash, capture hash, public URL, selector, method, and extractor version for every meeting and agreement.",
            "Assign topics as source_explicit, reviewed, derived_rule, or derived_model; publish derived unreviewed assignments with that label.",
            "Keep influence_assertions empty for a fact-only slice. Higher inference levels require supporting and contrary evidence plus the W8 review/publication gates.",
            "Require stable replay, zero foreign-key violations, integrity ok, no private workstation traces, bounded JSON, static publication, and independent live origin probes.",
        ],
        validation=[
            "just moncloa-agreements-check",
            "sqlite3 -header -column etl/data/staging/agreements-moncloa-mvp.db < docs/examples/moncloa-actor-agreement-evidence.sql",
            "just privacy-check-public-artifacts",
            "just site-build",
            "just moncloa-agreements-live-verify",
        ],
        evidence=[
            Evidence(
                source="docs/data-model/agreements-influence-spec-v1.md",
                detail="Canonical meeting, agreement, actor, evidence, topic, inference, publication, and million-scale contract.",
            ),
            Evidence(
                source="docs/etl/sprints/AGREEMENTS-20260819/evidence/moncloa-agreements-validation.json",
                detail="Exact capture, excerpt, date, actors, topics, no-attendance, no-influence, FK, integrity, and real-only validation.",
            ),
            Evidence(
                source="ui/site/public/agreements/data/moncloa-sample.json",
                detail="Bounded public view of official Council of Ministers agreement summaries with explicit limits.",
            ),
        ],
        references={
            "real agreement materialization": "decision.Preserve identities published by official sources",
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Promote one real scale lane",
        description=(
            "`real lane promotion` advances one evidence lane from deterministic "
            "fixture to 100k representative real items and then one million real "
            "items. Promotion requires bounded memory, resumability, lineage, "
            "quality sampling, reconciliation, publication, restore, and cost proof."
        ),
        steps=[
            "Run fixture/CI contracts for idempotence, lineage, privacy, and failure states.",
            "Build a stratified 100k real corpus and publish format/source quality strata.",
            "Verify durable object checksums and restore before increasing fetch volume.",
            "Export typed Hive-partitioned facts with bounded files, explicit URL scope, and independently verified checksums/content hashes.",
            "Fingerprint partitions before materialization so unchanged snapshots reuse verified files and changed snapshots rebuild only affected partitions.",
            "Reconcile stage/source/published totals and require the lane-specific quality threshold before public promotion.",
            "Run one-million real items with throughput, RSS, bytes, retries, dead letters, quality, and cost evidence.",
            "Update the operational tracker; never promote adjacent lanes by inference.",
        ],
        validation=[
            "just etl-scale-smoke",
            "just etl-scale-readiness",
            "just etl-scale-eurostat-indicators-report",
            "just etl-scale-eurostat-indicators-validate",
            "just etl-scale-eurostat-indicators-replay-validate",
            "just privacy-check-public-artifacts",
        ],
        evidence=[
            Evidence(
                source="ROADMAP.md",
                detail="Scale promotion sequence and mandatory SLOs.",
            ),
            Evidence(
                source="docs/roadmap-tecnico.md",
                detail="SCALE-001 through SCALE-052 executable backlog.",
            ),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Operational scale status and next gates.",
            ),
        ],
        references={
            "real lane promotion": "gotcha.Generated records never count toward readiness"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Ingest mutable Infoelectoral elected-official snapshots",
        description=(
            "`Infoelectoral elected snapshots` use bounded XLSX parsing, "
            "content-addressed raw storage, set-based writes, stable historical "
            "facts, versioned observations, explicit presence, and source drift "
            "control. They assert an election occurrence, not cross-election "
            "identity or current office."
        ),
        steps=[
            "Run SNAPSHOT_DATE=<date> just etl-extract-infoelectoral-elected-officials.",
            "Require both workbooks to pass byte, ZIP-member, uncompressed-byte, row, and minimum-row bounds before database mutation.",
            "Review and explicitly override only legitimate per-chamber row drift above 15 percent.",
            "Preserve omitted prior outcomes as is_present=0; never delete their facts or observations.",
            "Inspect direct entity-link completeness, observation coverage, SQLite quick_check, and foreign_key_check in the run report.",
        ],
        validation=[
            "python3 -m unittest tests.test_infoelectoral_elected_officials",
            "SNAPSHOT_DATE=<date> just etl-extract-infoelectoral-elected-officials",
            "just etl-tracker-status",
        ],
        evidence=[
            Evidence(
                source="scripts/ingest_infoelectoral_elected_officials.py",
                detail="Canonical acquisition, validation, drift, ingest, and report command.",
            ),
            Evidence(
                source="etl/infoelectoral_es/elected_officials.py",
                detail="Set-based facts, observations, presence finalization, and direct links.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-elected-officials-real-20260811.json",
                detail="Live official-source v2 reconciliation evidence.",
            ),
        ],
        references={
            "Infoelectoral elected snapshots": (
                "fact.Readiness counts only verified official corpora"
            )
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Ingest official Infoelectoral candidate archives",
        description=(
            "`Infoelectoral candidate archives` are durable queued official "
            "fixed-width ZIP inputs. Public DNI, birth fields, and every other official "
            "identity field remain intact with source provenance. Normalized facts model election "
            "occurrences, not mandates or verified cross-election identities."
        ),
        steps=[
            "Refresh infoelectoral_descargas, then run SNAPSHOT_DATE=<date> just etl-infoelectoral-candidates-enqueue.",
            "Require a new access lever before retrying an origin reset or timeout; start with exactly one worker item.",
            "Keep the content-addressed raw root immutable; publish official public identity fields while excluding only secrets, workstation traces, and non-public state.",
            "Require ZIP/member/byte/ratio/row floors and the 15 percent pre-mutation archive drift gate before fact writes.",
            "Persist separate 03 party-row and 04 candidate-row totals per archive; require candidate totals to reconcile to present facts and party rows to be nonempty for every loaded archive.",
            "Complete all queue items and reconcile archive/source/fact/observation totals before materializing the separate candidate-occurrence Parquet contract; never coerce candidates into mandates or publish an empty artifact.",
            "Advance by official archive cohorts only: one archive, then 10, then the full queued set, with reconciliation and quality gates before every expansion.",
            "Keep source-scoped occurrence people separate until adjudicated identity evidence supports merge or split decisions.",
        ],
        validation=[
            "python3 -m unittest tests.test_infoelectoral_candidates",
            "python3 -m unittest tests.test_candidate_occurrence_partitions",
            "just etl-infoelectoral-candidates-report",
            "just etl-scale-export-semantic-candidate-occurrences",
            "just etl-scale-validate-semantic-candidate-occurrences",
            "just privacy-check-public-artifacts",
        ],
        evidence=[
            Evidence(
                source="scripts/ingest_infoelectoral_candidates.py",
                detail="Durable catalog, worker, local replay, drift, provenance, and report command.",
            ),
            Evidence(
                source="publicdata_publish/candidate_occurrence_partitions.py",
                detail="Public typed partitions retain official identity fields with provenance, bounded files, canonical fingerprints, and incremental reuse.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-candidate-archive-queue-latest.json",
                detail="Canonical 60-item pending queue and database integrity snapshot.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/reports/infoelectoral-candidate-archive-lane-20260811.md",
                detail="Public-field retention, access blocker, implementation, gates, and next action.",
            ),
        ],
        references={
            "Infoelectoral candidate archives": (
                "fact.Readiness counts only verified official corpora"
            )
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Build and publish the source-scoped actor graph",
        description=(
            "`actor graph publication` projects the complete selected official "
            "actor corpus into source-scoped identities, time-bounded relationships, "
            "resolution decisions, and evidence rows. It never merges actors across "
            "sources by name and exposes only a bounded browser projection."
        ),
        steps=[
            "Hash all selected source rows and upstream release artifacts before assigning a release ID.",
            "Reconstruct every input source definition; retain metadata conflicts under deterministic source-id@database-key mappings.",
            "Keep actor identity validity separate from mandate, candidacy, meeting, agreement, award, and action dates.",
            "Materialize actors, identifiers, aliases, relationships, decisions, and evidence into a sibling temporary database.",
            "Fail on source-mapping drift, missing labels, unsafe identity state, evidence mismatch, FK failure, or integrity failure before atomic replacement.",
            "Run the independent validator against every selected real row and repeat the producer with an idempotence reference.",
            "Publish bounded aggregate and sample JSON plus the static evidence view; keep the full graph out of the browser.",
            "Before million-scale promotion, export bounded Parquet partitions, publish durable origin, and prove clean restore and second-snapshot history.",
        ],
        validation=[
            "just actor-graph-check",
            "just privacy-check-public-artifacts",
            "just site-build",
            "just site-publish",
            "just actor-graph-live-verify",
        ],
        evidence=[
            Evidence(
                source="docs/architecture/entity-resolution-v1.md",
                detail="Identity layers, time model, source-collision handling, failure modes, and scale gates.",
            ),
            Evidence(
                source="docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-validation.json",
                detail="Independent full-row reconciliation, identity, source mapping, replay, and provenance proof.",
            ),
            Evidence(
                source="docs/release-notes/actor-graph-mvp.md",
                detail="Exact release counts, hashes, physical limits, and open promotion gates.",
            ),
        ],
        references={
            "actor graph publication": "gotcha.Source IDs can collide across input databases"
        },
        updated_at=UPDATED,
    ),
    Workflow(
        name="Rebuild outcome review capacity",
        description=(
            "`outcome capacity rebuild` serially validates the official identity "
            "companion, portable C2B pair package, and C2C capacity database against "
            "the same immutable real planner inputs. Shared kernel leases prevent "
            "mixed source snapshots."
        ),
        steps=[
            "Run the identity companion check with exact official public names and no identity suppression.",
            "Export the pair package into a private work root with bounded inventory, descriptor-bound reads, durable checkpoints, and fail-closed controls.",
            "Interrupt after a real checkpoint cohort, resume against identical source fingerprints, and reject config or source drift.",
            "Validate all rows, physical files, hashes, manifest roots, decompression bounds, memory ceilings, and non-claim safety fields.",
            "Build an independent replay root and require every Parquet byte and semantic root to match.",
            "Materialize and validate C2C capacity only after pair leases release; require zero human or release events unless real operational inputs were explicitly supplied.",
            "Run real-data-only, publication-hygiene, staging-integrity, and repository-hygiene gates before recording current status in the tracker.",
        ],
        validation=[
            "just outcome-pair-identity-check",
            "just outcome-pair-discovery-check",
            "just outcome-review-control-c2c-check",
            "just privacy-check-public-artifacts",
            "just etl-data-integrity-audit-all-staging",
            "just etl-data-integrity-reconcile-all-staging",
            "just repo-hygiene-check",
        ],
        evidence=[
            Evidence(
                source="tests/test_outcome_pair_identity_companion_real_pipeline.py",
                detail="Real-source identity, restart, path, resource, and exact replay tests.",
            ),
            Evidence(
                source="tests/test_outcome_pair_partitions_real_pipeline.py",
                detail="Real-source package interruption, recovery, inventory, Parquet, and replay tests.",
            ),
            Evidence(
                source="tests/test_outcome_review_control_c2c_real_pipeline.py",
                detail="Real capacity, immutable-operation boundary, leases, paths, and adversarial tests.",
            ),
        ],
        references={
            "outcome capacity rebuild": "fact.Outcome C2B delivery separates planning identity and portable rows"
        },
        updated_at=UPDATED,
    ),
]


PROJECT_GOTCHAS = [
    Gotcha(
        name="Do not mix host and container access to one live SQLite WAL state",
        description=(
            "`single-runtime SQLite state` is required for long document queues on a "
            "bind-mounted database. Concurrent host inspection while a container owns "
            "the live WAL state can produce unsafe cross-runtime locking behavior; the "
            "first document-profile attempt was quarantined after SQLite quick_check "
            "reported malformed structures. This state is never counted as evidence."
        ),
        mitigation=(
            "Run the producer and all live state inspection in one runtime namespace. "
            "Use emitted progress instead of opening the live database elsewhere. After "
            "the writer exits, run quick_check before reuse; quarantine any failed state "
            "without deleting it, then resume from a new database."
        ),
        evidence=[
            Evidence(
                source="justfile",
                detail="Document profile producer and validator use the pinned Docker runtime; lifecycle inspection runs only after the producer exits.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/reports/million-scale-foundation-and-real-document-run.md",
                detail="Profile closeout records the quarantined container state and successful host-only replacement.",
            ),
        ],
        references={
            "single-runtime SQLite state": "fact.Project is static and SQLite first"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Bound semantic markup locators to major source containers",
        description=(
            "`major-container markup lineage` avoids treating every XML/HTML leaf as "
            "a section. A real depth-3 canary averaged about 79 locators per document "
            "and reached 25,061 locators on one BOE XML, which projected toward about "
            "79 million content locators at one million documents."
        ),
        mitigation=(
            "Use source-derived XPath owners only for root/direct-child structure and "
            "recognized major containers, then split long sections at the configured "
            "character bound. Require exact reconstruction of the existing native CAS; "
            "fall back to bounded character spans when structure cannot be proven. Bind "
            "the locator algorithm and bounds into queue metadata, canary real files, "
            "and reject designs whose locator fan-out does not scale."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-locator-extraction.json",
                detail="Complete v3 fan-out, source-structure coverage, fallback, memory, and throughput evidence.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-locator-validation.json",
                detail="Independent exact full-corpus locator replay.",
            ),
        ],
        references={
            "major-container markup lineage": "fact.BOE document and candidate cohorts preserve exact public evidence"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Never run markup normalization over extracted PDF plain text",
        description=(
            "`PDF plain-text normalization` must preserve literal angle brackets. A real "
            "55-page official PDF contained less-than and greater-than text across page "
            "boundaries; the former HTML tag regex treated that range as markup and "
            "silently removed public evidence. Six real PDF CAS objects changed when the "
            "defect was corrected, recovering 50,958 characters."
        ),
        mitigation=(
            "Use markup normalization only for HTML/XML inputs. Normalize PDF extractor "
            "output as plain text, bind the extraction algorithm version into queue and "
            "manifest identity, reconstruct native text from exact page output, and rerun "
            "every dependent profile, OCR, locator, origin, and readiness gate after a "
            "normalization-version change."
        ),
        evidence=[
            Evidence(
                source="publicdata_docs/extraction.py",
                detail="Separate markup/plain-text normalization and exact PDF page reconstruction contract.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-locator-validation.json",
                detail="Full real-corpus raw/native rehash and exact locator recomputation.",
            ),
        ],
        references={
            "PDF plain-text normalization": "fact.BOE document and candidate cohorts preserve exact public evidence"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Keep volatile telemetry out of semantic manifests",
        description=(
            "`semantic manifest determinism` requires content identity to exclude "
            "wall time, per-item elapsed time, RSS, CPU, generated timestamps, and "
            "other run-variant observations. Embedding those values makes identical "
            "official inputs and output CAS objects produce different manifest hashes."
        ),
        mitigation=(
            "Store volatile telemetry in the durable state database and aggregate run "
            "report. Keep the semantic manifest limited to stable evidence identity and "
            "prove replay hashes across independent real states."
        ),
        evidence=[
            Evidence(
                source="scripts/ocr_real_document_pages.py",
                detail="Per-page elapsed stays in SQLite and aggregate totals but is excluded from semantic manifest rows.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-validation-physical-20260829.json",
                detail="Independent validation of the stable 856-row real OCR manifest and all referenced CAS objects.",
            ),
        ],
        references={
            "semantic manifest determinism": (
                "fact.Readiness counts only verified official corpora"
            )
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Source IDs can collide across input databases",
        description=(
            "`source catalog collision` occurs when separate databases reuse one "
            "source_id but publish different names, URLs, formats, or timestamps. "
            "INSERT OR IGNORE silently selects load order and corrupts provenance."
        ),
        mitigation=(
            "Reconstruct the complete source catalog before graph writes. Keep "
            "identical definitions under the upstream ID; namespace every conflicting "
            "origin as source-id@database-key, persist its metadata hash and mapping "
            "reason, and include the mapping digest in release identity."
        ),
        evidence=[
            Evidence(
                source="scripts/materialize_actor_graph.py",
                detail="Deterministic source mapping plan and atomic source-scoped graph projection.",
            ),
            Evidence(
                source="docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-validation.json",
                detail="Real corpus proves 55 mappings, three conflicting upstream IDs, and seven namespaced origins.",
            ),
        ],
        references={
            "source catalog collision": "workflow.Build and publish the source-scoped actor graph"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Baseline indicator release is not revision proof",
        description=(
            "`indicator baseline semantics` means the first capture observed by this "
            "project. It does not mean the upstream value is final, unchanged, or free "
            "of revisions before capture. A single snapshot cannot prove revision behavior."
        ),
        mitigation=(
            "Publish baseline and source status explicitly, keep uncertainty visible, "
            "capture a second official snapshot, and append version deltas without "
            "overwriting the original observation."
        ),
        evidence=[
            Evidence(
                source="docs/data-model/indicators-spec-v1.md",
                detail="Append-only release and observation-version semantics.",
            ),
            Evidence(
                source="docs/release-notes/indicators-mvp.md",
                detail="First public release limitation and required second-snapshot gate.",
            ),
        ],
        references={
            "indicator baseline semantics": "workflow.Publish a canonical Eurostat indicator family"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Senate session cache is legislature scoped",
        description=(
            "`Senate cache scope` is part of evidence identity. Session filenames "
            "repeat across legislatures, so a recursive fallback across all "
            "legislature folders can silently attach the wrong roll call. Absence "
            "is also distinct from no-vote, and successful refreshes must remove "
            "stale seats without inventing unitemized individual ballots."
        ),
        mitigation=(
            "Resolve cached files inside the legislature directory, use "
            "--local-cache-only when network is forbidden, preserve totals_absent, "
            "and run scripts/audit_vote_database.py after authoritative refresh."
        ),
        evidence=[
            Evidence(
                source="publicdata_connectors_es/parliamentary/senado_votaciones.py",
                detail="Legislature-isolated cache lookup and hard local-only loader.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/senado-local-cache-repair-audit.json",
                detail="Measured offline repair, integrity, and reconciliation evidence.",
            ),
        ],
        references={"Senate cache scope": "workflow.Promote one real scale lane"},
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Do not fake blocked sources done",
        description=(
            "`blocked source honesty` is mandatory: WAF, Cloudflare challenge, "
            "HTML where structured data is expected, persistent 403, or missing "
            "credentials must stay PARTIAL/TODO with evidence, not DONE."
        ),
        mitigation=(
            "Record the blocker in the tracker, add name-and-shame evidence when "
            "confirmed, and move to a controllable primary slice."
        ),
        evidence=[
            Evidence(source="AGENTS.md", detail="Strict-network and WAF rules."),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="Rules require evidence and records_loaded > 0 for DONE.",
            ),
        ],
        references={
            "blocked source honesty": "workflow.Strict network blocker handling"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Public artifact hygiene gate is mandatory",
        description=(
            "`public artifact hygiene gate` blocks publication when docs or "
            "published outputs contain workstation paths, personal local profile "
            "data, secrets, cookies, bearer tokens, or environment values."
        ),
        mitigation=(
            "Fix the generator or sanitizer, regenerate artifacts, then rerun "
            "just privacy-check-public-artifacts before public build or HF publish."
        ),
        evidence=[
            Evidence(source="AGENTS.md", detail="Privacy and publication hygiene."),
            Evidence(
                source="tests/test_check_public_privacy_leaks.py",
                detail="Publication-hygiene leak tests; public-source identity is allowed.",
            ),
            Evidence(
                source="justfile", detail="privacy-check-public-artifacts recipe."
            ),
        ],
        references={
            "public artifact hygiene gate": (
                "workflow.Accountability ledger refresh and publish"
            )
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Heavy backfills stay explicit",
        description=(
            "`explicit backfills` keep normal ingestion fast. Historical "
            "normalization, initiative document downloads, and heavy evidence "
            "hydration should run through dedicated commands, not hidden inside "
            "the default ingest path."
        ),
        mitigation=(
            "Use the documented backfill commands and cache/prefetch patterns; "
            "keep ingest focused on raw/source traceability and quick upserts."
        ),
        evidence=[
            Evidence(
                source="AGENTS.md",
                detail="ETL performance rules and heavy work section.",
            ),
            Evidence(
                source="scripts/ingestar_politicos_es.py",
                detail="Dedicated backfill-normalized command.",
            ),
            Evidence(
                source="scripts/ingestar_parlamentario_es.py",
                detail="Dedicated initiative link/document backfills.",
            ),
        ],
        references={"explicit backfills": "fact.Project is static and SQLite first"},
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Legacy initiative document dry run still uses network",
        description=(
            "`legacy document dry run` is not discovery-only: the old "
            "backfill-initiative-documents --dry-run path can still perform live "
            "GET requests while materializing document mappings."
        ),
        mitigation=(
            "For scalable link discovery, run scripts/enqueue_pipeline_work.py, "
            "which materializes initiative document links without downloading; "
            "then let the durable fetch queue own bounded network work."
        ),
        evidence=[
            Evidence(
                source="scripts/enqueue_pipeline_work.py",
                detail="Separates link materialization from document-fetch enqueue.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/reports/million-scale-foundation-and-real-document-run.md",
                detail="Records the real discovery, fetch, and extraction separation.",
            ),
        ],
        references={"legacy document dry run": "workflow.Promote one real scale lane"},
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Do not flatten source confidence",
        description=(
            "`source confidence` must stay visible. Tier 1 votes, BOE, official "
            "bulletins, procurement, subsidies, sanctions, inspections, court, "
            "or audit records are not equivalent to communications, reusers, or "
            "media leads."
        ),
        mitigation=(
            "Preserve evidence_tier, source_id, source_url, caveats, and "
            "unknown/no_signal states in exports and UI."
        ),
        evidence=[
            Evidence(source="ROADMAP.md", detail="Source hierarchy Tier 1 through 5."),
            Evidence(
                source="scripts/accountability_evidence_tiers.py",
                detail="Evidence tier inference.",
            ),
            Evidence(
                source="AGENTS.md",
                detail="Preserve explainability and uncertainty by default.",
            ),
        ],
        references={"source confidence": "domain_concept.Evidence hierarchy"},
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Parliamentary group is not party",
        description=(
            "`group is not party` for attribution. Parliamentary group rollups "
            "must stay separate from party rollups, and party attribution should "
            "use source-backed party_id such as a dated mandate."
        ),
        mitigation=(
            "Keep group and party actors distinct in ledger exports; never infer "
            "formal party affiliation only from parliamentary group code."
        ),
        evidence=[
            Evidence(
                source="ROADMAP.md",
                detail="D0 identity bridge caveat keeps group rollups separate.",
            ),
            Evidence(
                source="docs/etl/e2e-scrape-load-tracker.md",
                detail="D1 party rollups source-backed row.",
            ),
            Evidence(
                source="scripts/backfill_accountability_ledger_from_parliament.py",
                detail="Party rollups based on dated mandate party_id.",
            ),
        ],
        references={"group is not party": "domain_concept.Accountability ledger spine"},
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Generated records never count toward readiness",
        description=(
            "`official records only` means coverage and scale are measured from "
            "captured official sources with materialized provenance and artifacts."
        ),
        mitigation=(
            "Keep readiness incomplete until each priority lane passes "
            "its own representative real-corpus gate and restore/reconciliation proof."
        ),
        evidence=[
            Evidence(
                source="etl/data/published/scale-readiness-latest.json",
                detail="Policy and corpus results count only official-source artifacts.",
            ),
            Evidence(
                source="ROADMAP.md",
                detail="Capacity-class promotion requires representative real corpora.",
            ),
        ],
        references={
            "official records only": "fact.Readiness counts only verified official corpora"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Fallback fixtures can contaminate production artifacts",
        description=(
            "`fallback contamination` occurs when sample, fixture, generated, or "
            "placeholder rows enter a staging database, semantic ledger, dossier, "
            "snapshot, or published artifact and are then mistaken for official facts."
        ),
        mitigation=(
            "Run just real-data-only-check, remove contaminated source records from "
            "the owning database, rebuild every downstream artifact, and record exact "
            "removed counts and evidence. A blocked or empty real source stays empty."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/non-real-record-purge-20260812.json",
                detail="Exact purge of fallback-derived source, issue, policy-event, and ledger rows.",
            ),
            Evidence(
                source="scripts/check_real_data_only.py",
                detail="Repository gate rejects known non-real markers and contaminated artifacts.",
            ),
            Evidence(
                source="docs/etl/sprints/DATA-INTEGRITY-20260812/report.md",
                detail="Correction report and downstream rebuild contract.",
            ),
        ],
        references={
            "fallback contamination": "fact.Readiness counts only verified official corpora"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Valid zero values must survive validation defaults",
        description=(
            "`zero-safe validation` matters for exact scale gates. Using truthiness "
            "such as value or -1 converts a valid zero gap or zero failure count into "
            "the fallback and can make correct official evidence fail validation."
        ),
        mitigation=(
            "Default only when a key is absent or its value is None. Keep explicit "
            "zero-value regression tests for numeric supply gaps, failure totals, and "
            "other readiness counters."
        ),
        evidence=[
            Evidence(
                source="scripts/validate_real_document_source_universe.py",
                detail="Zero-safe integer parsing preserves the exact zero numeric gap.",
            ),
            Evidence(
                source="tests/test_real_document_source_universe.py",
                detail="Real-artifact regression proves the zero-gap source universe validates.",
            ),
        ],
        references={
            "zero-safe validation": "workflow.Operate the bounded document fetch queue"
        },
        updated_at=UPDATED,
    ),
    Gotcha(
        name="Million-scale control state must be sharded and generation-bound",
        description=(
            "`input-bound control state` appears before raw bytes become the only "
            "problem. BOE lineage now bounds 100,051 rows / 234,632,869 logical bytes "
            "behind 11 content-addressed gzip shards and a small index. Its immutable "
            "index archives, activation receipts, predecessor chain, forced-interruption "
            "test, and independent lifecycle audit prove non-destructive lineage "
            "supersession. Native and OCR now use the same terminal-only activation "
            "boundary, bounded gzip shards, immutable receipts, checksum-addressed "
            "SQLite state snapshots, restored-state quick checks, and fail-closed "
            "input identities while reusing content-addressed output safely. The "
            "complete local origin lane adds a resumable 240,226-object queue, 25 "
            "bounded replica-manifest shards, a restorable queue snapshot, and a "
            "full 5,902,879,469-byte bounded clean restore without claiming that a "
            "same-machine filesystem origin is durable public recovery. Its exact "
            "generation now also forms 25 deterministic publication packs with both "
            "10,000-object and 448-MiB payload ceilings, content-addressed member "
            "manifests, complete member rehash, and no-delete lifecycle control. The "
            "exact pack generation is bound to one 122-file content-addressed release; "
            "its publisher refuses immutable collisions, never deletes, verifies parity "
            "before resume, seals the release manifest after data, and moves the latest "
            "pointer last. A read-only live preflight is not durable-origin proof."
        ),
        mitigation=(
            "Shard large manifests and execution state by deterministic generation, "
            "record immutable input roots, publish manifest-last, preserve explicit "
            "supersession lineage, and reject state whose bound input identity differs. "
            "Use deterministic byte-bounded packs instead of loose million-object upload "
            "fanout. Require explicit release authority, immutable remote checksum parity, "
            "manifest-after-data and pointer-last ordering. Prove independent remote "
            "reconstruction and interrupted replay before any durability or one-million-row "
            "claim."
        ),
        evidence=[
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus-lineage-validation-20260830.json",
                detail="Independent shard, row, raw-document, summary, order, bound, and policy validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus-generation-audit-20260830.json",
                detail="Active index archive, receipt chain, retained generation, and zero orphan or deletion state.",
            ),
            Evidence(
                source="tests/test_boe_document_corpus_sharded_manifest.py",
                detail="Real-capture interruption and successor transition retain the old live index and both generations.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-validation.json",
                detail="Current generation-bound native-text state and independently rehashed manifest/CAS.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-text-generation-audit.json",
                detail="Full native shard and restored SQLite state audit with zero lifecycle debris.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr-generation-audit.json",
                detail="Full OCR shard and restored SQLite state audit with exact public-information retention.",
            ),
            Evidence(
                source="tests/test_real_document_generation_lifecycle.py",
                detail="Real captured rows prove interrupted activation availability, retained candidate state, and non-destructive supersession.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-replication.json",
                detail="Exact raw, native, and OCR local-origin queue totals, sharded activation, and zero-failure replication.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-clean-restore.json",
                detail="Full bounded restore rehashes every current object and byte while keeping durable-public-origin false.",
            ),
            Evidence(
                source="tests/test_real_document_origin_replication.py",
                detail="Real production raw, native, and OCR objects prove replication, activation, audit, and clean restore without invented fixtures.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-packaging.json",
                detail="Exact origin generation becomes 25 deterministic object-and-byte-bounded immutable packs with zero failure.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-pack-validation.json",
                detail="Full validation restores and rehashes all 240,226 packed real objects and 5,902,879,469 payload bytes.",
            ),
            Evidence(
                source="tests/test_real_document_origin_packs.py",
                detail="Actual production objects prove byte-identical deterministic replay plus lifecycle and full member validation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-release-preparation.json",
                detail="Exact 122-file release inventory rehashes pack data, retained lifecycle controls, and validation evidence without remote mutation.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-hf-publish-dry-run.json",
                detail="Read-only public-origin preflight proves collision-free append-only eligibility while durable origin remains false.",
            ),
            Evidence(
                source="tests/test_real_document_origin_release.py",
                detail="Production-only release replay, local rehash, bounded upload batches, and double remote-write fence tests.",
            ),
            Evidence(
                source="docs/etl/sprints/SCALE-FOUNDATION-20260810/reports/million-scale-foundation-and-real-document-run.md",
                detail="Current report records completed BOE/native/OCR sharding and lifecycle boundaries plus remaining physical gates.",
            ),
        ],
        references={
            "input-bound control state": "workflow.Operate the bounded document fetch queue"
        },
        updated_at=UPDATED,
    ),
]
