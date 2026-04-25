# Source Scrape Queue Execution Contract (`2026-04-13`)

## Donde estamos ahora

- El repo ya publica el universo de fuentes y una cola de scraping derivada, pero la cola todavia no diferenciaba bien entre fuentes verificadas por red, fuentes reproducibles solo desde muestra y fuentes que siguen bloqueadas.
- Eso hacia que el backlog de cobertura total siguiera siendo parcialmente manual: habia ranking, pero no un contrato estable de ejecucion por fuente o por lote.
- El rerun validado sobre la cola (`one-go-r3`) ya cerro el bug operativo principal: `congreso_intervenciones` pasa de `records_loaded=0` a `records_loaded=9` cuando la cola ejecuta antes `congreso_votaciones`, `link-votes` y `backfill-topic-analytics`.
- Las pseudo-fuentes derivadas `bdns_subvenciones` y `placsp_contratacion` ya no aparecen como fallos falsos: quedan `skipped/no_command_available` y fuera de la ruta `ingest --source ...`.
- El estado que queda abierto despues del rerun no es un bug de orquestacion sino deuda de umbrales/muestras en ocho fuentes reproducibles y tres lanes externos/manuales.

## Hacia donde vamos

- La cola publica debe funcionar como control plane reproducible para cerrar cobertura por `source_id`, no solo como dashboard.
- Cada item debe decir con claridad:
  - que script lo ejecuta
  - cual es su objetivo minimo estricto
  - si existe muestra local reproducible
  - si el siguiente paso preferente es `strict-network`, `from-file` o `manual_capture`
  - en que lote/batch entra

## Que sigue

- Consumir `source-scrape-queue` desde operacion/UI para lanzar batches por `priority_band`, `queue_reason`, `scope` y `repeatability_state`.
- Convertir los casos `manual_capture_required` en paquetes reproducibles de adquisicion/evidencia en vez de reintentos ad hoc.
- Mantener la regla de no fingir `DONE` cuando el upstream siga bloqueado: si no hay red real, debe quedar visible como `blocked_*` o como replay desde muestra.
- Revisar los `strict_target` y/o las muestras de las ocho fuentes que siguen `records_loaded_below_target`, para que la cola distinga mejor entre cobertura parcial aceptable y fallo real de reproducibilidad.

## Evidencia

- `docs/etl/runs/source-scrape-queue-run-2026-04-13-one-go-r3-summary.json`
- `scripts/run_source_scrape_queue.py`
- `scripts/graph_ui_server.py`
- `scripts/export_source_scrape_queue_snapshot.py`
- `tests/test_run_source_scrape_queue.py`
- `tests/test_export_source_catalog_snapshot.py`
- `tests/test_export_source_scrape_queue_snapshot.py`
- `tests/test_congreso_votaciones_samples_e2e.py`
- `tests/test_congreso_intervenciones_samples_e2e.py`
