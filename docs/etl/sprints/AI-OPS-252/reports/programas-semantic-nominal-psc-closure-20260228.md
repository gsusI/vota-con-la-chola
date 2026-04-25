# AI-OPS-252 — Cierre de calidad semántica PSC + hardening de recompute

Fecha: 2026-02-28

## Objetivo
Cerrar la TODO de calidad semántica residual en `PSC` dentro de `programas_partidos` y mantener la lane en estado reproducible con gate declarado en verde.

## Cambios aplicados
- Extractor: expansión de verbos/nominalizaciones programáticas en `etl/parlamentario_es/declared_stance.py` para capturar formulaciones de propuesta frecuentes en manifiestos.
- Tests: ampliación de `tests/test_parl_declared_stance.py` (casos nominales ES/CA).
- Recompute correcto del source declarado:
  - `backfill-declared-stance --source-id programas_partidos`
  - `backfill-declared-positions --source-id programas_partidos --as-of-date 2026-02-28`
  - `backfill-combined-positions --as-of-date 2026-02-28`

## Incidente detectado y corregido
Durante el primer pase de AI-OPS-252, `backfill-declared-positions` se ejecutó por error sobre `congreso_intervenciones`. Se corrigió re-ejecutando el backfill con `--source-id programas_partidos` y regenerando quality/tracker artifacts.

## Resultado (post-fix, post-ignore)
Delta AI-OPS-251(v4) -> AI-OPS-252:
- `support`: `134 -> 199` (`+65`)
- `unclear`: `361 -> 296` (`-65`)
- `declared_positions_total`: `173 -> 237` (`+64`)
- `party_proxy_count`: `15 -> 15`
- `review_pending`: `0 -> 0`

Cierre de `PSC`:
- `evidence_rows=36`
- `support_rows=21`
- `unclear_rows=15`

Gate y tracker:
- `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate`: `passed=true`
- `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`: `mismatches=0`, `done_zero_real=0`

## Evidencia principal
- `docs/etl/sprints/AI-OPS-252/evidence/backfill_declared_positions_programas_semantic_nominal_v4_fix_20260228.log`
- `docs/etl/sprints/AI-OPS-252/evidence/programas_declared_status_post_semantic_nominal_v4_fix_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-252/evidence/quality_declared_programas_post_semantic_nominal_v4_fix_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-252/evidence/tracker_status_post_semantic_nominal_v4_fix_post_ignore_enforce_20260228.log`
- `docs/etl/sprints/AI-OPS-252/exports/programas_status_delta_ai_ops_251_v4_vs_ai_ops_252_semantic_nominal_fix_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-252/exports/programas_party_delta_ai_ops_251_v4_vs_ai_ops_252_semantic_nominal_fix_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-252/exports/programas_psc_url_quality_audit_post_semantic_nominal_v4_fix_post_ignore_20260228.csv`

## Gap residual abierto
Sigue pendiente la calidad semántica en partidos con `support=0` (`BNG`, `EH Bildu`, `EQUO`) y mejora de baja señal en `PP`/`VOX`.
