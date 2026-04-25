# AI-OPS-221: Cierre de linkage de dominios en indicadores outcomes/confusores

Fecha (UTC): 2026-02-26
DB objetivo: `etl/data/staging/politicos-es.db`

## Objetivo
Cerrar el gap del tracker en linkage causal de indicadores (`indicator_series.domain_id`) para Eurostat/BDE/AEMET, manteniendo trazabilidad y reproducibilidad.

## Cambio implementado
- `etl/politicos_es/indicator_backfill.py`:
  - añade resolución con seed determinista de dominios (`domains`) cuando falta `domain_key` en catálogo inicial.
  - usa `upsert_domain` para crear/actualizar dominios inferidos con metadatos explícitos.
  - expone métricas nuevas: `indicator_domains_seeded` y `indicator_domain_keys_seeded`.
- tests:
  - nuevo caso `test_indicator_backfill_seeds_domains_for_inferred_keys` en `tests/test_indicator_backfill.py`.

## Validación
- `python3 -m unittest tests/test_indicator_backfill.py`
  - Resultado: `Ran 3 tests ... OK`.

## Corrida real
Comando ejecutado:
- `python3 scripts/ingestar_politicos_es.py backfill-indicators --db etl/data/staging/politicos-es.db --source-ids eurostat_sdmx bde_series_api aemet_opendata_series`

Resultado (`backfill_indicators_latest.json`):
- `source_records_seen=2400`
- `source_records_mapped=2400`
- `indicator_domains_seeded=3`
- `indicator_domain_keys_seeded=[energia_medio_ambiente, proteccion_social_pensiones, vivienda_urbanismo]`
- `indicator_series_total=2400`
- `indicator_series_with_domain_id=2400`
- `indicator_series_unresolved_domain=0`
- `indicator_points_total=37431`
- `indicator_observation_records_total=37431`

## Evidencia
- `docs/etl/sprints/AI-OPS-221/evidence/backfill_indicators_latest.json`
- `docs/etl/sprints/AI-OPS-221/evidence/unittest_indicator_backfill_20260226T2354Z.txt`
- `docs/etl/sprints/AI-OPS-221/evidence/tracker_status_latest.log`
