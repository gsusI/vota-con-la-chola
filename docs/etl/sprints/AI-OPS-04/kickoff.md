# Sprint AI-OPS-04 Kickoff

Fecha de baseline: 2026-02-16  
Repo: `REPO_ROOT/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo del sprint (congelado)

Ejecutar el primer slice fuera del parlamento en la ruta critica del roadmap: `Accion ejecutiva (Consejo de Ministros)` (`La Moncloa: referencias + RSS`), moviendo su fila de tracker de `TODO` a `PARTIAL` con evidencia reproducible y trazabilidad en `policy_events`.

## Contexto de alineacion (roadmap + closeout previo)

Entradas leidas para este kickoff:
- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-03/closeout.md`

Anclaje de ruta critica:
- `docs/roadmap.md` (4.3): siguiente desbloqueo de valor es anadir una fuente de accion fuera del parlamento como `policy_events` trazables.
- `docs/roadmap-tecnico.md` (Fase 1): doble entrada para acciones (senal comunicacional + validacion contra registros con efectos cuando aplique).
- `docs/etl/e2e-scrape-load-tracker.md`: fila `Accion ejecutiva (Consejo de Ministros)` esta en `TODO`.
- `docs/etl/sprints/AI-OPS-03/closeout.md`: AI-OPS-03 abre AI-OPS-04 con familia unica Moncloa.

## Baseline kickoff (comandos y salidas exactas)

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Salida exacta:

```text
0
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_total FROM policy_events;"
```

Salida exacta:

```text
0
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_instruments_total FROM policy_instruments;"
```

Salida exacta:

```text
0
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, is_active, name FROM sources WHERE lower(source_id) LIKE '%moncloa%' OR lower(name) LIKE '%moncloa%' OR lower(name) LIKE '%consejo de ministros%';"
```

Salida exacta:

```text
```

Interpretacion de la salida exacta anterior: sin filas (stdout vacio).

Chequeo auxiliar de conteo (solo para evitar ambiguedad de stdout vacio):

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS moncloa_sources_total FROM sources WHERE lower(source_id) LIKE '%moncloa%' OR lower(name) LIKE '%moncloa%' OR lower(name) LIKE '%consejo de ministros%';"
```

```text
0
```

## Gates AI-OPS-04 (bloqueados)

| Gate | Criterio de aceptacion | Evidencia de cierre esperada |
|---|---|---|
| G1 Integridad | `fk_violations = 0` al cierre | `sqlite3 ... "SELECT COUNT(*) FROM pragma_foreign_key_check;"` |
| G2 Onboarding fuente | Existe al menos un `source_id` Moncloa activo (`is_active=1`) | `sqlite3 ... "SELECT source_id,is_active,name FROM sources WHERE ...;"` |
| G3 Ingesta reproducible | Al menos una corrida reproducible (`--strict-network` o `--from-file`) con `records_loaded > 0` para `source_id LIKE 'moncloa_%'` | `sqlite3 ... "SELECT source_id, records_loaded, run_mode FROM ingestion_runs ..."` + reporte de matriz |
| G4 Modelo de accion | `policy_instruments_total > 0` y `policy_events` de Moncloa `> 0` | `sqlite3 ... "SELECT COUNT(*) FROM policy_instruments;"` + `sqlite3 ... "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'moncloa_%';"` |
| G5 Trazabilidad de eventos | Para `policy_events` Moncloa: `source_url`, `source_record_pk`, `raw_payload` presentes en 100% de filas | SQL de null-checks por campo sobre `policy_events` Moncloa |
| G6 Publicacion y estado operativo | Paridad live/export para metricas auditadas de Moncloa + fila tracker reconciliada con evidencia, bloqueador (si aplica) y un siguiente comando | reporte de paridad dashboard + actualizacion de `docs/etl/e2e-scrape-load-tracker.md` |

## Secuencia de ejecucion (ordenada)

1. T1: congelar baseline y gates (este documento).
2. T2-T3: preparar lote manual reproducible y contrato de campos Moncloa (HTML/RSS + manifest).
3. T4: implementar conectores Moncloa y tests de idempotencia.
4. T5 + T6 (en paralelo): matriz de ingesta (`strict-network`/`from-file`) y mapeo a `policy_events`.
5. T7: aplicar overrides deterministicos y recomputar una vez.
6. T8: refrescar export `explorer-sources` y validar paridad live vs export.
7. T9: reconciliar evidencia y texto de tracker para `Accion ejecutiva (Consejo de Ministros)`.
8. T10: closeout L3 con decision PASS/FAIL contra G1-G6.

## Criterio de salida del sprint

AI-OPS-04 solo puede cerrar en `PASS` si G1-G6 estan en verde con evidencia reproducible (comando + salida + artefacto markdown) y sin abrir nuevas familias fuera de Moncloa en este sprint.
