# Roadmap técnico

Actualizado: `2026-08-12`.

Autoridad:

- dirección, secuencia y definición global de éxito: `ROADMAP.md`;
- estrategia del producto: `docs/roadmap.md`;
- estado operativo por fuente: `docs/etl/e2e-scrape-load-tracker.md`;
- registro verificable de corpora reales: `docs/etl/real-corpus-registry.json`.

Este documento traduce `ROADMAP.md` a trabajo técnico cercano. No crea scope nuevo.

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
- estado de privacidad;
- límites, cobertura y siguiente gate.

Las muestras usadas en tests deben ser capturas oficiales con provenance. Datos inventados, endpoints locales y orígenes placeholder no cuentan como cobertura, capacidad ni readiness.

Gate canónico:

```bash
just etl-scale-readiness
```

## 2. Estado actual verificable

| Lane | Filas reales | Artefacto actual | Estado |
| --- | ---: | --- | --- |
| votos nominales | `1,809,222` | `8,373` shards gzip, `170,990,067` bytes | validado; no promocionado |
| indicadores Eurostat | `1,755,809` | `37` Parquet, `253,373,860` bytes | validado; replay `26/26`; no representativo |
| PLACSP | `263,302` | `50` Parquet, `20,803,781` bytes | v5 validado; identidad source `128,849/128,849`; replay `50/50`; historia incompleta |
| BDNS | `100,000` | `1` Parquet, `3,464,007` bytes | v5 validado; nombres `100,000/100,000`, identificadores `39,539/39,539`; replay `1/1`; solo 100 páginas |
| accountability ledger | `126,760` | `13` Parquet, `1,271,649` bytes | real-only validado; replay `13/13`; mix parlamentario |
| actores/mandatos | `88,031` | `108` Parquet, `9,236,064` bytes | validado; replay `108/108`; bajo `100k` |

Defectos visibles:

- votos: URL pública/source record `100%`; `102,172` filas con URL oficial HTTP;
- candidatos: `8,926` resultados históricos electos, pero `0` filas nominales aceptadas del archivo de candidaturas por bloqueo de origen;
- BDNS: el root actual valida `100,000` filas oficiales; el checkpoint anterior de `146,000` carece de root v5 vigente y no sustituye esta evidencia;
- ledger: `126,760` facts reales recuperados; `10` facts derivados de fixtures fueron purgados; `26` source IDs legacy se infieren explícitamente desde URL BOE oficial; faltan mix representativo, `1M`, origin y restore;
- documentos: `21,398` instancias / `19,538` hashes reconciliados; faltan provenance de origen por fichero, muestra de calidad suficiente y escala;
- lanes promocionadas: `0`.

El reporte `etl/data/published/scale-readiness-latest.json` debe decir `real_foundation_ready_scale_incomplete` hasta cerrar representatividad, origin público, clean restore y correcciones.

## 3. Sprint inmediato — recuperación de verdad

### RT-001 — Mantener el registry real-only

Implementado:

- registry explícito por lane;
- allowlist de `source_id` y host oficial;
- hash de registry, manifest y validation;
- verificación de cada fichero declarado;
- conteo real desde gzip/Parquet;
- lectura de `source_id` y `source_url` de todas las filas;
- validación de replay por hardlink para Eurostat, PLACSP, ledger y actores;
- promotion separada del row gate.

DoD:

- `python3 -m unittest tests.test_report_scale_readiness` pasa;
- `just etl-scale-readiness` pasa;
- ningún artifact ausente cuenta;
- ningún endpoint no oficial cuenta;
- cualquier fila sin URL/lineage aparece como gap.

### RT-002 — BDNS semántico v5 (`S1` cerrado; `R2` abierto)

Entrada ejecutada:

- DB `etl/data/staging/bdns-concessions-real-s1-20260812.db`;
- CAS `etl/data/object-origin/bdns-concessions-real-s1-20260812`;
- `100` páginas oficiales nuevas de `1,000` filas.

Resultado:

1. queue `100 succeeded / 0 unfinished / 0 dead / 0 retries`;
2. `100,000` records, source IDs, record URLs y version sightings distintos;
3. `80,509,937` raw bytes en `100` objetos checksum-linked;
4. SQLite `quick_check=ok`, FK `0`;
5. `public_money_facts_v5`: `100,000` rows, `1` Parquet, `3,464,007` bytes;
6. nombres oficiales `100,000/100,000` e identificadores source `39,539/39,539` retenidos exactamente;
7. validator full-row verde, `0` private tokens, replay `1/1` por hardlink;
8. corpus registrado, pero `promotion_gate_passed=false`.

Comandos base:

```bash
just etl-scale-bdns-bulk-report
just etl-scale-bdns-bulk-version-lineage
just etl-scale-export-semantic-public-money
just etl-scale-validate-semantic-public-money
```

DoD `S1`: `DONE 2026-08-12`.

- source/page/version/amount/public-field totals exactos;
- manifest, validation y replay actuales;
- registry/readiness/tracker actualizados;
- lane global sigue `PARTIAL` hasta `1M`, segundo snapshot, historia representativa, origin y restore.

Siguiente salto:

1. preflight de disco, origin y request budget para `1,000` páginas;
2. nueva cohorte durable sin reutilizar el checkpoint v3 no conforme;
3. mismo pacing/circuit; detener ante error-rate o latencia fuera de presupuesto;
4. exportar v5 solo después de reconciliar `1,000/1,000` páginas y `1M` filas reales.

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

1. inventariar raw y derived reales;
2. reconciliar file instances, content hashes, fetch queue, text queue y DB;
3. clasificar faltantes, duplicados, corruptos, cifrados y unsupported;
4. persistir MIME, bytes, páginas, idioma y densidad;
5. medir cobertura de texto y OCR por source/format;
6. seleccionar cohorte estratificada de `100k`;
7. calcular request/storage/OCR budget antes de fetch.

