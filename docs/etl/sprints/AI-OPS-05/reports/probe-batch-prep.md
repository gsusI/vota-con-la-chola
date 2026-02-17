# Probe Batch Prep — AI-OPS-05 (P3)

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Scope

Prepare deterministic probe matrix for:
- moncloa (`moncloa_referencias`, `moncloa_rss_referencias`)
- navarra (`parlamento_navarra_parlamentarios_forales`)
- galicia (`parlamento_galicia_deputados`)

Modes prepared per source:
- `strict-network` probe
- `from-file` replay

## Batch Folder Created

- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/`

Core batch files:
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/run-probe-matrix.sh`
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/command-matrix.tsv`
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/probe_snapshot_queries.sql`

## From-file Asset Readiness (escalation_rule)

| source_id | from-file asset | readiness check | blocker |
|---|---|---|---|
| `moncloa_referencias` | `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216` | `manifest.json` present | none |
| `moncloa_rss_referencias` | `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216` | `manifest.json` present | none |
| `parlamento_navarra_parlamentarios_forales` | `etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages` | 50 `.html` files | none |
| `parlamento_galicia_deputados` | `etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages` | 75 `.html` files | none |

Escalation rule result:
- No source is missing reproducible `from-file` input in this batch.
- No explicit `from-file` blocker opened for this prep.

## Deterministic Command Matrix

DB target for probe batch:
- `etl/data/staging/probe-matrix-20260216.db`

Snapshot date:
- `2026-02-16`

Init command:

```bash
python3 scripts/ingestar_politicos_es.py init-db --db etl/data/staging/probe-matrix-20260216.db
```

Per-source/per-mode commands are pinned in:
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/command-matrix.tsv`

Direct examples:

```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source moncloa_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source moncloa_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30

python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source moncloa_rss_referencias --snapshot-date 2026-02-16 --strict-network --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source moncloa_rss_referencias --from-file etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216 --snapshot-date 2026-02-16 --timeout 30

python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-16 --strict-network --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source parlamento_navarra_parlamentarios_forales --from-file etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages --snapshot-date 2026-02-16 --timeout 30

python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source parlamento_galicia_deputados --snapshot-date 2026-02-16 --strict-network --timeout 30
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/probe-matrix-20260216.db --source parlamento_galicia_deputados --from-file etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages --snapshot-date 2026-02-16 --timeout 30
```

## Pre-created Evidence Capture Files

All required captures were pre-created in:
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/logs/`
- `docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/sql/`

Prepared artifacts include:
- `init-db.stdout.log` / `init-db.stderr.log`
- For each source x mode (`strict-network`, `from-file`):
  - `<source>__<mode>.stdout.log`
  - `<source>__<mode>.stderr.log`
  - `<source>__<mode>__run_snapshot.csv`
  - `<source>__<mode>__source_records_snapshot.csv`

Runner behavior:
- `run-probe-matrix.sh` captures stdout/stderr per command and writes SQL snapshots after each probe, including failed strict-network runs (deterministic failure evidence).
