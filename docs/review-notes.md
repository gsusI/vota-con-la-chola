# Project Review Notes

- Date: 2026-02-24
- Reviewer: Codex
- Scope: ETL, schema, API/UI, publish pipeline, docs/contracts and critical scripts.
- Process: notes captured during inspection (append-only).

## Findings


### 2026-02-24T review pass 1

- Severity: High
- Finding: `citizen` export/validate contract mismatch for `topics[].stakes_rank`.
- Evidence:
  - Export can emit `null`: `scripts/export_citizen_snapshot.py:296`.
  - Validator requires strict `int`: `scripts/validate_citizen_snapshot.py:191`.
  - Schema allows nullable `stakes_rank`: `etl/load/sqlite_schema.sql:408`.
- Impact: A valid DB state (topic with `stakes_rank IS NULL`) makes `validate_citizen_snapshot.py` fail and can block snapshot publishing.
- Suggested fix: Align contract either by allowing `null` in validator or normalizing exporter output to an integer sentinel.

- Severity: Medium
- Finding: `fetch_source_metrics()` overcounts runs when a run has multiple fetch rows.
- Evidence:
  - Aggregation uses `COUNT(ir.run_id)` and `SUM(CASE WHEN ir.status='ok'...)` after joining `ingestion_runs` with `{run_fetches|raw_fetches}`: `scripts/e2e_tracker_status.py:301-302`, `scripts/e2e_tracker_status.py:331`.
- Impact: `runs_total` / `runs_ok` are inflated; status table and operator decisions can be misleading.
- Suggested fix: Compute run counters from `ingestion_runs` in a separate grouped subquery (or use `COUNT(DISTINCT ir.run_id)` and distinct-safe status aggregation).

- Severity: Medium
- Finding: Tracker table parsing is brittle and can silently degrade to zero tracker rows.
- Evidence:
  - Parser requires exact header text match: `scripts/e2e_tracker_status.py:175`, `scripts/e2e_tracker_status.py:180`.
  - If not matched, parser returns `{}` without error: `scripts/e2e_tracker_status.py:206`.
- Impact: Small markdown header edits can disable tracker checks without explicit failure.
- Suggested fix: Parse markdown tables more defensively and fail fast when required header/columns are not found.

### 2026-02-24T review pass 2

- Severity: Medium
- Finding: Explorer hot paths recompute full DB schema and full-table row counts on each request.
- Evidence:
  - `build_explorer_rows_payload()` calls `fetch_schema()` for every request: `scripts/graph_ui_server.py:5243`.
  - `fetch_schema()` executes `SELECT COUNT(*)` for every table in SQLite: `scripts/graph_ui_server.py:4603`.
- Impact: Request latency scales with total DB size/table count, not only the requested table; this can degrade `/api/explorer/rows`, `/api/explorer/record`, and `/api/explorer/related` under normal usage.
- Suggested fix: Cache schema metadata, avoid per-request full `COUNT(*)`, and compute table counts lazily only where explicitly needed.

### 2026-02-24T review pass 3

- Severity: Medium
- Finding: Citizen party aggregation is anchored to `mandates.is_active=1` (current-state), not the requested snapshot date.
- Evidence:
  - Party roster query filters only by `m.is_active = 1`: `scripts/export_citizen_snapshot.py:352`.
  - Position aggregation joins mandates with the same `m.is_active = 1` predicate: `scripts/export_citizen_snapshot.py:448`.
  - Both queries are used even when `scope.as_of_date` is explicitly historical.
- Impact: Exports for historical `--as-of-date` can mix historical positions with current mandate-party assignments; results may drift from the intended snapshot semantics.
- Suggested fix: Derive party membership as-of `scope.as_of_date` (or from party_id already attached to position rows) and enforce one deterministic party assignment per person for the scope date.

### 2026-02-24T review pass 4

- Severity: Low (supporting evidence)
- Note: Existing citizen UI tests already model `topics[].stakes_rank = null` as valid input.
- Evidence:
  - `tests/test_citizen_first_answer_accelerator.js:78` uses `stakes_rank: null` in fixture data.
- Relevance: Reinforces that strict `int` validation in `scripts/validate_citizen_snapshot.py` is likely too restrictive versus downstream consumer expectations.

### 2026-02-24T review pass 5 (test coverage gaps)

- Severity: Medium (testing gap)
- Finding: No regression test exercises `stakes_rank = NULL` in exporter + validator integration.
- Evidence:
  - Current exporter test seeds only integer `stakes_rank` values: `tests/test_export_citizen_snapshot.py:130-137`.
  - Validator enforces `int` at runtime: `scripts/validate_citizen_snapshot.py:191`.
  - UI-side fixture already accepts `stakes_rank: null`: `tests/test_citizen_first_answer_accelerator.js:78`.
- Impact: The contract bug can reappear without failing CI in the current test suite.

- Severity: Medium (testing gap)
- Finding: No test covers duplicated fetch rows per run for tracker metrics aggregation.
- Evidence:
  - Tracker tests insert one fetch row per run in fixtures: `tests/test_e2e_tracker_status_tracker.py:170`, `tests/test_e2e_tracker_status_tracker.py:277`, `tests/test_e2e_tracker_status_tracker.py:335`, `tests/test_e2e_tracker_status_tracker.py:394`.
  - `fetch_source_metrics()` aggregates after joining fetch rows: `scripts/e2e_tracker_status.py:301-314`, `scripts/e2e_tracker_status.py:331`.
