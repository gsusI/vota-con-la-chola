# AI-OPS-262 - Dedupe reproducible de muestra de precision (`programas_partidos`)

## Objetivo
Cerrar la deuda de muestreo duplicado en auditoria de precision: dedupe opcional reproducible y contrato explicito de diversidad minima por partido.

## Cambios implementados
- `scripts/export_programas_support_precision_sample.py`
  - Nuevo `--dedupe-key` con opciones: `none`, `content_sha256`, `excerpt_norm`, `source_url`, `excerpt_norm+source_url`.
  - Dedupe determinista por partido antes de aplicar limites (`per-party-limit` / `limit`).
  - Nuevo `--min-unique-per-party` + `--strict` para validar diversidad minima.
  - Resumen extendido con:
    - `candidate_total_before_dedupe`
    - `dropped_duplicates_total`
    - `dropped_duplicates_by_party`
    - `unique_by_party`
    - `parties_below_min_unique`
    - `checks/status/strict_fail_reasons`
- `justfile`
  - Nuevas vars:
    - `PROGRAMAS_PRECISION_SAMPLE_DEDUPE_KEY`
    - `PROGRAMAS_PRECISION_SAMPLE_MIN_UNIQUE_PER_PARTY`
  - `parl-export-programas-support-precision-sample` ahora soporta dedupe/diversidad.
  - Nuevo lane estricto: `parl-check-programas-support-precision-sample`.
- `tests/test_export_programas_support_precision_sample.py`
  - Cobertura de dedupe `excerpt_norm+source_url`.
  - Cobertura de contrato `min_unique_per_party`.

## Corridas reales (staging)
DB: `etl/data/staging/politicos-es.db`

1) Contrato estricto exigente (`min_unique_per_party=10`) para detectar cola real
- `status=degraded`, `strict_fail_reasons=[min_unique_per_party_not_met]`, `exit=4`
- Resultado: `sample_total=35`, `candidate_total_before_dedupe=110`, `dropped_duplicates_total=61`
- `unique_by_party`: `BNG=10`, `VOX=5`, `FORO Asturias=10`, `PP=10`

2) Contrato estricto operativo (`min_unique_per_party=5`) vía lane `just`
- `status=ok`, `exit=0`
- Mantiene dedupe reproducible (`dropped_duplicates_total=61`) y cobertura de partidos objetivo.

## Evidencia
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_summary_latest.json`
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_min5_summary_latest.json`
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_just_summary_latest.json`
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_min10_fail_summary_latest.json`
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_min10_fail_stdout_latest.txt`
- `docs/etl/sprints/AI-OPS-262/evidence/programas_support_precision_sample_dedup_min10_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-262/evidence/unittest_programas_precision_sample_dedupe_20260228.txt`
- `docs/etl/sprints/AI-OPS-262/exports/programas_support_precision_sample_dedup_just_latest.csv`
