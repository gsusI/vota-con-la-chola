# AI-OPS-266 — Curación residual BNG/VOX + hardening de precisión por partido

## Objetivo
Reducir deuda semántica residual en `programas_partidos` (fila 770 del tracker) con un patch acotado en `declared:regex_v3`, manteniendo el guardrail de precisión global y por partido.

## Cambios implementados
- `etl/parlamentario_es/declared_stance.py`
  - Ampliación de cobertura de fallback programático para casos reales en gallego/castellano:
    - acciones: `ampliando`, `elaboraran/elaboraremos/elaborar`
    - concerns: `auga`, `luz`, `gas`, `autoconsumo*`, `bono social`, `eficiencia enerxetica*`, `serviz* public*`, `axuda*`
  - Hard blockers específicos anti-falso-positivo:
    - `partidos politicos deben fomentar la igualdad entre hombres y mujeres`
    - `amenazas en las redes de internet`
- `tests/test_parl_declared_stance.py`
  - Nuevos casos positivos y negativos para cubrir la ampliación y los bloqueadores.

## Validación técnica
- Unit tests focales:
  - `python3 -m unittest tests/test_parl_declared_stance.py`
  - Resultado: `Ran 9 tests`, `OK`.

## Corrida de datos y resultados
1. Recompute declarado en staging (`2026-02-28`):
- `backfill-declared-stance --reconcile-no-signal`
- `backfill-declared-positions`
- `backfill-combined-positions`

2. Delta global declarado (`programas_partidos`):
- `topic_evidence.support`: `423 -> 424` (`+1`)
- `topic_evidence.unclear`: `145 -> 144` (`-1`)
- `declared_positions_total`: `436 -> 437` (`+1`)
- `review_pending`: `0 -> 0`

3. Delta focal BNG/VOX por documento:
- `BNG galegas 2024`: `support 9 -> 12`, `unclear 3 -> 0`
- `BNG europeas 2024`: sin cambio (`8/16`)
- `VOX web 2025`: sin cambio (`18/15`)

4. Guardrail de precisión (sample rotado + etiquetado manual incremental):
- `sample_total=40`, `reviewed=40`
- precisión global: `0.95`
- precisión por partido requerido:
  - `BNG=0.90`
  - `VOX=1.00`
  - `FORO Asturias=1.00`
  - `PP=0.90`
- strict audit: `status=ok`, `passed=true`

5. Gates de calidad y tracker:
- `quality-report --include-declared --enforce-gate`: `declared.gate.passed=true`
- `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`: `mismatches=0`, `done_zero_real=0`

## Evidencia
- Baseline:
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_declared_status_pre_semantic_patch_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_quality_declared_pre_semantic_patch_latest.json`
  - `docs/etl/sprints/AI-OPS-266/exports/programas_bng_vox_url_breakdown_pre_latest.csv`
- Post:
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_declared_status_post_semantic_patch_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_quality_declared_post_semantic_patch_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_semantic_patch_delta_latest.json`
  - `docs/etl/sprints/AI-OPS-266/exports/programas_bng_vox_url_breakdown_post_latest.csv`
  - `docs/etl/sprints/AI-OPS-266/exports/programas_bng_vox_url_breakdown_delta_latest.csv`
- Precisión:
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_support_precision_sample_summary_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_support_precision_rotate_summary_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_support_precision_manual_labels_added_latest.json`
  - `docs/etl/sprints/AI-OPS-266/evidence/programas_support_precision_audit_latest.json`
  - `docs/etl/sprints/AI-OPS-266/exports/programas_support_precision_audit_breakdown_latest.csv`
- Integridad tracker:
  - `docs/etl/sprints/AI-OPS-266/evidence/tracker_status_post_semantic_patch_latest.log`
