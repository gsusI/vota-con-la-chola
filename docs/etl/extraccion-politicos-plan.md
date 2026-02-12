# Plan de extraccion (fuente por fuente)

Fecha de referencia operativa: **2026-02-12**

## Objetivo
Extraer e ingerir politicos en SQLite de forma reproducible, con trazabilidad y ejecucion automatizable por colaborador.

## Estrategia por fuente

1. `congreso_diputados` (prioridad P0)
- Origen: `https://www.congreso.es/es/opendata/diputados`
- Metodo: discovery del JSON versionado `DiputadosActivos__YYYYMMDDhhmmss.json` y descarga del ultimo.
- Modo: `strict-network` (sin fallback), porque la fuente responde correctamente.
- Validacion minima: `records_loaded > 300`.

2. `senado_senadores` (prioridad P0)
- Origen oficial: OpenData Senado (`tipoFich=4` grupos/partidos, `tipoFich=2` miembros por grupo, `tipoFich=1` ficha individual).
- Metodo: extraccion compuesta para resolver `idweb` y enriquecer partido real por senador activo.
- Modo: `strict-network` recomendado para control E2E.
- Validacion minima: `records_loaded > 250` y cobertura de `party_id` al 100% en mandatos activos del Senado.

3. `europarl_meps` (prioridad P1)
- Origen: `https://www.europarl.europa.eu/meps/es/full-list/xml`
- Metodo: parse XML de MEPs y filtro por pais Espana.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 40`.

4. `municipal_concejales` (prioridad P1)
- Origen base: `https://concejales.redsara.es/consulta/getConcejalesLegislatura`.
- Cobertura: cargos electos y de gobierno municipal en formato tabular (alcaldia, tenencias, concejalias delegadas, portavocias, etc.).
- Metodo: parse de XLSX oficial (con deteccion de fila de cabeceras) y tolerancia a variantes de cabeceras para fallback CSV (`cargo`, `municipio`, `codigo_ine`, etc.).
- Modo: intento de red primero y fallback local (`etl/data/raw/samples/municipal_concejales_sample.csv`) si falla conectividad.
- Validacion minima: `records_loaded > 0` y presencia de `level=municipal` en `mandates`.

5. `asamblea_madrid_ocupaciones` (prioridad P1)
- Origen: Asamblea de Madrid OpenData (CSV): `https://ctyp.asambleamadrid.es/static/doc/opendata/SGP_ADMIN.OPENDATA_OCUPACIONES_ASAMBLEA.csv`.
- Metodo: parse CSV + calculo de la legislatura mas reciente y marcado de `is_active` usando `FECHA_FIN`.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 0` y `mandates_active` > 0 (y para `role_title='Diputado/a'` se espera ~135 activos).

5b. `asamblea_extremadura_diputados` (prioridad P1)
- Origen: listado (HTML) + paginacion: `https://www.asambleaex.es/dipslegis` (`dipslegis-12-ALTA-{offset}`).
- Metodo: crawl de offsets (20 por pagina) y parse de `verdiputado-{id}` + `Grupo Parlamentario` + provincia.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 50` (se espera 65).

5b2. `asamblea_murcia_diputados` (prioridad P1)
- Origen: listado (HTML): `https://www.asambleamurcia.es/diputados` (incluye seccion `Han causado baja`) + fichas: `/diputado/<id>/<slug>`.
- Metodo: parse de IDs desde el listado y extraccion de `Grupo Parlamentario` desde la ficha individual; `is_active` segun seccion del listado.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 35` (se esperan >45 incluyendo bajas; activos ~45).

5c. `jgpa_diputados` (prioridad P1)
- Origen: listado (HTML, Liferay) con paginacion: `https://www.jgpa.es/diputados-y-diputadas` (forzando `delta=50`).
- Metodo: parse de listado por entradas (`<li class='entry'>`) para extraer `diputadoId` (ID estable) y grupo parlamentario.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 35` (se espera 45).

5d. `parlamento_canarias_diputados` (prioridad P1)
- Origen: API oficial (JSON): `https://parcan.es/api/diputados/por_legislatura/11/?format=json`.
- Metodo: descarga JSON directa y normalizacion de `alta_cargo/baja_cargo`, `circunscripcion` y `alias_grupo/grupo`.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 60` (se esperan >70 incluyendo altas/bajas de la legislatura).

5d2. `parlamento_cantabria_diputados` (prioridad P1)
- Origen: listado del pleno XI (HTML): `https://parlamento-cantabria.es/informacion-general/composicion/11l-pleno-del-parlamento-de-cantabria` + fichas Drupal individuales.
- Metodo: discovery de links `11l-<slug>` desde el pleno y enriquecimiento desde la ficha (grupo parlamentario, node id).
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 25` (se espera 35).

5e. `parlament_balears_diputats` (prioridad P1)
- Origen: listado ParlamentIB (HTML): `https://www.parlamentib.es/Representants/Diputats.aspx?criteria=0` + fichas legacy `web.parlamentib.es/webgtp`.
- Metodo: parse de `showDiputado(CFautor, CFTract, CFnom, CFcongnoms)` desde el listado y enriquecimiento por ficha `UnRegPers.asp` (seleccionando rol `DIPUTAT` en legislatura 11).
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 45` (se espera 59).

5f. `parlamento_larioja_diputados` (prioridad P1)
- Origen: listado por grupos (HTML): `https://adminweb.parlamento-larioja.org/composicion-y-organos/diputados` (XI Legislatura).
- Metodo: parse de bloques por `Grupo Parlamentario` y discovery de slugs de ficha por diputado.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 25` (se espera 33).

6. `parlament_catalunya_diputats` (prioridad P1)
- Origen: composicion actual (HTML) + fichas por diputado (HTML): `https://www.parlament.cat/web/composicio/ple-parlament/composicio-actual/index.html`.
- Metodo: discovery de `p_codi` desde la pagina de composicion y fetch de fichas `diputats-fitxa` para extraer `Partit Polític`, `Grup parlamentari` y circumscripcion.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 100` (se espera ~135).

7. `corts_valencianes_diputats` (prioridad P1)
- Origen: listado de diputados (HTML) + ficha por diputado (HTML): `https://www.cortsvalencianes.es/es/composicion/diputados`.
- Metodo: discovery de URLs de ficha desde el listado y parse de `Grupo parlamentario` + provincia desde HTML.
- ID estable: `stable_id` hex (ultimo segmento del path) + legislatura.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 70` (se espera 99).

8. `parlamento_andalucia_diputados` (prioridad P1)
- Origen: listado + fichas (HTML): `https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do`.
- Metodo: discovery de `codmie/nlegis` desde el listado (solo seccion de diputados; excluye renuncias) y parse de ficha de pleno (`codorg=3`) para `G.P.` + circunscripcion.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 90` (se espera 109).

