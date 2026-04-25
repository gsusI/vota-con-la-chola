# AI-OPS-279 · Objetivos priorizados de scraping para delegacion persona/cargo

## Objetivo
Convertir la cola accionable de regulación delegada en un backlog de scraping ejecutable por paquetes (`institución`) con prioridad reproducible y queries listas para captura de evidencia primaria.

## Cambios
- Nuevo script: `scripts/export_liberty_delegated_person_window_scrape_targets.py`.
  - Reusa cola/review queue de delegación y emite targets `only_actionable`.
  - Asigna `priority_score`/`priority_rank` deterministas por razones de gap y confianza de cadena.
  - Agrupa por `packet_key` (institución) para ejecución por lotes.
  - Publica queries operativas (`search_query_primary`, `search_query_secondary`) y `scrape_goal` por fila.
  - Soporta gate estricto de volumen con `--strict-min-targets`.
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-person-window-scrape-targets`
  - `parl-check-liberty-delegated-person-window-scrape-targets`
  - variables `LIBERTY_DELEGATED_SCRAPE_TARGETS_*`
- Test añadido: `tests/test_export_liberty_delegated_person_window_scrape_targets.py`.

## Corrida real (staging)
DB: `etl/data/staging/politicos-es.db`.

1) Export lane (`parl-export-liberty-delegated-person-window-scrape-targets`):
- `targets_total=8`
- `packets_total=4`
- `top_priority_score=65`
- `lowest_priority_score=30`
- `by_packet={aeat:3, inspeccion-de-trabajo-y-seguridad-social:2, dgt:2, delegaciones-subdelegaciones-del-gobierno:1}`

2) Check estricto (pass-path):
- `LIBERTY_DELEGATED_SCRAPE_TARGETS_STRICT_MIN_TARGETS=1`
- resultado: `status=ok`

3) Check estricto (fail-path contractual):
- `LIBERTY_DELEGATED_SCRAPE_TARGETS_STRICT_MIN_TARGETS=20`
- resultado esperado: `rc=4`

4) Test focal:
- `python3 -m unittest tests/test_export_liberty_delegated_person_window_scrape_targets.py`
- resultado: `Ran 1 test`, `OK`

## Resultado
- Slice cerrado: el backlog de delegación ya tiene una cola de scraping priorizada, paquetizada y reproducible para captura manual/semiautomática de nombramientos y actos de enforcement.
- La fila principal de regulación delegada sigue `PARTIAL` hasta aplicar decisiones revisadas no vacías y reducir `actionable_queue_rows`.
