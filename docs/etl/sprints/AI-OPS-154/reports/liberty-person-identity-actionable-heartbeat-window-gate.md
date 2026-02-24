# AI-OPS-154 - Heartbeat + ventana estricta para cola accionable de identidad personal

## Donde estamos ahora
- La fila `103` ya separa backlog `actionable` vs placeholders (`AI-OPS-153`) y tiene check puntual `parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-empty`.
- Faltaba observabilidad histórica append-only y una ventana estricta para detectar regresión de forma automática en el pipeline principal.

## A donde vamos
- Mantener cierre operativo continuo del loop `manual_seed -> official_*` sin depender de chequeo manual por sprint.
- Exigir no solo estado puntual `latest`, sino también estabilidad en ventana (`last N`) con umbrales explícitos.

## Cambios entregados
- Nuevo heartbeat append-only:
  - `scripts/report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.py`
  - Lee el resumen de `export_liberty_person_identity_official_upgrade_review_queue.py` (modo `--only-actionable`), persiste JSONL deduplicado y marca `status=failed` cuando reaparece backlog accionable.
- Nueva ventana estricta:
  - `scripts/report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window.py`
  - Evalúa `failed_in_window` y `actionable_nonempty_runs_in_window` con thresholds configurables.
- Integración operativa (`justfile`):
  - Nuevas variables/env para heartbeat + window (`...HEARTBEAT_PATH`, `...WINDOW_*`).
  - Nuevos lanes:
    - `parl-report-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat`
    - `parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat`
    - `parl-check-liberty-person-identity-official-upgrade-review-queue-actionable-heartbeat-window`
  - `parl-liberty-restrictions-pipeline` ahora ejecuta:
    - heartbeat report
    - check puntual strict-empty
    - check de ventana strict
- CI:
  - `.github/workflows/etl-tracker-gate.yml` incluye tests nuevos del heartbeat/window en `liberty-focus-gate-contract`.
- Tests nuevos:
  - `tests/test_report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat.py`
  - `tests/test_report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window.py`

## Validacion
- Tests focales heartbeat/window:
  - `Ran 5`, `OK`
  - Evidencia: `docs/etl/sprints/AI-OPS-154/evidence/unittest_liberty_person_identity_actionable_heartbeat_20260223T235521Z.txt`
- Suite completa `Derechos`:
  - `Ran 99`, `OK (skipped=1)`
  - Evidencia: `docs/etl/sprints/AI-OPS-154/evidence/just_parl_test_liberty_restrictions_20260223T235521Z.txt`
- Corrida real sobre `etl/data/staging/politicos-es.db`:
  - `actionable_rows_total=0`
  - `actionable_queue_empty=true`
  - heartbeat `status=ok`
  - ventana (`last=20`) `status=ok`, `failed_in_window=0`, `actionable_nonempty_runs_in_window=0`
  - Evidencia:
    - `docs/etl/sprints/AI-OPS-154/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_20260223T235521Z.json`
    - `docs/etl/sprints/AI-OPS-154/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_20260223T235521Z.json`
    - `docs/etl/sprints/AI-OPS-154/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_20260223T235521Z.json`
    - `docs/etl/sprints/AI-OPS-154/evidence/just_parl_report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_20260223T235521Z.txt`
    - `docs/etl/sprints/AI-OPS-154/evidence/just_parl_check_liberty_person_identity_official_upgrade_review_queue_actionable_empty_20260223T235521Z.txt`
    - `docs/etl/sprints/AI-OPS-154/evidence/just_parl_check_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window_20260223T235521Z.txt`

## Siguiente paso
- Mantener la rutina en cada sprint via `parl-liberty-restrictions-pipeline`.
- Si `actionable_rows_total >= 1`, abrir batch de `review-decision` y volver a verde en heartbeat + ventana.
