# AI-OPS-257 - Expansion semantica fallback `programas_partidos` (FORO/BNG)

## Objetivo del slice
Cerrar el nuevo gap `FORO Asturias post-higiene` y seguir reduciendo residual `BNG/VOX` con cambios controlables en inferencia semantica (`declared:regex_v3`) y paridad de verbos en ingest.

## Cambios implementados
Se ampliaron patrones en `etl/parlamentario_es/declared_stance.py`:
- Acciones nuevas: `incentivar`, `implicar`, `formar`, `realizar`, `suprimir`, `velar`, `exigir`, `demanda*`, `reconocer/reconecendo`, `coidar`, `mejorara`, `reforzar`.
- Lenguaje nominal adicional: `reconecemento/reconocimiento`, `reduccion`.
- Concerns nuevos: `pesquer*`, `piscicol*`, `electric*`, `administraci*`, `servicios publicos`, `transparen*`, `emplead*`, `inversion*`, `investigaci*`, `jovenes/juventud`.

Se alineo el hot path de ingest en `etl/parlamentario_es/pipeline.py` ampliando `_PROGRAMA_POLICY_VERBS_NORM` con las mismas familias verbales para preservar consistencia de extraccion y fallback.

Se anadieron regresiones en `tests/test_parl_declared_stance.py` para frases reales de residual:
- FORO pesca/administracion/transparencia.
- BNG europeas (demanda/reconecemento/tarifa electrica/materia pesqueira).

## Validacion de codigo
- `python3 -m unittest tests/test_parl_declared_stance.py` -> `OK`
- `python3 -m unittest tests/test_parl_programas_partidos.py` -> `OK`

## Ejecucion en DB real (staging)
1. `backfill-declared-stance --source-id programas_partidos`
2. `backfill-declared-positions --source-id programas_partidos --as-of-date 2026-02-28`
3. `backfill-combined-positions --as-of-date 2026-02-28`
4. `review-queue --status pending` (verificacion de cola)
5. `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate`
6. `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`

## Resultado principal (AI-OPS-256 -> AI-OPS-257)
Global (`programas_partidos`):
- `support`: `355 -> 392` (`+37`)
- `unclear`: `209 -> 172` (`-37`)
- `declared_positions_total`: `376 -> 376` (`=`, estable)
- `review_pending`: `0 -> 0` (cola cerrada)
- `party_proxy_count`: `15 -> 15`
- gate declarado: `passed=true`
- tracker enforce: `mismatches=0`, `done_zero_real=0`

Foco residual (`BNG/VOX/FORO`):
- `FORO Asturias`: `33/48 -> 45/48` (`+12 support`, `unclear 15->3`)
- `BNG`: `20/48 -> 24/48` (`+4 support`, `unclear 28->24`)
- `VOX`: `16/33 -> 18/33` (`+2 support`, `unclear 17->15`)

Detalle por URL:
- `FORO Programa-electoral-FORO-Asturias-20232027.pdf`: `33/48 -> 45/48`
- `BNG 24_bng_programa_europeas_2.pdf`: `4/24 -> 8/24`
- `VOX Programa-WEB-021025.pdf`: `16/33 -> 18/33`

## Estado de gaps
- `FORO post-higiene`: objetivo cumplido (recuperacion >= `+3 support`).
- `BNG/VOX` residual: mejora material, pero persisten bloques narrativos/no accionables (`BNG europeas 16 unclear`, `VOX 15 unclear`).

## Evidencia
- Estado pre/post:
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_declared_status_pre_semantic_patch_20260228.json`
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_declared_status_post_semantic_patch_20260228.json`
- Backfills:
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_backfill_declared_stance_post_semantic_patch_20260228.json`
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_backfill_declared_positions_post_semantic_patch_20260228.json`
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_backfill_combined_positions_post_semantic_patch_20260228.json`
- Gates:
  - `docs/etl/sprints/AI-OPS-257/evidence/programas_review_queue_pending_post_semantic_patch_20260228.json`
  - `docs/etl/sprints/AI-OPS-257/evidence/quality_declared_programas_post_semantic_patch_20260228.json`
  - `docs/etl/sprints/AI-OPS-257/evidence/tracker_status_post_semantic_patch_enforce_20260228.log`
  - `docs/etl/sprints/AI-OPS-257/evidence/tracker_status_post_tracker_update_enforce_20260228.log`
- Deltas/auditorias:
  - `docs/etl/sprints/AI-OPS-257/exports/programas_party_evidence_delta_pre_vs_post_semantic_patch_20260228.csv`
  - `docs/etl/sprints/AI-OPS-257/exports/programas_bng_vox_foro_url_delta_pre_vs_post_semantic_patch_20260228.csv`
  - `docs/etl/sprints/AI-OPS-257/exports/programas_bng_vox_foro_unclear_excerpt_audit_post_semantic_patch_20260228.csv`
  - `docs/etl/sprints/AI-OPS-257/exports/programas_support_precision_sample_20260228.csv`
- Tests:
  - `docs/etl/sprints/AI-OPS-257/evidence/unittest_parl_declared_stance_20260228.txt`
  - `docs/etl/sprints/AI-OPS-257/evidence/unittest_parl_programas_partidos_20260228.txt`
