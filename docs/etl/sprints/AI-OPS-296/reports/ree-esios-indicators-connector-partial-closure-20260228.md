# AI-OPS-296 - Cierre parcial del conector ESIOS/REE (2026-02-28)

## Objetivo
Cerrar el gap estructural de la fila `Indicadores (confusores): ESIOS/REE` del tracker, entregando conector operativo y evidencia reproducible de ingesta, y documentar bloqueo upstream en `strict-network`.

## Cambios entregados
- Nuevo conector `etl/politicos_es/connectors/ree_esios_indicators.py` (`source_id=ree_esios_indicators`) con:
  - parse de payload REE real (`included[].attributes.values`),
  - soporte de contenedor serializado de replay (`{"records": [...]}`),
  - `source_record_id` determinista por serie,
  - rechazo explícito de snapshots legacy `metric,value`,
  - soporte opcional de token (`ESIOS_API_TOKEN`) y cabeceras API.
- Cableado en config/registry + muestra fallback:
  - `etl/politicos_es/config.py`
  - `etl/politicos_es/connectors/__init__.py`
  - `etl/politicos_es/registry.py`
  - `etl/data/raw/samples/ree_esios_indicators_sample.json`
- Integración en estructuración de outcomes y mapeos tracker:
  - `etl/politicos_es/indicator_backfill.py`
  - `etl/politicos_es/cli.py`
  - `scripts/e2e_tracker_status.py`
  - `scripts/graph_ui_server.py`
- Cobertura de tests objetivo (`33 OK`):
  - `tests/test_ree_connector.py`
  - stack de indicator/tracker mapping/parity.

## Evidencia de corrida
- Probe de red estricta (`strict-network`) al endpoint oficial:
  - `HTTP 500`, body HTML, `x-cdn: Imperva`.
  - Evidencia: `docs/etl/sprints/AI-OPS-296/evidence/ree_esios_strict_network_stderr_latest.log`, `ree_esios_curl_headers_latest.txt`, `ree_esios_curl_body_filetype_latest.txt`.
- Ingesta reproducible desde muestra local:
  - DB temporal: `ingestion_runs_ok=1`, `ingestion_runs_error=1`, `source_records_total=2`.
  - DB principal: `run_id=310`, `status=ok`, `records_seen=2`, `records_loaded=2`, `source_records_total=2`.
  - Evidencia: `ree_esios_ingest_status_latest.json`, `ree_esios_main_db_ingestion_runs_latest.txt`, `ree_esios_main_db_source_records_total_latest.txt`.
- Stack de tests:
  - `python3 -m unittest -v tests.test_ree_connector tests.test_indicator_backfill tests.test_graph_ui_server_tracker_mapping tests.test_e2e_tracker_status_tracker tests.test_tracker_contract_parity`
  - Resultado: `Ran 33 tests ... OK`
  - Evidencia: `unittest_ree_tracker_stack_latest.txt`.

## Decisión de estado tracker
- La fila `Indicadores (confusores): ESIOS/REE` pasa de `TODO` a `PARTIAL`.
- Motivo:
  - la parte controlable queda entregada (conector + ingest + tests + wiring),
  - pero no procede `DONE` porque la red real sigue bloqueada (`HTTP 500`/Imperva).

## Siguiente escalación
1. Validar contrato oficial de acceso (token/cabeceras/cuota) para respuesta JSON reproducible.
2. Ejecutar un retry `strict-network` por sprint con delta de evidencia.
3. Cuando pase red real, correr `backfill-indicators --source-ids ree_esios_indicators` y cerrar a `DONE` con evidencia de red.
