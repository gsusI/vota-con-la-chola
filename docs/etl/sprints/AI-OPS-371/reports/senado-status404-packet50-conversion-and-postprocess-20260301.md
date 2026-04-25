# AI-OPS-371 — Conversión dirigida `status=404` (`packet50`) + postproceso

## Objetivo
Ejecutar la lane `861` sobre el residual dominante `status=404` en `linked_to_votes`, con un replay acotado y cierre anti-loop con evidencia.

## Comandos ejecutados
```bash
python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --doc-source-id parl_initiative_docs \
  --only-linked-to-votes \
  --out docs/etl/sprints/AI-OPS-371/evidence/senado_waf_block_profile_before_20260301T111618Z.json

python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --json-out docs/etl/sprints/AI-OPS-371/evidence/quality_initiatives_before_20260301T111618Z.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 404 \
  --limit 50 --format csv \
  --out docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet50_20260301T111618Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet50_20260301T111618Z.csv \
  --retry-http-statuses 404 \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 404 \
  --limit 500 --format csv \
  --out docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet500_20260301T111618Z.csv

# Construcción de packet50 efectivo desde pool ya filtrado
head -n 1 docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet500_20260301T111618Z.csv > \
  docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet50_effective_20260301T111618Z.csv
tail -n +2 docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet500_20260301T111618Z.csv | head -n 50 >> \
  docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet50_effective_20260301T111618Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-371/exports/senado_status404_linked_packet50_effective_20260301T111618Z.csv \
  --retry-http-statuses 404 \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas --limit 0

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas --only-missing \
  --out docs/etl/sprints/AI-OPS-371/evidence/initiative_doc_extractions_backfill_senado_only_missing_final_20260301T111618Z.json
```

## Resultado
- Primer export `limit=50` quedó subllenado por interacción `limit + dedupe redundante`: `rows=9` (`excluded_redundant_senado_global=41`).
- Retry sobre packet subllenado (`9` URLs): `fetched_ok=2`, `archive_hits=2`, `failures=7`.
- Se corrige la selección construyendo packet efectivo de `50` URLs desde pool filtrado (`limit=500`, `rows=322`), y se ejecuta segunda pasada:
  - `candidate_urls=50`, `fetched_ok=18`, `archive_hits=19`, `failures=30`.
- Delta KPI (baseline AI-OPS-370 -> cierre AI-OPS-371):
  - `downloaded_doc_links`: `5233 -> 5253` (`+20`)
  - `missing_doc_links_actionable`: `4129 -> 4109` (`-20`)
  - `missing_urls`: `353 -> 333` (`-20`)
  - `status=404` en perfil WAF: `331 -> 272` (`-59`)
  - `blocked_403_urls`: `22 -> 61` (`+39`) por reclasificación tras probes/variantes
- Postproceso estructural:
  - `backfill_initiative_doc_excerpts`: `seen=0`, `updated=0`.
  - `backfill_initiative_doc_extractions --only-missing`: total slice `seen/upserted/needs_review=20/20/0`.
  - Calidad resultante: `downloaded_doc_links_missing_excerpt=0`, `downloaded_doc_links_missing_extraction=0`.

## Conclusión operativa
La lane `861` queda cumplida con margen sobre DoD (`+20/-20`). El residual dominante sigue en `status=404` (`272`) pero con reducción material y evidencia de reclasificación estructural hacia `403` en cohortes `detalleiniciativa` (especialmente `leg10 tipo610`), lo que abre siguiente lane dirigida a `status=403` residual.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-371/evidence/senado_status404_retry_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/senado_status404_retry_packet50_effective_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/senado_status404_conversion_delta_ai_ops_371_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/quality_initiatives_before_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/quality_initiatives_after_postprocess_final_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/senado_waf_block_profile_before_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/senado_waf_block_profile_after_final_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/initiative_doc_excerpts_backfill_senado_final_20260301T111618Z.json`
- `docs/etl/sprints/AI-OPS-371/evidence/initiative_doc_extractions_backfill_senado_only_missing_final_20260301T111618Z.json`
