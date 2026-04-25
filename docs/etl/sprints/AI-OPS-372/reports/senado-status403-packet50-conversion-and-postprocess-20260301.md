# AI-OPS-372 — Conversión dirigida `status=403` (`packet50`) + postproceso

## Objetivo
Ejecutar la lane `862` sobre el residual reclasificado `status=403` en `linked_to_votes`, con replay acotado y cierre anti-loop con evidencia.

## Comandos ejecutados
```bash
python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-linked-to-votes \
  --out docs/etl/sprints/AI-OPS-372/evidence/senado_waf_block_profile_before_20260301T114610Z.json

python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-372/evidence/quality_initiatives_before_20260301T114610Z.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 403 \
  --limit 50 --format csv \
  --out docs/etl/sprints/AI-OPS-372/exports/senado_status403_linked_packet50_20260301T114610Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-372/exports/senado_status403_linked_packet50_20260301T114610Z.csv \
  --retry-http-statuses 403 \
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
  --out docs/etl/sprints/AI-OPS-372/evidence/senado_waf_block_profile_after_20260301T114610Z.json

python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-372/evidence/quality_initiatives_after_postprocess_20260301T114610Z.json
```

## Resultado
- Packet objetivo `status=403`: `rows=50`.
- Retry sobre packet: `candidate_urls=50`, `fetched_ok=34`, `failures=16`.
- Conversión dominante vía variantes directas (`direct_variant_fetched_ok=34`), con fallback archivo residual (`archive_hits=1`, `archive_fetched_ok=0`).
- Delta KPI (baseline AI-OPS-371 -> cierre AI-OPS-372):
  - `downloaded_doc_links`: `5253 -> 5287` (`+34`)
  - `missing_doc_links_actionable`: `4109 -> 4075` (`-34`)
  - `missing_urls`: `333 -> 299` (`-34`)
  - `blocked_403_urls`: `61 -> 27` (`-34`)
  - `status=404`: `272 -> 272` (`0`)
- Postproceso estructural:
  - `backfill_initiative_doc_excerpts`: `seen=27`, `updated=27`.
  - `backfill_initiative_doc_extractions --only-missing`: `seen/upserted/needs_review=34/34/0`.
  - Calidad resultante: `downloaded_doc_links_missing_excerpt=0`, `downloaded_doc_links_missing_extraction=0`.

## Conclusión operativa
La lane `862` queda cumplida con margen claro sobre el DoD (`+34/-34`). El residual `status=403` se reduce de forma material y la cola accionable `linked_to_votes` queda concentrada de nuevo en `status=404` (`272` URLs), que pasa a ser la siguiente lane prioritaria.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-372/evidence/senado_status403_retry_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/senado_status403_conversion_delta_ai_ops_372_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/quality_initiatives_before_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/quality_initiatives_after_postprocess_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/senado_waf_block_profile_before_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/senado_waf_block_profile_after_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/initiative_doc_excerpts_backfill_senado_20260301T114610Z.json`
- `docs/etl/sprints/AI-OPS-372/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T114610Z.json`
