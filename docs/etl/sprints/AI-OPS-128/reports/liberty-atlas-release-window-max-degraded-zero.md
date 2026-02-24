# AI-OPS-128 — Liberty Atlas release window strict `max_degraded=0`

Fecha: 2026-02-23 (UTC)

## Objetivo
Cerrar el pending técnico de `Derechos/Atlas público` endureciendo la ventana strict del heartbeat de release para no tolerar degradaciones (`max_degraded=0`) por defecto.

## Cambio aplicado
- `justfile`: `LIBERTY_ATLAS_RELEASE_WINDOW_MAX_DEGRADED` pasa de `20` a `0`.

## Ejecución reproducible
```bash
python3 -m unittest tests/test_report_liberty_atlas_release_heartbeat.py tests/test_report_liberty_atlas_release_heartbeat_window.py

SNAPSHOT_DATE=2026-02-23 \
LIBERTY_ATLAS_RELEASE_HEARTBEAT_OUT=docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_20260223T202426Z.json \
just parl-report-liberty-atlas-release-heartbeat

SNAPSHOT_DATE=2026-02-23 \
LIBERTY_ATLAS_RELEASE_HEARTBEAT_WINDOW_OUT=docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_window_20260223T202426Z.json \
just parl-check-liberty-atlas-release-heartbeat-window

SNAPSHOT_DATE=2026-02-23 \
LIBERTY_ATLAS_RELEASE_HEARTBEAT_OUT=docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_pipeline_20260223T202426Z.json \
LIBERTY_ATLAS_RELEASE_HEARTBEAT_WINDOW_OUT=docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_window_pipeline_20260223T202426Z.json \
just parl-liberty-restrictions-pipeline
```

## Resultado
- Heartbeat (`manual`): `status=ok`.
- Window strict (`manual`): `status=ok`, `entries_in_window=20`, `failed_in_window=0`, `degraded_in_window=0`, `stale_alerts_in_window=0`, `drift_alerts_in_window=0`, `hf_unavailable_in_window=0`.
- Pipeline completo (`Derechos`): `status=ok` y window strict también `status=ok` con `degraded_in_window=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-128/evidence/unittest_liberty_atlas_release_heartbeat_20260223T202426Z.txt`
- `docs/etl/sprints/AI-OPS-128/evidence/just_parl_report_liberty_atlas_release_heartbeat_20260223T202426Z.txt`
- `docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_20260223T202426Z.json`
- `docs/etl/sprints/AI-OPS-128/evidence/just_parl_check_liberty_atlas_release_heartbeat_window_20260223T202426Z.txt`
- `docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_window_20260223T202426Z.json`
- `docs/etl/sprints/AI-OPS-128/evidence/just_parl_liberty_restrictions_pipeline_20260223T202426Z.txt`
- `docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_pipeline_20260223T202426Z.json`
- `docs/etl/sprints/AI-OPS-128/evidence/liberty_atlas_release_heartbeat_window_pipeline_20260223T202426Z.json`

## Estado
DONE: contrato strict de ventana endurecido a tolerancia cero de degradación por defecto, con validación reproducible en lane y pipeline.
