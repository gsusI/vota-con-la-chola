# AI-OPS-126 — Heartbeat de frescura y drift para `release-latest` del Atlas

## Objetivo
Cerrar el pendiente de `Derechos/Atlas público` añadiendo una capa operativa reproducible que detecte, antes de publicar, dos riesgos críticos del `release-latest`:
- `stale snapshot` (release desactualizado)
- `drift de release` entre superficies públicas (`published`, GH Pages y HF)

## Cambios entregados
- Nuevo script `scripts/report_liberty_atlas_release_heartbeat.py`:
  - Construye heartbeat append-only en JSONL con fingerprint canónico de release por superficie.
  - Evalúa continuidad (`AI-OPS-125`) + paridad (`published_gh`, `published_hf`, `gh_hf`) + frescura por `snapshot_age_days`.
  - Soporta HF en layouts reales de dataset:
    - `latest.json` remoto para resolver `snapshot_date`
    - fallback en orden: `snapshots/<date>/.../release-latest.json` -> `snapshots/<date>/.../release-<date>.json` -> rutas `main/published/*`.
  - Permite tolerancia controlada de indisponibilidad HF (`--allow-hf-unavailable`) sin ocultar la señal (`warnings`, `hf_unavailable`).
- Nuevo script `scripts/report_liberty_atlas_release_heartbeat_window.py`:
  - Ventana strict `last N` sobre el heartbeat con umbrales explícitos:
    - `max_failed`
    - `max_degraded`
    - `max_stale_alerts`
    - `max_drift_alerts`
    - `max_hf_unavailable`
  - Checkea latest run para evitar degradaciones silenciosas (`latest_continuity_ok`, `latest_published_gh_parity_ok`, `latest_expected_snapshot_match_ok`).
- `justfile`:
  - Nuevas variables `LIBERTY_ATLAS_RELEASE_*` para heartbeat/window.
  - Nuevos lanes:
    - `just parl-report-liberty-atlas-release-heartbeat`
    - `just parl-check-liberty-atlas-release-heartbeat-window`
  - Integración en `just parl-liberty-restrictions-pipeline`.
  - Integración de tests en `just parl-test-liberty-restrictions`.
  - Ajuste importante: `snapshot_date` esperado pasa a ser opcional (`LIBERTY_ATLAS_RELEASE_EXPECTED_SNAPSHOT_DATE`) para evitar falsos rojos por default global no alineado al release.
- Tests nuevos:
  - `tests/test_report_liberty_atlas_release_heartbeat.py`
  - `tests/test_report_liberty_atlas_release_heartbeat_window.py`

## Ejecución
- Compilación scripts: PASS.
- Unit tests nuevos: PASS (`6` tests).
- Suite `Derechos` ampliada: PASS (`just parl-test-liberty-restrictions`).
- Corrida operativa final (`20260223T194348Z`):
  - `just parl-report-liberty-atlas-release-heartbeat`: `status=ok`
  - `just parl-check-liberty-atlas-release-heartbeat-window`: `status=ok`
  - Triple paridad OK (`published`/GH/HF), sin stale ni drift.
- Corrida E2E integrada (`20260223T194611Z`):
  - `SNAPSHOT_DATE=2026-02-23 just parl-liberty-restrictions-pipeline`: PASS.
  - Incluye lanes nuevos de heartbeat/window en secuencia real de pipeline con `status=ok` en ambos.

## Evidencia
- `docs/etl/sprints/AI-OPS-126/evidence/py_compile_liberty_atlas_release_heartbeat_20260223T194252Z.txt`
- `docs/etl/sprints/AI-OPS-126/evidence/unittest_liberty_atlas_release_heartbeat_20260223T194252Z.txt`
- `docs/etl/sprints/AI-OPS-126/evidence/just_parl_test_liberty_restrictions_20260223T194705Z.txt`
- `docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_20260223T194348Z.json`
- `docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_window_20260223T194348Z.json`
- `docs/etl/sprints/AI-OPS-126/evidence/just_parl_report_liberty_atlas_release_heartbeat_20260223T194348Z.txt`
- `docs/etl/sprints/AI-OPS-126/evidence/just_parl_check_liberty_atlas_release_heartbeat_window_20260223T194348Z.txt`
- `docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_pipeline_20260223T194611Z.json`
- `docs/etl/sprints/AI-OPS-126/evidence/liberty_atlas_release_heartbeat_window_pipeline_20260223T194611Z.json`
- `docs/etl/sprints/AI-OPS-126/evidence/just_parl_liberty_restrictions_pipeline_20260223T194611Z.txt`

## DoD
- Heartbeat append-only multi-superficie del `release-latest`: `OK`.
- Alerta strict de `stale/drift` pre-publicación: `OK`.
- Integración en pipeline + test lane `Derechos`: `OK`.
- Evidencia reproducible en sprint: `OK`.
