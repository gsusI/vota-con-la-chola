# Name-and-Shame Draft Update (AI-OPS-26)

Purpose:
- Draft append-only updates for `docs/etl/name-and-shame-access-blockers.md` based on fresh strict-network evidence.

## Candidate append entries

1. `Parlamento de Galicia` (`parlamento_galicia_deputados`)
- first/last seen UTC in this sprint: `2026-02-19T16:15:13Z` / `2026-02-19T16:15:14Z`
- reproducible command:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_galicia_deputados --snapshot-date 2026-02-19 --strict-network --timeout 30`
- failure signal:
  - `HTTP Error 403: Forbidden`
- evidence:
  - `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
  - `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`

2. `Parlamento de Navarra` (`parlamento_navarra_parlamentarios_forales`)
- first/last seen UTC in this sprint: `2026-02-19T16:15:14Z` / `2026-02-19T16:15:15Z`
- reproducible command:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source parlamento_navarra_parlamentarios_forales --snapshot-date 2026-02-19 --strict-network --timeout 30`
- failure signal:
  - `HTTP Error 403: Forbidden`
- evidence:
  - `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
  - `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`

3. `AEMET OpenData` (`aemet_opendata_series`)
- first/last seen UTC in this sprint: `2026-02-19T16:15:09Z` / `2026-02-19T16:15:10Z`
- reproducible command:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --url https://opendata.aemet.es/opendata/api/observacion/convencional/todas --snapshot-date 2026-02-19 --strict-network --timeout 30`
- failure signal:
  - `Error: Expecting value: line 1 column 1 (char 0)`
- evidence:
  - `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
  - `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`

4. `Banco de España API` (`bde_series_api`)
- first/last seen UTC in this sprint: `2026-02-19T16:15:10Z` / `2026-02-19T16:15:13Z`
- reproducible command:
  - `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --url https://api.bde.es/datos/series/PARO.TASA.ES.M --snapshot-date 2026-02-19 --strict-network --timeout 30`
- failure signal:
  - `error: [Errno 8] nodename nor servname provided, or not known`
- evidence:
  - `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
  - `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`

## Editorial check

- factual wording only
- no motive claims
- append-only update style
- explicit next escalation action per entry
