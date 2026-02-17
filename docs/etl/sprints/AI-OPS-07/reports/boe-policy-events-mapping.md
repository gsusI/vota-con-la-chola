# AI-OPS-07 BOE -> policy_events Mapping

Fecha: 2026-02-16  
Repo: `REPO_ROOT/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo

Mapear `source_records` BOE en `policy_events` de forma minima, trazable e idempotente, y dejar hooks basicos para contraste Moncloa-BOE.

## Cambios implementados

1. Mapping BOE en backend ETL
- `etl/politicos_es/policy_events.py`
  - Nuevas funciones:
    - `ensure_boe_policy_instruments(...)`
    - `backfill_boe_policy_events(...)`
  - Instrumentos sembrados:
    - `boe_legal_document`
    - `boe_daily_summary`
  - `policy_event_id` determinista:
    - `boe:{source_id}:{BOE-REF}` (fallback `source_record_id` si no hay referencia BOE)
  - Upsert idempotente con `ON CONFLICT(policy_event_id) DO UPDATE`.

2. Nuevo comando CLI
- `etl/politicos_es/cli.py`
  - comando `backfill-policy-events-boe`
  - default `--source-ids boe_api_legal`

3. Operacion por `just`
- `justfile`
  - receta `etl-backfill-policy-events-boe`

4. Tests focalizados
- `tests/test_boe_policy_events_mapping.py`
  - trazabilidad obligatoria
  - idempotencia en re-run
  - regla de fecha ambigua (`event_date=NULL`, `published_date` preservado)

## Regla de fechas (deterministica)

Para BOE en este sprint:
- `event_date` se mantiene `NULL`.
- `published_date` se toma de `published_at_iso` (YYYY-MM-DD).
- Si falta `published_at_iso`, fallback a `source_snapshot_date`.

Motivo: evitar inferencias no robustas de “fecha efectiva de evento” desde RSS mientras se preserva fecha de publicacion para corroboracion.

## Before / After (staging)

### Before

Comando:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe_before FROM policy_events WHERE source_id LIKE 'boe_%';"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe_with_url_before FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'';"
```

Salida:
```text
policy_events_boe_before
------------------------
0

policy_events_boe_with_url_before
---------------------------------
0
```

### Backfill BOE (run 1)

Comando:
```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db etl/data/staging/politicos-es.db
```

Salida:
```json
{
  "sources": [
    "boe_api_legal"
  ],
  "source_records_seen": 3,
  "source_records_mapped": 3,
  "source_records_skipped": 0,
  "policy_events_upserted": 3,
  "skips": [],
  "policy_events_total": 3,
  "policy_events_with_source_url": 3,
  "policy_events_null_event_date_with_published": 3
}
```

### Backfill BOE (run 2, idempotencia)

Comando:
```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-boe --db etl/data/staging/politicos-es.db
```

Salida:
```json
{
  "sources": [
    "boe_api_legal"
  ],
  "source_records_seen": 3,
  "source_records_mapped": 3,
  "source_records_skipped": 0,
  "policy_events_upserted": 3,
  "skips": [],
  "policy_events_total": 3,
  "policy_events_with_source_url": 3,
  "policy_events_null_event_date_with_published": 3
}
```

### After

Comando:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe_after FROM policy_events WHERE source_id LIKE 'boe_%';"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe_with_url_after FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'';"
```

Salida:
```text
policy_events_boe_after
-----------------------
3

policy_events_boe_with_url_after
--------------------------------
3
```

## Instrumentos BOE sembrados

Comando:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT code, label FROM policy_instruments WHERE code IN ('boe_daily_summary','boe_legal_document') ORDER BY code;"
```

Salida:
```text
code                label
------------------  -------------------
boe_daily_summary   Sumario diario BOE
boe_legal_document  Documento legal BOE
```

## Trazabilidad requerida (BOE)

Comando:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS boe_traceability_full FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'' AND source_record_pk IS NOT NULL AND raw_payload IS NOT NULL AND trim(raw_payload)<>'' AND source_snapshot_date IS NOT NULL AND trim(source_snapshot_date)<>'';"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT policy_event_id, source_id, event_date, published_date, source_url, source_record_pk, source_snapshot_date FROM policy_events WHERE source_id LIKE 'boe_%' ORDER BY policy_event_id;"
```

Salida:
```text
boe_traceability_full
---------------------
3

policy_event_id                    source_id      event_date  published_date  source_url                                                source_record_pk  source_snapshot_date
---------------------------------  -------------  ----------  --------------  --------------------------------------------------------  ----------------  --------------------
boe:boe_api_legal:BOE-A-2026-3482  boe_api_legal              2026-02-15      https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3482  125908            2026-02-16
boe:boe_api_legal:BOE-A-2026-3499  boe_api_legal              2026-02-15      https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-3499  125909            2026-02-16
boe:boe_api_legal:BOE-S-2026-41    boe_api_legal              2026-02-15      https://www.boe.es/boe/dias/2026/02/16/                   125910            2026-02-16
```

## Hooks minimos Moncloa-BOE (corroboracion)

Comando:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) AS c FROM policy_events WHERE source_id IN ('boe_api_legal','moncloa_referencias','moncloa_rss_referencias') GROUP BY source_id ORDER BY source_id;"
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT b.published_date AS published_date, COUNT(DISTINCT b.policy_event_id) AS boe_events, COUNT(DISTINCT m.policy_event_id) AS moncloa_events FROM policy_events b LEFT JOIN policy_events m ON m.source_id LIKE 'moncloa_%' AND m.published_date = b.published_date WHERE b.source_id LIKE 'boe_%' GROUP BY b.published_date ORDER BY b.published_date DESC;"
```

Salida:
```text
source_id                c
-----------------------  --
boe_api_legal            3
moncloa_referencias      20
moncloa_rss_referencias  8

published_date  boe_events  moncloa_events
--------------  ----------  --------------
2026-02-15      3           0
```

## Acceptance query

Comando:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'boe_%';"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'boe_%' AND source_url IS NOT NULL AND trim(source_url)<>'';"
python3 -m unittest discover -s tests -p 'test*boe*py'
```

Salida:
```text
3
3
.....
----------------------------------------------------------------------
Ran 5 tests in 0.168s

OK
```

## Limitaciones actuales

- El slice BOE actual usa feed RSS diario (`boe_api_legal`) y no separa aun actos electorales vs no electorales.
- `event_date` se fija en `NULL` por diseno conservador; la corroboracion temporal se hace con `published_date`.
- El hook Moncloa-BOE en este corte es de bajo nivel (coexistencia por familia de fuente y cruce por fecha de publicacion); matching semantico por contenido queda para la tarea de reconciliacion dedicada.

## Resultado

- BOE -> `policy_events` implementado con upsert idempotente.
- Campos de trazabilidad requeridos preservados en `policy_events`.
- Instrumentos BOE sembrados de forma reproducible.
- Hooks minimos de corroboracion Moncloa-BOE disponibles para siguiente etapa.
