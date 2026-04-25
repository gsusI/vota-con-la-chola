# AI-OPS-243 - Programas web: filtro no-programático + hardening de señal

## Objetivo
Reducir evidencia `declared:programa` espuria proveniente de homepages/páginas legales y mejorar densidad de señal útil sin perder trazabilidad de ingesta.

## Cambios implementados
- `etl/parlamentario_es/pipeline.py`
  - Clasificador `_is_programmatic_program_doc(...)` para distinguir documentos programáticos vs no programáticos usando:
    - hints de URL,
    - hints de texto,
    - proximidad verbo-política + keyword de concern,
    - fallback por densidad de verbos.
  - Nuevo contador `skipped.non_program_doc` y telemetría `program_doc_signals` en `ingestion_runs.message`.
  - Matching semántico ampliado a `text_for_matching` (ventana larga) manteniendo `text_excerpt` corto para almacenamiento/UI.
- `tests/test_parl_programas_partidos.py`
  - Test de heurísticas del clasificador.
  - Test de contrato: `source_records/text_documents` se conservan, pero los docs no programáticos no generan `topic_evidence`.

## Resultado en staging (manifest unión multicíclo)
- Run: `run_id=292`, `records_seen=51`, `records_loaded=51`, `evidence_inserted=27`.
- Filtro aplicado: `skipped.non_program_doc=42`.
- Señales del clasificador: `legal_or_cookie_text=31`, `no_programmatic_signal=11`, `text_program_phrase=6`, `url_program_hint=3`.

## Delta KPI (baseline -> post-ignore)
- `topic_evidence_total`: `223 -> 68` (`-155`)
- `topic_evidence_by_stance.support`: `2 -> 4` (`+2`)
- `topic_evidence_by_stance.unclear`: `221 -> 64` (`-157`)
- `declared_positions_total`: `5 -> 4` (`-1`)
- `review_pending`: `0 -> 0` (tras cierre explícito de cola residual)
- Gate declarado: `passed=true`.

## Estado
- Lane anti-`no_signal`: mejora material en densidad de señal y reducción de ruido, pero cobertura partidaria todavía parcial (`party_proxy_count=4` sobre universo de 15).
- Conclusión operativa: mantener `PARTIAL` y mover el próximo esfuerzo a curación de deeplinks programáticos (evitar homepages genéricas).
