# AI-OPS-242 - Parsing PDF en hot path de `programas_partidos` (2026-02-28)

## Objetivo
Cerrar la lane `Parsing PDF de programas (extractor reutilizable)` y mantener progreso operativo en la lane `anti no_signal`.

## Cambios implementados
- `etl/parlamentario_es/pipeline.py`
  - Nuevo extractor `_extract_program_pdf_text()` para `programas_partidos` con estrategia:
    1. `pypdf`
    2. `PyPDF2`
    3. fallback `pdftotext`
  - Integración en hot path de ingest cuando `ext=pdf` o cabecera `%PDF-`.
- `tests/test_parl_programas_partidos.py`
  - Cobertura de fallback `pdftotext` en extractor PDF.
  - Cobertura de selección de ventana por co-ocurrencia verbo+keyword.
- `tests/test_parl_declared_stance.py`
  - Cobertura del fallback `programa_policy_proposal` y backfill asociado.

## Validación técnica
- Tests: `Ran 12 tests`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-242/evidence/unittest_declared_programas_pdf_lane_20260228.txt`
- Ingest PDF priorizado (6 filas) en staging:
  - `source_records=52`, `text_documents=52`.
  - `programa_pdf` materializado en `6` registros con `text_excerpt` legible (no decode binario bruto).
  - Evidencia: `docs/etl/sprints/AI-OPS-242/evidence/programas_declared_status_pdf_priorizado_20260228.json` + extractos en query reproducible (`pdf_records=6`).

## Estado operativo post-slice (staging)
- Estado final consolidado (manifest deep-link restaurado + cierre de cola):
  - `topic_evidence_total=223`
  - `topic_evidence_by_stance={support:2, unclear:221}`
  - `declared_positions_total=5` (`support=4`, `oppose=1`)
  - `review_pending=0`, `review_ignored=221`, `review_closed_pct=1.0`
  - Gate declarado enforce: `passed=true`
- Tracker gate: `mismatches=0`, `done_zero_real=0`; `programas_partidos max_net=51`.

## Notas operativas
- El manifest unión (`51` filas) requiere `--timeout 60` para evitar timeout de lectura intermitente en `strict-network`.
- La lane anti-`no_signal` mejora parcialmente, pero mantiene gap semántico sobre URLs no programáticas.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-242/exports/programas_manifest_pdf_priorizado_20260228.csv`
- `docs/etl/sprints/AI-OPS-242/evidence/programas_manifest_pdf_priorizado_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-242/exports/programas_manifest_union_multicycle_plus_pdf_20260228.csv`
- `docs/etl/sprints/AI-OPS-242/evidence/programas_manifest_union_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-242/evidence/programas_ingest_union_timeout60_20260228.stdout`
- `docs/etl/sprints/AI-OPS-242/evidence/programas_declared_status_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-242/evidence/quality_declared_programas_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-242/evidence/tracker_status_post_pdf_lane_20260228.log`
