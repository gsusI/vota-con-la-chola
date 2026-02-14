# E2E Scrape/Load Tracker

Fecha de referencia: **2026-02-12**

Objetivo: tener una lista unica de TODO para completar el E2E de scraping + transform + load + publish para todos los tipos de dato del proyecto.

## Como usar este tracker

1. Marcar tareas con `[x]` solo cuando esten verificadas con evidencia (comando, SQL o snapshot).
2. No cerrar un conector por "status=ok" si `records_loaded=0`.
3. Para cada conector, exigir una corrida `strict-network` y otra con fallback controlado.
4. Mantener este documento como backlog operativo (no en otros sitios duplicados).

## Definicion de Done por conector (obligatoria)

- [ ] Fuente oficial documentada (`source_url`) y contrato de formato real.
- [ ] Extractor robusto (maneja auth, redirects, HTML inesperado, codificacion y delimitadores).
- [ ] Normalizacion a esquema canonico (`persons`, `institutions`, `parties`, `mandates`).
- [ ] Carga idempotente con `source_record_id` estable.
- [ ] Validaciones minimas:
  - [ ] `records_loaded > 0` en run real.
  - [ ] umbral minimo por fuente definido y cumplido.
  - [ ] `raw_fetches` y `ingestion_runs.message` trazables.
- [ ] Snapshot publicado en `etl/data/published/` (o tabla publicada definida).
- [ ] Consulta de verificacion documentada.
- [ ] Recipe de `just` para correr el conector en Docker.

## Estado actual (run de control en DB temporal)

Comandos ejecutados (DB: `etl/data/staging/politicos-es.e2e19.db`):

- `congreso_diputados --strict-network`: `350/350`
- `cortes_aragon_diputados --strict-network`: `75/75` (67 activos + 8 bajas)
- `senado_senadores --strict-network`: `264/264`
- `europarl_meps --strict-network`: `60/60`
- `municipal_concejales --strict-network`: `66895/66895`
- `asamblea_madrid_ocupaciones --strict-network`: `9188/9285`
- `asamblea_ceuta_diputados --strict-network`: `25/25`
- `asamblea_melilla_diputados --strict-network`: `26/26`
- `asamblea_extremadura_diputados --strict-network`: `65/65`
- `asamblea_murcia_diputados --strict-network`: `54/54` (45 activos + 9 bajas)
- `jgpa_diputados --strict-network`: `45/45`
- `parlamento_canarias_diputados --strict-network`: `79/79`
- `parlamento_cantabria_diputados --strict-network`: `35/35`
- `parlament_balears_diputats --strict-network`: `59/59`
- `parlamento_larioja_diputados --strict-network`: `33/33`
- `parlament_catalunya_diputats --strict-network`: `135/135`
- `corts_valencianes_diputats --strict-network`: `99/99`
- `cortes_clm_diputados --strict-network`: `33/33`
- `cortes_cyl_procuradores --strict-network`: `81/81`
- `parlamento_andalucia_diputados --strict-network`: `109/109`
- `parlamento_vasco_parlamentarios --strict-network`: `75/75`

Lectura operativa:

