# Fuentes de datos del proyecto

## Inventario operativo

| Prioridad | Dominio | Fuente | URL | Uso principal | Cadencia sugerida | Formato esperado |
|---|---|---|---|---|---|---|
| P0 | Electoral (Espana) | Infoelectoral: area de descargas | https://infoelectoral.interior.gob.es/es/elecciones-celebradas/area-de-descargas/ | Resultados, historico y descargas oficiales | Por proceso / semanal | CSV, ZIP, docs |
| P0 | Electoral (Espana) | Infoelectoral: procesos celebrados | https://infoelectoral.interior.gob.es/es/elecciones-celebradas/procesos-electorales/ | Catalogo oficial de procesos electorales | Semanal | Web/HTML |
| P0 | Definiciones electorales | Metodologia Infoelectoral | https://infoelectoral.interior.gob.es/export/sites/default/pdf/metodologia/Metodologia.pdf | Interpretacion de campos y reglas de datos | Mensual o ante cambios | PDF |
| P0 | Estado de convocatorias | Junta Electoral Central: elecciones actuales | https://www.juntaelectoralcentral.es/cs/jec/elecciones/actuales | Saber que proceso esta convocado/en curso | Diario en periodo electoral | Web/HTML |
| P0 | Marco legal | BOE API datos abiertos | https://www.boe.es/datosabiertos/api/api.php | LOREG, convocatorias y normativa aplicable | Diario | XML/JSON/API |
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
| P1 | UE (europeas) | European Parliament data release notes | https://data.europarl.europa.eu/release-notes | Cambios de datasets y contratos de datos UE | Mensual | Web/JSON/RDF |
| P1 | UE (procedimiento legislativo) | OEIL Parlamento Europeo | https://oeil.europarl.europa.eu/ | Trazabilidad de expedientes UE | Semanal | Web/API |
| P1 | UE legal | EUR-Lex data reuse | https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html | Marco legal/documental UE para contexto | Semanal | XML/RDF/API |
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

## Criterio de uso (lean)

1. Empezar solo con `P0` para el MVP.
2. Incorporar `P1` cuando el flujo P0 sea estable.
3. Tratar `P2` como capa editorial asistida, no automatica sin revision humana.

## Ubicacion sugerida en ETL

- `etl/data/raw/`: descargas brutas por fuente y fecha.
- `etl/data/staging/`: datos normalizados y validados.
- `etl/data/published/`: snapshots canónicos consumidos por app/API.

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
