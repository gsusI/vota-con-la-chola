# AI-OPS-261 - Cierre gate de precision minima por partido (`programas_partidos`)

## Objetivo
Cerrar el TODO de tracker para endurecer el guardrail de precision de `programas_partidos` con floor por partido y curacion dirigida de falsos positivos detectados.

## Cambios implementados
- `scripts/report_programas_support_precision_audit.py`
  - Nuevo argumento `--min-party-precision`.
  - Nuevos checks en reporte:
    - `required_parties_min_precision`
    - `below_min_party_precision`
    - `precision_by_required_party`
  - Nuevo fail reason estricto: `required_party_precision_below_threshold`.
- `justfile`
  - Nuevo env var `PROGRAMAS_PRECISION_MIN_PARTY` (default `0.85`).
  - Wiring del nuevo umbral en:
    - `parl-report-programas-support-precision-audit`
    - `parl-check-programas-support-precision-audit`
    - `parl-programas-precision-guardrail-rotated`
- `etl/parlamentario_es/declared_stance.py`
  - Hardening del fallback `programa_policy_proposal` para bloquear contexto historico/narrativo sin intencion programatica fuerte.
  - Resultado: los FPs objetivo (`1560538`, `1560545`, `1561270`, `1561275`) dejan de clasificarse como `support` y pasan a `unclear` tras reconcile.
- Tests
  - `tests/test_report_programas_support_precision_audit.py`: cobertura de fail por floor de precision por partido.
  - `tests/test_parl_declared_stance.py`: regresion para contextos historicos que no deben disparar `support`.

## Corrida E2E (staging)
Comando principal:
- `DB_PATH=etl/data/staging/politicos-es.db SNAPSHOT_DATE=2026-02-28 PROGRAMAS_PRECISION_MIN=0.90 PROGRAMAS_PRECISION_MIN_PARTY=0.85 just parl-programas-precision-guardrail-rotated`

Resultados:
- Muestra rotada: `40` filas (`10` por partido), `carried_forward=40`, `unlabeled=0`.
- Audit estricto:
  - `reviewed=40`, `precision=1.0`
  - `precision_by_required_party`: `BNG=1.0`, `VOX=1.0`, `FORO Asturias=1.0`, `PP=1.0`
  - `required_parties_min_precision=true` (umbral `0.85`)
- Reconcile/backfill:
  - `support=386`, `unclear=178`, `review_pending=0`
  - `declared_positions_total=400`, `declared_positions_by_stance={support:399, oppose:1}`
- Quality declared gate: `passed=true`.
- Tracker enforce: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-261/evidence/programas_support_precision_audit_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-261/exports/programas_support_precision_audit_guardrail_breakdown_latest.csv`
- `docs/etl/sprints/AI-OPS-261/evidence/programas_backfill_declared_stance_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-261/evidence/programas_declared_status_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-261/evidence/programas_quality_declared_guardrail_latest.json`
- `docs/etl/sprints/AI-OPS-261/evidence/tracker_status_programas_guardrail_latest.log`
- `docs/etl/sprints/AI-OPS-261/exports/programas_precision_party_floor_false_positive_candidates_latest.csv`
- `docs/etl/sprints/AI-OPS-261/evidence/unittest_programas_party_floor_guardrail_20260228.txt`
