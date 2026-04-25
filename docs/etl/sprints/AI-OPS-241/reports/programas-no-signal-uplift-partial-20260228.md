# AI-OPS-241 - Uplift parcial anti `no_signal` en `programas_partidos` (2026-02-28)

## Objetivo
Avanzar la lane editorial de señal útil en manifiestos web (fila tracker `Señal útil en manifiestos web (anti no_signal)`), manteniendo reproducibilidad y contrato de calidad.

## Trabajo ejecutado
- Probe reproducible de deep-links por partido:
  - salida: `docs/etl/sprints/AI-OPS-241/evidence/programas_deeplink_probe_20260228.json`
  - cobertura: `15` partidos
- Manifest curado (1 best-link por partido, ciclo `es_generales_2023`):
  - `docs/etl/sprints/AI-OPS-241/exports/programas_manifest_deeplink_generales_20260228.csv`
  - validación: `rows_total=15`, `rows_valid=15`, `valid=true`
- Hardening extractor de stance para programas:
  - `etl/parlamentario_es/declared_stance.py`
  - fallback source-specific `programa_policy_proposal` (confidence `0.62`) cuando `regex_v3` no detecta señal explícita.
- Mejora de excerpt topic-scoped:
  - `etl/parlamentario_es/pipeline.py`
  - nueva selección `_programa_keyword_excerpt_window()` que prioriza co-ocurrencia `verbo_propuesta + concern_keyword` antes del fallback por keyword pura.
- Tests añadidos y verdes:
  - `tests/test_parl_declared_stance.py`
  - `tests/test_parl_programas_partidos.py`
  - ejecución: `Ran 11 tests`, `OK`.

## KPI delta (baseline AI-OPS-240 -> post windowfix)
Fuente: `docs/etl/sprints/AI-OPS-241/exports/programas_status_delta_baseline_vs_windowfix_20260228.csv`

- `topic_evidence_support`: `0 -> 2` (`+2`)
- `topic_evidence_by_stance`: `{unclear:204} -> {support:2, unclear:202}`
- `declared_positions_total`: `3 -> 5` (`+2`)
- `declared_positions_by_stance.support`: `2 -> 4` (`+2`)
- `review_rows_resolved` en backfill: `2`
- residual: `review_pending=8` (`no_signal`) en cola focalizada

## Estado de gate
- `quality-report --include-declared --skip-vote-gate --enforce-gate`: `passed=true`
- `review_closed_pct=0.960784...`

## Gap residual
- Persisten casos `no_signal` ligados a páginas no programáticas y PDFs con texto pobre en hot path.
- Se abre TODO específico: parsing PDF reutilizable para `programas_partidos`.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-241/evidence/programas_manifest_deeplink_validate_20260228.json`
- `docs/etl/sprints/AI-OPS-241/evidence/programas_declared_status_baseline_20260228.json`
- `docs/etl/sprints/AI-OPS-241/evidence/programas_declared_status_post_windowfix_20260228.json`
- `docs/etl/sprints/AI-OPS-241/evidence/programas_backfill_declared_stance_post_windowfix_20260228.stdout`
- `docs/etl/sprints/AI-OPS-241/evidence/programas_backfill_declared_positions_post_windowfix_20260228.stdout`
- `docs/etl/sprints/AI-OPS-241/evidence/quality_declared_programas_post_windowfix_enforce_20260228.json`
- `docs/etl/sprints/AI-OPS-241/evidence/tracker_status_post_windowfix_20260228.log`
- `docs/etl/sprints/AI-OPS-241/evidence/unittest_declared_programas_ai_ops_241_20260228.txt`
