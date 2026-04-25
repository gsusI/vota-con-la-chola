# AI-OPS-339 — Senado `status=404`: agotamiento canónico, ventana de dedupe y gap de fallback

Fecha (UTC): `2026-03-01T02:02:40Z`  
DB: `etl/data/staging/politicos-es.db`

## Objetivo
Seguir reduciendo la cola accionable de documentos Senado en `status=404`, manteniendo trazabilidad completa y sin degradar extracción semántica.

## Ejecución
1. Baseline de estado (`initiative_doc_status`, perfil WAF y cola `status=404` linked-to-votes).
2. Retry canónico inicial (`retry_packet_only_dedup`, `max_rows=240`): `fresh_rows_total=2`.
3. Exploración de lanes alternas:
- `status=500` linked-to-votes: `pool_rows_total=0` (sin cola accionable).
- `status=0`: packet `120` filas, pero `urls_to_fetch=0` (todas `skipped_existing/skipped_retry_http_statuses`).
4. Palanca controlable: se añade modo `--packet-csv-refs-file-only` en `scripts/export_senado_retry_packet_only_dedup.py`, se integra en `justfile` vía `SENADO_RETRY_PACKET_REFS_ONLY=1`, y queda con test unitario dedicado.
5. Repacket `status=404` con ventana reciente real (`refs-only`): `fresh_rows_total=160`.
6. Burst acotado sobre subpacket (`20` URLs) para señal rápida: `fetched_ok=0`, `archive_hits=0`.

## Resultado
- Estado de datos principal: **sin delta**.
- Métricas globales permanecen:
- `downloaded_doc_links=4420`
- `missing_doc_links=5133`
- `missing_doc_links_actionable=4949`
- `effective_downloaded_doc_links_pct=47.18`
- WAF linked-to-votes estable:
- `missing_urls=1173`
- `blocked_403_urls=160`
- `unknown_status_urls=217`

## Hallazgos operativos
- La dedupe canónica estaba agotando la lane `404` (`fresh_rows_total=2`) por historial acumulado.
- El nuevo modo `refs-only` reabre capacidad de packet (`fresh_rows_total=160`) sin romper reproducibilidad.
- El burst de muestra (`20`) falló por ausencia de snapshots archivados (`archive fallback: no snapshot candidates`) en URLs clave de legislatura 14 (`tipo 622/626`).

## Decisión
La fila `837` permanece `TODO`: no hubo conversión material en AI-OPS-339, pero se cerró una mejora de toolchain que habilita ventanas de dedupe controladas y se aisló un gap técnico explícito (`archive_no_snapshot_candidates`) para la siguiente lane.

## Evidencia
- `docs/etl/sprints/AI-OPS-339/evidence/initiative_doc_status_before_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/initiative_doc_status_after_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/initiative_doc_status_delta_ai_ops_339_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_status404_fresh_packet_summary_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_retry_status404_fresh_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_status404_recent-window_packet_summary_20260301T020240Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_status404_recent-window_packet_summary_via_just_20260301T020240Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_retry_status404_recent-window_packet20_20260301T020240Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_waf_block_profile_delta_ai_ops_339_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_tail_actionable_delta_ai_ops_339_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/senado_cookie_lever_status_20260301T015814Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/backfill_initdoc_records_from_fetches_dry_run_20260301T015950Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/backfill_initdoc_fetch_status_senado_20260301T015950Z.json`
- `docs/etl/sprints/AI-OPS-339/evidence/unittest_export_senado_retry_packet_only_dedup_20260301T020240Z.txt`
