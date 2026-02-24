# AI-OPS-164 — Responsabilidad por fragmento: evidencia de ejecución sancionadora

Fecha: 2026-02-24 (UTC)

## Objetivo del slice

Extender la cadena de `Responsabilidad por fragmento normativo` hacia señal de ejecución real (expedientes/importes) sin depender de nuevas fuentes externas, usando `sanction_volume_observations` ya cargadas en DB.

## Implementación

- Nuevo backfill reproducible: `scripts/backfill_sanction_norms_execution_evidence.py`.
- Fuente de señal: `sanction_volume_observations` con `norm_id + fragment_id` y señal cuantitativa (`expediente_count/importe_total_eur/recursos`).
- Matching conservador por defecto:
  - `fragment_id` exacto
  - roles `enforce` (configurable con `--roles`)
- Materialización en `legal_fragment_responsibility_evidence` con:
  - `evidence_type='other'` (compatible con constraint actual)
  - `raw_payload.record_kind='sanction_norm_execution_evidence_backfill'`
  - `raw_payload.evidence_type_hint='sanction_volume_observation'`
- Trazabilidad documental:
  - `source_url` único por observación (`...#observation_id=<id>`)
  - autoresolución de `source_record_pk` vía `boe_ref:<BOE-ID>` cuando la observación no trae FK directo.
- Observabilidad extendida en `scripts/report_sanction_norms_seed_status.py`:
  - `responsibility_evidence_items_execution_total`
  - `responsibilities_with_execution_evidence_total`
  - `responsibilities_missing_execution_evidence`
  - `responsibility_evidence_item_execution_share_pct`
  - `responsibility_execution_coverage_pct`
  - check `responsibility_evidence_execution_chain_started`
- `justfile` añade lane:
  - `parl-backfill-sanction-norms-execution-evidence`
- Tests añadidos/actualizados:
  - `tests/test_backfill_sanction_norms_execution_evidence.py`
  - `tests/test_report_sanction_norms_seed_status.py`

## Corrida de cierre (DB real)

Comando ejecutado:

```bash
DB_PATH=etl/data/staging/politicos-es.db \
SANCTION_NORMS_EXECUTION_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-164/evidence/sanction_norms_execution_evidence_backfill_20260224T012849Z.json \
just parl-backfill-sanction-norms-execution-evidence
```

Resultado (`20260224T012849Z`):

- `observations_scanned_total=7`
- `observations_with_responsibility_total=2`
- `observations_without_responsibility_total=5`
- `source_record_pk_resolved_total=2`
- `source_record_pk_missing_total=0`
- `evidence_inserted=2`
- `evidence_updated=0`
- `by_role.enforce=2`
- `by_norm`:
  - `es:boe-a-2015-11724=1`
  - `es:boe-a-2000-15060=1`

## Estado del lane tras backfill

`report_sanction_norms_seed_status.py` (`20260224T012849Z`):

- `status=ok`
- `responsibility_evidence_items_total=39` (antes: 37)
- `responsibility_evidence_items_execution_total=2`
- `responsibilities_with_execution_evidence_total=2/15`
- `responsibility_execution_coverage_pct=0.133333`
- `responsibility_evidence_item_execution_share_pct=0.051282`
- `responsibility_evidence_items_with_non_seed_source_record_total=39/39`
- `responsibility_evidence_execution_chain_started=true`

## Integridad y pruebas

- `PRAGMA foreign_key_check`: `0` violaciones.
- `just parl-test-sanction-norms-seed`: `Ran 21`, `OK`.
- `just parl-test-liberty-restrictions`: `Ran 100`, `OK (skipped=1)`.
- Cola `seed -> non-seed` permanece cerrada:
  - `queue_rows_total=0`.

## Artefactos

- Backfill ejecución:
  - `docs/etl/sprints/AI-OPS-164/evidence/sanction_norms_execution_evidence_backfill_20260224T012849Z.json`
  - `docs/etl/sprints/AI-OPS-164/evidence/just_parl_backfill_sanction_norms_execution_evidence_20260224T012849Z.txt`
- Status lane:
  - `docs/etl/sprints/AI-OPS-164/evidence/sanction_norms_seed_status_20260224T012849Z.json`
  - `docs/etl/sprints/AI-OPS-164/evidence/just_parl_report_sanction_norms_seed_status_20260224T012849Z.txt`
- Queue post-apply:
  - `docs/etl/sprints/AI-OPS-164/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T012849Z.json`
  - `docs/etl/sprints/AI-OPS-164/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T012849Z.csv`
- Integridad/tests:
  - `docs/etl/sprints/AI-OPS-164/evidence/sqlite_fk_check_20260224T012849Z.txt`
  - `docs/etl/sprints/AI-OPS-164/evidence/just_parl_test_sanction_norms_seed_20260224T012849Z.txt`
  - `docs/etl/sprints/AI-OPS-164/evidence/just_parl_test_liberty_restrictions_20260224T012849Z.txt`
