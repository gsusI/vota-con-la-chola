# Contrato de indicadores económicos y sociales v1

Estado: `approved_for_first_vertical_slice`

Fecha: `2026-08-20`

Autoridad de dirección: `ROADMAP.md` (`W7-001..008`)

Ontología superior: `docs/data-model/core-ontology-v1.md`

## 1. Propósito

Este contrato permite contestar, con datos oficiales y trazables:

- qué resultado fue medido;
- para qué población y territorio;
- en qué intervalo temporal;
- con qué unidad, método y estado estadístico;
- qué publicó la fuente en cada captura;
- qué cambió después por revisión, corrección o retirada;
- qué se desconoce;
- y qué evidencia exacta permite reproducir cada valor.

Un indicador describe una medición. No atribuye mérito, culpa, influencia ni
causalidad política. La cronología entre una decisión y un indicador tampoco es
causalidad.

## 2. Reglas no negociables

1. Solo datos reales de fuentes oficiales o de una redistribución oficial
   verificable. No se aceptan filas sintéticas, mocks ni valores de relleno.
2. Una revisión nunca sobrescribe una versión publicada anteriormente.
3. El valor numérico canónico se conserva como texto decimal exacto. Un `REAL`
   auxiliar puede usarse para consulta, pero no es autoridad monetaria o
   estadística.
4. Códigos de estado de la fuente —provisional, estimado, ruptura de serie,
   confidencial u otros— se conservan sin reinterpretarlos.
5. Ausencia, supresión, confidencialidad y cero son estados distintos.
6. Territorio, clasificación geográfica y versión de esa clasificación son parte
   de la identidad de la serie.
7. Cada observación pública debe llegar a un URL oficial, SHA-256 del bruto y
   localizador estable dentro del bruto.
8. Toda incertidumbre no publicada queda como `not_provided`; nunca se inventa.
9. Toda lectura pública debe declarar la unidad y la frecuencia.
10. Cualquier enlace a una acción política se publica como descriptivo salvo que
    supere un gate causal separado.

## 3. Conceptos

### 3.1 Definición de indicador

La definición identifica una medida semántica estable:

- fuente y conjunto oficial;
- código y etiqueta;
- definición;
- dominio;
- frecuencia;
- unidad;
- versión y enlace metodológico;
- política de revisiones;
- licencia/reutilización;
- URL oficial.

Una unidad distinta crea otra definición pública cuando altera el significado de
la medida. Por ejemplo, PIB total en millones de euros y PIB por habitante en PPS
no son la misma definición.

Tabla: `indicator_definitions`.

### 3.2 Release de fuente

Representa un bruto oficial inmutable observado por el proyecto:

- fecha de snapshot del proyecto;
- timestamp de actualización declarado por la fuente;
- URL;
- SHA-256, bytes y ruta repo-relativa del bruto;
- metadatos de la fuente;
- release anterior, si existe;
- estado de comparación: `baseline` o `compared`.

Tabla: `indicator_releases`.

### 3.3 Versión de serie

Identifica una combinación de dimensiones en un release:

- clave estable de serie;
- territorio y etiqueta oficial;
- sistema, nivel y versión geográfica;
- dimensiones originales completas.

La clave estable excluye el release. La versión de serie incluye el release. Así
se puede comparar la misma serie entre capturas sin fingir que una clasificación
territorial histórica es eterna.

Tabla: `indicator_series_versions`.

### 3.4 Versión de observación

Una observación es una medición de una serie durante un intervalo:

- inicio y fin inclusivos;
- etiqueta de periodo de la fuente;
- valor decimal exacto o texto oficial;
- código y etiquetas de estado de fuente;
- incertidumbre publicada o `not_provided`;
- release, ordinal y estado de revisión;
- versión anterior, cuando procede;
- timestamp oficial de publicación/actualización;
- índice de celda y valor bruto.

Tabla: `indicator_observation_versions`.

### 3.5 Evidencia

Cada versión de observación conserva:

