# Data Catalogue

Generated from current workspace snapshot.

## Scope
- Raw downloads: `etl/data/raw`
- Derived snapshots: `etl/data/published`
- Staging databases: `etl/data/staging`
- Root snapshots: top-level `*.db` files

## Raw Sources

| Source Directory | Size | Files |
| --- | --- | --- |
| `aemet_opendata_series` | 12K | 3 |
| `asamblea_ceuta_diputados` | 56K | 7 |
| `asamblea_extremadura_diputados` | 144K | 9 |
| `asamblea_madrid_diputados` | 580K | 1 |
| `asamblea_madrid_ocupaciones` | 19M | 18 |
| `asamblea_melilla_diputados` | 140K | 5 |
| `asamblea_murcia_diputados` | 184K | 9 |
| `bde_series_api` | 12K | 3 |
| `bdns_api_subvenciones` | 72K | 6 |
| `bdns_autonomico` | 64K | 4 |
| `boe_api_legal` | 568K | 4 |
| `congreso_diputados` | 6.5M | 42 |
| `congreso_iniciativas` | 76K | 19 |
| `congreso_intervenciones` | 8.0K | 2 |
| `congreso_votaciones` | 152K | 38 |
| `congreso_votaciones_zips` | 14M | 5 |
| `cortes_aragon_diputados` | 200K | 13 |
| `cortes_clm_diputados` | 160K | 10 |
| `cortes_cyl_procuradores` | 240K | 10 |
| `corts_valencianes_diputats` | 484K | 13 |
| `europarl_meps` | 4.4M | 34 |
| `eurostat_sdmx` | 39M | 9 |
| `infoelectoral_descargas` | 276K | 6 |
| `infoelectoral_procesos` | 312K | 6 |
| `jgpa_diputados` | 124K | 11 |
| `manual` | 1.1G | 9874 |
| `moncloa_referencias` | 184K | 9 |
| `moncloa_rss_referencias` | 144K | 11 |
| `municipal_concejales` | 54M | 27 |
| `parlament_balears_diputats` | 192K | 8 |
| `parlament_catalunya_diputats` | 780K | 13 |
| `parlamento_andalucia_diputados` | 476K | 11 |
| `parlamento_canarias_diputados` | 288K | 8 |
| `parlamento_cantabria_diputados` | 96K | 8 |
| `parlamento_galicia_deputados` | 252K | 9 |
| `parlamento_larioja_diputados` | 96K | 8 |
| `parlamento_navarra_parlamentarios_forales` | 720K | 9 |
| `parlamento_vasco_parlamentarios` | 220K | 11 |
| `placsp_autonomico` | 304K | 6 |
| `placsp_sindicacion` | 456K | 9 |
| `programas_partidos` | 24K | 6 |
| `samples` | 456K | 44 |
| `senado_iniciativas` | 80K | 20 |
| `senado_senadores` | 3.4M | 44 |
| `senado_votaciones` | 444K | 55 |
| `senado_votaciones_xmls` | 6.0M | 796 |
| `text_documents` | 563M | 7628 |

## Published Artifacts

| File | Size | Modified |
| --- | --- | --- |
| `infoelectoral-es-2026-02-12.json` | 10687 | Feb 14 15:09 |
| `poblacion_municipios_es.json` | 1921365 | Feb 14 15:10 |
| `proximas-elecciones-espana.json` | 3320 | Feb 12 06:10 |
| `representantes-es-2026-02-12.json` | 3323784 | Feb 12 17:57 |
| `votaciones-es-2026-02-12.json` | 1373593133 | Feb 15 23:32 |
| `votaciones-es-2026-02-12.json.gz` | 17083809 | Feb 14 15:23 |
| `votaciones-kpis-es-2026-02-12.json` | 3153 | Feb 16 00:38 |
| `votaciones-kpis-senado-2026-02-12.json` | 1772 | Feb 14 17:09 |
| `votaciones-kpis-senado-temp.json` | 2233 | Feb 14 15:10 |

## Staging Databases