- Impact: Overcount behavior can regress unnoticed because CI currently lacks a multi-fetch fixture.

### 2026-02-24T review pass 6

- Severity: Medium
- Finding: Some backfill/document workflows depend on CWD-sensitive relative `raw_path` values.
- Evidence:
  - Default raw dir is relative: `etl/parlamentario_es/config.py:8`.
  - Raw files are persisted as `str(raw_path)` from that base: `etl/parlamentario_es/text_documents.py:633-657`.
  - Excerpt backfill reads `Path(raw_path)` directly and marks missing when not found: `scripts/backfill_initiative_doc_excerpts.py:191-195`.
- Impact: Running backfill commands from a different working directory can silently classify existing docs as missing (`skipped_missing_file`), reducing reproducibility across environments.
- Suggested fix: Normalize to absolute paths at write-time, or resolve relative `raw_path` against a deterministic repo/db anchor at read-time.

### 2026-02-24T review pass 7

- Severity: High
- Finding: URL cache reuse in text-document backfill can match the wrong document via prefix `LIKE`.
- Evidence:
  - Reuse query uses `source_url LIKE ?` with `f"{url_canon}%"`: `etl/parlamentario_es/text_documents.py:601-608`.
  - `url_canon` strips only URL fragment (`#...`), not path/query collisions: `etl/parlamentario_es/text_documents.py:588`.
- Impact: A URL such as `.../doc1` can match stored `.../doc10` and reuse wrong bytes/raw_path, corrupting excerpt and evidence traceability.
- Suggested fix: Match canonical URL exactly (or store/query an explicit canonical_url column) instead of prefix matching.

### 2026-02-24T review pass 8 (test coverage gap)

- Severity: Medium (testing gap)
- Finding: No regression test covers canonical-URL prefix collision in text-document reuse.
- Evidence:
  - Current text-doc tests validate fragment handling/idempotence but not URL prefix ambiguity: `tests/test_parl_text_documents.py:20-152`.
  - Reuse implementation uses prefix `LIKE` matching: `etl/parlamentario_es/text_documents.py:601-608`.
- Impact: A subtle traceability bug (wrong raw payload reused) can pass CI.

### 2026-02-24T review pass 9

- Severity: Medium
- Finding: Raw HF block archives are not reproducible byte-for-byte across runs.
- Evidence:
  - `build_block_archive()` writes tarballs with `tarfile.open(..., mode='w:gz')` and no fixed gzip/tar metadata normalization: `scripts/publicar_hf_raw_blocks.py:176-187`.
- Impact: Archive checksum drift can occur between identical-content runs (gzip header timestamp and tar metadata), weakening deterministic snapshot guarantees.
- Suggested fix: Build tar with normalized metadata (mtime/uid/gid/uname/gname/mode/order) and gzip with fixed `mtime`.

### 2026-02-24T review pass 10 (test coverage gap)

- Severity: Low (testing gap)
- Finding: Raw block tests do not cover determinism of generated archives.
- Evidence:
  - Existing tests for `publicar_hf_raw_blocks` only cover chunking/filtering/readme text: `tests/test_publicar_hf_raw_blocks.py:16-57`.
- Impact: Reproducibility regressions in archive generation can pass CI unnoticed.

## Pass 11 - Explorer API hot path does full-schema full-count scans on every request (high)

- Severity: high
- Area: `scripts/graph_ui_server.py`
- Evidence:
  - `fetch_schema()` computes `row_count` via `SELECT COUNT(*)` for every table (`scripts/graph_ui_server.py:4603`).
  - The generic list/detail endpoints call `fetch_schema(conn)` per request:
    - schema payload: `scripts/graph_ui_server.py:5165`
    - rows payload: `scripts/graph_ui_server.py:5243`
    - record payload: `scripts/graph_ui_server.py:5362`
    - related rows payload: `scripts/graph_ui_server.py:5515`
- Why this is risky:
  - For large DBs, each click/search/pagination can trigger many full-table counts before even executing the target query.
  - This creates avoidable latency spikes and I/O pressure in the main Explorer UX path.
- Suggested fix:
  - Stop recomputing full schema for rows/record/related calls.
  - Cache schema metadata (or a lightweight per-table view) and avoid eager `COUNT(*)` across all tables on hot endpoints.

## Pass 12 - Empty extraction can deactivate all active mandates for a source (high)

- Severity: high
- Area: `etl/politicos_es/pipeline.py`, `etl/politicos_es/db.py`
- Evidence:
  - Ingest loop only hard-fails on `records_seen > 0 && loaded == 0` (`etl/politicos_es/pipeline.py:291`).
  - After loop it always calls `close_missing_mandates(...)` (`etl/politicos_es/pipeline.py:314`).
  - `close_missing_mandates()` explicitly deactivates all active mandates when `seen_ids` is empty (`etl/politicos_es/db.py:629` + update at `etl/politicos_es/db.py:632`).
