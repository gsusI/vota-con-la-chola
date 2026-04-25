# AI-OPS-370 — Conversión dirigida `status=403` (`packet32`) + postproceso

## Objetivo
Ejecutar la lane `860` con un replay único y acotado sobre `status=403` en `linked_to_votes`, y cerrar con delta real o `NO_DELTA_WITH_EVIDENCE`.

## Comandos ejecutados
```bash
python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 403 \
  --limit 32 --format csv \
  --out docs/etl/sprints/AI-OPS-370/exports/senado_status403_linked_packet32_20260301T105944Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-370/exports/senado_status403_linked_packet32_20260301T105944Z.csv \
  --retry-http-statuses 403 \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas --limit 0

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas --only-missing \
  --out docs/etl/sprints/AI-OPS-370/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T105944Z.json
```

## Resultado
- Packet export `status=403`: `32` URLs.
- Retry `status=403`: `candidate_urls=32`, `fetched_ok=10`, `archive_hits=10`, `failures=22`.
- Variantes directas: `direct_variant_attempted_urls=22`, `direct_variant_fetched_ok=0`.
- Delta KPI (baseline AI-OPS-369 -> post AI-OPS-370):
  - `downloaded_doc_links`: `5223 -> 5233` (`+10`)
  - `missing_doc_links_actionable`: `4139 -> 4129` (`-10`)
  - `missing_urls`: `363 -> 353` (`-10`)
  - `blocked_403_urls`: `32 -> 22` (`-10`)
  - `status=404` residual: `331 -> 331` (`0`)
- Postproceso semántico:
  - `backfill_initiative_doc_excerpts`: `seen=0`, `updated=0`.
  - `backfill_initiative_doc_extractions --only-missing`: `seen=10`, `upserted=10`, `needs_review=0`.
  - Calidad resultante: `downloaded_doc_links_missing_excerpt=0`, `downloaded_doc_links_missing_extraction=0`.

## Conclusión operativa
La lane `860` queda cumplida con holgura (DoD `+5/-5` superado por `+10/-10`). Tras esta corrida, el residual `linked_to_votes` queda concentrado en `status=404` (`331`) y `status=403` (`22`), con cobertura `linked_to_votes_with_downloaded_docs=751/751` ya cerrada.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-370/evidence/senado_status403_retry_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/senado_status403_conversion_delta_ai_ops_370_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/quality_initiatives_before_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/quality_initiatives_after_postprocess_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/senado_waf_block_profile_before_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/senado_waf_block_profile_after_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/initiative_doc_excerpts_backfill_senado_20260301T105944Z.json`
- `docs/etl/sprints/AI-OPS-370/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T105944Z.json`
