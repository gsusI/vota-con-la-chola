# AI-OPS-238: Cierre de cobertura BDE multi-serie + dominio resuelto

## Objetivo
Cerrar la fila `Cobertura BDE multi-serie (confusores)` pasando de una carga canónica de 1 serie a una cesta reproducible de múltiples series con `strict-network`, y dejar la estructuración sin `unresolved_domain`.

## Cambios de código
- `etl/politicos_es/config.py`
  - `bde_series_api.default_url` actualizado a cesta multi-serie validada (58 códigos BIEREST).
  - `bde_series_api.min_records_loaded_strict` endurecido de `1` a `58` para detectar drift de cobertura.
- `etl/politicos_es/indicator_backfill.py`
  - nueva heurística BDE para series de tipos de interés/deuda pública:
    - `tipo de interes/interés`, `interbancario`, `mercado monetario`, `eonia`, `ester`, `deuda publica/pública`, `rendimiento`, `benchmark`
    - mapeo a `impuestos_gasto_fiscalidad`.
- `scripts/build_source_probe_matrix.py`
  - `STRICT_URL_OVERRIDES['bde_series_api']` ahora se toma desde `SOURCE_CONFIG['bde_series_api']['default_url']` para evitar deriva de URL legacy.
- `tests/test_indicator_backfill.py`
  - nuevo test: `test_bde_interest_and_debt_maps_to_fiscal_domain`.

## Descubrimiento reproducible de series
Se ejecutó una exploración de prefijos conocidos y revalidación:
- Probe bruto (`D_1NB{PP}{000..999}` en `PP={AA,AC,AD,AE,AF,AS,BO,BP}`):
  - `docs/etl/sprints/AI-OPS-238/exports/bde_series_probe_known_prefixes_000_999.csv`
  - `docs/etl/sprints/AI-OPS-238/evidence/bde_series_probe_known_prefixes_000_999_summary.json`
- Recheck de candidatos `status=200` con parse correcto:
  - `candidate_count=58`, `ok_count=58`.
  - `docs/etl/sprints/AI-OPS-238/evidence/bde_series_probe_known_prefixes_200_recheck_summary.json`
  - `docs/etl/sprints/AI-OPS-238/exports/bde_series_ok_codes_known_prefixes_200_recheck.txt`

## Ejecución canónica (strict-network)

```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source bde_series_api \
  --url "$(cat docs/etl/sprints/AI-OPS-238/evidence/bde_multi_series_url_58_latest.txt)" \
  --snapshot-date 2026-02-27 \
  --strict-network \
  --timeout 30
```

Resultado:
- `bde_series_api: 58/58 registros validos`
- `run_id=280`, `run_status=ok`, `run_records_seen=58`, `run_records_loaded=58`

Evidencia:
- `docs/etl/sprints/AI-OPS-238/evidence/bde_multi_series_url_58_latest.txt`
- `docs/etl/sprints/AI-OPS-238/evidence/bde_series_ingest_multi58_strict_latest.json`
- `docs/etl/sprints/AI-OPS-238/evidence/bde_series_ingestion_runs_multi58_latest.txt`

## Estructuración y limpieza
Antes del ajuste de dominio:
- `indicator_series_upserted=60`
- `indicator_series_unresolved_domain=33`

Después del ajuste de dominio:
- `indicator_series_upserted=60`
- `indicator_series_with_domain_id=60`
- `indicator_series_unresolved_domain=0`
- `indicator_points_upserted=1804`
- `observation_records_upserted=1804`

Evidencia:
- `docs/etl/sprints/AI-OPS-238/evidence/backfill_indicators_bde_multi58_latest.json`
- `docs/etl/sprints/AI-OPS-238/evidence/backfill_indicators_bde_multi58_after_domain_fix_latest.json`

## Validación

```bash
python3 -m unittest tests/test_bde_connector.py tests/test_indicator_backfill.py
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real
```

Resultado:
- unit tests: `Ran 12 tests`, `OK`
- tracker gate: `mismatches=0`, `done_zero_real=0`

## Decisión
Fila `Cobertura BDE multi-serie (confusores)` cerrable en `DONE`:
- `series_loaded=58 (>=20)`
- `indicator_series_unresolved_domain=0`
- `records_loaded_strict=58` y `records_loaded_strict>=series_requested (58)`

## Verificación de baseline por defecto
Se valida también la ejecución sin `--url` (usando `SOURCE_CONFIG['bde_series_api']['default_url']`):

```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.db \
  --source bde_series_api \
  --snapshot-date 2026-02-27 \
  --strict-network \
  --timeout 30
```

Resultado:
- `bde_series_api: 58/58 registros validos`
- `run_id=281`, `status=ok`, `records_seen=58`, `records_loaded=58`

Evidencia:
- `docs/etl/sprints/AI-OPS-238/evidence/bde_series_ingest_default_multi58_strict_latest.json`
- `docs/etl/sprints/AI-OPS-238/evidence/bde_series_ingestion_runs_default_multi58_latest.txt`