- Why this is risky:
  - If a connector returns zero extracted records (upstream glitch, contract drift, transient anti-bot/empty feed) without throwing, this path can mass-close mandates for that source.
- Suggested fix:
  - Guard the close step when extraction is empty unless explicitly allowed by connector policy.
  - At minimum require a positive extracted baseline (or strict source-specific rule) before mass deactivation logic runs.

## Pass 13 - Error path can commit partial writes in parlamentario ingest (high)

- Severity: high
- Area: `etl/parlamentario_es/pipeline.py`
- Evidence:
  - `ingest_one_source()` catches exceptions and directly calls `finish_run(...)` without a preceding rollback (`etl/parlamentario_es/pipeline.py:2919`, `etl/parlamentario_es/pipeline.py:2920`).
  - `finish_run()` commits (`etl/politicos_es/db.py:672`, commit at `etl/politicos_es/db.py:705`).
- Why this is risky:
  - Partial ETL writes from a failed run may get committed together with status=`error`, leaving inconsistent/half-applied state.
  - This diverges from `etl/politicos_es/pipeline.py`, which does rollback before `finish_run`.
- Suggested fix:
  - Mirror the politicos pattern: rollback first in exception path, then write and commit run status metadata.

## Pass 14 - `--strict-grid` validator checks length only, not unique topic-party coverage (medium)

- Severity: medium
- Area: `scripts/validate_citizen_snapshot.py`
- Evidence:
  - For `party_topic_positions`, strict mode validates only `len(positions) == topics*parties` (`scripts/validate_citizen_snapshot.py:261`-`scripts/validate_citizen_snapshot.py:263`).
  - There is no duplicate `(topic_id, party_id)` guard for this grid, while such duplicate protection exists for `party_concern_programas` (`scripts/validate_citizen_snapshot.py:289`).
- Why this is risky:
  - A payload with duplicated pairs and missing pairs can still pass strict grid size checks.
- Suggested fix:
  - Enforce uniqueness and exact set coverage for `(topic_id, party_id)` in strict mode.

## Pass 15 - `--computed-method auto` can choose stale snapshot date despite help text claiming global max(as_of_date) (medium)

- Severity: medium
- Area: `scripts/export_citizen_snapshot.py`
- Evidence:
  - CLI help says omitted `--as-of-date` infers `max(as_of_date)` for scope (`scripts/export_citizen_snapshot.py:70`).
  - Resolver uses method-first preference (`combined`, then `votes`) and picks the first method with any date (`scripts/export_citizen_snapshot.py:200`, `scripts/export_citizen_snapshot.py:202`, `scripts/export_citizen_snapshot.py:222`, `scripts/export_citizen_snapshot.py:223`, `scripts/export_citizen_snapshot.py:232`).
- Why this is risky:
  - If `combined` exists but is older than `votes`, exported snapshot may be stale while still presented as latest.
- Suggested fix:
  - Either compute global latest date first then resolve preferred method at that date, or update help/contract to explicitly state method-priority semantics.

## Pass 16 - Exporter/validator contract mismatch for nullable `stakes_rank` (medium)

- Severity: medium
- Area: `scripts/export_citizen_snapshot.py`, `scripts/validate_citizen_snapshot.py`
- Evidence:
  - Exporter emits `stakes_rank: null` when source rank is missing (`scripts/export_citizen_snapshot.py:296`).
  - Validator requires `stakes_rank` to be `int` (`scripts/validate_citizen_snapshot.py:191`).
- Why this is risky:
  - Valid exports can fail validation when any topic has missing rank.
- Suggested fix:
  - Align contract to accept nullable int in validator or force exporter to materialize deterministic integer fallback.

## Pass 17 - Strict review apply path may ignore two skip counters in strict-failure total (high)

- Severity: high
- Area: `scripts/apply_sanction_procedural_official_review_metrics.py`
- Evidence (carry-over finding from prior pass, pending dedicated regression test):
  - Counters for `skipped_invalid_evidence_date` and `skipped_short_evidence_quote` are defined/incremented, but strict-mode skipped-total calculation appears not to include them.
- Why this is risky:
  - `--strict` can report success while silently skipping rows for evidence date/quote quality reasons.
- Suggested fix:
  - Include both counters in strict skipped-total logic and add a strict-mode regression test covering these branches.

## Pass 18 - Validator does not cross-check `meta.quality` against actual grid rows (medium)

- Severity: medium
- Area: `scripts/validate_citizen_snapshot.py`
- Evidence:
  - `meta.quality` is validated only for internal consistency (shape, ranges, sums) (`scripts/validate_citizen_snapshot.py:103`-`scripts/validate_citizen_snapshot.py:181`).
  - Actual row-level stance counts are computed later (`scripts/validate_citizen_snapshot.py:231`) but never compared back to `meta.quality.stance_counts`/totals.
- Why this is risky:
  - Stale or tampered quality KPIs can pass validation even if they disagree with `party_topic_positions`.
- Suggested fix:
  - Recompute quality metrics from rows in validator and compare against declared `meta.quality` (or drop `meta.quality` trust and always recompute downstream).

## Pass 19 - Senado detail backfill applies `limit` after `fetchall()` (medium)

