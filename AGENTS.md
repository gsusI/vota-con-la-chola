# Agent Operating Notes

This repo is intentionally ultra-lean. When expanding ETL/schema/UI, optimize for:
- Reproducibility (single SQLite file, deterministic-ish results per snapshot date)
- Traceability (raw payloads and sources)
- Fast ingestion (avoid N+1 DB roundtrips)
- Schema-driven navigation (Explorer UI should work as schema/data evolve)

## Execution Philosophy (KISS + Delivery)

### Documentation Philosophy
- One source of truth per layer:
  - Strategy and destination: `docs/roadmap.md`
  - Near-term execution: `docs/roadmap-tecnico.md`
  - Operational backlog and real status: `docs/etl/e2e-scrape-load-tracker.md`
  - Public accountability log for blocked access to public data: `docs/etl/name-and-shame-access-blockers.md`
- Do not duplicate roadmaps in random docs. Link instead of copy.
- Every non-trivial change must answer three questions in docs or tracker:
  - where we are now
  - where we are going
  - what is next
- Keep docs lean and operational:
  - decisions, constraints, commands, DoD
  - avoid long narrative that does not change implementation choices

### Structuring Complexity
- Build in thin vertical slices, not big-bang layers.
- Keep boundaries explicit:
  - ingest (raw + traceability)
  - normalize (ids + FKs)
  - enrich (topic/action semantics)
  - aggregate (positions/vectors)
  - publish (snapshot + KPIs)
  - UI/API (drill-down to evidence)
- Prefer additive schema evolution (new tables/columns/indexes) over rewrites.
- Keep manual work explicit and bounded (codebook, arbitration, intervention definition). Never hide it behind fake automation.
- Preserve explainability by default:
  - every score/position should be traceable to evidence rows
  - uncertainty and "no_signal" are valid outputs

### Get-Shit-Done Operating Loop
- Ship the smallest useful slice that improves user-visible truth.
- For each slice:
  - define the gate (quality KPI or integrity check)
  - implement end-to-end
  - publish snapshot/artifact
  - update tracker/roadmap status
- Prefer "boring and reliable" over clever and fragile.
- If blocked (WAF, broken upstream, missing contract), do not fake DONE:
  - record evidence of the block
  - mark status honestly
  - move to next highest-leverage task
- Finish before expanding scope: close loops (`pending -> resolved/ignored`) before opening new surfaces.

### Name & Shame Protocol (Public-Data Access Obstruction)
- Policy basis: this project treats official public-data blocking against transparency obligations as a democratic accountability incident.
- Every confirmed blocking case MUST be recorded in `docs/etl/name-and-shame-access-blockers.md`.
- Required evidence for each incident:
  - organism/institution name and source/endpoint URL
  - first/last seen timestamps (UTC)
  - exact reproducible command used (prefer `--strict-network`)
  - machine-verifiable failure signal (`HTTP 403`, `cf-mitigated: challenge`, anti-bot HTML, persistent timeout pattern)
  - links to immutable evidence artifacts (logs/reports under `docs/etl/sprints/*/evidence` or equivalent)
  - impacted tracker row(s) in `docs/etl/e2e-scrape-load-tracker.md`
  - explicit next escalation action
- Editorial rule:
  - Name institutions clearly, but keep entries factual and evidence-first.
  - No insults, speculation, or motive claims beyond what evidence supports.
  - Append-only history; if resolved, mark resolution with proof and keep the original incident visible.

## Project Skills

- MTurk manual review workflow: `skills/mturk-review-loop/SKILL.md`
- Use this skill for batch prep/apply/progress on `topic_evidence_reviews` (`congreso_intervenciones`).

## Working Agreement

### Source Of Truth
- SQLite schema lives in `etl/load/sqlite_schema.sql`.
- ETL entrypoint is `scripts/ingestar_politicos_es.py`.
- UI server is `scripts/graph_ui_server.py`.
- Explorer UI is `ui/graph/explorer.html`.

### Schema Evolution Rules (SQLite)
- Prefer additive changes: new tables, new columns, new indexes.
- Avoid destructive migrations (dropping columns/tables) unless explicitly requested.
- Every table that should be navigable in Explorer MUST have:
  - A stable identity: single-column `PRIMARY KEY` is best.
  - If no PK, it will fall back to `rowid` (works only if table is not `WITHOUT ROWID`).
  - Tables `WITHOUT ROWID` without PK are not drill-down navigable.

