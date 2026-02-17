# AI-OPS-04 Moncloa Connector Implementation (T4)

Fecha: 2026-02-16  
Repo: `REPO_ROOT/vota-con-la-chola`

## Objetivo

Implementar conectores de ingesta para `La Moncloa referencias + RSS` con trazabilidad e idempotencia, integrados al pipeline de `scripts/ingestar_politicos_es.py`.

## Cambios aplicados

1. Nuevos `source_id` en `etl/politicos_es/config.py`:
   - `moncloa_referencias`
   - `moncloa_rss_referencias`
2. Nuevos conectores en `etl/politicos_es/connectors/moncloa_exec.py`:
   - `MoncloaReferenciasConnector`
   - `MoncloaRssReferenciasConnector`
3. Registro de conectores:
   - `etl/politicos_es/connectors/__init__.py`
   - `etl/politicos_es/registry.py`
4. Soporte de modo de ingesta trazabilidad-only en pipeline:
   - `etl/politicos_es/connectors/base.py` (`ingest_mode`)
   - `etl/politicos_es/pipeline.py` (`source_records_only`)
5. Fixtures de muestra reproducibles:
   - `etl/data/raw/samples/moncloa_referencias_sample.html`
   - `etl/data/raw/samples/moncloa_rss_referencias_sample.xml`
6. Tests:
   - `tests/test_moncloa_connectors.py` (estabilidad parser + idempotencia Moncloa)
   - `tests/test_samples_e2e.py` actualizado para soportar fuentes `source_records_only`

## Comandos ejecutados y resultados

### 1) Tests de conectores Moncloa

Comando:
```bash
python3 -m unittest tests.test_moncloa_connectors
```

Salida:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.077s

OK
```

### 2) Test de idempotencia global de samples

Comando:
```bash
python3 -m unittest tests.test_samples_e2e
```

Salida:
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.437s

OK
```

### 3) Ingesta reproducible `from-file` (Moncloa)

Comando:
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --from-file etl/data/raw/samples/moncloa_referencias_sample.html --strict-network
```

Salida:
```text
moncloa_referencias: 3/3 registros validos [from-file]
Total: 3/3 registros validos
```

Comando:
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_rss_referencias --from-file etl/data/raw/samples/moncloa_rss_referencias_sample.xml --strict-network
```

Salida:
```text
moncloa_rss_referencias: 4/4 registros validos [from-file]
Total: 4/4 registros validos
```

### 4) Evidencia de trazabilidad en DB

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS source_records_total FROM source_records WHERE source_id LIKE 'moncloa_%' GROUP BY source_id ORDER BY source_id;"
```

Salida:
```text
moncloa_referencias|3
moncloa_rss_referencias|4
```

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS raw_fetches_total FROM raw_fetches WHERE source_id LIKE 'moncloa_%' GROUP BY source_id ORDER BY source_id;"
```

Salida:
```text
moncloa_referencias|1
moncloa_rss_referencias|1
```

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS run_fetches_total FROM run_fetches WHERE source_id LIKE 'moncloa_%' GROUP BY source_id ORDER BY source_id;"
```

Salida:
```text
moncloa_referencias|1
moncloa_rss_referencias|1
```

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, records_loaded FROM ingestion_runs WHERE source_id LIKE 'moncloa_%' ORDER BY run_id DESC LIMIT 10;"
```

Salida:
```text
moncloa_rss_referencias|4
moncloa_rss_referencias|0
moncloa_referencias|3
```

Nota operativa: la fila `moncloa_rss_referencias|0` corresponde a un intento concurrente que fallo por `database is locked` (SQLite con dos escritores a la vez). Reejecucion secuencial posterior: `4/4` en verde.

### 5) Integridad referencial post-cambios

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;" | wc -l
```

Salida:
```text
0
```

## Manejo de drift de contrato (regla de escalado)

- En modo red, ambos conectores capturan errores parciales por feed/detail y devuelven `note=network-with-partial-errors (...)` cuando aplica.
- Con `--strict-network`, errores de red/contrato elevan fallo.
- Sin `--strict-network`, se usa fallback de muestra y se conserva motivo explicito en `note=network-error-fallback: ...`.

Con esto, la ingesta Moncloa queda no-fatal por defecto y trazable para debugging/ops.
