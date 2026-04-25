# AI-OPS-235: Hardening de captura manual + probe de cookie refresh Senado

## Objetivo
Intentar completar la palanca externa de cookie refresh (`Captura manual headful`) con tooling reproducible dentro del repo y un retry estricto acotado para medir delta real de cierre.

## Cambios de código
- `scripts/manual_capture_playwright.py`
  - añade fallback automático de runtime Node (`PLAYWRIGHT_NODEJS_PATH`) cuando el driver bundled de Playwright no arranca,
  - añade flag `--headless` para poder ejecutar capturas en este runner,
  - añade telemetría de runtime en `meta.json`.
- `tests/test_manual_capture_playwright.py`
  - cobertura de fallback cuando el driver bundled está no sano,
  - cobertura de respeto de override por `PLAYWRIGHT_NODEJS_PATH`.

## Validación técnica

```bash
python3 -m unittest \
  tests/test_manual_capture_playwright.py \
  tests/test_report_senado_cookie_lever_status.py \
  tests/test_report_senado_waf_block_profile.py
```

Resultado: `Ran 7 tests`, `OK`.

## Ejecución de palanca (captura + retry)

### Capturas Playwright realizadas
1. URL de iniciativa Senado (detalle):
   - `scripts/manual_capture_playwright.py --url ...detalleiniciativa... --headless --channel ""`
2. URL raíz Senado:
   - `scripts/manual_capture_playwright.py --url https://www.senado.es/ --headless --channel ""`

Resultado común:
- `result_status=captured`, pero `title="Access Denied"`.
- `cookie_count=0` y `senado_domain_cookie_count=0` en ambos artefactos.
- Runtime fallback aplicado correctamente (`runtime_fallback_applied=true`).

Resumen canónico:
- `docs/etl/sprints/AI-OPS-235/evidence/senado_manual_cookie_capture_summary_latest.json`

### Estado de palanca cookie (estricto)

```bash
python3 scripts/report_senado_cookie_lever_status.py \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_refresh_ai_ops_235_20260227T100143Z.cookies.json \
  --domain-contains senado.es \
  --max-age-hours 24 \
  --min-domain-cookies 1 \
  --min-unexpired-persistent-cookies 1 \
  --strict \
  --out docs/etl/sprints/AI-OPS-235/evidence/senado_cookie_lever_status_strict_latest.json
```

Resultado:
- `cookie_status=degraded`
- `no_new_lever=true`
- `age_hours=0.005` (fresco)
- `strict_fail_reasons=["no_domain_cookies", "no_unexpired_persistent_cookies"]`
- `cookie_strict_rc=4`

### Retry acotado con cookie refresh capturada

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --skip-link-backfill \
  --retry-forbidden \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_refresh_ai_ops_235_20260227T100143Z.cookies.json \
  --limit-initiatives 25 \
  --max-docs-per-initiative 1 \
  --timeout 15 \
  > docs/etl/sprints/AI-OPS-235/evidence/senado_backfill_docs_retry_cookie_refresh_limit25_latest.json
```

Resultado:
- `candidate_urls=50`
- `fetched_ok=0`
- `text_documents_upserted=0`
- `playwright_init_error=null`
- `failures_count=30` (predominio `HTTP 403`)

### KPI delta vs AI-OPS-234
- `missing_urls=680` (delta `0`)
- `missing_initiatives=345` (delta `0`)
- `zero_doc_initiatives=25` (delta `0`)
- `blocked_403_urls=607` (delta `0`)

Evidencia:
- `docs/etl/sprints/AI-OPS-235/evidence/senado_waf_block_profile_delta_vs_ai_ops_234_latest.json`

## Decisión operativa
- Se completa el hardening técnico de la lane de captura (runtime + tests + ejecución reproducible).
- No se completa el desbloqueo de Senado: las capturas automáticas siguen en `Access Denied` sin cookies válidas de `senado.es`.
- Próximo paso sigue siendo una captura manual interactiva (resolviendo challenge) para obtener un cookie file válido antes de otro retry estricto.
