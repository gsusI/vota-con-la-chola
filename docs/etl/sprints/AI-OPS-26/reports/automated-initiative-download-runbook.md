# Automated Initiative Download Runbook

Date:
- 2026-02-19

Objective:
- Run a deterministic, fast, low-intelligence pipeline to download and process initiative documents at scale.

Baseline snapshot (2026-02-19):
- `initiatives_with_downloaded_docs=339`
- `congreso_iniciativas=104/429`
- `senado_iniciativas=235/3607`

## Execution Script

```bash
#!/usr/bin/env bash
set -euo pipefail

DB="${DB:-etl/data/staging/politicos-es.db}"
SNAPSHOT_DATE="${SNAPSHOT_DATE:-2026-02-19}"
RAW_DIR="${RAW_DIR:-etl/data/raw}"
OUT_DIR="${OUT_DIR:-docs/etl/runs/initdocs_${SNAPSHOT_DATE}}"
SENADO_PROFILE_DIR="${SENADO_PROFILE_DIR:-}"   # optional Playwright profile dir

mkdir -p "$OUT_DIR"

# 1) Repair initiative links first (required)
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-links \
  --db "$DB" \
  --source-ids congreso_iniciativas,senado_iniciativas \
  | tee "$OUT_DIR/01_links.json"

# 2) Download Congreso docs for ALL initiatives (include-unlinked)
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db "$DB" \
  --initiative-source-ids congreso_iniciativas \
  --include-unlinked \
  --raw-dir "$RAW_DIR" \
  --snapshot-date "$SNAPSHOT_DATE" \
  --timeout 25 \
  --max-docs-per-initiative 3 \
  --limit-initiatives 5000 \
  --auto --max-loops 60 \
  --sleep-seconds 0.05 \
  --sleep-jitter-seconds 0.10 \
  | tee "$OUT_DIR/02_congreso_auto.json"

# 3) Download Senado docs for ALL initiatives
if [[ -n "$SENADO_PROFILE_DIR" && -d "$SENADO_PROFILE_DIR" ]]; then
  # Preferred path: browser-backed session
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --raw-dir "$RAW_DIR" \
    --snapshot-date "$SNAPSHOT_DATE" \
    --timeout 25 \
    --max-docs-per-initiative 2 \
    --limit-initiatives 5000 \
    --retry-forbidden \
    --auto --max-loops 30 \
    --playwright-user-data-dir "$SENADO_PROFILE_DIR" \
    --playwright-headless \
    | tee "$OUT_DIR/03_senado_auto_profile.json"
else
  # No profile: single bounded probe, do not loop
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --raw-dir "$RAW_DIR" \
    --snapshot-date "$SNAPSHOT_DATE" \
    --timeout 25 \
    --max-docs-per-initiative 1 \
    --limit-initiatives 200 \
    | tee "$OUT_DIR/03_senado_probe_noprofile.json" || true
fi

# 4) Quality report (processing KPI output)
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db "$DB" \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out "$OUT_DIR/04_quality_initiatives.json"

# 4b) Unified initiative-doc operational status (links/downloaded/fetch/excerpt + missing sample)
python3 scripts/report_initiative_doc_status.py \
  --db "$DB" \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --missing-sample-limit 20 \
  --out "$OUT_DIR/04b_initiative_doc_status.json"

# 5) Export missing URLs for next pass / blocker tracking
python3 scripts/export_missing_initiative_doc_urls.py \
  --db "$DB" \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --only-missing \
  --format csv \
  --out "$OUT_DIR/05_missing_all.csv"

python3 scripts/export_missing_initiative_doc_urls.py \
  --db "$DB" \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --format csv \
  --out "$OUT_DIR/06_missing_senado_actionable.csv"

# 5b) Optional strict gate: fail this stage if actionable queue is non-empty
python3 scripts/export_missing_initiative_doc_urls.py \
  --db "$DB" \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --strict-empty \
  --format csv \
  --out "$OUT_DIR/06b_missing_senado_actionable_strict.csv"

# 6) Hard counts
sqlite3 -header -csv "$DB" "
SELECT COUNT(*) AS downloaded_documents
FROM text_documents WHERE source_id='parl_initiative_docs';
SELECT COUNT(DISTINCT pid.initiative_id) AS initiatives_with_downloaded_docs
FROM parl_initiative_documents pid
JOIN text_documents td ON td.source_record_pk=pid.source_record_pk
WHERE td.source_id='parl_initiative_docs';
" > "$OUT_DIR/07_counts.csv"
```

