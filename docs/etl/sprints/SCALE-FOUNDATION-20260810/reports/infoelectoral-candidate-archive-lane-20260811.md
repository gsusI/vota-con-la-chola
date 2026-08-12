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
- Raw archive storage is restricted and ignored. Source DNI and birth-date columns are neither represented in the normalized record model nor written to `source_records` or candidate facts.
- A local replay test runs acquisition, CAS, validation, ingestion, provenance, queue completion, report, SQLite integrity, and FK checks end-to-end. Another test proves a `99%` source-row drop is dead-lettered before fact mutation.
- Parser metrics keep `03*.DAT` party rows separate from `04*.DAT` candidate rows. The archive ledger persists both totals; readiness now requires latest archive candidate totals to equal present occurrence facts and every loaded archive to contain party rows.
- A separate synthetic restricted ZIP proves the production parser at `1,000,000` candidate rows plus `1,000` party rows (`122,234,000` uncompressed bytes; `18,127,477` compressed; ratio `6.743023`). Parsing completes in `7.714978s` (`129,617.990 rows/s`) at `235.688 MB` peak RSS with exact counts/line range and `142,857` elected rows. The fixture raw contains synthetic DNI/birth fields, but neither enters the record schema or safe payload samples. It uses zero network and makes no real-archive claim.
- A separate typed `candidate_occurrences` Parquet lane partitions by election type/year, bounds row groups and files, fingerprints canonical public rows, reuses unchanged partitions, and validates every row/file/schema/hash/partition/source identity independently. The public schema excludes raw payload, DNI, and birth date. Four focused tests cover export/validation, unchanged reuse, one-partition invalidation, private-URL fail-closed behavior, and manifest tampering.
- The separate synthetic capacity run completes `1,000,000` source records, people, and candidate occurrences. A resumable single-transaction bulk load defers and rebuilds `12` secondary indexes. SQLite is `1,999,773,696` bytes, `quick_check=ok`, FK errors are `0`, and the covering partition scan uses no temporary sort. Generation takes `87.565821s` (`11,419.981 rows/s`) with `499.293 MB` RSS, an `11.277x` improvement over the prior indexed-write baseline. Its pre-export checkpoint validates script hash, exact DB bytes, counts, integrity, and query plan before resume.
- Export produces `50` typed Zstandard Parquet partitions/files (`108,575,834` bytes) in `95.097071s`. Source-record, public source URL, archive checksum, member, line, and presence lineage cover `100%`; `142,857` rows are elected; private findings are `0`. Independent full-row/schema/hash/natural-key/privacy validation passes. An unchanged run reuses `50/50` partitions through `50/50` hardlinks with zero rebuilds in `59.264696s`. Process peak RSS is `571.219 MB`.
- The non-linear gate generates `10,000,000` candidate occurrences directly into partitioned columnar storage, with no SQLite intermediate: `50` election-type/year partitions, `100` bounded Parquet files, and `1,078,764,475` bytes. Initial generation/export takes `353.975767s` (`28,250.517 rows/s`). Independent full-row validation passes in `455.928100s` (`21,933.283 rows/s`). Unchanged replay takes `288.620431s` (`34,647.580 rows/s`) and reuses `50/50` partitions plus `100/100` files by hardlink, with zero rebuilds or copies; its second full validation passes in `449.013877s` (`22,271.027 rows/s`). Process peak RSS is `620.137 MB`.
- Capacity evidence is deliberately synthetic and local: `real_coverage_claim=false`, `cross_election_identity_verified=false`, `restricted_source_fields_generated=false`, and nothing was published. The direct-columnar path closes local `S3` capacity, not real coverage. `S4` requires `100M`, partition-parallel validation, interruption recovery, cost evidence, durable publication, and clean-room restore.

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
- Privacy: DNI and birth dates absent from normalized/public artifacts; restricted raw objects never enter public packages.
- Identity: no cross-election merge is published without reviewed evidence; false merge/split and unresolved rates are measured.
- Scale: bounded memory and worker throughput measured on the complete real candidate corpus; actor/candidate lane reaches `S1` and progresses to `S2` or documents the smaller complete official universe.
- Higher scale: use the passed direct-columnar `10M` gate as the baseline; parallelize partition validation, then prove `100M` with bounded time/RSS/bytes/cost, interruption recovery, unchanged reuse, checksum verification, and clean-room restore before any `S4` claim.
- Publication: typed bounded partitions, manifest checksums, durable origin, independent validation, clean-room restore, and evidence drill-down all pass.

## Next action

No more blind retries this sprint. Obtain a new origin/access lever, then run exactly one queue worker item and compare the result against the recorded access failure before increasing throughput.