### Relationship Rules (Explorer Compatibility)
Explorer relations are inferred from SQLite FK metadata (`PRAGMA foreign_key_list`).
- Declare FK constraints in the schema.
- Prefer single-column FKs pointing to single-column PKs for best UX.
  - This enables batched FK label resolution in list views.
- Use consistent naming:
  - `*_id` for FK columns.

## ETL Performance Rules

### Hot Path: Ingest
Ingestion must remain fast even as normalization expands.
- Avoid per-record DB lookups.
- Use in-memory caches for dimension upserts during a single `ingest_one_source` run.
  - Implemented caches include admin levels, roles, territories, genders, parties, institutions, persons, source_records.
- Use idempotent upserts (`INSERT ... ON CONFLICT DO UPDATE`) and keep them simple.

### Heavy Work: Backfill
Do not run full-table backfills inside the normal `ingest` command.
- Historical normalization/backfills are triggered explicitly via:
  - `python3 scripts/ingestar_politicos_es.py backfill-normalized --db <path>`
  - or `just etl-backfill-normalized`

This keeps the regular ETL runs quick.

### Migrations On Existing DBs
Old DBs may be missing columns that new schema indexes reference.
- `apply_schema()` is responsible for forward-compat:
  - It retries the schema script after adding missing columns.
  - `ensure_schema_compat()` performs additive `ALTER TABLE ... ADD COLUMN ...`.

## Normalization Model (Current)
The schema includes normalized dimension tables to support Wikidata-like navigation:
- `territories` and `*_territory_id` columns
- `roles` and `mandates.role_id`
- `admin_levels` and `*.admin_level_id`
- `genders` and `persons.gender_id`
- `source_records` and `mandates.source_record_pk`
- `party_aliases` for party name variance

When adding new data, prefer normalized FK columns + keep the original denormalized text columns for backward compatibility.

## Explorer UI Expectations

### Human-Friendly Labels
The Explorer UI relies on backend label inference.
- Backend label candidates are configured via `LABEL_COLUMN_CANDIDATES` in `scripts/graph_ui_server.py`.
- If you add a new major entity table, make sure it has a good label column:
  - Prefer `name` / `full_name` / `title` / `label`.

### List Views: FK Label Resolution
For table lists and 1:n relation lists, the backend returns:
- `preview`: raw preview fields
- `preview_display`: same shape, but FK-ish fields resolved to human-friendly labels when possible

Rules for best out-of-the-box display:
- Define FK constraints.
- Prefer single-column FKs -> single-column PKs.
- Ensure referenced tables have a label column.

### 1:n Relationships
Explorer supports expandable 1:n lists via:
- `/api/explorer/related?table=<t>&col=<c>&val=<v>...`

This returns paginated rows with identities, labels, and previews.

### Browser Navigation
Explorer uses `history.pushState` / `popstate`.
- When changing table, paging, searching, or opening a record, update history exactly once.
- Breadcrumb route segments are clickable and should restore state without extra pushes.

## Data Quality Gates (Pragmatic)
- `PRAGMA foreign_key_check` should return no rows after ETL runs.
- For each ingested source, `records_loaded` should be non-zero in `ingestion_runs`.
- Prefer emitting normalized FK ids where possible (but allow NULL when upstream data lacks a usable key).

## Politicos ES ETL (Connector Learnings)

### How To Run (Reproducible)
- Use Docker + `justfile` recipes; avoid relying on host Python env.
- Key env vars:
  - `DB_PATH` (defaults to `etl/data/staging/politicos-es.db`)
  - `SNAPSHOT_DATE` (defaults to `2026-02-12`)
- Canonical E2E:
  - `DB_PATH=etl/data/staging/politicos-es.e2e19.db SNAPSHOT_DATE=2026-02-12 just etl-e2e`
- Tracker gate (SQL vs checklist):
  - `DB_PATH=etl/data/staging/politicos-es.e2e19.db just etl-tracker-status`

