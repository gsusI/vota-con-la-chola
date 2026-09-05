# Reproducir el corte PLACSP

Alfa técnica: 120 resultados de adjudicación, decisiones del 1 al 3 de enero de 2025. Selección parcial por fecha e identificador, no cobertura completa de esos días ni de los organismos. Importe adjudicado sin impuestos; no pagos ni contratos únicos. No inferir irregularidades.

## Inicio

Requisito: Python 3.10 o posterior. No requiere pip, Docker, claves ni bases previas. Tras descargar y verificar el ZIP enlazado en la demo, descomprimir en una carpeta nueva:

```sh
python3 reproduce.py --bundle .
```

El comando verifica todos los hashes, contrasta CSV y JSON, comprueba los XML, crea SQLite en memoria y reproduce las tres consultas contra sus resultados esperados. Los resultados aparecen en JSON; `amount_cents` usa céntimos enteros para evitar errores de coma flotante.

```sh
python3 reproduce.py --bundle . --start 2025-01-02 --end 2025-01-03
```

`--authority` y `--supplier` aceptan los nombres exactos del CSV; filtran etiquetas publicadas, no identifican una entidad universal. Las agrupaciones conservan nombre, identificador y esquema. Fechas inclusivas. Sin filtros, suma esperada: 604519346 céntimos; 120 resultados.

## Descarga anónima fijada por hash

Descarga `reproduce.py` desde los assets de la release `v0.1.0-placsp-alpha.1` y ejecútalo con Python:

```sh
python3 reproduce.py --url https://github.com/gsusI/vota-con-la-chola/releases/download/v0.1.0-placsp-alpha.1/placsp-launch.zip --sha256 9d322d80c13247e835991d9187b75d5ad4c32d59bb440c1ca564672f242f7c9b
```

El directorio de datos es temporal y nuevo en cada ejecución. El hash fija los bytes aunque la descarga cambie; cualquier diferencia detiene la reproducción. El ZIP conserva la guía que se selló al crear el paquete.

## Contenido y diccionario

- `awards.csv`, `awards.parquet`, `awards.json`: las mismas 120 filas. CSV técnico exacto: importar como datos, no abrir fórmulas automáticamente en una hoja de cálculo.
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
| `authority_id`, `authority` | Identificador y nombre del órgano publicados; vacío indica identificador ausente |
| `supplier_id_scheme`, `supplier_id`, `supplier` | Esquema, identificador y nombre publicados; sin fusión por nombre |
| `contract_id`, `lot_id`, `award_ordinal` | Expediente, lote publicado o vacío, posición del resultado en la fuente |
| `decision_date` | Fecha de adjudicación publicada, ISO 8601 |
| `amount_decimal`, `amount_cents`, `currency` | Decimal fuente, equivalente exacto en céntimos, EUR; sin impuestos |
| `supplier_source_text`, `authority_source_text` | Texto literal XML, incluidos espacios; las etiquetas analíticas normalizan espacios y conservan aquí el original |
| `title`, `source_url` | Título del expediente y URL oficial |
| `source_snapshot_date`, `entry_updated_at` | Etiqueta de captura y actualización de la entrada; no fecha de lanzamiento |
| `entry_sha256`, `capture_path` | Hash de entrada XML y ruta de captura verificable |

El manifest original rotula 2025-03-31, pero sus filas contienen etiquetas de captura 2025-03-31 y 2025-06-30. El lanzamiento no actualiza esos datos. El conjunto original mezcla anuncios y resultados; este derivado incluye solo resultados de adjudicación con código fuente 8, importe EUR exacto y versión no ambigua dentro del corpus congelado. Excluye discrepancias entre Parquet y fuente. No certifica vigencia actual, representatividad o cobertura nacional.

## Derechos y créditos

Fuente: Plataforma de Contratación del Sector Público, Ministerio de Hacienda. Captura y transformación: Vota Con La Chola. No hay revisión independiente registrada. Código: MIT; datos sujetos a las condiciones por fuente de https://github.com/gsusI/vota-con-la-chola/blob/main/docs/legal/data-rights.md. No atribuir licencia MIT a los documentos oficiales. Citación del proyecto: `CITATION.cff` en el repositorio.
