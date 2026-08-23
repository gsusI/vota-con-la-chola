# Indicators MVP

Fecha: 2026-08-20

Estado: publicado y verificado live

## Resultado

Primer recorrido canónico de outcomes: fuente oficial -> definición -> release ->
serie territorial -> observación versionada -> evidencia exacta. Usa una captura
real, content-addressed y checksum-pinned de Eurostat.

Fuente:

- Eurostat API de difusión JSON-stat;
- dataset `nama_10r_3gdp`;
- actualización declarada `2026-02-10T11:00:00+0100`;
- captura de `4.763.587` bytes;
- SHA-256
  `8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491`;
- familia: PIB a precios corrientes por habitante en PPS UE-27 desde 2020;
- regla de alcance: todos los códigos de geografía que empiezan por `ES`.

Release de datos:
`a5d2782888c550487087244b679cd0c5c89f95392a9de3d6a8384c734d757a69`.

SHA-256 del JSON público:
`8a878b41108d2eb58989af825aa1a9309aca389c4da041b09a915230172ab8d7`.

Artefacto público: `2.448.614` bytes.

Cobertura del slice:

- `1` definición;
- `1` release baseline;
- `86` series territoriales: `1` país, `7` NUTS 1, `19` NUTS 2 y `59` NUTS 3;
- `2.091` observaciones reales, entre `2000` y `2024`;
- `2.091` enlaces de evidencia a celda JSON-stat;
- `113` celdas marcadas `p` —provisional— por Eurostat;
- `1.978` celdas sin marca estadística adicional;
- `2.091` incertidumbres explícitas `not_provided`;
- `2.091` estados de revisión `baseline`;
- `0` claims causales y `0` asignaciones de mérito o culpa.

Corpus de escala ya validado:

- `1.755.809` observaciones Eurostat oficiales;
- `155.435` series;
- `37` Parquet;
- `253.373.860` bytes;
- manifest SHA-256
  `b8d8bde43f8e788f465ad980cea2c6803822a2ea71584ff7390d7fed6078ddbc`.

Ese corpus demuestra capacidad de procesamiento real. Sus cuatro datasets no son
una codebook representativa de todos los outcomes.

## Qué cambia

- Contrato `docs/data-model/indicators-spec-v1.md`.
- Cinco tablas aditivas: definitions, releases, series versions, observation
  versions y observation evidence.
- Valores decimales exactos como texto, sin autoridad basada en `float`.
- Releases y revisiones append-only; una corrección futura no sobrescribe la
  publicación observada antes.
- Estado fuente, incertidumbre, periodo anual y geografía forman parte del dato.
- Materializador directo desde el bruto oficial, sin depender de una fila
  preseleccionada manualmente.
- Validador independiente que compara las `2.091` celdas, valores, statuses y
  pointers contra el JSON-stat bruto.
- Página estática `/indicators/` y feed
  `/indicators/data/eurostat-gdp-es.json`.
- Ningún dato synthetic, mock, anonimizado, inventado o placeholder.

## Contrato de verdad

El release permite afirmar qué valor y estado publicó Eurostat para cada
territorio/periodo en la captura.

No permite afirmar:

- que PIB por habitante sea bienestar, igualdad o calidad de servicios;
- que el último dato sea definitivo;
- que una ausencia sea cero;
- que un cambio territorial pueda ignorarse;
- que una decisión política concreta causara una variación;
- que un partido, cargo o institución merezca mérito o culpa;
- que cuatro datasets cubran todos los outcomes relevantes.

Solo hay una captura comprobada. `baseline` significa primera versión observada,
no “dato sin revisiones”. El siguiente gate exige una segunda captura real.

## Escala

El contrato físico soporta `100M+` versiones de observación sin enviar el corpus al
navegador:

1. bruto content-addressed y manifest-first;
2. ingestión por cola con leases, heartbeat y retry acotado;
3. parseo streaming/bounded y upserts por batches;
4. particiones por fuente, dataset, snapshot, geografía y año;
5. Parquet Zstandard con row groups acotados;
6. releases/revisiones append-only;
7. JSON web preagregado con presupuesto `<=5 MB`;
8. origin durable, clean restore, reconciliación y correction workflow antes de
   promoción representativa.

## Verificación

```bash
just eurostat-gdp-indicator-check
sqlite3 -header -column etl/data/staging/indicators-eurostat-gdp-mvp.db \
  < docs/examples/eurostat-indicator-observation-evidence.sql
just privacy-check-public-artifacts
just cloudflare-pages-build
just eurostat-gdp-indicator-live-verify
```

Evidencia local:

- `docs/etl/sprints/INDICATORS-20260820/evidence/eurostat-gdp-materialization.json`
- `docs/etl/sprints/INDICATORS-20260820/evidence/eurostat-gdp-validation.json`
- `docs/etl/sprints/INDICATORS-20260820/evidence/live-eurostat-gdp-verification.json`
- `docs/etl/sprints/INDICATORS-20260820/evidence/live-route-audit.json`
- `tests/test_eurostat_gdp_indicator_real_pipeline.py`
- `tests/test_eurostat_gdp_indicator_ui_contract.js`

Publicación verificada:

- commit `gh-pages` `72060edc1eb6170b6baf443b71462fed1fd29397`;
- HTML live `200`, `205.105` bytes;
- JSON live `200`, `2.448.614` bytes y SHA-256 exacto
  `8a878b41108d2eb58989af825aa1a9309aca389c4da041b09a915230172ab8d7`;
- paridad local/live exacta para las `86` series, `2.091` observaciones y `113`
  marcas provisionales;
- dataset, metodología y condiciones de reutilización oficiales devuelven `200`;
- QA desktop `1440px` y móvil `390x844`: sin overflow de página, controles
  cortados ni errores de consola; la tabla queda acotada en su contenedor;
- auditoría global: `44` rutas, `48` assets críticos y `119` evidencias, `0`
  fallos.

## Siguiente

Capturar un segundo snapshot real del mismo dataset. Comparar cada identidad y
publicar balance `new / unchanged / changed / deleted`, con versiones anteriores
intactas. Después, aprobar una codebook representativa para empleo, gasto,
servicios, desigualdad, clima, vivienda y salud.
