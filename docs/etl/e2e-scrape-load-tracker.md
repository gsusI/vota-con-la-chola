# E2E Scrape/Load Tracker

Objetivo: **una sola lista** de trabajo operativo para completar el extremo a extremo (extract -> transform -> load -> publish) por tipo de dato.

Reglas:
- Marcar `DONE` solo con evidencia (comando/SQL/snapshot) y `records_loaded > 0` en red real (cuando aplique).
- No duplicar este backlog en otros docs (para planificación: `docs/roadmap.md` y `docs/roadmap-tecnico.md`).

Atajos:
- Estado (SQL vs tracker): `just etl-tracker-status`
- Gate (falla si un `DONE` carga 0 en red): `just etl-tracker-gate`

## Definition of Done (por fila)

- Fuente oficial documentada (`source_url`) y contrato real (formatos/IDs).
- Ingesta reproducible (ideal: `--strict-network`; fallback `--from-file` solo si está documentado y con muestras).
- Normalización a esquema canónico con PKs/FKs navegables en Explorer cuando aplique.
- Carga idempotente (upsert) con `source_record_id` estable.
- Validaciones mínimas (incluye `PRAGMA foreign_key_check` sin filas).
- Artefacto publicado o endpoint/UI consumible (según tipo de dato).

## Tracker por tipo de dato

