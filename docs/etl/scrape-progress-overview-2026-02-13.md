# Scrape & ETL Progress Overview

Date: Friday, 2026-02-13  
Reference DB: `etl/data/staging/politicos-es.db`  
Published snapshot files reviewed: `etl/data/published/*-2026-02-12.json`  
Tracker reference: `docs/etl/e2e-scrape-load-tracker.md` and `scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db`

## Executive snapshot

- Tracked data-types: `28`  
- Sources present in DB registry: `29`  
- Tracker mismatch count: `7`  
- `done_zero_real`: `4`  
- Ingestion runs: `103` total (`81` `ok`, `22` `error`)  
- Total mandates: `77,179`  
- Active mandates: `68,460`  
- Raw rows in `source_records`: `87,059`  
- Vote events: `5,835`  
- Roll-call rows: `355,996`  
- Initiatives: `4,036`  
- Persons mapped in roll-call: `221,519` (`62.2%`), missing `134,477`  
- `parl_vote_events` by source:
  - `congreso_votaciones`: `301`
  - `senado_votaciones`: `5,534`
- `parl_vote_member_votes` by source:
  - `congreso_votaciones`: `105,350` votes (`98.99%` with `person_id`)
  - `senado_votaciones`: `250,646` votes (`46.77%` with `person_id`)
- `parl_initiatives` by source:
  - `congreso_iniciativas`: `429`
  - `senado_iniciativas`: `3,607`
- Published artifacts:
  - `representantes-es-2026-02-12.json`: `2374` records in `totales.items`
  - `votaciones-es-2026-02-12.json`: `5,835` eventos, `183,811` votos nominales, `178,163` with `person_id`
  - `infoelectoral-es-2026-02-12.json`: `2` source_ids, `2` archivos_extraccion, `1` convocatoria, `2` procesos, `3` resultados

## High-level tracker status (per docs + tracker check)

- Tracker macro: `22` DONE, `5` PARTIAL, `5` TODO
- `scripts/e2e_tracker_status.py` adds operational flags for the same set:
  - MISMATCH: `7`
  - `DONE_ZERO_REAL`: `4`

## What is scraped (mandatos)

Configured representative sources (`etl/politicos_es/config.py`): `23`

| source_id | total mandates | active mandates |
|---|---:|---:|
| asamblea_ceuta_diputados | 25 | 25 |
| asamblea_extremadura_diputados | 65 | 65 |
| asamblea_madrid_ocupaciones | 9,188 | 724 |
| asamblea_melilla_diputados | 26 | 26 |
| asamblea_murcia_diputados | 54 | 45 |
| congreso_diputados | 352 | 350 |
| cortes_aragon_diputados | 0 | 0 |
| cortes_clm_diputados | 33 | 33 |
| cortes_cyl_procuradores | 81 | 81 |
| cortes_valencianes_diputats | 0 | 0 |
| europarl_meps | 62 | 60 |
| jgpa_diputados | 45 | 45 |
| municipal_concejales | 66,101 | 66,101 |
| parlamento_andalucia_diputados | 109 | 109 |
| parlamento_canarias_diputados | 79 | 70 |
| parlamento_cantabria_diputados | 35 | 35 |
| parlamento_galicia_deputados | 75 | 75 |
| parlamento_larioja_diputados | 33 | 33 |
| parlament_balears_diputats | 59 | 59 |
| parlament_catalunya_diputats | 135 | 135 |
| parlamento_navarra_parlamentarios_forales | 50 | 50 |
| parlamento_vasco_parlamentarios | 75 | 75 |
| senado_senadores | 497 | 264 |

## What is still pending / partially complete

- Congress voting:
  - Core events and initiatives are present, but not yet stable enough for full DoD (`PARTIAL` in tracker and status mismatch signals).
- Senate voting:
  - Event + totals extraction exists, person linking and KPIs still incomplete (`PARTIAL` + mismatch).
- Galicia and Navarra representative mandates:
  - Both currently rely on non-primary retrieval paths in some runs and are flagged as partial quality-wise.
- Municipal territory catalogues:
  - REL/INE/IGN references not yet canonized (`TODO` in tracker docs).
- Electoral process metadata:
  - Convocatorias JEC, Marco Legal BOE, Congreso intervenciones, declared party positions are still unimplemented (`TODO` family).
- Quality debt observed from tracker:
  - `cortes_aragon_diputados`, `cortes_valencianes_diputats`, `infoelectoral_descargas`, `infoelectoral_procesos` are `DONE_ZERO_REAL` in status check (non-zero SQL data mismatch vs checklist expectation).

## Practical interpretation

- Most person-level structured scraping is in place (`mandatos`, Congress/Senate votes, initiatives, representative rosters).
- The backlog is now mostly governance/quality and parity work: unblock partial blockers (WAF/coverage gaps), finish Congress/Senate voting hardening, and ingest remaining TODO domains (territorial/electoral/legal/reference corpora).

## Pending work to resume (next actions)

1. `congreso_votaciones` (PARTIAL, mismatch)
   - Complete event-to-initiative linkage consistency and rerun congress quality publish gate.
   - Validate `parl_vote_events=301` + unmatched linkage for `senado/congreso` cross-source KPIs.

2. `senado_votaciones` (PARTIAL, mismatch)
   - Finish Senate vote-person linkage quality (`senado_votaciones` has `5,534` events and `250,646` nominal votes, only `46.77%` mapped).
   - Confirm `senado_mociones` linkage to `parl_initiatives` and improve identifier normalization.

3. `cortes_aragon_diputados` (DONE technically, PARTIAL operationally)
   - Current source shows `0` mandates in DB in strict comparison despite expected structure.
   - Reconcile manifest with canonical parser and source row handling in tracker status.

4. `cortes_valencianes_diputats` (DONE in code, but `DONE_ZERO_REAL`)
   - Reconcile expected/actual counts and confirm data source path is producing non-zero real network rows.

5. `infoelectoral_descargas` / `infoelectoral_procesos` (`DONE_ZERO_REAL` in checks)
   - Keep under close watch: checklist marks complete, but strict check sees zero real rows for some phases.
   - Run ingestion with latest sample/response fixtures and confirm strict-network invariants.

6. `convocatorias_jec` (TODO)
   - Missing connector for convocatorias + estado electoral.

7. `marco_legal_boe` (TODO)
   - Missing legal BOE catalog ingestion + normalized docs model.

8. `congreso_intervenciones` (TODO)
   - Missing textual intervention connector and evidence model.

9. `referencias_territoriales` (TODO)
   - Missing canonical catalog for REL/INE/IGN references.

10. `posiciones_declaradas_programas` (TODO)
   - Missing NLP/curation pipeline for party program positions and revision workflow.

## Quick runbook to continue

- Run remaining population extraction through `just`:
  - `just etl-poblacion-municipios-json`
  - `just etl-poblacion-municipios-2025`
- Resume parliamentary quality pipeline when ready:
  - `just parl-quality-pipeline`
  - `just etl-publish-votaciones`
