# AI-OPS-229 - Alineación de scope KPI cola Senado (quality-report vs queue operativa)

Fecha: 2026-02-27

## Objetivo
Eliminar drift de scope entre:
- Gate/KPI de `quality-report` (antes implícitamente global)
- Cola operativa usada para drenaje (`linked_to_votes`)

## Cambios implementados
- `etl/parlamentario_es/quality.py`
  - `compute_initiative_quality_kpis(..., actionable_scope=...)` ahora soporta scope explícito.
  - Se calculan y publican KPIs duales:
    - Global (`...actionable...` existente)
    - Linkeado a votos (`..._linked_to_votes`)
  - Se expone selección activa:
    - `actionable_scope`
    - `actionable_metric`
    - `missing_doc_links_actionable_selected`
    - `actionable_doc_links_closed_pct_selected`
  - `evaluate_initiative_quality_gate(..., actionable_metric=...)` permite gatear por métrica de scope activo.
- `etl/parlamentario_es/cli.py`
  - Nuevo flag: `--initiative-actionable-scope {global,linked_to_votes}`.
  - `quality-report --include-initiatives` pasa ese scope a KPIs y gate.
- `justfile`
  - Nuevo env var: `INITIATIVE_QUALITY_ACTIONABLE_SCOPE` (default `global`).
  - Recipes de quality con iniciativas ahora propagan `--initiative-actionable-scope`.

## Validación
- Unit tests:
  - `python3 -m unittest tests/test_parl_quality.py tests/test_cli_quality_report.py tests/test_export_missing_initiative_doc_urls.py`
  - Resultado: `Ran 31 tests`, `OK`.

## Resultado en DB real (`etl/data/staging/politicos-es.db`)
- Scope global:
  - `missing_doc_links_actionable=4456`
  - `actionable_doc_links_closed_pct=0.4897`
- Scope `linked_to_votes`:
  - `missing_doc_links_actionable_selected=680`
  - `actionable_doc_links_closed_pct_selected=0.6726`
- Paridad con export operativo:
  - `senado_missing_actionable_linked_latest.csv`: `680` filas (`345` iniciativas)
  - `senado_zero_doc_actionable_queue_latest.csv`: `25` iniciativas críticas (`403=24`, `404=1`)

## Evidencia
- `docs/etl/sprints/AI-OPS-229/evidence/quality_initiatives_scope_global_latest.json`
- `docs/etl/sprints/AI-OPS-229/evidence/quality_initiatives_scope_linked_latest.json`
- `docs/etl/sprints/AI-OPS-229/evidence/quality_initiatives_scope_compare_latest.json`
- `docs/etl/sprints/AI-OPS-229/evidence/quality_initiatives_scope_linked_enforce_latest.json`
- `docs/etl/sprints/AI-OPS-229/evidence/quality_initiatives_scope_linked_enforce_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-229/exports/senado_missing_actionable_linked_latest.csv`
- `docs/etl/sprints/AI-OPS-229/exports/senado_zero_doc_actionable_queue_latest.csv`

## Conclusión operativa
El contrato de scope queda explícito y reproducible. El gate puede evaluar exactamente el mismo scope que la cola operativa (`linked_to_votes`), evitando drift metodológico.
