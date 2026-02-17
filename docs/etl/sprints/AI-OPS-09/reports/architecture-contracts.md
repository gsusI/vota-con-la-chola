# AI-OPS-09 Architecture Contracts

Date: 2026-02-17

## Objective

Define additive schema and source-contract foundations for the five new source families so downstream L1 execution is deterministic and auditable.

## Source ID Contract (Frozen)

The following `source_id` values are now explicit contract keys in `etl/politicos_es/config.py` and tracker mapping logic.

| Family | Slice | source_id |
|---|---|---|
| PLACSP | Espana (sindicacion/ATOM) | `placsp_sindicacion` |
| PLACSP | Piloto CCAA | `placsp_autonomico` |
| BDNS/SNPSAP | Espana (API) | `bdns_api_subvenciones` |
| BDNS/SNPSAP | Piloto CCAA | `bdns_autonomico` |
| Eurostat | Outcomes | `eurostat_sdmx` |
| Banco de Espana | Confusores | `bde_series_api` |
| AEMET | Confusores | `aemet_opendata_series` |

Notes:
- All new source configs include deterministic `fallback_file` paths.
- All new source configs include `min_records_loaded_strict` thresholds for `--strict-network` guardrails.

## Additive Schema Contract

Updated `etl/load/sqlite_schema.sql` with additive-only structures (no drop/replace):

1. `money_contract_records`
- Purpose: normalized staging for PLACSP rows before mapping to `policy_events`.
- Contract guard: `CHECK (source_id LIKE 'placsp_%')`.
- Traceability: `source_id`, `source_record_pk`, `source_record_id`, `source_snapshot_date`, `source_url`, `raw_payload`.
- Idempotence key: `UNIQUE (source_id, source_record_pk)`.

2. `money_subsidy_records`
- Purpose: normalized staging for BDNS/SNPSAP rows before mapping to `policy_events`.
- Contract guard: `CHECK (source_id LIKE 'bdns_%')`.
- Traceability and idempotence mirrors contracting table.

3. `indicator_observation_records`
- Purpose: raw/staging traceability for outcomes/confusores before/alongside `indicator_series` + `indicator_points`.
- Contract guard: source limited to `eurostat_%`, `bde_%`, `aemet_%`.
- Fields include `series_code`, `point_date`, `dimensions_json`, `methodology_version`, and full provenance.
- Idempotence key: `UNIQUE (source_id, series_code, point_date, source_record_id)`.

4. Added query indexes
- `idx_money_contract_records_*`
- `idx_money_subsidy_records_*`
- `idx_indicator_observation_records_*`

These changes are additive and compatible with existing schema migration flow.

## Tracker-Hint Compatibility Contract

Updated `scripts/e2e_tracker_status.py` to map tracker rows deterministically:

- Tipo de dato -> source_id (explicit row contracts):
  - `Contratación autonómica (piloto 3 CCAA)` -> `placsp_autonomico`
  - `Contratacion publica (Espana)` -> `placsp_sindicacion`
  - `Subvenciones autonómicas (piloto 3 CCAA)` -> `bdns_autonomico`
  - `Subvenciones y ayudas (Espana)` -> `bdns_api_subvenciones`
  - `Indicadores (outcomes): Eurostat` -> `eurostat_sdmx`
  - `Indicadores (confusores): Banco de España` -> `bde_series_api`
  - `Indicadores (confusores): AEMET` -> `aemet_opendata_series`

- Fuentes objetivo fallback hints were also added for the same families.

Validation test added:
- `tests/test_e2e_tracker_status_tracker.py::test_parse_tracker_rows_maps_money_and_outcomes_rows_to_expected_source_ids`

## L1 Runbook Command Stubs (Deterministic)

Use these stubs as canonical commands for the next implementation wave.

1. Initialize/upgrade schema
```bash
python3 scripts/ingestar_politicos_es.py init-db --db etl/data/staging/politicos-es.db --schema etl/load/sqlite_schema.sql
```

2. Verify source registry contract seeded
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT source_id, scope, default_url FROM sources WHERE source_id IN ('placsp_sindicacion','placsp_autonomico','bdns_api_subvenciones','bdns_autonomico','eurostat_sdmx','bde_series_api','aemet_opendata_series') ORDER BY source_id;"
```

3. Verify additive tables exist
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('money_contract_records','money_subsidy_records','indicator_observation_records') ORDER BY name;"
```

4. Verify tracker mapping contract for target rows
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json
```

5. Strict gate probe (pre-implementation safety)
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --fail-on-mismatch --fail-on-done-zero-real
```

6. Future connector execution stubs (to be enabled when connectors land)
```bash
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source placsp_sindicacion --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bdns_api_subvenciones --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source eurostat_sdmx --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source bde_series_api --strict-network
python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.db --source aemet_opendata_series --strict-network
```

## Safety

No destructive schema operations were introduced (no table/column drops, no rewrites).
