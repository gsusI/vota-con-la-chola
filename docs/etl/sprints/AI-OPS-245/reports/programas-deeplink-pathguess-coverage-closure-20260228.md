# AI-OPS-245 - Curación path-guess de deeplinks programáticos (2026-02-28)

## Objetivo
Cerrar el DoD de cobertura de `programas_partidos` para la lane de curación de deeplinks (`party_proxy_count >= 10`) manteniendo contrato reproducible `strict-network` y gate declarado en verde.

## Cambios implementados
- `scripts/build_programas_deeplink_manifest.py`
  - scoring ampliado: URL + anchor text + contenido.
  - fallback robusto por rutas canónicas en dominio raíz (`/programa`, `/programa-electoral`, `/propuestas`, etc.) cuando homepage no aporta anchors útiles.
  - deduplicación de candidatos combinando anchors + path-guess y cache por `source_url`.
  - metadatos de candidato (`candidate_source`) para trazabilidad de selección.
- Tests
  - `tests/test_build_programas_deeplink_manifest.py` cubre `score_anchor_text`, extracción scored y fallback `build_path_guess_candidates`.

## Artefactos generados
- Manifest curado:
  - `docs/etl/sprints/AI-OPS-245/exports/programas_manifest_deeplink_curated_pathguess_multicycle_20260228.csv`
- Validación de manifest:
  - `docs/etl/sprints/AI-OPS-245/evidence/programas_manifest_deeplink_curated_pathguess_validate_20260228.json`
- Reporte de curación:
  - `docs/etl/sprints/AI-OPS-245/evidence/programas_deeplink_curation_report_pathguess_20260228.json`
- Resumen por partido de selección deeplink:
  - `docs/etl/sprints/AI-OPS-245/exports/programas_deeplink_party_summary_20260228.csv`

## Resultado de curación
- `rows_total=51`
- `rows_updated=30`
- `rows_kept=15`
- `rows_skipped=6`
- `failures_total=0`

## Resultado en staging (`etl/data/staging/politicos-es.db`)
- Ingest real: `run_id=294`, `records_seen=51`, `records_loaded=51`, `status=ok`.
- Post backfill + cierre de cola pendiente (`87` evidence_id -> `ignored`):
  - `party_proxy_count=10`
  - `declared_positions_total=42`
  - `topic_evidence_total=305`
  - `topic_evidence_by_stance.support=43`
  - `review_pending=0`
  - gate declarado `passed=true`
  - tracker enforce: `mismatches=0`, `done_zero_real=0`

## Delta vs AI-OPS-244 (post-ignore)
Fuente: `docs/etl/sprints/AI-OPS-245/exports/programas_status_delta_ai_ops_244_vs_245_post_ignore_20260228.csv`

- `party_proxy_count`: `8 -> 10` (`+2`)
- `declared_positions_total`: `34 -> 42` (`+8`)
- `topic_evidence_total`: `236 -> 305` (`+69`)
- `topic_evidence_by_stance.support`: `37 -> 43` (`+6`)
- `review_pending`: `0 -> 0`

## Estado
- Lane `Curación de deeplinks programáticos por partido/ciclo`: DoD cerrado (pasa a `DONE`).
- Lane `Señal útil en manifiestos web`: sigue `PARTIAL` por volumen alto de `unclear` y partidos aún en `no_candidate_above_threshold`.

## Gap residual (nuevo TODO)
- Remediación fina por partido/ciclo para: `EH Bildu`, `UPN`, `Compromis`, `PSC`, `CUP`.
- Objetivo: bajar `unclear` y reducir ruido `no_signal` sin reabrir `review_pending`.
