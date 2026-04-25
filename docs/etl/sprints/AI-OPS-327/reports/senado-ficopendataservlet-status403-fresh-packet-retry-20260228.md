# AI-OPS-327 - Retry dirigido `ficopendataservlet` (`status=403`) con cohorte fresca

## Objetivo
Continuar la fila `822` sobre la cola residual `ficopendataservlet` con una cohorte fresca `status=403`, manteniendo un único intento acotado por sprint.

## Ejecucion
1. Baseline
- `report_initiative_doc_status.py` (before)
- `report_senado_waf_block_profile.py --only-linked-to-votes` (before)
- `report_senado_manual_capture_validity.py --strict` (`status=degraded`, `strict_fail_reasons=[no_usable_capture]`, `rc=4`)

2. Seleccion de packet fresco
- Pool base: cola accionable post-AI-OPS-326.
- Filtro: `doc_url LIKE %ficopendataservlet%`, `last_http_status=403`, excluyendo URLs ya usadas en AI-OPS-31x/32x/324/325/326.
- Resultado: `80` URLs / `80` iniciativas (`excluded_used_urls_total=723`).

3. Retry acotado
- `backfill-initiative-documents --doc-urls-file <fresh_packet> --retry-http-statuses 403 --archive-fallback --archive-fallback-http-statuses 403`
- Resultado:
  - `candidate_urls=80`, `urls_to_fetch=80`
  - `fetched_ok=1`, `archive_hits=1`, `archive_fetched_ok=1`, `text_documents_upserted=1`
  - `skipped_redundant_global_urls=25`, `failures=30`
  - `selected_scope_no_limit=true`

4. Post-proceso estructural y calidad local
- `backfill_initiative_doc_extractions.py --only-missing --initiative-source-ids senado_iniciativas`
  - `seen=1`, `upserted=1`, `needs_review=0`.
- Se detecta `downloaded_missing_excerpt=1` tras la nueva descarga.
- `backfill_initiative_doc_excerpts.py` cierra la regresion local (`seen=1`, `updated=1`), dejando `downloaded_missing_excerpt=0`.

## Delta medido
- Cobertura global iniciativas:
  - `downloaded_doc_links: 4410 -> 4411` (`+1`)
  - `missing_doc_links: 5143 -> 5142` (`-1`)
  - `missing_doc_links_actionable: 4959 -> 4958` (`-1`)
  - `effective_downloaded_doc_links_pct: 47.07 -> 47.08`
- Senado (`by_source`):
  - `downloaded_doc_links: 3598 -> 3599` (`+1`)
  - `missing_doc_links_actionable: 4959 -> 4958` (`-1`)
- Cola/WAF `only_linked_to_votes`:
  - `missing_urls: 1183 -> 1182` (`-1`)
  - CSV cola (`incl. cabecera`): `1184 -> 1183`
  - `blocked_403_urls: 331 -> 251` (`-80`)
  - `blocked_500_urls: 0 -> 0`
  - `unknown_status_urls: 297 -> 297`
  - `zero_doc_initiatives: 6 -> 5`.

## Lectura operativa
- Hay mejora material, pero marginal en descarga (`+1`) frente al volumen reintentado (`80` URLs): rendimiento decreciente en esta cohorte.
- Mantener la politica anti-loop: siguiente sprint con una sola cohorte nueva (`status=0` trazabilidad) o cambio de palanca (captura usable).

## Evidencia
- `docs/etl/sprints/AI-OPS-327/evidence/initiative_doc_status_before_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_waf_block_profile_before_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_manual_capture_validity_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_ficopendataservlet_status403_fresh_packet_summary_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_retry_ficopendataservlet_status403_fresh_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/initiative_doc_extractions_backfill_after_retry_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/initiative_doc_excerpts_backfill_after_retry_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/initiative_doc_status_after_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/initiative_doc_status_delta_ai_ops_327_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_waf_block_profile_after_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_waf_block_profile_delta_ai_ops_327_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_tail_actionable_delta_ai_ops_327_20260228T235854Z.json`
- `docs/etl/sprints/AI-OPS-327/evidence/senado_extraction_nav_noise_post_20260228T235854Z.json`
