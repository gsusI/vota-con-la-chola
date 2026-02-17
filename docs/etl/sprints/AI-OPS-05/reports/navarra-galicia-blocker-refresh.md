# Navarra/Galicia Blocker Refresh — AI-OPS-05

Date: 2026-02-16  
Repository: `REPO_ROOT/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

## Objective
Refresh blocker evidence for Navarre and Galicia using strict-network probes plus from-file replays to preserve a PARTIAL status posture without false DONE promotion.

## Commands Executed

Source-level command set used:

- `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --strict-network --timeout 30`
  - stdout: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_navarra_parlamentarios_forales__strict-network.stdout.log`
  - stderr: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_navarra_parlamentarios_forales__strict-network.stderr.log`
  - SQL: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/parlamento_navarra_parlamentarios_forales__strict-network__run_snapshot.csv`

- `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --from-file etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages --snapshot-date 2026-02-16 --timeout 30`
  - stdout: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_navarra_parlamentarios_forales__from-file.stdout.log`
  - stderr: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_navarra_parlamentarios_forales__from-file.stderr.log`
  - SQL: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/parlamento_navarra_parlamentarios_forales__from-file__run_snapshot.csv`

- `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-16 --strict-network --timeout 30`
  - stdout: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_galicia_deputados__strict-network.stdout.log`
  - stderr: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_galicia_deputados__strict-network.stderr.log`
  - SQL: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/parlamento_galicia_deputados__strict-network__run_snapshot.csv`

- `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --from-file etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages --snapshot-date 2026-02-16 --timeout 30`
  - stdout: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_galicia_deputados__from-file.stdout.log`
  - stderr: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/parlamento_galicia_deputados__from-file.stderr.log`
  - SQL: `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/parlamento_galicia_deputados__from-file__run_snapshot.csv`

## Evidence Queries (session-scoped, latest 2 runs/source)

```bash
sqlite3 etl/data/staging/politicos-es.db "WITH ranked AS (SELECT source_id, run_id, status, records_loaded, source_url, message, ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY run_id DESC) AS rn FROM ingestion_runs WHERE source_id IN ('parlamento_navarra_parlamentarios_forales','parlamento_galicia_deputados')) SELECT source_id, COUNT(*) AS runs_total, SUM(status='ok') AS runs_ok, MAX(CASE WHEN source_url NOT LIKE 'file://%' THEN records_loaded ELSE 0 END) AS max_net, MAX(records_loaded) AS max_any, MAX(CASE WHEN rn=1 THEN records_loaded END) AS last_loaded FROM ranked WHERE rn <= 2 GROUP BY source_id;"
```

```text
parlamento_galicia_deputados|2|1|0|75|75
parlamento_navarra_parlamentarios_forales|2|1|0|50|50
```

```bash
sqlite3 etl/data/staging/politicos-es.db "WITH ranked AS (SELECT source_id, run_id, status, records_loaded, source_url, message, ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY run_id DESC) AS rn FROM ingestion_runs WHERE source_id IN ('parlamento_navarra_parlamentarios_forales','parlamento_galicia_deputados')) SELECT source_id, run_id, rn, status, records_loaded, source_url, message FROM ranked WHERE rn <= 2 ORDER BY source_id, rn;"
```

```text
parlamento_galicia_deputados|172|1|ok|75|file://REPO_ROOT/vota-con-la-chola/etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages|Ingesta completada: 75/75 registros validos (from-dir)
parlamento_galicia_deputados|171|2|error|0|https://www.parlamentodegalicia.gal/Composicion/Deputados|Error: HTTP Error 403: Forbidden
parlamento_navarra_parlamentarios_forales|170|1|ok|50|file://REPO_ROOT/vota-con-la-chola/etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages|Ingesta completada: 50/50 registros validos (from-dir)
parlamento_navarra_parlamentarios_forales|169|2|error|0|https://parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales|Error: HTTP Error 403: Forbidden
```

## Per-Source Summary

| source_id | strict-network runs_ok/total | from-file runs_ok/total | max_net | max_any | last_loaded | blocker_signature |
|---|---:|---:|---:|---:|---:|---|
| parlamento_navarra_parlamentarios_forales | 0/1 | 1/1 | 0 | 50 | 50 | 403 Forbidden |
| parlamento_galicia_deputados | 0/1 | 1/1 | 0 | 75 | 75 | 403 Forbidden |

Observed signatures:
- `strict-network` for both sources resolves to `HTTP Error 403: Forbidden` (no `challenge`/`WAF` token in current traces).
- `from-file` replay succeeds for both using local captures:
  - `etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages` (50 records)
  - `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages` (75 records)

## Escalation Rule

No unexpected stable strict-network success appeared in this refresh run.
- Status remains **PARTIAL-compatible** for both rows.
- No L2 escalation required for now.
- Next command for explicit blocker confirmation if needed: repeat strict-network probes during next matrix window with rotated network context and capture fresh `run_id`/stderr hashes.

