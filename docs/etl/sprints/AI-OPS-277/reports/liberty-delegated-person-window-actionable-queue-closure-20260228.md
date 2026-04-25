# AI-OPS-277 · Cola accionable persona/cargo en regulación delegada

## Objetivo
Cerrar un slice controlable de la fila `Regulacion delegada y enforcement de organismos (DGT y similares)` materializando una cola accionable reproducible para los gaps de `persona/cargo + ventana + evidencia`.

## Cambios
- Nuevo script: `scripts/report_liberty_delegated_person_window_queue.py`.
  - Construye cola accionable sobre `liberty_delegated_enforcement_links`.
  - Marca razones por enlace: `missing_designated_actor`, `institutional_designated_actor`, `missing_enforcement_evidence_date`, etc.
  - Exporta JSON + CSV, con modo `--strict` y umbral `--max-actionable-rows`.
- Nuevo test: `tests/test_report_liberty_delegated_person_window_queue.py`.
- Wiring en `justfile`:
  - `parl-report-liberty-delegated-person-window-queue`
  - `parl-check-liberty-delegated-person-window-queue`
  - variables `LIBERTY_DELEGATED_PERSON_QUEUE_*`
  - integración del test en `parl-test-liberty-restrictions`.

## Corrida real (staging)
DB: `etl/data/staging/politicos-es.db`.

1) Rehidratación secuencial de seeds (sin carrera):
- `parl-sanction-norms-seed-pipeline`
- `parl-import-liberty-restrictions-seed`
- `parl-import-liberty-delegated-enforcement-seed`

2) Estado base delegado (`parl-report-liberty-delegated-enforcement-status`):
- `status=ok`
- `links_total=8`
- `fragments_with_designated_actor_total=6`
- `links_with_enforcement_evidence_total=7`
- `weak_links_total=2`

3) Cola accionable (pass contractual):
- `parl-check-liberty-delegated-person-window-queue` con `LIBERTY_DELEGATED_PERSON_QUEUE_MAX_ACTIONABLE_ROWS=100`
- `status=ok`
- `actionable_queue_rows=8`
- `by_reason={missing_designated_actor:2, institutional_designated_actor:6, missing_enforcement_evidence_date:1}`

4) Fail-path contractual:
- mismo check con `LIBERTY_DELEGATED_PERSON_QUEUE_MAX_ACTIONABLE_ROWS=0`
- `status=degraded`
- `strict_fail_reasons=[actionable_rows_above_threshold]`
- `rc=4`

## Resultado
- Slice cerrado: la deuda residual de persona/cargo en delegación queda convertida en cola accionable deterministicamente exportable (`JSON+CSV`) y con gate estricto reproducible.
- La fila principal de delegación permanece `PARTIAL` (gap de sustitución real por cadena persona/cargo/evidencia primaria sigue abierto), pero ya tiene contrato operativo de remediación.
