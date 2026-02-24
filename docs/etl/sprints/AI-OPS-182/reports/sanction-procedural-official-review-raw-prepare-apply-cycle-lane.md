# AI-OPS-182 — Unified raw `->` prepare/apply cycle lane for official procedural metrics

## Objetivo
Cerrar el loop operativo de `Scenario A` en un solo comando para la lane oficial procedimental:
`raw source metrics -> KPI apply rows -> prepare -> readiness -> apply -> status`.

## Entregado
- Script nuevo: `scripts/run_sanction_procedural_official_review_raw_prepare_apply_cycle.py`
  - Orquesta en una sola corrida:
    1. transformación raw con `export_sanction_procedural_official_review_apply_from_raw_metrics.py`,
    2. `prepare` incremental,
    3. `readiness -> apply -> status` vía `run_cycle(...)`.
  - Soporta gating estricto por etapa:
    - `--strict-raw` bloquea temprano con `skip_reason=raw_not_ok` (exit `4`).
    - `--strict-prepare` bloquea cuando `prepare != ok` (exit `4`).
    - `--strict-readiness` mantiene bloqueo de la etapa apply.
  - Emite artefactos separados y payload consolidado (`raw`, `prepare`, `cycle`) para auditoría.
- `justfile`
  - nuevas vars `SANCTION_PROCEDURAL_OFFICIAL_REVIEW_RAW_CYCLE_*`
  - nuevos lanes:
    - `parl-run-sanction-procedural-official-review-raw-prepare-apply-cycle`
    - `parl-run-sanction-procedural-official-review-raw-prepare-apply-cycle-dry-run`
- Tests
  - nuevo: `tests/test_run_sanction_procedural_official_review_raw_prepare_apply_cycle.py`
    - fail-path con `strict-raw` (`raw_not_ok`)
    - pass-path dry-run end-to-end.
  - `parl-test-sanction-data-catalog` sube a `Ran 28`.

## Resultado de corrida (20260224T105455Z)
- Pass-path (`4` fuentes raw, dry-run):
  - `raw.status=ok` (`rows_seen=4`, `rows_emitted=4`, `kpi_rows_emitted=12`, `rows_rejected=0`)
  - `prepare.status=ok`
  - `readiness.status=ok`
  - apply dry-run: `rows_ready=12`, `source_record_pk_would_create=12`
- Fail-path (`strict-raw`):
  - input raw inválido (`evidence_date` mal formato, cita corta, `presentados=0`)
  - `exit=4`
  - `raw.status=degraded` (`rows_seen=1`, `rows_emitted=0`, `rows_rejected=1`)
  - ciclo bloqueado sin avanzar a prepare/apply: `skip_reason=raw_not_ok`
- Estado lane oficial en staging:
  - `status=degraded`
  - `official_review_procedural_metrics_total=0`
  - `official_review_source_metric_coverage_pct=0.0`
  - (sin carga real en este slice; solo hardening operativo).

## Conclusión operativa
La lane oficial queda operable de extremo a extremo desde captura raw, con gates explícitos por etapa y salida auditable. El siguiente paso de impacto en cobertura sigue siendo aplicar datos oficiales reales.

## Evidencia
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_prepare_apply_cycle_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_prepare_apply_cycle_bad_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_cycle_raw_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_raw_cycle_raw_bad_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_apply_prepare_from_raw_cycle_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_apply_readiness_from_raw_cycle_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/sanction_procedural_official_review_status_20260224T105455Z.json`
- `docs/etl/sprints/AI-OPS-182/evidence/just_parl_run_sanction_procedural_official_review_raw_prepare_apply_cycle_dry_run_20260224T105455Z.txt`
- `docs/etl/sprints/AI-OPS-182/evidence/just_parl_run_sanction_procedural_official_review_raw_prepare_apply_cycle_bad_20260224T105455Z.txt`
- `docs/etl/sprints/AI-OPS-182/evidence/just_parl_run_sanction_procedural_official_review_raw_prepare_apply_cycle_bad_exit_20260224T105455Z.txt`
- `docs/etl/sprints/AI-OPS-182/evidence/just_parl_test_sanction_data_catalog_20260224T105455Z.txt`