## Decision Rules

1. Always run steps in order.
2. Never use `--refetch-existing` in normal runs.
3. If no Senado profile is available, run only one Senado probe and stop.
4. If `04_quality_initiatives.json` shows Congreso linked-vote doc coverage `< 0.99`, mark run `FAIL`.
5. If Senado remains blocked (`403/404/500` tail non-empty), mark run `PARTIAL_BLOCKED` (not `FAIL`).

## Learnings (2026-02-20)

- Ready process is already in place: do not introduce a separate custom downloader for Senate initiative docs. Reuse `backfill-initiative-documents` directly.
- Early window (same day): three operational modes (`no profile`, Playwright profile, cookie file) returned zero successful Senate doc fetches with `HTTP 403/500` failures (`candidate_urls=24`, `initiatives_seen=12`, `text_documents_upserted=0`).
- Later window (same day): bounded non-auto loops recovered throughput and produced material progress with the same process (net `+1131` Senate docs in one session; linked-to-votes initiatives with downloaded docs moved to `583/647 = 90.11%`).
- Effective recovery mode in unstable windows: repeated bounded passes with `--include-unlinked --retry-forbidden --limit-initiatives 40 --max-docs-per-initiative 1`, stopping when a pass returns `fetched_ok=0`, then resuming after cooldown.
- Tail-drain rule (same day, later): once linked-vote objective is complete, switch to skip-blocked mode (drop `--retry-forbidden`) so historical `403/404/500` URLs are skipped and the queue can advance to fetchable pockets.
- Wide-slice rule: for sparse non-linked tail, use `--limit-initiatives 2000+` to bypass blocked clusters in narrow slices and extract remaining low-volume successes.
- Queue-selection pitfall/fix (2026-02-21): with `--max-docs-per-initiative 1`, the pipeline could repeatedly pick an already-downloaded first URL and never attempt missing secondary URLs of the same initiative. Fix applied in `etl/parlamentario_es/text_documents.py` to skip already downloaded URLs before enforcing per-initiative caps.
- Post-fix impact (2026-02-21): immediate bounded drain of `+873` Senate docs (`6375 -> 7248`) in one run (`docs/etl/runs/senado_postfix_bounded_20260221T093208Z/13_run_summary.md`), then plateau on legacy clusters with persistent `403/500/404` (`docs/etl/runs/senado_postfix_bounded2_20260221T094545Z/13_run_summary.md`, `docs/etl/runs/senado_postfix_playwright_20260221T095052Z/13_run_summary.md`).
- Historical traceability fix (2026-02-22): some already-downloaded Congreso initiative docs had no `document_fetches` rows (not a download miss). Use `scripts/backfill_initiative_doc_fetch_status.py` to reconstruct success rows from `parl_initiative_documents + text_documents` and remove false missing noise.
- Current hard tail signal (2026-02-22): latest bounded Senate retry (`docs/etl/sprints/AI-OPS-27/evidence/senado_tail_retry_post_fetchstatus_20260222T102357Z.json`) kept `fetched_ok=0` for `119` remaining URLs; status bucket is now `HTTP 404` for the whole tail (primarily `global_enmiendas_vetos_*`).
- Archive fallback (2026-02-22): `backfill-initiative-documents` now supports `--archive-fallback --archive-timeout <s>` and can prioritize archive lookup first for URLs already marked `404` in `document_fetches`; checkpoint sweep on Senate tail attempted `119` lookups with `0` archive hits (`docs/etl/sprints/AI-OPS-27/evidence/initdoc_archive_sweep_20260222T135005Z.json`).
- Derived-INI fallback (2026-02-22): for Senado `global_enmiendas_vetos_*`, downloader now derives `.../xml/INI-3-<exp>.xml` and prioritizes it under low per-initiative caps. On the current tail this isolated `8` initiatives with no INI local and confirmed all `8` derived INIs as `HTTP 404`; unfetched derived probes are no longer persisted into `parl_initiative_documents` (no metric inflation).
- Detail-XML fallback in status triage (2026-02-22): when INI is missing, `report_initiative_doc_status.py` now reuses downloaded `tipoFich=3` XML to infer `enmCantidad`; first pass narrowed actionable tail from `8` to `4`.
- Redundant-global triage (2026-02-22, late): status/report now classifies stale Senate `global_enmiendas_vetos` URLs as `likely_not_expected_redundant_global_url` when alternative BOCG docs are already downloaded; current tail is `119/119` redundant, `0` actionable (`docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`).
- Queue guard (2026-02-22, late): downloader skips those redundant Senate globals (and derived INI probes) so default queue runs stop retry churn (`docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json`).
- New observability command (2026-02-22): `scripts/report_initiative_doc_status.py` emits one deterministic JSON with by-source link/download/fetch/excerpt coverage and missing status buckets to avoid ad-hoc SQL in each retry session.
- Core KPI extension (2026-02-22): `quality-report --include-initiatives` now also emits doc-link/fetch/excerpt KPIs and missing status buckets in `initiatives.kpis`, so gate artifacts can carry initiative-doc tail diagnostics without extra SQL.
- KPI extension (2026-02-22, late): canonical `quality-report --include-initiatives` now also emits tail triage KPIs (`missing_doc_links_likely_not_expected`, `missing_doc_links_actionable`, `effective_downloaded_doc_links_pct`) and Senate `global_enmiendas_vetos_analysis`.
- Anti-stall loop guard (2026-02-22): `scripts/senado_tail_daemon.sh` now exits with explicit stop reasons and writes `RUN_DIR/_stop_summary.json`, preventing infinite retry loops when no new lever exists.
  - Stop reasons: `complete`, `uniform_404_tail`, `no_progress`, `max_rounds`.