### Public Snapshot Distribution (Hugging Face)
- Public data mirror lives in Hugging Face Datasets (free/public access for collaborators).
- Credentials are loaded from `.env`:
  - `HF_TOKEN`
  - `HF_USERNAME`
  - `HF_DATASET_REPO_ID` (default `<HF_USERNAME>/vota-con-la-chola-data`)
- Canonical publish command:
  - `just etl-publish-hf`
  - Use `just etl-publish-hf-dry-run` before first publish or when changing packaging logic.
- Current HF packaging contract:
  - `just etl-publish-hf` exports public-safe metadata + Parquet tables for Data Studio browsing.
  - Parquet tuning env vars:
    - `HF_PARQUET_BATCH_ROWS` (default `50000`)
    - `HF_PARQUET_COMPRESSION` (default `zstd`)
    - `HF_PARQUET_TABLES` (optional subset; empty means all non-excluded tables)
    - `HF_PARQUET_EXCLUDE_TABLES` (default `raw_fetches,run_fetches,source_records,lost_and_found`)
    - `HF_ALLOW_SENSITIVE_PARQUET` (`0` by default; set `1` only for private repos)
    - `HF_INCLUDE_SQLITE_GZ` (`0` by default; set `1` only for private repos)
- Significant data change checklist (required):
  - Run `just etl-publish-hf-dry-run` and verify non-zero `Parquet tables`/`Parquet files`.
  - Run `just etl-publish-hf` to push the new snapshot to `HF_DATASET_REPO_ID`.
  - Confirm `latest.json` points to the new `snapshot_date`.
  - If publish fails, record blocker evidence in `docs/etl/e2e-scrape-load-tracker.md` (do not mark DONE).
- Completion rule for snapshot slices:
  - A slice that claims published artifacts is not complete until HF publish succeeds or the blocker is recorded with evidence in `docs/etl/e2e-scrape-load-tracker.md`.

### Idempotence Contract (Must Preserve)
- DB upserts are keyed by `(source_id, source_record_id)` for mandates.
- Samples-based test enforces idempotence across all connectors:
  - `just etl-test` (runs `tests/test_samples_e2e.py` inside Docker)
- Every connector MUST have a deterministic sample in:
  - `etl/data/raw/samples/<source_id>_sample.*`
  - declared in `etl/politicos_es/config.py` as `fallback_file`

### Strict-Network Guardrails
- `--strict-network` must fail fast on:
  - HTML payload when structured data is expected (see `etl/politicos_es/http.py`).
  - suspicious "seen > 0 but loaded == 0" runs (pipeline gate).
- Each connector should set `min_records_loaded_strict` in `etl/politicos_es/config.py`.

### When TLS Is Broken
- Some official sites have TLS chain issues in container/CI contexts.
- `etl/politicos_es/http.py:http_get_bytes()` supports `insecure_ssl=True` (unverified context).
- Use it surgically per-host, never globally.

### When WAF/Cloudflare Blocks (Reality)
As of `2026-02-12` from this environment:
- Parlamento de Galicia endpoints return `403` (WAF).
- Parlamento de Navarra endpoints return `403` with `cf-mitigated: challenge`.
Guideline:
- Do not "fake DONE". Mark as blocked in tracker + document the failure mode and evidence URL/status.
- Add/update the corresponding incident in `docs/etl/name-and-shame-access-blockers.md` with evidence links and the planned escalation action.
- If a bypass requires interactive browser challenges/cookies, it is not reproducible by default; only add optional cookie injection if explicitly accepted as a tradeoff.

### Connector-Specific Notes (Hard-Won)

#### Cortes de Aragon (XI)
- Active list and "bajas" are separate views under the same system.
- Implemented extraction merges:
  - activos: `uidcom=-2` -> 67 active mandates
  - bajas: `uidcom=-99` -> 8 inactive mandates (`is_active=0`, `end_date=snapshot_date`)
- See: `etl/politicos_es/connectors/cortes_aragon.py`.

#### Senado (Detail Endpoint Instability)
- Senate detail (`tipoFich=1`) can occasionally return transient `500`.
- Connector must be resilient: a single bad senator detail must not abort the full run.
- Current behavior: if detail fails, still emits record from group membership data, with `detail_error` populated.
- See: `etl/politicos_es/connectors/senado.py`.