- URL oficial;
- SHA-256 del bruto;
- ruta repo-relativa;
- JSON Pointer o localizador equivalente del valor;
- localizador del estado estadístico;
- método y versión del extractor.

Tabla: `indicator_observation_evidence`.

## 4. Identidades

Los IDs son deterministas y content-addressed:

- `indicator_id`: hash de fuente, dataset, código semántico, frecuencia y unidad;
- `indicator_release_id`: hash de `indicator_id` y SHA-256 del bruto;
- `indicator_series_version_id`: hash de release y clave estable de serie;
- `indicator_observation_version_id`: hash de serie-version, periodo y valor/estado;
- `indicator_observation_evidence_id`: hash de observación, bruto y localizador.

Formato recomendado: prefijo legible + 24 caracteres hexadecimales. La entrada al
hash usa JSON canónico UTF-8, claves ordenadas y separadores compactos.

## 5. Tiempo

Frecuencias soportadas inicialmente:

| Código | Intervalo canónico |
| --- | --- |
| `A` | año natural, `YYYY-01-01` a `YYYY-12-31` |
| `Q` | trimestre natural |
| `M` | mes natural |
| `D` | día |
| otra | conservar etiqueta y marcar método de intervalo explícito |

No se convierte un periodo anual en un instante. La fecha de publicación de la
fuente se almacena aparte del periodo observado.

## 6. Geografía

Campos obligatorios:

- `geography_code` y `geography_name` oficiales;
- `geography_system`, por ejemplo `NUTS`;
- `geography_level`, por ejemplo `country`, `NUTS1`, `NUTS2`, `NUTS3`;
- `geography_version` si la fuente la declara;
- `territory_id` solo cuando exista un enlace normalizado demostrable.

Inferir el nivel NUTS por longitud del código es una transformación mecánica
permitida y versionada. No autoriza a fusionar códigos históricos. Una serie con
cambio de frontera conserva sus observaciones y el cambio se documenta.

## 7. Valores, estados e incertidumbre

### 7.1 Valor

- `value_decimal`: representación decimal exacta del JSON/XML/CSV oficial;
- `value_text`: valor textual oficial cuando no sea numérico;
- al menos uno debe existir salvo una versión `deleted`.

### 7.2 Estado estadístico

`source_status_code` conserva el token oficial completo. Las etiquetas se guardan
en `source_status_labels_json`. Para Eurostat v1 aparecen, entre otros:

- `b`: ruptura de serie;
- `p`: provisional;
- `e`: estimado;
- `|C`: confidencial.

No se transforma `confidential` en cero ni se publica un valor privado no incluido
por la propia fuente.

### 7.3 Incertidumbre

Estados:

- `provided`: límites o medida de incertidumbre publicados;
- `not_provided`: la fuente no publicó incertidumbre para esa celda;
- `not_applicable`: la medida no admite ese concepto según método documentado.

El primer slice Eurostat usa `not_provided`; no estima intervalos.

## 8. Revisiones

La identidad comparada es:

`indicator_id + stable_series_key + period_label`.

Al incorporar un nuevo release:

1. localizar la última versión anterior de la identidad;
2. comparar valor decimal, valor textual, códigos de estado y metadatos que
   cambien el significado;
3. crear siempre una versión del nuevo release;
4. asignar:
   - `unchanged` si el contenido es igual;
   - `changed` si difiere;
   - `deleted` si la identidad desapareció del release completo;
   - `corrected` solo cuando la fuente lo declara explícitamente;
5. enlazar `previous_observation_version_id`;
6. mantener la versión anterior; no actualizarla ni borrarla;
7. producir balance por release: nuevas, iguales, cambiadas y retiradas.

El primer release es `baseline`, ordinal `1`, sin versión anterior. `Baseline` no
significa definitivo ni no revisable.

## 9. Provenance y reproducibilidad

Por release se verifica:

