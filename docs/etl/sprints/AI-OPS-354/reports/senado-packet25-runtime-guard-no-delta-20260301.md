# AI-OPS-354 — Packet 25 con runtime guard (sin delta neta)

## Objetivo
Validar escalado operativo `status=404` a packet `25` con guard de runtime antes de cerrar el objetivo de conversión neta.

## Resultado
- Intento 1 (`archive-fallback-http-statuses=403,404`): timeout operativo (`rc=124`, `runtime=422s`).
- Intento 2 tuneado (`archive-fallback-http-statuses=404`): completo en `5s`, sin timeout.
- Retry tuneado: `candidate_urls=24`, `urls_to_fetch=24`, `fetched_ok=0`, `archive_hits=0`, `failures_total=24`.
- Deltas de cobertura en DB principal: sin cambios (`downloaded_doc_links=4804`, `missing_doc_links_actionable=4559`, `missing_urls=783`).

## Evidencia principal
- `docs/etl/sprints/AI-OPS-354/evidence/senado_status404_manual_cookie_archive_retry_packet25_runtime_20260301T081547Z.json`
- `docs/etl/sprints/AI-OPS-354/evidence/senado_status404_manual_cookie_archive_retry_packet25_tuned_20260301T083334Z.json`
- `docs/etl/sprints/AI-OPS-354/evidence/quality_initiatives_before_packet25_20260301T081547Z.json`
- `docs/etl/sprints/AI-OPS-354/evidence/quality_initiatives_after_packet25_tuned_20260301T083334Z.json`
- `docs/etl/sprints/AI-OPS-354/evidence/senado_archive_gap_urls_packet25_tuned_20260301T083334Z.json`
- `docs/etl/sprints/AI-OPS-354/evidence/senado_packet25_runtime_guard_no_delta_ai_ops_354_20260301T083334Z.json`

## Conclusión
El guard de runtime queda validado, pero el objetivo de conversión neta no se cumple en AI-OPS-354. Se mantiene la fila abierta y se pasa a siguiente sprint con nueva ejecución dirigida.