#### Senado (Parallel Download Learnings)
- Fast backfill is now implemented via threaded detail enrichment in `etl/parlamentario_es/pipeline.py` and exposed as `--detail-workers` on `backfill-senado-details`.
- Practical defaults:
  - `--detail-workers 16` is a good first pass on local network links.
  - Use `1` when debugging or when upstream blocks concurrency.
  - Keep `--timeout` low-moderate (e.g. `20-30`) to avoid long-tail stalls.
  - In container runs, set `SENADO_DETAIL_DIR` to a repo-mounted path (e.g. `etl/data/raw/manual/senado_votaciones_ses`) so cached `ses_*.xml` files are visible and reusable.
- Auto-loop behavior:
  - When prefetch hits hard `HTTP 403`, backend sets `detail_blocked=True` and auto loops stop with `stop_reason=detail_blocked` to avoid blind repeated attempts.
  - In that state, avoid rerunning with high limits; switch to `--senado-detail-dir` or lower workers + single-event probing.
- Strong gain case:
  - Dry-run backfills of `--max-events` batches complete quickly and keep per-event work off main ingest path.
  - Works well when URLs are reachable and cache-friendly.
- Critical bottleneck:
 - Multiple `senado_es` legislaturas return WAF-style `HTTP 403` on detail endpoints; in those cases increasing workers gives no quality gain and just increases failure attempts.
 - In this environment, legis 10/12/15 hit 403 clusters while others may still work.
- Speed-up rule of thumb:
  - Maximize parallelism only for batches with expected high hit-rate.
  - For blocked ranges, switch to `--senado-detail-dir` (pre-fetched local XML), or pause/fallback with lower worker count and explicit cookies.
- Current backfill guard:
  - In blocked scenarios, prefetch now probes a small seed set (up to 3 URLs); if all sampled requests return hard `HTTP 403`, the run is treated as blocked and the remaining URLs are marked blocked in-cache without extra network calls.
- Operational detail:
  - Backfill now deduplicates `ses_*.xml` URLs and performs a parallel prefetch pass before per-row enrichment, so one successful session fetch can feed multiple vote rows in the same batch.
  - The warm cache is read-only during row enrichment, reducing duplicate network calls and lowering total HTTP churn when many rows share a session context.
- Data tracking:
  - Track `detail_failures` by exact `leg=... ses=...: network-detail: HTTPError: HTTP Error 403: Forbidden` patterns in logs/JSON output to identify which legislatures require manual capture or fallback.

#### Parallel Scraping/Downloads: Practical Speed Notes
- Prefer one large parallel batch over many small batches when endpoints are healthy.
- Use bounded worker counts as a throughput lever (`--detail-workers` or equivalent), then tune downward quickly if:
  - error rate climbs (especially 403/429),
  - upstream latency spikes,
  - or response body sizes shrink (common anti-bot failure signatures).
- Always dedupe request URLs before dispatch; one session/ID can often hydrate many rows.
- Split work into:
  - a prefetch stage (`HEAD`/first-successful GET probe + shared cache warmup),
  - then idempotent row enrichment reading from cache.
- Reuse a single HTTP session/client per worker group to cut TLS handshake and DNS churn.
- Set short timeouts for discovery and longer ones for payload reads if needed; a 20-30s envelope usually wins overall runtime by pruning dead workers.
- In blocked/WAF conditions, parallelism no longer helps throughput; switch to local replay (`SENADO_DETAIL_DIR`/`--senado-detail-dir`) or smaller batches.

#### Asamblea de Ceuta (No Stable IDs)
- Source is a government web page listing members by group and a Mesa section.
- No canonical person IDs: connector generates stable-ish IDs from `(term, name, institution)`.
- Prefer group membership rows when a person appears in multiple sections.
- See: `etl/politicos_es/connectors/asamblea_ceuta.py`.

### Infoelectoral (Important For Next Wave)
- The "Área de Descargas" UI uses a backend API under `https://infoelectoral.interior.gob.es/min/`.
- API is protected by Basic Auth as shipped in their JS:
  - user: `apiInfoelectoral`
  - pass: `apiInfoelectoralPro`
- Example endpoint:
  - `GET /min/convocatorias/tipos/` with Basic Auth returns JSON.
- Treat as official but expect contract drift; add strict-network guards + samples.
