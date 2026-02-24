# Download Catalog (from raw_fetches)

- Generated (UTC): 2026-02-21 09:26:35 UTC
- Database: `etl/data/staging/politicos-es.db`
- Configured sources: 44
- Logged fetch rows: 101
- Distinct network URLs fetched: 39

## Network URLs Fetched In This Snapshot

| source_id | host | source_url | url_ext | logged_content_type(s) | fetch_count |
| --- | --- | --- | --- | --- | ---: |
| asamblea_ceuta_diputados | www.ceuta.es | `https://www.ceuta.es/gobiernodeceuta/index.php/el-gobierno/la-asamblea` | (no_ext) | application/json | 1 |
| asamblea_extremadura_diputados | www.asambleaex.es | `https://www.asambleaex.es/dipslegis` | (no_ext) | application/json | 1 |
| asamblea_madrid_ocupaciones | ctyp.asambleamadrid.es | `https://ctyp.asambleamadrid.es/static/doc/opendata/SGP_ADMIN.OPENDATA_OCUPACIONES_ASAMBLEA.csv` | csv | text/csv | 1 |
| asamblea_melilla_diputados | sede.melilla.es | `https://sede.melilla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_MIEMBROS` | (no_ext) | application/json | 1 |
| asamblea_murcia_diputados | www.asambleamurcia.es | `https://www.asambleamurcia.es/diputados` | (no_ext) | application/json | 1 |
| bdns_api_subvenciones | www.pap.hacienda.gob.es | `https://www.pap.hacienda.gob.es/bdnstrans/api/convocatorias/ultimas` | (no_ext) | application/json | 1 |
| bdns_autonomico | www.pap.hacienda.gob.es | `https://www.pap.hacienda.gob.es/bdnstrans/api/convocatorias/busqueda` | (no_ext) | application/json | 1 |
| boe_api_legal | www.boe.es | `https://www.boe.es/rss/boe.php` | php | application/json | 1 |
| congreso_diputados | www.congreso.es | `https://www.congreso.es/webpublica/opendata/diputados/DiputadosActivos__20260212050007.json` | json | application/json | 1 |
| congreso_iniciativas | www.congreso.es | `https://www.congreso.es/es/opendata/iniciativas` | (no_ext) | text/html;charset=UTF-8 | 1 |
| congreso_intervenciones | www.congreso.es | `https://www.congreso.es/es/opendata/intervenciones` | (no_ext) | text/html;charset=UTF-8 | 1 |
| congreso_votaciones | www.congreso.es | `https://www.congreso.es/es/opendata/votaciones` | (no_ext) | text/html;charset=UTF-8 | 8 |
| cortes_clm_diputados | www.cortesclm.es | `https://www.cortesclm.es/web2/paginas/resul_diputados.php?legislatura=11` | php | application/json | 1 |
| cortes_cyl_procuradores | www.ccyl.es | `https://www.ccyl.es/Organizacion/PlenoAlfabetico` | (no_ext) | application/json | 1 |
| corts_valencianes_diputats | www.cortsvalencianes.es | `https://www.cortsvalencianes.es/es/composicion/diputados` | (no_ext) | application/json | 1 |
| europarl_meps | www.europarl.europa.eu | `https://www.europarl.europa.eu/meps/es/full-list/xml` | (no_ext) | application/xml;charset=UTF-8 | 1 |
| eurostat_sdmx | ec.europa.eu | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_a` | (no_ext) | application/json | 1 |
| infoelectoral_descargas | infoelectoral.interior.gob.es | `https://infoelectoral.interior.gob.es/min/convocatorias/tipos/` | (no_ext) | application/json | 1 |
| infoelectoral_procesos | infoelectoral.interior.gob.es | `https://infoelectoral.interior.gob.es/min/procesos/` | (no_ext) | application/json | 1 |
| jgpa_diputados | www.jgpa.es | `https://www.jgpa.es/diputados-y-diputadas?p_p_id=jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-2&p_p_col_count=1&p_r_p_2113237475_diputadoId=0&p_r_p_2113237475_legislaturaId=0&p_r_p_2113237475_grupoParlamentarioId=0&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_redirect=%2Fdiputados-y-diputadas&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_delta=50&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_keywords=&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_advancedSearch=false&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_andOperator=true&_jgpaportlet_WAR_jgpaportlet_INSTANCE_JoGQRoxbw79k_resetCur=false&cur=1` | (no_ext) | application/json | 1 |
| moncloa_referencias | www.lamoncloa.gob.es | `https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx` | aspx | application/json | 1 |
| moncloa_rss_referencias | www.lamoncloa.gob.es | `https://www.lamoncloa.gob.es/Paginas/rss.aspx?tipo=16` | aspx | application/json | 1 |
| municipal_concejales | concejales.redsara.es | `https://concejales.redsara.es/consulta/` | (no_ext) | text/html; charset=UTF-8 | 1 |
| municipal_concejales | concejales.redsara.es | `https://concejales.redsara.es/consulta/getConcejalesLegislatura` | (no_ext) | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=utf-8 | 1 |
| parlament_balears_diputats | www.parlamentib.es | `https://www.parlamentib.es/Representants/Diputats.aspx?criteria=0` | aspx | application/json | 1 |
| parlament_catalunya_diputats | www.parlament.cat | `https://www.parlament.cat/web/composicio/ple-parlament/composicio-actual/index.html` | html | application/json | 1 |
| parlamento_andalucia_diputados | www.parlamentodeandalucia.es | `https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do` | do | application/json | 1 |
| parlamento_canarias_diputados | parcan.es | `https://parcan.es/api/diputados/por_legislatura/11/?format=json` | (no_ext) | application/json; charset=utf-8 | 1 |
| parlamento_cantabria_diputados | parlamento-cantabria.es | `https://parlamento-cantabria.es/informacion-general/composicion/11l-pleno-del-parlamento-de-cantabria` | (no_ext) | application/json | 1 |
| parlamento_larioja_diputados | adminweb.parlamento-larioja.org | `https://adminweb.parlamento-larioja.org/composicion-y-organos/diputados` | (no_ext) | application/json | 1 |
| parlamento_navarra_parlamentarios_forales | parlamentodenavarra.es | `https://parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales` | (no_ext) | application/json | 1 |
| parlamento_vasco_parlamentarios | www.legebiltzarra.eus | `https://www.legebiltzarra.eus/comparla/c_comparla_alf_ACT.html` | html | application/json | 1 |
| placsp_autonomico | contrataciondelestado.es | `https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom` | atom | application/json | 1 |
| placsp_sindicacion | contrataciondelestado.es | `https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom` | atom | application/json | 1 |
| senado_iniciativas | www.senado.es | `https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15` | (no_ext) | text/xml; charset=UTF-8 | 2 |
| senado_senadores | www.senado.es | `https://www.senado.es/legis15/senadores/csv/SenadoresRedesSociales.csv` | csv | text/csv | 1 |
| senado_senadores | www.senado.es | `https://www.senado.es/web/ficopendataservlet?tipoFich=4&legis=15` | (no_ext) | application/json | 1 |
| senado_senadores | www.senado.es | `https://www.senado.es/web/ficopendataservlet?tipoFich=6&legis=10,11,12,14,15&skip_details=1` | (no_ext) | application/json | 1 |
| senado_votaciones | www.senado.es | `https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html?legis=15` | html | (none),text/html;charset=UTF-8 | 16 |

