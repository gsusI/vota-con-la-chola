# ETL

Estructura minima de `etl/`:

- `etl/extract/`: scripts o jobs de extraccion desde fuentes.
- `etl/transform/`: normalizacion, validacion y enriquecimiento.
- `etl/load/`: publicacion/carga a destino final.
- `etl/data/raw/`: descargas sin transformar.
- `etl/data/staging/`: datos intermedios validados.
- `etl/data/published/`: salidas canonicas consumidas por la app.

Actualmente:
- Snapshot de proximas elecciones: `etl/data/published/proximas-elecciones-espana.json`.
- Snapshot de representantes (JSON, excluye municipal por defecto): `etl/data/published/representantes-es-<snapshot_date>.json` (ver `scripts/publicar_representantes_es.py`).
- Snapshot de votaciones parlamentarias (JSON): `etl/data/published/votaciones-es-<snapshot_date>.json` (ver `scripts/publicar_votaciones_es.py`).
- Snapshot de KPIs de calidad de votaciones: `etl/data/published/votaciones-kpis-es-<snapshot_date>.json`.
- Esquema SQLite ETL: `etl/load/sqlite_schema.sql`.
- Esquema analitico (posiciones por temas): `topics`, `topic_sets`, `topic_set_topics`, `topic_evidence`, `topic_positions` (en el mismo SQLite).
- CLI ingesta politicos: `scripts/ingestar_politicos_es.py`.
- CLI ingesta Infoelectoral (descargas): `scripts/ingestar_infoelectoral_es.py`.
- CLI parlamentario (votaciones, iniciativas): `scripts/ingestar_parlamentario_es.py`.
- Tracker E2E scrape/load (TODO operativo): `docs/etl/e2e-scrape-load-tracker.md`.
- El backlog de conectores y calidad vive solo en el tracker (y el dashboard `/explorer-sources`).
- Artefactos de sprint (canónicos): `docs/etl/sprints/`.
- Índice de sprints: `docs/etl/sprints/README.md`.
- Puntero al prompt pack de sprint activo: `docs/etl/sprint-ai-agents.md`.
- Contrato de snapshot citizen (`scripts/export_citizen_snapshot.py`): `meta.quality` publica conteos de stance, `% clear/unknown`, promedio de confianza en celdas con señal y tiers `high/medium/low/none`; validable con `scripts/validate_citizen_snapshot.py`.
- Contrato KPI producto citizen v1 (`scripts/report_citizen_product_kpis.py`): artefacto reproducible con `unknown_rate`, `time_to_first_answer_seconds` y `drilldown_click_rate` (estos dos últimos desde telemetría opcional), con estados `ok|degraded|failed` y gates `--strict` / `--strict-require-complete`; atajos `just citizen-report-product-kpis`, `just citizen-check-product-kpis`, `just citizen-check-product-kpis-complete`.
- Tendencia + retención de KPI producto citizen: heartbeat/window + compaction/parity (`scripts/report_citizen_product_kpis_heartbeat.py`, `_heartbeat_window.py`, `_heartbeat_compaction.py`, `_heartbeat_compaction_window.py`) con checks estrictos de incidentes/último estado; atajos `just citizen-test-product-kpis-heartbeat`, `just citizen-check-product-kpis-heartbeat*`, `just citizen-check-product-kpis-heartbeat-compact*`.
- Contrato de observabilidad de coherencia drilldown (`/citizen -> /explorer-temas`): `scripts/report_citizen_coherence_drilldown_outcomes.py` + heartbeat/window + retención (`scripts/report_citizen_coherence_drilldown_outcomes_heartbeat.py`, `_heartbeat_window.py`, `_heartbeat_compaction.py`, `_heartbeat_compaction_window.py`) con gates estrictos; atajos `just citizen-test-coherence-drilldown-outcomes`, `just citizen-check-coherence-drilldown-outcomes*`.
- Contrato de configuracion citizen (`ui/citizen/concerns_v1.json`): validable con `scripts/validate_citizen_concerns.py` (checks de `concerns`/`packs` + integridad referencial); ejecutado en `just explorer-gh-pages-build`.
- Onboarding citizen (UI estática): `ui/citizen/index.html` incluye flujo \"Empieza aqui\" para primera visita (concern -> item -> alignment), con dismiss local en `localStorage` (`LS_ONBOARD_DISMISSED`).
- Contrato de onboarding citizen: `ui/citizen/onboarding_funnel.js` define estado/orden del funnel y `next_action` (`apply_pack|select_concern|open_topic|open_alignment|set_preference|done`), con test estricto `just citizen-test-onboarding-funnel`.
- Acelerador de primera respuesta: `ui/citizen/first_answer_accelerator.js` rankea concern+item recomendados con fallback determinista y links de auditoría (`explorer_temas|explorer_positions|explorer_evidence`); tests con `just citizen-test-first-answer-accelerator`.
- Contrato explainability unknown/no_signal: `ui/citizen/unknown_explainability.js` deriva causa dominante (`no_signal|unclear|mixed`) y recomendacion accionable para reducir incertidumbre; tests con `just citizen-test-unknown-explainability`.
- Contrato mobile-performance citizen: `scripts/report_citizen_mobile_performance_budget.py` valida presupuesto de `ui/citizen/index.html` + assets JS + snapshot + markers de latencia (`SEARCH_INPUT_DEBOUNCE_MS`, `scheduleRenderCompare`); atajos `just citizen-test-mobile-performance`, `just citizen-report-mobile-performance-budget`, `just citizen-check-mobile-performance-budget`.
- Contrato mobile observability citizen v1: `scripts/report_citizen_mobile_observability.py` valida percentiles `input_to_render_p50_ms`/`input_to_render_p90_ms` (y `p95` informativo) + `sample_count` desde telemetría JSON/JSONL, con estados `ok|degraded|failed` y gates estrictos; atajos `just citizen-test-mobile-observability`, `just citizen-report-mobile-observability`, `just citizen-check-mobile-observability`.
- Contrato Tailwind+MD3 citizen v1: `ui/citizen/tailwind_md3.tokens.json` + `scripts/build_citizen_tailwind_md3_css.py` generan `ui/citizen/tailwind_md3.generated.css` de forma determinista (`--check` para drift), validable con `scripts/report_citizen_tailwind_md3_contract.py`; atajos `just citizen-build-tailwind-md3`, `just citizen-check-tailwind-md3-sync`, `just citizen-report-tailwind-md3`, `just citizen-check-tailwind-md3`, `just citizen-test-tailwind-md3`.
- Tendencia + retención de drift Tailwind+MD3: heartbeat/window + compaction/parity (`scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat.py`, `_heartbeat_window.py`, `_heartbeat_compaction.py`, `_heartbeat_compaction_window.py`) con checks estrictos de incidentes/último estado; atajos `just citizen-check-tailwind-md3-drift-heartbeat*`, `just citizen-check-tailwind-md3-drift-heartbeat-compact*`.
- Contrato de calidad de concern packs citizen: `scripts/report_citizen_concern_pack_quality.py` puntua cada pack (`quality_score`) con heuristicas de cobertura/unknown/confianza/high-stakes y marca `weak` con razones; atajos `just citizen-test-concern-pack-quality`, `just citizen-report-concern-pack-quality`, `just citizen-check-concern-pack-quality`.
- Contrato de outcomes de concern packs citizen v1: `scripts/report_citizen_concern_pack_outcomes.py` resume adopcion de packs y follow-through de packs `weak` (`pack_selected`, `topic_open_with_pack`, share `unknown`) con estado `ok|degraded|failed`; atajos `just citizen-test-concern-pack-outcomes`, `just citizen-report-concern-pack-outcomes`, `just citizen-check-concern-pack-outcomes`.
- Tendencia + retención de concern-pack outcomes: heartbeat/window + compaction/parity (`scripts/report_citizen_concern_pack_outcomes_heartbeat.py`, `_heartbeat_window.py`, `_heartbeat_compaction.py`, `_heartbeat_compaction_window.py`) con checks estrictos de incidentes/último estado; atajos `just citizen-test-concern-pack-outcomes-heartbeat`, `just citizen-check-concern-pack-outcomes-heartbeat*`, `just citizen-check-concern-pack-outcomes-heartbeat-compact*`.
- Contrato de trust-to-action nudges citizen v1: `scripts/report_citizen_trust_action_nudges.py` mide adopcion/clickthrough de nudges de evidencia (`trust_action_nudge_shown`, `trust_action_nudge_clicked`) con estado `ok|degraded|failed`; atajos `just citizen-test-trust-action-nudges`, `just citizen-report-trust-action-nudges`, `just citizen-check-trust-action-nudges`.
- Tendencia + retención de trust-action nudges: heartbeat/window + compaction/parity (`scripts/report_citizen_trust_action_nudges_heartbeat.py`, `_heartbeat_window.py`, `_heartbeat_compaction.py`, `_heartbeat_compaction_window.py`) con checks estrictos de incidentes/último estado; atajos `just citizen-test-trust-action-nudges-heartbeat`, `just citizen-check-trust-action-nudges-heartbeat*`, `just citizen-check-trust-action-nudges-heartbeat-compact*`.
- Contrato de panel de confianza de evidencia citizen: `ui/citizen/evidence_trust_panel.js` normaliza `method`, `freshness_tier`, `trust_level`, `trust_reasons` y enlaces de auditoria; tests con `just citizen-test-evidence-trust-panel`.
- Contrato de estabilidad cross-method citizen: `ui/citizen/cross_method_stability.js` calcula deltas `votes/declared/combined`, mismatch/comparables y razones de incertidumbre; tests con `just citizen-test-cross-method-stability`.
- Contrato de accesibilidad/readability citizen: `tests/test_citizen_accessibility_readability_ui_contract.js` valida skip-link, landmark principal, live regions y labels ARIA en `/citizen`; tests con `just citizen-test-accessibility-readability`.
- Contrato de explainability-copy citizen v1: `scripts/report_citizen_explainability_copy.py` valida glosario/tooltips de lenguaje claro (`data-explainability-*`), limites de palabras por definicion/frase y ausencia de jerga prohibida, con estado `ok|degraded|failed`; atajos `just citizen-test-explainability-copy`, `just citizen-report-explainability-copy`, `just citizen-check-explainability-copy`.
- Contrato de release hardening citizen: `scripts/report_citizen_release_hardening.js` verifica paridad `ui/citizen` vs `docs/gh-pages/citizen` + shape/budget de snapshot/config; atajos `just citizen-report-release-hardening`, `just citizen-check-release-hardening`, `just citizen-release-regression-suite`.
- Packs de preocupaciones (UI estática): `ui/citizen/concerns_v1.json` define `packs` (`id`, `label`, `concern_ids`, `tradeoff`) y la UI los aplica con estado reproducible en URL (`concern_pack` + `concerns_ids`).
- Presets compartibles de alineamiento (opt-in): la UI genera/lee enlaces `#preset=v1:...` (fragmento, no query) para reproducir `view/method/pack/concerns/concern` sin backend.
- Codec compartido de preset citizen: `ui/citizen/preset_codec.js` (servido también por `/citizen/preset_codec.js` en explorer local); tests deterministas con `just citizen-test-preset-codec`.
- Contrato de errores preset (`#preset`): `error_code` estable en codec (`decode_error`, `unsupported_version`, `empty_payload`, `no_supported_fields`) + hint UX en banner para enlaces corruptos/truncados.
- Contrato de recovery/canonicalizacion preset (`#preset`): la UI recupera formatos legacy/no-encode/double-encode, normaliza a hash canonico v1 (`history.replaceState`) y expone acciones `Copiar enlace canonico` / `Limpiar hash preset`; tests en `tests/test_citizen_preset_codec.js` y `tests/test_citizen_preset_recovery_ui_contract.js`.
- Matriz canónica de ejemplos preset (QA + tests): `tests/fixtures/citizen_preset_hash_matrix.json` (`schema_version=v2`, con `hash_cases` + `share_cases`, consumidos por `tests/test_citizen_preset_codec.js`).
- Reporte de drift del contrato preset: `just citizen-report-preset-contract` (JSON con conteos por sección + `failed_ids`; usa `--strict` para fail-fast).
- Reporte de paridad source->published del codec preset: `just citizen-report-preset-codec-parity` (JSON con `source_sha256`, `published_sha256`, bytes y `first_diff_line`; `--strict` falla en drift).
- Reporte de sync-state source->published del codec preset: `just citizen-report-preset-codec-sync` (JSON con `would_change`, hashes before/after y `recommended_command`; `--strict` falla si el published está desactualizado).
- Reporte bundle de contrato preset: `just citizen-report-preset-contract-bundle` (JSON único con `sections_fail`, `failed_sections`, `failed_ids` + nested reports de contract/parity/sync).
- Reporte histórico de bundle preset: `just citizen-report-preset-contract-bundle-history` (JSON con `history_size_before/after`, `regression_detected`, `regression_reasons`; historial JSONL configurable en `CITIZEN_PRESET_BUNDLE_HISTORY_PATH`).
- Reporte ventana de histórico (last-N): `just citizen-report-preset-contract-bundle-history-window` (JSON con `entries_in_window`, `regressions_in_window`, `regression_events`; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_WINDOW`).
- Reporte de compactación de histórico (cadencia 1/5/20 configurable): `just citizen-report-preset-contract-bundle-history-compact` (JSON con `entries_total/selected/dropped`, `tiers`, `incidents_*`, `strict_fail_reasons`; compacted JSONL configurable en `CITIZEN_PRESET_BUNDLE_HISTORY_COMPACT_PATH`).
- Reporte SLO de histórico (ventana + thresholds): `just citizen-report-preset-contract-bundle-history-slo` (JSON con `regressions_in_window`, `regression_rate_pct`, `green_streak_latest`, `latest_entry_clean`, `previous_window`, `deltas`, `risk_level`, `risk_reasons`, `checks`, `strict_fail_reasons`; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_*`).
- Reporte digest SLO de histórico (compacto para polling): `just citizen-report-preset-contract-bundle-history-slo-digest` (JSON con `status`, `risk_level`, `risk_reasons`, `strict_fail_reasons`, `key_metrics`, `key_checks`, `thresholds`, `previous_window`, `deltas`; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_OUT` y `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_OUT`).
- Reporte heartbeat NDJSON de digest SLO (tendencia lightweight): `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat` (append JSONL por corrida con `status/risk_level` + métricas clave; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_OUT`, `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_PATH`, `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_OUT`).
- Reporte ventana de heartbeat digest SLO (last-N + conteos + first/last failed/red): `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-window` (JSON con `status_counts`, `risk_level_counts`, `failed_in_window`, `failed_rate_pct`, timestamps first/last; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_*`).
- Reporte compactación de heartbeat digest SLO (cadencia + preservación de incidentes): `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact` (JSON con `entries_total/selected/dropped`, `failed_*`, `red_*`, `incidents_*`, `strict_fail_reasons`; compacted JSONL configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_*`).
- Reporte paridad raw-vs-compacted del heartbeat (last-N): `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window` (JSON con cobertura de ventana, `missing_*_sample`, checks de `latest`/incidentes/failed/red; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW*`).
- Reporte digest del compact-window heartbeat (single-file polling): `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest` (JSON compacto con `status/risk_level` derivados de paridad last-N, `risk_reasons`, `strict_fail_reasons`; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_OUT` y `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_OUT`).
- Reporte heartbeat NDJSON del compact-window digest: `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat` (append dedupe JSONL con `status/risk_level`, conteos de `missing/incident_missing` y razones; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_*`).
- Reporte ventana del heartbeat de compact-window digest: `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window` (JSON `last-N` con conteos/rates de `failed`+`degraded`, first/last timestamps y checks estrictos; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_*`).
- Reporte compactación del heartbeat de compact-window digest: `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact` (compacta la nueva serie NDJSON con preservación estricta de incidentes `failed/degraded/red/strict`, resumen `entries_total/selected/dropped` y `strict_fail_reasons`; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_*`).
- Reporte ventana de paridad del heartbeat compactado de compact-window digest: `just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window` (compara `last-N` raw vs compacted de esta nueva serie, exige `latest` presente y paridad de incidentes/failed/degraded/red; configurable con `CITIZEN_PRESET_BUNDLE_HISTORY_SLO_DIGEST_HEARTBEAT_COMPACT_WINDOW_DIGEST_HEARTBEAT_COMPACT_WINDOW*`).
- CI del contrato preset: `.github/workflows/etl-tracker-gate.yml` incluye job `citizen-preset-contract` (tests + reportes estrictos + artifacts `citizen-preset-contract`, `citizen-preset-codec-parity`, `citizen-preset-codec-sync`, `citizen-preset-contract-bundle`, `citizen-preset-contract-bundle-history`, `citizen-preset-contract-bundle-history-window`, `citizen-preset-contract-bundle-history-compaction`, `citizen-preset-contract-bundle-history-slo`, `citizen-preset-contract-bundle-history-slo-digest`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-window`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat-window`, `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat-compaction` y `citizen-preset-contract-bundle-history-slo-digest-heartbeat-compaction-window-digest-heartbeat-compaction-window`).

Nota para votaciones:
- Flujo recomendado: `ingest -> backfill-member-ids -> link-votes -> backfill-topic-analytics -> quality-report -> publish`.
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py link-votes --db <db>` antes de publicar si quieres maximizar `evento -> iniciativa` (y por extensión el tagging a topics en `backfill-topic-analytics`).
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db <db>` después de la ingesta de `congreso_votaciones,senado_votaciones` para resolver `person_id` en votos nominales.
- Sugerencia operativa: añade `--unmatched-sample-limit 50` para capturar casos sin emparejar y priorizar corrección manual por razón (`no_candidates`, `skipped_no_name`, `ambiguous`, ...).
- Para publicar y auditar unmatched en un pass sin escribir cambios, usa:
  - `python3 scripts/publicar_votaciones_es.py --db <db> --snapshot-date <fecha> --include-unmatched --unmatched-sample-limit 100`
- Para publicar y materializar el emparejado de `person_id` al vuelo (sin paso separado), usa:
  - `python3 scripts/publicar_votaciones_es.py --db <db> --snapshot-date <fecha> --backfill-member-ids`
- Revisa KPIs/gate con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --source-ids congreso_votaciones,senado_votaciones` y usa `--enforce-gate` para fallar en CI cuando no se cumpla el minimo.
- Para incluir diagnóstico de emparejado de persona en seco, usa `--include-unmatched --unmatched-sample-limit <n>`.
- Si además pasas `--include-initiatives`, el bloque `initiatives.kpis` ahora incluye cobertura a nivel de doc-link:
  - `total_doc_links`, `downloaded_doc_links`, `downloaded_doc_links_pct`
  - `missing_doc_links`, `missing_doc_links_likely_not_expected`, `missing_doc_links_actionable`
  - `effective_downloaded_doc_links_pct`, `actionable_doc_links_closed_pct`
  - `doc_links_with_fetch_status`, `fetch_status_coverage_pct`
  - `downloaded_doc_links_with_excerpt`, `excerpt_coverage_pct`
  - extracción sobre docs descargados:
    - `downloaded_doc_links_with_extraction`, `downloaded_doc_links_missing_extraction`
    - `extraction_coverage_pct`, `extraction_needs_review_doc_links`, `extraction_needs_review_pct`, `extraction_review_closed_pct`
  - `missing_doc_links_status_buckets` (ej. `404/403/500`) por fuente y agregado
  - en `by_source.senado_iniciativas`: `global_enmiendas_vetos_analysis` con el split redundante/accionable del tail
- El gate de iniciativas (`initiatives.gate`) ahora también protege extracción:
  - `actionable_doc_links_closed_pct >= 1.0`
  - `extraction_coverage_pct >= 0.95`
  - `extraction_review_closed_pct >= 0.95`
- Si además pasas `--include-declared --declared-source-ids <csv>`, el bloque `declared.kpis` expone salud de fuentes declaradas (`congreso_intervenciones`, `programas_partidos`):
  - `topic_evidence_total`, `topic_evidence_with_nonempty_stance_pct`
  - `review_total`, `review_pending`, `review_closed_pct`
  - `declared_positions_scope_total`, `declared_positions_total`, `declared_positions_coverage_pct`
  - breakdown por fuente en `declared.kpis.by_source`
- El gate declarado (`declared.gate`) valida por defecto:
  - `topic_evidence_with_nonempty_stance_pct >= 0.99`
  - `review_closed_pct >= 0.95`
  - `declared_positions_coverage_pct >= 0.95`
- Exporta KPIs por fecha con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --json-out etl/data/published/votaciones-kpis-es-<snapshot>.json`.
- En el flujo `just parl-quality-pipeline`, el gate ahora se evalúa con `--include-initiatives --enforce-gate` para cubrir también KPIs de extracción de iniciativas.
- Atajos para lane declarada:
  - `just parl-quality-report-declared`
  - `just parl-quality-report-declared-enforce`
  - Variables opcionales: `DECLARED_QUALITY_SOURCE_IDS`, `DECLARED_QUALITY_VOTE_SOURCE_IDS`, `DECLARED_QUALITY_OUT`, `DECLARED_QUALITY_SKIP_VOTE_GATE` (default `1`)
  - Para ejecución declarada pura (sin bloquear por gate de votaciones), usar `--skip-vote-gate` en CLI o mantener `DECLARED_QUALITY_SKIP_VOTE_GATE=1` en `just`.
- El JSON de votaciones puede ser muy grande en corridas completas; para smoke/debug usa `--max-events` y/o `--max-member-votes-per-event`.

Nota para posiciones por temas:
- La representacion “politico x scope x tema” se construye desde evidencia atómica trazable (`topic_evidence`) y se agrega en snapshots recomputables (`topic_positions`).
- El roadmap operativo y de calidad vive en `docs/etl/e2e-scrape-load-tracker.md` (filas “Analitica”).
- Para poblar un MVP desde **votaciones** (hecho, reproducible), ejecuta:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db <db> --as-of-date <YYYY-MM-DD>`
  - Esto materializa `topic_sets`, `topics`, `topic_set_topics`, `topic_evidence`, `topic_positions` y desbloquea `/explorer-temas`.
- Seed/versionado del set (parámetros + curación opcional): `etl/data/seeds/topic_taxonomy_es.json`.
- Para capturar evidencia **textual** (metadata + excerpt) para evidencia declarada (p.ej. intervenciones Congreso):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db <db> --source-id congreso_intervenciones --only-missing`
  - Esto materializa `text_documents` y además copia un snippet a `topic_evidence.excerpt` para auditoría en `/explorer-temas`.
- Para preparar cola de análisis de PDFs/XML ya descargados (sin re-fetch de red), usa:
  - `python3 scripts/export_pdf_analysis_queue.py --db <db> --initiative-source-id senado_iniciativas --doc-source-id parl_initiative_docs --only-missing-excerpt --out docs/etl/sprints/<SPRINT>/exports/senado_pdf_analysis_queue.csv`
  - atajo: `just parl-export-initdoc-analysis-queue`
- Para preparar una cola determinista de extracción sobre `text_documents` (dedupe por checksum `content_sha256`, útil para subagentes/batches), usa:
  - `python3 scripts/export_text_extraction_queue.py --db <db> --source-ids parl_initiative_docs,congreso_intervenciones,programas_partidos --formats pdf,html,xml --dedupe-by content_sha256 --out docs/etl/sprints/<SPRINT>/exports/text_extraction_queue.csv --summary-out docs/etl/sprints/<SPRINT>/evidence/text_extraction_queue_summary.json`
  - solo pendientes de excerpt: añade `--only-missing-excerpt`
  - atajos: `just parl-export-text-extraction-queue` / `just parl-export-text-extraction-queue-missing`
  - salida CSV: `queue_key`, `queue_status`, `refs_total`, `refs_missing_excerpt`, `source_record_pks_json`
- Para rellenar `text_excerpt/text_chars` en documentos de iniciativas ya descargados (XML/PDF), usa:
  - `python3 scripts/backfill_initiative_doc_excerpts.py --db <db> --source-id parl_initiative_docs --initiative-source-id senado_iniciativas`
  - `python3 scripts/backfill_initiative_doc_excerpts.py --db <db> --source-id parl_initiative_docs`
  - atajos: `just parl-backfill-initdoc-excerpts` / `just parl-backfill-initdoc-excerpts-all`
- Para materializar extracción semántica reproducible de \"qué se votó\" sobre docs ya descargados, usa:
  - `python3 scripts/backfill_initiative_doc_extractions.py --db <db> --doc-source-id parl_initiative_docs --initiative-source-ids congreso_iniciativas,senado_iniciativas --extractor-version heuristic_subject_v2 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_extractions.json`
  - tabla destino: `parl_initiative_doc_extractions` (1 fila por `source_record_pk`, idempotente)
  - `heuristic_subject_v2` añade `title_hint_strong` para auto-cerrar títulos legislativos explícitos (reduce cola de revisión sin redescargar bytes).
  - refinamiento actual: la cola residual queda concentrada en `keyword_window`; `title_hint*` queda prácticamente cerrada.
  - re-ejecución solo pendientes: añade `--only-missing`
  - atajos: `just parl-backfill-initdoc-extractions` / `just parl-backfill-initdoc-extractions-missing`
- Para exportar cola de revisión de extracciones (`needs_review=1`) para subagentes/manual, usa:
  - `python3 scripts/export_initdoc_extraction_review_queue.py --db <db> --source-id parl_initiative_docs --only-needs-review --out docs/etl/sprints/<SPRINT>/exports/initdoc_extraction_review_queue.csv`
  - atajo: `just parl-export-initdoc-extraction-review-queue`
  - para paginar batches deterministas: añade `--limit <N> --offset <K>`
  - El CSV incluye columnas de decisión para round-trip:
    - `subject_method` (derivado de `analysis_payload_json`)
    - `review_status` (`resolved|ignored|pending`)
    - `final_subject`, `final_title`, `final_confidence`
    - `review_note`, `reviewer`
- Para aplicar decisiones del CSV de revisión sobre `parl_initiative_doc_extractions`, usa:
  - `python3 scripts/apply_initdoc_extraction_reviews.py --db <db> --source-id parl_initiative_docs --in <review_csv> --out docs/etl/sprints/<SPRINT>/evidence/initdoc_extraction_review_apply.json`
  - smoke seguro (sin escribir): añade `--dry-run`
  - atajos: `just parl-apply-initdoc-extraction-reviews` / `just parl-apply-initdoc-extraction-reviews-dry-run` (requiere `INITDOC_EXTRACT_REVIEW_APPLY_FILE=<csv_path>`)
- Para reconstruir trazabilidad de descargas históricas en `document_fetches` (cuando ya existen `parl_initiative_documents + text_documents` pero faltan filas de fetch), usa:
  - `python3 scripts/backfill_initiative_doc_fetch_status.py --db <db> --source-id parl_initiative_docs`
  - opcional por fuente de iniciativas: `python3 scripts/backfill_initiative_doc_fetch_status.py --db <db> --source-id parl_initiative_docs --initiative-source-id congreso_iniciativas`
  - atajo: `just parl-backfill-initdoc-fetch-status` (filtra con `INITDOC_FETCH_SCOPE=senado_iniciativas` o `congreso_iniciativas`)
- Para ampliar links de Senado usando XML de detalle ya descargado (`tipoFich=3`) y añadir PDFs BOCG/DS oficiales a `links_bocg_json/links_ds_json`, usa:
  - `python3 scripts/backfill_senado_publication_links_from_detail_docs.py --db <db> --source-id senado_iniciativas --doc-source-id parl_initiative_docs --only-initiatives-with-missing-docs`
  - atajo: `just parl-backfill-senado-detail-publication-links`
- Para emitir un reporte único de estado de iniciativas/docs (links, descargados, buckets HTTP faltantes, cobertura de excerpt, cobertura linked-to-votes), usa:
  - `python3 scripts/report_initiative_doc_status.py --db <db> --initiative-source-ids congreso_iniciativas,senado_iniciativas --doc-source-id parl_initiative_docs --out docs/etl/sprints/<SPRINT>/evidence/initiative_doc_status.json`
  - atajo: `just parl-report-initdoc-status` (controla salida con `INITDOC_STATUS_OUT=...`)
  - La salida también incluye cobertura de extracción semántica:
    - `downloaded_with_extraction`, `downloaded_missing_extraction`
    - `extraction_coverage_pct`
    - `extraction_needs_review`, `extraction_needs_review_pct`
  - El reporte también incluye triage de cola Senado:
    - `missing_doc_links_likely_not_expected`
    - `missing_doc_links_actionable`
    - `effective_downloaded_doc_links_pct`
    - `global_enmiendas_vetos_analysis` (solo `senado_iniciativas`) con `likely_not_expected_zero_enmiendas`, `likely_not_expected_redundant_global_url`, `likely_not_expected_total`, `actionable_missing_count`, `no_ini_downloaded`
  - Para exportar solo URLs realmente accionables de Senado (sin cola redundante `global_enmiendas_vetos`), usa:
    - `python3 scripts/export_missing_initiative_doc_urls.py --db <db> --initiative-source-ids senado_iniciativas --only-actionable-missing --format csv --out docs/etl/sprints/<SPRINT>/exports/senado_tail_actionable.csv`
    - Para usarlo como gate estricto de cola vacía: añade `--strict-empty` (exit `4` si quedan filas accionables).
    - atajos: `just parl-export-missing-initdoc-urls-actionable` / `just parl-check-missing-initdoc-urls-actionable-empty`
  - Para el mismo gate en JSON machine-readable, usa:
    - `python3 scripts/report_initdoc_actionable_tail_contract.py --db <db> --initiative-source-ids senado_iniciativas --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_contract.json`
    - estricto: añade `--strict` (exit `4` si `actionable_missing > 0`)
    - atajos: `just parl-report-initdoc-actionable-tail-contract` / `just parl-check-initdoc-actionable-tail-contract`
  - Para una tarjeta compacta de alerting/dashboard basada en ese contrato, usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest.py --contract-json docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_contract.json --max-actionable-missing 0 --max-actionable-missing-pct 0 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest.json`
    - estricto: añade `--strict` (exit `4` si el digest queda en `status=failed`)
    - estados: `ok` (cola accionable vacía), `degraded` (cola no vacía pero dentro de umbrales), `failed` (supera umbrales)
    - atajos: `just parl-report-initdoc-actionable-tail-digest` / `just parl-check-initdoc-actionable-tail-digest`
  - Para historial append-only del digest (heartbeat NDJSON, dedupe por `heartbeat_id`), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat.py --digest-json docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest.json --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat.json`
    - estricto: añade `--strict` (exit `4` si el heartbeat queda en `status=failed` o hay `validation_errors`)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat` / `just parl-check-initdoc-actionable-tail-digest-heartbeat`
  - Para resumen de tendencia `last N` sobre heartbeat (conteos `ok/degraded/failed`, latest/streaks y checks estrictos), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_window.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl --last 20 --max-failed 0 --max-failed-rate-pct 0 --max-degraded 0 --max-degraded-rate-pct 0 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_window.json`
    - estricto: añade `--strict` (exit `4` si `strict_fail_reasons` no está vacío)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-window` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-window`
  - Para compactar el heartbeat preservando incidentes (`failed/degraded/strict/malformed`) con cadencia determinista, usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl --compacted-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.compacted.jsonl --keep-recent 20 --keep-mid-span 100 --keep-mid-every 5 --keep-old-every 20 --min-raw-for-dropped-check 25 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction.json`
    - estricto: añade `--strict` (exit `4` si falla latest/paridad de incidentes o no hay `dropped` cuando corresponde)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact`
  - Para comparar paridad `raw vs compacted` en `last N` (latest + incidentes), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl --compacted-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.compacted.jsonl --last 20 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window.json`
    - estricto: añade `--strict` (exit `4` si faltan latest/incidentes en compacted)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window`
  - Para un digest compacto de esa paridad (`ok|degraded|failed` + `risk_level`) apto para polling, usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --compaction-window-json docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window.json --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.json`
    - estricto: añade `--strict` (exit `4` si el digest queda en `status=failed`)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest`
  - Para historial append-only del digest de paridad compacta (NDJSON dedupe), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.py --digest-json docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.json --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.json`
    - estricto: añade `--strict` (exit `4` si heartbeat inválido o `status=failed`)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat`
  - Para resumen de tendencia `last N` sobre ese heartbeat (fallidos/degraded/risk-level), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl --last 20 --max-failed 0 --max-failed-rate-pct 0 --max-degraded 0 --max-degraded-rate-pct 0 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.json`
    - estricto: añade `--strict` (exit `4` si `strict_fail_reasons` no está vacío)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-window` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-window`
  - Para compactar ese heartbeat de digest compacto (retención acotada + preservación de incidentes), usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl --compacted-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl --keep-recent 20 --keep-mid-span 100 --keep-mid-every 5 --keep-old-every 20 --min-raw-for-dropped-check 25 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.json`
    - estricto: añade `--strict` (exit `4` si falla latest/paridad de incidentes o no hay `dropped` cuando corresponde)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact`
  - Para comparar paridad `raw vs compacted` de ese heartbeat en `last N`, usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --heartbeat-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl --compacted-jsonl docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl --last 20 --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.json`
    - estricto: añade `--strict` (exit `4` si faltan latest/incidentes en compacted)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window`
  - Para digest compacto de esa paridad (`ok|degraded|failed` + `risk_level`) apto para polling, usa:
    - `python3 scripts/report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --compaction-window-json docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.json --out docs/etl/sprints/<SPRINT>/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.json`
    - estricto: añade `--strict` (exit `4` si el digest queda en `status=failed`)
    - atajos: `just parl-report-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest` / `just parl-check-initdoc-actionable-tail-digest-heartbeat-compact-window-digest-heartbeat-compact-window-digest`
    - Publicación UI/API: `/api/sources/status` y `docs/gh-pages/explorer-sources/data/status.json` incluyen `initdoc_actionable_tail` (`contract` + `digest` + `heartbeat_window` + `heartbeat_compaction_window` + `heartbeat_compaction_window_digest` + `heartbeat_compaction_window_digest_heartbeat_window` + `heartbeat_compaction_window_digest_heartbeat_compaction_window` + `heartbeat_compaction_window_digest_heartbeat_compaction_window_digest`) y la card \"Iniciativas Senado (tail)\" muestra también `cd-compact` + `cd-digest`.
  - CI: `.github/workflows/etl-tracker-gate.yml` incluye job `initdoc-actionable-tail-contract` que valida fail/pass con fixture determinista para:
    - `export_missing_initiative_doc_urls.py --strict-empty`
    - `report_initdoc_actionable_tail_contract.py --strict`
    - `report_initdoc_actionable_tail_digest.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_window.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_window.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.py --strict`
    - `report_initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest.py --strict`
- Para drenaje unattended de cola Senado con frenos anti-loop (sin quedarse colgado indefinidamente), usa:
  - `bash scripts/senado_tail_daemon.sh`
  - atajo: `just parl-senado-tail-daemon`
  - stop conditions: `uniform_404_tail`, `no_progress`, `max_rounds`, `complete`
  - resumen machine-readable: `RUN_DIR/_stop_summary.json`
- Para intentar recuperación desde archivo público cuando el tail queda en `404` (sin golpear de nuevo URL original en cada loop), usa:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents --db <db> --initiative-source-ids senado_iniciativas --include-unlinked --archive-fallback --archive-timeout 12 --limit-initiatives 5000 --max-docs-per-initiative 1`
  - atajo: `just parl-backfill-initiative-documents-archive`
  - métricas nuevas en la salida JSON: `archive_first_urls`, `archive_lookup_attempted`, `archive_hits`, `archive_fetched_ok`
- Para inferir un **stance mínimo** en evidencia declarada (regex v2 conservador sobre excerpts ya capturados):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db <db> --source-id congreso_intervenciones --min-auto-confidence 0.62`
  - atajo parametrizable: `just parl-backfill-declared-stance` (usa `DECLARED_SOURCE_ID=<source_id>`, default `congreso_intervenciones`)
  - El comando auto-escribe solo casos de confianza alta y alimenta `topic_evidence_reviews` para casos ambiguos (`missing_text`, `no_signal`, `low_confidence`, `conflicting_signal`).
- Para inspeccionar la cola de revisión:
  - `python3 scripts/ingestar_parlamentario_es.py review-queue --db <db> --source-id congreso_intervenciones --status pending --limit 50`
  - atajo parametrizable: `just parl-review-queue` (usa `DECLARED_SOURCE_ID=<source_id>` y `DECLARED_REVIEW_LIMIT=<n>`)
- Si se delega revisión a crowd (MTurk), usar el runbook:
  - `docs/etl/mechanical-turk-review-instructions.md`
- Para aplicar decisión manual sobre evidencia pendiente (y opcionalmente recomputar posiciones):
  - `python3 scripts/ingestar_parlamentario_es.py review-decision --db <db> --source-id congreso_intervenciones --evidence-ids 123,124 --status resolved --final-stance support --recompute --as-of-date <YYYY-MM-DD>`
  - `python3 scripts/ingestar_parlamentario_es.py review-decision --db <db> --source-id congreso_intervenciones --evidence-ids 130 --status ignored --note \"sin señal accionable\"`
  - atajo parametrizable: `just parl-review-resolve <evidence_id> <stance>` (usa `DECLARED_SOURCE_ID=<source_id>`)
- Para materializar **posiciones (says)** desde esa evidencia declarada (en `topic_positions`, `computed_method=declared`):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db <db> --source-id congreso_intervenciones --as-of-date <YYYY-MM-DD>`
  - atajo parametrizable: `just parl-backfill-declared-positions` (usa `DECLARED_SOURCE_ID=<source_id>`, default `congreso_intervenciones`)
- Para ejecutar el loop reproducible de `programas_partidos` con manifest local:
  - preflight de manifest (fail-fast): `PROGRAMAS_MANIFEST=<manifest.csv> PROGRAMAS_MANIFEST_VALIDATE_OUT=docs/etl/sprints/<SPRINT>/evidence/programas_manifest_validate.json just parl-validate-programas-manifest`
  - (opcional) exigir `local_path` en todas las filas: añade `PROGRAMAS_MANIFEST_REQUIRE_LOCAL_PATH=1`
  - `SNAPSHOT_DATE=<YYYY-MM-DD> PROGRAMAS_MANIFEST=<manifest.csv> just parl-programas-pipeline`
  - Esto ejecuta: validate-manifest + ingest (`programas_partidos`) + `backfill-declared-stance` + `backfill-declared-positions` + status JSON.
- Para emitir un status machine-readable de cualquier fuente declarada:
  - `python3 scripts/report_declared_source_status.py --db <db> --source-id <source_id> --out docs/etl/sprints/<SPRINT>/evidence/declared_source_status.json`
  - atajo genérico: `DECLARED_SOURCE_ID=<source_id> DECLARED_STATUS_OUT=<path>.json just parl-report-declared-source-status`
  - atajo `programas`: `PROGRAMAS_STATUS_OUT=<path>.json just parl-programas-status`
- Para materializar una **posición combinada** (KISS: `votes` si existe; si no, `declared`) en `topic_positions`, `computed_method=combined`:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db <db> --as-of-date <YYYY-MM-DD>`
  - (o `just parl-backfill-combined-positions`)

## Política de snapshots publicables

- Los artefactos publicados en `etl/data/published/` llevan la fecha de snapshot en el nombre (`...-<fecha>.json`).
- El snapshot se produce con `SNAPSHOT_DATE` y es reproducible para una fecha concreta.
- Política de refresco: re-generar `representantes` y `votaciones` cuando cambie la composición o tras mejoras de parsing/linking de fuente, documentando la fecha en commit y tracker.
- Mantener al menos un snapshot publicado por nivel operativo tras cambios de formato relevantes.

## Publicación abierta en Hugging Face

- Decisión: el espejo público de snapshots vive en un dataset de Hugging Face.
- Credenciales en `.env`:
  - `HF_TOKEN`
  - `HF_USERNAME`
  - `HF_DATASET_REPO_ID` (opcional, por defecto `<HF_USERNAME>/vota-con-la-chola-data`)
- Comandos:
  - `just etl-publish-hf-dry-run` para validar paquete local sin subir.
  - `just etl-publish-hf` para subir snapshot real.
  - `just etl-verify-hf-quality` para verificar en remoto que `latest.json` + `manifest.json` + `README.md` publican `quality_report` consistente para `SNAPSHOT_DATE`.
  - `just etl-publish-hf-verify` para ejecutar publish + verificación remota en un solo flujo.
  - `just etl-publish-hf-raw-dry-run` para validar empaquetado raw en bloques.
  - `just etl-publish-hf-raw` para subir bloques raw (`HF_RAW_DATASET_REPO_ID`).
- Estructura remota por snapshot:
  - `snapshots/<snapshot_date>/politicos-es.sqlite.gz` (solo si `HF_INCLUDE_SQLITE_GZ=1`; no recomendado en público)
  - `snapshots/<snapshot_date>/published/*`
  - `snapshots/<snapshot_date>/sources/<source_id>.json` (procedencia legal por fuente: licencia/aviso, obligaciones, terms_url, estado de verificación)
  - `snapshots/<snapshot_date>/ingestion_runs.csv`
  - `snapshots/<snapshot_date>/source_records_by_source.csv`
  - `snapshots/<snapshot_date>/explorer_schema.json`
  - `snapshots/<snapshot_date>/manifest.json`
  - `snapshots/<snapshot_date>/checksums.sha256`
  - `latest.json` en la raíz del dataset.
  - `manifest.json` y `latest.json` incluyen `quality_report` cuando existe `published/votaciones-kpis-es-<snapshot_date>.json` (estado de gate y KPIs clave).
  - `README.md` generado para el dataset incluye un "Resumen de calidad del snapshot" con esos KPIs/gates.
- Reutilización/licencias:
  - El repo HF usa `license: other` porque mezcla múltiples condiciones de reutilización por fuente.
  - La referencia normativa efectiva está en `sources/<source_id>.json` dentro de cada snapshot.
- Guardas de privacidad por defecto:
  - `HF_PARQUET_EXCLUDE_TABLES=raw_fetches,run_fetches,source_records,lost_and_found`
  - `HF_ALLOW_SENSITIVE_PARQUET=0` (activar solo en datasets privados)
  - `HF_INCLUDE_SQLITE_GZ=0` (activar solo en datasets privados)
- Guardrail de calidad en publish HF:
  - `HF_REQUIRE_QUALITY_REPORT=1` por defecto en `just etl-publish-hf*` (inyecta `--require-quality-report`).
  - para casos excepcionales (backfill histórico sin KPI), se puede desactivar temporalmente con `HF_REQUIRE_QUALITY_REPORT=0`.
- Publicación raw en bloques:
  - Se empaqueta en `tar.gz` con límite `HF_RAW_MAX_FILES_PER_BLOCK` (default `10000`) por bloque.
  - `etl/data/raw/manual/**` se excluye por defecto para evitar fuga de perfiles/cookies; habilitar explícitamente con `HF_RAW_INCLUDE_MANUAL=1` solo si la revisión de privacidad lo permite.
- Regla operativa: después de publicar artefactos locales por snapshot, ejecutar `just etl-publish-hf` o registrar bloqueo con evidencia en tracker.
- Gate recomendado post-publish: ejecutar `just etl-verify-hf-quality` y adjuntar JSON de verificación en evidencia de sprint.

## Entorno reproducible con Docker

Prerequisitos:
- Docker Desktop o Docker Engine + Compose.
- `just` instalado (`brew install just` en macOS).

## Opcion recomendada: just (sin Python local)

```bash
just etl-build
just etl-init
just etl-samples
just parl-backfill-member-ids
just parl-quality-pipeline
just parl-publish-votaciones
just parl-congreso-votaciones-pipeline
just parl-samples
just parl-link-votes
just parl-quality-report
just parl-quality-report-initiatives
just parl-quality-report-initiatives-enforce
just parl-quality-report-declared
just parl-quality-report-declared-enforce
just citizen-test-preset-codec
just citizen-report-preset-contract
just citizen-report-preset-codec-parity
just citizen-report-preset-codec-sync
just citizen-report-preset-contract-bundle
just citizen-report-preset-contract-bundle-history
just citizen-report-preset-contract-bundle-history-window
just citizen-report-preset-contract-bundle-history-compact
just citizen-report-preset-contract-bundle-history-slo
just citizen-report-preset-contract-bundle-history-slo-digest
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-window
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-window
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact
just citizen-report-preset-contract-bundle-history-slo-digest-heartbeat-compact-window-digest-heartbeat-compact-window
just etl-stats
just etl-backfill-territories
just etl-backfill-normalized
just etl-e2e
just etl-publish-representantes
just etl-publish-votaciones
just etl-publish-hf-verify
just etl-verify-hf-quality
just parl-quality-report-json
just etl-smoke-e2e
just etl-smoke-votes
```

UI de navegacion de grafo (Docker):

```bash
just graph-ui
```

Gate local del tracker:

```bash
just etl-tracker-status
just etl-tracker-gate
```

## Opcion alternativa: docker compose (sin just)

Todos los comandos Python se ejecutan dentro del contenedor `etl`, asi que no necesitas instalar Python en el host.

### Build de imagen

```bash
docker compose build etl
```

### Inicializar SQLite

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py init-db --db etl/data/staging/politicos-es.db"
```

### Ingesta live (cuando haya red)

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest \
    --db etl/data/staging/politicos-es.db \
    --source all \
    --snapshot-date 2026-02-12 \
    --strict-network"
```

Extraccion live fuente por fuente (sin `just`):

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest \
    --db etl/data/staging/politicos-es.db \
    --source congreso_diputados \
    --snapshot-date 2026-02-12 \
    --strict-network"
```

Gate local del tracker (falla si una fuente marcada `DONE` tiene `0` carga real):

```bash
docker compose run --rm etl \
  "python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-done-zero-real"
```

UI de navegacion de grafo (Docker):

```bash
DB_PATH=etl/data/staging/politicos-es.db docker compose up --build graph-ui
```

Esto publica la UI en `http://localhost:8080` (usa `DB_PATH` para elegir otra SQLite).

Modo background:

```bash
DB_PATH=etl/data/staging/politicos-es.db docker compose up --build -d graph-ui
docker compose stop graph-ui
docker compose rm -f graph-ui
```

Override de variables:

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.e2e9.db --source all --snapshot-date 2026-02-12 --strict-network"
DB_PATH=etl/data/staging/politicos-es.e2e9.db docker compose up --build graph-ui
```

Backfill opcional de normalizacion (una vez, para historico):

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py backfill-normalized --db etl/data/staging/politicos-es.db"
```

Con `just`:

```bash
just etl-backfill-normalized
```

Backfill opcional de **referencias territoriales** (enriquece `territories.name/level/parent`):

```bash
just etl-backfill-territories
```

Nota de rendimiento:
- La ingesta normal (`ingest`) mantiene el camino rapido y no ejecuta backfills pesados.
- El backfill de tablas/columnas normalizadas se ejecuta solo bajo demanda con `backfill-normalized`.

## Consultas SQL utiles

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM persons;"
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) FROM mandates WHERE is_active=1 GROUP BY source_id;"
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, source_id, status, records_loaded FROM ingestion_runs ORDER BY run_id DESC LIMIT 5;"
```
