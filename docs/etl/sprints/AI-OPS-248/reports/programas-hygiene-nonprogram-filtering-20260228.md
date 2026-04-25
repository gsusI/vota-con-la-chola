# AI-OPS-248 - Higiene de manifiestos (ruido/no-programa)

## Objetivo
Reducir evidencia `unclear` inflada por URLs de navegación/listados no programáticos y endurecer curación reproducible de deeplinks.

## Cambios implementados
- `etl/parlamentario_es/pipeline.py`
  - Endurecido `_is_programmatic_program_doc`:
    - añade detección de ruido de navegación (`_PROGRAMA_TEXT_NAV_NOISE_HINTS_NORM`),
    - evita auto-aceptar por `url_program_hint` cuando el texto es claramente índice/listado,
    - mantiene paso para evidencia con señal real (`policy_pair_hit`, `policy_verb_density`).
- `scripts/build_programas_deeplink_manifest.py`
  - Scoring de curación mejorado:
    - verbos/terminología multilingüe (`es/ca/gl/eu`) para señal programática,
    - penalización de ruido (news/feed/nav/legal/transparencia/fiscalización),
    - heurística de recencia en URL (preferencia por docs más recientes; penalización legacy).
  - Resultado: recuración reproducible del manifest multi-ciclo.
- Tests
  - `tests/test_parl_programas_partidos.py`: caso de URL programática pero texto ruidoso (`url_program_but_noisy_listing`).
  - `tests/test_build_programas_deeplink_manifest.py`: ruido de navegación + preferencia recencia docs.
  - Suite focal ejecutada: `Ran 23 tests`, `OK`.

## Ejecución reproducible
- Curación deeplink:
  - `python3 scripts/build_programas_deeplink_manifest.py --input-manifest docs/etl/sprints/AI-OPS-242/exports/programas_manifest_union_multicycle_plus_pdf_20260228.csv --output-manifest docs/etl/sprints/AI-OPS-248/exports/programas_manifest_deeplink_hygiene_multicycle_20260228.csv --report-out docs/etl/sprints/AI-OPS-248/evidence/programas_deeplink_curation_report_hygiene_20260228.json --min-score 7 --max-probe-candidates 12 --timeout 20`
  - `python3 scripts/validate_programas_manifest.py --manifest docs/etl/sprints/AI-OPS-248/exports/programas_manifest_deeplink_hygiene_multicycle_20260228.csv --out docs/etl/sprints/AI-OPS-248/evidence/programas_manifest_deeplink_hygiene_validate_20260228.json`
- Ingest + recompute (staging, red real):
  - `python3 scripts/ingestar_parlamentario_es.py ingest --db etl/data/staging/politicos-es.db --source programas_partidos --from-file docs/etl/sprints/AI-OPS-248/exports/programas_manifest_deeplink_hygiene_multicycle_20260228.csv --snapshot-date 2026-02-28 --strict-network`
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id programas_partidos`
  - `python3 scripts/ingestar_parlamentario_es.py review-decision --db etl/data/staging/politicos-es.db --source-id programas_partidos --evidence-ids <pending_csv> --status ignored --recompute --as-of-date 2026-02-28`
- Gate tracker:
  - `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real`

## Delta principal (pre-hygiene -> post-hygiene + post-ignore)
- `party_proxy_count`: `15 -> 9` (`-6`)
- `topic_evidence_total`: `386 -> 292` (`-94`)
- `topic_evidence_by_stance.support`: `56 -> 88` (`+32`)
- `topic_evidence_by_stance.unclear`: `330 -> 204` (`-126`)
- `declared_positions_total`: `93 -> 127` (`+34`)
- `review_pending`: `0 -> 0` (tras cierre reproducible de `38` pendientes `no_signal`)
- Gate declarado: `passed=true`.

## Lectura operativa
- El slice cumple objetivo de higiene (menos ruido/no-programa y más señal útil neta),
  pero revela tradeoff de cobertura por partido (`party_proxy_count` baja a `9`).
- Partidos sin evidencia post-higiene: `CCa`, `EAJ-PNV`, `EH Bildu`, `Izquierda Unida`, `PSC`, `UPN`.

## Artefactos
- Reporte:
  - `docs/etl/sprints/AI-OPS-248/reports/programas-hygiene-nonprogram-filtering-20260228.md`
- Evidencia:
  - `docs/etl/sprints/AI-OPS-248/evidence/programas_deeplink_curation_report_hygiene_20260228.json`
  - `docs/etl/sprints/AI-OPS-248/evidence/programas_manifest_deeplink_hygiene_validate_20260228.json`
  - `docs/etl/sprints/AI-OPS-248/evidence/programas_declared_status_post_hygiene_post_ignore_20260228.json`
  - `docs/etl/sprints/AI-OPS-248/evidence/quality_declared_programas_post_hygiene_post_ignore_20260228.json`
  - `docs/etl/sprints/AI-OPS-248/evidence/programas_ingestion_runs_latest_20260228.csv`
  - `docs/etl/sprints/AI-OPS-248/evidence/tracker_status_post_hygiene_post_ignore_enforce_20260228.log`
- Exports:
  - `docs/etl/sprints/AI-OPS-248/exports/programas_manifest_deeplink_hygiene_multicycle_20260228.csv`
  - `docs/etl/sprints/AI-OPS-248/exports/programas_manifest_url_changes_vs_ai_ops_246_20260228.csv`
  - `docs/etl/sprints/AI-OPS-248/exports/programas_status_delta_pre_vs_post_hygiene_post_ignore_20260228.csv`
  - `docs/etl/sprints/AI-OPS-248/exports/programas_party_delta_pre_vs_post_hygiene_post_ignore_20260228.csv`
  - `docs/etl/sprints/AI-OPS-248/exports/programas_party_url_delta_pre_vs_post_hygiene_post_ignore_20260228.csv`