| File | Size | Modified |
| --- | --- | --- |
| `_inspect.db` | 192512 | Feb 12 09:33 |
| `moncloa-aiops04-matrix-20260216.db` | 708608 | Feb 16 15:12 |
| `parl-quality-smoke.db` | 688128 | Feb 12 22:54 |
| `parl-quick.db` | 704512 | Feb 13 00:22 |
| `politicos-es.and-pv.db` | 516096 | Feb 12 10:30 |
| `politicos-es.aragoncheck.db` | 290816 | Feb 12 12:33 |
| `politicos-es.aragonfix.db` | 303104 | Feb 12 12:39 |
| `politicos-es.asamblea-madrid-20260212.db` | 2011136 | Feb 12 08:49 |
| `politicos-es.asamblea-madrid-occup-uniq-20260212.db` | 192512 | Feb 12 08:56 |
| `politicos-es.asamblea-madrid-ocup-20260212.db` | 13746176 | Feb 12 08:54 |
| `politicos-es.asamblea-madrid-ocup-uniq-20260212.db` | 14417920 | Feb 12 08:57 |
| `politicos-es.asambleaex-20260212.db` | 294912 | Feb 12 11:31 |
| `politicos-es.cantabria-20260212.db` | 245760 | Feb 12 12:23 |
| `politicos-es.cat.db` | 495616 | Feb 12 10:00 |
| `politicos-es.ccyl-20260212.db` | 335872 | Feb 12 11:22 |
| `politicos-es.ceuta.db` | 237568 | Feb 12 13:03 |
| `politicos-es.ci-gate-local.db` | 634880 | Feb 12 07:28 |
| `politicos-es.clean.db` | 90112 | Feb 12 06:48 |
| `politicos-es.cortes-clm-20260212.db` | 258048 | Feb 12 11:01 |
| `politicos-es.cv.db` | 405504 | Feb 12 10:17 |
| `politicos-es.db` | 3254673408 | Feb 21 09:36 |
| `politicos-es.e2e-20260212.db` | 634880 | Feb 12 06:59 |
| `politicos-es.e2e-postfix-20260212.db` | 22409216 | Feb 12 08:08 |
| `politicos-es.e2e10.db` | 137195520 | Feb 12 11:08 |
| `politicos-es.e2e11.db` | 137355264 | Feb 12 11:28 |
| `politicos-es.e2e12.db` | 137486336 | Feb 12 11:38 |
| `politicos-es.e2e16.db` | 137904128 | Feb 12 12:09 |
| `politicos-es.e2e17.db` | 138129408 | Feb 12 12:50 |
| `politicos-es.e2e18.db` | 1183744 | Feb 12 13:04 |
| `politicos-es.e2e19.db` | 317444096 | Feb 15 10:38 |
| `politicos-es.e2e6.db` | 136585216 | Feb 12 10:04 |
| `politicos-es.e2e7.db` | 136798208 | Feb 12 10:22 |
| `politicos-es.e2e9.db` | 137121792 | Feb 12 10:36 |
| `politicos-es.fresh.db` | 916041728 | Feb 14 17:33 |
| `politicos-es.fresh.recovered.20260214_1705.db` | 459022336 | Feb 14 17:01 |
| `politicos-es.fresh.work.20260214_1710.db` | 460959744 | Feb 14 18:22 |
| `politicos-es.full-20260212.db` | 119738368 | Feb 12 08:20 |
| `politicos-es.html-guard-20260212.db` | 192512 | Feb 12 08:06 |
| `politicos-es.jgpa-20260212.db` | 241664 | Feb 12 11:45 |
| `politicos-es.just-e2e-20260212.db` | 634880 | Feb 12 07:01 |
| `politicos-es.larioja-20260212.db` | 241664 | Feb 12 12:02 |
| `politicos-es.municipal-strict-20260212.db` | 118296576 | Feb 12 08:03 |
| `politicos-es.murcia-20260212.db` | 278528 | Feb 12 12:17 |
| `politicos-es.norm-samples.db` | 192512 | Feb 12 07:59 |
| `politicos-es.norm-test.db` | 192512 | Feb 12 07:58 |
| `politicos-es.parcan-20260212.db` | 331776 | Feb 12 11:49 |
| `politicos-es.parlamentib-20260212.db` | 290816 | Feb 12 11:58 |
| `politicos-es.recovered.db` | 1513271296 | Feb 13 14:36 |
| `politicos-es.refactor-e2e.db` | 119926784 | Feb 12 09:27 |
| `politicos-es.refactor-e2e2.db` | 134492160 | Feb 12 09:29 |
| `politicos-es.senado-fix-all.db` | 70344704 | Feb 12 07:45 |
| `politicos-es.senado-fix-v2.db` | 364544 | Feb 12 07:47 |
| `politicos-es.senado-fix.db` | 360448 | Feb 12 07:43 |
| `politicos-es.strict-check.db` | 90112 | Feb 12 07:04 |
| `politicos-es.thresholds-smoke.db` | 134492160 | Feb 12 09:38 |
| `politicos-es.tracker-check-20260212.db` | 634880 | Feb 12 07:17 |

## Root DB Files

| File | Kind | Size (bytes) | Size (resolved target bytes) |
| --- | --- | --- | --- |
| `politicos-es.db` | -rw-r--r--@ | 0 | 0 |
| `politicos-es.e2e19.db` | -rw-r--r--@ | 0 | 0 |

Note: In this snapshot, both root DB files are zero-byte placeholders.
