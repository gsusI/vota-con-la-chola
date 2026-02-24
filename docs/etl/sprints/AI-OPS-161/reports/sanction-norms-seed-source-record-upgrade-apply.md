# AI-OPS-161 - Aplicar migracion `seed -> non-seed` en `source_record_pk` (lane sancionador)

## Donde estamos ahora
- AI-OPS-160 dejó una cola accionable abierta (`15` filas) para migrar evidencia sancionadora desde `source_records` seed hacia referencias canónicas de ingesta real.
- La cobertura documental ya estaba al `100%` (`15/15`), pero con procedencia `seed=15`, `non-seed=0`.

## A donde vamos
- Cerrar la cola `seed -> non-seed` con una ejecución reproducible sobre BOE real, manteniendo trazabilidad `norma -> fragmento -> responsabilidad -> evidencia -> source_record`.
- Dejar la base lista para extender la cadena fuera de seed (Congreso/Senado/ejecución por expediente).

## Cambios entregados
- Nuevo backfill canónico BOE:
  - `scripts/backfill_sanction_norms_boe_source_records.py`
  - Descarga `xml.php?id=<BOE-ID>` y crea/actualiza `source_records` canónicos con `source_record_id=boe_ref:<BOE-ID>` para `source_id=boe_api_legal`.
- Nuevo aplicador de upgrades:
  - `scripts/apply_sanction_norms_seed_source_record_upgrade_queue.py`
  - Reasigna `legal_fragment_responsibility_evidence.source_record_pk` desde filas seed a filas canónicas no-seed cuando existe candidato `boe_ref:<BOE-ID>`.
- Hardening del apply:
  - Se elimina un join redundante a `sanction_norm_fragment_links` para evitar duplicación de filas durante el apply.
- Integración operativa en `justfile`:
  - `parl-backfill-sanction-norms-boe-source-records`
  - `parl-apply-sanction-norms-source-record-upgrade`
  - vars de salida/límites para AI-OPS-161.
- Tests:
  - `tests/test_backfill_sanction_norms_boe_source_records.py`
  - `tests/test_apply_sanction_norms_seed_source_record_upgrade_queue.py`
  - Incluidos en `just parl-test-sanction-norms-seed`.

## Validacion
- Corrida de cierre (`20260224T005304Z`):
  - Backfill BOE: `targets_total=8`, `records_inserted=8`, `records_fetch_failed=0`, `records_html_blocked=0`.
  - Apply upgrade: `queue_rows_seen=15`, `upgraded_rows=15`, `missing_candidate_rows=0`.
  - Status lane: `responsibility_evidence_items_with_seed_source_record_total=0`, `responsibility_evidence_items_with_non_seed_source_record_total=15`, `responsibility_evidence_item_non_seed_source_record_coverage_pct=1.0`, `status=ok`.
  - Queue post-apply: `queue_rows_total=0`, `queue_empty=true`, `status=ok`.
- Integridad y regresión:
  - `PRAGMA foreign_key_check`: `fk_violations_total=0`
  - `just parl-test-sanction-norms-seed`: `Ran 16`, `OK`
  - `just parl-test-liberty-restrictions`: `Ran 100`, `OK (skipped=1)`

Evidencia:
- `docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_boe_backfill_20260224T005304Z.json`
- `docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_source_record_upgrade_apply_20260224T005304Z.json`
- `docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_seed_status_20260224T005304Z.json`
- `docs/etl/sprints/AI-OPS-161/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T005304Z.json`
- `docs/etl/sprints/AI-OPS-161/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T005304Z.csv`
- `docs/etl/sprints/AI-OPS-161/evidence/sqlite_fk_check_20260224T005304Z.json`
- `docs/etl/sprints/AI-OPS-161/evidence/just_parl_test_liberty_restrictions_20260224T005304Z.txt`

## Siguiente paso
- Extender la misma estrategia de procedencia no-seed a evidencias de Congreso/Senado y a la capa `acto sancionador -> cobro -> recurso/resultado` por expediente.
