# AI-OPS-232: Huella WAF Senado + cola zero-doc reproducible (2026-02-27)

## Objetivo
Convertir el bloqueo remoto de Senado en un artefacto canónico, reproducible y accionable por cohorte (`legis/tipoEx`), con priorización explícita de iniciativas sin ningún documento descargado.

## Comandos ejecutados

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --retry-forbidden \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --limit-initiatives 25 \
  --max-docs-per-initiative 1 \
  --timeout 15 \
  > docs/etl/sprints/AI-OPS-232/evidence/senado_backfill_docs_retry_cookie_latest.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --only-linked-to-votes \
  --only-initiatives-without-any-doc \
  --max-urls-per-initiative 1 \
  --format csv \
  --out docs/etl/sprints/AI-OPS-232/exports/senado_zero_doc_actionable_queue_latest.csv

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --only-linked-to-votes \
  --sample-limit 25 \
  --out docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_latest.json

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --only-linked-to-votes \
  --sample-limit 25 \
  --strict \
  --out docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_strict_latest.json
```

## Resultado medible
- Retry acotado Senado (`limit-initiatives=25`): `candidate_urls=50`, `fetched_ok=0`, `text_documents_upserted=0`, `failures=30` (predominio `HTTP 403`), `playwright_init_error=null`.
- Cola priorizada zero-doc: `25` filas (`25` iniciativas únicas), con exclusiones reproducibles (`excluded_redundant_senado_global=70`, `excluded_initiatives_with_downloaded_docs=603`).
- Perfil WAF canónico (`only_linked_to_votes=true`):
  - `missing_urls=680`
  - `missing_initiatives=345`
  - `blocked_403_urls=588`
  - `blocked_403_rate=0.864706`
  - `blocked_500_urls=90`
  - `zero_doc_initiatives=25`
- Cohortes de mayor incidencia 403: `leg10:tipo610`, `leg14:tipo621`, `leg14:tipo624`, `leg14:tipo622`.
- Verificación strict del reporte: `exit=0`.

## Artefactos
- `docs/etl/sprints/AI-OPS-232/evidence/senado_backfill_docs_retry_cookie_latest.json`
- `docs/etl/sprints/AI-OPS-232/exports/senado_zero_doc_actionable_queue_latest.csv`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_zero_doc_actionable_queue_export_latest.txt`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_latest.json`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_summary_latest.json`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_strict_latest.json`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_strict_stdout_latest.txt`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_strict_rc_latest.txt`

## Decisión operativa
Se cierra la deuda de "captura reproducible" (huella WAF) y se mantiene abierta la deuda de desbloqueo real de descarga Senado (fila de cola accionable), ya con priorización por cohorte e iniciativas zero-doc para escalado dirigido.
