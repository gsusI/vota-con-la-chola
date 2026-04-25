# AI-OPS-234: Refresh de sesión Senado (evidencia `no_new_lever`)

## Objetivo
Resolver la fila de "refresh reproducible de sesión" con criterio verificable: mejora real en cola (`zero_doc_initiatives`) o cierre explícito por `no_new_lever` con evidencia machine-readable y actualización append-only.

## Comandos ejecutados

```bash
python3 scripts/report_senado_cookie_lever_status.py \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --domain-contains senado.es \
  --max-age-hours 24 \
  --min-domain-cookies 1 \
  --min-unexpired-persistent-cookies 1 \
  --out docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_latest.json

python3 scripts/report_senado_cookie_lever_status.py \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --domain-contains senado.es \
  --max-age-hours 24 \
  --min-domain-cookies 1 \
  --min-unexpired-persistent-cookies 1 \
  --strict \
  --out docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_strict_latest.json

python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --retry-forbidden \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --limit-initiatives 25 \
  --max-docs-per-initiative 1 \
  --timeout 15 \
  > docs/etl/sprints/AI-OPS-234/evidence/senado_backfill_docs_retry_cookie_limit25_latest.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --only-linked-to-votes \
  --only-initiatives-without-any-doc \
  --max-urls-per-initiative 1 \
  --format csv \
  --out docs/etl/sprints/AI-OPS-234/exports/senado_zero_doc_actionable_queue_latest.csv

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --only-linked-to-votes \
  --sample-limit 25 \
  --out docs/etl/sprints/AI-OPS-234/evidence/senado_waf_block_profile_latest.json
```

## Resultado medible
- Estado palanca cookie (`report_senado_cookie_lever_status`):
  - `status=degraded`, `no_new_lever=true`
  - `age_hours=204.153` (umbral `24h`)
  - `domain_total=6`, `unexpired_persistent_total=2`
  - `strict_fail_reasons=["cookie_file_stale"]`
  - `strict rc=4`
- Retry acotado posterior (misma cookie):
  - `candidate_urls=50`, `fetched_ok=0`, `text_documents_upserted=0`
  - `playwright_init_error=null`
  - `failures_count=30` (predominio `HTTP 403`)
- Cola zero-doc post-run: `25` iniciativas (sin delta)
- WAF post-run vs AI-OPS-233:
  - `missing_urls=680` (delta `0`)
  - `missing_initiatives=345` (delta `0`)
  - `zero_doc_initiatives=25` (delta `0`)
  - `blocked_403_urls=607` (delta `0`)

## Decisión operativa
Se cierra la fila de refresh por criterio `no_new_lever` verificado (stale cookie + retry sin mejora). El siguiente trabajo queda explícitamente fuera de retries ciegos: captura manual/headful de una sesión nueva y sanitizada (nueva palanca) antes de otro intento estricto.

## Artefactos
- `docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_latest.json`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_strict_latest.json`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_cookie_lever_status_strict_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_backfill_docs_retry_cookie_limit25_latest.json`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_waf_block_profile_latest.json`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_waf_block_profile_summary_latest.json`
- `docs/etl/sprints/AI-OPS-234/evidence/senado_waf_block_profile_delta_vs_ai_ops_233_latest.json`
- `docs/etl/sprints/AI-OPS-234/exports/senado_zero_doc_actionable_queue_latest.csv`
- `docs/etl/sprints/AI-OPS-234/evidence/tracker_status_latest.log`
