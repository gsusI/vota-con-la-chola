# Tracker Reconciliation — AI-OPS-05

Date: 2026-02-16  \
Repository: `REPO_ROOT/vota-con-la-chola`  \
DB: `etl/data/staging/politicos-es.db`

## Inputs

- `docs/etl/sprints/AI-OPS-04/reports/moncloa-tracker-row-draft.md`
- `docs/etl/sprints/AI-OPS-05/reports/moncloa-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-05/reports/navarra-galicia-blocker-refresh.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `scripts/export_explorer_sources_snapshot.py`

## Changes Applied to Tracker

Updated in `docs/etl/e2e-scrape-load-tracker.md`:

- `Accion ejecutiva (Consejo de Ministros)` updated from `TODO` to `PARTIAL` with evidence-backed blocker wording and explicit DoD next command.
- Navarra/Galicia blocker text refreshed to evidence-backed `403`-classified strict-network failure language and explicit local-replay success paths:
  - `parlamento_galicia_deputados` fallback dir `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages`.
  - `parlamento_navarra_parlamentarios_forales` fallback dir `etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages`.

## Snapshot Refresh

Command:
```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
```

Observed output:
```text
OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json
```

## Snapshot Summary (`jq '.summary.tracker' docs/gh-pages/explorer-sources/data/status.json`)

```json
{
  "items_total": 54,
  "unmapped": 26,
  "todo": 20,
  "partial": 5,
  "done": 29
}
```

## Reconciliation Checks

Executed:
- `just etl-tracker-status`
- `just etl-tracker-gate` (default estricto: mismatch + done_zero_real)
- `just etl-tracker-gate-legacy` (compat: solo done_zero_real)
- `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch` (comando explícito equivalente al check de mismatch)

Command log for strict mismatch check captured in:
`docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation-fail-on-mismatch.log` (run in this task with explicit `EXIT_CODE:1`)

### Result

`--fail-on-mismatch` exits non-zero when mismatches remain (`exit=1` in this run).

Observed outcome summary:
- `mismatch_exit_code: 1`
- `mismatches: 3`
- `sources_in_db: 32`, `tracker_sources: 30`
- Non-zero mismatches list:

| source_id | checklist | sql | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result |
|---|---|---|---:|---:|---:|---:|---|---|
| moncloa_referencias | PARTIAL | DONE | 7/8 | 2 | 20 | 20 | 2/5 | MISMATCH |
| moncloa_rss_referencias | PARTIAL | DONE | 8/10 | 8 | 8 | 8 | 2/6 | MISMATCH |
| parlamento_navarra_parlamentarios_forales | PARTIAL | DONE | 3/8 | 50 | 50 | 50 | 1/2 | MISMATCH |


## Escalation

Per escalation rule: if mismatch remains after edits, escalate with exact source IDs and per-source metrics.

Escalated source IDs and blocker interpretation:
- `moncloa_referencias` (status intentionally kept `PARTIAL` while SQL shows `DONE` due `max_net > 0` and `last_loaded>0`)
- `moncloa_rss_referencias` (status intentionally kept `PARTIAL` while SQL shows `DONE` for same reason)
- `parlamento_navarra_parlamentarios_forales` (status `PARTIAL` with `bloqueado` evidence; SQL remains `DONE` due historical/max network signal)

Action for L2: reconcile interpretation contract for `PARTIAL` with blocked rows when `runs_ok` remains partially file-backed, either by:
1) making tracker blocker text explicit as blocked-but-evidenced and accepting explicit mismatch, or 2) adjusting checker semantics if historical max_net should be gated by strict recency rules.

Current tracker edit objective (`Accion ejecutiva (Consejo de Ministros)` -> `PARTIAL`) is in place.
