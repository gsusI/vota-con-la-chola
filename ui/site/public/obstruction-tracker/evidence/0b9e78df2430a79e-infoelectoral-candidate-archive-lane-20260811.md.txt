# Infoelectoral candidate archive lane

Date: `2026-08-11`

Status: `PARTIAL` — scalable ingestion path implemented and fixture-proven; real origin acquisition blocked before the first archive completed.

## Where we are now

- The canonical Infoelectoral catalog contains `60` supported named-candidate archives across `36` election IDs: Congress `16`, Senate `13`, municipal `12`, cabildos `10`, and European Parliament `9`.
- All `60` immutable archive references are in durable queue `infoelectoral-candidates-v1`: `60 pending`, `0 leased`, `0 succeeded`, `0 dead`, `0 attempts`.
- The official API probe timed out after `30s` with zero bytes. One separately bounded direct probe of the official 2023 municipal archive ended in `Connection reset by peer`; no partial file remains.
- No real candidate fact has been loaded or published. The actor lane therefore remains `88,031` mandates, below the `100,000` real `S1` row gate.

Evidence:

- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-candidate-archive-queue-latest.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/infoelectoral-candidate-origin-access-20260811.json`

## What is implemented

- Strict official-host URL allowlist and stable source/archive/election identities.
- Durable queue references partitioned by election year. Atomic leases, heartbeat renewal, bounded attempts, retry/dead-letter audit, and repeatable workers reuse the shared scale control plane.
- Streaming content-addressed acquisition with byte ceilings, atomic finalization, and no corpus-sized in-memory archive body.
- ZIP safety gates for path traversal, duplicate members, member count, compressed bytes, total uncompressed bytes, compression ratio, party rows, and candidate rows.
- ISO-8859-1 fixed-width parsing for official `03*.DAT` party rows and `04*.DAT` candidate rows.
- Deterministic source-scoped candidate occurrence IDs based on election/position coordinates. Equal names across elections are never merged implicitly.
- Set-based SQLite staging and bounded write batches. Candidate occurrences remain separate from mandates; candidacy is not misrepresented as public office.
- Direct links to source record, occurrence-scoped person, party, and territory; immutable per-snapshot/per-content observations; complete-stream presence finalization preserves removals instead of deleting history.
- Pre-mutation row-count floor and `15%` archive drift blocker, with explicit reviewed override only.
- Official raw archives are retained as public-domain accountability evidence. Source DNI and birth-date fields are persisted in normalized candidate facts and source payloads with archive URL, checksum, member, and line provenance; classification never suppresses them.
- A local replay test runs acquisition, CAS, validation, ingestion, provenance, queue completion, report, SQLite integrity, and FK checks end-to-end. Another test proves a `99%` source-row drop is dead-lettered before fact mutation.
- Parser metrics keep `03*.DAT` party rows separate from `04*.DAT` candidate rows. The archive ledger persists both totals; readiness now requires latest archive candidate totals to equal present occurrence facts and every loaded archive to contain party rows.
- The typed `candidate_occurrences` Parquet lane partitions by election type/year, bounds row groups and files, fingerprints canonical public rows, reuses unchanged partitions, and validates every row/file/schema/hash/partition/source identity independently. Its public schema retains source DNI and birth-date fields exactly when the official archive supplies them.
- Historical generated capacity artifacts are excluded from readiness and are not project data. No synthetic or mock row may satisfy a coverage, capacity, quality, or publication gate. Scale proof now requires real official archive rows end to end.

Canonical commands:

```bash
SNAPSHOT_DATE=2026-08-11 just etl-infoelectoral-candidates-enqueue
INFOELECTORAL_CANDIDATE_WORKER_MAX_ITEMS=1 just etl-infoelectoral-candidates-work
just etl-infoelectoral-candidates-report
just etl-scale-export-semantic-candidate-occurrences
just etl-scale-validate-semantic-candidate-occurrences
just etl-scale-benchmark-candidate-occurrences-million
just etl-scale-benchmark-candidate-occurrences-ten-million-streaming
just etl-scale-benchmark-candidate-archive-parser-million
```

For a reviewed local replay, set `INFOELECTORAL_CANDIDATE_LOCAL_ARCHIVE_DIR` to a repo-mounted restricted directory containing the exact official archive filenames.

## Where we are going

1. Acquire one fresh archive only after a new lever: confirmed origin recovery, an official alternate mirror, or a reviewed local official archive.
2. Validate the first real archive against format, row-floor, drift, privacy, memory, provenance, and DB reconciliation gates.
3. Run multiple independent bounded workers, beginning at one request per origin host and increasing only from measured success/latency signals.
4. Complete all `60` queue items with exact source/archive/fact/observation balance and classified residual failures.
5. Materialize and independently validate the implemented candidate-occurrence Parquet contract on the complete reconciled real corpus. Do not force candidate rows into the mandate artifact, and do not publish an empty artifact.
6. Build an adjudicated cross-election identity layer with merge, split, conflict, review, and correction history; source-scoped occurrence people remain canonical until that gate passes.
7. Publish only PII-safe normalized facts and bounded manifests/shards to durable public origin, then execute a clean-room restore and public drill-down proof.

## Definition of done

- Queue: `60/60 succeeded`, `0 pending`, `0 leased`, `0 dead` or every residual dead item has an accepted documented disposition.
- Acquisition: archive checksums/bytes and official URLs recorded; no partial objects; reachable-item fetch success meets the lane SLO.
- Transformation: source rows, normalized occurrences, observations, and published rows reconcile exactly; replay creates no duplicate logical records.
- Public accountability identity: every official DNI and birth-date value is retained exactly in normalized/public artifacts with field-level source lineage; absent values remain absent rather than imputed.
- Identity: no cross-election merge is published without reviewed evidence; false merge/split and unresolved rates are measured.
- Scale: bounded memory and worker throughput measured on the complete real candidate corpus; actor/candidate lane reaches `S1` and progresses to `S2` or documents the smaller complete official universe.
- Higher scale: use the passed direct-columnar `10M` gate as the baseline; parallelize partition validation, then prove `100M` with bounded time/RSS/bytes/cost, interruption recovery, unchanged reuse, checksum verification, and clean-room restore before any `S4` claim.
- Publication: typed bounded partitions, manifest checksums, durable origin, independent validation, clean-room restore, and evidence drill-down all pass.

## Next action

No more blind retries this sprint. Obtain a new origin/access lever, then run exactly one queue worker item and compare the result against the recorded access failure before increasing throughput.
