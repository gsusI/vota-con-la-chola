# Agent Operating Notes

This repo is intentionally ultra-lean. When expanding ETL/schema/UI, optimize for:
- Reproducibility (single SQLite file, deterministic-ish results per snapshot date)
- Traceability (raw payloads and sources)
- Fast ingestion (avoid N+1 DB roundtrips)
- Schema-driven navigation (Explorer UI should work as schema/data evolve)

## Execution Philosophy (KISS + Delivery)

### Documentation Philosophy
- One source of truth per layer:
  - Future direction and sequencing: `ROADMAP.md`
  - Strategy/model background: `docs/roadmap.md`
  - Near-term execution (derived): `docs/roadmap-tecnico.md`
  - Operational backlog and real status: `docs/etl/e2e-scrape-load-tracker.md`
  - Public accountability log for blocked access to public data: `docs/etl/name-and-shame-access-blockers.md`
- Do not duplicate roadmaps in random docs. Link instead of copy. If direction changes, update `ROADMAP.md` first.
- Every non-trivial change must answer three questions in docs or tracker:
  - where we are now
  - where we are going
  - what is next
- Keep docs lean and operational:
  - decisions, constraints, commands, DoD
  - avoid long narrative that does not change implementation choices

### Privacy & Publication Hygiene (Mandatory)
- Never commit workstation-identifying strings in artifacts/docs:
  - absolute local paths (`/Users/...`, `file:///...`, `/home/...`)
  - personal emails/usernames in local path segments
  - browser profile state dumps, local cookie jars, or local session files
- For sprint evidence under `docs/etl/sprints/**`, prefer repo-relative paths (for example `docs/etl/sprints/...`) over absolute filesystem paths.
- Treat credentials/secrets as hard-blockers for commit/publish:
  - API tokens, Bearer headers, cookies, `.env` values, private keys
  - if they appear in logs/evidence, redact before commit
- Public artifact gate is mandatory before publish:
  - `just privacy-check-public-artifacts` (ETL-wide) must pass before `just site-build-refresh`, `just etl-publish-hf-dry-run`, and `just etl-publish-hf`
  - frozen site builds (`just site-publish`) gate exactly what they ship with `just site-artifact-gate` (real-data markers + leak scan over `ui/site/out`); it runs inside `site-build-frozen`
- If a leak is detected in public outputs (`docs/gh-pages` or `etl/data/published`):
  - stop the publish
  - fix the generator/sanitizer (not just the generated file)
  - regenerate artifacts and re-run the privacy gate
  - record the incident + remediation in tracker/sprint evidence when applicable
- If sensitive data was already committed, do not ignore it:
  - open a follow-up to scrub affected files
  - if needed, plan history rewrite (`git filter-repo`) with explicit maintainer approval
- Frontend publish rule: when you modify any frontend artifact (`ui/**` or static/public UI files), commit and push first, then deploy from the local machine with `just site-publish` (builds `ui/site/out` from the public exports already on disk and syncs it to the R2 origin of votaconlachola.org), so `main` and the live site stay in sync. Deploys are built locally on purpose: they must take ~2.5–3 min (CI takes ~5.5 min). If one takes much longer, find the regression instead of accepting it (see `docs/public-site.md` for what keeps it fast). Run it in the background: it may first wait for another session's publish lock, and a queued publish whose inputs are already live exits immediately. Exactly one deploy per change: nothing in CI deploys on push or on schedule (the nightly `Live ETL Publish` only validates the build). The `Site deploy` workflow is a manual fallback only (`gh workflow run site-deploy.yml`), for when no local machine is available; never run it for a change you already published locally. Regenerating exports from local staging DBs is a separate data change (`just site-build-refresh`, review, commit) or `CLOUDFLARE_PAGES_FROZEN_INPUTS=0 just site-publish`. The `gh-pages` branch is no longer published.

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

### Anti-Loop Sprint Policy (Mandatory)
- Every sprint MUST deliver at least one visible, user-facing delta that is under repo control (schema/data/UI/API/artifact), even if external sources remain blocked.
- Default sprint capacity split:
  - `>=70%` controllable work (can ship without upstream behavior change)
  - `<=30%` unblock/probe work (external dependency risk)
- Do not repeat the same blocker probe pattern unless there is a new lever. Valid new levers include:
  - new credential/token available,
  - changed endpoint/contract with evidence,
  - approved reproducible bypass policy,
  - upstream status change with fresh signal.