9. `parlamento_vasco_parlamentarios` (prioridad P1)
- Origen: listado ACT (HTML): `https://www.legebiltzarra.eus/comparla/c_comparla_alf_ACT.html`.
- Metodo: parse de tabla HTML (id + grupo + fechas) desde listado; opcionalmente enriquecer con ficha personal.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 60` (se espera 75).

10. `cortes_clm_diputados` (prioridad P1)
- Origen: listado legacy (PHP): `https://www.cortesclm.es/web2/paginas/resul_diputados.php?legislatura=11` + ficha individual: `https://www.cortesclm.es/web2/paginas/detalle_diputado.php?id=...`.
- Metodo: parse de listado (id, nombre, provincia, grupo) y enriquecimiento por ficha (grupo completo + `Fecha Alta` minima).
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 25` (se espera 33).

11. `cortes_cyl_procuradores` (prioridad P1)
- Origen: listado oficial (HTML): `https://www.ccyl.es/Organizacion/PlenoAlfabetico`.
- Metodo: parse de listado alfabético para extraer `CodigoPersona` (ID estable), `Grupo Parlamentario` y provincia.
- Modo: `strict-network`.
- Validacion minima: `records_loaded > 70` (se espera 81).

## Ejecucion operativa (Docker)

```bash
just etl-build
just etl-init
just etl-extract-congreso
just etl-extract-senado
just etl-extract-europarl
just etl-extract-municipal
just etl-extract-asamblea-madrid
just etl-extract-asamblea-extremadura
just etl-extract-asamblea-murcia
just etl-extract-jgpa
just etl-extract-parlamento-canarias
just etl-extract-parlamento-cantabria
just etl-extract-parlament-balears
just etl-extract-parlamento-larioja
just etl-extract-parlament-catalunya
just etl-extract-corts-valencianes
just etl-extract-cortes-clm
just etl-extract-cortes-cyl
just etl-extract-parlamento-andalucia
just etl-extract-parlamento-vasco
just etl-stats
```

Flujo completo en un solo comando:

```bash
just etl-e2e
```

## Criterios de exito end-to-end

1. `ingestion_runs` registra 18 ejecuciones en estado `ok`.
2. `raw_fetches` registra 18 entradas (una por fuente procesada).
3. `mandates_active` coincide con la suma de activos por fuente.
4. En caso de fallback, queda trazado en `ingestion_runs.message`.

## SQL de control rapido

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, source_id, status, records_loaded, message FROM ingestion_runs ORDER BY run_id DESC LIMIT 10;"
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) total FROM mandates WHERE is_active=1 GROUP BY source_id ORDER BY source_id;"
```
