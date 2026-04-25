# AI-OPS-287 - Captura dirigida BOE por cargo exacto (delegación)

## Objetivo
Reducir el backlog `pending` del lane de regulación delegada sin relajar el gate semántico de cargo (`role_alignment`).

## Cambios implementados
- `scripts/scrape_liberty_delegated_person_window_boe_candidates.py`
  - Nuevas variantes de query orientadas a cargo exacto (normalización de `Dirección General -> Director General`).
  - Expansión institucional integrada en el propio título de cargo (p. ej. `AEAT` -> `Agencia Estatal de Administración Tributaria`).
  - Variantes quoted y fallbacks conservadores para mantener reproducibilidad.
- `scripts/export_liberty_delegated_person_window_auto_review_decisions.py`
  - Fix conservador en alineación semántica `ITSS`: cuando un candidato cumple patrón explícito de dirección (`Inspección de Trabajo` + `director/dirección`) y no cae en jerarquía `subdirector`, la evaluación pasa a `itss_direction_matched` (evita falso negativo en `role_alignment_insufficient`).
- `tests/test_scrape_liberty_delegated_person_window_boe_candidates.py`
  - Cobertura de variantes de query para `DGT` y `AEAT` con cargo exacto.
- `tests/test_export_liberty_delegated_person_window_auto_review_decisions.py`
  - Cobertura de regresión para caso `ITSS` con candidato `Director general de Inspección de Trabajo y Seguridad Social`.

## Comandos ejecutados
```bash
PYTHONPATH=. python3 scripts/scrape_liberty_delegated_person_window_boe_candidates.py \
  --targets-csv docs/etl/sprints/AI-OPS-279/exports/liberty_delegated_person_window_scrape_targets_latest.csv \
  --top-results-per-target 25 \
  --out docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_boe_candidates_targeted_latest.csv \
  --summary-out docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_boe_candidates_targeted_latest.json

PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_review_assist_from_boe_candidates.py \
  --review-queue-csv docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv \
  --boe-candidates-csv docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_boe_candidates_targeted_latest.csv \
  --min-candidate-score 20 \
  --max-candidates-per-link 12 \
  --out docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_review_assist_targeted_latest.csv \
  --summary-out docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_review_assist_targeted_latest.json

PYTHONPATH=. python3 scripts/export_liberty_delegated_person_window_auto_review_decisions.py \
  --review-queue-csv docs/etl/sprints/AI-OPS-278/exports/liberty_delegated_person_window_review_queue_latest.csv \
  --review-assist-csv docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_review_assist_targeted_latest.csv \
  --min-candidate-score 25 \
  --max-candidates-per-link 12 \
  --out docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_auto_review_decisions_targeted_latest.csv \
  --summary-out docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_auto_review_decisions_targeted_latest.json

PYTHONPATH=. python3 scripts/export_liberty_delegated_pending_resolution_review_queue.py \
  --auto-review-csv docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_auto_review_decisions_targeted_latest.csv \
  --review-assist-csv docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_person_window_review_assist_targeted_latest.csv \
  --top-candidates-per-link 5 \
  --out docs/etl/sprints/AI-OPS-287/exports/liberty_delegated_pending_resolution_review_queue_targeted_latest.csv \
  --summary-out docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_pending_resolution_review_queue_targeted_latest.json
```

## Resultado
- Scrape dirigido:
  - `candidate_rows_total=163`
  - `candidate_unique_boe_ids_total=136`
  - `http_errors_total=0`
- Assist:
  - `assist_rows_total=85`
  - `review_links_with_candidates_total=8/8`
- Auto-review role-aligned (tras fix ITSS):
  - baseline (AI-OPS-285): `approved=2`, `pending=6`
  - targeted (AI-OPS-287): `approved=5`, `pending=3`
  - delta: `approved +3`, `pending -3`

Aprobaciones nuevas destrabadas por evidencia BOE de cargo exacto:
- `BOE-A-2004-7862` (AEAT, dirección general)
- `BOE-A-1996-12484` (DGT, dirección general)
- `BOE-A-1984-27292` (ITSS, dirección general)

## Gap residual
Persisten `3` casos `pending` con bloqueos semánticos:
- `procedural_unit_not_found`
- `role_alignment_insufficient`
- `role_topic_overlap_zero`

Estos casos requieren captura alternativa oficial fuera del buscador BOE (portales institucionales/nombramientos o fuentes oficiales equivalentes) para no degradar precisión.

## Evidencia
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_boe_candidates_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_review_assist_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_person_window_auto_review_decisions_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_pending_resolution_review_queue_targeted_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_targeted_capture_delta_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/liberty_delegated_targeted_capture_resolution_latest.json`
- `docs/etl/sprints/AI-OPS-287/evidence/unittest_liberty_delegated_targeted_queries_latest.txt`
