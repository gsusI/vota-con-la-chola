# AI-OPS-247 - Expansión multilingüe de señal declarada en programas

## Objetivo
Reducir `unclear` y aumentar señal útil (`support`) en `programas_partidos` tras el gap detectado en AI-OPS-246 para textos `ca/eu/gl`.

## Cambios implementados
- `etl/parlamentario_es/declared_stance.py`
  - Ampliación de `_PROGRAMA_POLICY_SUPPORT_PATTERNS` con terminología multilingüe (acciones + dominios) usando `declared:regex_v3`.
  - Segunda iteración con stems de dominios (`habitatg*`, `ocupaci*`, `dependenc*`, etc.) para cubrir flexiones/plurales.
- `etl/parlamentario_es/pipeline.py`
  - Ampliación de `_PROGRAMA_POLICY_VERBS_NORM` para mejorar `policy_pair_hit` y ventanas de excerpt en textos no castellanos.
- Tests
  - `tests/test_parl_declared_stance.py`: casos `ca/gl` para `_infer_programa_policy_support_detail`.
  - `tests/test_parl_programas_partidos.py`: heurística/ventana con verbos multilingües.

## Ejecución reproducible (staging real)
- Baseline:
  - `python3 scripts/report_declared_source_status.py --db etl/data/staging/politicos-es.db --source-id programas_partidos`
  - `python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --include-declared --declared-source-ids programas_partidos --skip-vote-gate`
- Backfill (2 pasadas tras parche):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id programas_partidos`
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db etl/data/staging/politicos-es.db --source-id programas_partidos`
  - `python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db etl/data/staging/politicos-es.db`
- Tracker gate:
  - `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real`

## Delta principal (baseline -> post v2)
- `party_proxy_count`: `15 -> 15` (sin cambio)
- `topic_evidence_total`: `386 -> 386` (sin cambio)
- `topic_evidence_by_stance.support`: `43 -> 56` (`+13`)
- `topic_evidence_by_stance.unclear`: `343 -> 330` (`-13`)
- `declared_positions_total`: `42 -> 93` (`+51`)
- `review_pending`: `0 -> 0`
- Gate declarado: `passed=true`
- Tracker enforce: sin `mismatches`, sin `done_zero_real`

## Desglose de mejora por partido
- Mejora neta en `support`:
  - `Compromis`: `+6`
  - `FORO Asturias`: `+4`
  - `CUP`: `+3`
- Sin mejora en esta pasada: `BNG`, `EAJ-PNV`, `EH Bildu`, `UPN`, `PP`, `PSC`, `VOX`, `CCa`, `Izquierda Unida`, `EQUO`, `Ciudadanos`, `SUMAR`.

## Gap residual
La lane sigue `PARTIAL`: aún hay partidos con `0 support` y excerpts dominados por navegación/document listing o texto programático sin verbo-acción suficientemente explícito para la regla actual.

## Artefactos
- Evidencia:
  - `docs/etl/sprints/AI-OPS-247/evidence/programas_declared_status_baseline_20260228.json`
  - `docs/etl/sprints/AI-OPS-247/evidence/programas_declared_status_post_multilingual_v2_20260228.json`
  - `docs/etl/sprints/AI-OPS-247/evidence/quality_declared_programas_post_multilingual_v2_20260228.json`
  - `docs/etl/sprints/AI-OPS-247/evidence/backfill_declared_stance_programas_multilingual_v2_20260228.log`
  - `docs/etl/sprints/AI-OPS-247/evidence/tracker_status_post_multilingual_v2_enforce_20260228.log`
- Exports:
  - `docs/etl/sprints/AI-OPS-247/exports/programas_status_delta_pre_vs_post_multilingual_v2_20260228.csv`
  - `docs/etl/sprints/AI-OPS-247/exports/programas_party_support_delta_pre_vs_post_multilingual_v2_20260228.csv`
  - `docs/etl/sprints/AI-OPS-247/exports/programas_party_evidence_breakdown_post_multilingual_v2_20260228.csv`
  - `docs/etl/sprints/AI-OPS-247/exports/programas_support_examples_regex_v3_post_multilingual_v2_20260228.csv`