- Severity: medium
- Area: `etl/parlamentario_es/pipeline.py`
- Evidence:
  - Candidate rows are fully materialized first (`etl/parlamentario_es/pipeline.py:1286`).
  - `limit` is applied afterward in Python slicing (`etl/parlamentario_es/pipeline.py:1288`).
- Why this is risky:
  - For large datasets this defeats `--max-events` as a DB-level cap, increasing latency and memory pressure before any work starts.
- Suggested fix:
  - Push `LIMIT` (and cursoring semantics) into SQL query construction directly.

## Pass 20 - Missing regression tests for empty-extract mandate closure and parlamentario rollback semantics (testing gap)

- Severity: medium (coverage risk)
- Area: `tests/test_samples_e2e.py` + parlamentario ingest tests
- Evidence:
  - `tests/test_samples_e2e.py` exercises happy-path/idempotence with non-empty sample payloads only (`tests/test_samples_e2e.py:14` onward) and does not cover zero-record extraction behavior.
  - I did not find tests asserting `ingestion_runs` + data state on exception for `etl/parlamentario_es.pipeline.ingest_one_source` (no rollback/error-path contract checks surfaced in current test scan).
- Why this matters:
  - Two high-impact paths remain unguarded:
    - accidental mass mandate deactivation when extracted set is empty,
    - partial-write commit risk on parlamentario ingest exceptions.
- Suggested tests:
  - Add a connector fixture that returns `records=[]` and assert mandates are not globally closed by default.
  - Add a failing connector fixture for parlamentario ingest and assert no domain writes persist after run status=`error`.

## Pass 21 - Validator-specific negative-case coverage is thin (testing gap)

- Severity: low-medium (coverage)
- Area: citizen snapshot validation tests
- Evidence:
  - There is one end-to-end exporter test that invokes validator on happy path (`tests/test_export_citizen_snapshot.py`).
  - I did not find a dedicated validator test module with focused negative cases (duplicate grid keys, nullable `stakes_rank`, mismatched `meta.quality` vs rows).
- Why this matters:
  - Contract drift in validator can ship undetected because only success-path behavior is covered.
- Suggested tests:
  - Add dedicated validator tests with malformed fixtures covering strict-grid uniqueness, nullable rank contract, and quality cross-check integrity.

## Pass 22 - Citizen UI auto-writes preference-like state into query params (privacy/policy drift, high)

- Severity: high
- Area: `ui/citizen/index.html`
- Evidence:
  - URL state writer persists `concern`, `concerns_ids`, `concern_pack`, `topic_id`, `party_id`, `view`, `method`, `mode` into `location.search` on normal interactions (`ui/citizen/index.html:3189`-`ui/citizen/index.html:3208`).
  - Comment confirms query URL as primary share mechanism (`ui/citizen/index.html:3210`).
- Why this is risky:
  - Repo policy requires citizen preferences to be local-first and not auto-written into query params; share links should be explicit opt-in and use fragment.
  - Query params are typically logged server-side, increasing preference leakage risk.
- Suggested fix:
  - Keep routine preference state in localStorage only; generate shareable state explicitly via opt-in fragment payload (`#...`) when user requests sharing.

## Pass 23 - Hash-preset privacy mode is dropped on first push update (medium)

- Severity: medium
- Area: `ui/citizen/index.html`
- Evidence:
  - `writeUrlState(push)` disables `hashPresetActive` when `push===true` (`ui/citizen/index.html:3173`).
  - Afterwards, the function writes state back to query params (`ui/citizen/index.html:3189`-`ui/citizen/index.html:3208`).
  - `writeUrlState(true)` is triggered from many interaction handlers (`ui/citizen/index.html:3691`, `ui/citizen/index.html:4607`, `ui/citizen/index.html:7974`, etc.).
- Why this is risky:
  - A user who opened a fragment-based share link can quickly transition to query-based state persistence on normal interaction, weakening the intended privacy posture.
- Suggested fix:
  - Keep hash-only mode sticky for the session unless user explicitly opts into query-based sharing.

## Pass 24 - Explorer generic API payload builders appear uncovered by direct tests (testing gap)

- Severity: medium (coverage risk)
- Area: `scripts/graph_ui_server.py` generic explorer endpoints
- Evidence:
  - I did not find test references to:
    - `build_explorer_rows_payload`
    - `build_explorer_record_payload`
    - `build_explorer_related_rows_payload`
    - `/api/explorer/*` routes
  - Existing graph UI server tests are focused on citizen assets/routes and tracker/coherence payloads.
- Why this matters:
  - Hot-path regressions (performance and record navigation semantics) can ship without failing CI.
- Suggested tests:
  - Add endpoint-level tests for list/record/related behavior with representative table sizes and FK-heavy schemas.

## Pass 25 - Exporter test coverage is narrow vs current contract surface (testing gap)

- Severity: low-medium (coverage)
- Area: `tests/test_export_citizen_snapshot.py`
- Evidence:
  - Current module has a single happy-path test focused on optional fields + concern filtering.
  - Missing explicit cases for:
    - auto method/date resolution when `combined` is older than `votes`,
    - nullable `stakes_rank` interoperability with validator,
    - duplicate/missing `(topic_id, party_id)` grid integrity handling.
