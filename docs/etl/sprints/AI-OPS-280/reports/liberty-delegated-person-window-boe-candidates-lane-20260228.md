# AI-OPS-280 · Candidatos BOE de nombramiento para cola delegada

## Objetivo
Convertir los targets priorizados de delegación (`AI-OPS-279`) en evidencia primaria estructurada del BOE para acelerar decisiones `approved/ignored` en la cola review/apply (`AI-OPS-278`).

## Cambios
- Nuevo scraper: `scripts/scrape_liberty_delegated_person_window_boe_candidates.py`.
  - Consume `scrape_targets` CSV y consulta BOE vía `redirector.php?accion=Buscar&bd=boe&texto=...`.
  - Aplica variantes de query reproducibles con expansión de acrónimos (`AEAT`, `DGT`, `ITSS`).
  - Parsea resultados BOE (`li.resultado-busqueda`) y extrae campos estructurados:
    - `candidate_boe_id`, `candidate_doc_url`, `candidate_publication_date`
    - `candidate_department`, `candidate_title`, `candidate_person_hint`
    - `query`, `query_variant`, `candidate_rank`, `candidate_score`.
  - Incluye cache por query para evitar N requests duplicadas y reducir runtime.
  - Gate estricto por volumen con `--strict-min-candidates`.
- Wiring en `justfile`:
  - `parl-scrape-liberty-delegated-person-window-boe-candidates`
  - `parl-check-liberty-delegated-person-window-boe-candidates`
  - variables `LIBERTY_DELEGATED_BOE_CANDIDATES_*`.
- Test añadido: `tests/test_scrape_liberty_delegated_person_window_boe_candidates.py`.

## Corrida real

1) Scrape estructurado (targets AI-OPS-279):
- `targets_total=8`
- `targets_with_results_total=8`
- `candidate_rows_total=40`
- `candidate_unique_boe_ids_total=25`
- `http_errors_total=0`

2) Gate estricto:
- pass-path: `strict_min_candidates=1` -> `status=ok`
- fail-path contractual: `strict_min_candidates=9999` -> `rc=4`

3) Test focal:
- `python3 -m unittest tests/test_scrape_liberty_delegated_person_window_boe_candidates.py`
- resultado: `Ran 4 tests`, `OK`

4) Rendimiento:
- corrida timed con cache: `real 16.34s`

## Resultado
- Slice cerrado: el backlog de delegación ahora tiene una tabla de candidatos BOE reutilizable para revisión humana y posterior `apply` al seed.
- Estado principal permanece `PARTIAL` hasta convertir candidatos en decisiones no vacías (`approved`) y reducir `actionable_queue_rows`.
