# AI-OPS-255 - Cierre parcial de curacion documental residual (`BNG`/`VOX`)

## Objetivo del slice
Avanzar el item `Curacion documental residual de manifiestos (BNG/VOX)` elevando la relacion `support/unclear` con cambios reproducibles en heuristica semantica, sin perder cobertura ni reabrir review queue.

## Cambios implementados
Se amplio `programa_policy_proposal` en `etl/parlamentario_es/declared_stance.py` con foco en frases detectadas en auditoria residual:
- Nuevos verbos/acciones: `impulsar`, `actualizar`, `revisar`, `dotar`, `prohibir`, `atajar`, `fomentar`, `reformular`, `establecer`, `desarrollar/desenvolver`, etc.
- Nuevo lenguaje nominal: `propuesta/proposta`, `plan(es) nacional(es)`, `introduccion/introducion`, `modernizacion`.
- Nuevos concerns: `fiscalidad/fiscalidade`, `irpf`, `tribut*`, `gravam*`, `inflacion*`, `violenc*`, `machist*`, `feminicid*`, `xener*`, `infraestrutur*`, `ferroviari*`, `viari*`, `pesca*`.

Se anadieron regresiones en `tests/test_parl_declared_stance.py` para:
- Frases BNG de vivienda/fiscalidad (`reformular`, `IRPF`, `gravame`, `feminicidio/violencia`).
- Frase VOX de vivienda/inmigracion (`prohibir` + `atajar`).
- Control negativo numérico (debe seguir `no_signal`).

## Validacion de codigo
- `python3 -m unittest tests/test_parl_declared_stance.py` -> `OK`.
- `python3 -m unittest tests/test_parl_programas_partidos.py` -> `OK`.

## Ejecucion en DB real (staging)
1. `backfill-declared-stance --source-id programas_partidos`
2. `backfill-declared-positions --source-id programas_partidos --as-of-date 2026-02-28`
3. `backfill-combined-positions --as-of-date 2026-02-28`
4. `quality-report --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate`
5. `e2e_tracker_status --fail-on-mismatch --fail-on-done-zero-real`

## Resultado principal
Global (`programas_partidos`, pre AI-OPS-255 -> post):
- `support`: `302 -> 338` (`+36`)
- `unclear`: `262 -> 226` (`-36`)
- `declared_positions_total`: `327 -> 360` (`+33`)
- `party_proxy_count`: `15 -> 15`
- `review_pending`: `0 -> 0`
- gate declarado: `passed=true`
- tracker enforce: `mismatches=0`, `done_zero_real=0`

Target residual:
- `BNG`: `7/48 -> 18/48` (ratio `0.1458 -> 0.3750`, `+11 support`)
- `VOX`: `9/33 -> 12/33` (ratio `0.2727 -> 0.3636`, `+3 support`)
- `PP`: `23/56 -> 24/56` (ratio `0.4107 -> 0.4286`, `+1 support`)

Detalle por URL (`BNG/VOX`):
- `23_bng_xerais_programa.pdf`: `0/12 -> 8/12`
- `24_bng_galegas_programa_goberno.pdf`: `3/12 -> 6/12`
- `24_bng_programa_europeas_2.pdf`: `4/24 -> 4/24` (sin mejora en este slice)
- `VOX Programa-WEB-021025.pdf`: `9/33 -> 12/33`

## Residual abierto
El gap baja de forma clara, pero queda deuda documental:
- `BNG` europeas (`24_bng_programa_europeas_2.pdf`) mantiene baja intensidad (`4/24`).
- `VOX` conserva bloques estadistico-narrativos de baja accion (`21 unclear`, 7 excerpts unicos post-slice).

Siguiente palanca recomendada:
- Filtro de higiene textual por bloque para `programa_pdf` (TOC/graficas/numerico) antes de inferencia, con validacion de no perdida de cobertura.

## Evidencia
- Estado declarado pre/post:
  - `docs/etl/sprints/AI-OPS-255/evidence/programas_declared_status_pre_bng_vox_slice_20260228.json`
  - `docs/etl/sprints/AI-OPS-255/evidence/programas_declared_status_post_bng_vox_slice_20260228.json`
- Backfills:
  - `docs/etl/sprints/AI-OPS-255/evidence/programas_backfill_declared_stance_post_bng_vox_slice_20260228.json`
  - `docs/etl/sprints/AI-OPS-255/evidence/programas_backfill_declared_positions_post_bng_vox_slice_20260228.json`
  - `docs/etl/sprints/AI-OPS-255/evidence/programas_backfill_combined_positions_post_bng_vox_slice_20260228.json`
- Gates:
  - `docs/etl/sprints/AI-OPS-255/evidence/quality_declared_programas_post_bng_vox_slice_20260228.json`
  - `docs/etl/sprints/AI-OPS-255/evidence/tracker_status_post_bng_vox_slice_enforce_20260228.log`
- Deltas/auditorias:
  - `docs/etl/sprints/AI-OPS-255/exports/programas_party_evidence_delta_pre_vs_post_bng_vox_slice_20260228.csv`
  - `docs/etl/sprints/AI-OPS-255/exports/programas_bng_pp_vox_delta_pre_vs_post_bng_vox_slice_20260228.csv`
  - `docs/etl/sprints/AI-OPS-255/exports/programas_bng_vox_url_delta_pre_vs_post_20260228.csv`
  - `docs/etl/sprints/AI-OPS-255/exports/programas_bng_vox_unclear_excerpt_audit_pre_20260228.csv`
  - `docs/etl/sprints/AI-OPS-255/exports/programas_bng_vox_unclear_excerpt_audit_post_20260228.csv`
