# AI-OPS-369 — Conversión dirigida `status=0/200` + postproceso semántico

## Objetivo
Ejecutar la lane `859` (residual no bloqueado) con replay acotado en `linked_to_votes` para convertir `status=0/200`, y cerrar limpieza/estructuración sobre los documentos recién descargados.

## Comandos ejecutados
```bash
python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 0 \
  --limit 25 --format csv \
  --out docs/etl/sprints/AI-OPS-369/exports/senado_status0_linked_packet25_20260301T104519Z.csv

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing --only-linked-to-votes --only-status 200 \
  --limit 25 --format csv \
  --out docs/etl/sprints/AI-OPS-369/exports/senado_status200_linked_packet25_20260301T104519Z.csv

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-369/exports/senado_status0_linked_packet25_20260301T104519Z.csv \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --doc-urls-file docs/etl/sprints/AI-OPS-369/exports/senado_status200_linked_packet25_20260301T104519Z.csv \
  --archive-fallback --archive-fallback-http-statuses 403,404 \
  --refetch-existing --timeout 15 --snapshot-date 2026-03-01

python3 scripts/backfill_initiative_doc_excerpts.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas --limit 0

python3 scripts/backfill_initiative_doc_extractions.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas --only-missing \
  --out docs/etl/sprints/AI-OPS-369/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T104519Z.json
```

## Resultado
- Packet export:
  - `status=0`: `18` URLs
  - `status=200`: `5` URLs
- Retry `status=0`: `candidate_urls=18`, `fetched_ok=16`, `archive_hits=16`, `failures=2`.
- Retry `status=200`: `candidate_urls=5`, `fetched_ok=5`, `archive_hits=5`, `failures=0`.
- Delta KPI (baseline AI-OPS-367 -> post AI-OPS-369):
  - `downloaded_doc_links`: `5202 -> 5223` (`+21`)
  - `missing_doc_links_actionable`: `4160 -> 4139` (`-21`)
  - `missing_urls`: `384 -> 363` (`-21`)
  - `blocked_403_urls`: `32 -> 32` (`0`)
  - `unknown_status_urls`: `18 -> 0` (`-18`)
  - `status=200` residual: `5 -> 0` (`-5`)
- Postproceso semántico sobre nuevos docs:
  - `backfill_initiative_doc_excerpts`: `seen=351`, `updated=351`.
  - `backfill_initiative_doc_extractions --only-missing`: `seen=21`, `upserted=21`, `needs_review=0`.
  - Calidad resultante: `downloaded_doc_links_missing_excerpt=0`, `downloaded_doc_links_missing_extraction=0`, `excerpt_coverage_pct=1.0`, `extraction_coverage_pct=1.0`.

## Conclusión operativa
La lane `859` queda cumplida con holgura (DoD `+3/-3` superado por `+21/-21`) y además deja cerrada la limpieza/estructuración de los documentos recién convertidos. El residual queda concentrado en `status=404/403`, con `status=0` y `status=200` drenados en `linked_to_votes`.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-369/evidence/senado_status0_retry_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/senado_status200_retry_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/senado_status0_200_conversion_delta_ai_ops_369_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/quality_initiatives_after_postprocess_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/senado_waf_block_profile_before_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/senado_waf_block_profile_after_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/initiative_doc_excerpts_backfill_senado_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/initiative_doc_extractions_backfill_senado_only_missing_20260301T104519Z.json`
- `docs/etl/sprints/AI-OPS-369/evidence/e2e_tracker_status_with_tracker_20260301T105651Z.log`