- Actionable-tail export contract (2026-02-22, AI-OPS-61): `scripts/export_missing_initiative_doc_urls.py` now supports `--only-actionable-missing` and `--strict-empty`, so queue ops can distinguish redundant non-actionable Senate tail (`global_enmiendas_vetos`) from real actionable backlog and fail fast only when actionable rows remain.
  - Useful env toggles: `STOP_ON_UNIFORM_404=1`, `MAX_IDLE_ROUNDS=6`, `MAX_ROUNDS=0` (unlimited unless another stop condition triggers).
- Evidence to reuse for future sessions:
  - Early-failure window: `docs/etl/sprints/AI-OPS-26/reports/senado-vpn-retry-20260220.md`, `docs/etl/sprints/AI-OPS-26/evidence/senado_retry_*.json`, `docs/etl/runs/senado_retry_20260220T000000Z/13_senado_retry_summary.md`.
  - Recovery window: `docs/etl/runs/senado_stable_loop_20260220T115905Z/`, `docs/etl/runs/senado_drain_loop_20260220T120121Z/`, `docs/etl/runs/senado_drain_loop2_20260220T120721Z/13_run_summary.md`, `docs/etl/runs/senado_unlinked_cookie_drain8_20260220T141131Z/13_run_summary.md`, `docs/etl/runs/senado_unlinked_skip_blocked16_20260220T142634Z/13_run_summary.md`, `docs/etl/runs/senado_unlinked_skip_blocked17_20260220T142756Z/13_run_summary.md`.
  - AI-OPS-27 checkpoint: `docs/etl/sprints/AI-OPS-27/reports/senado-tail-status-20260222.md`, `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-fetch-status-backfill-20260222.md`, `docs/etl/sprints/AI-OPS-27/reports/initiative-doc-status-report-20260222.md`, `docs/etl/sprints/AI-OPS-27/evidence/initdoc_fetch_status_post_20260222T102357Z.json`, `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_20260222T103042Z.json`, `docs/etl/sprints/AI-OPS-27/evidence/initiative_doc_status_redundant_global_triage_20260222T142835Z.json`, `docs/etl/sprints/AI-OPS-27/evidence/senado_redundant_global_skip_run_20260222T142846Z.json`.

## Daemon helper (anti-stall)

Use when you want unattended bounded retries with explicit stop semantics.

```bash
DB_PATH=etl/data/staging/politicos-es.db \
RUN_DIR=docs/etl/runs/senado_tail_daemon_$(date -u +%Y%m%dT%H%M%SZ) \
MAX_IDLE_ROUNDS=6 \
MAX_ROUNDS=0 \
STOP_ON_UNIFORM_404=1 \
ARCHIVE_FALLBACK=1 \
ARCHIVE_TIMEOUT=12 \
COOKIE_FILE=etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
bash scripts/senado_tail_daemon.sh
```

Output artifacts:
- `RUN_DIR/round_*_retry_cookie.json`
- `RUN_DIR/round_*_skip_wide.json`
- `RUN_DIR/_stop_summary.json`
