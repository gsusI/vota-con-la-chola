# AI-OPS-228 - Senado: hardening de cola accionable "zero-doc"

Fecha: 2026-02-27

## Objetivo
Reducir ambigüedad operativa del tail Senado y priorizar la cola realmente crítica: iniciativas linkeadas a votos que siguen con `0` documentos descargados.

## Cambios implementados
- `scripts/export_missing_initiative_doc_urls.py`
  - Nuevo filtro `--only-linked-to-votes`.
  - Nuevo filtro `--only-initiatives-without-any-doc`.
  - Nuevo control `--max-urls-per-initiative`.
- `justfile`
  - `parl-export-missing-initdoc-urls-actionable` y `parl-check-missing-initdoc-urls-actionable-empty` ahora exportan cola linkeada a votos.
  - Nuevos atajos:
    - `parl-export-missing-initdoc-urls-actionable-zero-doc`
    - `parl-check-missing-initdoc-urls-actionable-zero-doc-empty`
- Tests:
  - `tests/test_export_missing_initiative_doc_urls.py` amplía cobertura para los 3 filtros nuevos.

## Ejecuciones y resultados
1. Retry acotado con cookie seed sobre cohort prioritario (25 iniciativas):
   - Comando: `backfill-initiative-documents --skip-link-backfill --retry-forbidden --cookie-file ... --limit-initiatives 25 --max-docs-per-initiative 2`
   - Resultado: `fetched_ok=0`, bloqueo dominante `HTTP 403`.
   - Evidencia: `docs/etl/sprints/AI-OPS-228/evidence/senado_zero_doc_cookie_probe_backfill_20260227T_latest.json`

2. Export cola accionable linkeada (scope operativo):
   - Resultado: `680` URLs accionables (`345` iniciativas).
   - Evidencia: `docs/etl/sprints/AI-OPS-228/evidence/senado_missing_actionable_linked_export_latest.txt`
   - CSV: `docs/etl/sprints/AI-OPS-228/exports/senado_missing_actionable_linked_latest.csv`

3. Export cola crítica zero-doc (1 URL por iniciativa):
   - Resultado: `25` filas / `25` iniciativas (todas `leg14`).
   - Buckets: `403=24`, `404=1`.
   - Evidencia: `docs/etl/sprints/AI-OPS-228/evidence/senado_zero_doc_actionable_queue_export_latest.txt`
   - Resumen: `docs/etl/sprints/AI-OPS-228/evidence/senado_zero_doc_queue_summary_latest.json`
   - CSV: `docs/etl/sprints/AI-OPS-228/exports/senado_zero_doc_actionable_queue_latest.csv`

## Gap nuevo identificado
Hay drift de scope entre métricas:
- `quality-report --include-initiatives` mantiene `missing_doc_links_actionable=4456` (scope global).
- Export operativo linkeado reporta `680` URLs.

Se abre item nuevo en tracker para unificar contrato de scope (`linked_to_votes` vs global) entre gate, runbook y CI.
