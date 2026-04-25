# AI-OPS-367 — Cohorte `detalleiniciativa` reclasificada a `status=403` (row 857)

## Objetivo
Ejecutar la lane `status=403` sobre la cohorte fija de `18` URLs (`leg10 tipo610`) usando perfil/captura fresca, y cerrar el TODO `857` con delta real o `NO_DELTA_WITH_EVIDENCE`.

## Palanca fresca (captura)
- Captura ejecutada: `senado_cookie_refresh_ai_ops_367_01_leg10_tipo610_20260301T102944Z`.
- Resultado de captura: `Access Denied`, `cookies_domain_total=0`, `usable_capture=false`.
- Estado de lever fresco: `status=degraded`, `no_new_lever=true`, `strict_fail_reasons=[no_domain_cookies,no_unexpired_persistent_cookies]`.

## Retry dirigido (cohorte fija)
- Cohorte: `docs/etl/sprints/AI-OPS-364/exports/senado_archive_gap_urls_20260301T092750Z.csv`.
- Modo: `retry-http-statuses=403`, `archive-fallback-http-statuses=403,404`, `refetch-existing`, `playwright-user-data-dir=<fresh_profile>`.
- Resultado: `candidate_urls=18`, `urls_to_fetch=18`, `fetched_ok=0`, `archive_hits=0`, `direct_variant_attempted_urls=18`, `direct_variant_fetched_ok=0`, `failures=18`, `playwright_init_error=null`.
- Patrón de fallo: `HTTP 403 (playwright)` en variantes `ficopendataservlet` (`tipoFich=3/12`).

## Delta KPI
- `downloaded_doc_links`: `5202 -> 5202` (`0`)
- `missing_doc_links_actionable`: `4160 -> 4160` (`0`)
- `missing_urls`: `384 -> 384` (`0`)
- `blocked_403_urls`: `32 -> 32` (`0`)

## Conclusión
Con captura/perfil fresco en este entorno no se obtuvo nueva palanca efectiva (`no_new_lever=true`) y la cohorte permanece bloqueada por `403`. Se cierra `857` como `NO_DELTA_WITH_EVIDENCE` y corresponde abrir una estrategia de adquisición de sesión challenge-resolved fuera de este entorno (o despriorizar la cohorte si no hay nueva palanca).

## Evidencia
- `docs/etl/sprints/AI-OPS-367/evidence/senado_manual_capture_validity_20260301T102943Z.json`
- `docs/etl/sprints/AI-OPS-367/evidence/senado_cookie_lever_status_fresh_20260301T102943Z.json`
- `docs/etl/sprints/AI-OPS-367/evidence/senado_status403_profile_retry_20260301T102943Z.json`
- `docs/etl/sprints/AI-OPS-367/evidence/senado_status403_profile_retry_delta_ai_ops_367_20260301T102943Z.json`
- `docs/etl/sprints/AI-OPS-367/evidence/e2e_tracker_status_with_tracker_20260301T102943Z.log`
