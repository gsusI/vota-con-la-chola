# AI-OPS-269 — Cierre de ratio documental (`support` vs `unclear_unique`) en BNG/VOX

## Objetivo
Cerrar la fila 770 (`Curación documental residual de manifiestos (BNG/VOX)`) con un criterio reproducible que elimine el sesgo por duplicados multi-topic y mida la relación documental sobre cola dedupe.

## Implementación
- Nuevo script: `scripts/report_programas_support_unclear_unique_ratio.py`
  - Cruza por `party_name + source_url`:
    - `support_rows`
    - `unclear_rows`
    - `unclear_unique_excerpt_rows`
    - `support_to_unclear_unique_ratio`
  - Contrato estricto por umbral `--min-support-unclear-unique-ratio`.
- Nuevo test: `tests/test_report_programas_support_unclear_unique_ratio.py`.
- Nuevas recetas `just`:
  - `parl-report-programas-support-unclear-unique-ratio`
  - `parl-check-programas-support-unclear-unique-ratio`

## Resultado en staging
Corrida strict (`min_ratio=1.0`) -> `status=ok`:
- `BNG xerais 2023`: `10 / 2` => `5.00`
- `BNG europeas 2024`: `10 / 7` => `1.428571`
- `VOX web 2025`: `18 / 5` => `3.60`

Con este contrato, los tres documentos objetivo quedan por encima del umbral operativo (`>=1.0`).

Fail-path contractual validado (`min_ratio=2.0`):
- `status=degraded`, `strict_fail_reasons=[ratio_below_threshold]`, `rc=4`.

## Integridad
- Tracker gate post-slice: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-269/evidence/programas_support_unclear_unique_ratio_latest.json`
- `docs/etl/sprints/AI-OPS-269/exports/programas_support_unclear_unique_ratio_latest.csv`
- `docs/etl/sprints/AI-OPS-269/evidence/programas_support_unclear_unique_ratio_fail_latest.json`
- `docs/etl/sprints/AI-OPS-269/evidence/programas_support_unclear_unique_ratio_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-269/evidence/tracker_status_post_latest.log`
- `docs/etl/sprints/AI-OPS-269/evidence/unittest_report_programas_support_unclear_unique_ratio_latest.txt`
