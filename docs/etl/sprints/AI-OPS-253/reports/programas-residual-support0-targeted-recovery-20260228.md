# AI-OPS-253 — Recuperación residual `support=0` en manifiestos (`BNG`/`EH Bildu`/`EQUO`)

Fecha: 2026-02-28

## Objetivo
Avanzar la TODO de calidad semántica residual en `programas_partidos`, priorizando partidos con `support=0` (`BNG`, `EH Bildu`, `EQUO`) sin perder cobertura global (`party_proxy_count=15`).

## Cambios operativos
- Curación dirigida de URLs programáticas en manifest:
  - `BNG` -> PDFs programáticos por ciclo (`xerais 2023`, `europeas 2024`, `galegas 2024`).
  - `EH Bildu` -> PDF programático en castellano (`ES_1682328517.pdf`) en lugar de documento financiero histórico de `gardentasuna`.
  - `EQUO` -> PDF programático (`Un-Programa-para-ti-bueno.pdf`) en lugar de `homepage` con contenido no útil.
- Validación de manifests (`validate_programas_manifest.py`) y trazabilidad de cambios URL.
- Reingesta final en modo reproducible con `local_path` para las 51 filas del manifest completo (`local replay`), seguida de recompute declarado/combinado.
- Cierre de cola `review_pending` (`277` ids) con `review-decision --status ignored` en 3 lotes.

## Incidente detectado y remediación
- Un run intermedio con manifest parcial (3 partidos) reescribió temporalmente la señal declarada de `programas_partidos` a un subconjunto (`party_proxy_count=3`).
- Remediación aplicada en el mismo sprint:
  - Se generó manifest completo (51 filas) con overrides de AI-OPS-253.
  - Se ejecutó reingesta completa y recompute.
  - Se restauró cobertura global (`party_proxy_count=15`) y tracker enforce quedó limpio.

## Resultado final (post-ignore)
Delta AI-OPS-252 -> AI-OPS-253:
- `support`: `199 -> 244` (`+45`)
- `unclear`: `296 -> 320` (`+24`)
- `topic_evidence_total`: `495 -> 564` (`+69`)
- `declared_positions_total`: `237 -> 280` (`+43`)
- `party_proxy_count`: `15 -> 15`
- `review_pending`: `0 -> 0`

Partidos objetivo:
- `EH Bildu`: `support 0 -> 20` (`evidence 24 -> 48`)
- `EQUO`: `support 0 -> 24` (`evidence 3 -> 36`)
- `BNG`: `support 0 -> 1` (`evidence 36 -> 48`)

Gate y tracker:
- `quality-report --include-declared ... --enforce-gate`: `passed=true`
- `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`: `mismatches=0`, `done_zero_real=0`

## Gap residual abierto
- Ya no quedan partidos `support=0` en la cohorte objetivo; el residual pasa a ser **baja relación señal/ruido** en:
  - `BNG` (`1/48 support`),
  - `PP` (`3/56 support`),
  - `VOX` (`3/33 support`).

## Evidencia principal
- `docs/etl/sprints/AI-OPS-253/exports/programas_manifest_url_changes_vs_ai_ops_251_v4_residual_support0_targeted_v1_20260228.csv`
- `docs/etl/sprints/AI-OPS-253/evidence/programas_manifest_full_v5_residual_support0_targeted_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-253/evidence/programas_manifest_full_v5_residual_support0_targeted_localreplay_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-253/evidence/programas_ingest_full_v5_residual_support0_targeted_localreplay_20260228.json`
- `docs/etl/sprints/AI-OPS-253/evidence/programas_declared_status_post_full_v5_localreplay_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-253/evidence/quality_declared_programas_post_full_v5_localreplay_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-253/evidence/tracker_status_post_full_v5_localreplay_post_ignore_enforce_20260228.log`
- `docs/etl/sprints/AI-OPS-253/exports/programas_party_delta_ai_ops_252_vs_ai_ops_253_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-253/exports/programas_residual_support0_url_audit_post_full_v5_localreplay_pre_review_20260228.csv`
