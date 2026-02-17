# Sprint AI-OPS-02 Kickoff

Fecha de baseline: 2026-02-16

## Objetivo del sprint

Congelar baseline y orden de ejecucion antes de implementar, priorizando el loop de ambiguedad de alta prioridad (low_confidence, conflicting_signal, high-stakes), sin romper integridad del esquema ni trazabilidad por batch.

## Baseline (comandos y salidas exactas)

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT status, COUNT(*) FROM topic_evidence_reviews GROUP BY status ORDER BY status;"
```

Salida exacta:

```text
ignored|474
resolved|50
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT computed_method, COUNT(*) FROM topic_positions GROUP BY computed_method ORDER BY computed_method;"
```

Salida exacta:

```text
combined|68610
declared|164
votes|68528
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;"
```

Salida exacta:

```text

```

Interpretacion operativa del baseline:
- `topic_evidence_reviews` no tiene `pending` al inicio (`ignored=474`, `resolved=50`).
- `topic_positions` tiene volumen mayoritariamente en `combined` y `votes`, con menor cobertura en `declared`.
- Integridad referencial base en verde (`PRAGMA foreign_key_check` sin filas).

## Insumos leidos para fijar ejecucion

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`

Alineamiento usado:
- Priorizar slices verticales cortos y auditables (ingesta -> evidencia -> posiciones -> publish).
- Mantener trazabilidad por evidencia y por corrida.
- Cerrar loop de revision antes de abrir superficies nuevas.

## Secuencia ordenada de tareas (AI-OPS-02)

1. Congelar baseline de sprint (queries SQL anteriores) y registrar punto de partida.
2. Generar lote MTurk estrictamente dirigido a casos de alto valor ambiguo (`low_confidence`, `conflicting_signal`, `is_high_stakes=1`).
3. Validar contrato de export MTurk (sin drift de schema entre `tasks_input.csv`, `workers_raw.csv`, `decisions_adjudicated.csv`).
4. Aplicar decisiones nuevas con tagging obligatorio de batch en notas/metadatos.
5. Recomputar posiciones `declared` y `combined` tras aplicar decisiones.
6. Verificar gates de salida y dejar evidencia en tracker/doc del sprint.

## Gates del sprint

- Gate 1: Baseline registrado en este documento con comandos y salidas exactas.
- Gate 2: Todas las decisiones nuevas aplicadas quedan etiquetadas por batch (sin excepciones).
- Gate 3: Cero drift de schema en exports MTurk del sprint.
- Gate 4: `PRAGMA foreign_key_check` sin filas tras aplicar cambios.
- Gate 5: Estado final auditado (conteos de reviews y `computed_method` actualizados y trazables).

## Criterio de salida

Sprint listo para implementacion cuando los 5 gates esten en verde y la evidencia quede trazable por batch y por snapshot.
