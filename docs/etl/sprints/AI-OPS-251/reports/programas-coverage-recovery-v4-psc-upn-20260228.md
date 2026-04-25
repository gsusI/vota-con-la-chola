# AI-OPS-251 - Cierre de cobertura residual (`PSC`/`UPN`)

## Objetivo
Cerrar la recuperación de cobertura partidaria post-higiene dejando `party_proxy_count` sin partidos en cero.

## Cambios ejecutados
- Manifest `v4` sobre baseline AI-OPS-250 `v3`:
  - `PSC` (`3` ciclos): `https://www.socialistes.cat/programa` -> `https://www.socialistes.cat/es/actualitat/programa-electoral-psc-montgat-2023-2027/`
  - `UPN` (`3` ciclos): `https://www.upn.org/propuestas-de-upn-para-la-proxima-legislatura-en-materia-de-discapacidad/` -> `https://elecciones.upn.org/programa/`
- Corrida real en staging (`strict-network`): `run_id=302`, `records_seen=51`, `records_loaded=51`.
- Recompute declarado/combinado + cierre reproducible de cola (`45` pendientes -> `0` ignorados).
- Gates:
  - `declared.gate.passed=true`
  - `e2e_tracker_status` enforce: `mismatches=0`, `done_zero_real=0`.

## Resultado (AI-OPS-250 v3 -> AI-OPS-251 v4, post-ignore)
- `party_proxy_count`: `13 -> 15` (`+2`)
- `support`: `107 -> 134` (`+27`)
- `unclear`: `316 -> 361` (`+45`)
- `declared_positions_total`: `146 -> 173` (`+27`)
- `review_pending`: `0 -> 0`

## Cierre de cobertura
- Sin partidos en cero (`missing_count=0`).
- Delta por partido recuperado:
  - `PSC`: `evidence 0 -> 36` (`support 0`, `unclear 36`)
  - `UPN`: `evidence 0 -> 36` (`support 27`, `unclear 9`)

## Lectura operativa
- El objetivo de cobertura queda cerrado en esta lane: todos los partidos objetivo vuelven a tener evidencia.
- Persiste deuda de calidad semántica en `PSC` (`support=0`), que requiere afinado de fuente/candidato o reglas semánticas específicas sin perder el contrato de higiene.

## Evidencia
- `docs/etl/sprints/AI-OPS-251/evidence/programas_ingestion_runs_latest_20260228.csv`
- `docs/etl/sprints/AI-OPS-251/evidence/programas_declared_status_post_recovery_v4_psc_upn_targeted_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-251/evidence/quality_declared_programas_post_recovery_v4_psc_upn_targeted_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-251/evidence/tracker_status_post_recovery_v4_psc_upn_targeted_post_ignore_enforce_20260228.log`
- `docs/etl/sprints/AI-OPS-251/exports/programas_status_delta_ai_ops_250_v3_vs_ai_ops_251_v4_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-251/exports/programas_party_delta_ai_ops_250_v3_vs_ai_ops_251_v4_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-251/exports/programas_party_missing_after_recovery_v4_psc_upn_targeted_post_ignore_20260228.csv`