- `congreso_diputados`: operativo.
- `europarl_meps`: operativo.
- `senado_senadores`: operativo con OpenData XML (`tipoFich=4/2/1`) y afiliacion politica real.
- `municipal_concejales`: operativo con endpoint oficial `getConcejalesLegislatura` (XLSX) y parse robusto.
- `asamblea_madrid_ocupaciones`: operativo con CSV oficial (ocupaciones/cargos) y `is_active` calculado con `FECHA_FIN` + legislatura maxima.
- `asamblea_extremadura_diputados`: operativo con scrape HTML (listado `dipslegis` + paginacion) y afiliacion por `Grupo Parlamentario ... (SIGLAS)`.
- `asamblea_melilla_diputados`: operativo con extracción del dataset `dataset_PTS2_MIEMBROS` embebido en JS (`externString`, `descriptionProc`, `isActive`) y `source_record_id` estable por `dboid`.
- `asamblea_murcia_diputados`: operativo con scrape HTML (listado + seccion `Han causado baja`) y afiliacion por `Grupo Parlamentario ...` desde ficha individual.
- `jgpa_diputados`: operativo con scrape HTML (Liferay search container, forzando `delta=50`) y afiliacion por `Grupo Parlamentario ...`.
- `parlamento_canarias_diputados`: operativo con API oficial JSON (por legislatura 11) incluyendo altas/bajas y circunscripcion.
- `parlamento_cantabria_diputados`: operativo con scrape HTML (Drupal) del pleno XI + ficha individual (grupo parlamentario).
- `parlament_balears_diputats`: operativo con scrape HTML (listado ParlamentIB) + fichas legacy `webgtp` (grupo, isla, partido, inicio/fin).
- `parlamento_larioja_diputados`: operativo con scrape HTML (Plone) del listado por grupos parlamentarios (XI Legislatura).
- `parlament_catalunya_diputats`: operativo con scrape HTML (listado + fichas por `p_codi`) y afiliacion (`Partit Polític` + `Grup parlamentari`).
- `corts_valencianes_diputats`: operativo con scrape HTML (listado + fichas con `stable_id` hex) y afiliacion por `Grupo parlamentario`.
- `cortes_clm_diputados`: operativo con scrape HTML (listado legacy PHP + fichas) y afiliacion por `GRUPO PARLAMENTARIO ...`.
- `cortes_cyl_procuradores`: operativo con scrape HTML (listado oficial `PlenoAlfabetico`) y afiliacion por `Grupo Parlamentario` en el listado.
- `parlamento_andalucia_diputados`: operativo con scrape HTML (listado + fichas por `codmie`) y afiliacion por `G.P.` + circunscripcion.
- `parlamento_galicia_deputados`: operativo via fichas HTML (captura manual Playwright + `--from-file <dir>`). `--strict-network` bloqueado por WAF/403 desde ETL (2026-02-12).
- `parlamento_navarra_parlamentarios_forales`: operativo via fichas HTML (captura manual Playwright + `--from-file <dir>`). `--strict-network` bloqueado por Cloudflare challenge/403 desde ETL (2026-02-12).
- `parlamento_vasco_parlamentarios`: operativo con scrape HTML del listado ACT (75 filas) con grupo y fechas.

## Tracker por tipo de dato

