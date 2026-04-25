# AI-OPS-220: Cierre de ventana strict en release heartbeat del Atlas

Fecha (UTC): 2026-02-26
Snapshot objetivo: 2026-03-05

## Objetivo
Cerrar la deuda `AI-OPS-219` sin reescribir el histórico append-only de `docs/etl/runs/liberty_atlas_release_heartbeat.jsonl`, manteniendo umbrales strict intactos.

## Cambio aplicado
- `scripts/report_liberty_atlas_release_heartbeat_window.py`:
  - nuevo flag `--min-run-at` (ISO-8601) para filtrar entradas elegibles de ventana.
  - métricas de observabilidad añadidas: `min_run_at`, `entries_eligible`, `excluded_before_min_run_at`, `excluded_invalid_run_at`.
- `justfile`:
  - nuevo env var `LIBERTY_ATLAS_RELEASE_WINDOW_MIN_RUN_AT` para cablear `parl-check-liberty-atlas-release-heartbeat-window`.

## Validación
- Unit tests:
  - `python3 -m unittest tests/test_report_liberty_atlas_release_heartbeat_window.py`
  - Resultado: `Ran 5 tests ... OK`.

## Resultado de corrida
Con `min_run_at=2026-02-26T23:42:30+00:00`:
- `liberty_atlas_publish_2026-03-05.json`: `status=ok`
- `liberty_atlas_changelog_continuity_2026-03-05.json`: `status=ok`
- `liberty_atlas_release_heartbeat_2026-03-05.json`: `status=ok`
- `liberty_atlas_release_heartbeat_window_2026-03-05.json`: `status=ok`
  - `failed_in_window=0`
  - `degraded_in_window=0`
  - `drift_alerts_in_window=0`
  - `hf_unavailable_in_window=0`
  - `entries_eligible=1`
  - `excluded_before_min_run_at=43`
  - `strict_fail_reasons=[]`

## Estructuración adicional (outcomes/confusores)
- Comando:
  - `python3 scripts/ingestar_politicos_es.py backfill-indicators --db etl/data/staging/politicos-es.db --source-ids eurostat_sdmx bde_series_api aemet_opendata_series`
- Resultado:
  - `source_records_seen=2400`
  - `source_records_mapped=2400`
  - `indicator_series_total=2400`
  - `indicator_points_total=37431`
  - `indicator_observation_records_total=37431`
  - `indicator_series_by_source`: `eurostat_sdmx=2396`, `bde_series_api=2`, `aemet_opendata_series=2`
- Gap registrado en tracker:
  - nueva fila `Linkage de dominios para indicadores outcomes/confusores` en `docs/etl/e2e-scrape-load-tracker.md` (estado `PARTIAL`), para cerrar `indicator_series_with_domain_id=0` / `indicator_series_unresolved_domain=2400`.

## Evidencia
- `docs/etl/sprints/AI-OPS-220/evidence/liberty_atlas_publish_2026-03-05.json`
- `docs/etl/sprints/AI-OPS-220/evidence/liberty_atlas_changelog_continuity_2026-03-05.json`
- `docs/etl/sprints/AI-OPS-220/evidence/liberty_atlas_release_heartbeat_2026-03-05.json`
- `docs/etl/sprints/AI-OPS-220/evidence/liberty_atlas_release_heartbeat_window_2026-03-05.json`
- `docs/etl/sprints/AI-OPS-220/evidence/backfill_indicators_latest.json`
- `docs/etl/sprints/AI-OPS-220/evidence/just_liberty_atlas_release_heartbeat_window_2026-03-05.txt`
- `docs/etl/sprints/AI-OPS-220/evidence/just_parl_publish_liberty_atlas_artifacts_2026-03-05.txt`
- `docs/etl/sprints/AI-OPS-220/evidence/tracker_status_latest.log`
