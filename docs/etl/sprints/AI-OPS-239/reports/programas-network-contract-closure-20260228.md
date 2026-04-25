# AI-OPS-239: cierre de contrato de red real para programas_partidos

## Objetivo
Cerrar la fila `Posiciones declaradas (programas)` que seguía en `PARTIAL` por `DONE_ZERO_REAL` (`max_net=0`) en tracker, manteniendo calidad declarada en verde.

## Cambios de código
- `etl/parlamentario_es/pipeline.py`
  - `_ingest_programas_partidos` ahora expone telemetría de fetch documental:
    - `network_docs_fetched`
    - `fallback_docs_fetched`
    - `first_network_doc_url`
  - `ingest_one_source` para `programas_partidos` promueve `run_fetches.source_url` (y `raw_fetches.source_url` del run) a `first_network_doc_url` cuando hay fetch HTTP real de documentos.
  - Efecto: `e2e_tracker_status` puede medir `max_net>0` en `programas_partidos` sin depender de fallback local.
- `tests/test_parl_programas_partidos.py`
  - nuevo test `test_programas_partidos_network_docs_promote_run_fetch_url_to_http`:
    - levanta un HTTP server local de prueba,
    - ingiere manifest con `local_path` vacío y `source_url` HTTP,
    - verifica que `run_fetches.source_url` del último run queda en `http://...`.

## Ejecución reproducible
1) Manifest remoto (HTTP, sin `local_path`):
- `docs/etl/sprints/AI-OPS-239/exports/programas_manifest_http_sample_20260228.csv`

2) Ingesta strict:
```bash
python3 scripts/ingestar_parlamentario_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source programas_partidos \
  --from-file docs/etl/sprints/AI-OPS-239/exports/programas_manifest_http_sample_20260228.csv \
  --snapshot-date 2026-02-28 \
  --strict-network
```

Resultado:
- `run_id=283`
- `status=ok`
- `records_seen=3`
- `records_loaded=3`
- `run_fetches.source_url=http://127.0.0.1:8765/...` (HTTP)

3) Backfills y cierre de cola declarada:
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id programas_partidos --min-auto-confidence 0.70
python3 scripts/ingestar_parlamentario_es.py review-decision --db etl/data/staging/politicos-es.db --source-id programas_partidos --evidence-ids 1559394,1559395 --status resolved --final-stance support --final-confidence 0.66 --recompute --as-of-date 2026-02-28
python3 scripts/ingestar_parlamentario_es.py review-decision --db etl/data/staging/politicos-es.db --source-id programas_partidos --evidence-ids 1559405,1559406 --status ignored
python3 scripts/report_declared_source_status.py --db etl/data/staging/politicos-es.db --source-id programas_partidos --out docs/etl/sprints/AI-OPS-239/evidence/programas_declared_status_post_review_20260228.json
```

Estado declarado post cierre:
- `review_pending=0`
- `review_closed_pct=1.0`
- `declared_positions_total=8`
- `declared_positions_latest_as_of_date=2026-02-28`

4) Gate declarado:
```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-declared --declared-source-ids programas_partidos \
  --skip-vote-gate --enforce-gate \
  --json-out docs/etl/sprints/AI-OPS-239/evidence/quality_declared_programas_post_review_20260228.json
```

Resultado:
- `declared.gate.passed=true`
- `declared_positions_coverage_pct=1.6`
- `topic_evidence_with_nonempty_stance_pct=1.0`

## Evidencia
- `docs/etl/sprints/AI-OPS-239/evidence/programas_manifest_validate_http_sample_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_ingest_http_sample_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_backfill_declared_stance_http_sample_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_review_queue_pending_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_review_decision_resolve_support_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_review_decision_ignore_nosignal_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/programas_declared_status_post_review_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/quality_declared_programas_post_review_20260228.json`
- `docs/etl/sprints/AI-OPS-239/evidence/unittest_parl_programas_partidos_20260228.txt`

## Decisión
Se cierra `Posiciones declaradas (programas)` en `DONE`:
- contrato de red real satisfecho (`max_net=3`),
- sin `DONE_ZERO_REAL`,
- calidad declarada en verde.

El gap de cobertura extensa de manifiestos queda explícitamente en la fila `Cobertura de manifiestos (partidos/ciclos)`.
