# Fuentes de datos del proyecto

## Accion politica: definicion operativa (para modelar "hechos")

Una "accion politica" util en datos se modela como un **evento** con:

- `actor`: persona/cargo/organo (diputado, ministro, comision, pleno, etc)
- `tipo_accion`: voto, iniciativa, norma, adjudicacion, subvencion, comparecencia, nombramiento, convenio, modificacion presupuestaria...
- `objeto`: texto normativo / expediente / iniciativa / partida / contrato / subvencion...
- `resultado`: aprobado/rechazado, importe, adjudicatario, enmiendas aceptadas...
- `tiempo`: fecha del acto + fecha de publicacion oficial (si aplica)
- `fuente_primaria`: URL/identificador + `fetched_at` + `content_hash`
- `evidencia`: documento integro (raw) + metadatos (trazabilidad)

Regla practica: para "que han hecho", la fuente canonica suele ser la que **produce efectos** (boletin/registro/acta oficial). Comunicaciones (notas, agendas, RSS) sirven para **deteccion temprana**, pero se validan contra la publicacion oficial cuando exista.

## Escala de fiabilidad de fuente (0-5)

- `5/5` primaria con efectos: boletines oficiales / registros obligatorios con responsabilidad legal (ej: BOE, BDNS, PLACSP, EUR-Lex)
- `4/5` oficial estructurado: open data/datasets exportables con metadatos consistentes (ej: Congreso/Senado OpenData)
- `3/5` oficial comunicacional: notas, "referencias", agendas, RSS (hecho de comunicacion, no efecto juridico)
- `2/5` reutilizador fiable: ONG/academia que deriva de 4-5 (util, pero verificar contra original)
- `1/5` senal: prensa/redes/rumores (alertas, no evidencia)
- `0/5` sin trazabilidad: afirmacion sin fuente verificable

## Inventario operativo

