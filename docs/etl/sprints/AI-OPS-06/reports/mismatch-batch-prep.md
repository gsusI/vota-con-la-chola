# Mismatch batch prep report (AI-OPS-06)

- Timestamp UTC: 2026-02-16T17:03:19Z
- Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`
- DB: `etl/data/staging/politicos-es.db`
- Live inputs: `docs/etl/e2e-scrape-load-tracker.md`, `docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md`, `ingestion_runs`/`run_fetches`

## 1) Live tracker command log

```bash
just etl-tracker-status | tee docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-tracker-status.log
```

Observed:
- mismatches: `3`
- waived_mismatches: `0`
- done_zero_real: `0`
- mismatch source_ids: `moncloa_referencias`, `moncloa_rss_referencias`, `parlamento_navarra_parlamentarios_forales`

## 2) SQL extracts attached

```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "WITH metrics AS (SELECT s.source_id AS source_id, COUNT(ir.run_id) AS runs_total, SUM(CASE WHEN ir.status = 'ok' THEN 1 ELSE 0 END) AS runs_ok, COALESCE(MAX(ir.records_loaded), 0) AS max_loaded_any, COALESCE(MAX(CASE WHEN rf.source_url LIKE 'http%' THEN ir.records_loaded ELSE NULL END), 0) AS max_loaded_network, COALESCE((SELECT ir2.records_loaded FROM ingestion_runs ir2 WHERE ir2.source_id = s.source_id ORDER BY ir2.run_id DESC LIMIT 1), 0) AS last_loaded FROM sources s LEFT JOIN ingestion_runs ir ON ir.source_id=s.source_id LEFT JOIN run_fetches rf ON rf.run_id = ir.run_id GROUP BY s.source_id ORDER BY s.source_id);" > docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-source-metrics.csv

sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT s.source_id, ir.run_id, ir.started_at, ir.finished_at, ir.status AS run_status, ir.source_url AS run_source_url, ir.records_seen, ir.records_loaded, ir.message, rf.rowid AS fetch_rowid, rf.source_url AS fetch_source_url, rf.fetched_at, rf.content_sha256, rf.bytes FROM (SELECT 'moncloa_referencias' AS source_id UNION ALL SELECT 'moncloa_rss_referencias' UNION ALL SELECT 'parlamento_navarra_parlamentarios_forales') s JOIN ingestion_runs ir ON ir.source_id = s.source_id LEFT JOIN run_fetches rf ON rf.run_id = ir.run_id ORDER BY s.source_id, ir.run_id, rf.rowid;" > docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-fetches.csv

sqlite3 -header -csv etl/data/staging/politicos-es.db "SELECT DISTINCT s.source_id, COUNT(ir.run_id) AS runs_total, SUM(CASE WHEN ir.status = 'ok' THEN 1 ELSE 0 END) AS runs_ok, COALESCE(MAX(ir.records_loaded),0) AS max_any, COALESCE(MAX(CASE WHEN rf.source_url LIKE 'http%' THEN ir.records_loaded ELSE NULL END),0) AS max_net, COALESCE((SELECT ir2.records_loaded FROM ingestion_runs ir2 WHERE ir2.source_id=s.source_id ORDER BY ir2.run_id DESC LIMIT 1),0) AS last_loaded FROM sources s LEFT JOIN ingestion_runs ir ON ir.source_id=s.source_id LEFT JOIN run_fetches rf ON rf.run_id=ir.run_id WHERE s.source_id IN ('moncloa_referencias','moncloa_rss_referencias','parlamento_navarra_parlamentarios_forales') GROUP BY s.source_id ORDER BY s.source_id;" > docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-only-metrics.csv
```

## 3) generated outputs

### mismatch_candidates.csv

```csv
source_id,checklist_status,sql_status,runs_ok_total,max_net,max_any,last_loaded,blocker_note
moncloa_referencias,PARTIAL,DONE,7/8,2,20,20,"Ingesta y normalización reproducibles con replay (`--from-file`) y trazabilidad confirmada (`policy_events=28`, `source_id/source_url` completos). `--strict-network` muestra cargas en este entorno (reusable en pipeline), pero completa DoD y validación contra BOE/contexto normativo siguen pendientes. Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`."
moncloa_rss_referencias,PARTIAL,DONE,8/10,8,8,8,"Ingesta y normalización reproducibles con replay (`--from-file`) y trazabilidad confirmada (`policy_events=28`, `source_id/source_url` completos). `--strict-network` muestra cargas en este entorno (reusable en pipeline), pero completa DoD y validación contra BOE/contexto normativo siguen pendientes. Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`."
parlamento_navarra_parlamentarios_forales,PARTIAL,DONE,3/8,50,50,50,Bloqueado por 403 en `--strict-network` (no carga en red). Reproducible fallback con `--from-file etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages` (`50/50` válido) para continuidad operativa. Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --strict-network --timeout 30`.
```

### waiver_candidates.csv

```csv
source_id,reason,owner,expires_on,evidence_path
moncloa_referencias,TEMP_WAIVER_CANDIDATE: tracker remains PARTIAL while SQL reports DONE; requires explicit policy decision (reconcile vs waive).,L2,2026-02-20,docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-tracker-status.log;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-only-metrics.csv;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-fetches.csv;docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md
moncloa_rss_referencias,TEMP_WAIVER_CANDIDATE: tracker remains PARTIAL while SQL reports DONE; requires explicit policy decision (reconcile vs waive).,L2,2026-02-20,docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-tracker-status.log;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-only-metrics.csv;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-fetches.csv;docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md
parlamento_navarra_parlamentarios_forales,TEMP_WAIVER_CANDIDATE: blocked network replay semantics despite fallback load and tracker PARTIAL; confirm policy action path.,L2,2026-02-20,docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-tracker-status.log;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-only-metrics.csv;docs/etl/sprints/AI-OPS-06/evidence/mismatch-batch-prep-mismatch-fetches.csv;docs/etl/sprints/AI-OPS-05/evidence/tracker-reconciliation.md
```

## 4) Escalation/resolution rule check

- Reproducible evidence pointers present for all mismatch sources:
  - `moncloa_referencias`
  - `moncloa_rss_referencias`
  - `parlamento_navarra_parlamentarios_forales`
- No mismatch source lacks evidence pointers under current artifacts.
- Therefore no row is marked unresolved in `waiver_candidates.csv`.
- `blocker_note` is preserved from tracker row text for traceability.

## 5) Output contract validation (manual)

```bash
test -f docs/etl/sprints/AI-OPS-06/exports/mismatch_candidates.csv
test -f docs/etl/sprints/AI-OPS-06/exports/waiver_candidates.csv
rg -n "source_id,checklist_status,sql_status|expires_on|owner" docs/etl/sprints/AI-OPS-06/exports/*.csv
```

Expected:
- both export files exist
- headers include required columns
