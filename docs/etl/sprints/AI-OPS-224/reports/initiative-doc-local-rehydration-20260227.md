# AI-OPS-224 - Rehidratación local de documentos de iniciativas

Fecha (UTC): 2026-02-27  
DB: `etl/data/staging/politicos-es.db`

## Objetivo

Recuperar cobertura de limpieza/estructura sobre `parl_initiative_docs` sin depender de red:
- `document_fetches` para docs ya descargados,
- `text_excerpt` en `text_documents`,
- extracción semántica en `parl_initiative_doc_extractions`.

## Ejecución

```bash
python3 scripts/backfill_initiative_doc_fetch_status.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --doc-source-id parl_initiative_docs \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas
```

## Resultado (pre -> post)

- `doc_links_missing_fetch_status`: `205 -> 0`
- `downloaded_doc_links_missing_excerpt`: `2383 -> 0`
- `downloaded_doc_links_missing_extraction`: `4041 -> 0`
- `fetch_status_coverage_pct`: `0.9765 -> 1.0`
- `excerpt_coverage_pct`: `0.4103 -> 1.0`
- `extraction_coverage_pct`: `0.0 -> 1.0`
- `extraction_review_closed_pct`: `0.0 -> 0.99975`

Backfill semántico:
- `seen=3958`, `upserted=3958`, `needs_review=1`

Gate iniciativas (enforce):
- Sigue `failed` por un único residual:
  - `actionable_doc_links_closed_pct=0.4724 < 1.0`
- Ya no falla por extracción (`extraction_coverage_pct=1.0`, `extraction_review_closed_pct=0.99975`).

Cola accionable exportada para siguiente pasada:
- `export_missing_initiative_doc_urls.py --initiative-source-ids senado_iniciativas --only-actionable-missing`
- Resultado: `rows=4599` (`excluded_redundant_senado_global=77`)

## Estado de cierre

La fila `Textos de iniciativas (qué se votó)` permanece `PARTIAL`:
- limpieza/estructuración local recuperadas,
- cierre final bloqueado por cola accionable de URLs faltantes en Senado.

## Evidencia

- `docs/etl/sprints/AI-OPS-224/evidence/initiative_doc_status_pre_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/initiative_doc_status_post_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/quality_initiatives_pre_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/quality_initiatives_post_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/quality_initiatives_delta_latest.csv`
- `docs/etl/sprints/AI-OPS-224/evidence/quality_initiatives_post_backfill_enforce_20260227T0136Z.json`
- `docs/etl/sprints/AI-OPS-224/evidence/quality_initiatives_post_backfill_enforce_rc_20260227T0136Z.txt`
- `docs/etl/sprints/AI-OPS-224/evidence/initdoc_fetch_status_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/initdoc_excerpts_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/initdoc_extractions_backfill_latest.json`
- `docs/etl/sprints/AI-OPS-224/evidence/tracker_status_latest.log`
- `docs/etl/sprints/AI-OPS-224/evidence/senado_missing_actionable_export_latest.txt`
- `docs/etl/sprints/AI-OPS-224/exports/senado_missing_actionable_latest.csv`