- Per blocked source, run at most one strict-network retry per sprint when no new lever exists; otherwise log `no_new_lever` and move on.
- Sprint closeout must include a `visible_progress` check with evidence. Examples:
  - tracker row improved with measurable KPI delta,
  - new reproducible artifact published and linked in UI/status payload,
  - new drill-down capability or parity check added and passing.
- If a proposed objective depends only on external unblock, recast it as a secondary lane and set a controllable primary objective.

### Citizen-First Product Rules (Static, Evidence-First)
- Treat `/citizen` (GH Pages) as the default user-facing surface for “what happened on what you care about”.
- Keep it **static-first**:
  - prefer bounded JSON artifacts + client-side rendering
  - avoid server requirements unless explicitly approved
- Prefer shareable state:
  - encode meaningful view state in URL params (concerns, party focus, method) so a link reproduces the view
  - use `localStorage` only as a convenience fallback when URL state is absent
- Privacy exception (user preferences):
  - citizen preference inputs are **local-first by default** (store in `localStorage`)
  - never write preferences into URL query params automatically
  - if a share link is provided, it must be explicit opt-in and should use URL **fragment** (`#...`) over query (`?...`) to avoid server log leakage
- Preserve auditability:
  - every stance shown in the citizen UI must link to a concrete explorer drill-down (SQL/evidence/tema)
  - render `unknown/no_signal` explicitly (never silently impute)
- Versioned voting-aid tests (`/citizen/vota/`): when the test changes (questions, scoring, data set), publish it as a new version and keep every earlier one online in parallel.
  - Register it in `ui/site/app/citizen/vota/votingAidVersions.mjs`: the new one is `current` at `/citizen/vota/`; old ones keep their own path, snapshot file and localStorage key, so users can reopen, review and compare their old answers.
  - Never overwrite an old version's published snapshot; a new version gets a new `voting_aid_generales_vN.json`.
- Enforce performance budgets:
  - citizen snapshot JSON must remain bounded (target <= `5MB`), validated in `just site-build`
  - prefer pre-aggregation (small grids) over shipping raw evidence blobs to the browser

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
- Durable agent knowledge base: `project_kb/README.md`.
- Use it for stable project learnings, decisions, workflows, and gotchas. Do not duplicate roadmap or tracker authority there.

## Subagent Fan-Out (Efficient Mode From The Start)
When a task is split across many subagents (one per question, vote, source...), launch them in efficient mode
from the first wave. Measured on the voting-aid «A quién afecta» pass (2026-10-13): cost is dominated by re-reading
context every turn (old prompt: 4–25 M cache tokens and 40–160 turns per agent; efficient mode: ~0.6–1.5 M and 5–20
turns, same validator, same quality).
- Prepare before launching: a compact per-unit worklist with everything already extracted (texts, locators,
  voted point, official text URL pre-cached) and a pre-filled output skeleton with every key, so the agent edits
  instead of building.
- Self-contained prompt (rules, schema, one example, validation command): tell agents NOT to read seeds, exporters,
  guides or other agents' outputs.
- Shared knowledge, not rediscovery: a catalog of already verified facts searchable by regex, a shared download
  cache, and the list of known blocked hosts. For voting-aid impacts use `python3 -m scripts.voting_aid_impacts_kit`
  (`catalog`, `fetch`, `vote`, `ine`, `eurostat`); the exporter merges part files and checks coverage
  (`scripts/export_voting_aid_vote_impacts.py --part/--require-complete`). Guide: `docs/etl/sprints/VOTING-AID-20261011/prompts/ramificaciones-redaccion.md`.
- Budgets in the prompt: bounded tool outputs (never cat whole files, never Read PDFs/images), ≤4 WebSearch per
  agent (the quota is shared and runs out), fill all items in one edit, validate at the end, report ≤6 lines.
- Order waves so later units reuse earlier work (big/thematic units first, then units that mostly pick from the
  catalog). Max 20 concurrent subagents; one output file per agent to avoid write conflicts.

Mandatory loop for any large subagent job (do not launch a full wave blind):
1. **Pilot with ONE agent** on a small but varied slice (2–5 items of different kinds), run in foreground.
2. **Measure** with `python3 scripts/subagent_usage_report.py <session-dir>/subagents --only <id>`: turns, input
   tokens, largest tool results. Ask the agent to end its report with "what tool/data would have saved me turns".
3. **Fix the wheel, not the agent**: turn every rediscovery into shared tooling (kit subcommand or python helper,
   pre-extracted field in the worklist, known-blocked host, example in `--help`) and tighten the prompt. Prefer
   helpers that let the agent fetch + compute in ONE python call over multi-step shell chains.