- host HTTPS permitido;
- bytes y SHA-256 exactos;
- dataset/código esperado;
- cardinalidad de dimensiones y límites de cubo;
- conteo de valores y estados;
- IDs deterministas;
- FK e `integrity_check`;
- paridad byte a byte entre artefacto publicado y validado;
- ausencia de datos sintéticos/mocks;
- ausencia de rutas locales, cookies, tokens o credenciales.

La higiene de publicación no elimina información personal oficial. Los
indicadores agregados no suelen contener personas, pero la regla global del
proyecto sigue siendo conservar identidad pública oficial para accountability.

## 10. Contrato físico para millones

Objetivo operativo:

- `100M+` versiones de observación;
- `10M+` series-version;
- `10k+` releases de dataset;
- ingestión reanudable y sin N+1;
- memoria acotada por batch/row group;
- publicación estática sin cargar el corpus completo al navegador.

Particionado analítico:

`source_id / dataset_code / snapshot_date / geography_level / period_year`.

Orden dentro de partición:

`indicator_id, stable_series_key, period_start, revision_ordinal,
indicator_observation_version_id`.

Reglas de ejecución:

- bruto content-addressed descargado una vez;
- cola con lease, heartbeat, retry acotado y dead letter;
- URLs deduplicadas antes de descargar;
- parseo streaming o por bloques;
- upserts por batches, no búsquedas por fila;
- Parquet Zstandard, row groups acotados;
- manifiesto con filas, bytes, SHA-256, min/max IDs y esquema;
- publicación web mediante artefactos preagregados con presupuesto de 5 MB;
- segunda captura obligatoria para afirmar que la lógica de revisión funciona con
  revisiones reales.

## 11. Primer slice oficial

Fuente: Eurostat API de difusión JSON-stat.

Dataset: `nama_10r_3gdp`.

Familia: PIB a precios corrientes por habitante en PPS (`PPS_EU27_2020_HAB`).

Frecuencia: anual.

Ámbito: todos los códigos oficiales que empiezan por `ES`, sin seleccionar valores
por conveniencia.

Bruto: captura real content-addressed del snapshot `2026-08-11`.

El slice conserva:

- todas las celdas españolas disponibles de 2000 a 2024;
- todos los niveles territoriales presentes;
- códigos de estado Eurostat por celda;
- texto decimal exacto;
- índice plano JSON-stat;
- timestamp de actualización, versión de estructura y enlace metodológico;
- estado de revisión `baseline` porque solo existe una captura comprobada.

No afirma:

- que PIB sea bienestar;
- que cubra todos los outcomes sociales;
- que los territorios sean comparables sin revisar rupturas;
- que el último año sea definitivo;
- que una política concreta causó una variación;
- que cuatro datasets Eurostat sean una codebook representativa.

## 12. Gates de publicación

Un release pasa solo si:

- `source_sha256_match = true`;
- `source_bytes_match = true`;
- `official_origin = true`;
- observaciones y series son no cero;
- cada observación tiene evidencia exacta;
- valor/estado publicado coincide con la celda bruta;
- todos los territorios cumplen el filtro declarado;
- todas las revisiones tienen ordinal y estado válidos;
- FK e integridad SQLite pasan;
- replay independiente produce el mismo release ID y JSON SHA-256;
- UI declara unidad, provisionalidad/estimación/ruptura y no causalidad;
- `just real-data-only-check` y `just privacy-check-public-artifacts` pasan.

## 13. Próximos incrementos

1. Capturar un segundo snapshot real del mismo dataset y demostrar el balance de
   revisiones con evidencia oficial.
2. Aprobar codebook representativa: gasto, empleo, servicios, desigualdad, clima,
   vivienda y salud.
3. Añadir fuente nacional y autonómica con geografía más granular.
4. Publicar diffs de metodología y rupturas de serie.
5. Enlazar indicadores a dossiers solo como contexto descriptivo.
6. Habilitar análisis causal únicamente bajo `docs/method/outcome-linking-v1.md`
   y gates metodológicos posteriores.
