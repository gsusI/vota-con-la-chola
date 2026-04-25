# AI-OPS-283 · Cierre de cola delegada por scoring institucional expandido

## Objetivo
Cerrar la cola accionable residual (`3` filas) en regulación delegada mejorando el matching BOE para instituciones en formato acrónimo (`AEAT`, `DGT`, `ITSS`) y ejecutando nuevamente el loop `assist -> auto-review -> apply`.

## Cambios
- Hardening de scoring en `scripts/scrape_liberty_delegated_person_window_boe_candidates.py`:
  - nuevo helper `_institution_tokens()` que combina tokens del valor original + expansión institucional (`INSTITUTION_QUERY_EXPANSIONS`).
  - el score institucional deja de penalizar casos en los que BOE publica el nombre expandido y la semilla usa acrónimo.
- Regresión añadida en `tests/test_scrape_liberty_delegated_person_window_boe_candidates.py`:
  - verifica que `AEAT` incorpora tokens de expansión (`agencia`, `tributaria`).
- Re-ejecución de pipeline de la lane:
  - BOE candidates (AI-OPS-280)
  - review assist (AI-OPS-281)
  - auto-review decisions + apply (AI-OPS-282)
  - replay before/after de cola (AI-OPS-283)

## Corrida real
- `review_links_with_candidates_total`: `5 -> 8`
- `assist_rows_total`: `15 -> 24`
- `relevance_bucket_counts`: `{strong:6, medium:14, weak:4}`
- auto-review:
  - `rows_total=8`
  - `approved_rows_total=8`
  - `pending_rows_total=0`
- apply:
  - `updated_rows=8`
  - `validation.valid=true`
- replay before/after (DB temporal reproducible):
  - `actionable_queue_rows: 8 -> 0` (`delta=-8`)
  - `missing_designated_actor: 2 -> 0`
  - `institutional_designated_actor: 6 -> 0`
  - `missing_enforcement_evidence_date: 1 -> 0`

## Test focal
- `python3 -m unittest tests/test_scrape_liberty_delegated_person_window_boe_candidates.py tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
- resultado: `Ran 8 tests`, `OK`

## Resultado
- Slice cerrado: la cola delegada queda en `0` bajo replay reproducible usando seed actualizado por `apply`.
- Se mantiene follow-up recomendado de control de precisión (muestreo manual de decisiones auto-aprobadas) para evitar sobreajuste semántico de cargo.