## Local File (file://) Inputs Seen In This Snapshot

| source_id | url_ext | logged_content_type | file_url |
| --- | --- | --- | --- |
| aemet_opendata_series | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/aemet_opendata_series/aemet_opendata_series_replay_20260217.json` |
| aemet_opendata_series | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/aemet_opendata_series_sample.json` |
| asamblea_melilla_diputados | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/asamblea_melilla_diputados_sample.json` |
| bde_series_api | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bde_series_api/bde_series_api_replay_20260217.json` |
| bde_series_api | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/bde_series_api_sample.json` |
| bdns_api_subvenciones | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bdns_api_subvenciones/bdns_api_subvenciones_replay_20260217.json` |
| bdns_api_subvenciones | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/bdns_api_subvenciones_sample.json` |
| bdns_autonomico | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/bdns_autonomico/bdns_autonomico_replay_20260217.json` |
| bdns_autonomico | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/bdns_autonomico_sample.json` |
| boe_api_legal | xml | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/boe_api_legal_sample.xml` |
| boe_api_legal | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/boe_api_legal_sample.xml` |
| congreso_diputados | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chota/etl/data/raw/samples/congreso_diputados_sample.json` |
| congreso_iniciativas | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/congreso_iniciativas_sample.json` |
| congreso_votaciones | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/congreso_votaciones_sample.json` |
| cortes_aragon_diputados | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/cortes_aragon_diputados_sample.json` |
| corts_valencianes_diputats | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/corts_valencianes_diputats_sample.json` |
| europarl_meps | xml | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chota/etl/data/raw/samples/europarl_meps_sample.xml` |
| eurostat_sdmx | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/eurostat_sdmx/eurostat_sdmx_replay_20260217.json` |
| eurostat_sdmx | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/eurostat_sdmx_sample.json` |
| infoelectoral_descargas | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/infoelectoral_descargas_sample.json` |
| infoelectoral_procesos | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/infoelectoral_procesos_sample.json` |
| moncloa_referencias | (no_ext) | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216` |
| moncloa_referencias | html | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/moncloa_referencias_sample.html` |
| moncloa_referencias | html | (none) | `file:///workspace/etl/data/raw/samples/moncloa_referencias_sample.html` |
| moncloa_rss_referencias | (no_ext) | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216` |
| moncloa_rss_referencias | json | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/overrides/moncloa_rss_referencias_override_event_date.json` |
| moncloa_rss_referencias | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/moncloa_rss_referencias_sample.xml` |
| moncloa_rss_referencias | xml | (none) | `file:///workspace/etl/data/raw/samples/moncloa_rss_referencias_sample.xml` |
| parlamento_galicia_deputados | (no_ext) | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages` |
| parlamento_galicia_deputados | json | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/parlamento_galicia_deputados_sample.json` |
| parlamento_navarra_parlamentarios_forales | (no_ext) | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages` |
| placsp_autonomico | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/placsp_autonomico/placsp_autonomico_replay_20260217.xml` |
| placsp_autonomico | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/placsp_autonomico_sample.xml` |
| placsp_sindicacion | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/placsp_sindicacion/placsp_sindicacion_replay_20260217.xml` |
| placsp_sindicacion | xml | application/json | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/placsp_sindicacion_sample.xml` |
| programas_partidos | csv | text/csv | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/programas_partidos_sample.csv` |
| senado_iniciativas | xml | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/senado_iniciativas_sample.xml` |
| senado_senadores | csv | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chota/etl/data/raw/samples/senado_senadores_sample.csv` |
| senado_votaciones | xml | (none) | `file:///Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola/etl/data/raw/samples/senado_votaciones_sample.xml` |

