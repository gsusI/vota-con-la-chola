# AI-OPS-223 - Cierre de `Posiciones declaradas (programas)`

Fecha (UTC): 2026-02-27  
DB: `etl/data/staging/politicos-es.db`

## Objetivo

Cerrar la deuda residual de calidad marcada en tracker para `programas_partidos`:
- cola manual pendiente,
- hardening del gate declarado.

## Ejecución

1. Estado de la fuente declarada:

```bash
python3 scripts/report_declared_source_status.py \
  --db etl/data/staging/politicos-es.db \
  --source-id programas_partidos \
  --out docs/etl/sprints/AI-OPS-223/evidence/programas_declared_status_20260227T012803Z.json
```

2. Gate declarado estricto (sin gate de voto, lane editorial):

```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-declared \
  --declared-source-ids programas_partidos \
  --skip-vote-gate \
  --enforce-gate \
  --json-out docs/etl/sprints/AI-OPS-223/evidence/quality_declared_programas_20260227T012803Z.json
```

3. Consistencia tracker/UI para la fila editorial:

```bash
python3 -m unittest tests/test_e2e_tracker_status_tracker.py
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json \
  --fail-on-mismatch \
  --fail-on-done-zero-real \
  > docs/etl/sprints/AI-OPS-223/evidence/tracker_status_latest.log
```

## Resultado

- `review_pending=0`
- `review_closed_pct=1.0`
- `declared_positions_coverage_pct=1.0`
- `topic_evidence_with_nonempty_stance_pct=1.0`
- `declared.gate.passed=true`
- `mismatches=0` y `done_zero_real=0` con la fila en `PARTIAL`

Contrato actualizado:
- `scripts/e2e_tracker_status.py` mapea `Posiciones declaradas (programas) -> programas_partidos`.
- `scripts/graph_ui_server.py` replica el mismo mapeo para paridad con Explorer Sources.

Cobertura actual del lane (sin cambio de alcance):
- `source_records=3`
- `text_documents=3`
- `topic_evidence_total=11`
- `declared_positions_total=5`
- `declared_positions_by_stance={support:4, oppose:1}`

## Decisión

La fila `Posiciones declaradas (programas)` queda en `PARTIAL`:
- calidad/hardening cerrados,
- cierre final pendiente por contrato de red real (`DONE_ZERO_REAL` al forzar `DONE` en `e2e_tracker_status`, con `max_net=0`, `max_any=3`, `net/fallback_fetches=0/6`).

## Gap abierto para siguiente slice

Cobertura editorial insuficiente para scraping continuo multi-ciclo/multi-ámbito.  
Se abrió TODO explícito: `Cobertura de manifiestos (partidos/ciclos)`.
