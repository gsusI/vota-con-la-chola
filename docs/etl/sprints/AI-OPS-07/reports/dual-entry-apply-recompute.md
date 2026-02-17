# AI-OPS-07 dual-entry apply/recompute report

## Scope
- BOE+Moncloa apply/recompute cycle and gate reconciliation for BOE integration.
- Deterministic capture of strict and waiver-aware checker results, before/after mismatch deltas, and policy_events count deltas.

## Evidence logs
- `docs/etl/sprints/AI-OPS-07/evidence/pre_apply_waiveraware_checker.log`
- `docs/etl/sprints/AI-OPS-07/evidence/pre_apply_strict_checker.log`
- `docs/etl/sprints/AI-OPS-07/evidence/pre_apply_metrics.log`
- `docs/etl/sprints/AI-OPS-07/evidence/boe_ingest_strict.log`
- `docs/etl/sprints/AI-OPS-07/evidence/boe_policy_events_backfill.log`
- `docs/etl/sprints/AI-OPS-07/evidence/moncloa_moncloa_referencias_strict.log`
- `docs/etl/sprints/AI-OPS-07/evidence/moncloa_moncloa_referencias_fallback.log`
- `docs/etl/sprints/AI-OPS-07/evidence/moncloa_moncloa_rss_referencias_strict.log`
- `docs/etl/sprints/AI-OPS-07/evidence/moncloa_moncloa_rss_referencias_fallback.log`
- `docs/etl/sprints/AI-OPS-07/evidence/moncloa_policy_events_backfill.log`
- `docs/etl/sprints/AI-OPS-07/evidence/explorer_snapshot_refresh.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_strict_checker.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_strict_checker_final.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker_final.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_metrics_final.log`
- `docs/etl/sprints/AI-OPS-07/evidence/strict_unwaived_mismatches.tsv`

## Commands executed
1. Baseline pre-apply gate checks and snapshot counts
   - `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`
   - `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real`
   - `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa FROM policy_events WHERE source_id LIKE 'moncloa_%';"`
   - `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe FROM policy_events WHERE source_id LIKE 'boe_%';"`
2. BOE ingest (strict-network)
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source boe_api_legal --snapshot-date 2026-02-16 --timeout 30 --strict-network"`
3. BOE policy-events backfill
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db etl/data/staging/politicos-es.db --source-ids boe_api_legal"`
4. Moncloa strict replay + fallback
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --snapshot-date 2026-02-16 --timeout 30 --strict-network"`
   - fallback: `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --snapshot-date 2026-02-16 --timeout 30"`
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --timeout 30 --strict-network"`
   - fallback: `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --timeout 30"`
5. Moncloa policy-events backfill
   - `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py backfill-policy-events-moncloa --db etl/data/staging/politicos-es.db --source-ids moncloa_referencias moncloa_rss_referencias"`
6. Explorer snapshot refresh
   - `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json`
7. Post-apply checker matrix
   - strict: `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real`
   - waiver-aware: `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`

## Before/after counts

### Before apply
- `mismatches: 3`
- `waived_mismatches: 0`
- `waivers_active: 0` (strict checker invocation)
- `policy_events_moncloa = 28`
- `policy_events_boe = 3`
- `done_zero_real: 0`

### After apply
- `mismatches: 3`
- `waived_mismatches: 0`
- `waivers_active: 0` (strict)
- `policy_events_moncloa = 28`
- `policy_events_boe = 298`
- `done_zero_real: 0`
- `EXIT_CODE_STRICT_UNWAIVED = 1`
- `EXIT_CODE_WAIVER_AWARE = 0`

## Checker outputs
- Strict unwaived output: `docs/etl/sprints/AI-OPS-07/evidence/post_apply_strict_checker_final.log`
  - Includes hard mismatch rows for:
    - `moncloa_referencias`
    - `moncloa_rss_referencias`
    - `parlamento_navarra_parlamentarios_forales`
  - `done_zero_real` remains `0`.
- Waiver-aware output: `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker_final.log`
  - No hard mismatches (`mismatches: 0`) and `waived_mismatches: 3`.

## Escalation
- Strict gate remains failing after replay because these mismatches are policy-waived but still unaligned at SQL-vs-checklist level.
- Exact strict mismatch sources and current waiver status:

| source_id | waiver_status | next_remediation_command |
|---|---|---|
| moncloa_referencias | WAIVED (active until 2026-02-20) | `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --snapshot-date 2026-02-16 --timeout 30"` |
| moncloa_rss_referencias | WAIVED (active until 2026-02-20) | `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --timeout 30"` |
| parlamento_navarra_parlamentarios_forales | WAIVED (active until 2026-02-20) | `docker compose run --rm --build etl "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --timeout 30"` |

If strict-unwaived behavior is required, rerun with `--strict-network` first for the above sources and then fallback (where needed) exactly as in the Moncloa fallback commands logged above.

## Additional artifacts
- Snapshot refreshed to `docs/gh-pages/explorer-sources/data/status.json`.
- `docs/etl/sprints/AI-OPS-07/evidence/strict_unwaived_mismatches.tsv` contains machine-readable strict-mismatch extract (empty for unwaived entries because active waivers cover all 3 current strict mismatches).
