# AI-OPS-192 - Packet-fix queue lane (`non-ready packets -> prioritized remediation`)

## Objetivo
Convertir el diagnóstico de readiness de paquetes en una cola operativa priorizada por fuente para cerrar más rápido los gaps de captura oficial.

## Entregado
- `scripts/export_sanction_procedural_official_review_packet_fix_queue.py`
  - reusa `build_raw_packets_progress_report` y exporta solo paquetes no listos (`ready_for_transform=false`);
  - genera cola con:
    - `queue_key`
    - `priority`
    - `next_action`
    - `packet_status`
    - `missing_required_fields`
    - `row_reject_reasons`
    - `kpis_missing*`
  - prioridad determinista por estado:
    - `missing_packet_file=100`
    - `invalid_headers=90`
    - `multiple_rows=85`
    - `empty_packet=80`
    - `invalid_row=70`
  - soporta gate `--strict-empty` para exigir cola vacía.
- `justfile`
  - variables nuevas `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_PACKET_FIX_QUEUE_*`;
  - lane nueva:
    - `parl-export-sanction-procedural-official-review-packet-fix-queue`;
  - integración en `parl-sanction-data-catalog-pipeline`.
- Tests
  - `tests/test_export_sanction_procedural_official_review_packet_fix_queue.py` (`Ran 3`).
  - `parl-test-sanction-data-catalog` sube a `Ran 56`.

## Resultado de corrida
- Staging (`AI-OPS-188/latest`, `period=2026-02-12/year`):
  - `status=degraded`
  - `queue_rows_total=4`
  - `queue_rows_by_packet_status={invalid_row:4}`
  - `next_action` homogénea: `complete_evidence_and_raw_count_fields_then_recheck`
  - `missing_required_fields` identifica de forma explícita `evidence_*` + counts raw faltantes por fuente.
- Fixture contractual (`AI-OPS-189` paquetes completos, `period=2025-12-31/year`):
  - `status=ok`
  - `queue_rows_total=0`
  - `fix_queue_empty=true`.
- Integración:
  - `just parl-export-sanction-procedural-official-review-packet-fix-queue` -> `OK`
  - `just parl-sanction-data-catalog-pipeline` -> `OK`
  - `just parl-test-sanction-data-catalog` -> `Ran 56`, `OK`

## Conclusión operativa
La captura oficial ya tiene backlog accionable por fuente y prioridad, listo para ejecución manual o delegación por lotes. Esto elimina ambigüedad sobre “qué completar primero” y acelera el cierre de `missing_metric`.

## Evidencia
- `docs/etl/sprints/AI-OPS-192/evidence/sanction_procedural_official_review_packet_fix_queue_20260224T120848Z.json`
- `docs/etl/sprints/AI-OPS-192/exports/sanction_procedural_official_review_packet_fix_queue_20260224T120848Z.csv`
- `docs/etl/sprints/AI-OPS-192/evidence/sanction_procedural_official_review_packet_fix_queue_fixture_20260224T120848Z.json`
- `docs/etl/sprints/AI-OPS-192/exports/sanction_procedural_official_review_packet_fix_queue_fixture_20260224T120848Z.csv`
- `docs/etl/sprints/AI-OPS-192/evidence/just_parl_export_sanction_procedural_official_review_packet_fix_queue_20260224T120902Z.txt`
- `docs/etl/sprints/AI-OPS-192/evidence/just_parl_sanction_data_catalog_pipeline_20260224T120902Z.txt`
- `docs/etl/sprints/AI-OPS-192/evidence/just_parl_test_sanction_data_catalog_20260224T120902Z.txt`