Legenda:
- `DONE`: listo E2E.
- `PARTIAL`: hay piezas, pero falta para DoD/quality.
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
| Procesos electorales y resultados | Electoral | Infoelectoral descargas/procesos | DONE | Hardening de parsing de campos opcionales en procesos/resultados |
| Convocatorias y estado electoral | Electoral | Junta Electoral Central | TODO | Falta scraper y normalizacion |
| Marco legal electoral | Legal | BOE API | TODO | Falta conector legal y modelo de documentos |
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
| Contratacion publica (Espana) | Dinero | PLACSP: sindicación/ATOM (CODICE) | TODO | Falta ingesta y modelo de licitacion/adjudicacion; KPI: cobertura + trazabilidad por expediente |
| Subvenciones y ayudas (Espana) | Dinero | BDNS/SNPSAP: API | TODO | Falta ingesta y modelo de convocatorias/concesiones; KPI: % con importe, organo y beneficiario |
| Transparencia: agendas altos cargos | Transparencia | La Moncloa + Portal de Transparencia (agendas) | TODO | Falta ingesta de agendas; KPI: % con fecha + actor resuelto; no inferir accion sin evidencia |
| Transparencia: declaraciones/intereses | Integridad | Portal Transparencia: declaraciones bienes/derechos | TODO | Falta modelo y pipeline de declaraciones; KPI: versionado + trazabilidad 100% |
| Votaciones Congreso | Parlamentario | Congreso votaciones | PARTIAL | Ingesta de votaciones (OpenData) a `parl_vote_events` + `parl_vote_member_votes`; publish canónico disponible (`scripts/publicar_votaciones_es.py`), pendiente corrida completa + KPIs |
| Iniciativas Congreso | Parlamentario | Congreso iniciativas | PARTIAL | Ingesta de iniciativas (export JSON en OpenData) a `parl_initiatives`; linking a `parl_vote_events` mejorado (regex + titulo normalizado), pendiente KPIs globales |
| Intervenciones Congreso | Parlamentario | Congreso intervenciones | TODO | Falta conector y modelo de evidencia textual |
| Votaciones Senado y mociones | Parlamentario | Senado votaciones/mociones | PARTIAL | `senado_votaciones` carga eventos + totales + roll-call (host `www.senado.es`); `senado_iniciativas` (tipoFich=9) carga temas/expedientes y permite linking determinista `(legislature, expediente)`; publish canónico disponible, pendiente KPIs y cobertura `person_id` |
| Referencias territoriales | Catalogos | REL, INE, IGN | TODO | Falta catalogo canonico territorial |
| UE: legislacion y documentos | UE | EUR-Lex / Cellar (SPARQL/REST) | TODO | Falta conector UE legal; linking a expedientes y textos vigentes |
| UE: votaciones (roll-call) | UE | Parlamento Europeo: votes XML/PDF + Open Data Portal | TODO | Falta ingesta de votos + mapeo a MEPs; KPI: % con actor resuelto |
| UE: contratacion publica | UE | TED API (notices) | TODO | Falta ingesta; KPI: cobertura y trazabilidad por notice |
| UE: lobbying/influencia | UE | EU Transparency Register | TODO | Falta ingesta y modelo de entidades; linking cuando existan meetings/agendas publicas |
| Posiciones declaradas (programas) | Editorial | Webs/programas de partidos | TODO | Falta pipeline semiestructurado + revision humana |
| Taxonomia de temas (alto impacto por scope) | Analitica | Definicion de temas + stake scoring por institucion/territorio/mandato | TODO | Falta seed inicial + reglas de versionado + KPI: cobertura de temas high-stakes por scope |
| Evidencia textual (para posiciones declaradas) | Analitica | Diarios de sesiones, intervenciones, preguntas, notas oficiales | TODO | Falta conector(es) + modelo canonico de evidencia textual + KPI: % evidencia con `person_id` y timestamp |
| Clasificacion evidencia -> tema (trazable) | Analitica | Reglas deterministas + señales ML opcionales (siempre auditables) | TODO | Falta pipeline + KPI: % evidencia con `topic_id` + distribucion de confianza/errores |
| Posiciones por tema (politico x scope) | Analitica | Agregacion reproducible + drill-down a evidencia | TODO | Falta agregador + KPI: % politicos con señal suficiente por tema high-stakes + sesgo por tipo de evidencia |

## TODO global (infra y calidad)

- [x] Fallar corrida `strict-network` si `records_seen > 0` y `records_loaded == 0`.
- [x] Detectar payload HTML cuando se espera CSV/JSON/XML y tratarlo como error de extraccion.
- [x] Validar charset real (`latin-1/cp1252`) antes de parse CSV.
- [x] Definir umbrales minimos por fuente en codigo (no solo en docs).  
  `etl/politicos_es/config.py` define `min_records_loaded_strict` y `etl/politicos_es/pipeline.py` aplica la validación en modo `--strict-network`.
- [x] Documentar y estandarizar el “camino manual aceptado” para fuentes bloqueadas por WAF/anti-bot (captura Playwright no-headless + ingesta por `--from-file <dir>`), incluyendo receta `just` y evidencia en tracker.
- [x] Documentar la ventana de backfill histórico (`just etl-backfill-normalized`) como paso de mantenimiento tras cambios de esquema de normalización.
- [x] Crear smoke test E2E en CI (`init-db + ingest por fuente + asserts SQL`).  
  Implementado como camino práctico con `just etl-smoke-e2e`.
