# AI-OPS-374 — Conversión iterativa `status=404` (`packet50` efectivo) + postproceso

## Objetivo
Ejecutar la lane `864` con una nueva pasada `status=404` en `linked_to_votes`, manteniendo cierre anti-loop y evidencia reproducible.

## Comandos ejecutados
```bash
python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-linked-to-votes \
  --out docs/etl/sprints/AI-OPS-374/evidence/senado_waf_block_profile_before_20260301T133600Z.json

python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-374/evidence/quality_initiatives_before_20260301T133600Z.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 404 \
  --limit 500 --format csv \
  --out docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet500_20260301T133600Z.csv

# Construcción de packet50 efectivo
head -n 1 docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet500_20260301T133600Z.csv > \
  docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet50_effective_20260301T133600Z.csv
tail -n +2 docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet500_20260301T133600Z.csv | head -n 50 >> \
  docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet50_effective_20260301T133600Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-374/exports/senado_status404_linked_packet50_effective_20260301T133600Z.csv \
  --retry-http-statuses 404 \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --source-id parl_initiative_docs \
  --initiative-source-id senado_iniciativas

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --doc-source-id parl_initiative_docs \
  --initiative-source-ids senado_iniciativas --only-missing

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-linked-to-votes \
  --out docs/etl/sprints/AI-OPS-374/evidence/senado_waf_block_profile_after_20260301T133600Z.json

python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-374/evidence/quality_initiatives_after_postprocess_20260301T133600Z.json
```

## Resultado
- Packet efectivo construido desde pool `status=404` (`rows=222` -> `packet50`).
- Retry limpio sobre packet: `candidate_urls=50`, `fetched_ok=50`, `failures=0`.
- Conversión dominada por variantes directas (`direct_variant_fetched_ok=50`), sin dependencia de archive fallback (`archive_hits=0`).
- Delta KPI (baseline AI-OPS-373 -> cierre AI-OPS-374):
  - `downloaded_doc_links`: `5337 -> 5387` (`+50`)
  - `missing_doc_links_actionable`: `4025 -> 3975` (`-50`)
  - `missing_urls`: `249 -> 199` (`-50`)
  - `status=404`: `222 -> 172` (`-50`)
  - `blocked_403_urls`: `27 -> 27` (`0`)
- Postproceso estructural:
  - `backfill_initiative_doc_excerpts`: `seen=0`, `updated=0`.
  - `backfill_initiative_doc_extractions --only-missing`: `seen/upserted/needs_review=50/50/0`.
  - Calidad resultante: `downloaded_doc_links_missing_excerpt=0`, `downloaded_doc_links_missing_extraction=0`.

## Conclusión operativa
La lane `864` queda cumplida con margen alto (`+50/-50`). El bucket `status=404` continúa siendo el principal (`172`) y se mantiene como siguiente lane para una iteración adicional.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-374/evidence/senado_status404_retry_packet50_effective_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/senado_status404_conversion_delta_ai_ops_374_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/quality_initiatives_before_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/quality_initiatives_after_postprocess_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/senado_waf_block_profile_before_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/senado_waf_block_profile_after_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/initiative_doc_excerpts_backfill_senado_20260301T133600Z.json`
- `docs/etl/sprints/AI-OPS-374/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T133600Z.json`