4. **Scale gradually while watching**: a second small wave (2–3 agents) with the fixes, re-measure, then the rest.
   Batch items that share a source in the same agent (cache + context reuse; ~5 items per agent).
5. **Verify outputs mechanically** (validator/apply script), never by trusting reports; collect reject/unverifiable
   for a person. Reviewer outputs are one file per item (e.g. `kit apply-reviews <dir>` stamps `review` on facts).
6. **Review a random sample for quality before publishing** (a validator only proves shape): ~10–20 items checked
   against the source by one reviewer agent, with a decision rule fixed in advance. The voting-aid indirect effects
   passed every validator but failed this (4/20, then 2/10 on the narrowed scope) and were closed unpublished after
   ~65 M tokens; a 10-item quality pilot right after the drafting pilot would have caught it.
Reference costs (2026-10-13): drafting old prompt ~0.7 M input tokens per vote; efficient mode ~0.15–0.4 M;
derived-figure review: pilot 0.7 M per figure → 0.35 M after the first fixes → 0.15–0.25 M
once the kit fetched+computed in one python call (outliers were TLS-broken hosts and xlsx sources, then added to the kit);
generic-scale review: pilot 0.23 M per vote → 0.14–0.17 M at scale (50 agents, 447 votes, 74 M total);
direct effects from official text: 0.05 M per vote (37 agents, 475 votes, 25 M) because a deterministic step reused
the repo's own extractor to put the literal voted text in each worklist. Check pre-extracted inputs for traps before
scaling (e.g. approved motions are renumbered: point N voted ≠ point N published).
Indirect effects from Pleno debates: 0.15 M per initiative / 0.06 M per vote (106 agents, 427 initiatives, 63 M) once each
worklist carried the debate already cut per speech (presidency turns and co-official-language paragraphs dropped,
≤2800 chars per speech, `[pág. N]` markers) and the prompt gave the batch's exact line count for parallel 450-line
Reads; first cut (whole debate) cost 0.58 M per initiative. Apply with `kit apply-indirect <dir> --map exp_votes.json`
(only votes left with both kinds get effects); the exporter's `PARTY_RE` flags «Sumar» as a verb, so reword it.

## Working Agreement

### Source Of Truth
- SQLite schema lives in `etl/load/sqlite_schema.sql`.
- ETL entrypoint is `scripts/ingestar_politicos_es.py`.
- Parlamentario ETL entrypoint is `scripts/ingestar_parlamentario_es.py`.
- UI server is `scripts/graph_ui_server.py`.
- Explorer UI is `ui/graph/explorer.html`.
- Citizen UI is `ui/citizen/index.html` (static GH Pages).
- Citizen snapshot export + validation are `scripts/export_citizen_snapshot.py` and `scripts/validate_citizen_snapshot.py`.

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

Parlamentario evidence backfills (votes -> "what was voted"):
- Backfill missing initiative links (historical rows):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-links --db <path> --source-ids congreso_iniciativas`
- Download the actual BOCG/Diario de Sesiones PDFs/HTML for initiatives linked to votes:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db <path> --limit-initiatives 200 --max-docs-per-initiative 3`
- Storage model:
  - URLs live in `parl_initiatives.links_bocg_json` / `parl_initiatives.links_ds_json`
  - Downloaded bytes + metadata live in `text_documents` with `source_id='parl_initiative_docs'`
  - Initiative->doc mapping lives in `parl_initiative_documents`

### Disk Footprint
- Never byte-copy local data that already exists on disk: use `publicdata_core.storage.clone_or_copy` (APFS clone / reflink, copy fallback) or a hardlink when the target is immutable.
- `FilesystemObjectStore` put/restore and HF/semantic publish staging already clone; a same-volume local origin costs ~0 extra bytes.
- Playwright capture scripts prune browser caches (`prune_browser_profile`) after closing the context; cookies/local storage are kept for profile reuse.
- Reclaim existing duplicates losslessly with `just storage-dedupe-dry-run` / `just storage-dedupe` (host only; `du` double-counts clones, check `df`).
- Cold snapshot DBs belong in `*.db.zst`; keep uncompressed only the DBs a recipe opens by default.

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
    - `HF_PARQUET_EXCLUDE_TABLES` (default `raw_fetches,run_fetches,lost_and_found`; `source_records` remains public so official personal evidence is not stripped)
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
