# AI-OPS-334 — Eficiencia de packet `status=404` (scope + prefilter)

## Objetivo
Reducir desperdicio en la lane `status=404` sin depender de nueva palanca externa, alineando el scope del packet con el scope efectivo de `backfill-initiative-documents`.

## Cambios entregados
- `etl/parlamentario_es/text_documents.py`
  - En scope seleccionado (`selected_doc_urls` / `selected_doc_entry_keys`), `max_docs_per_initiative` ya no recorta candidatos del packet.
  - Nuevo campo de trazabilidad en salida: `selected_scope_ignores_doc_cap`.
- `scripts/export_missing_initiative_doc_urls.py`
  - El prefiltro `--exclude-redundant-senado-global` ahora detecta redundancia con el mismo criterio operativo del backfill (`source_record_pk IS NOT NULL` + patrones de URL alterna), sin depender de join a `text_documents`.
- Tests de regresión:
  - `tests/test_parl_text_documents.py::test_backfill_initiative_documents_selected_doc_urls_ignore_max_docs_cap`
  - `tests/test_export_missing_initiative_doc_urls.py::test_only_actionable_missing_excludes_redundant_even_without_text_documents_row`

## Evidencia cuantitativa (DB principal)
Timestamp base: `20260301T011834Z` (guardado en `docs/etl/sprints/AI-OPS-334/evidence/.ts`).

### 1) Prefiltro en pool `status=404`
- pool raw linked-to-votes: `877`
- pool actionable (prefiltro redundante): `802`
- delta: `-75` filas redundantes

Fuente:
- `docs/etl/sprints/AI-OPS-334/evidence/senado_status404_pool_prefilter_delta_*.json`

### 2) Dry-run comparativo del mismo contrato de packet (sin tráfico de descarga)
Configuración: packet `80` filas, `--retry-http-statuses 599`, `--dry-run`.

- **raw packet**:
  - `selected_doc_urls_total=80`
  - `candidate_urls=24`
  - `selected_doc_urls_not_in_candidates=56`
  - `skipped_redundant_global_urls=79`
- **actionable prefilter packet**:
  - `selected_doc_urls_total=80`
  - `candidate_urls=80`
  - `selected_doc_urls_not_in_candidates=0`
  - `skipped_redundant_global_urls=40`
- **delta (actionable - raw)**:
  - `candidate_urls: +56`
  - `selected_doc_urls_not_in_candidates: -56`
  - `skipped_redundant_global_urls: -39`

Fuente:
- `docs/etl/sprints/AI-OPS-334/evidence/senado_status404_retry_dryrun_raw_*.json`
- `docs/etl/sprints/AI-OPS-334/evidence/senado_status404_retry_dryrun_actionable_*.json`
- `docs/etl/sprints/AI-OPS-334/evidence/senado_status404_retry_dryrun_delta_*.json`

## Resultado
Se cierra el gap controlable de eficiencia de packet: la cohorte actionable `status=404` vuelve a convertir `80/80` URLs seleccionadas en candidatas (`candidate_urls/fresh_rows = 1.0`) bajo contrato reproducible.

El bloqueo externo de conversión de red (`cookie_file_stale`) permanece en la fila de lane `837` y no se marca como resuelto aquí.
