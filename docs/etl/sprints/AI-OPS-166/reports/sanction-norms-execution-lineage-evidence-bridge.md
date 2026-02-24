# AI-OPS-166 — Puente de lineage para cerrar ejecucion en `delegate`

## Objetivo
Cerrar el gap de cobertura de ejecucion en rol `delegate` (`0/2`) sin depender de nuevas fuentes externas, reutilizando observaciones sancionadoras ya cargadas y la capa de lineage normativo.

## Cambios implementados
- `scripts/backfill_sanction_norms_execution_lineage_evidence.py` (nuevo)
  - Conecta responsabilidades de `legal_fragment_responsibilities` con observaciones de `sanction_volume_observations` via:
    - `delegate_to_observed_direct`
    - `shared_related_norm`
  - Materializa evidencia `other` en `legal_fragment_responsibility_evidence` con `record_kind=sanction_norm_execution_lineage_bridge_backfill`.
  - Resuelve `source_record_pk` por `boe_ref:<BOE-ID>` para mantener trazabilidad no-seed.
- `scripts/report_sanction_norms_seed_status.py`
  - Incluye `sanction_norm_execution_lineage_bridge_backfill` en los KPIs/checks de cadena de ejecucion.
- `justfile`
  - Nuevo lane `parl-backfill-sanction-norms-execution-lineage-evidence`.
  - Variables dedicadas `SANCTION_NORMS_EXECUTION_LINEAGE_EVIDENCE_*`.
- Tests
  - Nuevo `tests/test_backfill_sanction_norms_execution_lineage_evidence.py`.
  - Regresión en `tests/test_report_sanction_norms_seed_status.py` para garantizar el cómputo del nuevo `record_kind`.

## Corrida de cierre (DB real)
Timestamp: `20260224T014904Z`

### Backfill lineage (`roles=delegate`)
- `responsibilities_scanned_total=2`
- `observations_scanned_total=7`
- `responsibilities_with_lineage_match_total=2`
- `observation_links_total=4`
- `evidence_inserted=4`
- `source_record_pk_resolved_total=4`
- `by_match_method={shared_related_norm:3, delegate_to_observed_direct:1}`
- `by_delegate_norm={es:boe-a-1994-8985:2, es:boe-a-2004-18398:2}`

### Estado agregado lane sancionador
- `responsibility_evidence_items_total=66` (antes `62`)
- `responsibility_evidence_items_execution_total=29` (antes `25`)
- `responsibilities_with_execution_evidence_total=13/15` (antes `11/15`)
- `responsibility_execution_coverage_pct=0.866667` (antes `0.733333`)
- Cobertura por rol de ejecucion:
  - `approve=6/6`
  - `propose=3/3`
  - `delegate=2/2`
  - `enforce=2/4`
- `responsibility_evidence_item_non_seed_source_record_coverage_pct=1.0`
- Cola `seed->non-seed`: `queue_rows_total=0`
- `PRAGMA foreign_key_check`: `0` filas

## Validacion
- `just parl-test-sanction-norms-seed` -> `Ran 25`, `OK`
- `just parl-test-liberty-restrictions` -> `Ran 100`, `OK (skipped=1)`

## Evidencia
- `docs/etl/sprints/AI-OPS-166/evidence/sanction_norms_execution_lineage_evidence_backfill_20260224T014904Z.json`
- `docs/etl/sprints/AI-OPS-166/evidence/sanction_norms_seed_status_20260224T014904Z.json`
- `docs/etl/sprints/AI-OPS-166/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T014904Z.json`
- `docs/etl/sprints/AI-OPS-166/evidence/sqlite_fk_check_20260224T014904Z.txt`
- `docs/etl/sprints/AI-OPS-166/evidence/just_parl_test_sanction_norms_seed_20260224T014904Z.txt`
- `docs/etl/sprints/AI-OPS-166/evidence/just_parl_test_liberty_restrictions_20260224T014904Z.txt`

## Siguiente paso sugerido
Cerrar el gap residual en `enforce` (`2/4`) con el mismo enfoque de puente + señales de ejecución/procedimentales priorizando normas con baja observación real.
