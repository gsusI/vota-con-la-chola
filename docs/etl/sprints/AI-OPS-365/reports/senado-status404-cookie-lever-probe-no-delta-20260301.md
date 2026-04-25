# AI-OPS-365 — Senado `status=404` cohorte `detalleiniciativa` (cookie lever probe)

## Objetivo
Ejecutar el TODO de palanca (fila 855): validar disponibilidad real de captura manual usable y probar conversión en la cohorte bloqueada `leg10 tipo610` (`18` URLs `detalleiniciativa`).

## Estado de palanca manual
- `manual_capture_validity.status=ok`
- `usable_captures_total=4`
- `pending_targets_total=8` (`pending_unmatched=2`, `pending_access_denied=6`)

Fuentes:
- `docs/etl/sprints/AI-OPS-365/evidence/senado_manual_capture_validity_20260301T094234Z.json`
- `docs/etl/sprints/AI-OPS-365/evidence/senado_manual_capture_target_progress_20260301T094234Z.json`
- `docs/etl/sprints/AI-OPS-365/evidence/senado_manual_capture_pending_targets_20260301T094234Z.json`

## Probe 1 (cookie usable genérica)
- cookie seleccionada: `etl/data/raw/manual/senado_cookie_refresh_ai_ops_299_01_seed_20260301T075125Z.cookies.json`
- `candidate_urls=18`, `fetched_ok=0`, `failures=18`, `archive_hits=0`, runtime `294.00s`
- patrón de fallo: `archive fallback: no snapshot candidates`

Fuente: `docs/etl/sprints/AI-OPS-365/evidence/senado_status404_gap_cookie_retry_20260301T094234Z.json`

## Probe 2 (cookie específica `leg10 tipo610`)
- cookie usada: `etl/data/raw/manual/senado_cookie_refresh_ai_ops_299_02_leg10_tipo610_20260301T075159Z.cookies.json`
- `candidate_urls=18`, `fetched_ok=0`, `failures=18`, `archive_hits=0`, runtime `311.00s`
- mismo patrón de fallo: `archive fallback: no snapshot candidates`

Fuente: `docs/etl/sprints/AI-OPS-365/evidence/senado_status404_gap_cookie_retry_leg10_20260301T094234Z.json`

## Delta KPI
- `downloaded_doc_links`: `5202 -> 5202` (`0`)
- `missing_doc_links_actionable`: `4160 -> 4160` (`0`)
- `missing_urls`: `384 -> 384` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-365/evidence/senado_status404_gap_cookie_retry_delta_ai_ops_365_20260301T094234Z.json`
- `docs/etl/sprints/AI-OPS-365/evidence/senado_status404_gap_cookie_retry_leg10_delta_ai_ops_365_20260301T094234Z.json`

## Conclusión
La palanca de captura existe, pero no es efectiva para esta cohorte: no hay snapshots archivísticos y los retries con cookie no convierten. Se cierra el objetivo como `NO_DELTA_WITH_EVIDENCE` y se requiere fallback técnico alterno para `detalleiniciativa` sin snapshot.
