# AI-OPS-04 Evidence Packet — Moncloa Tracker Reconciliation

Date: 2026-02-16
Repository: `REPO_ROOT/vota-con-la-chola`

## Scope
Evidence packet for tracker row:
- `Accion ejecutiva (Consejo de Ministros)`

Evidence inputs consumed:
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-dashboard-parity.md`
- `docs/etl/e2e-scrape-load-tracker.md`

Current tracker row (baseline):

```text
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
```

## 1) Ingest Matrix Evidence (strict-network vs from-file)

Commands (from matrix DB):

```bash
sqlite3 -header -csv etl/data/staging/moncloa-aiops04-matrix-20260216.db "SELECT run_id, source_id, status, records_seen, records_loaded, message FROM ingestion_runs WHERE source_url NOT LIKE 'file://%' ORDER BY run_id;"
sqlite3 -header -csv etl/data/staging/moncloa-aiops04-matrix-20260216.db "SELECT run_id, source_id, status, records_seen, records_loaded, message FROM ingestion_runs WHERE source_url LIKE 'file://%' ORDER BY run_id;"
sqlite3 -header -csv etl/data/staging/moncloa-aiops04-matrix-20260216.db "SELECT CASE WHEN source_url LIKE 'file://%' THEN 'from-file' ELSE 'strict-network' END AS mode, COUNT(*) AS runs, SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok_runs, SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS error_runs, ROUND(100.0 * SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)/COUNT(*), 2) AS failure_rate_pct FROM ingestion_runs GROUP BY mode ORDER BY mode;"
```

Observed outputs:

```text
strict-network
run_id,source_id,status,records_seen,records_loaded,message
1,moncloa_referencias,error,0,0,"Error: <urlopen error [Errno 8] nodename nor servname provided, or not known>"
2,moncloa_rss_referencias,error,0,0,"Error: No se pudo extraer ningun item RSS de Moncloa"

from-file
run_id,source_id,status,records_seen,records_loaded,message
3,moncloa_referencias,ok,20,20,"Ingesta completada: 20/20 registros validos (from-dir)"
4,moncloa_rss_referencias,ok,8,8,"Ingesta completada: 8/8 registros validos (from-dir)"
5,moncloa_referencias,ok,20,20,"Ingesta completada: 20/20 registros validos (from-dir)"
6,moncloa_rss_referencias,ok,8,8,"Ingesta completada: 8/8 registros validos (from-dir)"

mode,runs,ok_runs,error_runs,failure_rate_pct
from-file,4,4,0,0.0
strict-network,2,0,2,100.0
```

Conclusion:
- Reproducible blocker in this environment: strict-network fails, from-file succeeds with repeatability.

## 2) Apply/Recompute Evidence (live DB)

Commands:

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT source_id, is_active, name FROM sources WHERE source_id IN ('moncloa_referencias','moncloa_rss_referencias') ORDER BY source_id;"
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS source_records_total FROM source_records WHERE source_id IN ('moncloa_referencias','moncloa_rss_referencias') GROUP BY source_id ORDER BY source_id;"
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS policy_events_total FROM policy_events WHERE source_id IN ('moncloa_referencias','moncloa_rss_referencias') GROUP BY source_id ORDER BY source_id;"
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa_total FROM policy_events WHERE source_id LIKE 'moncloa_%';"
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa_with_source_url FROM policy_events WHERE source_id LIKE 'moncloa_%' AND source_url IS NOT NULL AND trim(source_url)<>'';"
sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa_null_event_date_with_published FROM policy_events WHERE source_id LIKE 'moncloa_%' AND (event_date IS NULL OR trim(event_date)='') AND published_date IS NOT NULL AND trim(published_date)<>'';"
```

Observed outputs:

```text
source_id,is_active,name
moncloa_referencias,1,"La Moncloa - Referencias del Consejo de Ministros"
moncloa_rss_referencias,1,"La Moncloa - RSS Referencias/Resumenes del Consejo de Ministros"

source_id,source_records_total
moncloa_referencias,21
moncloa_rss_referencias,8

source_id,policy_events_total
moncloa_referencias,20
moncloa_rss_referencias,8

policy_events_moncloa_total
28

policy_events_moncloa_with_source_url
28

policy_events_moncloa_null_event_date_with_published
0
```

Integrity check:

```bash
sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;" | wc -l
```

```text
0
```

## 3) Dashboard Export Parity Evidence

Commands:

```bash
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
python3 - <<'PY'
import json, sqlite3
from pathlib import Path
status = json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
conn = sqlite3.connect('etl/data/staging/politicos-es.db')
live_policy_total = conn.execute("SELECT COUNT(*) FROM policy_events").fetchone()[0]
live_moncloa_sources = conn.execute("SELECT COUNT(*) FROM sources WHERE source_id IN ('moncloa_referencias','moncloa_rss_referencias')").fetchone()[0]
conn.close()
export_policy_total = (((status.get('analytics') or {}).get('action') or {}).get('policy_events_total'))
sources = status.get('sources') or []
found = sorted(set(s.get('source_id') for s in sources if isinstance(s, dict) and s.get('source_id') in ('moncloa_referencias','moncloa_rss_referencias')))
print('live_policy_events_total', live_policy_total)
print('export_policy_events_total', export_policy_total)
print('live_moncloa_sources_count', live_moncloa_sources)
print('export_moncloa_source_ids', found)
print('all_match', live_policy_total == export_policy_total and live_moncloa_sources == len(found))
PY
```

Observed outputs:

```text
OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json
live_policy_events_total 28
export_policy_events_total 28
live_moncloa_sources_count 2
export_moncloa_source_ids ['moncloa_referencias', 'moncloa_rss_referencias']
all_match True
```

## 4) DoD Check for Tracker Reconciliation

Required wording:
- what is done
- blocker
- one next command

Evidence-backed status decision:
- `TODO` is no longer accurate (ingest + mapping + parity evidence exist and are reproducible).
- `DONE` is not yet justified (strict-network remains blocked; BOE validation still pending).
- Recommended status: `PARTIAL` with explicit blocker proof and one next command.

## 5) Recommended Next Command (single)

```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30
```

Purpose:
- Probe if network blocker is resolved; if still failing, keep documented blocker and continue from-file path.
