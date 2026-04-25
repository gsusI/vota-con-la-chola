# AI-OPS-297 - Cierre de señal multilingüe y higiene residual en `programas_partidos` (2026-02-28)

## Objetivo
Cerrar las filas pendientes del tracker en el bloque editorial:
- `Señal semántica multilingüe en programas (ca/eu/gl)`
- `Higiene residual de manifiestos (ruido/no-programa)`

con criterio reproducible sobre datos reales en `etl/data/staging/politicos-es.db`.

## Comandos ejecutados
- `python3 scripts/report_programas_support_unclear_unique_ratio.py --db etl/data/staging/politicos-es.db --parties BNG,VOX --min-support-unclear-unique-ratio 2.0 --out docs/etl/sprints/AI-OPS-297/evidence/programas_support_unclear_unique_ratio_latest.json --csv-out docs/etl/sprints/AI-OPS-297/exports/programas_support_unclear_unique_ratio_latest.csv --strict`
- `python3 scripts/report_programas_unclear_tail_dedupe.py --db etl/data/staging/politicos-es.db --parties BNG,VOX --max-duplicate-share 0.60 --out docs/etl/sprints/AI-OPS-297/evidence/programas_unclear_tail_dedupe_report_latest.json --queue-out docs/etl/sprints/AI-OPS-297/exports/programas_unclear_tail_deduped_queue_latest.csv --profile-out docs/etl/sprints/AI-OPS-297/exports/programas_unclear_tail_duplicate_profile_latest.csv --strict`
- `python3 scripts/report_declared_source_status.py --db etl/data/staging/politicos-es.db --source-id programas_partidos --out docs/etl/sprints/AI-OPS-297/evidence/programas_declared_status_latest.json`
- `python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate --json-out docs/etl/sprints/AI-OPS-297/evidence/quality_declared_programas_latest.json`
- `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json`

## Resultado
- Gate de ratio dedupe (`support_to_unclear_unique_ratio >= 2.0`) en verde:
  - `BNG xerais 2023`: `3.0`
  - `BNG europeas 2024`: `2.0`
  - `VOX web 2025`: `3.6`
  - `below_threshold_rows=[]`, `status=ok`
- Gate de higiene de tail unclear en verde:
  - `raw_unclear_rows_total=32`
  - `unclear_unique_excerpt_rows_total=15`
  - `unclear_duplicate_rows_total=17`
  - `duplicate_share=0.53125 <= 0.60`
  - `status=ok`
- Estado declarado `programas_partidos`:
  - `review_pending=0`
  - `topic_evidence_by_stance={support:421, unclear:147}`
  - `party_proxy_count=16`
- Quality report declarado en verde:
  - `declared.gate.passed=true`
  - `topic_evidence_with_nonempty_stance_pct=1.0`
- Tracker checker en verde:
  - `mismatches=0`
  - `done_zero_real=0`

## Decisión
Se considera cerrado el residual operativo de ambas filas:
- la señal multilingüe útil queda bajo contrato con threshold explícito por documento objetivo;
- el ruido residual queda acotado y medido por dedupe, sin cola de revisión pendiente.