## Sources Without Network Fetches In This Snapshot

| source_id | name | default_url | configured_format | network_rows | file_rows | total_rows |
| --- | --- | --- | --- | ---: | ---: | ---: |
| aemet_opendata_series | AEMET OpenData - Indicadores confusores | `https://opendata.aemet.es/opendata/api/valores/climatologicos` | json | 0 | 2 | 2 |
| bde_series_api | Banco de Espana - Indicadores confusores (API series) | `https://api.bde.es/datos/series` | json | 0 | 2 | 2 |
| bdns_subvenciones | Subvenciones publicas (canonico policy_events) | `https://www.pap.hacienda.gob.es/bdnstrans/GE/es/convocatorias` | json | 0 | 0 | 0 |
| cortes_aragon_diputados | Cortes de Aragon - Diputados (XI Legislatura) | `https://www.cortesaragon.es/Quienes-somos.2250.0.html?no_cache=1&tx_t3comunicacion_pi3%5Bnumleg%5D=11&tx_t3comunicacion_pi3%5Btipinf%5D=3&tx_t3comunicacion_pi3%5Buidcom%5D=-2#verContenido` | json | 0 | 1 | 1 |
| parl_initiative_docs | Parlamento - Documentos de iniciativas (BOCG/Diario de Sesiones) | `manifest://parl_initiative_docs` | bin | 0 | 0 | 0 |
| parlamento_galicia_deputados | Parlamento de Galicia - Deputados (fichas HTML) | `https://www.parlamentodegalicia.gal/Composicion/Deputados` | json | 0 | 2 | 2 |
| placsp_contratacion | Contratacion publica (canonico policy_events) | `https://contrataciondelestado.es/` | json | 0 | 0 | 0 |
| programas_partidos | Programas de partidos (manifest-driven) | `manifest://programas_partidos` | csv | 0 | 1 | 1 |
