# Infoelectoral historical elected officials: real ingest

Date: `2026-08-11`

## Where we are now

- Official inputs: Congress and Senate elected-official XLSX datasets listed by the Ministry of the Interior catalog.
- Acquisition: streamed to content-addressed storage with a `64 MiB` per-workbook cap and a reserve-aware `5 GiB` free-space floor.
- Transport: official origin, but `tls_verified=false`; the host's certificate chain does not verify in this runtime, so the canonical command uses a source-scoped TLS bypass and records it.
- Parsed outcomes: `8,926` total: `5,600` Congress and `3,326` Senate across `16` election dates from `1977-06-15` to `2023-07-23`.
- Load: two `5,000`-row bounded batches; `8,926` facts, source records, occurrence people, mandates, and observations reconcile exactly. Rerun is idempotent.
- Snapshot durability: `8,926` present, `0` absent; first/last-seen dates are complete. Removals in later complete snapshots remain as historical facts and become absent instead of disappearing.
- Navigation: every fact has direct links to its person, mandate, party, institution, role, territory, and source record.
- Drift: before fact mutation, per-chamber totals are compared with the prior complete snapshot. Unreviewed absolute drift above `15%` blocks the run; this replay reports `0%` for both chambers. Accepted upstream restructures require `--allow-large-drift`.
- Integrity: SQLite `quick_check=ok`, foreign-key violations `0`, all report checks pass, peak ingest RSS `49.246 MB`.
- Real actor artifact: `88,031` mandates / `79,023` distinct people, `108` Parquet partitions/files, `9,236,064` bytes, full-row validator `status=ok`, private findings `0`.
- Incremental proof: unchanged rebuild reuses `108/108` partitions through `108/108` hardlinks and rebuilds `0`.

## Semantics and limits

- Each imported person is a source-scoped historical election occurrence.
- Equal names across elections are not merged without evidence.
- The rows do not assert current office, continuous tenure, or external identity equivalence.
- An observation is versioned by outcome, snapshot date, and workbook content hash; execution reruns update last-observed metadata without duplicating the observation.
- The actor lane remains `11,969` rows below `S1 100k` and remains local/unpublished.

## Reproduce

```sh
SNAPSHOT_DATE=2026-08-11 just etl-extract-infoelectoral-elected-officials
SNAPSHOT_DATE=2026-08-11 just etl-scale-export-semantic-actor-mandates
SNAPSHOT_DATE=2026-08-11 just etl-scale-validate-semantic-actor-mandates
```

Evidence:

- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-elected-officials-real-20260811.json`
- `etl/data/published/actor-mandate-semantic-partition-manifest-latest.json`
- `etl/data/published/actor-mandate-semantic-partition-validation-latest.json`
- `etl/data/published/actor-mandate-semantic-partition-incremental-latest.json`
- `etl/data/published/actor-mandate-semantic-partition-validation-incremental-latest.json`

## Where we are going

- Pass `S1` with at least `11,969` additional representative real actor/candidate/appointment outcomes and source-total reconciliation.
- Build an adjudicated identity gold set; measure precision/recall and preserve merge/split/conflict history.
- Reach `S2` using full official universes or one million real rows, then replicate to durable public origin and prove clean-room restore.

## What is next

1. Discover and contract official nominal candidate/result files beyond the elected-person workbooks.
2. Apply the same observation/presence/drift contract to every new mutable actor source.
3. Build the identity gold set and external merge/split/conflict workflow.
4. Reach `100,000` representative real actor rows, then publish to durable origin and run clean-room restore.
