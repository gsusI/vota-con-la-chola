# Reproducir el histórico disponible de PLACSP

Release reproducible: todos los resultados de adjudicación elegibles, sin recorte de fechas dentro del corpus congelado. Importe adjudicado sin impuestos; no pagos ni contratos únicos. No inferir irregularidades ni cobertura fuera del snapshot.

## Inicio

Requisito: Python 3.10 o posterior. No requiere pip, Docker, claves ni bases previas. Tras descargar y verificar el ZIP enlazado en la demo, descomprimir en una carpeta nueva:

```sh
python3 reproduce.py --bundle .
```

El comando verifica todos los hashes, contrasta CSV y JSON, comprueba los XML, crea SQLite en memoria y reproduce las tres consultas contra sus resultados esperados. Los resultados aparecen en JSON; `amount_cents` usa céntimos enteros para evitar errores de coma flotante.

```sh
python3 reproduce.py --bundle . --start 2025-01-02 --end 2025-01-03
```

`--authority` y `--supplier` aceptan los nombres canónicos del CSV. Las agrupaciones usan los identificadores publicados cuando existen y convergen variantes tipográficas del mismo nombre; los campos `*_source_text` conservan el texto literal de cada XML. Fechas inclusivas. Sin filtros se consulta todo el histórico. El puntero `latest.json` publica el número de resultados y la suma esperada en céntimos.

## Descarga completa verificada

En `https://votaconlachola.org/spending/`, pulsa «Descargar datos y consultas». La página reúne todas las partes del ZIP, verifica SHA-256 y descarga un único archivo que puede descomprimirse y consultarse con el comando anterior. El puntero público `spending/launch/latest.json` contiene `archive_sha256`, tamaños y partes de transporte. La compresión y las partes son reversibles: no eliminan filas ni XML.

Los XML descargados desde cada resultado se descomprimen y verifican contra `entry_sha256`. El paquete completo conserva `evidence/*.xml` sin comprimir individualmente para la reproducción local.

## Contenido y diccionario

- `awards.csv`, `awards.parquet`, `awards.json`: las mismas filas del histórico completo. CSV técnico exacto: importar como datos, no abrir fórmulas automáticamente en una hoja de cálculo.
- `name-aliases.json`: grupos de variantes, nombre canónico, criterio de identidad y frecuencia de cada texto fuente.
- `by-supplier.sql`: resultados e importes por órgano y proveedor, con identificadores separados.
- `by-month.sql`: distribución temporal de las decisiones del corte.
- `records.sql`: detalle, expediente, lote, URL oficial y captura.
- `expected.json`: respuestas calculadas independientemente de SQL; `manifest.json`: tamaño y SHA-256 de cada archivo.
- `evidence/*.xml`: entradas Atom originales serializadas como en la ingesta; `lineage.json` enlaza ZIP oficial, fecha de captura, miembro y hashes. No se presentan como bytes del ZIP original.
- `source-manifest.json`: manifest PLACSP congelado; `audit.json`: selección, exclusiones, unidades y cobertura.

| Campo | Significado |
| --- | --- |
| `award_key` | Identificador estable del expediente fuente + ordinal del resultado; versión capturada única |
| `money_fact_id`, `source_record_id` | Referencias al corpus analítico congelado |
| `authority_id`, `authority` | Identificador publicado y nombre canónico del órgano; vacío indica identificador ausente |
| `supplier_id_scheme`, `supplier_id`, `supplier` | Esquema e identificador publicados y nombre canónico del proveedor |
| `contract_id`, `lot_id`, `award_ordinal` | Expediente, lote publicado o vacío, posición del resultado en la fuente |
| `decision_date` | Fecha de adjudicación publicada, ISO 8601 |
| `amount_decimal`, `amount_cents`, `currency` | Decimal fuente, equivalente exacto en céntimos, EUR; sin impuestos |
| `supplier_source_text`, `authority_source_text` | Texto literal XML, incluidos espacios y puntuación; las etiquetas analíticas convergen variantes y conservan aquí el original |
| `title`, `source_url` | Título del expediente y URL oficial |
| `source_snapshot_date`, `entry_updated_at` | Etiqueta de captura y actualización de la entrada; no fecha de lanzamiento |
| `entry_sha256`, `capture_path` | Hash de entrada XML y ruta de captura verificable |

El manifest original rotula 2025-03-31, pero sus filas contienen etiquetas de captura 2025-03-31 y 2025-06-30. El lanzamiento no actualiza esos datos. El conjunto original mezcla anuncios y resultados; este derivado incluye solo resultados de adjudicación con código fuente 8, importe EUR exacto y versión no ambigua dentro del corpus congelado. Excluye discrepancias entre Parquet y fuente. No certifica vigencia actual, representatividad o cobertura nacional.

## Derechos y créditos

Fuente: Plataforma de Contratación del Sector Público, Ministerio de Hacienda. Captura y transformación: Vota Con La Chola. No hay revisión independiente registrada. Código: MIT; datos sujetos a las condiciones por fuente de https://github.com/gsusI/vota-con-la-chola/blob/main/docs/legal/data-rights.md. No atribuir licencia MIT a los documentos oficiales. Citación del proyecto: `CITATION.cff` en el repositorio.
