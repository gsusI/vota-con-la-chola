# AI-OPS-08 waiver burn-down apply/recompute report

## Scope
- Deterministic command set for Navarra/BoE re-run and truth refresh
- Gates executed in strict default and waiver-aware modes
- Policy events counters and gate metrics captured before and after

## Commands executed
1. `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`
2. `just etl-tracker-gate`
3. `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --strict-network --timeout 30`
4. `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-16 --strict-network --timeout 30`
5. `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source boe_api_legal --snapshot-date 2026-02-16 --strict-network --timeout 30`
6. `python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db etl/data/staging/politicos-es.db`
7. `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json`
8. `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`
9. `just etl-tracker-gate`

## Evidence logs
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-baseline-waiver-aware.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-baseline-strict-gate.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-navarra-strict.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-galicia-strict.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-boe-ingest-replay.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-boe-policy-events-backfill.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-snapshot-refresh.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-after-waiver-aware.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-after-strict-gate.log`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-runbook.log`

## Before metrics
- `tracker_sources: 28`
- `sources_in_db: 33`
- `mismatches: 1`
- `waived_mismatches: 1`
- `waivers_active: 1`
- `waivers_expired: 0`
- `done_zero_real: 0`
- `policy_events_moncloa: 28`
- `policy_events_boe: 298`

## After metrics
- `tracker_sources: 28`
- `sources_in_db: 33`
- `mismatches: 1`
- `waived_mismatches: 1`
- `waivers_active: 1`
- `waivers_expired: 0`
- `done_zero_real: 0`
- `policy_events_moncloa: 28`
- `policy_events_boe: 298`

## Gate outputs
- Strict default gate (`just etl-tracker-gate`) exit: `FAIL` (exit code 1)
- Policy-aware check (explicit `--waivers docs/etl/mismatch-waivers.json`) exit: `FAIL` (exit code 1)

## Row-level impact (post-run)
- `boe_api_legal` remains `PARTIAL | DONE | MISMATCH`.
- `parlamento_navarra_parlamentarios_forales` remains `PARTIAL | DONE | WAIVED_MISMATCH`.
- `parlamento_galicia_deputados` remains `PARTIAL | PARTIAL | OK` and not considered mismatch.

## Escalation rules check
- Navarra unresolved due hard blocker in strict-network probe remains unresolved for waiver burn-down and still requires governance decision.
- Current waiver record:
  - `waiver_owner`: `L2`
  - `waiver_expires_on`: `2026-02-20`
  - blocker evidence: `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-navarra-strict.log`
- No new Navarra expiry was proposed or applied in this cycle.
- Since mismatch remains covered by active waiver and no new deterministic remediation exists, **do not renew in this cycle without explicit sponsor decision**.

## Evidence deltas
- BOE ingest replay: successful (`source_records_seen=298`, `policy_events_upserted=298`) and policy-events backfill completed.
- NAVARRA strict-network probe: `HTTPError 403` (blocked) while strict.
- GALICIA strict-network probe: `HTTPError 403` (blocked) while strict.

## Output checks
```bash
test -f docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md
rg -n "mismatches:|waived_mismatches:|waivers_active:|waivers_expired:|done_zero_real:|policy_events_boe|policy_events_moncloa" docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md
just etl-tracker-gate || true
```