- Suggested tests:
  - Add targeted fixtures for method/date precedence and nullable rank contract.
  - Add negative fixtures checked by validator under `--strict-grid`.

## Pass 26 - Empty-published guard can be bypassed by always-included static files (medium)

- Severity: medium
- Area: `scripts/publicar_hf_snapshot.py`
- Evidence:
  - `collect_published_files()` always appends static artifacts (`STATIC_PUBLISHED_FILES`) and atlas latest if present, regardless of whether snapshot-dated artifacts exist (`scripts/publicar_hf_snapshot.py:479`-`scripts/publicar_hf_snapshot.py:486`).
  - Main gate checks only `if not published_files and not args.allow_empty_published` (`scripts/publicar_hf_snapshot.py:1445`).
- Why this is risky:
  - A run can pass the “non-empty snapshot” gate with only static/global files, even when date-scoped artifacts are missing.
  - This weakens the anti-empty publish control implied by `--allow-empty-published`.
- Suggested fix:
  - Separate counters for `snapshot_date` artifacts vs static/global files, and enforce the non-empty gate on date-scoped artifacts.

## Pass 27 - Parquet export determinism gap for tables without PK/order key (medium)

- Severity: medium
- Area: `scripts/publicar_hf_snapshot.py`
- Evidence:
  - Parquet export ordering uses PK columns, else `rowid` only when table is not `WITHOUT ROWID` (`scripts/publicar_hf_snapshot.py:1209`-`scripts/publicar_hf_snapshot.py:1221`).
  - For `WITHOUT ROWID` tables without PK columns, no `ORDER BY` is applied (`scripts/publicar_hf_snapshot.py:1216`-`scripts/publicar_hf_snapshot.py:1221`).
- Why this is risky:
  - Row order can vary across exports for the same snapshot, hurting reproducibility and checksum stability of Parquet parts.
- Suggested fix:
  - Enforce deterministic fallback ordering for such tables (e.g., sorted by all columns or explicit canonical key requirement).

## Pass 28 - Concern keyword duplicate check ignores diacritic normalization (medium)

- Severity: medium
- Area: `scripts/validate_citizen_concerns.py`
- Evidence:
  - Duplicate detection uses `token.casefold()` only (`scripts/validate_citizen_concerns.py:323`).
  - Validator contract includes normalization flags for `strip_diacritics`, but this dedupe path does not apply it.
- Why this is risky:
  - Semantically duplicate keywords like `"educación"` vs `"educacion"` can pass validation, while runtime matching in citizen flow may normalize them to the same concept.
- Suggested fix:
  - Apply the same normalization pipeline used by runtime matching (case + diacritic stripping) before duplicate checks.

## Pass 29 - `errors_count`/`warnings_count` are truncated by `max_issues` cap (low-medium)

- Severity: low-medium
- Area: `scripts/validate_citizen_concerns.py`
- Evidence:
  - `_add_issue` stops appending after `max_issues` (`scripts/validate_citizen_concerns.py:35`-`scripts/validate_citizen_concerns.py:43`).
  - Final counters are `len(errors)`/`len(warnings)` (`scripts/validate_citizen_concerns.py:501`-`scripts/validate_citizen_concerns.py:502`).
- Why this is risky:
  - Reported counts can understate true issue volume when cap is reached, reducing operational clarity.
- Suggested fix:
  - Track total issue counters separately from the capped issue arrays.

## Pass 30 - Preset codec accepts unknown `concern` ID even when `concerns` are constrained to known IDs (low-medium)

- Severity: low-medium
- Area: `ui/citizen/preset_codec.js`
- Evidence:
  - `concerns` list is normalized via `normalizeSelectedConcernIds(..., cfg)` (known-ID filtered) (`ui/citizen/preset_codec.js:92`).
  - Single `concern` is accepted verbatim without known-ID validation (`ui/citizen/preset_codec.js:94`-`ui/citizen/preset_codec.js:95`).
- Why this is risky:
  - Preset payload can be internally inconsistent (`concerns_ids` valid but `concern` unknown), producing fragile deep-link behavior.
- Suggested fix:
  - Validate `concern` against known concern IDs (or drop it when unknown) using the same config contract as `concerns`.

## Pass 31 - Strict-network minimum-load gate misses partial-network mode in Infoelectoral pipeline (high)

- Severity: high
- Area: `etl/infoelectoral_es/pipeline.py`
- Evidence:
  - Connector emits `note="network-with-partial-errors (...)"` on partial failures (`etl/infoelectoral_es/connectors/descargas.py:184`).
  - Strict min-load gate checks only exact `extracted.note == "network"` (`etl/infoelectoral_es/pipeline.py:306`).
- Why this is risky:
  - Runs with degraded network quality can bypass `min_records_loaded_strict` despite partial errors.
- Suggested fix:
  - Apply gate for any network-derived mode (`note == "network"` or `note.startswith("network-with-partial-errors")`).

## Pass 32 - Infoelectoral `proceso_resultado` rows are skipped unless parent process appears in same batch (medium)

