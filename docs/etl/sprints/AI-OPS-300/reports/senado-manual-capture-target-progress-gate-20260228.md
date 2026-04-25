# AI-OPS-300: Gate de progreso de captura manual contra cola objetivo (Senado)

## Objetivo
Añadir un contrato reproducible de progreso para la captura manual: medir cuánto de la cola objetivo ya tiene captura asociada y, dentro de eso, cuántas capturas son realmente utilizables para desbloqueo (`usable_capture`).

## Cambios entregados
- Nuevo script: `scripts/report_senado_manual_capture_target_progress.py`.
- Nuevas recetas `just`:
  - `parl-report-senado-manual-capture-target-progress`
  - `parl-check-senado-manual-capture-target-progress`
- Cobertura de tests dedicada + regresión con lanes Senado relacionadas (`14 tests`, `OK`).

## Comandos ejecutados

```bash
just parl-report-senado-manual-capture-target-progress
just parl-check-senado-manual-capture-target-progress
```

## Resultado medible (corrida real)
- Progreso contra cola objetivo (`AI-OPS-299/exports/senado_manual_capture_targets_latest.csv`):
  - `targets_total=8`
  - `matched_targets_total=6`
  - `unmatched_targets_total=2`
  - `coverage_pct=0.75`
  - `usable_targets_total=0`
  - `usable_coverage_pct=0.0`
  - `access_denied_matched_targets_total=6`
- Strict check del gate: `rc=4` por `usable_targets_below_min`.

## Conclusión operativa
Se cierra una deuda estructural de seguimiento: ahora el estado de la captura manual se mide sobre una cola explícita de targets y no solo sobre glob de archivos. El bloqueo externo persiste (capturas asociadas pero no utilizables), pero el siguiente paso queda cuantificado por gap (`usable 0/8`).

## Artefactos
- `docs/etl/sprints/AI-OPS-300/evidence/senado_manual_capture_target_progress_latest.json`
- `docs/etl/sprints/AI-OPS-300/exports/senado_manual_capture_target_progress_latest.csv`
- `docs/etl/sprints/AI-OPS-300/evidence/just_parl_check_senado_manual_capture_target_progress_latest.txt`
- `docs/etl/sprints/AI-OPS-300/evidence/just_parl_check_senado_manual_capture_target_progress_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-300/evidence/unittest_senado_manual_capture_target_progress_lane_latest.txt`
