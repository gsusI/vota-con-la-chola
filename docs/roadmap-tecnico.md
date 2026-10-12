# Roadmap técnico

Actualizado: `2026-09-05`.

Autoridad:

- dirección, secuencia y definición global de éxito: `ROADMAP.md`;
- estrategia del producto: `docs/roadmap.md`;
- estado operativo por fuente: `docs/etl/e2e-scrape-load-tracker.md`;
- registro verificable de corpora reales: `docs/etl/real-corpus-registry.json`.

Este documento traduce `ROADMAP.md` a trabajo técnico cercano. No crea scope nuevo.

## Lanzamiento comunitario: primer trabajo

Prioridad, recortes, capacidad y aceptación: [L0–L5 en ROADMAP](../ROADMAP.md#prioridad-inmediata-lanzamiento-útil-para-la-comunidad). Estado: alfa publicada; corte, paquete, demo y reproducción anónima remota verificados. Revisión comunitaria y adopción pendientes. Evidencia: [auditoría pública](etl/sprints/PUBLIC-LAUNCH-20260905/evidence/launch-audit.md).

1. **L0 — Fijar inputs.** Resolver `scale/latest.json` público a una release inmutable; usar `placsp_public_money` de `docs/etl/real-corpus-registry.json` y su manifest. Verificar descarga/checksums. Los `263302` facts incluyen `121555` anuncios y `141747` resultados de adjudicación; snapshot fuente `2025-03-31`. Reconciliar unidades con `ui/site/public/spending/data/placsp-sample.json`, procedente de otro corte. No mezclar contadores ni asumir contratos distintos.
2. **L0 — Comprobar semántica.** Resolver expediente/lote/versión, duplicados, moneda, significado del importe y fecha. Investigar particiones anómalas (el manifest contiene `year=1925`); preservar raw, declarar exclusiones justificadas en el derivado y comparar ejemplos públicos con la fuente. Elegir órgano y periodo solo tras verificar cobertura; sin denominador oficial, titular «en este corte».
3. **L1 — Reproducir una respuesta.** Adaptar `docs/examples/placsp-actor-spending-evidence.sql` al contrato Parquet real: ahora requiere una base staging que un recién llegado no tiene. Entregar consultas/datos fijados, resultados esperados y ejecución desde descarga pública en entorno vacío. No anunciar un comando nuevo hasta implementarlo y comprobarlo. Medir descarga/setup además de ejecución.
4. **L2/L3 — Usar lo existente.** Trabajar sobre `ui/site/app/spending/page.js`, `ui/site/app/page.js`, `README.md`, `CONTRIBUTING.md` y `docs/dev/quickstart.md`. Mantener navegación avanzada accesible con etiquetas fieles: `/explorer/` actual no ejecuta SQL. Separar uso de datos de desarrollo ETL. Para nuevas fuentes conservar `source_records_only`, captura oficial, procedencia y gates; no exigir expansión de ontología en la primera PR. SDK existente: `docs/examples/sample-plugin.md`.
5. **L4 — Publicar el mismo corte validado.** Aislar cambios del trabajo previo sin descartar nada. Ejecutar pruebas del exportador, consultas y UI afectada; `just privacy-check-public-artifacts`; gates aplicables y `just explorer-gh-pages-publish` para UI según las reglas del repo. Si cambian datos significativos, dry-run y publicación HF según su contrato. Verificar después descarga, hashes, resultado y enlace profundo públicos. Guardar evidencia antes de declarar listo.

Esta modificación documental no requiere ejecutar backfills ni `etl-contributor-gates`. En implementación, medir el coste de ese gate —incluye exportación de catálogo y dry-run HF— y separar checks por fuente de integración global sin eliminar validaciones requeridas. Ejecución actual: [evidencia del lanzamiento](etl/sprints/PUBLIC-LAUNCH-20260905/evidence/launch-execution.md).

## 1. Regla de ejecución

Solo cuentan registros capturados de fuentes oficiales identificables.

Cada slice debe conservar:

- URL y `source_id` oficiales;
- fecha de captura y estado HTTP;
- bytes raw con SHA-256;
- identidad del registro fuente;
- versiones de parser y schema;
- lineage de transformación;
- manifest de filas/ficheros/bytes/hashes;
- validación independiente del artefacto real;
- retención exacta de cada nombre, identificador y campo personal publicado por la fuente oficial, con URL/checksum/lineage; solo se bloquean secretos, credenciales, estado de sesión privada, trazas del workstation y datos no obtenidos de una fuente pública;
- límites, cobertura y siguiente gate.

Las muestras usadas en tests deben ser capturas oficiales con provenance. Datos inventados, endpoints locales y orígenes placeholder no cuentan como cobertura, capacidad ni readiness.

Gate canónico:

```bash
just etl-scale-readiness
just etl-storage-health
```

## 2. Estado actual verificable

| Lane | Filas reales | Artefacto actual | Estado |
| --- | ---: | --- | --- |
| votos nominales | `1,809,222` | `8,373` shards gzip, `170,990,631` bytes | validado; no promocionado |
| indicadores Eurostat | `1,755,809` | `37` Parquet, `253,373,860` bytes | validado; replay `26/26`; no representativo |
| PLACSP | `263,302` | `50` Parquet, `20,803,781` bytes | v5 validado; identidad source `128,849/128,849`; replay `50/50`; historia incompleta |
| BDNS | `1,360,382` | `14` Parquet, `42,955,289` bytes | v7 validado; `capacity_class=s2_1m`; nombres `1,360,382/1,360,382`, identificadores `163,270/163,270`; replay `1/1` por `14/14` hardlinks; 1,419 páginas y `89/89` fechas completas |
| accountability ledger | `126,760` | `13` Parquet, `1,271,649` bytes | real-only validado; replay `13/13`; mix parlamentario |
| actores/mandatos | `88,031` | `108` Parquet, `9,236,064` bytes | validado; replay `108/108`; bajo `100k` |
| candidatos BOE | `42,056` base / `10,820` efectivos | `2` Parquet, `2,083,541` bytes | identidad/texto oficial base `42,056/42,056`; lineage efectivo normalizado; `88` filas corregidas; `31,241` base pendientes excluidas; outcome desconocido explícito; replay `2/2`; origin firmado y restore aislado pasan; no promocionado |

Defectos visibles:

- actualización documental `2026-08-30`, que supersede las cifras documentales anteriores conservadas como historial: source-universe validado `337,704` edges / `115,246` URLs oficiales / `111,600` HTTPS / `101,303` elegibles; gap numérico `0`. Planner exacto fija `100,000` filas reales (`98,748` BOE XML + `1,166` BOE summaries + `86` Parlamento de Andalucía), SHA `c81d3c0...`, preflight completo y cero synthetic/mock. Captura BOE física queda `100,051/100,867`, `1` dead y `815` unfinished; el lineage activo referencia `1,156/1,166` summaries success y readiness falla cerrado. Corpus actual: `122,653` instancias / `120,801` contenidos / `5,652,067,717` bytes; provenance checksum+URL `122,540`, gaps `113`, conflicts `0`; extracción v3 `3,192,030,152` chars / `119,346` CAS / cero fallo o truncación. Locator v5 cubre `30,634` páginas PDF + `782,814` secciones XML/HTML + `5,333` spans fallback + `261` row groups XLSX: `819,042` locators de contenido / `879,374` de instancia, full replay y cero mismatch. Perfil real: `108,042` XML / `13,128` HTML / `1,437` PDF / `46` XLSX. Las `44` XLSX distintas replayan con `openpyxl`; inventario de instancia: `2,845,172` filas. Fanout XLSX: media `5.931818`, máximo `6`, proyección `5,931,818/1M`, techo `10M`. Fórmulas observadas: `0`; no se declara corrección de fórmulas ni soporte para otros formatos office. Las `46` URLs XLSX inferidas quedan `mapped_unverified`, sin crédito de provenance. OCR `856/856` / `131` CAS; review humano `0/40`. Origin/restore/package local actual pasa para `240,278` objetos / `6,048,142,788` bytes; dry-run local y preflight HF read-only pasan sin mutación. Telemetría native/OCR current-full es warm-output; benchmark cold ausente y coste monetario desconocido. Cierra procesamiento/lineage actual, no BOE, `DEC-01`, review, origin remoto durable, cold economics ni `1M`;
- votos: URL pública/source record `100%`; las `102,172` filas HTTP / `1,166` URLs están clasificadas: `33,683` filas / `484` URLs tienen captura checksum local y `68,489` filas / `682` URLs siguen sin replacement inmutable; dos probes HTTPS acotados devolvieron `403` HTML y ninguna URL histórica fue reescrita;
- candidatos: siete proclamaciones BOE conservan `42,056` ocurrencias base / `4,901` candidaturas (`25,077` titulares; `16,979` suplentes) para seis fechas electorales entre 2015 y 2024. Once correcciones retienen `956` párrafos exactos. El subconjunto revisado de 2023/2024 conserva `10,815` base / `1,188` candidaturas y tres correcciones con `180` párrafos: `127` sostienen `17` operaciones y `53` quedan como contexto; produce `10,820` efectivas con lineage completo, `10,795` links base reutilizados, `25` identidades BOE-scoped y `88` source records corregidos. Ocho correcciones / `776` párrafos y sus `31,241` candidatos base quedan `captured_unapplied` y excluidos del efectivo. Una cola determinista exporta los `776` párrafos a dual review con decisiones vacías y separa un contexto deduplicado de `3,713` candidaturas / `31,241` candidatos; regenera preservando review idéntico o falla ante drift. Noviembre 2019 se conserva como documento pero falla cerrado porque la fuente omite un número obligatorio. El artifact semántico valida y replays `2/2`, outcome null; los `8,926` resultados electos son otro hecho. No se infiere identidad cross-source ni identificadores ausentes;
- BDNS: el root actual valida `1,360,382` filas oficiales y cruza el gate de capacidad `R2`; las `89/89` ventanas seleccionadas están completas; origin y clean-room restore pasan, pero faltan historia completa y segundo snapshot para promoción;
- ledger: `126,760` facts reales recuperados; `10` facts derivados de fixtures fueron purgados; `26` source IDs legacy se infieren explícitamente desde URL BOE oficial; origin y clean-room restore pasan; faltan mix representativo y `1M`;
- documentos: inventario v6 reconcilia `122,653` instancias / `120,801` contenidos / `5,652,067,717` bytes y cuatro formatos reales: XML `108,042`, HTML `13,128`, PDF `1,437`, XLSX `46`. Extracción v3 produce `3,192,030,152` caracteres / `119,346` CAS; locator v5 produce `819,042` filas de contenido / `879,374` de instancia. `openpyxl` replaya las `44` XLSX distintas y sus valores públicos; `261` row groups quedan bajo el contrato de fanout a `1M`. Fórmulas `0`: soporte no probado. Provenance valida `122,540` y deja `113` gaps; las `46` URL mappings XLSX son inferidas, `mapped_unverified`, y no suman crédito. Origin filesystem actual replica/restaura `240,278` objetos / `6,048,142,788` bytes; `25` packs y release `a891bbab...` (`154` ficheros / `2,250,233,559` bytes) pasan validación local. HF preflight fue read-only; no hubo upload, commit ni pointer change. Economics valida current-full native/OCR sobre output warm; cold-output y tarifas monetarias quedan abiertos. Captura BOE `100,051/100,867`, lineage `1,156/1,166` summaries y `815` unfinished mantienen readiness en rojo;
- planificación y lineage documental: v4 usa SQLite file-backed, cursor ordenado, shards gzip bounded, hashes exactos, locks kernel, inputs rehasheados y manifest-last recuperable. El plan `100k` valida `100,000/100,000` filas reales sin afirmar transporte completo ni representatividad. BOE mantiene `100,051` filas en `11` shards y lifecycle no destructivo, pero debe reconciliar los `10` summaries success ausentes del lineage activo y cerrar `815` jobs. Native/OCR/profile/locator activan solo generaciones terminales, archivan índices/receipts, retienen snapshots SQLite, hacen live-switch al final y prohíben delete; full replay/lifecycle pasan sobre la generación actual. Próximo paso controlable: preservar esos gates y cerrar gaps de provenance XLSX solo con receipts/manifests exactos. Próximo paso externo: esperar nueva palanca BOE, reintentar una vez, cerrar cola/lineage y activar la generación final. `DEC-01`, review humano, origin remoto y `1M` permanecen separados;
- outcome C2B: el planner SQLite real de `2,865,602` filas se mantiene separado del formato de entrega. El companion conserva exactamente `119,116` votos nominales / `490` nombres públicos / `458` acciones en `8` Parquet; el paquete portable añade `1,205` Parquet de pares y totaliza `1,213` ficheros / `251,522,252` bytes. La prueba canónica se interrumpió tras `25` particiones durables, invalidó controles de éxito obsoletos, reanudó los `25` checkpoints y completó `1,205/1,205`; manifest root `81cc315e...`. Raíces semántica `2afaf9ef...`, física `f2d50fa5...` y portable `049f9718...` coinciden entre canonical y replay byte a byte. Validator full-row: `376.845s`, `621.047 MiB`, techo `1 GiB`; `22/22` tests de identidad y `23/23` de paquete pasan. `ranking_eligible_rows=0`, `publication_eligible_rows=0`, `private_token_findings=0`; los nombres oficiales no se suprimen;
- review C2C: Python `3.12` queda fijado porque el runtime host alteraba el hash físico SQLite. El capacity artifact actual tiene `2,865,603` tareas / `2,865,604` slots, `115` batches, `2,864,201,728` bytes, SHA `a97f9941...`, semantic root `21acddf2...`, `330/330` checks y `12/12` tests adversariales. Materialización: `366.340s`, `7,822.249` filas/s, `370,376,704` bytes RSS. Validator: `159,727,616` bytes RSS. Todas las `16` tablas de trust/reviewer/auth/conflict/assignment/claim/decision/adjudication/eligibility/promotion/release/publication/audit operacional contienen `0` filas. Es capacidad local, no operación humana;
- lanes promocionadas: `0`.

El reporte `etl/data/published/scale-readiness-latest.json` permanece `not_ready`, `foundation.ready=false` y `failure.reason=BOE document corpus checks failed`. La ejecución enforced actual valida primero los gates XLSX/origin/economics y se detiene honestamente en lineage/cola BOE; ausencia de benchmark cold se registra como gap de medición, no como fallo de integridad ni como coste cero. `real_foundation_ready_scale_incomplete` solo puede reaparecer cuando el builder actual pase. Después seguirán abiertos representatividad, review, origin público/restore remoto, coste real y `1M`.

## 3. Sprint inmediato — recuperación de verdad

### RT-000 — Cerrar el salto documental `100k` sin falsear escala (`P0`)

Orden obligatorio derivado de `ROADMAP.md` `W2`:

1. `DONE`: preservar supply numérico `>=100,000` mediante source-universe report + validator; actual `101,303`, gap `0`;
2. `DONE`: preservar plan exacto `100,000`, selection SHA `c81d3c0...`, full preflight, real-only/public-identity gates y queue prístina;
3. `BLOCKED_EXTERNAL`: no repetir BOE este sprint. Esperar palanca nueva: señal upstream fresca, ruta bulk BOE documentada o canal oficial alternativo reproducible;
4. con palanca nueva, ejecutar un único control acotado sobre `BOE-A-2022-13616`; si falla igual, actualizar incidente y parar;
5. si responde, ejecutar `etl-scale-boe-document-requeue-transient-failures`; no usar requeue genérico ni modificar attempts sin telemetría;
6. reanudar cola; claims normales recuperan leases expirados. Exigir progreso atómico por batch y budget acumulado `<=500,000`;
7. exigir `etl-scale-boe-document-status` verde: `100,867/100,867` documentos success, `0` dead/unfinished, `1,166/1,166` summary captures success referenciados, checksum/bytes/manifest exactos;
8. `DONE 2026-08-30`: sustituir lineage BOE monolítico por index + shards acotados. Resultado real: `11` shards, máximo `10,000` filas / `64 MiB` uncompressed por shard, `16,081,029` bytes comprimidos, índice `7,717` bytes, full validator verde;
9. `DONE 2026-08-30`: cerrar lifecycle/supersession del lineage BOE. Cada índice queda archivado por SHA-256; el pointer live cambia después de shards + archive; receipt inmutable registra predecessor; reactivation ambigua falla; no hay delete automático. Test con capturas reales interrumpe antes del switch, conserva índice anterior y candidato reportado, luego completa successor reteniendo ambas generaciones. Auditor producción: `1` archive, `1` receipt, `1` generación, `11` shards, `0` orphan/unactivated/staging/delete;
9. `DONE current captured generation`: inventario v6 y provenance v13 reconcilian `122,653` instancias; `122,540` tienen checksum+URL, `113` son gaps explícitos y conflicts=`0`. Las `46` mappings XLSX inferidas quedan `mapped_unverified` sin crédito; tras BOE, regenerar sobre la generación final;
10. `DONE current captured generation`: activar native/OCR/profile/locator solo en estado terminal, con shards bounded, índice archivado, receipt, snapshot SQLite, live-switch final y delete prohibido;
11. `DONE current captured generation`: extracción v3 + validator full raw/CAS, OCR + validator, profile + validator, locator v5 + full replay y lifecycle pasan para `122,653` instancias / `120,801` contenidos; mantener `0/40` hasta decisiones humanas reales;
11a. `DONE real XLSX cohort 2026-08-30`: procesar `46` instancias / `44` workbooks distintos / `2,845,172` filas de instancia; replay independiente `openpyxl` de valores públicos. Mantener fórmulas `unproven` porque el cohort contiene `0`;
11b. `DONE bounded XLSX locators 2026-08-30`: `261` row groups, promedio `5.931818`, máximo `6`, proyección `5,931,818/1M`, hard ceiling `10M`;
11c. `DONE local mechanics 2026-08-30`: replicar y restaurar `240,278` objetos raw/native/OCR / `6,048,142,788` bytes mediante queue resumable y scratch bounded; lifecycle no-delete verde. Mantener `durable_public_origin_proven=false` hasta origin remoto autorizado;
11d. `DONE immutable local package 2026-08-30`: `25` packs deterministas, limitados por objetos y bytes, member manifests checksum-addressed, queue resumable y full rehash `240,278/240,278`;
11e. `DONE release-safe read-only preflight 2026-08-30`: release `a891bbab...`, `154` ficheros / `2,250,233,559` bytes; dry-run local y preflight HF read-only sin conflicts ni mutación. No marcar durable hasta upload data -> manifest -> parity -> pointer y restore independiente;
11f. `PARTIAL economics 2026-08-30`: current-full native/OCR valida output warm; dashboard trata cold ausente como gap de medición y conserva integridad fail-closed. Ejecutar benchmark con state+output realmente vacíos y añadir tarifas reales antes de publicar coste/1,000;
12. resolver `DEC-01`: aprobar la mezcla BOE-heavy como prueba de carga solamente o producir selección representativa nueva antes de adquisición cold;
13. ejecutar adquisición física de la selección aprobada, validar every-row source contract, revisions, requests/bytes/RSS/cost, luego raw-origin upload + clean restore;
14. solo después abrir `1M`, por shards/source periods, con checkpoint, correction path y delivery bounded.

Gates que no se fusionan:

| Gate | Estado `2026-08-30` | Cierre |
| --- | --- | --- |
| supply numérico | `DONE` | `101,303 >= 100,000`, replay independiente |
| plan exacto | `DONE` | `100,000/100,000`, SHA de selección fijado, preflight verde |
| captura fuente BOE | `BLOCKED` | `100,867/100,867`, `0` dead/unfinished |
| lineage BOE | `PARTIAL` | `1,166/1,166` summaries success referenciados; actual `1,156/1,166` |
| corpus procesado actual | `DONE_FOR_CAPTURED_GENERATION` | `122,653` raw + `119,346` text CAS + `856` OCR; PDF/XML/HTML/XLSX replayados |
| provenance corpus | `PARTIAL` | `122,653/122,653` checksum+URL o gap explícito; actual `122,540` verificados / `113` gaps, sin dar crédito a mappings inferidas |
| representatividad | `DECISION_REQUIRED` | matriz aprobada source/jurisdiction/time/format/language/size |
| quality humana | `OPEN` | `40/40` dual review + adjudicación + métricas por estrato |
| raw durability | `LOCAL_DONE_REMOTE_OPEN` | local actual `240,278/240,278`; falta origin externo inmutable + restore vacío + rehash independiente |
| economics | `PARTIAL` | current-full warm pasa; falta cold state+output, tarifas monetarias y coste/1,000 |
| document `R2` | `OPEN` | `1M` real + todos los SLOs §4.2 |

### RT-001 — Mantener el registry real-only

Implementado:

- registry explícito por lane;
- allowlist de `source_id` y host oficial;
- hash de registry, manifest y validation;
- verificación de cada fichero declarado;
- conteo real desde gzip/Parquet;
- lectura de `source_id` y `source_url` de todas las filas;
- validación de replay por hardlink para Eurostat, PLACSP, ledger, actores y candidatos;
- promotion separada del row gate.

DoD:

- `python3 -m unittest tests.test_report_scale_readiness` pasa;
- `just etl-scale-readiness` pasa;
- ningún artifact ausente cuenta;
- ningún endpoint no oficial cuenta;
- cualquier fila sin URL/lineage aparece como gap.

### RT-002 — BDNS semántico v7 (`R2` de capacidad cerrado; promoción abierta)

Entrada ejecutada:

- DB `etl/data/staging/bdns-concessions-partitioned-real-s3-20260812.db`;
- CAS `etl/data/object-origin/bdns-concessions-partitioned-real-s3-20260812`;
- `1,419` páginas oficiales de hasta `1,000` filas, distribuidas en `89` ventanas diarias completas.

Resultado:

1. queue `1,419 succeeded / 0 unfinished / 0 dead / 0 retries`;
2. `1,360,382` records, source IDs, record URLs y version sightings distintos;
3. `1,080,788,680` raw bytes en `1,419` objetos checksum-linked;
4. SQLite `quick_check=ok`, FK `0`;
5. `public_money_facts_v5` contract, artifact v7: `1,360,382` rows, `14` Parquet, `42,955,289` bytes y `capacity_class=s2_1m`;
6. nombres oficiales `1,360,382/1,360,382` e identificadores source `163,270/163,270` retenidos exactamente;
7. validator full-row verde, `0` private tokens, replay `1/1` partición por `14/14` hardlinks;
8. `89/89` ventanas completas tras expansión append-only; corpus registrado con row-scale gate verde, `durable_public_origin=true` y restore desde cache vacío validado contra la release v2; `promotion_gate_passed=false` por historia incompleta y segundo snapshot.
9. el worker hace preflight antes de cada claim y reserva CAS + crecimiento SQLite/WAL. Un preflight intermedio llegó a verde tras liberar temporales, pero el actual vuelve a fallar cerrado con `5,685,862,400` bytes libres frente a `10,863,247,360` requeridos y headroom `-5,177,384,960`; no se reclama más trabajo.

Comandos base:

```bash
just etl-scale-bdns-bulk-report
just etl-scale-bdns-storage-preflight
just etl-scale-bdns-bulk-version-lineage
just etl-scale-export-semantic-public-money
just etl-scale-validate-semantic-public-money
```

DoD `S1`: `DONE 2026-08-12`.

- source/page/version/amount/public-field totals exactos;
- manifest, validation y replay actuales;
- registry/readiness/tracker actualizados;
- lane global sigue `PARTIAL` hasta segundo snapshot e historia representativa.

Siguiente salto:

1. recuperar al menos `5,177,384,960` bytes de headroom y exigir preflight verde de disco, origin y request budget antes de cada cohorte;
2. nueva cohorte durable sin reutilizar el checkpoint v3 no conforme;
3. mismo pacing/circuit; detener ante error-rate o latencia fuera de presupuesto;
4. exportar v5 solo después de reconciliar `1,000/1,000` páginas y `1M` filas reales.

### RT-002B — Origin bundle analítico (`P0`, rollback y raw objects abiertos)

Implementado:

- `scripts/publicar_hf_scale_snapshot.py` empaqueta únicamente registry, readiness, manifests, validations y ficheros canónicos declarados;
- valida path, bytes y SHA-256 de cada fichero antes de staging;
- usa hardlinks cuando es posible y no transforma ni suprime identidad pública;
- `scripts/verify_hf_scale_origin.py` reconstruye el bundle local, compara fail-closed el contrato estable de data/provenance y reporta drift de registry/readiness como metadata separada;
- `scripts/restore_hf_scale_origin.py` restaura por corpus con concurrencia acotada, preflight de storage, partials atómicos y bytes/SHA-256 exactos; el recipe canónico exige destino vacío, attestation válida y trust root externo, y acepta `--snapshot-path` inmutable para recovery sin depender de `latest`;
- `scripts/rebuild_restored_scale_sqlite.py` importa corpora Parquet restaurados por batches, conserva strings/listas/identidades publicados, compara hash lógico input/SQLite, exige integridad y RSS acotado, y hace publish local por rename atómico;
- `scripts/replicate_content_objects.py` y `scripts/verify_object_store_restore.py` procesan manifests en batches acotados con workers configurables; el manifest de objetos elimina timestamps por fila para ser determinista, el restore completo hace preflight de bytes + reserva antes de transferir, y el report conserva generated/throughput;
- el publisher tabular incluye `data-integrity-latest.json` y `scale-readiness-latest.json` en el snapshot actual.

Evidencia real actual:

- release firmada contract-bearing publicada: `7` corpora, `5,414,326` filas, `8,597` data files y `500,714,815` data bytes; release `5d9ce557...`, artifact contract `d7de5544...`. Pointer, manifest, registry/readiness, políticas y attestation SSH Ed25519 verifican live sin errores ni warnings;
- parity remota: pointer, manifest, artifact contract y contratos de los siete corpora coinciden. La identidad `vclc-snapshot-release-2026` firma el manifest exacto y el verificador confía solo en el `allowed_signers` externo;
- clean-room restore de las siete lanes: los seis corpora históricos validan `5,403,506` filas / `8,595` data files. El drill adicional anónimo GET-only de `candidate_occurrences` descarga `8` ficheros seleccionados / `2,211,900` bytes a un root inexistente, con `0` reuse, credenciales o mutación; el validator aislado usa el registry bundled y reconcilia `10,820` filas / `2` Parquet / `2,083,541` data bytes en un inventario exacto de `14` ficheros;
- recovery de release explícita: un cache vacío apuntado directamente a `scale/snapshots/2026-08-12/623b4a5a...` descarga y verifica `8,619/8,619` ficheros / `504,093,303` bytes en `1,199.614s`, sin consultar el pointer `latest`; el validador full-read pasa los seis corpora / `5,403,506` filas con peak RSS `1,007.453 MB`; el cache desechable se retiró. `just etl-scale-origin-hf-prepare-rollback` revalida live current/target, enlaza evidencia por SHA-256 y emite un plan compare-and-swap con delta cero, preservación de ambas releases y ninguna mutación;
- rebuild SQLite determinista: dos ejecuciones independientes desde ese restore actor producen `88,031` filas, `88,031` mandate IDs distintos y DBs byte-idénticos de `71,168,000` bytes (`SHA-256 61cfdf8e...`); el hash lógico de todas las columnas es `eb7fdb8e...`, `integrity_check=ok` y peak RSS queda entre `229.750` y `233.578 MB`;
- raw-object CAS local: `16` workers procesan los `6,792` objetos reales enlazados / `133,219,457` bytes; replay deduplica `6,792/6,792`, repite manifest de `2,733,754` bytes con SHA-256 `6e496f35...`, y restore `full_manifest` recupera `6,792/6,792` tras preflight con reserva `10 GiB`. El throughput warm/local observado (`7,482.620` objetos/s en dedupe; hasta `5,028.098` objetos/s en restore) no se extrapola a red;
- origin documental local actual: replica y restaura `240,278/240,278` objetos raw/native/OCR / `6,048,142,788` bytes; empaqueta `25` archives deterministas y prepara release `a891bbab...` de `154` ficheros / `2,250,233,559` bytes. Dry-run local y preflight remoto read-only pasan; no hubo upload, commit ni pointer mutation y este resultado no cambia `durable_public_origin_proven=false`;
- durable origin y clean-room restore pasan en las siete lanes publicadas. Ninguna se promociona por ello: representatividad, historia, reconciliación y correcciones siguen mandando.

DoD pendiente: reconstruir el esquema normalizado y sus relaciones desde inputs inmutables, activar/revertir `latest` bajo autorización explícita, registrar el evento de supersession, aprobar RPO formal, medir activation RTO y publicar/verificar el CAS completo en un origin S3-compatible con versioning/retention. El plan read-only ya fija compare-and-swap y no confunde delta cero con RPO. El publisher evita paths mutables y el contrato estable evita que cambiar el propio flag de publicación invalide la paridad de datos.

### RT-003 — Regenerar accountability ledger

Pasos:

1. congelar snapshot y DB de entrada;
2. ejecutar backfill sin incorporar facts sin source record;
3. reconciliar `accountability_entries`, evidence edges, actores e issues;
4. separar `resolved`, `unresolved`, `conflict` y `unknown`;
5. exportar Parquet tipado a root nuevo;
6. validar todas las filas y hashes;
7. replay unchanged;
8. añadir al registry solo si el root existe y pasa.

Comandos base:

```bash
just etl-backfill-accountability-ledger
just etl-scale-export-semantic-accountability-ledger
just etl-scale-validate-semantic-accountability-ledger
```

DoD:

- no edge huérfano;
- `100%` de claims publicables con evidencia;
- mix por tipo/source/issue publicado;
- dominancia parlamentaria explícita;
- no promotion antes de `1M` real representativo.

### RT-004 — Reconciliar documentos reales

Pasos:

1. `DONE_FOR_CAPTURED_GENERATION 2026-08-30`: inventario v6 `122,653` instancias raw oficiales / `120,801` contenidos / `5,652,067,717` bytes. Perfil cubre todo: `122,334` machine-language candidates, `319` unknown explícitos; encryption observada para `1,437` PDF, `46` XLSX `not_applicable_office_archive` y `121,170` XML/HTML `not_applicable_plain_markup`. Replay independiente rehasha raw+CAS y reclasifica `120,801/120,801` sin mismatch. Todo candidato sigue `unreviewed`; no es ground truth humano;
2. `PARTIAL/BLOCKED 2026-08-30`: worker persiste eventos de request, progreso atómico, budgets conservadores ante crash, límites por host, redirect refusal, fairness y circuitos por HTTP/network/timeout. BOE tail usa budget `500,000`, avanza `63` objetos dentro del último batch y queda `100,051/100,867`; `1` dead tras tres timeouts, `815` unfinished. El incidente `nso-2026-08-boe-document-xml-connect-timeout` prohíbe repetir sin palanca nueva;
3. `PARTIAL 2026-08-30`: provenance balancea `122,653/122,653`, verifica checksum + URL para `122,540`, preserva `113` gaps y `0` conflicts. Las `46` mappings XLSX inferidas quedan `mapped_unverified`, sin receipts ni crédito. Manifest BOE reconcilia `100,051` documentos, pero solo `1,156/1,166` summaries success y falla completion;
4. `DONE_FOR_CAPTURED_PDF_XML_HTML_XLSX_GENERATION 2026-08-30`: native state v9 procesa `120,801/120,801` contenidos / `5,435,782,744` bytes distintos, conserva `3,192,030,152` caracteres en `119,346` current CAS, `0` retry/dead/failure/truncation. Validator rehasha `122,653` raw y todos los CAS; `openpyxl` replaya `44/44` XLSX distintos, `2,827,577` filas no vacías / `28,615,639` celdas. Locator v5 cubre `30,634` páginas PDF + `782,814` secciones markup + `5,333` fallbacks + `261` row groups XLSX; replay recomputa `879,374` filas de instancia con `0` mismatch. Fórmulas reales `0`, por tanto formula semantics quedan unproven;
5. `DONE_FOR_CAPTURED_GENERATION 2026-08-30`: OCR state v6 procesa `856/856`, `849` text, `7` no-text, `89,632` chars, `17` gains, `131` CAS; validator verifica `58` PDFs y cada CAS;
6. `READY_FOR_HUMAN_REVIEW 2026-08-30`: packet determinista `40` páginas conserva campos humanos vacíos; integrity pasa, promotion false, review `0/40`; no machine-generated labels;
7. `PARTIAL 2026-08-30`: source-universe replaya `337,704` edges y fija `101,303` URLs elegibles / gap `0`. Planner prepara/preflighta `100,000` filas, SHA `c81d3c0...`, `98,748/1,166/86` por cohorte. Falta `DEC-01`, captura física terminal y final-generation rerun;
8. `PARTIAL 2026-08-30`: economics conserva adquisición física `10k` ligada a su run exacto. Native actual mide `328.374s` wall / `1,385,299,968` bytes peak self RSS y OCR valida su current-full run; ambos reutilizan output existente (`cold_state_and_output=false`). Dashboard acepta esos cold flags en false solo como gaps de medición; todos los checks de integridad siguen obligatorios. BOE partial no autoriza denominador completo `100k`; coste monetario sigue unknown hasta meter/rate real;
9. `DONE_LOCAL_REMOTE_OPEN 2026-08-30`: origin/restore local `240,278/240,278` objetos / `6,048,142,788` payload bytes; `25` packs y release `a891bbab...` (`154` ficheros / `2,250,233,559` bytes) rehasheados. Dry-run local y HF preflight read-only pasan; mutation=`false`, durable public origin=`false`;

Comandos base:

```bash
just etl-scale-inventory-documents
just etl-scale-export-xlsx-lineage
just etl-scale-recover-wayback-document-lineage
just etl-scale-recover-archived-document-lineage
just etl-scale-recover-captured-document-links
just etl-scale-recover-official-document-identifiers
just etl-scale-recover-official-path-documents
just etl-scale-audit-document-provenance
just etl-scale-reconcile-documents
just etl-scale-process-document-corpus
just etl-scale-document-language-encryption-profile
just etl-scale-document-text-locators
just etl-scale-replicate-document-origin-local
just etl-scale-restore-document-origin-local
just etl-scale-pack-document-origin
just etl-scale-validate-document-origin-packs
just etl-scale-document-origin-hf-dry-run
just etl-scale-document-origin-hf-preflight
just document-factory-economics-export
just etl-scale-prepare-document-page-ocr-review
just etl-scale-validate-document-page-ocr-review
just document-factory-disk-planner-test
just document-factory-disk-planner-10k-verify
just document-factory-disk-planner-max-verify
just document-factory-disk-planner-100k-prepare
just document-factory-disk-planner-100k-verify
just document-factory-source-universe-report
just etl-scale-boe-document-requeue-transient-failures
just etl-scale-boe-document-status
just etl-scale-require-document-page-ocr-review
just parl-enqueue-document-fetch-work
just parl-run-document-fetch-work
just document-fetch-operations-export
just parl-enqueue-text-extraction-work
just parl-run-text-extraction-work
```

DoD:

- balance exacto por stage;
- cero parcial huérfano;
- cada failure terminal con razón/replay;
- muestra de calidad revisada por humanos;
- coste y SLO medidos antes de `1M`.
- lineage BOE indexado en shards bounded, no un único control file creciente;
- cada generación native/OCR tiene identidad/supersession explícita y restore reproducible.
- cada generación profile tiene machine-candidate/unknown explícito, full replay, identidad/supersession y restore reproducible; ninguna etiqueta probabilística se presenta como review humano.

### RT-005 — Cerrar provenance de votos

Pasos:

1. `DONE`: aislar el único evento responsable de las `350` URLs nulas;
2. `DONE`: verificar el endpoint oficial Congreso con browser-equivalent request;
3. `DONE`: registrar URL, hash oficial, hash capturado, diferencia semántica y event ID estable en sidecar;
4. `DONE`: inventariar las filas con URL HTTP por cámara/legislatura mediante `just etl-scale-audit-vote-source-urls`: `102,172` filas / `1,166` URLs, todas de Senado legislaturas 10 y 12; `33,683` filas / `484` URLs tienen captura checksum local y `68,489` / `682` no;
5. `PARTIAL`: dos probes HTTPS content-equivalence acotados devolvieron `HTTP 403` con HTML de `417/418` bytes; no reescribir URLs y no repetir red sin una palanca nueva;
6. `DONE`: reexportar `8,373` shards y validar `1,809,222/1,809,222` URLs/source records;
7. mantener incompatibilidades como gaps públicos.

DoD:

- `100%` source record;
- `100%` public URL o replacement oficial inmutable;
- HTTPS o excepción content-addressed explícita;
- official totals reconciliados o discrepancia clasificada por evento.

Audit offline repetible:

```bash
just etl-scale-audit-vote-source-urls
```

Los probes de red son explícitos y solo se repiten si cambia el endpoint, existe una sesión reproducible o aparece otro canal oficial.

## 4. Backlog técnico priorizado

### P0 — storage y recovery

| ID | Entregable | DoD |
| --- | --- | --- |
| `STO-001` | ADR de origin S3-compatible | bucket/key/version/retention/encryption; sin secretos |
| `STO-002` | upload idempotente por SHA-256 | HEAD/GET verifica bytes y checksum |
| `STO-003` | release manifest remoto | objetos, bytes, ETags/checksums y latest pointer balancean |
| `STO-004` | cache descartable | borrar cache no pierde evidencia |
| `STO-005` | restore sample | muestra estratificada restaura `100%` |
| `STO-006` | restore full lane | lane `>=1M` valida desde entorno limpio |
| `STO-007` | rebuild SQLite | snapshot reproduce counts, FK y logical IDs |
| `STO-008` | rollback | release anterior vuelve sin mezcla de versiones |

### P0 — queues y observabilidad

| ID | Entregable | DoD |
| --- | --- | --- |
| `OPS-001` | contrato único pending/leased/succeeded/dead | attempts append-only |
| `OPS-002` | claims atómicos e indexados | query plan sin full scan/sort |
| `OPS-003` | heartbeat | tarea larga no se reclama dos veces |
| `OPS-004` | retry taxonomy | 403/404/429/5xx/timeout/parse/oversize distintos |
| `OPS-005` | circuit breaker por host | apertura/cierre y razón persistidas |
| `OPS-006` | stage balance | discovered = terminal states; fetched = parsed + failures |
| `OPS-007` | source drift | cambio de schema/body/count bloquea solo lane afectada |
| `OPS-008` | run telemetry | bytes, requests, CPU, RSS, latency, retries, cost |
| `OPS-009` | unattended recovery | kill de worker/source/storage/publish se detecta y recupera |

### P0 — documentos

| ID | Entregable | DoD |
| --- | --- | --- |
| `DOC-001` | inventory completo | `DONE_FOR_CAPTURED_GENERATION 2026-08-30`: source/MIME/bytes/pages/sheets/density y machine-language candidate/unknown para `122,653/122,653`; `120,801` contenidos, `46` XLSX / `44` distintos. Encryption status es explícito: observado en PDF y `not_applicable` en XLSX/markup; full raw/CAS replay y lifecycle pasan. Review lingüístico/representatividad, fórmulas, otros formatos office y rerun post-BOE siguen abiertos |
| `DOC-002` | fetch streaming | límite duro, SHA, atomic commit, cero parciales |
| `DOC-003` | digital extraction | `DONE_FOR_CAPTURED_PDF_XML_HTML_XLSX_GENERATION 2026-08-30`: `122,653/122,653` instancias, `120,801/120,801` contenidos, `3,192,030,152` chars, `119,346` CAS, `0` retry/dead/truncation. `30,634` páginas PDF + `782,814` secciones markup + `5,333` spans fallback + `261` row groups XLSX reconstruyen exactamente el CAS; validator rehasha raw/native y recomputa `879,374` locators de instancia con `0` mismatch. `openpyxl` replaya las `44` XLSX distintas. Fanout XLSX proyecta `5,931,818/1M` bajo techo `10M`; fórmulas observadas `0`, por tanto no validadas. Faltan otros formatos office y generación final post-BOE |
| `DOC-004` | OCR routing | `DONE current corpus`: `856/856` páginas pobres; razón persistida |
| `DOC-005` | OCR cache | `DONE current corpus`: input manifest + engine/language/version/config; rerun reclama `0` |
| `DOC-006` | quarantine | bombs, corruptos, password y unsupported separados |
| `DOC-007` | quality gold set | `PARTIAL`: packet real `40`, review humano `0/40`; falta doble review, métricas y adjudicación |
| `DOC-008` | `100k` real | `PARTIAL 2026-08-30`: supply `101,303`, gap `0`; plan exacto `100,000` y preflight pasan con SHA `c81d3c0...`, cero mock/synthetic y public identity retained. Captura BOE física `100,051/100,867`; `815` unfinished y lineage `1,156/1,166` summaries success bloquean readiness. Faltan palanca BOE, terminal queue/lineage, `DEC-01`, physical selected-cohort run, final processing generation, human review, remote origin/restore, cold benchmark y tarifas reales |
| `DOC-009` | `1M` real | Current pipeline: BOE `100,051`, native `122,653`, locator `879,374`, OCR `856`; lifecycle crash-safe. Fanout global `6.780093` proyecta `6,780,093/1M`; XLSX `5.931818` proyecta `5,931,818/1M`, ambos bajo `<=10` promedio; máximo global `1,568` bajo `<=2,000`, XLSX máximo `6` y techo absoluto `10M`. Origin/restore local pasa para `240,278` objetos / `6,048,142,788` bytes; `25` packs y release `a891bbab...` validan localmente y pasan preflight remoto read-only sin publicar. Faltan BOE, `DEC-01`, human quality, origin público + restore independiente, cold economics, corrections, changed-production chains y ejecución/entrega bounded `1M` |
| `DOC-010` | economics real | `PARTIAL 2026-08-30`: current-full native `120,801` contenidos y OCR `856` páginas pasan sobre output warm; adquisición física `10,000` conserva telemetría real. Dashboard acepta cold ausente como gap de medición, no como integridad verde falsa. DoD: state+output fríos, mismas entradas/checksums, CPU/RSS/bytes/latencia por stage, tarifas reales de compute/storage/request/egress/review y coste por `1,000`; unknown nunca se serializa como `0` |

### P0 — actores y candidatos

| ID | Entregable | DoD |
| --- | --- | --- |
| `ACT-001` | acceso oficial candidaturas | `PARTIAL`: siete proclamaciones BOE / once correcciones reproducibles y checksum-valid; selector exact-date/exact-ID fail-closed; defecto de número en noviembre 2019 y archive Interior aún bloqueados |
| `ACT-002` | ingest por elección | `PARTIAL`: dos elecciones BOE balancean base/correcciones/estado efectivo/lineage/Parquet; ampliar cohortes |
| `ACT-003` | observations/presence | `PARTIAL`: versiones y `is_present` preservan estado; falta segundo snapshot real para probar ausencia/supersession sin borrar historia |
| `ACT-004` | identity states | `PARTIAL`: `133,595` decisiones source-scoped, `55/55` mapeos de origen y prohibición de merge por nombre validados; reviewed/conflict/unresolved cross-source siguen sin gold set |
| `ACT-005` | gold set identidad | precision/recall por source/patrón |
| `ACT-006` | merge/split history | evidencia histórica reconstruible |
| `ACT-007` | `100k` real representativo | `PARTIAL`: grafo contiene `133,595` actores reales / `237,973` relaciones de `30` scopes usados; falta auditoría formal de representatividad nacional/autonómica/municipal/europea y gold set |
| `ACT-008` | `1M` real | `PARTIAL`: export graph suma `1,331,749` filas de tablas/versiones/evidencia, pero solo `133,595` actores; falta `1M` actor/candidate/mandate facts representativos, origin durable, restore, corrections y quality |

### P0 — votos y parlamento

| ID | Entregable | DoD |
| --- | --- | --- |
| `PAR-001` | coverage matrix | chamber/legislature/session/range |
| `PAR-002` | text-at-vote-time | versión exacta, no consolidado posterior |
| `PAR-003` | category semantics | yes/no/abstain/absence/no-vote separados |
| `PAR-004` | official total reconciliation | delta clasificado por evento |
| `PAR-005` | actor link quality | identity state y unresolved visibles |
| `PAR-006` | bounded shards | index/shard/hash, payload independiente del corpus |
| `PAR-007` | origin/restore | clean rebuild y old-link test |

### P0 — dinero público

| ID | Entregable | DoD |
| --- | --- | --- |
| `MON-001` | PLACSP history | catálogo sin gaps; versions/tombstones balancean |
| `MON-002` | BDNS full pagination | rows/source total/revisions balancean |
| `MON-003` | exact decimals | sin float drift; currency/tax semantics |
| `MON-004` | lifecycle separado | notice/award/change/invoice/payment/execution |
| `MON-005` | entity identity | public identifiers, aliases, conflicts, source provenance |
| `MON-006` | `1M` por lane | contratos y subvenciones pasan por separado |
| `MON-007` | execution joins | award nunca se presenta como pago |
| `MON-008` | restore/publication | manifests públicos y clean restore |

### P1 — responsabilidad, outcomes e integridad

| ID | Entregable | DoD |
| --- | --- | --- |
| `ACC-001` | rules/acts/appointments | originator/approver/publisher/effective/version |
| `ACC-002` | competence graph | delegación y current owner por fecha |
| `ACC-003` | issue codebook | ejemplos, exclusiones, versions |
| `ACC-004` | measure extraction | span, method, confidence, review |
| `ACC-005` | ledger `1M` | mix real, lineage, actor quality, restore |
| `CMP-001` | `LOCAL VALIDATED — PENDING PUBLICATION 2026-08-20`: comparison engine C1 | `5` assessments reales / `18` evidencias; `3` ambiguos, `1` insuficiente, `1` no comparable, `0` fuertes. Replay, validator independiente, FK/integridad y UI contract pasan. Cutoff de acciones `2026-02-12` stale; sin prueba física de millón ni promoción atómica del conjunto. Siguiente: publicar y auditar live `/comparisons/` + JSON exacto; `TODO 29` sigue abierto |
| `OUT-001` | indicator codebook | unit/geography/methodology/breaks/use |
| `OUT-002` | second snapshot | revisions/deletions verificadas |
| `OUT-003` | representative `1M` | outcomes Tier 1, origin, restore, correction |
| `OUT-004` | `DONE 2026-08-20`: contrato canónico + primera familia Eurostat | `86` series / `2.091` observaciones / `2.091` evidencias / `113` provisionales; release baseline inmutable, Decimal exacto, geografía/tiempo/metodología/uncertainty y no-causalidad; JSON live exacto. `OUT-001..003` siguen abiertos |
| `OUT-005` | `LOCAL VALIDATED — C1 PACKAGE/BUILD PASS; C2A+C2B PORTABLE PHYSICAL PASS; REMOTE PUBLICATION/ORIGIN OPEN 2026-08-29`: outcome context | C1: `1` candidato pendiente real / `20` pares / `25` observaciones / `264` participantes públicos / `7` evidencias; reviews, releases, memberships, links validados/públicos=`0`; semántica `2e04efb8...`, artifact set `22f43918...`. Status v3 `4.078` bytes / SHA `226dfdf9...`; paquete `5ac01878...`, manifest `9.496` bytes / SHA `2bfe3f2d...`, `17` assets y proyección determinista de `2.973` checks SHA `8e978632...`. Los `264` nombres permanecen exactos; eliminados/seudonimizados=`0`. Browser rehashes todos los assets y falla cerrado. C2A procesa físicamente `33.726` pares / `111` checks. C2B procesa `2.865.602` pares en el planner `3.587.743.744` bytes / SHA `04c82651...`, conserva identidad pública exacta (`119.116` member-votes / `490` nombres / `458` acciones) y entrega `1.205` pair + `8` identity Parquet / `251.522.252` bytes. Canonical/replay comparten raíces semantic `2afaf9ef...`, physical `f2d50fa5...`, portable `049f9718...` y bytes exactos; `22` identity + `23` package tests pasan. C2A/C2B son L0 internos, no publicables y sin claims. Abiertos: publicación/audit C1 live, XML original, actor provenance, origin remoto durable + restore/rollback C2, review humano y promoción |
| `INT-001` | review state machine | review/disagreement/adjudication/appeal/correction |
| `INT-002` | official historical calibration | labels con finding oficial citado |
| `INT-003` | counterevidence/right of reply | supersession pública end-to-end |
| `INT-004` | publication gate | modelo no puede publicar; dos fuentes y review humano |
| `INT-005` | generated candidate queue + decision-only review packets | candidate version ID inmutable, bounded evidence refs y manifest; la decisión append-only contiene solo reviewer/method/verdict/rationale/sign-off y nunca duplica el candidato completo ni sus `264+` participantes |
| `INT-006` | `PARTIAL — C2C CAPACITY PASS; REAL OPERATION OPEN 2026-08-29`: million-task review operations | capacity inmutable sobre `2.865.603` tareas / `2.865.604` slots, Python `3.12`, DB SHA `a97f9941...`, semantic `21acddf2...`, `330` checks y `12` tests. Cero trust roots/reviewers/auth/conflicts/assignments/claims/decisions/promotions/releases/publications. DoD pendiente: builder/export inmutable de snapshot operativo separado, identidades y autoridad reales, leases/heartbeat/reclaim, calibration, dual review, adjudication, conflicts, appeals, queue age, throughput y correction SLA medidos; identidad oficial pública permanece resoluble en evidencia |

### P1 — delivery y comunidad

| ID | Entregable | DoD |
| --- | --- | --- |
| `PUB-001` | bounded APIs | cursor estable; no million-row JSON |
| `PUB-002` | evidence cards | source/freshness/coverage/uncertainty/correction |
| `PUB-003` | `DONE 2026-08-19`: source catalog + obstruction tracker | ruta y feed v2 públicos; `27` incidentes / `14` fuentes; freshness/completeness/last run; `119/119` evidencias internas con bytes/SHA-256; identidad personal de dominio público retenida; audit live `44` rutas / `48` assets / `119` evidencias, `0` fallos. Siguiente: métricas históricas de respuesta/resolución dentro del dashboard de transparencia |
| `PUB-004` | adapter SDK | capture-to-validation en un comando |
| `PUB-005` | contributor issues | scope, fixture oficial, expected artifact, DoD |
| `PUB-006` | critical ownership | dos revisores; bus factor visible |
| `PUB-007` | external reproduction | maintainer externo valida release |
| `PUB-008` | `DONE 2026-08-19`: dashboard de transparencia + release flow | feed v1 actualizado con `10` métricas trazadas, `10` releases reales, freshness, health, obstruction, readiness y release durable; build `1,433/1,433`; audit live `44` rutas / `48` assets / `119` evidencias, `0` fallos. Siguiente: métricas históricas solo con observaciones reales comparables |
| `PUB-009` | `DONE 2026-08-19`: core ontology v1 | contrato humano + JSON máquina con `19` conceptos, `26` relaciones siempre evidence-backed, `49` tablas actuales mapeadas, IDs/tiempo/provenance/unknown/versionado, retención de identidad oficial pública y arquitectura para `10M` facts / `1M` documentos / `100M` sin cambio ontológico; `just core-ontology-check` y `8/8` tests verdes. Siguiente: `TODO 14`, plugin architecture v1 |
| `PUB-010` | `DONE 2026-08-19`: plugin architecture v1 | contrato humano + JSON Schema con `7` tipos, `14` hooks, `19` outputs ontológicos, `10` test hooks de datos reales, particiones bounded, seguridad por capabilities, at-least-once con efectos lógicos exactly-once, provenance de captura oficial y retención de identidad pública; `just plugin-architecture-check` y `8/8` tests verdes |
| `PUB-011` | `DONE 2026-08-19`: SDK mínimo + plugin de referencia oficial | loader/registry/contextos tipados y adapter de captura exacta; Congreso replays `2` veces una captura oficial hasheada de `2,073` bytes / `3` registros y converge en `3` source records, `3` mandates, `3` personas, `0` FKs rotas, URL oficial y logical hash estables; `just reference-plugin-check`, `10/10` tests y audit global de `25` fuentes / `277,715` bytes sin synthetic/mock verdes. Siguiente: `TODO 16`, snapshot firmado y reproducible |
| `PUB-012` | `DONE 2026-08-19`: provenance + snapshot firmado reproducible | release live inmutable `5d9ce557...`, manifest y artifact contract hasheados, attestation SSH Ed25519 con trust root externo, verificación live de `7` corpus / `5,414,326` filas / `8,597` data files / `500,714,815` bytes, metadata actual y políticas real-only/identidad pública; diff exacto anterior/actual `6` added / `2` changed / `0` removed / `8,617` unchanged; `just snapshot-reproducibility-check` fail-closed. `PUB-007` sigue abierto hasta segunda attestation de mantenedor externo. Siguiente: `TODO 17`, Evidence API/export contract estable |
| `PUB-018` | `DONE 2026-08-20`: indicadores Eurostat públicos | `/indicators/` + JSON exacto live; `86` series / `2.091` observaciones / `113` provisionales; hashes fuente/release/artefacto, replay de celdas y QA desktop/móvil pasan. No se atribuye causalidad, mérito ni culpa. Siguiente: `OUT-001..003` y `TODO 28` |
| `PUB-013` | `DONE 2026-08-19`: Evidence API v1 estable | pointer current + release inmutable `feb61b39...`; JSON Schema y contrato humano; `1,147` entidades, `1,105` evidence chains, `48` fuentes y `3,530` resultados reales en `26` páginas bounded; cursor seek opaco, hashes encadenados, provenance por objeto, gaps explícitos, deprecación `180` días / `2` releases e identidad pública `1,147/1,147`; `just evidence-api-v1-check` y `5/5` tests pasan; verificación live descarga `32` objetos / `11,452,986` bytes sin errores. Siguiente: `TODO 20/21`, spending/procurement real |
| `PUB-014` | `DONE 2026-08-19`: promesas oficiales BNG 2023 | schema aditivo directo a partido; PDF oficial fijado por SHA-256 `b8994dee...`, `396,842` bytes y `68` páginas; `266` claims / `266` evidence anchors / `91` promises / `323` topic links; live `/promises/` publica `20` con cita, página, hash, actor y topic; `6` fragmentos incompletos quedan `needs_context`; fulfillment queda `not_assessed`; replay idempotente, FK, tests real-only y live check de página/JSON/PDF oficial pasan. Siguiente: segundo manifiesto, revisión humana estratificada y luego `TODO 20/21` |
| `PUB-015` | `DONE 2026-08-19`: spending/procurement canónico PLACSP | spec v1 con `14` event kinds y `4` tablas aditivas; mapper sobre `330,577` registros / `262,558` awards / `3,190,620` documentos reales; sample `20` awards, `40` actors, `38` evidencias, exact Decimal `4,835,494.71 EUR`, identidad pública `10/5/5` legal/natural/unclassified y award != payment; release `7abe9ac6...` / JSON `b09990e1...` validan archive `146,382,691` bytes / SHA `bda70aa0...`, replay, FK e integridad; live `/spending/` y JSON HTTP `200`, tres estratos de identidad enlazan a PLACSP HTTP `200`. Siguiente: full materialization particionada, segunda observación y award -> contrato/pago/entrega solo con evidencia |
| `PUB-016` | `DONE 2026-08-19`: agreements/meetings/influence canónico | spec v1 + `11` tablas aditivas separan facts, actor roles, agenda, agreement states, topics y assertions; captura Moncloa real `21,234` bytes / SHA `ab08b7dc...` produce `11` sesiones/acuerdos, `37` parties, `20` topics derivados, `22` evidencias, `0` attendance claims y `0` influence assertions; release `6f75ec32...` / JSON `8d8ce219...`, replay, FK, integridad, real-only y browser pasan; live `/agreements/` + JSON exacto + `3` fuentes Moncloa HTTP `200`. Siguiente: agenda/lobby disclosure con personas públicas, segunda captura/history y agreement -> implementation |
| `PUB-017` | `DONE 2026-08-20`: geopolitics canónico | spec v1 + `8` tablas aditivas; release real-only `6683fd44...` / JSON `ea8c3eb1...` proyecta `2` procedimientos internacionales Moncloa en `2` acciones / `11` actores / `2` evidencias / `4` topics derivados / `2` links, con posiciones, observaciones posteriores, entrada en vigor, implementación e inferencias en `0`/not assessed; replay, FK, integridad y tests UI pasan; live `/geopolitics/`, JSON exacto y `2` fuentes Moncloa HTTP `200`; browser desktop/móvil y audit global `43/47/119` verdes. Siguiente: BOE para etapa jurídica posterior y `TODO 26/27` indicators |

## 5. Secuencia rolling de ocho semanas desde 2026-08-29

Semana 1 — cerrar publicación local -> live:

- ejecutar checks de actor graph, comparison engine y outcome context sobre sus inputs reales actuales;
- rerun `cloudflare-pages-build`; exigir paridad exacta entre artifacts fuente, `public/` y `out/`, real-only, higiene y budgets;
- publicar primero source/main y después `gh-pages`; verificar `/actor-graph/`, `/comparisons/`, `/policy-outcomes/`, assets exactos, hashes, browser desktop/móvil y audit global;
- no cambiar `pending publication` a `DONE` sin evidencia live.

Semana 2 — provenance y freshness antes de L2:

- recuperar bytes XML originales del voto o conservar el bloqueo explícito con locator/hash del registro normalizado;
- sustituir la provenance actor release/closure-only: fijar captura actor-source por checksum o declarar cada enlace como derived hasta resolverlo;
- hacer visibles por contrato la fecha contractual, action cutoff `2026-02-12`, indicator snapshot `2026-08-11`, upstream update/release y estado stale/current;
- bloquear L2 mientras actor origin/restore y el slice W4 de voto/texto no pasen sus gates requeridos.

Semanas 3-4 — congelar C2 aceptado y preparar plano humano real:

- congelar roots, manifests y receipts de C2A `33.726/111`, C2B planner `2.865.602/107`, package `1.213` Parquet y C2C capacity `2.865.603` tareas / `2.865.604` slots; mantener L0/capacity no publicables y sin claims humanos;
- mantener Python `3.12` + PyArrow `20.0.0`, exact inventory, copy-only replay, hard-link fail-closed y límites de batch/RSS como contrato; no volver a depender del SQLite planner único como formato de entrega;
- separar candidate queue de decisiones append-only keyed por immutable version ID; servir evidence packets bounded por referencia;
- implementar primero un builder de snapshot `operational_working` separado que acepte solo trust roots, identidades, autorizaciones, conflicts y assignments reales; exportarlo content-addressed antes de uso;
- operar después el primer lote humano real con reviewer identity, calibración, dos reviews independientes y adjudicación cuando discrepen.

Semanas 5-6 — origin durable y review operations:

- publicar los exactos artifacts C2A/C2B y C2C capacity aceptados en un origin remoto inmutable autorizado; verificar hashes, retention, versioning y coste;
- ejecutar clean restore y rollback aislados sin leer estado local; revalidar C2A `111/111`, C2B `107/107` + package completo, C2C `330/330`, roots y counts exactos;
- medir leases, heartbeat/reclaim, queue age, throughput, agreement, reversal, appeal y correction SLA;
- mantener candidate/reviewed/validated/published separados y conservar toda identidad oficial pública en evidencia.

Semanas 7-8 — scope representativo, review y promoción o cierre honesto:

- aprobar codebook/source mix representativo y segundos snapshots; usar la telemetría C2B real para fijar budgets de producción, no para declarar representatividad;
- publicar únicamente memberships L2 con review real y todos los prerequisites; resto permanece candidate/no_signal/blocked explícito;
- verificar origin, clean restore, rollback, release/pointer atómicos, shards públicos bounded y drill-down a evidencia;
- publicar scorecard y reordenar por gap medido. Si cualquier gate falla, registrar evidencia y mantener C4/C5/L2 abiertos.

## 6. Gates por cohorte real

Cada expansión `100 -> 1k -> 10k -> 100k -> 1M` exige:

1. preflight de disco/origin/request budget;
2. source contract actual;
3. queue vacía o delta explicado;
4. zero silent loss;
5. checksums y bytes balanceados;
6. parser success y quality sample;
7. DB integrity/FK;
8. semantic manifest y full validation;
9. publication-hygiene gate plus exact official-public-field retention;
10. cost/SLO report;
11. tracker update;
12. aprobación del siguiente salto basada en evidencia.

## 7. Comandos de control

```bash
# Readiness real
just etl-scale-readiness

# Capacidad de storage desde preflights reales, sin paths ni secretos
just etl-storage-health

# Calidad e integridad base
just etl-test
just etl-schema-compat-check
just privacy-check-public-artifacts
just etl-tracker-gate

# Documentos
just etl-scale-inventory-documents
just etl-scale-export-xlsx-lineage
just etl-scale-audit-document-provenance
just etl-scale-extract-document-text-corpus
just etl-scale-validate-document-text-corpus
just etl-scale-document-text-locators
just etl-scale-document-language-encryption-profile
just etl-scale-replicate-document-origin-local
just etl-scale-restore-document-origin-local
just etl-scale-pack-document-origin
just etl-scale-validate-document-origin-packs
just etl-scale-document-origin-hf-dry-run
just etl-scale-document-origin-hf-preflight
just document-factory-economics-export
just parl-document-pipeline-scale

# Votos
just etl-scale-audit-member-votes
just etl-scale-audit-vote-source-urls
just etl-scale-audit-vote-db
just etl-scale-export-vote-db-shards
just etl-scale-validate-vote-db-shards

# Eurostat real
just etl-scale-eurostat-indicators-report
just etl-scale-eurostat-indicators-export
just etl-scale-eurostat-indicators-validate
just etl-scale-eurostat-indicators-replay
just etl-scale-eurostat-indicators-replay-validate

# PLACSP real
just etl-scale-placsp-history-discover
just etl-scale-placsp-history-enqueue
just etl-scale-placsp-history-archives-work
just etl-scale-placsp-history-members-work
just etl-scale-placsp-report
just etl-scale-placsp-export
just etl-scale-placsp-validate
just etl-scale-placsp-replay
just etl-scale-placsp-replay-validate

# BDNS real
just etl-scale-bdns-bulk-enqueue-daily
just etl-scale-bdns-bulk-work
just etl-scale-bdns-bulk-report
just etl-scale-bdns-bulk-version-lineage

# Candidaturas oficiales
just etl-scale-boe-election-candidates
just etl-scale-export-semantic-candidate-occurrences
just etl-scale-validate-semantic-candidate-occurrences
just etl-scale-replay-semantic-candidate-occurrences
just etl-infoelectoral-candidates-report

# Actor graph real
just actor-graph-check

# Comparación promesa/acción real
just comparison-engine-check

# Outcome context real C0/L1 + planner físico C2A/C2B
just outcome-context-check
just outcome-context-pair-plan-check
just outcome-context-pair-plan-c2b-check

# C2B portable exacto: identidad pública, paquete y replay
just outcome-pair-identity-check
just outcome-pair-discovery-export
just outcome-pair-discovery-validate
just outcome-pair-discovery-replay
just outcome-pair-discovery-check

# C2C: capacidad inmutable; no equivale a review humano
just outcome-review-control-c2c-materialize
just outcome-review-control-c2c-validate
just outcome-review-control-c2c-check

# Build local y paridad del output
just cloudflare-pages-build
just comparison-engine-built-check
just outcome-context-built-check

# Publicación y verificación live
just site-publish
just actor-graph-live-verify
just comparison-engine-live-verify
node scripts/audit_public_routes.js --base-url https://votaconlachola.org
```

El audit global contract-valida status/manifest y rehashes todos los assets de
evidencia antes de aceptarlos. Después de publicar, verificar además el runtime
gate real de `/policy-outcomes/` en browser desktop y móvil: facts solo en estado
verified; cualquier asset ausente, alterado, redirigido o inseguro debe mostrar
únicamente el bloqueo genérico.

## 8. Cierre de sprint

Obligatorio:

- al menos un delta visible bajo control del repo;
- `>=70%` capacidad sobre trabajo controlable;
- máximo un probe estricto por source bloqueada sin nueva palanca;
- evidencia repo-relative y sin secretos/path local;
- tracker con estado honesto;
- `just etl-scale-readiness` y gates relevantes;
- lista de riesgos residuales;
- siguiente objetivo elegido por impacto público y gap medido.

No se declara listo porque el código soporte un volumen teórico. Solo cuenta el corpus oficial real materializado, validado, publicado, restaurable y corregible.