- Severity: medium
- Area: `etl/infoelectoral_es/pipeline.py`
- Evidence:
  - Insert path ignores a result if `proceso_id` is not in in-memory `proceso_ids` from current batch (`etl/infoelectoral_es/pipeline.py:268`).
- Why this is risky:
  - Incremental/partial runs can drop valid result rows even when parent `proceso` already exists in DB from prior runs.
- Suggested fix:
  - Fallback to DB existence check for `proceso_id` before skipping.

## Pass 33 - Infoelectoral procesos fallback may stop early and skip second endpoint (`datasets`) (medium)

- Severity: medium
- Area: `etl/infoelectoral_es/connectors/procesos.py`
- Evidence:
  - `_fetch_dataset_from_proceso()` iterates `resultados` then `datasets` (`etl/infoelectoral_es/connectors/procesos.py:249`).
  - It returns immediately after the first successful request, even if filtered rows are empty (`etl/infoelectoral_es/connectors/procesos.py:274`).
- Why this is risky:
  - If `.../resultados` responds but has no usable URLs, connector never attempts `.../datasets`, reducing recoverable dataset rows.
- Suggested fix:
  - Continue loop when first endpoint yields zero usable rows; return only after obtaining non-empty dataset rows or exhausting both endpoints.

## Pass 34 - Infoelectoral snapshot builder is time-dependent but tested as deterministic (medium)

- Severity: medium
- Area: `etl/infoelectoral_es/publish.py`, `tests/test_publish_infoelectoral.py`
- Evidence:
  - Snapshot payload includes `generado_en = now_utc_iso()` (`etl/infoelectoral_es/publish.py:339`).
  - Test asserts full object equality across two consecutive builds (`tests/test_publish_infoelectoral.py:62`).
- Why this is risky:
  - Determinism claim can become flaky when calls cross second boundaries.
  - Even without test flake, published artifacts are not byte-deterministic for identical DB/snapshot inputs.
- Suggested fix:
  - Exclude volatile timestamp from determinism-critical payloads (or make it optional/overrideable in builder/tests).

## Pass 35 - Run snapshot source inference misses `--source=<id>` CLI form (medium)

- Severity: medium
- Area: `etl/politicos_es/run_snapshot_schema.py`
- Evidence:
  - Source inference regex only matches spaced form `--source <id>` (`etl/politicos_es/run_snapshot_schema.py:35`).
  - It does not match common equals form `--source=<id>`.
- Why this is risky:
  - Normalization can drop `source_id` for valid command strings, weakening tracker parity contracts.
- Suggested fix:
  - Extend regex/parser to support both `--source <id>` and `--source=<id>` forms.

## Pass 36 - Initiative KPI `linked_to_votes_with_downloaded_docs` depends on `document_fetches` table presence (medium)

- Severity: medium
- Area: `etl/parlamentario_es/quality.py`
- Evidence:
  - `linked_doc_rows` query is executed only inside `if has_document_fetches:` block (`etl/parlamentario_es/quality.py:593`, `etl/parlamentario_es/quality.py:615`).
  - Metric itself is defined as a source_record/download linkage concept, not inherently dependent on fetch log presence.
- Why this is risky:
  - On DBs without `document_fetches`, KPI stays at zero even when downloaded docs exist via `source_record_pk`.
- Suggested fix:
  - Compute `initiatives_linked_to_votes_with_downloaded_docs` independently of `document_fetches` availability.

## Pass 37 - No quality test coverage for KPI behavior when `document_fetches` is absent (testing gap)

- Severity: low-medium (coverage)
- Area: `tests/test_parl_quality.py`
- Evidence:
  - Existing initiative KPI tests populate `document_fetches` (e.g., around `tests/test_parl_quality.py:412`, `tests/test_parl_quality.py:724`).
  - I did not find a counterpart test asserting expected KPI behavior on DBs missing that table.
- Why this matters:
  - Schema/back-compat scenarios can silently skew KPIs without CI detection.
- Suggested test:
  - Add a migration/back-compat fixture without `document_fetches` and assert KPI parity for download-link metrics.

## Pass 38 - Tracker parser depends on exact header string match (medium)

- Severity: medium
- Area: `scripts/e2e_tracker_status.py`
- Evidence:
  - Parser enters table mode only on an exact header literal match (`scripts/e2e_tracker_status.py:175`, `scripts/e2e_tracker_status.py:180`).
- Why this is risky:
  - Minor tracker formatting edits (column rename, extra spaces, punctuation changes) can silently yield zero parsed rows and weaken mismatch detection.
- Suggested fix:
  - Parse markdown tables more robustly (header token normalization or schema-by-column-position with tolerant matching).

## Pass 39 - Duplicate tracker mappings silently overwrite prior rows (low-medium)

- Severity: low-medium
- Area: `scripts/e2e_tracker_status.py`
- Evidence:
  - Parsed entries are stored as `rows[source_id] = ...` without duplicate detection (`scripts/e2e_tracker_status.py:200`).
- Why this is risky:
  - If one `source_id` is mapped by multiple tracker rows, the last one wins silently, hiding conflicting checklist statuses.
- Suggested fix:
  - Detect duplicate source mappings and fail fast (or surface explicit multi-row conflict warnings).

