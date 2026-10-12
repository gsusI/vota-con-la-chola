# AI-OPS-306: Rebaseline iniciativas + no_new_lever (Senado)

Fecha UTC: 2026-02-28
Objetivo primario (controlable): rebaselinar cobertura real de textos de iniciativas y ejecutar un único retry acotado en Senado sin abrir loops ciegos.

## Comandos ejecutados

```bash
DB_PATH=etl/data/staging/politicos-es.db SNAPSHOT_DATE=2026-02-28 just parl-quality-report-initiatives
python3 scripts/report_initiative_doc_status.py --db etl/data/staging/politicos-es.db --initiative-source-ids congreso_iniciativas,senado_iniciativas --doc-source-id parl_initiative_docs --missing-sample-limit 10 --out docs/etl/sprints/AI-OPS-306/evidence/initiative_doc_status_post_retry_20260228T205000Z.json
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --retry-forbidden --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json --limit-initiatives 25 --max-docs-per-initiative 1 --timeout 15
python3 scripts/report_senado_waf_block_profile.py --db etl/data/staging/politicos-es.db --initiative-source-id senado_iniciativas --only-linked-to-votes --sample-limit 25 --out docs/etl/sprints/AI-OPS-306/evidence/senado_waf_block_profile_post_retry_20260228T205000Z.json
python3 scripts/export_missing_initiative_doc_urls.py --db etl/data/staging/politicos-es.db --initiative-source-ids 'senado_iniciativas' --only-actionable-missing --only-linked-to-votes --format csv --out docs/etl/sprints/AI-OPS-306/exports/senado_tail_actionable_post_retry_20260228T205000Z.csv
INITDOC_MISSING_EXPORT_SOURCE_IDS='senado_iniciativas' INITDOC_MISSING_EXPORT_OUT=docs/etl/sprints/AI-OPS-306/exports/senado_tail_actionable_strict_20260228T205500Z.csv DB_PATH=etl/data/staging/politicos-es.db just parl-check-missing-initdoc-urls-actionable-empty
INITDOC_MISSING_EXPORT_SOURCE_IDS='congreso_iniciativas,senado_iniciativas' INITDOC_MISSING_EXPORT_OUT=docs/etl/sprints/AI-OPS-306/exports/global_tail_actionable_strict_20260228T205500Z.csv DB_PATH=etl/data/staging/politicos-es.db just parl-check-missing-initdoc-urls-actionable-empty
DB_PATH=etl/data/staging/politicos-es.db just etl-tracker-status
```

## Resultado

- Retry acotado Senado (sin palanca nueva): `initiatives_seen=25`, `candidate_urls=50`, `fetched_ok=0`, `failures_total=30` (primeros fallos `HTTP 403`), `playwright_init_error=null`.
- Cola accionable Senado (`only-linked-to-votes`) sin delta: `680` URLs (`345` iniciativas).
- Perfil WAF post-retry: `blocked_403_urls=607`, `blocked_500_urls=71`, `zero_doc_initiatives=25`.
- Checks strict-empty de cola accionable:
  - Senado: `rc=4`
  - Global (Congreso+Senado): `rc=4`
- Rebaseline de cobertura iniciativas (DB real):
  - `total_doc_links=8732`
  - `downloaded_doc_links=4205` (`48.16%`)
  - `missing_doc_links=4527`
  - `missing_doc_links_actionable=4456`
  - `effective_downloaded_doc_links_pct=48.55`
  - `linked_to_votes_with_downloaded_docs=726/751` (`96.67%`)
- Calidad local de docs descargados se mantiene cerrada:
  - `fetch_status_coverage_pct=100.0`
  - `excerpt_coverage_pct=100.0`
  - `extraction_coverage_pct=100.0`
  - `extraction_needs_review=0`
- Paridad tracker post-slice: `mismatches=0`, `done_zero_real=0`.

## Conclusión operativa

No hubo mejora de descarga en Senado con la cookie seed existente; se confirma estado `no_new_lever` para la cola accionable y se mantiene la dependencia externa de captura manual usable (fila 829).
