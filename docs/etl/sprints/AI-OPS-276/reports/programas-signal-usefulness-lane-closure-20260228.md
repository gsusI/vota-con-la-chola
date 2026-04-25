# AI-OPS-276 - Cierre de señal util en manifiestos web (`programas_partidos`)

## Objetivo
Cerrar la fila PARTIAL `Señal útil en manifiestos web (anti no_signal)` con contrato operativo estable y sin deuda duplicada con filas especializadas (`multilingue` e `higiene`).

## Contexto
Tras AI-OPS-275, el lane de `Empleo` fiscal quedó saneado cross-party (`suspicious_support_rows=0`), eliminando el principal leakage de `support` sin ancla laboral.

## Validaciones ejecutadas
1. Guardrail ratio dedupe BNG/VOX (`support_to_unclear_unique_ratio`, strict): `status=ok`.
   - BNG xerais: `3.0`
   - BNG europeas: `2.0`
   - VOX web: `3.6`
2. Gate declarado global de `programas_partidos`: `passed=true`.
3. Estado editorial: `review_pending=0`.
4. Tracker gate: `mismatches=0`, `done_zero_real=0`.

## Criterio de cierre aplicado
Se cierra la fila de señal útil porque el contrato anti-ruido está operativo y pasa en estricto:
- ratio dedupe por documento objetivo en verde,
- calidad declarada en verde,
- cola editorial pendiente en cero,
- leakage fiscal en `Empleo` controlado.

La deuda residual narrativa queda explícitamente acotada en filas específicas:
- `Señal semántica multilingüe en programas (ca/eu/gl)`
- `Higiene residual de manifiestos (ruido/no-programa)`

## Evidencia
- `docs/etl/sprints/AI-OPS-276/evidence/programas_support_unclear_unique_ratio_bng_vox_latest.json`
- `docs/etl/sprints/AI-OPS-276/exports/programas_support_unclear_unique_ratio_bng_vox_latest.csv`
- `docs/etl/sprints/AI-OPS-276/evidence/just_parl_check_programas_support_unclear_unique_ratio_bng_vox_latest.txt`
- `docs/etl/sprints/AI-OPS-276/evidence/programas_declared_status_latest.json`
- `docs/etl/sprints/AI-OPS-276/evidence/quality_declared_programas_latest.json`
- `docs/etl/sprints/AI-OPS-276/evidence/programas_signal_usefulness_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-276/evidence/tracker_status_latest.log`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_empleo_fiscal_snippets_audit_cross_party_latest.json`
