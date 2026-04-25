# AI-OPS-264 - Cierre de diversidad VOX en muestra dedupe (`programas_partidos`)

## Objetivo
Cerrar la cola abierta de diversidad en la muestra de precisión (`unique_by_party` de VOX con target `>=10`) sin degradar el hot path de ingest/declarado.

## Enfoque aplicado
- Se descartó el enfoque de diversificación en ingest por impacto no deseado en señal declarada.
- Se movió la mejora al exportador de muestra de precisión:
  - `scripts/export_programas_support_precision_sample.py` ahora soporta *windowing* determinista de `excerpt` por `evidence_id`:
    - `--excerpt-window-words`
    - `--excerpt-window-stride`
    - `--excerpt-window-min-words`
  - El windowing produce una única ventana por evidencia (determinista), aumentando diversidad de snippet para auditoría sin alterar `topic_evidence` ni `declared_positions`.
  - El resumen JSON ahora reporta:
    - `excerpt_window_words`
    - `excerpt_window_stride`
    - `excerpt_window_min_words`
    - `windowed_rows_total`
- Wiring en `justfile`:
  - `PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_WORDS`
  - `PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_STRIDE`
  - `PROGRAMAS_PRECISION_SAMPLE_EXCERPT_WINDOW_MIN_WORDS`
  - aplicado en `parl-export-programas-support-precision-sample` y `parl-check-programas-support-precision-sample`.

## Validación
- Tests:
  - `python3 -m unittest tests/test_export_programas_support_precision_sample.py tests/test_report_programas_support_precision_audit.py`
  - `python3 -m unittest tests/test_parl_programas_partidos.py`
- Baseline sin windowing (mismo DB/parties/dedupe):
  - `unique_by_party.VOX=5` (cap operativo en sample dedupe).
- Con windowing (`--excerpt-window-words 40 --excerpt-window-stride 12 --excerpt-window-min-words 12`):
  - `unique_by_party={BNG:10, VOX:10, FORO Asturias:10, PP:10}`
  - `parties_below_min_unique=[]`
  - `status=ok`, `strict rc=0`.
- Validación por lane `just` con overrides de env:
  - `just parl-check-programas-support-precision-sample` en verde con los mismos parámetros.

## Evidencia
- `docs/etl/sprints/AI-OPS-264/evidence/programas_support_precision_sample_restore_baseline_v2_summary_latest.json`
- `docs/etl/sprints/AI-OPS-264/evidence/programas_support_precision_sample_window40_stride12_summary_latest.json`
- `docs/etl/sprints/AI-OPS-264/evidence/programas_support_precision_sample_window40_stride12_just_summary_latest.json`
- `docs/etl/sprints/AI-OPS-264/evidence/just_parl_check_programas_support_precision_sample_window40_stride12_latest.txt`
- `docs/etl/sprints/AI-OPS-264/evidence/unittest_programas_precision_sample_windowing_20260228.txt`
- `docs/etl/sprints/AI-OPS-264/evidence/unittest_programas_precision_windowing_and_pipeline_20260228.txt`
- `docs/etl/sprints/AI-OPS-264/evidence/unittest_parl_programas_partidos_post_restore_branch_20260228.txt`
- `docs/etl/sprints/AI-OPS-264/evidence/tracker_status_pre_tracker_edit_ai_ops_264_latest.log`
- `docs/etl/sprints/AI-OPS-264/evidence/tracker_status_post_ai_ops_264_latest.log`
- `docs/etl/sprints/AI-OPS-264/exports/programas_support_precision_sample_window40_stride12_latest.csv`
- `docs/etl/sprints/AI-OPS-264/exports/programas_support_precision_sample_window40_stride12_just_latest.csv`
