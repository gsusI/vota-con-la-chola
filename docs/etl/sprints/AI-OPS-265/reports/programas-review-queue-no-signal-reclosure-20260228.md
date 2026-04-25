# AI-OPS-265 - Re-cierre de cola review `no_signal` (`programas_partidos`)

## Objetivo
Cerrar la cola `pending` residual de `topic_evidence_reviews` (`review_reason=no_signal`) reabierta tras replay local de manifiestos y restaurar baseline editorial del guardrail.

## Ejecución
1. Baseline de cola:
   - `python3 scripts/ingestar_parlamentario_es.py review-queue --db etl/data/staging/politicos-es.db --source-id programas_partidos --status pending --review-reason no_signal --limit 500 --offset 0`
   - Resultado: `pending_no_signal=64` (`returned=64`).
2. Aplicación de cierre en bloque:
   - `python3 scripts/ingestar_parlamentario_es.py review-decision --db etl/data/staging/politicos-es.db --source-id programas_partidos --evidence-ids <64 ids> --status ignored --note ai-ops-265:no_signal_queue_closure`
   - Resultado: `matched=64`, `review_rows_updated=64`, `not_found=[]`.
3. Verificación post-cierre (secuencial):
   - `review-queue` en el mismo filtro retorna `pending=0` / `returned=0`.
   - `report_declared_source_status` queda en `review_pending=0`, `review_ignored=300`.
   - `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate` mantiene gate declarado en verde.

## Delta de estado
- `review_pending`: `64 -> 0`
- `review_ignored`: `236 -> 300`
- `review_total`: `303 -> 303` (sin pérdida de trazabilidad)

## Evidencia
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_pending_no_signal_pre_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_pending_no_signal_pre_summary_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_pending_no_signal_pre_ids_latest.txt`
- `docs/etl/sprints/AI-OPS-265/exports/programas_review_queue_pending_no_signal_pre_latest.csv`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_apply_ignore_no_signal_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_pending_no_signal_post_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_declared_status_pre_review_queue_close_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_declared_status_post_review_queue_close_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_review_queue_no_signal_closure_delta_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_quality_declared_post_review_queue_close_latest.json`
- `docs/etl/sprints/AI-OPS-265/evidence/programas_quality_declared_post_review_queue_close_stdout_latest.txt`
- `docs/etl/sprints/AI-OPS-265/evidence/tracker_status_post_review_queue_close_pre_tracker_edit_latest.log`
- `docs/etl/sprints/AI-OPS-265/evidence/tracker_status_post_ai_ops_265_latest.log`
