# AI-OPS-352 — Reseed manual de capacidad Senado (fila 843)

## Objetivo
Reabrir capacidad reproducible tras el agotamiento canónico (`status=404`/`zero_doc`) usando la palanca manual de captura (`manual_capture_playwright`) y ejecutar retry acotado con cookie fresca.

## Qué se ejecutó
1. Gate inicial de palanca:
   - `report_senado_cookie_lever_status.py --strict`
   - `report_senado_manual_capture_validity.py --strict`
2. Iteración de cola manual:
   - `run_senado_manual_capture_iteration_cycle.py --strict`
   - Resultado inicial: 8 targets pendientes, todos `matched_access_denied`.
3. Reseed acotado de capturas (2 targets, 15s):
   - `export_senado_manual_capture_pending_targets.py --max-targets 2 --wait-seconds 15`
   - `bash .../senado_manual_capture_pending_targets_small_commands_*.sh`
4. Revalidación + retry con palanca ya utilizable:
   - `report_senado_manual_capture_validity.py --strict`
   - `run_senado_manual_capture_retry_cycle.py --strict-ready --limit-initiatives 8 --timeout 10 --python-bin python3`
5. Verificación de KPI antes/después:
   - `quality-report --include-initiatives --initiative-actionable-scope linked_to_votes`
   - `report_senado_waf_block_profile.py --only-linked-to-votes`

## Resultado
- Palanca manual reabierta (`status=ok`): `usable_captures_total=2` (antes `0`).
- Retry real ejecutado (`backfill.status=ok`, `exit_code=0`, `attempted=true`).
- Sin delta neta de cobertura en esta pasada:
  - `downloaded_doc_links: 4802 -> 4802`
  - `missing_doc_links_actionable: 4561 -> 4561`
  - `missing_urls: 785 -> 785`
- Hubo reclasificación de faltantes:
  - `status=404: 408 -> 396`
  - `status=403: 160 -> 172`

## Interpretación operativa
- Se cumple parcialmente el DoD de fila 843: la palanca reproducible existe y el retry ya corre en modo utilizable.
- No se cumple aún el criterio de delta neta de descarga/cierre; el primer retry convertido con cookie fresca no recuperó documentos nuevos.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-352/evidence/senado_cookie_lever_status_20260301T075033Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/senado_manual_capture_validity_after_small_run_20260301T075125Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/senado_manual_capture_retry_cycle_after_refresh_sanitized_20260301T075426Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/quality_initiatives_before_manual_retry_20260301T075243Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/quality_initiatives_after_manual_retry_sanitized_20260301T075426Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/senado_waf_block_profile_before_manual_retry_20260301T075243Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/senado_waf_block_profile_after_manual_retry_sanitized_20260301T075426Z.json`
- `docs/etl/sprints/AI-OPS-352/evidence/senado_manual_capture_reseed_delta_ai_ops_352_20260301T075426Z.json`
