# AI-OPS-138 - Derechos: scoring personal reproducible de atribucion

## Objetivo del slice
Cerrar el gap operativo de la fila `103` (atribucion personal) con un lane reproducible que combine cadena directa e indirecta y publique un ranking personal auditable por evidencia.

## Implementacion
- Script nuevo: `scripts/report_liberty_personal_accountability_scores.py`.
- Cobertura de scoring:
  - Directo: `legal_fragment_responsibilities` con `person_id`.
  - Indirecto: `liberty_indirect_responsibility_edges` filtrando por confianza, distancia causal y ventana persona/cargo valida.
- Formula explicita:
  - `weighted = irlc_score * role_weight * edge_confidence * primary_evidence_factor`
  - `primary_evidence_factor = 1.0` si hay evidencia primaria completa (`source_url`, `evidence_date`, `evidence_quote`), `0.5` en caso contrario.
- Gates operativos añadidos:
  - `min_persons_scored_gate`
  - `personal_fragment_coverage_gate`
  - `personal_primary_evidence_gate`
  - `indirect_person_window_gate`
- `justfile` integra lane y check:
  - `parl-report-liberty-personal-accountability-scores`
  - `parl-check-liberty-personal-accountability-gate`
  - ejecución dentro de `parl-liberty-restrictions-pipeline`.
- Snapshot:
  - `scripts/export_liberty_restrictions_snapshot.py` publica `personal_accountability_scores`, `personal_accountability_methodology`, `personal_accountability_summary` y `persons_scored_total`.

## Resultado de corrida (20260223T213615Z)
- Estado principal:
  - `status=ok`
  - `persons_scored_total=9`
  - `personal_edges_total=13`
  - `personal_edges_with_primary_evidence_total=13`
  - `fragments_with_personal_accountability_total=7/8`
  - `fragments_with_personal_accountability_pct=0.875`
  - `personal_edges_with_primary_evidence_pct=1.0`
  - `indirect_person_edges_with_valid_window_pct=1.0`
  - `gate.passed=true`
- Fail-path contractual:
  - Umbrales imposibles (`min_persons_scored=20` y pct > 1.0)
  - `status=degraded`
  - checks de gate en `false`
  - `exit=2`

## Evidencia
- Report/gate:
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_personal_accountability_scores_20260223T213615Z.json`
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_personal_accountability_gate_20260223T213615Z.json`
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_personal_accountability_gate_fail_20260223T213615Z.json`
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_personal_accountability_gate_fail_rc_20260223T213615Z.txt`
- Seeds/import de soporte:
  - `docs/etl/sprints/AI-OPS-138/evidence/sanction_norms_seed_import_20260223T213615Z.json`
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_restrictions_import_20260223T213615Z.json`
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_indirect_import_20260223T213615Z.json`
- Snapshot:
  - `docs/etl/sprints/AI-OPS-138/evidence/liberty_restrictions_snapshot_20260223T213615Z.json`
- Tests:
  - `docs/etl/sprints/AI-OPS-138/evidence/unittest_liberty_personal_scoring_20260223T213615Z.txt`
  - `docs/etl/sprints/AI-OPS-138/evidence/just_parl_test_sanction_norms_seed_20260223T213615Z.txt`
  - `docs/etl/sprints/AI-OPS-138/evidence/just_parl_test_liberty_restrictions_20260223T213615Z.txt`

## Comando de continuidad
```bash
DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-personal-accountability-gate
```
