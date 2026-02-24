# AI-OPS-183 — Raw template export lane for official procedural review capture

## Objetivo
Reducir fricción de captura en `Scenario A` con un template raw oficial (1 fila por fuente), compatible con el ciclo unificado `raw -> prepare -> apply`.

## Entregado
- Script nuevo: `scripts/export_sanction_procedural_official_review_raw_template.py`
  - Exporta template raw por fuente oficial (`TEAR`, `TEAC`, `contencioso`, `defensor`).
  - Incluye campos requeridos por el transformador raw:
    - `recurso_presentado_count`, `recurso_estimado_count`, `anulaciones_formales_count`, `resolution_delay_p90_days`
    - `evidence_date`, `evidence_quote`
  - Prefills de contexto:
    - `source_url`, `source_label`, `organismo`,
    - `source_id`, `source_record_id`,
    - `expected_metrics`, `procedural_kpis_expected`,
    - `procedural_kpis_covered_total`, `procedural_metric_rows_total`.
  - Soporta `--only-missing` para no emitir fuentes ya cubiertas en el periodo.
- `justfile`
  - lane nuevo: `parl-export-sanction-procedural-official-review-raw-template`
  - nuevas variables `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_TEMPLATE_*`.
- Tests
  - nuevo: `tests/test_export_sanction_procedural_official_review_raw_template.py`
  - `parl-test-sanction-data-catalog` sube a `Ran 30`.

## Resultado de corrida (20260224T105932Z)
- Export raw template (`--only-missing`):
  - `status=ok`
  - `sources_expected_total=4`
  - `sources_seeded_total=4`
  - `rows_emitted_total=4`
  - `rows_skipped_fully_covered_total=0`
- Verificación de gate estricto sobre template vacío (esperado):
  - `parl-run-...raw-prepare-apply-cycle-dry-run` con template recién exportado
  - `exit=4`
  - `raw.status=degraded` (`rows_emitted=0`, `rows_rejected=4`)
  - `cycle.apply.skip_reason=raw_not_ok`
  - confirma que el template no se puede aplicar sin completar valores/evidencia.
- Estado lane oficial en staging:
  - `status=degraded`
  - `official_review_procedural_metrics_total=0`
  - (sin carga oficial real en este slice).

## Conclusión operativa
El flujo oficial ya tiene un punto de entrada reproducible para captura raw por fuente y periodo. El siguiente paso de impacto es completar este template con datos oficiales y ejecutar el ciclo en modo no dry-run.

## Evidencia
- `docs/etl/sprints/AI-OPS-183/evidence/sanction_procedural_official_review_raw_template_20260224T105932Z.json`
- `docs/etl/sprints/AI-OPS-183/exports/sanction_procedural_official_review_raw_template_20260224T105932Z.csv`
- `docs/etl/sprints/AI-OPS-183/evidence/sanction_procedural_official_review_raw_cycle_raw_template_20260224T105932Z.json`
- `docs/etl/sprints/AI-OPS-183/evidence/sanction_procedural_official_review_raw_prepare_apply_cycle_template_20260224T105932Z.json`
- `docs/etl/sprints/AI-OPS-183/evidence/sanction_procedural_official_review_status_20260224T105932Z.json`
- `docs/etl/sprints/AI-OPS-183/evidence/just_parl_export_sanction_procedural_official_review_raw_template_20260224T105932Z.txt`
- `docs/etl/sprints/AI-OPS-183/evidence/just_parl_run_sanction_procedural_official_review_raw_prepare_apply_cycle_dry_run_template_exit_20260224T105932Z.txt`
- `docs/etl/sprints/AI-OPS-183/evidence/just_parl_test_sanction_data_catalog_20260224T105932Z.txt`
