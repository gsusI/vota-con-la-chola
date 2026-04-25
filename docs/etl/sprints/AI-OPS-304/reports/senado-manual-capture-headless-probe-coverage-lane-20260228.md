# AI-OPS-304 — Senado manual capture headless probe coverage lane (2026-02-28)

## Objetivo
Avanzar la fila `829` con una palanca controlable bajo bloqueo WAF: reducir targets `unmatched` de la cola de captura sin depender de resolución manual del challenge.

## Estrategia
- Ejecutar captura Playwright **headless** únicamente para los 2 targets que seguían `unmatched`.
- Re-ejecutar el ciclo integrado (`AI-OPS-303`) sobre la DB principal para medir impacto en cobertura y cola.

## Ejecución
Comandos ejecutados:
- `python3 scripts/manual_capture_playwright.py --url '<target_02>' --label senado_cookie_refresh_ai_ops_304_02_leg10_tipo610_probe --out-dir etl/data/raw/manual --wait-seconds 8 --channel "" --headless`
- `python3 scripts/manual_capture_playwright.py --url '<target_08>' --label senado_cookie_refresh_ai_ops_304_08_leg14_tipo622_probe --out-dir etl/data/raw/manual --wait-seconds 8 --channel "" --headless`
- `just parl-run-senado-manual-capture-iteration-cycle` (outputs en `docs/etl/sprints/AI-OPS-304/**`)
- `just parl-check-senado-manual-capture-iteration-cycle` (`rc=4`, esperado)

## Resultado real
Delta de cobertura (baseline AI-OPS-301 -> AI-OPS-304):
- `matched_targets_total: 6 -> 8` (`+2`)
- `unmatched_targets_total: 2 -> 0` (`-2`)
- `coverage_pct: 0.75 -> 1.0` (`+0.25`)
- `capture_files_total: 2 -> 4` (`+2`)

Estado post-probe:
- `usable_targets_total=0`
- `pending_targets_total=8`
- composición de pendientes: `matched_access_denied=8` (sin `unmatched`)
- check estricto del ciclo: `rc=4`

## Conclusión
Slice completado con progreso visible y medible sobre datos bajo control del repo:
- Se cerró el gap estructural de cobertura (`unmatched -> 0`).
- El bloqueo externo persiste en usabilidad de captura (`Access Denied`, sin cookie de dominio usable), por lo que todavía no se habilita `backfill-initiative-documents`.

## Evidencia
- `docs/etl/sprints/AI-OPS-304/evidence/senado_manual_capture_headless_probe_summary_latest.json`
- `docs/etl/sprints/AI-OPS-304/evidence/senado_manual_capture_target_progress_latest.json`
- `docs/etl/sprints/AI-OPS-304/evidence/senado_manual_capture_target_progress_delta_latest.json`
- `docs/etl/sprints/AI-OPS-304/evidence/senado_manual_capture_pending_targets_latest.json`
- `docs/etl/sprints/AI-OPS-304/evidence/senado_manual_capture_iteration_cycle_latest.json`
- `docs/etl/sprints/AI-OPS-304/evidence/just_parl_run_senado_manual_capture_iteration_cycle_latest.txt`
- `docs/etl/sprints/AI-OPS-304/evidence/just_parl_check_senado_manual_capture_iteration_cycle_latest.txt`
- `docs/etl/sprints/AI-OPS-304/evidence/just_parl_check_senado_manual_capture_iteration_cycle_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-304/evidence/tracker_status_latest.log`
- `docs/etl/sprints/AI-OPS-304/exports/senado_manual_capture_target_progress_latest.csv`
- `docs/etl/sprints/AI-OPS-304/exports/senado_manual_capture_pending_targets_latest.csv`
- `docs/etl/sprints/AI-OPS-304/exports/senado_manual_capture_pending_targets_commands_latest.sh`

## Siguiente comando
`bash docs/etl/sprints/AI-OPS-304/exports/senado_manual_capture_pending_targets_commands_latest.sh && just parl-run-senado-manual-capture-iteration-cycle && just parl-check-senado-manual-capture-iteration-cycle`
