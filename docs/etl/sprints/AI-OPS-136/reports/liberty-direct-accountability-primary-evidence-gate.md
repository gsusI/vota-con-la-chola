# AI-OPS-136 — Liberty Direct Accountability Primary Evidence Gate

## Objetivo
Endurecer la cadena de responsabilidad directa (`propose/approve/enforce`) para exigir trazabilidad primaria por edge y bloquear regresiones en el score directo.

## Implementación
- `scripts/report_liberty_direct_accountability_scores.py`
  - Nuevas métricas:
    - `direct_edges_with_primary_evidence_total`
    - `coverage.direct_edges_with_primary_evidence_pct`
  - Nuevo check:
    - `checks.direct_primary_evidence_gate`
  - `gate.passed` ahora exige:
    - `direct_coverage_gate` y `direct_primary_evidence_gate`.
  - Nuevos parámetros CLI:
    - `--direct-primary-evidence-min-pct`
    - `--min-direct-primary-evidence-edges`
- `justfile`
  - Nuevas variables:
    - `LIBERTY_DIRECT_ACCOUNTABILITY_PRIMARY_EVIDENCE_MIN_PCT` (default `1.0`)
    - `LIBERTY_DIRECT_ACCOUNTABILITY_MIN_PRIMARY_EVIDENCE_EDGES` (default `1`)
  - Propagadas en:
    - `parl-report-liberty-direct-accountability-scores`
    - `parl-check-liberty-direct-accountability-gate`
- Tests
  - `tests/test_report_liberty_direct_accountability_scores.py`
    - Aserciones de gate/metrics de evidencia primaria.
    - Caso degradado con umbral imposible.

## Corrida reproducible (2026-02-23T21:16:23Z)
- `liberty_direct_accountability_scores`: `status=ok`
  - `fragments_with_direct_chain_total=8/8`
  - `direct_edges_total=19`
  - `direct_edges_with_primary_evidence_total=19`
  - `direct_edges_with_primary_evidence_pct=1.0`
  - `gate.passed=true`
- Fail-path contractual (umbral imposible)
  - `direct_primary_evidence_min_pct=1.1`
  - `min_direct_primary_evidence_edges=20`
  - Resultado: `status=degraded`, `direct_primary_evidence_gate=false`, `exit=2`.
- Tests
  - Focales: `Ran 12 tests ... OK`
  - `just parl-test-sanction-norms-seed`: `Ran 7 tests ... OK`
  - `just parl-test-liberty-restrictions`: `Ran 59 tests ... OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-136/evidence/sanction_norms_seed_validate_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/sanction_norms_seed_import_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/sanction_norms_seed_status_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/liberty_restrictions_validate_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/liberty_restrictions_import_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/liberty_direct_accountability_scores_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/liberty_direct_accountability_gate_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/liberty_direct_accountability_gate_primary_evidence_fail_20260223T211623Z.json`
- `docs/etl/sprints/AI-OPS-136/evidence/just_parl_check_liberty_direct_accountability_gate_primary_evidence_fail_rc_20260223T211623Z.txt`
- `docs/etl/sprints/AI-OPS-136/evidence/unittest_direct_accountability_primary_evidence_contract_20260223T211623Z.txt`
- `docs/etl/sprints/AI-OPS-136/evidence/just_parl_test_sanction_norms_seed_20260223T211623Z.txt`
- `docs/etl/sprints/AI-OPS-136/evidence/just_parl_test_liberty_restrictions_20260223T211623Z.txt`
- `docs/etl/sprints/AI-OPS-136/evidence/run_meta_20260223T211623Z.txt`

## Comando de continuidad
`DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-direct-accountability-gate`