- [x] Publicar snapshot canonico de representantes en `etl/data/published/` (ej: `etl/data/published/representantes-es-2026-02-12.json`).
- [x] Implementar publish canónico de votaciones en `etl/data/published/` (script: `scripts/publicar_votaciones_es.py`).
- [x] Implementar publish canónico de procesos de Infoelectoral en `etl/data/published/` (script: `scripts/publicar_infoelectoral_es.py`).
- [x] Documentar versionado de snapshots y politica de refresh.

## TODO por conector activo

### 1) `congreso_diputados` (DONE tecnico, hardening pendiente)

- [x] Discovery de JSON versionado.
- [x] Ingesta real `strict-network`.
- [x] Upsert en esquema actual.
- [x] Anadir validacion de `records_loaded >= 300` como regla hard.
- [ ] Completar/normalizar campos de fecha de fin y metadata adicional (si disponible).

### 2) `senado_senadores` (DONE tecnico, calidad pendiente)

- [x] Extraccion OpenData de grupos (`tipoFich=4`) y miembros por grupo (`tipoFich=2`).
- [x] Resolucion de `idweb` y `source_record_id` estable por senador activo.
- [x] Enriquecimiento con ficha individual (`tipoFich=1`) para afiliacion politica (`partidoSiglas`/`partidoNombre`).
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 250`) en codigo.
- [x] Revisar normalizacion de aliases minoritarios de siglas (`INDEP`, `CCPV`, etc.).

### 3) `europarl_meps` (DONE tecnico, calidad pendiente)

- [x] Parse XML y filtro por Espana.
- [x] Ingesta real `strict-network`.
- [x] Upsert en esquema actual.
- [x] Mejorar mapping de `given_name` / `family_name` si el feed lo permite.
- [x] Definir umbral hard (`records_loaded >= 40`) en codigo.

### 4) `municipal_concejales` (DONE tecnico, calidad pendiente)

- [x] Conector declarado y normalizador preparado para CSV tabular.
- [x] Implementar flujo de descarga real desde `concejales.redsara.es` (`getConcejalesLegislatura`).
- [x] Si la respuesta es HTML, marcar error de extraccion (no parsear como CSV).
- [x] Definir endpoint estable de descarga y parsear XLSX oficial.
- [x] Validar carga real >0 con dataset oficial (`66895/66895` en strict-network).
- [ ] Definir umbral minimo por corrida y criterio de cobertura (municipios/cargos).

### 5) `asamblea_madrid_ocupaciones` (DONE tecnico, calidad pendiente)

- [x] Endpoint oficial CSV accesible en red y con contrato estable.
- [x] Parse y normalizacion a esquema canonico (`persons`, `mandates`, `parties`).
- [x] `is_active` calculado como `legislatura == max(LEGISLATURA)` y `FECHA_FIN` vacia/`-`.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (ej: `records_loaded >= 5000`) en codigo.
- [x] Documentar consulta recomendada para "diputados actuales":
  - `SELECT * FROM mandates WHERE source_id='asamblea_madrid_ocupaciones' AND role_title='Diputado/a' AND is_active=1;`

### 6) `parlament_catalunya_diputats` (DONE tecnico, calidad pendiente)

- [x] Discovery de `p_codi` desde composicion actual.
- [x] Enriquecimiento por ficha individual y parse de `Partit Polític` y `Grup parlamentari`.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 100`) en codigo.
- [x] Hardening del parse de fechas de alta (`Alta: dd.mm.yyyy`) y posibles cambios de etiquetas (ca/es).

### 7) `corts_valencianes_diputats` (DONE tecnico, calidad pendiente)

- [x] Discovery de fichas desde listado oficial (99 perfiles).
- [x] Parse de `Grupo parlamentario` y provincia (circunscripcion) desde ficha.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 70`) en codigo.
- [x] Hardening de parsing si el HTML cambia (clases CSS y headings).

### 8) `parlamento_andalucia_diputados` (DONE tecnico, calidad pendiente)

- [x] Discovery de `codmie/nlegis` desde listado (excluye `Listado de renuncias`).
- [x] Enriquecimiento por ficha de pleno (`codorg=3`) con `G.P.` + `Circunscripción`.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 90`) en codigo.
- [x] Hardening de parsing si el HTML cambia (secciones y headings).

