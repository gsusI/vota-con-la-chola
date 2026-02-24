# AI-OPS-139 - Derechos: contrato top_n estable en scoring personal

## Objetivo del slice
Corregir un sesgo operativo del lane de scoring personal (fila `103`): el parámetro de visualización `top_n` no debe alterar los totales de scoring ni gates (`persons_scored_total`).

## Implementacion
- `scripts/report_liberty_personal_accountability_scores.py`:
  - separa ranking completo (`all_person_scores`) de salida capada (`top_person_scores`),
  - calcula `persons_scored_total` sobre el universo completo,
  - añade `totals.top_person_scores_total`,
  - documenta en metodología que `top_n` es solo límite de visualización y no afecta gates.
- Test de regresión:
  - `tests/test_report_liberty_personal_accountability_scores.py` añade `test_persons_scored_total_not_truncated_by_top_n`.
  - Verifica estabilidad de `persons_scored_total` entre `top_n=1` y `top_n` amplio.

## Resultado de corrida (20260223T214125Z)
- Contrato top_n:
  - `top1_persons_scored_total=9`
  - `top200_persons_scored_total=9`
  - `persons_total_stable_across_topn=true`
  - `top1_top_person_scores_total=1`
  - `top200_top_person_scores_total=9`
- Fail-path contractual:
  - `--min-persons-scored 99 --enforce-gate`
  - `status=degraded`
  - `exit=2`
- Tests:
  - suite focal + export snapshot: `Ran 7 tests ... OK (skipped=1)`
  - suite completa derechos: `Ran 65 tests ... OK (skipped=1)`

## Evidencia
- Reportes top_n:
  - `docs/etl/sprints/AI-OPS-139/evidence/liberty_personal_accountability_top1_20260223T214125Z.json`
  - `docs/etl/sprints/AI-OPS-139/evidence/liberty_personal_accountability_top200_20260223T214125Z.json`
  - `docs/etl/sprints/AI-OPS-139/evidence/liberty_personal_accountability_topn_contract_20260223T214125Z.json`
- Fail-path:
  - `docs/etl/sprints/AI-OPS-139/evidence/liberty_personal_accountability_gate_fail_20260223T214125Z.json`
  - `docs/etl/sprints/AI-OPS-139/evidence/liberty_personal_accountability_gate_fail_rc_20260223T214125Z.txt`
- Import reproducible de soporte:
  - `docs/etl/sprints/AI-OPS-139/evidence/just_parl_import_sanction_norms_seed_20260223T214125Z.txt`
  - `docs/etl/sprints/AI-OPS-139/evidence/just_parl_import_liberty_restrictions_seed_20260223T214125Z.txt`
  - `docs/etl/sprints/AI-OPS-139/evidence/just_parl_import_liberty_indirect_accountability_seed_20260223T214125Z.txt`
- Tests:
  - `docs/etl/sprints/AI-OPS-139/evidence/unittest_liberty_personal_topn_contract_20260223T214125Z.txt`
  - `docs/etl/sprints/AI-OPS-139/evidence/just_parl_test_liberty_restrictions_20260223T214125Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-personal-accountability-gate
```
