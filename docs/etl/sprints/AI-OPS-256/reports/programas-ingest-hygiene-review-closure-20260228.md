# AI-OPS-256 - Higiene de ventanas + cierre de cola review en `programas_partidos`

## Objetivo del slice
Reducir ruido de extractos en `programas_partidos` (ventanas numericas/TOC sin accion politica), mantener trazabilidad reproducible y cerrar cualquier reapertura de review queue sin romper cobertura.

## Cambios implementados
Se extendio la higiene de ventanas en `etl/parlamentario_es/pipeline.py`:
- ampliacion de `_PROGRAMA_POLICY_VERBS_NORM` para alinearlo con la semantica de stance declarada;
- nuevo filtro `_is_low_signal_programa_window` para descartar bloques con alto ruido numerico/indice;
- uso de `_programa_window_verb_hits` en seleccion de ventanas para privilegiar texto accionable.

Se anadieron regresiones en `tests/test_parl_programas_partidos.py`:
- descartar ventanas dominadas por ruido numerico;
- conservar ventanas con accion politica aunque contengan numeros.

## Validacion de codigo
- `python3 -m unittest tests/test_parl_programas_partidos.py` -> `OK`.
- `python3 -m unittest tests/test_parl_declared_stance.py` -> `OK`.

## Ejecucion en DB real (staging)
- `review-decision --status ignored --evidence-ids 1561082,1560982,1560933 --recompute --as-of-date 2026-02-28`
- `report_declared_source_status --source-id programas_partidos`
- `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate`
- `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`

## Resultado principal (AI-OPS-255 -> AI-OPS-256)
Global (`programas_partidos`):
- `support`: `338 -> 355` (`+17`)
- `unclear`: `226 -> 209` (`-17`)
- `declared_positions_total`: `360 -> 376` (`+16`)
- `review_pending`: `0 -> 0` (cola cerrada; `review_ignored=343`)
- `party_proxy_count`: `15 -> 15`
- gate declarado: `passed=true`
- tracker enforce: `mismatches=0`, `done_zero_real=0`

Detalle residual (`BNG/VOX/FORO`):
- `BNG`: `18/48 -> 20/48` (`+2 support`)
- `VOX`: `12/33 -> 16/33` (`+4 support`)
- `FORO Asturias`: `36/48 -> 33/48` (`-3 support`, `+3 unclear`) tras higiene estricta; cola review cerrada con 3 `no_signal` ignorados para evitar deuda operativa abierta.

Detalle por URL (`BNG/VOX`):
- `24_bng_galegas_programa_goberno.pdf`: `6/12 -> 8/12`
- `24_bng_programa_europeas_2.pdf`: `4/24 -> 4/24` (sin mejora)
- `VOX Programa-WEB-021025.pdf`: `12/33 -> 16/33`

## Gap abierto y siguiente slice
Lane `BNG/VOX` sigue `PARTIAL` por deuda documental en:
- `BNG` europeas (`4/24` sostenido)
- bloques narrativos de `VOX` aun `unclear` (`17/33`)

Nuevo gap explicitado (item nuevo en tracker):
- deriva de `FORO Asturias` tras higiene (`33/48`) para evitar que mejoras globales oculten degradacion local.

Siguiente palanca recomendada:
- regla puntual de semantica para narrativa social/economica de `FORO` y `BNG` europeas, con guardas anti-falso-positivo y auditoria por URL.

## Evidencia
- Reporte principal:
  - `docs/etl/sprints/AI-OPS-256/reports/programas-ingest-hygiene-review-closure-20260228.md`
- Estado/calidad/tracker:
  - `docs/etl/sprints/AI-OPS-256/evidence/programas_declared_status_post_review_close_20260228.json`
  - `docs/etl/sprints/AI-OPS-256/evidence/programas_review_queue_pending_post_review_close_20260228.json`
  - `docs/etl/sprints/AI-OPS-256/evidence/quality_declared_programas_post_review_close_20260228.json`
  - `docs/etl/sprints/AI-OPS-256/evidence/tracker_status_post_review_close_enforce_20260228.log`
  - `docs/etl/sprints/AI-OPS-256/evidence/tracker_status_post_tracker_update_enforce_20260228.log`
- Decisiones review:
  - `docs/etl/sprints/AI-OPS-256/evidence/programas_review_decision_ignore_no_signal_foro_asturias_20260228.json`
- Deltas y auditorias:
  - `docs/etl/sprints/AI-OPS-256/exports/programas_party_evidence_delta_ai_ops_255_vs_ai_ops_256_post_review_close_20260228.csv`
  - `docs/etl/sprints/AI-OPS-256/exports/programas_bng_vox_url_delta_ai_ops_255_vs_ai_ops_256_post_review_close_20260228.csv`
  - `docs/etl/sprints/AI-OPS-256/exports/programas_bng_vox_foro_unclear_excerpt_audit_post_review_close_20260228.csv`
  - `docs/etl/sprints/AI-OPS-256/exports/programas_foro_unclear_excerpt_audit_post_review_close_20260228.csv`
- Tests:
  - `docs/etl/sprints/AI-OPS-256/evidence/unittest_parl_programas_partidos_20260228.txt`
  - `docs/etl/sprints/AI-OPS-256/evidence/unittest_parl_declared_stance_20260228.txt`
