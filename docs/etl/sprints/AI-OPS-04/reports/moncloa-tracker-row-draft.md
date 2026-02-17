# Moncloa Tracker Row Draft — AI-OPS-04

Date: 2026-02-16  
Row target: `Accion ejecutiva (Consejo de Ministros)` in `docs/etl/e2e-scrape-load-tracker.md`

## Propuesta de fila (para revision L2)

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | PARTIAL | Ingesta y normalizacion reproducibles via `--from-file` (20+8 `policy_events` mapeados, parity export `all_match=true`). Bloqueador: `--strict-network` falla en este entorno (100% error en matriz: DNS/zero-item RSS) y falta validar acuerdos/normas contra BOE cuando exista publicacion. Siguiente comando: `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30` |

## DoD wording (tracker-ready)

Hecho:
- Scraper y normalizacion operativos con replay reproducible (`from-file`) para `moncloa_referencias` y `moncloa_rss_referencias`.
- Re-materializacion aplicada: `policy_events` moncloa = `28` (20 + 8), `source_url` cubierto, `null event_date` efectivo en `policy_events` = `0`.
- Paridad live-vs-export verificada: `policy_events_total` live `28` = export `28`, presencia de ambas fuentes moncloa en snapshot.

Bloqueador:
- `strict-network` no reproducible en este entorno (matriz: `2/2` runs con `error`, failure rate `100%`), por DNS/alcance de red y RSS sin items bajo modo estricto.
- Queda pendiente validacion BOE de acuerdos/normas cuando haya publicacion enlazable.

Siguiente comando:
- `python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source moncloa_referencias --strict-network --timeout 30`

## Referencias de evidencia

- `docs/etl/sprints/AI-OPS-04/evidence/moncloa-tracker-evidence.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-ingest-matrix.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-04/reports/moncloa-dashboard-parity.md`
