# AI-OPS-289 - Captura alternativa institucional para pendientes delegados

## Objetivo
Cerrar el gap residual de `2` filas `pending` en regulación delegada publicando un backlog reproducible de captura alternativa fuera del buscador BOE, con URLs directas y trazabilidad por `link_key`.

## Cambios implementados
- Nuevo script `scripts/export_liberty_delegated_alternative_capture_targets.py`:
  - Construye objetivos de captura alternativa desde `pending_resolution_review_queue`.
  - Genera tres grupos de targets:
    - `boe_redirector_query` (query primaria/secundaria).
    - `boe_direct_doc` (URLs `doc.php?id=BOE-...` desde `top_candidates_json`).
    - `institutional_site` (DGT/AEAT/ITSS/transparencia).
  - Añade metadata de candidato BOE (`candidate_boe_id`, `candidate_score`, `candidate_rank_for_link`) para priorización manual.
  - Gate estricto por densidad de targets (`--strict-min-targets-per-link`, `rc=4`).
- Wiring en `justfile`:
  - `parl-export-liberty-delegated-alternative-capture-targets`
  - `parl-check-liberty-delegated-alternative-capture-targets`
  - Variables `LIBERTY_DELEGATED_ALTERNATIVE_CAPTURE_*`.
- Cobertura de tests:
  - `tests/test_export_liberty_delegated_alternative_capture_targets.py`
  - Incluido en `parl-test-liberty-restrictions`.

## Resultado de corrida real (AI-OPS-289)
- Entrada: `docs/etl/sprints/AI-OPS-288/exports/liberty_delegated_pending_resolution_review_queue_targeted_latest.csv` (`pending_links_total=2`).
- Salida: `target_rows_total=22` para `2` links pendientes (`11` targets/link).
- Desglose:
  - `boe_direct_doc=6`
  - `boe_redirector_query=4`
  - `institutional_site=12`
- Gate:
  - Pass estricto: `--strict-min-targets-per-link 3` (`rc=0`).
  - Fail-path contractual validado: `--strict-min-targets-per-link 12` (`rc=4`).

## Gap residual y siguiente paso
- Este slice deja cerrada la preparación operativa de captura alternativa.
- Queda pendiente aplicar evidencia capturada sobre estos `22` targets para intentar convertir los `2` casos residuales de `pending` a `approved` sin degradar precisión.

## Evidencia
- `docs/etl/sprints/AI-OPS-289/evidence/liberty_delegated_alternative_capture_targets_latest.json`
- `docs/etl/sprints/AI-OPS-289/evidence/liberty_delegated_alternative_capture_targets_check_latest.json`
- `docs/etl/sprints/AI-OPS-289/evidence/liberty_delegated_alternative_capture_targets_fail_latest.json`
- `docs/etl/sprints/AI-OPS-289/evidence/liberty_delegated_alternative_capture_targets_fail_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-289/evidence/just_parl_export_liberty_delegated_alternative_capture_targets_latest.txt`
- `docs/etl/sprints/AI-OPS-289/evidence/just_parl_check_liberty_delegated_alternative_capture_targets_latest.txt`
- `docs/etl/sprints/AI-OPS-289/evidence/unittest_liberty_delegated_alternative_capture_targets_latest.txt`
- `docs/etl/sprints/AI-OPS-289/exports/liberty_delegated_alternative_capture_targets_latest.csv`
