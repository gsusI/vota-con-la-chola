# AI-OPS-244 - Curación automática de deeplinks de programas (multicíclo)

## Objetivo
Avanzar la lane de cobertura útil en `programas_partidos` reemplazando filas de homepage genérica por deeplinks programáticos reproducibles, manteniendo contrato `strict-network` y trazabilidad.

## Cambios implementados
- Script nuevo: `scripts/build_programas_deeplink_manifest.py`
  - entrada: manifest base (`programas_manifest_union_multicycle_plus_pdf_20260228.csv`)
  - salida: manifest curado por scoring de URL + contenido
  - reporte JSON con `probes` por partido/ciclo.
- Tests nuevos:
  - `tests/test_build_programas_deeplink_manifest.py`
- Contrato de ejecución:
  - curation + validate + ingest/backfills + quality/tracker.

## Resultado de curación
- Manifest curado: `docs/etl/sprints/AI-OPS-244/exports/programas_manifest_deeplink_curated_multicycle_20260228.csv`
- Validación: `rows_total=51`, `rows_valid=51`, `valid=true`.
- Curation report:
  - `rows_updated=24`
  - `rows_kept=21`
  - `rows_skipped=6`
  - `failures_total=0`

## Resultado en staging (`strict-network`)
- Run: `run_id=293`, `records_seen=51`, `records_loaded=51`.
- `evidence_inserted=168`.
- Filtro no-programático activo:
  - `skipped.non_program_doc=24`
  - `program_doc_signals={url_program_hint:27, legal_or_cookie_text:16, no_programmatic_signal:8}`.

## KPI delta (baseline AI-OPS-243 post-ignore -> AI-OPS-244 post-ignore)
Fuente: `docs/etl/sprints/AI-OPS-244/exports/programas_status_delta_baseline_vs_post_ignore_20260228.csv`

- `party_proxy_count`: `4 -> 8` (`+4`)
- `topic_evidence_total`: `68 -> 236` (`+168`)
- `topic_evidence_by_stance.support`: `4 -> 37` (`+33`)
- `declared_positions_total`: `4 -> 34` (`+30`)
- `review_pending`: `0 -> 0` (tras cierre explícito de cola)
- Gate declarado final: `passed=true`.
- Tracker enforce: `mismatches=0`, `done_zero_real=0`.

## Estado
- Mejora clara de señal y cobertura útil frente al baseline.
- La lane principal sigue `PARTIAL`: aunque sube a `8` partidos con posición declarada, el DoD del TODO de deeplinks (`party_proxy_count >= 10`) aún no se cumple.
- Próximo gap accionable: elevar cobertura en partidos sin candidate URL válida (EAJ-PNV, SUMAR, UPN, Compromís, PSC, CUP, EQUO) y sustituir deeplinks débiles/antiguos.
