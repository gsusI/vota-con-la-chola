# AI-OPS-254 - Mejora semantica focal para baja relacion senal/ruido en `programas_partidos`

## Objetivo del slice
Reducir `unclear` y aumentar `support` en el residual de baja senal (`BNG`, `PP`, `VOX`) sin perder cobertura, sin abrir deuda de review y manteniendo gates en verde.

## Cambio implementado
Se amplio la heuristica de `programa_policy_proposal` en `etl/parlamentario_es/declared_stance.py` con nuevas familias de patrones:
- Acciones adicionales ES/GL/CA (`propora`, `frear/frenar`, `limitar`, `deflactar`, `incrementar`, `modificar`, `facilitar`, etc.).
- Cobertura en ingles para manifiestos UE (`we will invest/create/focus/...`).
- Terminos de concern ampliados (`vivend*`, `saude/sanidade`, `agua/hidric*`, `housing`, `education`, `employment`, `security`, `migration`, `taxes`, `agriculture`, `industry`, etc.).

Se anadieron regresiones en `tests/test_parl_declared_stance.py` para:
- Frase programatica en ingles.
- Frase gallega tipo BNG (`propora` + `sanidade`).
- Frase de politica hidrica (`plan nacional del agua`).

## Validacion de codigo
- `python3 -m unittest tests/test_parl_declared_stance.py` -> `OK`.
- `python3 -m unittest tests/test_parl_programas_partidos.py` -> `OK`.

## Ejecucion en DB real (staging)
1. `backfill-declared-stance --source-id programas_partidos`
2. `backfill-declared-positions --source-id programas_partidos --as-of-date 2026-02-28`
3. `backfill-combined-positions --as-of-date 2026-02-28`
4. `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate`
5. `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`

## Resultado (pre -> post)
Global `programas_partidos`:
- `topic_evidence_support`: `244 -> 302` (`+58`)
- `topic_evidence_unclear`: `320 -> 262` (`-58`)
- `declared_positions_total`: `280 -> 327` (`+47`)
- `party_proxy_count`: `15 -> 15` (sin perdida de cobertura)
- `review_pending`: `0 -> 0`
- gate declarado: `passed=true`
- tracker enforce: `mismatches=0`, `done_zero_real=0`

Target residual (`BNG`, `PP`, `VOX`):
- `BNG`: `support 1 -> 7`, `unclear 47 -> 41`, ratio `0.0208 -> 0.1458`
- `PP`: `support 3 -> 23`, `unclear 53 -> 33`, ratio `0.0536 -> 0.4107`
- `VOX`: `support 3 -> 9`, `unclear 30 -> 24`, ratio `0.0909 -> 0.2727`

## Residual abierto
La deuda de baja relacion senal/ruido se reduce de forma material pero no se cierra:
- `BNG` sigue siendo el principal outlier (`7/48` support).
- `VOX` mejora, pero mantiene predominio de `unclear` (`9/33` support).

Siguiente palanca propuesta:
- Curacion por documento para `BNG` (especialmente `23_bng_xerais_programa.pdf`, actualmente `0/12` support).
- Segunda iteracion semantica en frases nominales y de compromiso de accion para `VOX`.

## Evidencia
- Estado declarado pre/post:
  - `docs/etl/sprints/AI-OPS-254/evidence/programas_declared_status_pre_regex_upgrade_20260228.json`
  - `docs/etl/sprints/AI-OPS-254/evidence/programas_declared_status_post_regex_upgrade_20260228.json`
- Calidad y tracker:
  - `docs/etl/sprints/AI-OPS-254/evidence/quality_declared_programas_post_regex_upgrade_20260228.json`
  - `docs/etl/sprints/AI-OPS-254/evidence/tracker_status_post_regex_upgrade_enforce_20260228.log`
- Deltas y auditorias:
  - `docs/etl/sprints/AI-OPS-254/exports/programas_party_evidence_breakdown_pre_regex_upgrade_20260228.csv`
  - `docs/etl/sprints/AI-OPS-254/exports/programas_party_evidence_breakdown_post_regex_upgrade_20260228.csv`
  - `docs/etl/sprints/AI-OPS-254/exports/programas_party_evidence_delta_pre_vs_post_regex_upgrade_20260228.csv`
  - `docs/etl/sprints/AI-OPS-254/exports/programas_low_signal_ratio_target_delta_pre_vs_post_regex_upgrade_20260228.csv`
  - `docs/etl/sprints/AI-OPS-254/exports/programas_low_signal_ratio_url_audit_post_regex_upgrade_20260228.csv`
  - `docs/etl/sprints/AI-OPS-254/exports/programas_bng_vox_unclear_excerpt_audit_20260228.csv`
