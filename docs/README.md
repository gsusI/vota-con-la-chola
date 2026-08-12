# Docs (KISS)

Fuente de verdad (roadmaps):
- `ROADMAP.md` (futuro, secuencia y prioridades canónicas).
- `docs/roadmap.md` (visión macro, modelo y arquitectura de producto/datos).
- `docs/roadmap-tecnico.md` (ejecución derivada; no introduce scope nuevo por su cuenta).
- Visión y misión canónicas: `ROADMAP.md` + sección `Visión y misión` en `docs/roadmap.md`.

Backlog operativo (una sola lista):
- `docs/etl/e2e-scrape-load-tracker.md` (conectores + criterio de cierre (Definition of Done, DoD) + estado `DONE/PARTIAL/TODO`).
- Índice único de TODO: `docs/todo/README.md` (punto de entrada; sin duplicar backlog ni roadmap).

Cómo correr el ETL y la UI:
- `docs/etl/README.md`
- `docs/etl/object-storage.md` (contrato/runbook del origin durable para documentos).
- `docs/etl/mechanical-turk-review-instructions.md` (runbook de revisión humana delegada para `topic_evidence_reviews`).
- `docs/etl/sprint-ai-agents.md` (sprint operativo para ejecución por agentes L1/L2/L3).

Contexto mínimo (sin duplicar roadmaps):
- `docs/objetivo.md`
- `docs/principios-operativos.md`
- `docs/arquitectura.md`
- `docs/flow-diagram.md`
- `docs/personas-y-flujos-ideales.md` (visión north star de actores, objetivos y flujos ideales)
- `docs/flujos-ui-especificacion.md` (pantallas, botones, interacciones, gráficas y `URGENT TODO` de datos por flujo)
- `docs/preguntas-metodologia-citizen.md` (Q&A metodológico: preocupaciones, evidencia primaria, hipótesis, dice-vs-hace, granularidad y cambios de postura)
- `docs/database-inventory.md` (inventario de bases de datos del repo y esquema por familia/archivo)
- `docs/fuentes-datos.md`
- `docs/domain_taxonomy_es.md`
- `docs/codebook_tier1_es.md`
- `docs/annotation_protocol_es.md`
- `docs/intervention_template_es.md`

Otros:
- `docs/method/truth-contract.md` (contrato de evidencia, incertidumbre, cobertura y frescura).
- `docs/method/integrity-signal-policy.md` (gates de publicación, revisión y corrección para señales de riesgo).
- `CODE_OF_CONDUCT.md`, `SECURITY.md` y `CITATION.cff` (confianza y reutilización comunitaria).
- `docs/proximas-elecciones-espana.md` (se genera junto a `etl/data/published/proximas-elecciones-espana.json`).
- `ui/gh-pages-next/` es la app Next.js estática que genera el sitio público de Cloudflare Pages con `just cloudflare-pages-build`.
- `ui/gh-pages-next/out/` es salida generada para Cloudflare Pages; no editar a mano ni versionar.
