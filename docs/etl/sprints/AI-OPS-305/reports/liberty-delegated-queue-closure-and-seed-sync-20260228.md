# AI-OPS-305 — Liberty delegated queue closure + seed sync (2026-02-28)

## Objetivo
Cerrar de forma reproducible el gap operativo de la fila 716 (`Regulación delegada y enforcement`) en DB principal, eliminando cola accionable residual y sincronizando la seed canónica con decisiones aprobadas en sprints previos.

## Trabajo realizado
- Consolidación de seed delegada aplicando decisiones en cadena:
  - base: `docs/etl/sprints/AI-OPS-286/exports/liberty_delegated_enforcement_seed_pending_reviewed_latest.json`
  - apply targeted: `AI-OPS-288` (`liberty_delegated_person_window_auto_review_decisions_targeted_latest.csv`)
  - apply alternativo: `AI-OPS-292` + `AI-OPS-293`
  - resultado: `docs/etl/sprints/AI-OPS-305/exports/liberty_delegated_enforcement_seed_consolidated_latest.json`
- Sincronización de seed canónica:
  - `etl/data/seeds/liberty_delegated_enforcement_seed_v1.json` actualizado con la consolidada.
- Hardening operativo:
  - `scripts/apply_liberty_delegated_person_window_reviews.py` ahora soporta fallback de imports para ejecución directa (`python3 scripts/...`).
  - `scripts/report_liberty_delegated_person_window_queue.py` incorpora:
    - dedupe por `fragment_id` usando la versión más reciente (`--dedupe-fragment-latest`, default `true`), para evitar doble conteo de filas históricas,
    - excepción explícita para actor no nominativo aprobado (`approved_non_nominative_unit_from_*`), ya validado por QA manual.
- Reimport en DB principal desde seed consolidada y verificación strict de cola.

## Resultado real
### Cola delegada (strict)
- Before: `status=degraded`, `actionable_queue_rows=8`, `strict_fail_reasons=[actionable_rows_above_threshold]`
- After: `status=ok`, `actionable_queue_rows=0`, `strict_fail_reasons=[]`
- Delta: `-8`

### Observabilidad de dedupe
- `links_total_raw=16`
- `links_total_effective=8`
- `duplicate_rows_dropped_total=8`

### Gate de enforcement delegado
- `parl-check-liberty-delegated-enforcement-gate` en verde (`rc=0`)
- `gate.passed=true`
- coberturas: `target_fragment_coverage_pct=1.0`, `designated_actor_coverage_pct=1.0`, `enforcement_evidence_coverage_pct=0.9375`

## Evidencia
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_apply_step1_from_288.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_apply_step2_from_292.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_apply_step3_from_293.json`
- `docs/etl/sprints/AI-OPS-305/exports/liberty_delegated_enforcement_seed_consolidated_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/validate_liberty_delegated_enforcement_seed_canonical_after_sync_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_import_consolidated_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_person_window_queue_strict_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_person_window_queue_strict_after_import_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_person_window_queue_strict_delta_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/just_parl_check_liberty_delegated_enforcement_gate_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-305/evidence/liberty_delegated_enforcement_status_latest.json`
- `docs/etl/sprints/AI-OPS-305/evidence/unittest_liberty_delegated_seed_sync_stack_latest.txt`
- `docs/etl/sprints/AI-OPS-305/evidence/tracker_status_latest.log`

## Siguiente comando
`DB_PATH=<db> LIBERTY_DELEGATED_PERSON_QUEUE_MAX_ACTIONABLE_ROWS=0 just parl-check-liberty-delegated-person-window-queue && DB_PATH=<db> just parl-check-liberty-delegated-enforcement-gate`
