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

UPDATED = date(2026, 8, 12)


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
            "memory, without using canonical corpus input. "
            "A real Senate slice has 6,792 fetched/extracted "
            "XML/HTML documents and a successful local object-restore sample, but "
            "the broader local inventory has only 21,398 file instances / 19,538 "
            "distinct contents, including 1,436 PDFs / 44,825 pages. Page-density "
            "routing finds 848 OCR candidates and a 20-page OCR sample passes, "
            "but semantic accuracy, production caching, scanned-PDF diversity, "
            "and 100k remain open. A disk-backed file/edge audit reconciles all "
            "21,398 inventory rows, verifies checksum lineage for 10,219 files, "
            "public URL lineage for 10,195, and decompressed checksums for all 6,792 "
            "referenced text artifacts with zero conflicts. It leaves 11,179 files "
            "explicitly unlinked instead of promoting them. Each real lane still needs "
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
        name="Contributor source onboarding",
        description=(
            "`source onboarding` starts with just add-source, which creates "
            "config, sample fixture, parser, strict sample test, and docs hook. "
            "PRs for new sources should pass just etl-contributor-gates."
        ),
        steps=[
            'Run: just add-source <source_id> name="..." scope="..." url="..." format=json.',
            "Fill the sample fixture and parser contract created under the contributor path.",
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
            "If a public UI surface changes, run just explorer-gh-pages-publish after merge-ready changes.",
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
]


PROJECT_GOTCHAS = [
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
]
