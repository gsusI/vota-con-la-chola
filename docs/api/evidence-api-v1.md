# Evidence API v1

Estado: `implementado y publicado como export estático content-addressed`

Fecha: `2026-08-19`

Contrato máquina: `docs/api/evidence-api-v1.schema.json`

Entrada pública: `https://votaconlachola.org/api/v1/index.json`

## Objetivo

Evidence API v1 ofrece a herramientas externas una interfaz estable, de solo
lectura, para consumir entidades, cadenas de evidencia, salud de fuentes y
resultados de preguntas sin descargar un JSON monolítico ni depender de un servidor.

El contrato conserva nombres, identificadores, fechas y demás información personal
que una fuente oficial haya publicado. No contiene secretos, cookies, estado de
sesión, paths de workstation ni datos privados añadidos. No usa registros
sintéticos, mock, placeholder ni fallback implícito como datos públicos.

## Estado actual

Release API actual:

- API release: `feb61b39de9daddbcf53f5e1453cd9900c7272d6f1ee676ff9e3b8505729a300`;
- upstream scale release firmado: `5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd`;
- data snapshot del Evidence API: `2026-08-12`;
- snapshot del origin firmado: `2026-08-19`;
- `4` colecciones, `5,830` objetos y `26` páginas;
- `1,147` entidades, `1,105` cadenas de evidencia, `48` estados de fuente y
  `3,530` resultados de preguntas;
- página máxima observada: `1,080,866` bytes con límite contractual de `500`
  objetos; el release actual usa `250`;
- `1,147/1,147` labels públicos de actor/issue conservados byte a byte;
- todos los estados insuficientes siguen explícitos como `partial`, `blocked`,
  `unanswerable`, `unknown` o `no_signal`.

Esto no significa que las `5,414,326` filas del origin firmado sean ya respuestas
de accountability. El API solo publica las colecciones analíticas reales que han
pasado su contrato actual. El release index enlaza el snapshot firmado completo y
publica esta diferencia de cobertura, sin inflarla.

## Descubrimiento

El cliente empieza siempre por:

```text
GET /api/v1/index.json
```

Ese puntero pequeño contiene:

- `current_release.api_release_id`;
- SHA-256 del release index;
- release scale upstream;
- policy real-only/identidad pública;
- enlaces al contrato y al release inmutable.

Después abre:

```text
GET /api/v1/releases/<api_release_id>/index.json
```

El release index enumera los inputs exactos y sus SHA-256, el snapshot firmado,
las cuatro colecciones y el manifest de cada una. Un consumer debe fijar
`api_release_id` durante un job; no debe volver a resolver `index.json` entre
páginas.

## Colecciones

| Colección | Grano | ID estable en v1 | Contenido |
|---|---|---|---|
| `entities` | un actor o issue publicado | `answer_id` existente | tipo, label completo, identificadores fuente, rutas, cobertura, freshness y estado |
| `evidence-chains` | una evidencia deduplicada por entry + locator + URL | `evidence-chain:<sha256>` | source, source record, evidencia, accountability entry, cita, actor/issue y answer refs |
| `source-health` | una fuente catalogada | `source:<source_id>` | configuración pública, última ejecución real, conteos, estado, gaps y tracker |
| `question-results` | un resultado materializado | `question-result:<answer_id>` | respuesta, estado, caveats, cobertura, rutas y referencias a evidence chains |

Los IDs actuales de actor/issue mantienen el namespace ya publicado por
`accountability_evidence_api_v1`. Un futuro registry canónico puede añadir
`urn:vclc:*` y aliases, pero v1 no retirará ni reasignará estos IDs.

## Pagination

Cada colección tiene:

```text
/api/v1/releases/<api_release_id>/<collection>/manifest.json
```

El manifest declara `item_count`, `page_count`, `page_size`, `first` y el SHA-256
de cada página. Cada página declara:

- `start_cursor`: posición exclusiva anterior o `null` en la primera página;
- `end_cursor`: cursor opaco ligado a colección, release y último ID;
- `has_next`, `next_cursor` y `next`;
- `items`, siempre ordenados por `id` ascendente.

El consumer trata el cursor como opaco y sigue `page_info.next`. No construye URLs,
no usa offset y no mezcla cursores entre releases o colecciones.

Pseudocódigo:

