# AI-OPS-04 Moncloa -> policy_events Mapping (T6)

Fecha: 2026-02-16  
Repo: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo

Mapear `source_records` de Moncloa a `policy_events` de forma minima, trazable e idempotente.

## Cambios implementados

1. Nuevo modulo de mapeo:
   - `etl/politicos_es/policy_events.py`
   - `ensure_moncloa_policy_instruments(...)`
   - `backfill_moncloa_policy_events(...)`
2. Nuevo comando CLI:
   - `python3 scripts/ingestar_politicos_es.py backfill-policy-events-moncloa --db <db>`
   - Implementado en `etl/politicos_es/cli.py`
3. Soporte operativo:
   - `justfile`: receta `etl-backfill-policy-events-moncloa`
4. Tests:
   - `tests/test_moncloa_policy_events_mapping.py`

## Reglas de mapeo (KISS)

- `source_id='moncloa_referencias'` -> instrumento `exec_reference`
- `source_id='moncloa_rss_referencias'` -> instrumento `exec_rss_reference`
- `policy_event_id` determinista: `moncloa:{source_id}:{source_record_id}`
- Campos de trazabilidad preservados:
  - `source_id`
  - `source_url`
  - `source_record_pk`
  - `raw_payload`
  - `source_snapshot_date`
- Filtro de ruido:
  - se ignora `source_record_id='referencia:index.aspx'` como fila de discovery/index.

Regla de fecha (escalation_rule):
- Si no se puede extraer `event_date` de forma fiable:
  - mantener `published_date` (si existe),
  - guardar `event_date = NULL`.

## Comandos y evidencia

### 1) Tests

Comando:
```bash
python3 -m unittest tests.test_moncloa_policy_events_mapping
```
Salida:
```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.111s

OK
```

Comando:
```bash
python3 -m unittest tests.test_moncloa_connectors
```
Salida:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.143s

OK
```

Comando:
```bash
python3 -m unittest tests.test_samples_e2e
```
Salida:
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.524s

OK
```

### 2) Backfill de mapping

Comando:
```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-moncloa --db etl/data/staging/politicos-es.db
```
Salida:
```json
{
  "sources": [
    "moncloa_referencias",
    "moncloa_rss_referencias"
  ],
  "source_records_seen": 7,
  "source_records_mapped": 6,
  "source_records_skipped": 1,
  "policy_events_upserted": 6,
  "skips": [
    {
      "source_id": "moncloa_referencias",
      "source_record_id": "referencia:index.aspx",
      "reason": "discovery_index_row"
    }
  ],
  "policy_events_total": 6,
  "policy_events_with_source_url": 6,
  "policy_events_null_event_date_with_published": 0
}
```

Re-ejecucion idempotente (mismo comando, misma salida agregada):
- `policy_events_total` se mantiene en `6`.

### 3) Instrumentos sembrados

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT code, label FROM policy_instruments WHERE code LIKE 'exec_%' ORDER BY code;"
```
Salida:
```text
exec_reference|Referencia del Consejo de Ministros
exec_rss_reference|RSS de referencias/resumenes del Consejo de Ministros
```

### 4) Acceptance query

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```
Salida:
```text
6
```

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'moncloa_%' AND source_url IS NOT NULL AND trim(source_url)<>'';"
```
Salida:
```text
6
```

### 5) Trazabilidad por fila (muestra)

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT policy_event_id, source_id, event_date, published_date, source_url, source_record_pk, source_snapshot_date FROM policy_events WHERE source_id LIKE 'moncloa_%' ORDER BY source_id, policy_event_id LIMIT 20;"
```

Salida (extracto):
```text
moncloa:moncloa_referencias:referencia:20260203-referencia-rueda-de-prensa-ministros.aspx|moncloa_referencias|2026-02-03|2026-02-03|https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20260203-referencia-rueda-de-prensa-ministros.aspx|125640|
moncloa:moncloa_referencias:referencia:20260210-referencia-rueda-de-prensa-ministros.aspx|moncloa_referencias|2026-02-10|2026-02-10|https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20260210-referencia-rueda-de-prensa-ministros.aspx|125641|
moncloa:moncloa_rss_referencias:tipo16:20260120-referencia-rueda-de-prensa-ministros.aspx|moncloa_rss_referencias|2026-01-20|2026-01-20|https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20260120-referencia-rueda-de-prensa-ministros.aspx|125646|
...
```

### 6) Integridad referencial

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;" | wc -l
```
Salida:
```text
0
```

## Resultado

- Mapping Moncloa -> `policy_events` implementado y reproducible.
- Trazabilidad conservada en todos los eventos mapeados.
- Upsert idempotente validado por tests y re-ejecucion.
