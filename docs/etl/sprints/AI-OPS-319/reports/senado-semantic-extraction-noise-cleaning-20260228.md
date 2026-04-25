# AI-OPS-319 - Curación semántica de extracción en Senado (ruido HTML/JS)

## Objetivo
Cerrar un gap de limpieza/estructura en `parl_initiative_doc_extractions` para Senado: sujetos extraídos con ruido de navegación/JS (`Enmiendas | Senado de España !function(...)`) que degradaban la legibilidad aunque la cobertura de extracción estaba al 100%.

## Palanca aplicada (controlable, sin red)
1. Hardening en extractor heurístico:
   - `scripts/backfill_initiative_doc_extractions.py`
   - nueva detección `_looks_like_noisy_subject(...)` para descartar candidatos con firmas de ruido (`!function(`, `function(`, fragmentos branding + `|`, etc.).
   - fallback a título fuerte cuando la ventana keyword es corta o ruidosa.
2. Reproceso completo de extracciones para Senado:
   - `python3 scripts/backfill_initiative_doc_extractions.py --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --out docs/etl/sprints/AI-OPS-319/evidence/initiative_doc_extractions_semantic_cleaning_senado_20260228T225234Z.json`

## Resultado
- Cobertura estructural: estable (sin regresión)
  - `downloaded_doc_links`: `4347 -> 4347` (`delta=0`)
  - `downloaded_missing_extraction`: `0 -> 0`
  - `extraction_needs_review`: `0 -> 0`
- Limpieza semántica en Senado: mejora material
  - `noise_rows_total`: `18 -> 0` (`-18`)
  - `row_changes_subject_changed`: `18`
  - ejemplos ruidosos reemplazados por sujetos útiles (título fuerte / sujeto legislativo).

## Validaciones
- Test focal extractor:
  - `python3 -m unittest -v tests.test_backfill_initiative_doc_extractions`
  - `Ran 8 tests`, `OK`.
- Gate tracker:
  - `DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-status`
  - `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-319/evidence/senado_extraction_noise_pre_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/initiative_doc_extractions_semantic_cleaning_senado_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/senado_extraction_noise_post_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/senado_extraction_noise_delta_ai_ops_319_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/quality_initiatives_after_semantic_cleaning_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/initiative_doc_semantic_cleaning_status_delta_ai_ops_319_20260228T225234Z.json`
- `docs/etl/sprints/AI-OPS-319/evidence/unittest_backfill_initiative_doc_extractions_20260228T225234Z.txt`
- `docs/etl/sprints/AI-OPS-319/evidence/tracker_status_20260228T225234Z.log`

## Estado de lane
- `820/822`: sigue `PARTIAL` por bloqueo WAF en cola accionable de descarga Senado.
- Slice AI-OPS-319 cierra un avance visible y bajo control del repo en `processing/cleaning` (higiene semántica de extracción).
