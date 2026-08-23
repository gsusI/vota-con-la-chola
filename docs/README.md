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
- `docs/ops/reproducibility.md` (manifest content-addressed, firma ed25519, trust root, diff y verificación live).
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
- `docs/data-model/core-ontology-v1.md` + `.json` (vocabulario estable, IDs, tiempo, provenance, relaciones y scale contract compartido).
- `docs/data-model/promises-spec-v1.md` (claims, promesas, ambigüedad, evidencia exacta, revisión, idempotencia y escala).
- `docs/data-model/spending-spec-v1.md` (presupuesto, procurement, award, contrato, factura, pago, entrega, importe exacto, actores, evidencia y escala).
- `docs/data-model/agreements-influence-spec-v1.md` (acuerdos, reuniones, lobbying, agenda, actores, evidencia y separación estricta de influencia inferida).
- `docs/data-model/geopolitics-spec-v1.md` (tratados, resoluciones, sanciones, ayuda, defensa, votos internacionales, posiciones temporales, evidencia y disciplina de inferencia).
- `docs/data-model/indicators-spec-v1.md` (definiciones, releases, geografía, intervalos, valores exactos, estados estadísticos, incertidumbre, revisiones y provenance a escala).
- `docs/api/evidence-api-v1.md` + `.schema.json` (contrato público estable, paginado, versionado y content-addressed).
- `docs/architecture/plugin-system-v1.md` + `plugin-manifest-v1.schema.json` (tipos, hooks, manifest, seguridad, escala y gates de plugins).
- `docs/architecture/entity-resolution-v1.md` (grafo temporal source-scoped, resolución de identidad, aliases, coaliciones, merger/split, evidencia, fallos y scale contract).
- `docs/examples/sample-plugin.md` (SDK y plugin Congreso reproducible sobre captura oficial real; sin mock ni anonimización).
- `docs/examples/placsp-actor-spending-evidence.sql` (consulta reproducible actor -> adjudicación -> evidencia oficial).
- `docs/examples/moncloa-actor-agreement-evidence.sql` (consulta reproducible actor -> acuerdo -> reunión -> evidencia oficial, sin inferir asistencia o influencia).
- `docs/examples/moncloa-geopolitical-action-evidence.sql` (consulta reproducible actor -> acción exterior -> etapa -> evidencia oficial, sin inferir vigencia, alineamiento o impacto).
- `docs/examples/eurostat-indicator-observation-evidence.sql` (consulta reproducible indicador -> territorio -> periodo -> valor/status -> celda oficial).
- `docs/examples/actor-graph-evidence.sql` (consulta reproducible actor -> relación temporal -> contexto -> evidencia, sin merge por nombre ni inferencia causal).
- `CODE_OF_CONDUCT.md`, `SECURITY.md` y `CITATION.cff` (confianza y reutilización comunitaria).
- `docs/proximas-elecciones-espana.md` (se genera junto a `etl/data/published/proximas-elecciones-espana.json`).
- `ui/gh-pages-next/` es la app Next.js estática que genera el sitio público de Cloudflare Pages con `just cloudflare-pages-build`.
- `ui/gh-pages-next/out/` es salida generada para Cloudflare Pages; no editar a mano ni versionar.
