# AI-OPS-162 - Backfill de evidencia parlamentaria en la cadena sancionadora

## Donde estamos ahora
- La procedencia documental `seed -> non-seed` quedó cerrada en AI-OPS-161 (`seed=0`, `non-seed=15`, cola de upgrade vacía), pero la cadena seguía sin señal explícita de evidencia parlamentaria (Congreso/Senado) en `legal_fragment_responsibility_evidence`.

## A donde vamos
- Arrancar de forma reproducible la pista parlamentaria (`congreso_diario/senado_diario`) para normas sancionadoras, sin romper el contrato de evidencia primaria.
- Mantener `status=ok` del lane y `queue_rows_total=0` del upgrade `seed -> non-seed`.

## Cambios entregados
- Nuevo backfill:
  - `scripts/backfill_sanction_norms_parliamentary_evidence.py`
  - Extrae referencias `BOE-A-YYYY-NNNN` desde `text_documents` (`source_id=parl_initiative_docs`), cruza con normas del catálogo sancionador y materializa evidencia por responsabilidad (roles por defecto: `approve,propose`).
  - Mapea evidencia a tipo parlamentario por cámara (`congreso_* -> congreso_diario`, `senado_* -> senado_diario`).
  - Idempotencia: actualiza filas existentes y corrige legacy con `evidence_date` vacío.
- Observabilidad ampliada en status:
  - `scripts/report_sanction_norms_seed_status.py` añade:
    - `responsibility_evidence_items_parliamentary_total`
    - `responsibilities_with_parliamentary_evidence_total`
    - `responsibilities_missing_parliamentary_evidence`
    - `responsibility_evidence_item_parliamentary_share_pct`
    - `responsibility_parliamentary_coverage_pct`
    - check `responsibility_evidence_parliamentary_chain_started`
- Integración `just`:
  - `parl-backfill-sanction-norms-parliamentary-evidence`
  - vars:
    - `SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_OUT`
    - `SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_ROLES`
    - `SANCTION_NORMS_PARLIAMENTARY_EVIDENCE_LIMIT`
- Test nuevo:
  - `tests/test_backfill_sanction_norms_parliamentary_evidence.py`
  - agregado a `just parl-test-sanction-norms-seed`.

## Validacion
- Corrida AI-OPS-162 (`20260224T010415Z`):
  - Backfill parlamentario:
    - `docs_scanned_total=9016`
    - `docs_with_boe_token_total=1497`
    - `candidate_matches_total=2`
    - `evidence_inserted=0`, `evidence_updated=2` (idempotencia + normalización de fechas)
    - `by_evidence_type.senado_diario=2`
  - Status lane:
    - `status=ok`
    - `responsibility_evidence_items_total=17`
    - `responsibility_evidence_items_with_primary_fields_total=17`
    - `responsibility_evidence_items_parliamentary_total=2`
    - `responsibility_evidence_parliamentary_chain_started=true`
    - `responsibility_evidence_item_parliamentary_share_pct=0.117647`
    - `responsibility_parliamentary_coverage_pct=0.133333`
    - `responsibility_evidence_items_with_non_seed_source_record_total=17`
    - `responsibility_evidence_item_non_seed_source_record_coverage_pct=1.0`
  - Cola de upgrade seed/non-seed:
    - `queue_rows_total=0`
    - `queue_empty=true`
  - Integridad y regresión:
    - `PRAGMA foreign_key_check`: `fk_violations_total=0`
    - `just parl-test-sanction-norms-seed`: `Ran 17`, `OK`
    - `just parl-test-liberty-restrictions`: `Ran 100`, `OK (skipped=1)`

Evidencia:
- `docs/etl/sprints/AI-OPS-162/evidence/sanction_norms_parliamentary_evidence_backfill_20260224T010415Z.json`
- `docs/etl/sprints/AI-OPS-162/evidence/sanction_norms_seed_status_20260224T010415Z.json`
- `docs/etl/sprints/AI-OPS-162/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T010415Z.json`
- `docs/etl/sprints/AI-OPS-162/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T010415Z.csv`
- `docs/etl/sprints/AI-OPS-162/evidence/sqlite_fk_check_20260224T010415Z.json`
- `docs/etl/sprints/AI-OPS-162/evidence/just_parl_test_liberty_restrictions_20260224T010415Z.txt`

## Siguiente paso
- Extender la misma lógica desde referencias BOE en iniciativas hacia evidencia parlamentaria de actos (`congreso_vote/senado_vote`) y enlazarla con la cadena `acto sancionador -> cobro -> recurso/resultado`.
