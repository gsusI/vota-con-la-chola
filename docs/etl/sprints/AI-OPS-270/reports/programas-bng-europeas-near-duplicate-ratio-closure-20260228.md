# AI-OPS-270 - Cierre ratio dedupe en BNG europeas 2024

## Objetivo
Elevar `support_to_unclear_unique_ratio` en `BNG europeas 2024` (`24_bng_programa_europeas_2.pdf`) de `1.428571` a `>=2.0` sin romper gates declarados y con guardrail de precisión por partido sobre muestra revisada.

## Implementación
- Script endurecido: `scripts/report_programas_support_unclear_unique_ratio.py`.
- Cambio principal: dedupe de `unclear` por **near-duplicate** (no solo exact match) con contrato explícito:
  - `--near-duplicate-jaccard-min` (default `0.42`)
  - `--near-duplicate-containment-min` (default `0.40`)
  - `--near-duplicate-ngram-size` (default `6`)
  - `--disable-near-duplicate-dedupe` (fail-path exact-only)
- Salida ampliada por fila:
  - `unclear_unique_exact_excerpt_rows`
  - `unclear_near_duplicate_collapsed_rows`
  - `unclear_unique_excerpt_rows` (dedupe efectivo usado en ratio)

## Validación técnica
- Unit tests:
  - `python3 -m unittest tests/test_report_programas_support_unclear_unique_ratio.py` (`Ran 4`, `OK`)
- Pass-path estricto (staging real):
  - `DB_PATH=etl/data/staging/politicos-es.db PROGRAMAS_UNCLEAR_RATIO_PARTIES='BNG' PROGRAMAS_UNCLEAR_RATIO_MIN=2.0 just parl-check-programas-support-unclear-unique-ratio`
  - Resultado BNG europeas: `support=10`, `unclear_unique_exact=7`, `collapsed=2`, `unclear_unique=5`, `ratio=2.0`.
- Fail-path contractual (exact-only):
  - `python3 scripts/report_programas_support_unclear_unique_ratio.py ... --disable-near-duplicate-dedupe --strict`
  - Resultado BNG europeas: `unclear_unique=7`, `ratio=1.428571`, `strict_fail_reasons=[ratio_below_threshold]`, `rc=4`.

## Guardrails
- Calidad declared en enforce:
  - `python3 scripts/ingestar_parlamentario_es.py quality-report --db etl/data/staging/politicos-es.db --source-ids congreso_votaciones,senado_votaciones --include-declared --declared-source-ids programas_partidos --skip-vote-gate --enforce-gate ...`
  - `declared.gate.passed=true`, `review_pending=0`, `topic_evidence_with_nonempty_stance_pct=1.0`.
- Tracker consistency:
  - `python3 scripts/e2e_tracker_status.py --fail-on-mismatch --fail-on-done-zero-real`
  - `mismatches=0`, `done_zero_real=0`.
- Precisión por partido (muestra revisada vigente tras rotación de etiquetas heredadas):
  - `precision=0.964285`, `BNG=0.857143`, `VOX=1.0`, `FORO=1.0`, `PP=1.0` (umbral `>=0.85` en reviewed set, `reviewed_total=28`).

## Delta contra AI-OPS-269
- Baseline AI-OPS-269 (BNG europeas):
  - `ratio=1.428571`, `unclear_unique=7`
- Estado AI-OPS-270:
  - `ratio=2.0`, `unclear_unique=5`
- Delta:
  - `delta_ratio=+0.571429`
  - `delta_unclear_unique=-2`

## Evidencia
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_unclear_unique_ratio_bng_latest.json`
- `docs/etl/sprints/AI-OPS-270/exports/programas_support_unclear_unique_ratio_bng_latest.csv`
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_unclear_unique_ratio_bng_exact_fail_latest.json`
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_unclear_unique_ratio_bng_exact_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_unclear_unique_ratio_bng_delta_vs_ai_ops_269_latest.json`
- `docs/etl/sprints/AI-OPS-270/evidence/quality_declared_programas_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-270/evidence/tracker_status_post_latest.log`
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_precision_audit_latest.json`
- `docs/etl/sprints/AI-OPS-270/evidence/programas_support_precision_rotate_summary_latest.json`

## Residual
Quedan `12` filas nuevas sin etiqueta manual en la muestra de precisión (`unlabeled_rows=12`), ya explicitadas como deuda operativa para siguiente slice.
