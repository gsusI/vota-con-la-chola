# AI-OPS-267 — Reducción de tail residual BNG/VOX con intención futura

## Objetivo
Seguir cerrando la fila 770 (`Curación documental residual de manifiestos (BNG/VOX)`) reduciendo `unclear` en documentos objetivo sin degradar el guardrail de precisión por partido.

## Cambio aplicado
- `etl/parlamentario_es/declared_stance.py`
  - Se añade fallback controlado para intención futura explícita en manifiestos (`seguiremos|seguirem`) cuando coexiste con términos de preocupación pública en el excerpt.
  - No se amplía a `seguimos` para evitar falsos positivos descriptivos.
- `tests/test_parl_declared_stance.py`
  - Caso positivo nuevo para `seguirem` + tema público.
  - Caso negativo nuevo para `seguimos` sin propuesta concreta.

## Validación técnica
- `python3 -m unittest tests/test_parl_declared_stance.py`
- Resultado: `Ran 9 tests`, `OK`.

## Resultado en datos (staging)
Comparativa contra estado AI-OPS-266 (post):
- `topic_evidence.support`: `424 -> 426` (`+2`)
- `topic_evidence.unclear`: `144 -> 142` (`-2`)
- `declared_positions_total`: `437 -> 437` (`0`)
- `review_pending`: `0 -> 0`

Delta focal por documento:
- `BNG 24_bng_programa_europeas_2.pdf`: `support 8 -> 10`, `unclear 16 -> 14`
- `VOX Programa-WEB-021025.pdf`: sin cambio (`18/15`)

## Guardrails
- Precision audit strict: `status=ok`, `precision=0.95`, floors por partido en verde (`BNG=0.90`, `PP=0.90`, `VOX=1.00`, `FORO=1.00`).
- Quality declared gate: `passed=true`.
- Tracker enforce: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-267/evidence/programas_backfill_declared_stance_latest.json`
- `docs/etl/sprints/AI-OPS-267/evidence/programas_declared_status_post_latest.json`
- `docs/etl/sprints/AI-OPS-267/evidence/programas_semantic_patch_delta_vs_ai_ops_266_latest.json`
- `docs/etl/sprints/AI-OPS-267/exports/programas_bng_vox_url_breakdown_post_latest.csv`
- `docs/etl/sprints/AI-OPS-267/exports/programas_bng_vox_url_breakdown_delta_vs_ai_ops_266_latest.csv`
- `docs/etl/sprints/AI-OPS-267/evidence/programas_support_precision_audit_latest.json`
- `docs/etl/sprints/AI-OPS-267/evidence/programas_quality_declared_post_latest.json`
- `docs/etl/sprints/AI-OPS-267/evidence/tracker_status_post_latest.log`
