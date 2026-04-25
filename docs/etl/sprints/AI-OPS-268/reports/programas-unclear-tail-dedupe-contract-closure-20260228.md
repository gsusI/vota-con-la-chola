# AI-OPS-268 — Contrato de dedupe para tail `unclear` (BNG/VOX)

## Objetivo
Cerrar la fila 771 del tracker estableciendo un contrato reproducible para dedupe de cola `unclear` en `programas_partidos` usando clave `source_url + excerpt_norm`, con KPI explícito de únicos vs duplicados.

## Implementación
- Nuevo script: `scripts/report_programas_unclear_tail_dedupe.py`
  - Exporta reporte JSON con KPIs:
    - `raw_unclear_rows_total`
    - `unclear_unique_excerpt_rows_total`
    - `unclear_duplicate_rows_total`
    - `duplicate_share`
  - Exporta cola deduped CSV (1 fila por `source_url+excerpt_norm`) y perfil por fuente.
  - Modo `--strict` con fail reasons contractuales.
- Nuevo test: `tests/test_report_programas_unclear_tail_dedupe.py`
  - cobertura de dedupe + perfil
  - cobertura de fail-path estricto por umbral de duplicados
- `justfile` actualizado:
  - `parl-report-programas-unclear-tail-dedupe`
  - `parl-check-programas-unclear-tail-dedupe`
  - vars `PROGRAMAS_UNCLEAR_TAIL_*`

## Resultado en staging (DB real)
Corrida strict (`max_duplicate_share=1.0`) -> `status=ok`:
- `raw_unclear_rows_total=31`
- `unclear_unique_excerpt_rows_total=14`
- `unclear_duplicate_rows_total=17`
- `duplicate_share=0.5483870968`
- reducción efectiva por dedupe: `54.84%` (31 -> 14)

Perfil por fuente (top duplicados):
- `VOX web 2025`: `15` rows / `5` únicos / `10` duplicados
- `BNG europeas 2024`: `14` rows / `7` únicos / `7` duplicados

Fail-path contractual (`max_duplicate_share=0.5`, strict) correctamente detectado:
- `status=degraded`
- `strict_fail_reasons=[duplicate_share_above_threshold]`
- `rc=4`

## Integridad
- Tracker gate post-slice: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-268/evidence/programas_unclear_tail_dedupe_report_latest.json`
- `docs/etl/sprints/AI-OPS-268/evidence/programas_unclear_tail_dedupe_delta_latest.json`
- `docs/etl/sprints/AI-OPS-268/evidence/programas_unclear_tail_dedupe_report_fail_latest.json`
- `docs/etl/sprints/AI-OPS-268/evidence/programas_unclear_tail_dedupe_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-268/exports/programas_unclear_tail_deduped_queue_latest.csv`
- `docs/etl/sprints/AI-OPS-268/exports/programas_unclear_tail_duplicate_profile_latest.csv`
- `docs/etl/sprints/AI-OPS-268/evidence/tracker_status_post_latest.log`
- `docs/etl/sprints/AI-OPS-268/evidence/unittest_report_programas_unclear_tail_dedupe_latest.txt`