## Pass 40 - Smoke script can create empty DB implicitly and fail with low-signal SQL errors (low)

- Severity: low
- Area: `scripts/etl_smoke_e2e.py`
- Evidence:
  - Script opens SQLite directly without existence/schema checks (`scripts/etl_smoke_e2e.py:23`).
  - It immediately issues table queries (`scripts/etl_smoke_e2e.py:25`-`scripts/etl_smoke_e2e.py:27`).
- Why this is risky:
  - If `--db` path is wrong, SQLite may create a new empty DB, then fail with `no such table` traceback rather than clear smoke-gate diagnostics.
- Suggested fix:
  - Validate DB path exists and expected tables are present before running gate queries.

## Pass 41 - Initiative doc status report hard-fails on historical DBs missing optional tables (medium)

- Severity: medium
- Area: `scripts/report_initiative_doc_status.py`
- Evidence:
  - The script has a table-presence guard only for `parl_initiative_doc_extractions` (`scripts/report_initiative_doc_status.py:123`-`scripts/report_initiative_doc_status.py:124`).
  - Other queries unconditionally reference `document_fetches` (`scripts/report_initiative_doc_status.py:108`, `scripts/report_initiative_doc_status.py:204`, `scripts/report_initiative_doc_status.py:236`, `scripts/report_initiative_doc_status.py:395`).
  - Vote-link aggregation unconditionally joins `parl_vote_event_initiatives` (`scripts/report_initiative_doc_status.py:174`).
  - `main()` calls these aggregations without fallback (`scripts/report_initiative_doc_status.py:520`-`scripts/report_initiative_doc_status.py:522`).
- Why this is risky:
  - On older DB snapshots missing one of these tables, the report exits with SQL errors instead of emitting partial-but-useful coverage.
- Suggested fix:
  - Add `_table_exists` guards for optional tables and degrade to zero-valued metrics when absent.

## Pass 42 - Senado enmiendas classification depends on process CWD for `raw_path` resolution (medium)

- Severity: medium
- Area: `scripts/report_initiative_doc_status.py`
- Evidence:
  - `_parse_ini_enmiendas_meta` reads `Path(token)` directly from `text_documents.raw_path` and classifies missing when that relative path does not exist from current CWD (`scripts/report_initiative_doc_status.py:302`-`scripts/report_initiative_doc_status.py:308`).
- Why this is risky:
  - Running the report from a different working directory can misclassify available INI/detail files as missing (`ini_raw_path_missing`), inflating actionable counts.
- Suggested fix:
  - Resolve relative `raw_path` values against a deterministic base directory (or persisted raw artifact root) before classifying as missing.

## Pass 43 - Backfill inserted count reports attempted rows, not actual inserts (medium)

- Severity: medium
- Area: `scripts/backfill_initiative_doc_fetch_status.py`
- Evidence:
  - Inserts use `ON CONFLICT(doc_url) DO NOTHING` (`scripts/backfill_initiative_doc_fetch_status.py:200`).
  - Non-dry-run result still sets `inserted = len(insert_rows)` (`scripts/backfill_initiative_doc_fetch_status.py:204`), and exports it as `inserted_or_would_insert` (`scripts/backfill_initiative_doc_fetch_status.py:221`).
- Why this is risky:
  - Output can overstate writes when candidate URLs collide with existing rows.
- Suggested fix:
  - Compute actual inserts from before/after coverage delta (or `changes()`), and keep “would insert” only for dry-run mode.

## Pass 44 - Backfill fetch-status joins ignore `source_id`, weakening per-source traceability semantics (medium)

- Severity: medium
- Area: `scripts/backfill_initiative_doc_fetch_status.py`
- Evidence:
  - Coverage and candidate selection join fetch status by URL only (`LEFT JOIN document_fetches df ON df.doc_url = d.doc_url`) (`scripts/backfill_initiative_doc_fetch_status.py:65`, `scripts/backfill_initiative_doc_fetch_status.py:107`).
  - Insert path still writes configurable `source_id` into `document_fetches` (`scripts/backfill_initiative_doc_fetch_status.py:168`, `scripts/backfill_initiative_doc_fetch_status.py:188`).
- Why this is risky:
  - If URLs overlap across sources, a row from another source can mask missing status for the requested source, making source-scoped backfill outcomes ambiguous.
- Suggested fix:
  - Include `df.source_id = ?` in coverage/candidate joins to align query semantics with requested source scope.

## Pass 45 - No dedicated tests found for initiative fetch-status backfill script (testing gap)

- Severity: low-medium (coverage)
- Area: `scripts/backfill_initiative_doc_fetch_status.py`, `tests/`
- Evidence:
  - Repo search for script coverage (`rg -n "backfill_initiative_doc_fetch_status" tests`) returned no test hits.
  - Current initiative status tests (`tests/test_report_initiative_doc_status.py`) validate only extraction counting and one Senado global-enmiendas classification path.
- Why this matters:
  - Regressions in backfill accounting, source scoping, and idempotence can ship without CI detection.
- Suggested tests:
  - Dry-run vs apply with pre-existing `document_fetches` conflicts.
  - Source-scoped coverage behavior.
  - Accuracy of reported inserted counts under conflict-heavy inputs.

