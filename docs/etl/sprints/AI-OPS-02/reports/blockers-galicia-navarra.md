# Blockers: Galicia + Navarra (ai-ops-02)

- `timestamp_utc`: 2026-02-16T09:43:29Z
- `scope`: Reprobe of `parlamento_galicia_deputados` and `parlamento_navarra_parlamentarios_forales`
- `status`: both remain blocked in this environment

## Commands run (reproducible)

1. Validate runtime status
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md
```

2. Inspect most recent source runs
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, run_id, source_url, records_seen, records_loaded, started_at, status, message FROM ingestion_runs WHERE source_id IN ('parlamento_galicia_deputados','parlamento_navarra_parlamentarios_forales') ORDER BY run_id DESC;"
```

3. Non-strict Galicia ingest
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-12
```

4. Strict Galicia ingest
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-12 --strict-network
```

5. Bounded Navarra ingest attempts
```bash
timeout 60s python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-12
timeout 60s python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-12 --strict-network
```

6. Direct endpoint probes
```bash
curl -I -L -A "Mozilla/5.0" --max-time 20 https://www.parlamentodegalicia.gal/Composicion/Deputados
curl -I -L -A "Mozilla/5.0" --max-time 20 https://www.parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales
```

## Observed failures (captured in raw/manual/blockers)

### Tracker / status signals
- `e2e_tracker_status` shows:
  - `parlamento_galicia_deputados | PARTIAL | PARTIAL | 3/4 | max_net=0 | max_any=75 | net/fallback_fetches=0/3 | result=OK`
  - `parlamento_navarra_parlamentarios_forales | PARTIAL | DONE | 2/4 | max_net=50 | max_any=50 | net/fallback_fetches=1/1 | result=MISMATCH`

### DB run evidence
- `parlamento_galicia_deputados`
  - `... run_id 148 ... records_seen=0 records_loaded=0 status=error message='Error: HTTP Error 403: Forbidden'`
  - `run_id 46` (from-dir) and `run_id 47` were successful manual/seed-loaded baselines
- `parlamento_navarra_parlamentarios_forales`
  - `run_id 150,149,145,144` remained `status=running` during probe window when network/ingest commands were invoked
  - `run_id 47` (from-dir manual artifacts) remained the last completed success

### Ingest command failures
- Galicia non-strict: logs show network fallback path was still used (`Ingesta completada: 3/3 registros validos (network-error-fallback: HTTP Error 403: Forbidden)`) and data load did not come from live fetch.
- Galicia strict: unhandled `urllib.error.HTTPError: HTTP Error 403: Forbidden` from `etl/politicos_es/connectors/parlamento_galicia.py`.
- Navarra strict/non-strict: no completion within probe window in strict bound tests; repeated runs leave active `running` rows and no new completed fetch rows.

### Direct endpoint evidence
- Galicia endpoint returns 403 (`HTTP/1.1 403 Forbidden`).
- Navarra endpoint returns `HTTP/2 403` with `cf-mitigated: challenge`.

Artifacts created under `etl/data/raw/manual/blockers`:
- `galcova_probe_run.out`
- `galicia_direct_probe_clean.out`
- `navarra_direct_probe_clean.out`
- `galicia_navarra_network_probe.out`
- `galicia_strict_probe.out`
- `navarra_strict_probe.out`
- `galicia_navarra_blocker_evidence.out`
- `parlamento_galicia_deputados_probe_run.out`
- `navarra_galicia_network_probe.out`
- `parlamento_navarra_parlamentarios_forales_probe_run.out`

## Next probe command (required)

To confirm this state in one pass:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md && sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, run_id, source_url, records_seen, records_loaded, started_at, status, message FROM ingestion_runs WHERE source_id IN ('parlamento_galicia_deputados','parlamento_navarra_parlamentarios_forales') ORDER BY run_id DESC;" && python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-12 --strict-network && timeout 60s python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-12 --strict-network
```

Expected outcome for reproducibility:
- Galicia: `HTTP Error 403: Forbidden` in strict mode
- Navarra: non-completion or Cloudflare challenge/blocked behavior and challenge headers in direct endpoint probes
- Tracker remains non-DONE for both sources unless manual artifacts and explicit bypass are reintroduced.
