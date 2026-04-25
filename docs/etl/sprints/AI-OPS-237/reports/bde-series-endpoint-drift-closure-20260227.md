# AI-OPS-237: Cierre de deriva de endpoint BDE + carga strict real

## Objetivo
Cerrar la fila `Indicadores (confusores): Banco de España` eliminando el bloqueo por DNS del endpoint legado y restableciendo ingestión reproducible con red real + estructuración en tablas de indicadores.

## Cambios de código
- `etl/politicos_es/config.py`
  - `bde_series_api.default_url` actualizado al endpoint operativo actual:
    - `https://app.bde.es/bierest/resources/srdatosapp/listaSeries?idioma=es&series=D_1NBAF472&rango=30M`
- `etl/politicos_es/connectors/bde_series.py`
  - soporte para payload BDE en forma paralela `fechas` + `valores`,
  - soporte de payload comprimido `gzip` en parser (`parse_bde_records`).
- `etl/politicos_es/indicator_backfill.py`
  - heurística de dominio para BDE:
    - `euribor/hipotec/vivienda -> vivienda_urbanismo`
    - `paro/empleo/pension(es) -> proteccion_social_pensiones`
- Tests:
  - `tests/test_bde_connector.py`
    - nuevo test para shape `fechas/valores`,
    - nuevo test para payload `gzip`.
  - `tests/test_indicator_backfill.py`
    - nuevo test de mapeo de dominio `Euribor -> vivienda_urbanismo`.

## Validación técnica

```bash
python3 -m unittest tests/test_bde_connector.py tests/test_indicator_backfill.py
python3 -m unittest tests/test_bde_connector.py tests/test_samples_e2e.py
```

Resultado:
- `Ran 11 tests`, `OK`
- `Ran 11 tests`, `OK`

## Ejecución real (strict-network)

```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source bde_series_api \
  --snapshot-date 2026-02-27 \
  --strict-network \
  --timeout 30
```

Resultado:
- `bde_series_api: 1/1 registros validos`
- run DB más reciente:
  - `run_id=278`, `status=ok`, `records_seen=1`, `records_loaded=1`

## Estructuración posterior

```bash
python3 scripts/ingestar_politicos_es.py backfill-indicators \
  --db etl/data/staging/politicos-es.db \
  --source-ids bde_series_api
```

Resultado final (tras fix de dominio):
- `source_records_seen=3`, `source_records_mapped=3`
- `indicator_series_upserted=3`
- `indicator_points_upserted=37`
- `observation_records_upserted=37`
- `indicator_series_with_domain_id=3`
- `indicator_series_unresolved_domain=0`

## Decisión
- Se considera cerrado el bloqueo técnico de BDE en esta infraestructura.
- La fila del tracker puede pasar a `DONE` con evidencia AI-OPS-237.