```python
pointer = get_json("/api/v1/index.json")
release = get_json(pointer["current_release"]["href"])
entities = find_collection(release, "entities")
url = entities["first"]
while url:
    page = get_json(url)
    process(page["items"])
    url = page["page_info"]["next"]
```

Cada página incorpora el hash de la siguiente en su URL. El manifest compromete
todos los hashes. Cambiar un byte cambia el page filename y el release derivado de
inputs, evitando una sustitución silenciosa.

## Provenance obligatoria

Todo objeto contiene:

- `api_release_id`;
- `upstream_scale_release_id`;
- `data_snapshot_date`;
- `source_artifact_sha256`;
- `source_collection`;
- `source_record_id`;
- `official_real_record=true`.

Una evidence chain conserva además:

```text
source -> source_record -> evidence -> accountability_entry
```

`source_url_state=not_available_in_current_export` se publica cuando el export
upstream real no contiene URL. No se inventa una. `source_locator` sigue presente
para llegar al registro capturado.

El release index lista los artifacts locales que materializaron el API, su tamaño,
schema y SHA-256. También enlaza manifest y attestation del snapshot scale. La firma
upstream prueba el manifest scale; el API tiene su propio release derivado y no
afirma que sus páginas formen parte de aquel manifest.

## Versionado y compatibilidad

Compatible dentro de `/api/v1/`:

- añadir campos opcionales;
- añadir valores documentados sin cambiar el significado de los anteriores;
- añadir colecciones mediante una revisión del contrato;
- publicar un nuevo release content-addressed y mover el puntero current al final.

Incompatible:

- retirar o renombrar un campo existente;
- cambiar semántica, tipo, ID o orden de paginación;
- volver implícito un estado desconocido;
- reducir provenance o retirar identidad pública oficial;
- reutilizar un `api_release_id` con bytes distintos.

Un cambio incompatible exige `/api/v2/`. V1 seguirá público durante al menos
`180` días y `2` releases públicos paralelos desde el aviso de deprecación. El
puntero expondrá el aviso antes de retirar una major. Las releases inmutables no se
reescriben; una corrección produce otra release y enlaces `CORRECTS`/`SUPERSEDES`
cuando el modelo los tenga.

## Escala

- El reader usa memoria O(page size), no O(corpus).
- El writer ordena en un spool SQLite y materializa chunks bounded; no conserva una
  colección completa transformada en memoria.
- `page_size <= 500` es fail-closed.
- Las páginas son JSON pequeños y los corpora masivos continúan en Parquet/CAS.
- Un millón de objetos con page size `250` produce unas `4,000` páginas, no un JSON
  de millón de filas.
- El release index y manifests permiten workers paralelos con verificación de hash.
- Los consumers pueden hacer checkpoint por `api_release_id + collection + cursor`.
- El adaptador actual lee el export analítico bounded existente. Las futuras lanes
  masivas deben alimentar el mismo page writer desde Parquet/JSONL o SQLite por
  partición; no requieren cambiar el contrato del reader.

## Publicación y gates

```bash
just evidence-api-v1-check
just cloudflare-pages-build
just site-publish
```

`evidence-api-v1-check`:

1. verifica origin y firma del snapshot upstream;
2. exporta con IDs/hashes deterministas;
3. valida pointer, release, manifests, páginas, cursor chain e inventario;
4. reconcilia conteos contra los exports reales;
5. compara todos los labels públicos con el input exacto;
6. exige provenance y states explícitos;
7. ejecuta tests usando solo los artifacts reales actuales.

El gate de publicación general añade validación real-only, ausencia de secretos y
paths locales, límite de `25 MB` por fichero y auditoría de rutas live.

## Ahora, dirección y siguiente

Ahora: existe una superficie v1 consumible, inmutable por release y bounded. Cubre
las respuestas reales que el sistema ya puede sostener y no presenta cobertura
parcial como conclusión completa.

Dirección: cada vertical slice nueva añadirá objetos al mismo vocabulario, siempre
con source record, evidencia, estado de incertidumbre y snapshot. Las colecciones
masivas vendrán de manifests Parquet/CAS, no de browser JSON monolítico.

Siguiente: implementar `TODO 18/19` sobre claims y promesas reales, y añadir esas
evidencias al API sin romper v1. En paralelo sigue abierto que un segundo mantenedor
reconstruya y firme de forma independiente el snapshot scale.