| Prioridad | Dominio | Fuente | URL | Uso principal | Cadencia sugerida | Formato esperado |
|---|---|---|---|---|---|---|
| P0 | Electoral (Espana) | Infoelectoral: area de descargas | https://infoelectoral.interior.gob.es/es/elecciones-celebradas/area-de-descargas/ | Resultados, historico y descargas oficiales | Por proceso / semanal | CSV, ZIP, docs |
| P0 | Electoral (Espana) | Infoelectoral: procesos celebrados | https://infoelectoral.interior.gob.es/es/elecciones-celebradas/procesos-electorales/ | Catalogo oficial de procesos electorales | Semanal | Web/HTML |
| P0 | Definiciones electorales | Metodologia Infoelectoral | https://infoelectoral.interior.gob.es/export/sites/default/pdf/metodologia/Metodologia.pdf | Interpretacion de campos y reglas de datos | Mensual o ante cambios | PDF |
| P0 | Estado de convocatorias | Junta Electoral Central: elecciones actuales | https://www.juntaelectoralcentral.es/cs/jec/elecciones/actuales | Saber que proceso esta convocado/en curso | Diario en periodo electoral | Web/HTML |
| P0 | Marco legal | BOE API datos abiertos | https://www.boe.es/datosabiertos/api/api.php | LOREG, convocatorias y normativa aplicable | Diario | XML/JSON/API |
| P0 | Dinero publico (Espana) | BDNS/SNPSAP (Infosubvenciones): API | https://www.infosubvenciones.es/ | Convocatorias y concesiones de subvenciones/ayudas (registro oficial) | Diario/Semanal | JSON/XML API |
| P0 | Dinero publico (Espana) | PLACSP: sindicación/ATOM (especificacion) | https://www.hacienda.gob.es/Documentacion/Publico/D.G.%20PATRIMONIO/Plataforma_Contratacion/especificacion-sindicacion-1-3.pdf | Licitaciones publicadas en plataforma (registro oficial; sindicación para ingesta) | Diario/Semanal | ATOM/XML (CODICE) + PDF |
| P0 | Actividad parlamentaria (Congreso) | Portal de datos abiertos Congreso | https://www.congreso.es/es/datos-abiertos | Punto de entrada para actividad parlamentaria | Diario/Semanal | Web/API |
| P0 | Actividad parlamentaria (Congreso) | Diputados | https://www.congreso.es/es/opendata/diputados | Actores y metadatos de representantes | Semanal | JSON/XML/CSV |
| P0 | Actividad parlamentaria (Congreso) | Votaciones | https://www.congreso.es/opendata/votaciones | Evidencia de voto para scoring de fiabilidad | Diario/Semanal | JSON/XML/CSV |
| P0 | Actividad parlamentaria (Congreso) | Iniciativas | https://www.congreso.es/es/opendata/iniciativas | Contexto de accion politica | Semanal | JSON/XML/CSV |
| P0 | Actividad parlamentaria (Congreso) | Intervenciones | https://www.congreso.es/es/opendata/intervenciones | Evidencia de posicion declarada institucional | Semanal | JSON/XML/CSV |
| P0 | Actividad parlamentaria (Senado) | Datos abiertos Senado (indice) | https://www.senado.es/web/relacionesciudadanos/datosabiertos/informaciodatosabiertos/index.html | Punto de entrada Senado | Semanal | Web/API |
| P0 | Actividad parlamentaria (Senado) | Votaciones Senado | https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html | Evidencia de voto complementaria | Semanal | CSV/XML/API |
| P0 | Actividad parlamentaria (Senado) | Votaciones de mociones | https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votacionesmociones/index.html | Evidencia adicional por tipo de iniciativa | Semanal | CSV/XML/API |
| P0 | Cobertura municipal | Registro de alcaldes y concejales (RED SARA) | https://concejales.redsara.es/consulta/getConcejalesLegislatura | Cargos municipales (alcaldia y resto de cargos locales) | Semanal | XLSX/Web |
| P0 | Cobertura municipal | Registro de Entidades Locales | https://registroentidadeslocales.mpt.es/ | Catalogo oficial de municipios y codigos de entidad local | Mensual | Web/CSV |
| P1 | Accion ejecutiva (Espana) | Consejo de Ministros: referencias (La Moncloa) | https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx | Señal temprana de decisiones del ejecutivo (confirmar con BOE) | Semanal | Web/HTML + PDF |
| P1 | Accion ejecutiva (Espana) | La Moncloa: RSS | https://www.lamoncloa.gob.es/paginas/varios/rss.aspx | Alertas de publicaciones institucionales | Diario | RSS/XML |
| P1 | Agendas (Espana) | La Moncloa: agenda del Presidente | https://www.lamoncloa.gob.es/presidente/agenda/paginas/index.aspx | Evidencia de actividad publica (no prueba de decision) | Diario | Web/HTML |
| P1 | Agendas (Espana) | Portal Transparencia: agendas altos cargos | https://transparencia.gob.es/publicidad-activa/por-materias/altos-cargos/agendas | Agendas oficiales del gobierno/altos cargos | Diario/Semanal | Web/HTML |
| P1 | Integridad (Espana) | Transparencia: declaraciones bienes y derechos | https://transparencia.gob.es/publicidad-activa/por-materias/altos-cargos/declaraciones-bienes-derechos | Patrimonio/posibles conflictos de interes (formatos variados) | Trimestral/Anual | Web/HTML + PDF |
| P1 | Integridad (Espana) | Transparencia: altos cargos (fichas) | https://transparencia.gob.es/publicidad-activa/por-materias/altos-cargos | Perimetro de altos cargos (CV, retribuciones, etc) | Mensual | Web/HTML |
| P1 | Normativa (pre-BOE) | Transparencia: participacion publica | https://transparencia.gob.es/publicidad-activa/por-materias/normativa-otras-disposiciones/participacion-publica | Consultas previas y audiencias/informacion publica | Semanal | Web/HTML + PDF |
| P1 | Normativa (pre-BOE) | Transparencia: Plan Anual Normativo | https://transparencia.gob.es/publicidad-activa/por-materias/normativa-otras-disposiciones/plan-anual | Inventario anual de iniciativas previstas | Anual | Web/HTML + PDF |
| P1 | Normativa (pre-BOE) | Transparencia: normas en tramitacion | https://transparencia.gob.es/publicidad-activa/por-materias/normativa-otras-disposiciones/normas-tramitacion | Estado de tramitacion de proyectos/anteproyectos | Semanal | Web/HTML + PDF |
| P1 | Presupuesto (Espana) | Transparencia: ejecucion presupuestaria | https://transparencia.gob.es/publicidad-activa/por-materias/informacion-economico-presupuestaria/ejecucion | Ejecucion y seguimiento presupuestario | Mensual/Trimestral | Web/HTML + descargas |
| P1 | Presupuesto (Espana) | Liquidacion del Presupuesto (datos.gob.es) | https://datos.gob.es/es/catalogo/e05188501-liquidacion-del-presupuesto-estado | Serie oficial de liquidacion del Estado | Anual | XLS/CSV/PDF (segun distribucion) |
| P1 | Convenios (Espana) | Transparencia: convenios y encomiendas | https://transparencia.gob.es/publicidad-activa/por-materias/tramites/convenios-encomiendas | Convenios/encomiendas vigentes (AGE) | Mensual | Web/HTML |
| P1 | Inventario/radar | datos.gob.es: API/SPARQL | https://datos.gob.es/es/accessible-apidata | Descubrimiento programatico de datasets (publicadores, distribuciones) | Semanal | JSON/RDF/SPARQL |
| P1 | UE (europeas) | European Parliament data release notes | https://data.europarl.europa.eu/release-notes | Cambios de datasets y contratos de datos UE | Mensual | Web/JSON/RDF |
| P1 | UE (procedimiento legislativo) | OEIL Parlamento Europeo | https://oeil.europarl.europa.eu/ | Trazabilidad de expedientes UE | Semanal | Web/API |
| P1 | UE legal | EUR-Lex data reuse | https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html | Marco legal/documental UE para contexto | Semanal | XML/RDF/API |
| P1 | UE (votos) | Parlamento Europeo: resultados de votaciones | https://www.europarl.europa.eu/plenary/en/votes.html?tab=votes | Evidencia de votos (roll-call cuando exista) | Diario/Semanal | XML/PDF |
| P1 | UE (open data) | Parlamento Europeo: datasets | https://data.europarl.europa.eu/en/datasets | Datasets oficiales (agendas, actas, etc) | Mensual | RDF/JSON/CSV |
| P1 | UE (contratacion) | TED API | https://docs.ted.europa.eu/api/latest/index.html | Notificaciones de contratacion publica UE | Diario/Semanal | JSON API |
| P1 | UE (lobby) | EU Transparency Register | https://transparency-register.europa.eu/index_en | Registro de representantes de intereses (lobby) | Mensual | Web/datasets |
| P1 | Codigos territoriales | INE nomenclator/metodologia | https://www.ine.es/nomenclator/metodologia.htm | Normalizacion territorial y validacion de codigos | Trimestral | Web/PDF |
| P1 | Series INE/API | INE Tempus API base | https://servicios.ine.es/wstempus/js/es/ | Metadatos y series para normalizacion auxiliar | Semanal | JSON API |
| P1 | Geografia administrativa | IGN municipios | https://www.ign.es/resources/ane/Informacion_Geografica_Destacada/IGN_INFOGEO_MUNICIPIOS.html | Referencia geoespacial municipal | Trimestral | SHP/GPKG/CSV |
| P1 | Geografia administrativa | IGN provincias | https://www.ign.es/resources/ane/Informacion_Geografica_Destacada/IGN_INFOGEO_PROVINCIAS.html | Referencia geoespacial provincial | Trimestral | SHP/GPKG/CSV |
| P1 | Representacion autonomica | Parlament de Catalunya: composicio actual + fiches diputats | https://www.parlament.cat/web/composicio/ple-parlament/composicio-actual/index.html | Diputados autonómicos (nombre, partido, grupo, circunscripcion) | Semanal | HTML |
| P1 | Representacion autonomica | Les Corts Valencianes: listado + fichas diputados | https://www.cortsvalencianes.es/es/composicion/diputados | Diputados autonómicos (nombre, grupo, provincia, birthdate parcial) | Semanal | HTML |
| P1 | Representacion autonomica | Cortes de Aragon: diputados (XI, activos + bajas) | https://www.cortesaragon.es/Quienes-somos.2250.0.html?no_cache=1&tx_t3comunicacion_pi3%5Bnumleg%5D=11&tx_t3comunicacion_pi3%5Btipinf%5D=3&tx_t3comunicacion_pi3%5Buidcom%5D=-2#verContenido | Diputados autonómicos (nombre, grupo, activos/bajas) | Semanal | HTML (normalizado a JSON) |
| P1 | Representacion autonomica | Cortes de Castilla-La Mancha: listado diputados (XI) + fichas | https://www.cortesclm.es/web2/paginas/resul_diputados.php?legislatura=11 | Diputados autonómicos (nombre, grupo, provincia, fecha alta minima) | Semanal | HTML |
| P1 | Representacion autonomica | Cortes de Castilla y Leon: procuradores (XI) | https://www.ccyl.es/Organizacion/PlenoAlfabetico | Procuradores autonómicos (nombre, grupo, provincia) | Semanal | HTML |
| P1 | Representacion autonomica | Parlamento de Andalucia: diputados (listado + fichas) | https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do | Diputados autonómicos (nombre, grupo, circunscripcion) | Semanal | HTML |
| P1 | Representacion autonomica | Parlamento Vasco: parlamentarios (listado ACT) | https://www.legebiltzarra.eus/comparla/c_comparla_alf_ACT.html | Parlamentarios autonómicos (nombre, grupo, fechas alta/baja) | Semanal | HTML |
| P1 | Representacion autonomica | Asamblea de Extremadura: diputadas/os (XII) | https://www.asambleaex.es/dipslegis | Diputados autonómicos (nombre, grupo, provincia) | Semanal | HTML |
| P1 | Representacion autonomica | Asamblea de Madrid: OpenData ocupaciones | https://ctyp.asambleamadrid.es/static/doc/opendata/SGP_ADMIN.OPENDATA_OCUPACIONES_ASAMBLEA.csv | Cargos (incluye diputados) con fechas/legislatura | Semanal | CSV |
| P1 | Representacion autonomica | Asamblea de Ceuta: miembros (legislatura 2023/2027) | https://www.ceuta.es/gobiernodeceuta/index.php/el-gobierno/la-asamblea | Miembros de la Asamblea (nombre, grupo/partido) | Semanal | HTML (normalizado a JSON) |
| P1 | Representacion autonomica | Asamblea Regional de Murcia: diputados (activos + bajas) | https://www.asambleamurcia.es/diputados | Diputados autonómicos (nombre, grupo, activos/bajas) | Semanal | HTML |
| P1 | Representacion autonomica | Junta General del Principado de Asturias: diputados/as | https://www.jgpa.es/diputados-y-diputadas | Diputados autonómicos (nombre, grupo) | Semanal | HTML |
| P1 | Representacion autonomica | Parlament de les Illes Balears: diputats (listado + fichas via webGTP) | https://www.parlamentib.es/Representants/Diputats.aspx?criteria=0 | Diputados autonomicos (nombre, partido, grupo, isla) con ficha legacy `webgtp` | Semanal | HTML |
| P1 | Representacion autonomica | Parlamento de Canarias: diputados + grupos (API oficial) | https://parcan.es/api/diputados/por_legislatura/11/?format=json | Diputados autonomicos (id estable, partido, circunscripcion, fechas) + grupos parlamentarios | Semanal | JSON/CSV |
| P1 | Representacion autonomica | Parlamento de Cantabria: diputados (XI) | https://parlamento-cantabria.es/informacion-general/composicion/11l-pleno-del-parlamento-de-cantabria | Diputados autonómicos (nombre, grupo) | Semanal | HTML |
| P1 | Representacion autonomica | Parlamento de La Rioja: diputados (listado + fichas) | https://adminweb.parlamento-larioja.org/composicion-y-organos/diputados | Diputados autonomicos (nombre, grupo parlamentario) | Semanal | HTML (JSON embebido en home/hemiciclo) |
| P1 | Representacion autonomica | Parlamento de Galicia: deputados (WAF/403 desde ETL) | https://www.parlamento.gal/Composicion/Deputados | Diputados autonómicos (nombre, partido/grupo) | Semanal | HTML |
| P1 | Representacion autonomica | Parlamento de Navarra: parlamentarios forales (Cloudflare challenge/403 desde ETL) | https://parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales | Parlamentarios forales (nombre, partido/grupo) | Semanal | HTML |
| P1 | Representacion autonomica | Asamblea de Melilla (pendiente discovery) | https://bomemelilla.es/ | Fuente oficial candidata para listado nominal (BOME) | Mensual/por cambios | PDF/HTML |
| P1 | Cobertura local/autonomica | FAQ locales Infoelectoral (alcance) | https://infoelectoral.interior.gob.es/eu/proceso-electoral/preguntas-frecuentes/tipos-de-elecciones/elecciones-locales/ | Delimitar que requiere conectores por CCAA/institucion | Cuando cambie normativa | Web/HTML |
| P2 | Posiciones declaradas | Programas y webs oficiales de partidos/candidaturas | (variable por partido) | Capturar "lo que dicen" para gap discurso-accion | Por campana / mensual | HTML/PDF |
| P2 | Enriquecimiento (no oficial) | Wikidata Query Service | https://query.wikidata.org/ | IDs estables y enlaces (verificar hechos criticos con fuentes 4-5) | Mensual | SPARQL/JSON |
| P2 | Enriquecimiento (no oficial) | Civio: BOE nuestro de cada dia | https://civio.es/el-boe-nuestro-de-cada-dia/ | Deteccion/alertas y capa editorial (verificar contra BOE) | Diario/Semanal | Web |
| P2 | Enriquecimiento (no oficial) | Integrity Watch Spain | https://www.integritywatch.es/senadores.php | Dataset/visualizacion derivada (verificar contra fuente original) | Mensual | Web |
| P2 | Señal mediática | GDELT | https://www.gdeltproject.org/ | Termometro de narrativa/cobertura (no evidencia) | Diario | API |
| P2 | Señal mediática | Media Cloud | https://www.mediacloud.org/documentation | Archivo/analitica de noticias (no evidencia) | Diario | API |