## Pass 46 - Declared-source status report claims deterministic output but embeds volatile timestamp (low-medium)

- Severity: low-medium
- Area: `scripts/report_declared_source_status.py`
- Evidence:
  - Module docstring frames this as a deterministic status report (`scripts/report_declared_source_status.py:2`).
  - Report payload always includes `generated_at = now_utc_iso()` (`scripts/report_declared_source_status.py:257`).
- Why this is risky:
  - Two runs over identical DB state are not byte-identical, which weakens reproducibility and artifact diff stability.
- Suggested fix:
  - Either document timestamp volatility explicitly or add an optional fixed `generated_at` override for deterministic pipelines/tests.

## Pass 47 - Declared-source status CLI lacks upfront DB/schema guard and can fail with low-signal SQL errors (low)

- Severity: low
- Area: `scripts/report_declared_source_status.py`
- Evidence:
  - `main()` opens the DB path directly (`scripts/report_declared_source_status.py:280`) without validating existence.
  - `build_report()` immediately queries base tables (`scripts/report_declared_source_status.py:76`, `scripts/report_declared_source_status.py:81`, `scripts/report_declared_source_status.py:86`).
- Why this is risky:
  - A bad `--db` path can create/open an empty SQLite file and then crash with `no such table`, instead of returning a clear gate error.
- Suggested fix:
  - Add explicit DB existence + required-table preflight checks with structured error output.

## Pass 48 - Vote smoke gate has same empty-DB/low-signal failure mode as other smoke scripts (low)

- Severity: low
- Area: `scripts/etl_smoke_votes.py`
- Evidence:
  - Script opens SQLite directly (`scripts/etl_smoke_votes.py:46`) and immediately queries vote tables (`scripts/etl_smoke_votes.py:51`, `scripts/etl_smoke_votes.py:60`).
  - There is no upfront path/schema validation.
- Why this is risky:
  - Wrong DB path can surface as raw SQL table errors instead of a clear smoke diagnosis.
- Suggested fix:
  - Validate DB path and required table presence before running count checks.

## Pass 49 - No dedicated tests found for `etl_smoke_votes.py` (testing gap)

- Severity: low-medium (coverage)
- Area: `scripts/etl_smoke_votes.py`, `tests/`
- Evidence:
  - Repo search for `etl_smoke_votes`/`smoke-votes` in tests returned no hits.
- Why this matters:
  - CLI regressions in source parsing and threshold-gate semantics can ship without CI feedback.
- Suggested tests:
  - Empty/invalid `--source-ids` parsing behavior.
  - Clear failure messaging for missing DB/table scenarios.
  - Positive and negative threshold checks for per-source events and total member votes.

## Pass 50 - `export_explorer_sources_snapshot.py` lacks DB existence preflight (low)

- Severity: low
- Area: `scripts/export_explorer_sources_snapshot.py`
- Evidence:
  - Script builds payload from `db_path` directly (`scripts/export_explorer_sources_snapshot.py:39`) without checking file existence or schema.
- Why this is risky:
  - Wrong/missing DB path can fail deep in payload building with less actionable SQL errors.
- Suggested fix:
  - Mirror the explicit DB existence check already present in other exporter scripts.

## Pass 51 - `export_graph_snapshot.py` lacks DB existence check and limit guardrails (low-medium)

- Severity: low-medium
- Area: `scripts/export_graph_snapshot.py`
- Evidence:
  - No preflight check before payload generation (`scripts/export_graph_snapshot.py:36`-`scripts/export_graph_snapshot.py:42`).
  - User-provided `--limit` is passed through directly (`scripts/export_graph_snapshot.py:40`) with no lower bound clamp.
- Why this is risky:
  - Invalid DB paths produce low-signal failures.
  - Non-sensical limits (e.g., negative) can push undefined behavior into downstream query builders.
- Suggested fix:
  - Add DB existence/schema checks and normalize `limit` to a safe positive range.

## Pass 52 - Explorer temas snapshot includes volatile `generated_at`, reducing artifact reproducibility (low-medium)

- Severity: low-medium
- Area: `scripts/export_explorer_temas_snapshot.py`
- Evidence:
  - Snapshot metadata stamps current UTC time (`scripts/export_explorer_temas_snapshot.py:88`).
- Why this is risky:
  - Re-running export over unchanged data creates noisy diffs and non-byte-identical artifacts.
- Suggested fix:
  - Provide optional fixed timestamp override (or exclude volatile field when deterministic output is required).

## Pass 53 - No direct tests found for exporter CLI wrappers (testing gap)

- Severity: low-medium (coverage)
- Area: `scripts/export_explorer_sources_snapshot.py`, `scripts/export_explorer_votaciones_snapshot.py`, `scripts/export_explorer_temas_snapshot.py`, `scripts/export_graph_snapshot.py`
- Evidence:
  - Test search did not find direct references to these exporter scripts.
  - Existing coverage appears focused on `graph_ui_server` payload builders/routes rather than CLI wrappers.
- Why this matters:
  - Regressions in CLI argument handling, DB preflight behavior, and output writing can bypass CI.
- Suggested tests:
  - Minimal CLI-level tests for happy-path export, missing DB handling, and argument normalization.