Leyenda:
- `DONE`: listo E2E.
- `PARTIAL`: hay piezas, falta DoD/quality/publish.
- `TODO`: no implementado.

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Representantes y mandatos (Congreso) | Nacional | Congreso OpenData Diputados | DONE | Mejorar calidad de campos opcionales |
| Representantes y mandatos (Cortes de Aragon) | Autonomico | Cortes de Aragon: diputados (XI) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Senado) | Nacional | Senado OpenData XML (grupos + fichas) | DONE | Hardening de aliases y umbral minimo |
| Representantes y mandatos (Europarl) | Europeo | Europarl MEP XML | DONE | Mejorar completitud de fechas/metadatos |
| Representantes y cargos locales | Municipal | RED SARA Concejales | DONE | Definir umbral minimo y criterio de cobertura |
| Representantes y mandatos (Asamblea de Madrid) | Autonomico | Asamblea de Madrid OpenData Ocupaciones | DONE | Definir umbral minimo y aclarar semantica de `is_active` |
| Representantes y mandatos (Asamblea de Ceuta) | Autonomico | Asamblea de Ceuta: miembros (2023/2027) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Asamblea de Melilla) | Autonomico | Asamblea de Melilla: diputados (2023/2027) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Asamblea de Extremadura) | Autonomico | Asamblea de Extremadura (dipslegis + paginacion) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Asamblea Murcia) | Autonomico | Asamblea Regional de Murcia: diputados (listado + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (JGPA Asturias) | Autonomico | Junta General del Principado de Asturias (diputados) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de Canarias) | Autonomico | Parlamento de Canarias: diputados + grupos (API oficial) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de Cantabria) | Autonomico | Parlamento de Cantabria | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de Galicia) | Autonomico | Parlamento de Galicia: deputados (fichas HTML) | PARTIAL | Bloqueado por WAF/403 en `--strict-network`; requiere captura manual Playwright + `--from-file <dir>` |
| Representantes y mandatos (Parlament IB) | Autonomico | Parlament de les Illes Balears: diputats (listado + fichas via webGTP) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de La Rioja) | Autonomico | Parlamento de La Rioja: diputados (listado + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlament de Catalunya) | Autonomico | Parlament de Catalunya (composicio actual + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Corts Valencianes) | Autonomico | Corts Valencianes (listado + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Cortes CLM) | Autonomico | Cortes de Castilla-La Mancha (listado + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Cortes CyL) | Autonomico | Cortes de Castilla y Leon (PlenoAlfabetico) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de Andalucia) | Autonomico | Parlamento de Andalucia (listado + fichas) | DONE | Hardening de parsing y umbral minimo |
| Representantes y mandatos (Parlamento de Navarra) | Autonomico | Parlamento de Navarra: parlamentarios forales (fichas HTML) | PARTIAL | Bloqueado por Cloudflare challenge/403 en `--strict-network`; requiere captura manual Playwright + `--from-file <dir>` |
| Representantes y mandatos (Parlamento Vasco) | Autonomico | Parlamento Vasco (listado ACT) | DONE | Hardening de parsing y umbral minimo |
| Normativa autonómica (piloto 3 CCAA) | Legal | BOCM (Madrid) + DOGC (Catalunya) + BOJA (Andalucía) | TODO | Falta conector y modelo canónico de normas autonómicas (con efectos) con trazabilidad y dedupe por versión |
| Contratación autonómica (piloto 3 CCAA) | Dinero | PLACSP (filtrado por órganos autonómicos) | TODO | Falta estrategia reproducible: ingesta incremental + agregación CPV/órgano/importe; no intentar “leerlo todo” |
| Subvenciones autonómicas (piloto 3 CCAA) | Dinero | BDNS/SNPSAP (filtrado por órgano convocante/territorio) | TODO | Falta ingesta y normalización; entity resolution de beneficiario cuando no haya ID estable |
| Presupuesto + ejecución autonómica (piloto 3 CCAA) | Dinero | Portales presupuestarios autonómicos / IGAE cuando aplique | TODO | Falta conector y crosswalk de clasificaciones; preferir ejecución cuando exista |
| Procesos electorales y resultados | Electoral | Infoelectoral descargas/procesos | DONE | Hardening de parsing de campos opcionales en procesos/resultados |
| Convocatorias y estado electoral | Electoral | Junta Electoral Central | TODO | Falta scraper y normalizacion |
| Marco legal electoral | Legal | BOE API | TODO | Falta conector legal y modelo de documentos |
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
| Contratacion publica (Espana) | Dinero | PLACSP: sindicación/ATOM (CODICE) | TODO | Falta ingesta y modelo de licitacion/adjudicacion; KPI: cobertura + trazabilidad por expediente |
| Subvenciones y ayudas (Espana) | Dinero | BDNS/SNPSAP: API | TODO | Falta ingesta y modelo de convocatorias/concesiones; KPI: % con importe, organo y beneficiario |
| Transparencia: agendas altos cargos | Transparencia | La Moncloa + Portal de Transparencia (agendas) | TODO | Falta ingesta de agendas; KPI: % con fecha + actor resuelto; no inferir accion sin evidencia |
| Transparencia: declaraciones/intereses | Integridad | Portal Transparencia: declaraciones bienes/derechos | TODO | Falta modelo y pipeline de declaraciones; KPI: versionado + trazabilidad 100% |
| Votaciones Congreso | Parlamentario | Congreso votaciones | DONE | Pipeline de calidad y KPIs en verde (`just parl-quality-pipeline`). Linking voto -> iniciativa cubierto con fallback `derived` cuando no hay match oficial; KPI separado para cobertura oficial: `events_with_official_initiative_link_pct` |
| Iniciativas Congreso | Parlamentario | Congreso iniciativas | DONE | Ingesta OK (export del catálogo). Nota: el catálogo no incluye PNL/mociones; los votos sin match oficial se enlazan a iniciativas `derived`. Futuro opcional: incorporar tipos faltantes para subir cobertura oficial |
| Intervenciones Congreso | Parlamentario | Congreso intervenciones | PARTIAL | Conector implementado (`congreso_intervenciones`) y materializa evidencia `declared:intervention` en `topic_evidence` (solo para temas presentes en `topic_set_topics` del Congreso; requiere `backfill-topic-analytics` antes). Comando recomendado (end-to-end “temas + evidencia auditable”): `just parl-temas-pipeline` (incluye `backfill-text-documents` + `backfill-declared-stance` + `backfill-declared-positions`). Estado actual: `backfill-declared-stance` usa regex v2 conservador y alimenta `topic_evidence_reviews` para casos ambiguos; `review-decision` permite cerrar el loop (`pending -> resolved/ignored`) y recomputar posiciones. Pendiente: mejorar cobertura de signal y decidir si las intervenciones necesitan modelo canónico separado de `topic_evidence` o si basta con `topic_evidence + text_documents`. |
| Votaciones Senado y mociones | Parlamentario | Senado votaciones/mociones | DONE | Pipeline de calidad y KPIs en verde; linking determinista a iniciativas por `(legislature, expediente)`; residual de eventos sin roll-call depende de la fuente |
| Referencias territoriales | Catalogos | REL, INE, IGN | DONE | Backfill reproducible: `python3 scripts/ingestar_politicos_es.py backfill-territories --db <db>` (usa `etl/data/published/poblacion_municipios_es.json`) |
| Indicadores (outcomes): INE | Outcomes | INE (API series + metadatos) | TODO | Falta conector y modelo canonico de series/puntos; cachear metadatos/códigos y versionar definiciones |
| Indicadores (outcomes): Eurostat | Outcomes | Eurostat (API/SDMX) | TODO | Falta conector SDMX/JSON; normalizar dimensiones/codelists y documentar mapeos semánticos |
| Indicadores (confusores): Banco de España | Outcomes | Banco de España (API series) | TODO | Falta conector; normalizar códigos y unidades; versionar definiciones por snapshot |
| Indicadores (confusores): AEMET | Outcomes | AEMET OpenData | TODO | Falta conector; mapeo geográfico estación->territorio; cambios de cobertura/metodología |
| Indicadores (confusores): ESIOS/REE | Outcomes | ESIOS/REE API (token) | TODO | Falta conector; gestión de token/cuotas; almacenamiento eficiente para series horarias |
| UE: legislacion y documentos | UE | EUR-Lex / Cellar (SPARQL/REST) | TODO | Falta conector UE legal; linking a expedientes y textos vigentes |
| UE: votaciones (roll-call) | UE | Parlamento Europeo: votes XML/PDF + Open Data Portal | TODO | Falta ingesta de votos + mapeo a MEPs; KPI: % con actor resuelto |
| UE: contratacion publica | UE | TED API (notices) | TODO | Falta ingesta; KPI: cobertura y trazabilidad por notice |
| UE: lobbying/influencia | UE | EU Transparency Register | TODO | Falta ingesta y modelo de entidades; linking cuando existan meetings/agendas publicas |
| Posiciones declaradas (programas) | Editorial | Webs/programas de partidos | TODO | Falta pipeline semiestructurado + revision humana |
| Taxonomia de temas (alto impacto por scope) | Analitica | Definicion de temas + stake scoring por institucion/territorio/mandato | DONE | Seed/versionado: `etl/data/seeds/topic_taxonomy_es.json`. Build: `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db <db> --as-of-date <YYYY-MM-DD> --taxonomy-seed etl/data/seeds/topic_taxonomy_es.json` |
| Evidencia textual (para posiciones declaradas) | Analitica | Diarios de sesiones, intervenciones, preguntas, notas oficiales | DONE | Modelo canónico: `text_documents` (metadata + excerpt) enlazado por `source_record_pk` de `topic_evidence`. Backfill: `python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db <db> --source-id congreso_intervenciones --only-missing` (o `just parl-backfill-text-documents`). Además, copia un snippet a `topic_evidence.excerpt` para que `/explorer-temas` sea auditable sin joins. Nota: stance classification sigue siendo otro paso (ver filas de “Intervenciones”/“Posiciones”). |
| Clasificacion evidencia -> tema (trazable) | Analitica | Reglas deterministas + señales ML opcionales (siempre auditables) | DONE | MVP (votos + intervenciones): evidencia se etiqueta a `topic_id` (votos via `parl_vote_event_initiatives`; intervenciones via `initiative_id`/expediente). KPIs en `/explorer-sources`: `topic_evidence_with_topic_pct` + breakdown por `topic_method`/`stance_method`. |
| Posiciones por tema (politico x scope) | Analitica | Agregacion reproducible + drill-down a evidencia | PARTIAL | MVP: `topic_positions` se llena por método (`computed_method=votes` para does; `computed_method=declared` para says cuando hay signal; `computed_method=combined` como selector KISS: votes si existe, si no declared). Pendiente: ventanas y KPIs de cobertura high-stakes por scope. |
