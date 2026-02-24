# AI-OPS-135 — Liberty Accountability Primary Evidence Seed Hardening

## Objetivo
Cerrar el gap operativo de evidencia primaria en accountability (`source_url`, `evidence_date`, `evidence_quote`) para que el gate de foco de `Derechos` deje de operar en modo observabilidad y quede estricto por defecto.

## Implementación
- `scripts/validate_sanction_norms_seed.py`
  - `responsibility_hints` ahora exige: `source_url` (http/https), `evidence_date` (`YYYY-MM-DD`), `evidence_quote` no vacío.
- `scripts/import_sanction_norms_seed.py`
  - Inserta y actualiza `evidence_date` y `evidence_quote` en `legal_fragment_responsibilities`.
- `scripts/report_sanction_norms_seed_status.py`
  - Añade cobertura de evidencia primaria: `responsibilities_with_primary_evidence_total`, `responsibilities_missing_primary_evidence`, `responsibility_primary_evidence_coverage_pct`, y checks asociados.
- `etl/data/seeds/sanction_norms_seed_v1.json`
  - Se poblaron `evidence_date` y `evidence_quote` en todos los `responsibility_hints`.
- `scripts/report_liberty_restrictions_status.py` + `justfile`
  - Se endurece el contrato por defecto: `accountability_primary_evidence_min_pct=1.0` y `min_accountability_primary_evidence_edges=1`.
- Tests
  - Actualizados/extendidos: `tests/test_validate_sanction_norms_seed.py`, `tests/test_import_sanction_norms_seed.py`, `tests/test_report_sanction_norms_seed_status.py`, `tests/test_report_liberty_restrictions_status.py`.

## Resultado de corrida (2026-02-23T21:09:08Z)
- `sanction_norms_seed_status`: `status=ok`
  - `responsibilities_total=15`
  - `responsibilities_with_primary_evidence_total=15`
  - `responsibility_primary_evidence_coverage_pct=1.0`
- `liberty_restrictions_status`: `status=ok`
  - `accountability_edges_total=15`
  - `accountability_edges_with_primary_evidence_total=15`
  - `accountability_edges_with_primary_evidence_pct=1.0`
  - `focus_gate.passed=true` con defaults estrictos.
- `liberty_restrictions_status_heartbeat_window`: `status=ok`
  - `accountability_primary_evidence_gate_failed_in_window=0`
- Fail-path contractual (umbral imposible):
  - `LIBERTY_RESTRICTIONS_ACCOUNTABILITY_PRIMARY_EVIDENCE_MIN_PCT=1.1`
  - `LIBERTY_RESTRICTIONS_MIN_ACCOUNTABILITY_PRIMARY_EVIDENCE_EDGES=20`
  - Resultado: `status=degraded`, `exit=2`.
- Corrida E2E completa (`just parl-liberty-restrictions-pipeline`) en este DB:
  - Falla en `parl-report-liberty-atlas-release-heartbeat` por drift `published vs HF` (`strict_fail_reasons: published_hf_drift_detected, gh_pages_hf_drift_detected`), porque el release local nuevo no se ha publicado todavía en HF.

## Evidencia
- `docs/etl/sprints/AI-OPS-135/evidence/sanction_norms_seed_validate_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/sanction_norms_seed_import_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/sanction_norms_seed_status_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_validate_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_import_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_status_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_status_heartbeat_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_status_heartbeat_window_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/liberty_restrictions_focus_gate_accountability_primary_evidence_fail_20260223T210908Z.json`
- `docs/etl/sprints/AI-OPS-135/evidence/just_parl_check_liberty_focus_gate_accountability_primary_evidence_fail_rc_20260223T210908Z.txt`
- `docs/etl/sprints/AI-OPS-135/evidence/unittest_sanction_primary_evidence_contract_20260223T210908Z.txt`
- `docs/etl/sprints/AI-OPS-135/evidence/just_parl_test_sanction_norms_seed_20260223T210908Z.txt`
- `docs/etl/sprints/AI-OPS-135/evidence/just_parl_test_liberty_restrictions_20260223T210908Z.txt`
- `docs/etl/sprints/AI-OPS-135/evidence/just_parl_liberty_restrictions_pipeline_20260223T210908Z.txt`
- `docs/etl/sprints/AI-OPS-135/evidence/just_parl_liberty_restrictions_pipeline_rc_20260223T210908Z.txt`

## Comando de continuidad
`DB_PATH=<db> SNAPSHOT_DATE=2026-02-23 just parl-liberty-restrictions-pipeline`
