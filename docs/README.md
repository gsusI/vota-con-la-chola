# Docs (KISS)

Fuente de verdad (roadmaps):
- `docs/roadmap.md` (visión macro: producto + datos + “acción revelada + impacto”).
- `docs/roadmap-tecnico.md` (ejecución: cerrar “dicen/hacen”, fiabilidad y recomendación).
- Visión y misión canónicas: sección `Visión y misión` en `docs/roadmap.md`.

Backlog operativo (una sola lista):
- `docs/etl/e2e-scrape-load-tracker.md` (conectores + Definition of Done + estado `DONE/PARTIAL/TODO`).

Cómo correr el ETL y la UI:
- `docs/etl/README.md`
- `docs/etl/mechanical-turk-review-instructions.md` (runbook de revisión humana delegada para `topic_evidence_reviews`).
- `docs/etl/sprint-ai-agents.md` (sprint operativo para ejecución por agentes L1/L2/L3).

Contexto mínimo (sin duplicar roadmaps):
- `docs/objetivo.md`
- `docs/principios-operativos.md`
- `docs/arquitectura.md`
- `docs/flow-diagram.md`
- `docs/personas-y-flujos-ideales.md` (north-star de actores, objetivos y flujos ideales)
- `docs/flujos-ui-especificacion.md` (pantallas, botones, interacciones, charts y `URGENT TODO` de datos por flujo)
- `docs/preguntas-metodologia-citizen.md` (Q&A metodologico: preocupaciones, evidencia primaria, hipotesis, dice-vs-hace, granularidad y cambios de postura)
- `docs/database-inventory.md` (inventario de bases de datos del repo y schema por familia/archivo)
- `docs/fuentes-datos.md`
- `docs/domain_taxonomy_es.md`
- `docs/codebook_tier1_es.md`
- `docs/annotation_protocol_es.md`
- `docs/intervention_template_es.md`

Otros:
- `docs/proximas-elecciones-espana.md` (se genera junto a `etl/data/published/proximas-elecciones-espana.json`).
- `ui/gh-pages-next/` es la app Next.js estática que genera el landing de `docs/gh-pages/` en `just explorer-gh-pages-build`.
- `docs/gh-pages/` es salida generada (no editar a mano).
