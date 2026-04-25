# AI-OPS-340 - lane status=404 archive fallback (Senado)

## Objetivo
Cerrar parte del gap `archive fallback: no snapshot candidates` en la cola `status=404` con una palanca controlable en código y evidencia reproducible.

## Cambios de producto/pipeline
- `etl/parlamentario_es/text_documents.py`
  - Nuevos probes de familia de endpoint para lookup Wayback en URLs Senado:
    - `ficopendataservlet` <-> `detalleiniciativa`
    - `tipoFich=3` y `tipoFich=12`
  - Mantiene probes previas de esquema/host/query y añade métricas:
    - `archive_lookup_probe_requests`
    - `archive_variant_hits`
- `scripts/export_senado_archive_gap_urls.py`
  - Export estructurado de fallos `archive fallback: no snapshot candidates`.
  - Salidas: resumen JSON + CSV deduplicado por URL con campos operativos (`url_kind`, `legis`, `tipo_ex`, `num_ex`).
- `justfile`
  - Recipes:
    - `parl-report-senado-archive-gap-urls`
    - `parl-check-senado-archive-gap-urls`

## Validación
- Unit tests focales:
  - `tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_uses_senado_url_variants`
  - `tests.test_parl_text_documents.TestParlTextDocuments.test_backfill_initiative_documents_archive_fallback_uses_senado_endpoint_family_probes`
  - `tests.test_export_senado_archive_gap_urls`
- Resultado: `Ran 4 tests ... OK`.

## Corrida real (DB principal)
- Timestamp: `20260301T022459Z`
- Packet: `docs/etl/sprints/AI-OPS-340/exports/senado_status404_recent-window_packet6_20260301T021418Z.csv`
- Comando principal:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db etl/data/staging/politicos-es.db --initiative-source-ids senado_iniciativas --skip-link-backfill --doc-urls-file <packet6.csv> --retry-http-statuses 404 --archive-fallback --archive-fallback-http-statuses 404 --limit-initiatives 6 --max-docs-per-initiative 1 --timeout 12`

### Resultado del retry
- `candidate_urls=6`
- `urls_to_fetch=6`
- `fetched_ok=4`
- `archive_hits=4`
- `archive_fetched_ok=4`
- `archive_lookup_attempted=6`
- `archive_lookup_probe_requests=78`
- `archive_variant_hits=4`
- `failures=2` (ambos `detalleiniciativa ... no snapshot candidates`)

### Delta de cobertura
- `downloaded_doc_links: 4420 -> 4424` (`+4`)
- `missing_doc_links: 5133 -> 5129` (`-4`)
- `missing_doc_links_actionable: 4949 -> 4945` (`-4`)
- `effective_downloaded_doc_links_pct: 47.18 -> 47.22`
- `missing_urls (linked-to-votes): 1173 -> 1169`

## Cola residual de archive gap
- Consolidado AI-OPS-339 + AI-OPS-340:
  - `archive_no_snapshot_failures_total=24`
  - `unique_urls_total=22`
  - dominante: `legis=14`, `tipo_ex=622`

## Artefactos
- Retry:
  - `docs/etl/sprints/AI-OPS-340/evidence/senado_retry_status404_recent-window_packet6_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/evidence/senado_retry_status404_recent-window_packet6_20260301T022459Z.stderr.log`
- Estado/delta:
  - `docs/etl/sprints/AI-OPS-340/evidence/initiative_doc_status_before_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/evidence/initiative_doc_status_after_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/evidence/initiative_doc_status_delta_ai_ops_340_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/evidence/senado_waf_block_profile_before_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/evidence/senado_waf_block_profile_after_20260301T022459Z.json`
- Archive gap:
  - `docs/etl/sprints/AI-OPS-340/evidence/senado_archive_gap_urls_20260301T022459Z.json`
  - `docs/etl/sprints/AI-OPS-340/exports/senado_archive_gap_urls_20260301T022459Z.csv`