## Inventario ideal (ambicioso)

Además del inventario operativo (P0/P1/P2), mantenemos un inventario ideal, exhaustivo y programable, para “lo que dicen vs lo que hacen”:

- `docs/ideal_sources_say_do.json`

Ese inventario se muestra también en `explorer-sources` para que el roadmap tenga siempre un “north star”.

## Inventario ideal (ambicioso)

Además del inventario operativo (P0/P1/P2), mantenemos un inventario ideal, exhaustivo y programable, para “lo que dicen vs lo que hacen”:

- `docs/ideal_sources_say_do.json`

Ese inventario se muestra también en `explorer-sources` para que el roadmap tenga siempre un “north star”.

## Criterio de uso (lean)

1. Empezar solo con `P0` para el MVP.
2. Incorporar `P1` cuando el flujo P0 sea estable.
3. Tratar `P2` como capa editorial asistida, no automatica sin revision humana.

## Regla de "doble entrada" (evidencia vs efecto)

Para no confundir “lo comunicado” con “lo efectivo”, cuando exista un registro con efectos se aplica doble entrada:

- Consejo de Ministros (referencias/comunicado) -> validar con BOE (publicacion).
- Nota/portal institucional de adjudicacion -> validar con PLACSP (expediente publicado).
- Anuncio de ayuda/subvencion -> validar con BDNS/SNPSAP (registro oficial).

