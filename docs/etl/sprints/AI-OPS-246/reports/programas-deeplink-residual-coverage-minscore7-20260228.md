# AI-OPS-246 - Cierre de cobertura residual de deeplinks (min_score=7)

## Objetivo
Cerrar la cola residual de partidos con `selected_reason=no_candidate_above_threshold` en `programas_partidos`, manteniendo contrato reproducible (`strict-network`) y gate declarado en verde.

## Cambios ejecutados
- Curación reproducible con umbral más permisivo en selección de deeplinks:
  - `python3 scripts/build_programas_deeplink_manifest.py --min-score 7 --max-probe-candidates 8 ...`
- Manifest curado + validación + pipeline completo:
  - ingest `strict-network`
  - `backfill-declared-stance`
  - `backfill-declared-positions`
  - `quality-report --include-declared`
  - cierre de cola `review_pending` vía `review-decision --status ignored`

## Artefactos
- Manifest curado: `docs/etl/sprints/AI-OPS-246/exports/programas_manifest_deeplink_curated_minscore7_multicycle_20260228.csv`
- Validación: `docs/etl/sprints/AI-OPS-246/evidence/programas_manifest_deeplink_curated_minscore7_validate_20260228.json`
- Reporte de curación: `docs/etl/sprints/AI-OPS-246/evidence/programas_deeplink_curation_report_minscore7_20260228.json`
- Resumen por partido (deeplink seleccionado): `docs/etl/sprints/AI-OPS-246/exports/programas_deeplink_party_summary_minscore7_20260228.csv`
- Breakdown de evidencia por partido: `docs/etl/sprints/AI-OPS-246/exports/programas_party_evidence_breakdown_post_ignore_20260228.csv`

## Resultado de curación
- `rows_total=51`
- `rows_updated=45`
- `rows_kept=0`
- `rows_skipped=6`
- `failures_total=0`
- Todos los partidos del manifest quedaron en `candidate_selected` (sin remanente `no_candidate_above_threshold`).

## Resultado en staging (`etl/data/staging/politicos-es.db`)
- Ingest real: `run_id=295`, `records_seen=51`, `records_loaded=51`, `status=ok`.
- Estado post-ignore:
  - `party_proxy_count=15`
  - `declared_positions_total=42`
  - `topic_evidence_total=386`
  - `topic_evidence_by_stance.support=43`
  - `topic_evidence_by_stance.unclear=343`
  - `review_pending=0`
  - gate declarado `passed=true`
  - tracker enforce: `mismatches=0`, `done_zero_real=0`

## Delta vs AI-OPS-245 (post-ignore)
Fuente: `docs/etl/sprints/AI-OPS-246/exports/programas_status_delta_ai_ops_245_vs_246_post_ignore_20260228.csv`

- `party_proxy_count`: `10 -> 15` (`+5`)
- `declared_positions_total`: `42 -> 42` (`0`)
- `topic_evidence_total`: `305 -> 386` (`+81`)
- `topic_evidence_by_stance.support`: `43 -> 43` (`0`)
- `topic_evidence_by_stance.unclear`: `262 -> 343` (`+81`)
- `review_pending`: `0 -> 0`

## Estado
- Cierre de cobertura residual de deeplinks: completado.
- Gap principal restante: la nueva cobertura entra mayoritariamente como `unclear/no_signal`; la siguiente lane debe atacar clasificación semántica multilingüe (ca/eu/gl) para convertir cobertura en señal sustantiva.
