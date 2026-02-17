# Sprint AI-OPS-03 Kickoff

Fecha de baseline: 2026-02-16
Alcance de sprint (cerrado): `congreso_intervenciones` (sin abrir nuevas familias de fuentes).

## Objetivo del sprint

Mover el bloque de `congreso_intervenciones` y su capa analítica (`topic_evidence`/`topic_positions`) desde estado operativo `PARTIAL` hacia gates de calidad/publicación más cercanos a `DONE`, manteniendo KISS (SQLite único, trazabilidad completa, snapshots reproducibles).

## Baseline (comandos y salidas exactas)

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Salida exacta:

```text
0
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"
```

Salida exacta:

```text
0
```

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 15) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
```

Salida exacta:

```text
614|199|0.324104234527687
```

Comando:

```bash
python3 - <<'PY'
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload
p=Path('etl/data/staging/politicos-es.db')
s=build_topics_coherence_payload(p, limit=5, offset=0).get('summary', {})
print(s)
PY
```

Salida exacta:

```text
{'groups_total': 26, 'overlap_total': 153, 'explicit_total': 98, 'coherent_total': 51, 'incoherent_total': 47, 'coherence_pct': 0.5204081632653061, 'incoherence_pct': 0.47959183673469385}
```

Interpretación operativa:
- Integridad referencial: en verde.
- Cola de revisión: sin `pending`.
- Señal declarada: baseline actual de referencia para mejora incremental (`199/614`).
- Coherencia says-vs-does: ya existe señal útil (`overlap > 0`) y sirve de KPI de estabilidad.

## Alineación con roadmap (macro + técnico + tracker + closeout previo)

Documentos leídos:
- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-02/closeout.md`

Traducción a ejecución AI-OPS-03:
- `roadmap.md`: mantener slice vertical auditable (evidencia -> posiciones -> visibilidad dashboard) sin expandir dominio de fuentes.
- `roadmap-tecnico.md`: reforzar Fase 2 (posiciones públicas y coherencia) y publicación de KPIs reproducibles.
- `e2e tracker`: atacar bloqueadores explícitos de filas PARTIAL (`Intervenciones Congreso`, `Posiciones por tema`).
- `AI-OPS-02 closeout`: mantener restricción de una sola familia y cerrar brechas de `as_of_date` + publish parity.

## Secuencia ordenada de ejecución

1. Congelar baseline y gates de aceptación de sprint (este documento).
2. Alinear `as_of_date` en pipeline de analytics/positions para evitar drift entre sets.
3. Mejorar extractor de stance declarada con regresión anti-falsos positivos.
4. Ejecutar recompute completo del slice `congreso_intervenciones` (`text -> stance -> declared -> combined`).
5. Preparar/aplicar lotes MTurk orientados a casos de alto valor ambiguo.
6. Refrescar snapshot de `explorer-sources` y validar paridad live DB vs export.
7. Actualizar evidencia reproducible y reconciliar texto de filas PARTIAL en tracker.
8. Ejecutar closeout con decisión PASS/FAIL de AI-OPS-03.

## Gates del sprint (mapeados a fases del roadmap)

1. `fk_violations = 0`  
   - Mapea a `roadmap-tecnico` Fase 0 (base de calidad e integridad).
2. `topic_evidence_reviews pending = 0`  
   - Mapea a `roadmap-tecnico` Fase 2 (control de ambigüedad + revisión humana).
3. `declared_signal_pct` mejora vs baseline kickoff (`0.324104234527687`)  
   - Mapea a `roadmap-tecnico` Fase 2 (calidad de señal declarada).
4. Coherencia con `overlap > 0` y drill-down con filas de evidencia  
   - Mapea a Fase 2 (coherencia) y Fase 3 (explicabilidad).
5. Filas PARTIAL de analytics reconciliadas con evidencia y siguiente paso explícito  
   - Mapea a disciplina operativa del tracker (ruta crítica de ejecución).
6. Snapshot estático de `explorer-sources` en paridad con métricas live  
   - Mapea a publicación reproducible (`roadmap.md` producto trazable + `roadmap-tecnico` publicación/KPIs).

## Criterio de salida

AI-OPS-03 listo para cierre cuando los 6 gates estén en verde con evidencia reproducible (comando + salida + artefacto markdown), sin romper la restricción de alcance a `congreso_intervenciones`.