En el modelo de evidencia, esto permite aumentar confianza de un evento cuando se puede enlazar a la publicacion primaria.

## Ubicacion sugerida en ETL

- `etl/data/raw/`: descargas brutas por fuente y fecha.
- `etl/data/staging/`: datos normalizados y validados.
- `etl/data/published/`: snapshots canónicos consumidos por app/API.

## Metodo para enumerar fuentes "subnacionales" sin dejar agujeros (CCAA + local)

En vez de intentar listar miles de URLs a mano, usar un metodo reproducible:

1. **Arranque por catalogos**: consultar `datos.gob.es` (API/SPARQL) para extraer `publishers`, portales y distribuciones (CSV/JSON/XML/RSS).
2. **Descubrimiento por patrones** (por administracion): boletin oficial, parlamento/camara, transparencia, perfil del contratante, subvenciones, datos abiertos.
3. **Medir completitud** con contadores por dominio. Contadores sugeridos: normativa publicada; actividad parlamentaria/votaciones (si aplica); presupuesto/ejecucion; contratacion; subvenciones; agendas/transparencia.
4. **Mantener un inventario maestro vivo** (tabla/CSV interno) con: metodo de acceso, formatos, cobertura, latencia, fiabilidad (0-5), ids/joins posibles, y riesgos (cambios de esquema, sobrescritura, WAF, etc).

