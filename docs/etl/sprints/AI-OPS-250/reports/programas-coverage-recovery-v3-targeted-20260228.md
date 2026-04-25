# AI-OPS-250 - Recuperación dirigida de cobertura (`programas_partidos`)

## Objetivo
Reducir el gap abierto en AI-OPS-249 (`party_proxy_count=10`) recuperando partidos en cero sin romper contratos de calidad/tracker.

## Estrategia
- Lane controlable en dos etapas:
  - `v2`: overrides dirigidos a candidatos fuertes detectados por curación automática para `EAJ-PNV` e `Izquierda Unida`.
  - `v3`: discovery adicional para residuales (`CCa`, `UPN`, `PSC`) + overrides dirigidos en `CCa`/`UPN`.
- Validación obligatoria por etapa:
  - `strict-network` ingest real,
  - recompute declarado/combinado,
  - cierre reproducible de cola (`review-decision --status ignored`),
  - `quality-report --include-declared` + `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`.

## Cambios de datos ejecutados
### v2 (AI-OPS-250)
- Cambios URL (6 filas):
  - `EAJ-PNV` -> `https://www.eaj-pnv.eus/es/adjuntos-documentos/20945/pdf/con-voz-propia-programa-electoral-23-j`
  - `Izquierda Unida` -> `https://izquierdaunida.org/wp-content/uploads/2019/10/Programa-IU-10N-22-medidas-clave.pdf`
- Resultado post-ignore:
  - `party_proxy_count=12`
  - `support=97`
  - `unclear=291`
  - `declared_positions_total=136`

### v3 (AI-OPS-250, estado final)
- Discovery adicional residual:
  - `CCa`: se detectan PDFs programáticos en `programas-electorales` (incluye `Manifiesto Europeas 2024.pdf` y `Programa Electoral ... 2023.pdf`).
  - `UPN`: se detecta URL de propuestas temática; no fue suficiente para materializar evidencia.
  - `PSC`: sin candidatos programáticos en crawl/sitemap estático.
- Cambios URL sobre `v2` (6 filas):
  - `CCa` (3 ciclos) -> PDFs programáticos 2023/2024.
  - `UPN` (3 ciclos) -> `propuestas-de-upn-...discapacidad/`.
- Resultado post-ignore (final):
  - `party_proxy_count=13`
  - `support=107`
  - `unclear=316`
  - `declared_positions_total=146`
  - `review_pending=0`
  - gate declarado `passed=true`
  - tracker enforce limpio (`mismatches=0`, `done_zero_real=0`).

## Delta clave
### AI-OPS-249 -> AI-OPS-250 v3 (post-ignore)
- `party_proxy_count`: `10 -> 13` (`+3`)
- `support`: `88 -> 107` (`+19`)
- `unclear`: `228 -> 316` (`+88`)
- `declared_positions_total`: `127 -> 146` (`+19`)

### Partidos recuperados
- `EAJ-PNV`: `0 -> 36` evidencias (`support +6`).
- `Izquierda Unida`: `0 -> 36` evidencias (`support +3`).
- `CCa`: `0 -> 35` evidencias (`support +10`).

### Residual
- Persisten en cero: `PSC`, `UPN`.

## Artefactos
- Reportes y métricas:
  - `docs/etl/sprints/AI-OPS-250/evidence/programas_declared_status_post_recovery_v3_targeted_post_ignore_20260228.json`
  - `docs/etl/sprints/AI-OPS-250/evidence/quality_declared_programas_post_recovery_v3_targeted_post_ignore_20260228.json`
  - `docs/etl/sprints/AI-OPS-250/evidence/tracker_status_post_recovery_v3_targeted_post_ignore_enforce_20260228.log`
  - `docs/etl/sprints/AI-OPS-250/exports/programas_status_delta_ai_ops_249_vs_ai_ops_250_v3_post_ignore_20260228.csv`
  - `docs/etl/sprints/AI-OPS-250/exports/programas_party_delta_ai_ops_249_vs_ai_ops_250_v3_post_ignore_20260228.csv`
- Discovery residual:
  - `docs/etl/sprints/AI-OPS-250/exports/programas_missing3_candidate_links_discovery_20260228.csv`
  - `docs/etl/sprints/AI-OPS-250/exports/programas_psc_deep_discovery_20260228.csv`
  - `docs/etl/sprints/AI-OPS-250/exports/programas_psc_sitemap_discovery_20260228.csv`

## Decisión operativa
- Se mantiene `v3` en staging como mejor estado observable en este sprint (maximiza recuperación de cobertura y señal útil, con contratos en verde).
- Próximo foco: discovery reproducible específico para `PSC` y `UPN` con nueva palanca (fuente/canal/documento) para cerrar `party_proxy_count` residual sin degradar higiene.
