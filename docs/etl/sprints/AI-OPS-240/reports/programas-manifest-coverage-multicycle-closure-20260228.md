# AI-OPS-240 - Cierre de cobertura multicíclo en `programas_partidos` (2026-02-28)

## Objetivo
Cerrar la fila de tracker **Cobertura de manifiestos (partidos/ciclos)** elevando cobertura reproducible con URLs oficiales y validación estricta.

## Cambios ejecutados
- Nuevo manifest versionado: `docs/etl/sprints/AI-OPS-240/exports/programas_manifest_multicycle_20260228.csv`
  - `45` filas
  - `15` partidos (`party_id` existentes en DB)
  - `3` ciclos (`es_generales_2023`, `es_europeas_2024`, `es_autonomicas_2023`)
  - `source_url` oficiales (sin `local_path`)
- Preflight de manifest: `scripts/validate_programas_manifest.py` (`valid=true`, `rows_valid=45`).
- Corrida real en staging:
  - `ingest --strict-network` (`run_id=284`, `records_seen=45`, `records_loaded=45`, `status=ok`)
  - `backfill-declared-stance`
  - `backfill-declared-positions`
  - `report_declared_source_status`
  - `quality-report --include-declared --skip-vote-gate --enforce-gate`

## KPI post-run (staging)
- `source_records=46`
- `party_proxy_count=15`
- `topic_sets_touched=3`
- `source_snapshot_dates=[2026-02-28]`
- Tracker SQL line (`e2e_tracker_status`): `programas_partidos | max_net=45 | max_any=45 | net/fallback_fetches=3/6 | OK`

## Control de calidad de cola de revisión
La expansión abrió cola `no_signal` alta (`review_pending=200`), cerrada en el mismo slice con decisión bulk `ignored`:
- `review_pending: 200 -> 0`
- `review_ignored=204`
- Gate declarado tras cierre: `passed=true`

## Evidencia
- `docs/etl/sprints/AI-OPS-240/evidence/programas_manifest_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-240/evidence/programas_manifest_party_probe_20260228.json`
- `docs/etl/sprints/AI-OPS-240/evidence/programas_declared_status_multicycle_20260228.json`
- `docs/etl/sprints/AI-OPS-240/evidence/programas_review_decision_ignore_pending_bulk_20260228.stdout`
- `docs/etl/sprints/AI-OPS-240/evidence/programas_declared_status_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-240/evidence/quality_declared_programas_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-240/evidence/tracker_status_post_ignore_20260228.log`

## Gap residual abierto
Se crea lane específico para señal útil (`anti no_signal`) porque la cobertura quedó cerrada pero la extracción sustantiva sigue baja en fuentes web dinámicas.
