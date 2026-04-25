# AI-OPS-233: Escalado operativo Senado por cohortes top (retry estricto)

## Objetivo
Ejecutar un retry estricto ampliado sobre la cola Senado y verificar si existe mejora real en `zero_doc_initiatives` o `missing_urls` usando el perfil WAF canónico.

## Comandos ejecutados

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --retry-forbidden \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --limit-initiatives 50 \
  --max-docs-per-initiative 1 \
  --timeout 15 \
  > docs/etl/sprints/AI-OPS-233/evidence/senado_backfill_docs_retry_cookie_limit50_latest.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --only-linked-to-votes \
  --only-initiatives-without-any-doc \
  --max-urls-per-initiative 1 \
  --format csv \
  --out docs/etl/sprints/AI-OPS-233/exports/senado_zero_doc_actionable_queue_latest.csv

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --only-linked-to-votes \
  --sample-limit 25 \
  --out docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_latest.json

python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-id senado_iniciativas \
  --only-linked-to-votes \
  --sample-limit 25 \
  --strict \
  --out docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_strict_latest.json
```

## Resultado medible
- Retry ampliado (`limit-initiatives=50`):
  - `candidate_urls=76`
  - `fetched_ok=0`
  - `text_documents_upserted=0`
  - `playwright_init_error=null`
  - `failures_count=30` (predominio `HTTP 403`)
- Cola zero-doc accionable post-run: `25` filas (`25` iniciativas únicas), sin mejora frente al baseline previo.
- Perfil WAF post-run (`only_linked_to_votes=true`):
  - `missing_urls=680` (delta `0` vs AI-OPS-232)
  - `missing_initiatives=345` (delta `0`)
  - `zero_doc_initiatives=25` (delta `0`)
  - `blocked_403_urls=607` (delta `+19`)
  - `blocked_500_urls=71` (delta `-19`)
- Verificación strict del reporte: `exit=0`.

## Conclusión operativa
No hay mejora en cierre de cola (`zero_doc_initiatives` y `missing_urls` sin delta). Se confirma bloqueo remoto persistente por WAF, por lo que se cierra el objetivo de escalado como intento estricto ejecutado + evidencia formal publicada y se traslada el siguiente paso a una lane de desbloqueo con nueva palanca (refresh de sesión/cookie/canal alterno) para evitar reintentos ciegos.

## Artefactos
- `docs/etl/sprints/AI-OPS-233/evidence/senado_backfill_docs_retry_cookie_limit50_latest.json`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_latest.json`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_strict_latest.json`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_strict_stdout_latest.txt`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_strict_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_waf_block_profile_delta_vs_ai_ops_232_latest.json`
- `docs/etl/sprints/AI-OPS-233/evidence/senado_zero_doc_actionable_queue_export_latest.txt`
- `docs/etl/sprints/AI-OPS-233/exports/senado_zero_doc_actionable_queue_latest.csv`