### 9) `parlamento_vasco_parlamentarios` (DONE tecnico, calidad pendiente)

- [x] Extraccion desde listado ACT (tabla HTML) con ids `c_<id>.html`.
- [x] Parse de grupo (`GP XXX`) y fechas `(dd.mm.yyyy - ...)`.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 60`) en codigo.
- [x] Considerar enriquecer con ficha personal (`/fichas/c_<id>_SM.html`) para metadatos extra.

### 10) `cortes_clm_diputados` (DONE tecnico, calidad pendiente)

- [x] Discovery de listado oficial (PHP legacy) por legislatura (`legislatura=11`) con `id` estable.
- [x] Enriquecimiento por ficha individual (`detalle_diputado.php?id=...`) para `GRUPO PARLAMENTARIO ...` y `Fecha Alta` minima.
- [x] Ingesta real `strict-network` con carga >0.
- [x] Definir umbral hard (`records_loaded >= 25`) en codigo.
- [x] Hardening de parsing si el HTML cambia (estructura de tabla y `id=\"grupo\"`).

## TODO nuevos conectores (por prioridad)

### Cobertura pendiente (representacion institucional)

- [ ] Parlamento de Galicia: conector `parlamento_galicia_deputados` disponible (muestras + `--from-file <dir>`), pero `--strict-network` sigue bloqueado por WAF/403: `https://www.parlamento.gal/Composicion/Deputados` (2026-02-12 devuelve 403 desde ETL).
- [ ] Parlamento de Navarra: conector `parlamento_navarra_parlamentarios_forales` disponible (muestras + `--from-file <dir>`), pero `--strict-network` sigue bloqueado por Cloudflare challenge/403: `https://parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales` (2026-02-12 devuelve 403 cf-mitigated).

### P0 (siguiente ola, obligatoria para MVP de evidencia)

- [x] Infoelectoral: completar cobertura de resultados y datasets; publish y recipe `just` implementados; `source` y `resultados` incluidos en `infoelectoral-es-YYYY-MM-DD.json`.
- [ ] Junta Electoral Central: estado de convocatorias.
- [ ] BOE API: normativa/convocatorias.
- [ ] Consejo de Ministros (Moncloa): referencias + RSS (señal comunicacional) con validación por BOE cuando aplique.
- [ ] BDNS/SNPSAP: subvenciones y ayudas (registro con efectos).
- [ ] PLACSP: contratación pública (sindicación ATOM/CODICE) (registro con efectos).
- [ ] Congreso votaciones.
- [ ] Senado votaciones/mociones (cerrar publish y cobertura de `person_id`).

### P1

- [ ] Congreso iniciativas.
- [ ] Congreso intervenciones.
- [ ] Catalogos territoriales (REL/INE/IGN).
- [ ] OEIL / EUR-Lex (contexto UE).
- [ ] Agendas y transparencia (Moncloa + Portal de Transparencia): ingesta de actividad pública.
- [ ] Declaraciones/intereses (Transparencia y registros parlamentarios): modelo y pipeline (sin inferencias).

### P2

- [ ] Programas y webs de partidos con pipeline semiestructurado.
- [ ] Reglas de revision humana minima para contenido sensible/no estructurado.

## Query de control recomendadas

```bash
sqlite3 etl/data/staging/politicos-es.db \
  "SELECT run_id, source_id, status, records_seen, records_loaded, message FROM ingestion_runs ORDER BY run_id DESC LIMIT 20;"

sqlite3 etl/data/staging/politicos-es.db \
  "SELECT source_id, COUNT(*) AS active FROM mandates WHERE is_active=1 GROUP BY source_id ORDER BY source_id;"
```
