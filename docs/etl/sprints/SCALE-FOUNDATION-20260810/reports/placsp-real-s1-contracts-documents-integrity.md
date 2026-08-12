# PLACSP real H1 S1: contracts, documents, and integrity review

Date: `2026-08-11`

Status: `money_fact_s1_passed; stable_contract_s1_passed; historical_representativeness_unproven; not_published; not_promoted`

## Scope

Official PLACSP monthly complete-profile archives for January-June 2025. This slice proves the bounded archive-to-review pipeline above the real `100,000` stable-contract gate. It does not claim complete history, representative source coverage, payment execution, supplier identity resolution, or corruption findings.

## End-to-end result

| Stage | Observed | Gate |
| --- | ---: | --- |
| Official ZIP archives | `6/6` succeeded; `1,037,792,505` compressed bytes | pass for H1 cohort |
| Atom members | `667/667` succeeded; `10,077,339,637` uncompressed bytes | pass for H1 cohort |
| Records seen | `331,623` across two quarterly runs | reconciled by run |
| Unique record versions | `330,577` corpus total | reconciled |
| Stable contracts | `121,555` | `S1 100k` row gate passed |
| Tombstone sightings | `1,014` | preserved |
| Award-result versions | `262,558` | preserved |
| Document sightings | `3,190,620` | preserved |
| Duplicate-version sightings | `935` within quarterly runs | deduplicated without loss |
| Latest public-money facts | `263,302` = `121,555` notices + `141,747` awards | money-fact `S1` pass |
| Semantic partitions/files | `50/52` | full validator pass; unchanged replay `50/50` partitions / `52/52` files |
| Document queue | `998,392` unique URLs in `256` partitions | enqueued, not drained |
| Real document sample | `20/20`, `21,055,060` bytes, `20` hashes | bounded sample pass |
| Internal review signals | `2,036` v4 with `6,788` evidence links | internal only; idempotent replay |

Database integrity after acquisition, document sample, and signal materialization: `quick_check=ok`; foreign-key violations `0`.

## Complete-history readiness

The official catalog is now a bounded input contract, not a manually maintained URL list. The live `2026-08-11` discovery:

- fetched `65,235` catalog bytes with verified system CA and recorded SHA-256,
- discovered `35` PLACSP archive links,
- selected `22/22` expected inputs with no gaps: annual 2012-2025 plus monthly January-August 2026,
- rejected non-HTTPS/conflicting links and failed closed on missing periods in tests,
- locked the queue with archive-contract SHA-256 `27848dea5b511d0275e081d0e1a6e8cea6be03b235e999b5c33eab34601b29a1`,
- enqueued `22` pending archive items; idempotence replay inserted `0`.

The history download has not started. Archive and member workers now run a reserve-aware storage check before claiming queue items. The real archive worker reports `blocked_storage`: `41,134,141,440` bytes free against `107,911,053,312` required (`100 GiB` floor plus `512 MiB` next-archive reserve). All `22` items remain pending with `0` attempts, `0` leases, and therefore `0` network requests. A separate verified probe of the 2024 annual archive reset the connection three times; a one-byte diagnostic returned HTML `HTTP/1.1 200 Error` instead of ZIP. Earlier on the same day, all six H1 monthly archives succeeded, so this is recorded as intermittent access, not a permanent outage. No retry occurs until storage/origin capacity passes and a fresh upstream lever exists.

## Monetary and privacy semantics

- Published notice values: `EUR 182,101,866,149.820000`.
- Published award values: `EUR 89,093,709,352.750000`.
- Combined values: `EUR 271,195,575,502.570000`.
- Amount-present rows: `249,875/263,302` (`94.900532%`).
- Strictly classified legal-entity counterparties published: `117,531`.
- Potential natural-person counterparties withheld: `8,260`.
- Unclassified counterparties withheld: `15,956`.
- Private-token findings: `0`.

Notice and award amounts are publication values. They are not invoices, cash disbursements, or budget-execution proof.

## Failure found and closed

