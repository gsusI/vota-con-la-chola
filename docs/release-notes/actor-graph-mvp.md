# Time-aware actor graph MVP

Fecha: 2026-08-20

Estado: materializado, replay exacto y validación independiente superados;
publicación live en curso

## Resultado

Primer grafo temporal de actores sobre datos oficiales reales. Procesa el corpus
completo seleccionado; el JSON web es solo una proyección acotada.

Release:
`e52dd7fac6f29570d23756e927e0b9cfe73d1bf2f7c30fa01de75d4dc3a6f4a5`.

SHA-256 semántico de los inputs seleccionados:
`177545e3eab0bff97e03647805fbae82bda40f1831418a2944396267f12c31e7`.

Manifest actor/mandate de entrada:
`807d3841554d24872043bdd0e3210482fcf88d99e81a52a9a050b935f14a678c`.

SHA-256 del catálogo y mapeo completo de fuentes:
`b7d7d06f456bad77204d4b4e1a7fe9c17bd5cfc58a9a2888f2db9b26a22b40e3`.

Cobertura materializada:

- `133.595` actores;
- `121.960` personas, incluidas `5` personas contextuales PLACSP;
- `11.622` organizaciones;
- `8` oficinas;
- `5` actores cuyo tipo fuente sigue desconocido;
- `133.595` versiones de nodo;
- `79.208` identificadores públicos versionados;
- `4.186` aliases versionados;
- `237.973` relaciones y versiones de relación;
- `237.973` enlaces de evidencia;
- `133.595` decisiones explícitas de resolución;
- `133.595` evidencias de resolución;
- `30` scopes fuente usados por actores;
- `55` mapeos de origen para `51` IDs fuente upstream;
- `3` IDs upstream con metadata incompatible conservados como `7` scopes
  namespaced, sin escoger por precedencia;
- `0` merges cross-source;
- `0` merges por nombre;
- `0` eventos inventados de merger, split, rename o succession.

Inputs reales reconciliados:

- `88.031` mandatos;
- `87.068` afiliaciones de partido dentro del mandato;
- `42.056` ocurrencias base de candidaturas BOE;
- `10.820` estados efectivos revisados de candidatura BOE;
- `8.926` resultados electos Infoelectoral;
- `949` memberships de grupo parlamentario;
- `12` memberships organizativas;
- `40` roles actor en spending PLACSP;
- `37` parties de acuerdos Moncloa;
- `22` roles en reuniones Moncloa;
- `11` actores de acciones geopolíticas Moncloa;
- `1` partido publicador de manifiesto.

Evidencia:

- `174.296` relaciones con record exacto;
- `61.803` con documento exacto;
- `1.874` con URL oficial de fuente, expuestas como evidencia más débil;
- `0` relaciones sin evidence row;
- `0` FK violations;
- `PRAGMA integrity_check = ok`.

El artefacto web acotado contiene `32` nodos y `34` relaciones reales, pesa
`55.209` bytes y tiene SHA-256
`9272fb7395b1aa2392f1626d85ae1bc438ab9583a414b5ba6d4c1e37cc8b9f25`.
No reemplaza el grafo SQLite completo.

El export analítico lossless contiene `1.331.749` filas reales de las `13`
tablas del grafo en `179` particiones y `183` ficheros Parquet Zstd
(`144.407.180` bytes). El validator independiente reconcilió todas las filas,
hashes y schemas, `1.331.749` PK y `2.396.140` referencias FK con `0` ausentes.
La pasada full terminó en `84,12 s` con pico de `323,062 MiB`; la repetición
incremental reutilizó `179/179` particiones y reconstruyó `0`.

## Qué cambia

- Contrato detallado `docs/architecture/entity-resolution-v1.md`.
- Trece tablas aditivas para release, source mappings, node/version, identifiers, aliases,
  relationship/version/evidence, resolution decision/evidence y cambios de
  organización.
- Persona, partido, grupo parlamentario, institución, oficina y organización
  quedan separados.
- Los actors legacy se vuelven a scopear por fuente. El ID normalizado anterior
  no se presenta como identidad externa adjudicada.
- IDs fuente reutilizados con metadata distinta se conservan bajo
  `<source-id>@<database-key>`; los `55/55` orígenes están mapeados y validados.
- Fechas de mandato, candidatura, reunión, acuerdo y spending viven solo en la
  relación. `0` nodos o decisiones de identidad heredan esas fechas como vida
  de la persona u organización.
- Cada relación conserva valid time, observation time, presence, source, record,
  URL, hash y locator cuando existen.
- Los roles en spending, acuerdos, reuniones, geopolitics y manifiestos se
  integran como facts contextuales, no como tipos de identidad permanentes.
- Indicadores se leen como release context, pero no crean un actor responsable:
  outcome no implica causation.
- Información personal oficial pública preservada. Sin anonimización.
- Ningún dato synthetic, mock, fallback, placeholder o inventado.

## Límites

- No existe aún un gold set de identidad cross-source revisado.
- No se publica precision/recall de resolución porque todavía no hay decisiones
  humanas suficientes.
- No se materializa coalition membership, merger, split, rename o succession sin
  evidencia oficial revisada.
- Un path del graph no demuestra influencia, causalidad, mérito, culpa,
  corrupción ni conducta incorrecta.
- La ausencia de fecha no se imputa.
- La ausencia de una fila en otro snapshot no se tratará como delete; requiere
  segunda captura y presence version.
- SQLite y Parquet siguen siendo pruebas locales. Falta origin durable, restore
  clean-room y API paginada antes de promotion a escala.
- `1.331.749` filas de tablas/versiones/evidencia no significan un millón de
  actores: hay `133.595` nodos actor. El promotion gate permanece `false`.
- El SQLite actual ocupa `1.393.631.232` bytes; las tablas del grafo ocupan
  `712.417.280` bytes. No se extrapola esta representación textual a millones.
- El schema está preparado para versiones append-only, pero este builder de
  snapshot reemplaza el artefacto actual de forma atómica. La historia
  operacional multi-snapshot aún no está probada.
- La identidad del shell de relación ante evidencia multi-source debe cerrarse
  antes de activar resolución cross-source (`W3-006`).

## Verificación

```bash
just actor-graph-check
just etl-scale-validate-semantic-actor-graph
sqlite3 etl/data/staging/actor-graph-v1.db \
  < docs/examples/actor-graph-evidence.sql
just privacy-check-public-artifacts
just cloudflare-pages-build
```

Evidencia:

- `docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-materialization.json`
- `docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-validation.json`
- `etl/data/published/actor-graph-semantic-partition-manifest-latest.json`
- `docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-partition-validation.json`
- `docs/architecture/entity-resolution-v1.md`
- `docs/examples/actor-graph-evidence.sql`

Replay real: segunda ejecución completa produjo la misma release, los mismos
fingerprints de IDs, los mismos counts y el mismo JSON SHA-256. El validator
comparó el segundo resultado contra el reporte anterior con
`idempotent_rerun_reference=true`.

## Siguiente

1. Publicar `/actor-graph/` y verificar bytes/hash live.
2. Preparar gold set estratificado con decisiones vacías, dual review y
   adjudication.
3. Medir precision/recall por source, identifier y patrón de nombre.
4. Añadir segunda captura real y probar present/absent/superseded.
5. Publicar el full graph en origin durable y demostrar restore clean-room.
6. Añadir API paginada para el grafo completo.
7. Alcanzar `1M` facts representativos de actor/candidatura/mandato/cargo.