Comandos base:

```bash
just etl-scale-inventory-documents
just parl-enqueue-document-fetch-work
just parl-run-document-fetch-work
just parl-enqueue-text-extraction-work
just parl-run-text-extraction-work
```

DoD:

- balance exacto por stage;
- cero parcial huérfano;
- cada failure terminal con razón/replay;
- muestra de calidad revisada por humanos;
- coste y SLO medidos antes de `1M`.

### RT-005 — Cerrar provenance de votos

Pasos:

1. `DONE`: aislar el único evento responsable de las `350` URLs nulas;
2. `DONE`: verificar el endpoint oficial Congreso con browser-equivalent request;
3. `DONE`: registrar URL, hash oficial, hash capturado, diferencia semántica y event ID estable en sidecar;
4. inventariar las filas con URL HTTP por cámara/legislatura;
5. intentar equivalentes HTTPS sin cambiar identidad semántica;
6. `DONE`: reexportar `8,373` shards y validar `1,809,222/1,809,222` URLs/source records;
7. mantener incompatibilidades como gaps públicos.

DoD:

- `100%` source record;
- `100%` public URL o replacement oficial inmutable;
- HTTPS o excepción content-addressed explícita;
- official totals reconciliados o discrepancia clasificada por evento.

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
| `DOC-001` | inventory completo | source/MIME/bytes/pages/language/density o unknown |
| `DOC-002` | fetch streaming | límite duro, SHA, atomic commit, cero parciales |
| `DOC-003` | digital extraction | texto/página/método/version/checksum |
| `DOC-004` | OCR routing | solo páginas pobres; razón persistida |
| `DOC-005` | OCR cache | input+engine+version; unchanged = cero OCR nuevo |
| `DOC-006` | quarantine | bombs, corruptos, password y unsupported separados |
| `DOC-007` | quality gold set | doble review y métricas por estrato |
| `DOC-008` | `100k` real | success/quality/time/cost publicados |
| `DOC-009` | `1M` real | origin, restore, SLO y bounded public delivery |

### P0 — actores y candidatos

| ID | Entregable | DoD |
| --- | --- | --- |
| `ACT-001` | acceso oficial candidaturas | un archive real, checksum y contrato reproducible |
| `ACT-002` | ingest por elección | archive/member/party/candidate totals balancean |
| `ACT-003` | observations/presence | removals no borran historia |
| `ACT-004` | identity states | source exact/deterministic/reviewed/conflict/unresolved |
| `ACT-005` | gold set identidad | precision/recall por source/patrón |
| `ACT-006` | merge/split history | evidencia histórica reconstruible |
| `ACT-007` | `100k` real representativo | mix nacional/autonómico/municipal/europeo |
| `ACT-008` | `1M` real | origin, restore, correction y quality |

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
| `OUT-001` | indicator codebook | unit/geography/methodology/breaks/use |
| `OUT-002` | second snapshot | revisions/deletions verificadas |
| `OUT-003` | representative `1M` | outcomes Tier 1, origin, restore, correction |
| `INT-001` | review state machine | review/disagreement/adjudication/appeal/correction |
| `INT-002` | official historical calibration | labels con finding oficial citado |
| `INT-003` | counterevidence/right of reply | supersession pública end-to-end |
| `INT-004` | publication gate | modelo no puede publicar; dos fuentes y review humano |

### P1 — delivery y comunidad

| ID | Entregable | DoD |
| --- | --- | --- |
| `PUB-001` | bounded APIs | cursor estable; no million-row JSON |
| `PUB-002` | evidence cards | source/freshness/coverage/uncertainty/correction |
| `PUB-003` | source catalog | status y obstruction por fuente |
| `PUB-004` | adapter SDK | capture-to-validation en un comando |
| `PUB-005` | contributor issues | scope, fixture oficial, expected artifact, DoD |
| `PUB-006` | critical ownership | dos revisores; bus factor visible |
| `PUB-007` | external reproduction | maintainer externo valida release |

## 5. Orden de ejecución de ocho semanas

Semana 1:

- cerrar `RT-001`;
- ejecutar `RT-002` preflight;
- identificar DB/root exactos de `RT-003`;
- ejecutar inventario live `RT-004`;
- aislar eventos de `RT-005`.

Semana 2:

- materializar y validar BDNS;
- materializar y validar ledger;
- actualizar registry/tracker;
- cerrar defectos de URL de votos posibles sin nueva palanca externa.

Semanas 3-4:

- `STO-001..005`;
- replicar una lane `>=1M`;
- ejecutar restore sample y full lane;
- publicar release manifest y rollback contract.

Semanas 5-6:

- `DOC-001..007`;
- fijar strata y budget de `100k`;
- ejecutar cohortes `100 -> 1k -> 10k` con gate entre cohortes;
- detener si error rate, upstream blocking, storage o calidad salen de presupuesto.

Semanas 7-8:

- completar `DOC-008` si gates previos pasan;
- avanzar `ACT-001` solo con palanca oficial nueva;
- continuar PLACSP/BDNS por cohortes oficiales si storage y upstream están verdes;
- publicar scorecard de coverage/SLO/cost y reordenar según gaps reales.

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

# Calidad e integridad base
just etl-test
just etl-schema-compat-check
just privacy-check-public-artifacts
just etl-tracker-gate

# Documentos
just etl-scale-inventory-documents
just parl-document-pipeline-scale

# Votos
just etl-scale-audit-member-votes
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
just etl-scale-bdns-bulk-report
just etl-scale-bdns-bulk-version-lineage

# Candidaturas oficiales
just etl-infoelectoral-candidates-report
```

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