Nine Atom members initially exceeded the fixture-derived `1,000`-documents-per-entry ceiling. The observed maximum across those entries was `3,250`. The hard ceiling was raised explicitly to `10,000`; only matching dead items were requeued; all nine completed. The limit remains finite and tested.

The first integrity-signal persist exposed a uniqueness defect: authority+month was insufficient when one authority had multiple CPV patterns in the same month. Twelve partial v2 items are retained as superseded audit history. Detector v3 corrected authority+CPV+month identity. H1 then exposed a revision-lifecycle requirement: detector v4 adds an evidence-set fingerprint, supersedes missing/current-prior detector revisions, and withdraws superseded publication state. The final replay keeps `2,036` current v4 signals and `6,788` evidence links with `0` additional supersessions; `12` v2 and `1,041` v3 rows remain auditable, superseded, and withdrawn.

## Integrity-signal safety boundary

Detector v4 examines the latest contract version, prefers award-result amounts, and fingerprints the exact evidence set. At the configured analytical threshold of `EUR 15,000` and minimum group size `3`, it creates review leads only.

- `public_by_default=false`
- `human_review_required=true`
- `corruption_finding=false`
- state `review_signal`
- publication status `internal`

No signal may become a public risk claim without evidence corroboration, two human reviews including one independent reviewer, right-of-reply resolution, counterevidence handling, and correction/supersession support.

## Reproducible commands

```bash
just etl-scale-placsp-archives-enqueue
just etl-scale-placsp-history-discover
just etl-scale-placsp-history-enqueue
just etl-scale-placsp-history-archives-work
just etl-scale-placsp-history-members-work
just etl-scale-placsp-archives-work
just etl-scale-placsp-members-work
just etl-scale-placsp-report
just etl-scale-placsp-corpus-report
just etl-scale-placsp-export
just etl-scale-placsp-validate
just etl-scale-placsp-replay
just etl-scale-placsp-replay-validate
just etl-scale-placsp-documents-enqueue
just etl-scale-placsp-documents-work
just etl-scale-placsp-integrity-review
just etl-scale-readiness
```

`PLACSP_BULK_ARCHIVE_ARGS` selects explicit archives. `PLACSP_HISTORY_MIN_FREE_BYTES` defaults to `107374182400`; history archive/member commands exit non-zero without claiming work when floor plus next-item reserve does not fit. `PLACSP_DOCUMENT_WORKER_MAX_ITEMS` defaults to a small cohort. Do not drain the full document queue until request budgets, remote origin, telemetry, and extraction capacity are configured.

## Evidence

- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-run.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-archive-catalog-20260811.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-enqueue-20260811.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-storage-preflight-20260811.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-history-archive-access-probe-20260811.md`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025q2-run.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-manifest.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-validation.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-incremental-manifest.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-semantic-incremental-validation.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-document-fetch-enqueue.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-document-fetch-sample.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-integrity-signal-run.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-2025h1-integrity-signal-idempotence.json`

## Next gate

1. Provision versioned remote origin or enough local capacity to pass the `100 GiB` floor plus next-item reserve, obtain a fresh upstream-success signal, then drain complete official archive history since 2012 and prove representative authority/procedure/CPV/NUTS strata.
2. Reconcile expected period/archive/member counts against the official index, including revisions and withdrawals.
3. Run document cohorts `100 -> 1,000 -> 10,000 -> 100,000` under per-host budgets; publish throughput, bytes, cost, MIME, pages, retry, and dead-letter strata.
4. Replicate raw archives, documents, text, and Parquet to a versioned origin; pass clean-cache restore.
5. Resolve legal suppliers with external identifiers and an adjudicated merge/split/conflict set.
6. Link modifications, invoices/payments, budget execution, audit, sanction, and control-body findings as separate evidence semantics.
7. Calibrate the `2,036` review queue with a stratified gold set, double review, adjudication, false-positive/reversal/drift metrics, counterevidence, and right of reply.
8. Reach `1,000,000` stable contracts/lots/awards or `100%` of the official universe when smaller; then validate bounded public delivery and promote only after every lane-specific gate passes.