## Votos y temas: que datos hacen falta (por nivel)

Objetivo: poder responder a "que tema se voto" y "como voto cada representante" cuando exista voto nominal/roll-call.

Minimo comun (cualquier camara):

- Censo de representantes por legislatura/mandato: ids estables, nombre, grupo/partido, fechas (alta/baja).
- Catalogo de items votables ("temas"): iniciativas/expedientes (id estable), titulo/objeto, tipo, estado, enlaces a diario/boletin.
- Eventos de votacion: fecha, sesion, numero, contexto (orden del dia) y totales.
- Voto por miembro (si existe): id del miembro (ideal) o nombre + grupo + opcion de voto.
- Vinculo voto <-> expediente/iniciativa: idealmente via id/expediente en el payload; si no existe, guardar metodo+evidencia (matching determinista o manual).

Cobertura por nivel (fuentes tipicas):

- Europeo:
  - Parlamento Europeo: roll-call votes + metadatos de dossiers (temas) + MEP roster.
  - Consejo UE: resultados de votacion suelen ser por Estado miembro (no por politico individual).
- Nacional (Espana):
  - Congreso: `opendata/votaciones` (votos) + `opendata/iniciativas` (temas/expedientes) + `opendata/intervenciones` (contexto textual).
  - Senado: catalogo de datos abiertos (votaciones, mociones) + roster de senadores.
- Autonomico:
  - Parlamentos con votacion electronica/nominativa: actas/DS/diarios con listados de votos, o datasets (si existen).
  - Si solo hay votacion por asentimiento o por grupos, no se puede atribuir a individuo: guardar como voto no-nominal.
- Provincial/insular/municipal:
  - Plenos (actas y acuerdos) + grabaciones; el voto nominal individual suele ser raro.
  - Cuando exista (voto nominal en acta), se puede extraer; si no, solo voto por grupo o resultado agregado.
