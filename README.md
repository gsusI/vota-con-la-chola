# Vota Con La Chola

![Vota Con La Chola - portada](docs/screenshots/cover-graph-congreso-diputados-depth-3-active-lens-all.png)

[![ETL Tracker Gate](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml/badge.svg)](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml)
![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Estado del proyecto](https://img.shields.io/badge/status-mvp-orange.svg)
[![HF Dataset](https://img.shields.io/badge/HF-dataset-blue)](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data)

Herramienta abierta y orientada a la evidencia para ayudar a decidir tu voto: cruza tus prioridades con lo que actores políticos y partidos **dicen** y **hacen**, con explicaciones trazables y fuentes auditables.

Este repo es intencionalmente **ultraligero**: SQLite reproducible para control/snapshots, objetos content-addressed para documentos, artefactos analíticos/publicación acotados y trazabilidad por defecto.

## Sobre el repo (para colaboradores)

**Resumen para GitHub / About:**

- Infraestructura cívica de evidencia pública para transparencia política reproducible.
- Enfoque operativo en la trazabilidad: cada afirmación pública puede reconducirse a consulta y fuente.
- Público objetivo actual: ciudadanía de decisión rápida, periodistas de verificación y analistas ciudadanos.
- Estado: MVP funcional con prioridades claras de mejora continua y documentación de calidad.

## Visión y misión

Visión:
- Que cualquier persona en España pueda decidir su voto con la misma exigencia con la que audita una cuenta pública: comparando **lo que se promete, lo que se ejecuta y lo que impacta**, con evidencia verificable en su nivel territorial (Estado, CCAA, municipal, UE).

Misión:
- Construir y operar una infraestructura cívica abierta, reproducible y auditable que transforme datos públicos fragmentados en explicaciones claras y trazables para:
  1. medir alineamiento ciudadano-político,
  2. contrastar “dicen vs hacen”,
  3. estimar impacto cuando sea metodológicamente defendible.

## Estado actual de gobierno del repositorio

- Política de gobernanza general: [`GOVERNANCE.md`](GOVERNANCE.md)
- Proceso de decisiones: [`docs/governance/decision-log-process.md`](docs/governance/decision-log-process.md)
- Sobre el proyecto para GitHub/About, tópicos sugeridos y checklist de roles: [`docs/ops/github-about.md`](docs/ops/github-about.md)

## Leer primero

- Índice de docs: `docs/README.md`
- KB de agentes / aprendizajes duraderos: `project_kb/README.md`
- Roadmap canónico del futuro: `ROADMAP.md`
- Roadmap macro de modelo/arquitectura: `docs/roadmap.md`
- Roadmap técnico derivado (ejecución): `docs/roadmap-tecnico.md`
- Backlog operativo (conectores + DoD): `docs/etl/e2e-scrape-load-tracker.md`
- Índice único de TODO: `docs/todo/README.md`
- Cómo correr ETL/UI: `docs/etl/README.md`
- Sitio público canónico (Cloudflare Pages): https://votaconlachola.org/
- Hugging Face (dataset público): https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data

## Qué hay hoy (MVP)

- ETL de representantes y mandatos a un único SQLite.
- Ingesta parlamentaria (Congreso/Senado) para votaciones e iniciativas (con pipeline de calidad en curso).
- Ingesta inicial de Infoelectoral (procesos/descargas/resultados).
- Publicación de snapshots canónicos en `etl/data/published/`.
- App pública estática para Cloudflare Pages en `ui/gh-pages-next/`; salida de build en `ui/gh-pages-next/out/`.
- Espejo público de snapshots en Hugging Face Datasets (`just etl-publish-hf`): https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data
- Origen analítico versionado en Hugging Face (`just etl-scale-origin-hf-publish`): `scale/snapshots/<snapshot-date>/<full-manifest-sha256>/` empaqueta solo archivos declarados por manifests validados y mueve `scale/latest.json` al final. El bundle incluye un hash estable del contrato de datos/provenance, independiente del estado mutable de publicación. La release firmada actual `5d9ce557...` contiene `7` corpora / `5,414,326` filas / `8,597` data files; manifest, contrato, attestation Ed25519, registry/readiness y política real-only verifican sin warnings.
- Restore reproducible (`just etl-scale-origin-hf-restore-validate`): por defecto sigue `scale/latest.json`, exige destino vacío y firma válida, y valida solo con controles incluidos en el bundle más el trust root externo; `HF_SCALE_RESTORE_SNAPSHOT_PATH=scale/snapshots/<date>/<full-sha256>` fija una release inmutable sin depender del pointer mutable. Los seis corpora históricos ya pasaban restore limpio (`5,403,506` filas / `8,595` data files). El drill anónimo GET-only de `candidate_occurrences` del `2026-08-24` añade la séptima lane: `10,820` filas / `2` Parquet, `14/14` ficheros exactos incluyendo controles, cero reuse, credenciales, symlinks, undeclared files o mutación remota. Esto cierra recovery de todos los corpora analíticos publicados; raw documents y outcome C2 siguen separados y abiertos.
- Plan de rollback read-only (`just etl-scale-origin-hf-prepare-rollback`): vuelve a leer el pointer y ambos manifests, enlaza por SHA-256 el restore y full validation reales, exige parity de contratos/corpora y emite compare-and-swap para `5872efaf... -> 623b4a5a...`. El plan pasa con delta `0` filas / `0` ficheros / `0` bytes, conserva ambas releases, marca RPO formal como no definido y deja `authorized=false`, `mutation_performed=false`. No escribe el pointer.
- Rebuild SQLite desde origin restaurado (`just etl-scale-origin-sqlite-rebuild`): importa Parquet por batches, exige checksums/contrato real-only, conserva campos públicos sin transformación, valida hash lógico e integridad y publica el DB solo mediante rename atómico. Dos rebuilds del corpus actor produjeron el mismo SHA-256 SQLite `61cfdf8e...` para `88,031` filas.
- CAS de objetos documentales (`just etl-object-store-replicate` / `etl-object-store-restore-drill`): upload y restore usan batches con workers acotados, claves SHA-256, writes atómicos y manifest determinista. La prueba local real replica/deduplica `6,792` objetos / `133,219,457` bytes con `16` workers y restaura el manifest completo. Esto prueba el contrato y throughput local; el origen S3-compatible remoto sigue pendiente.
- Cola de gaps documentales (`just etl-scale-document-provenance-gap-queue`): valida el hash del audit y recorre `111,408` capturas oficiales elegibles. Checksum + URL pública cubren `111,357` (`99.9542%`) y la cola conserva los mismos `51` gaps históricos / `8,315,544` bytes; los `89,001` documentos y `1,034` resúmenes BOE están linked. Ninguna tarea contiene URL inferida. Las recovery lanes mantienen separadas las relaciones por href capturado, SQLite archivado, identificador oficial, path oficial byte-idéntico, sidecar, manifest y Wayback. Wayback conserva `3` targets / `5` nonmatches / `7` variantes inconclusas en checkpoint de `43` filas y no repite red sin nueva palanca. El discovery bruto es `111,422`: cinco fixtures/samples no cuentan y nueve denegaciones/errores quedan como evidencia de obstrucción.
- Procesamiento documental completo actual (`just etl-scale-process-document-corpus` con state v5): cola SQLite inmutable por inputs, leases y CAS deduplica y extrae `111,408/111,408` instancias / `109,558/109,558` contenidos en `108,139` CAS gzip, con `1,999,902,681` caracteres públicos exactos y `0` retry/dead/failure/truncation. Un validator independiente rehasha cada raw y CAS. OCR aditivo procesa `856/856` páginas de `58` PDFs, produce texto en `849`, conserva `7` no-text, `89,632` chars, `17` gains y `131` CAS verificados. El packet humano conserva `40` filas reales, rechaza decisiones inventadas y sigue `0/40`.
- Readiness sin deriva: `scripts/report_scale_readiness.py` ya no acepta el gap documental como texto manual sin verificar. Falla si registry, inventario, audit v12, cola, report/checkpoint/manifest Wayback, extracción nativa, OCR, validaciones independientes o CSV humano divergen; exige balance exacto de targets, paths, queries, captures, checksums raw/CAS, cero truncation, identidad pública intacta y labels humanos no inventados.
- Salud de storage publicable (`just etl-storage-health`): agrega solo preflights reales, valida la aritmética de reserva/headroom, incluye hashes de evidencia y omite roots, credenciales, sesiones y paths de workstation. `--enforce-ready` queda disponible para gates que deban fallar mientras exista cualquier lane bloqueada.
- UI local para explorar el esquema y la evidencia: `just graph-ui` (ver `docs/etl/README.md`).

Estado de escala (`2026-08-29`): solo datos capturados de fuentes oficiales cuentan. `just etl-scale-readiness` valida todos los ficheros, bytes, SHA-256, filas, `source_id` y hosts de siete corpora actuales:

- votos nominales: `1,809,222` filas / `8,373` shards; URL pública y source record `100%`; las `102,172` filas HTTP / `1,166` URLs están clasificadas, con captura checksum para `33,683` filas / `484` URLs y `68,489` filas / `682` URLs pendientes de replacement inmutable;
- Eurostat: `1,755,809` observaciones / `37` Parquet; full validation y replay `26/26`;
- PLACSP: `263,302` facts / `50` Parquet; `128,849/128,849` nombres e identificadores de contraparte publicados por la fuente se conservan exactamente; full validation y replay `50/50`;
- BDNS: `1,360,382` facts / `14` Parquet; nombres `1,360,382/1,360,382` e identificadores source `163,270/163,270` retenidos exactamente; full validation y replay `1/1` partición mediante `14/14` hardlinks;
- accountability ledger: `126,760` facts / `13` Parquet; full validation y replay `13/13`;
- actores: `88,031` mandatos / `108` Parquet; full validation y replay `108/108`;
- candidatos: `42,056` ocurrencias BOE base exactas / `4,901` candidaturas / `10,820` ocurrencias efectivas / `2` Parquet; identidad y texto oficial se conservan en cada fila base; `88` filas efectivas están respaldadas por corrección, resultados no inferidos y replay `2/2`. Ocho documentos de corrección / `776` párrafos y sus `31,241` candidatos base siguen pendientes y no entran en estado efectivo. `just etl-scale-boe-election-candidate-correction-review-queue` crea `776` tareas dual-review con decisiones vacías y un contexto JSONL deduplicado de `3,713` candidaturas / `31,241` candidatos públicos; readiness rehasha y reconcilia ambos.

Hay `3` lanes reales por encima de un millón, `7` corpora registrados y `0` lanes promocionadas. La release HF v2 content-addressed y firmada `5d9ce557...` y el contrato estable `d7de5544...6565` verifican los siete corpora autorizados: `5,414,326` filas, `8,597` ficheros de datos y `500,714,815` bytes sin transformar identidades públicas. Los siete corpora analíticos pasan clean-room restore. BOE conserva `42,056` ocurrencias base / `4,901` candidaturas de siete proclamaciones; `10,820` ocurrencias efectivas proceden del subconjunto revisado y `31,241` candidatos base de correcciones pendientes quedan fuera del efectivo. Ninguna fila base cambia, ningún campo personal oficial se elimina y no se fuerza identidad cross-source. El corpus documental actual contiene `122,607` instancias / `120,757` contenidos / `5,524,892,735` bytes; extracción v7 produce `2,211,254,429` caracteres públicos y locators exactos para `30,634` páginas PDF más `332,530` spans markup. OCR valida `856/856` páginas. La captura física BOE sigue `100,051/100,867`, con `1` dead y `815` unfinished; por eso el control actual publica `status=not_ready`, `foundation.ready=false` y `failure.reason=BOE document corpus checks failed`. Outcome C2 y el origin documental remoto durable siguen abiertos. Ver `etl/data/published/scale-readiness-latest.json`, `docs/etl/real-corpus-registry.json` y `ROADMAP.md`.

Verificación local de cierre: `1,471` tests Python pasan (`12` skips contextuales), `234/234` tests Node pasan y el último build estático genera `1,435` páginas. Las `130/130` bases staging pasan sin incidencias. Real-only escanea `153,946` ficheros con cero hallazgos y publication hygiene escanea `17,202` artefactos sin secretos, sesiones ni trazas de workstation. Estos gates conservan intactos nombres, identificadores y demás datos personales publicados oficialmente. No se ha ejecutado publicación remota de este cierre.

## Fuente de verdad (código)

- Esquema SQLite: `etl/load/sqlite_schema.sql`
- ETL (personas/mandatos): `scripts/ingestar_politicos_es.py`
- ETL (parlamentario): `scripts/ingestar_parlamentario_es.py`
- Servidor UI/API local: `scripts/graph_ui_server.py`
- Explorer UI: `ui/graph/explorer.html`

Antes de tocar ETL/esquema/UI: `AGENTS.md` (reglas de rendimiento, idempotencia y compatibilidad con Explorer).

## Inicio rápido (Docker + just)

```bash
just dev
```

Ojo: este es el flujo recomendado para entrar rápido. Si quieres detalles completos del path de fixture y del smoke de arranque, consulta [`docs/dev/quickstart.md`](docs/dev/quickstart.md).

Comandos completos sin fixture:

```bash
just etl-build
just etl-init
just etl-samples
just graph-ui
```

Si quieres una corrida más completa (y reproducible) en local:

```bash
just etl-e2e
just parl-quality-pipeline
just etl-publish-votaciones
```

Gates y pipelines de escala real:

```bash
just etl-scale-readiness
just etl-scale-process-document-corpus
just etl-scale-prepare-document-page-ocr-review
just etl-scale-validate-document-page-ocr-review
just etl-scale-origin-hf-dry-run
just etl-scale-origin-hf-verify
just etl-scale-origin-hf-restore-bdns
just etl-scale-audit-vote-db
just parl-refresh-senado-local-cache
just etl-scale-export-vote-db-shards
just etl-scale-validate-vote-db-shards
just etl-scale-export-semantic-member-votes
just etl-scale-validate-semantic-member-votes
just etl-scale-export-semantic-accountability-ledger
just etl-scale-validate-semantic-accountability-ledger
just etl-scale-export-semantic-actor-mandates
just etl-scale-validate-semantic-actor-mandates
just etl-scale-export-semantic-candidate-occurrences
just etl-scale-validate-semantic-candidate-occurrences
just etl-scale-replay-semantic-candidate-occurrences
just etl-scale-export-semantic-public-money
just etl-scale-validate-semantic-public-money
just etl-scale-export-semantic-indicators
just etl-scale-validate-semantic-indicators
just etl-scale-bdns-bulk-enqueue
just etl-scale-bdns-bulk-work
just etl-scale-bdns-bulk-report
just etl-scale-eurostat-indicators-enqueue
just etl-scale-eurostat-indicators-work
just etl-scale-eurostat-indicators-backfill
just etl-scale-eurostat-indicators-report
just etl-scale-eurostat-indicators-export
just etl-scale-eurostat-indicators-validate
just etl-scale-eurostat-indicators-replay
just etl-scale-eurostat-indicators-replay-validate
just etl-scale-placsp-archives-enqueue
just etl-scale-placsp-archives-work
just etl-scale-placsp-members-work
just etl-scale-placsp-report
just etl-scale-placsp-export
just etl-scale-placsp-validate
just etl-scale-placsp-replay
just etl-scale-placsp-replay-validate
just etl-scale-placsp-documents-enqueue
just etl-scale-placsp-documents-work
just etl-scale-placsp-integrity-review
just etl-scale-gate
just outcome-pair-identity-check
just outcome-pair-discovery-check
just outcome-review-control-c2c-check
```

El worker Eurostat renueva su lease durante cada chunk descargado y cada commit batch; aborta si pierde ownership. Cada query del registry declara `maximum_bytes` y `maximum_cube_cells`; payloads legacy de queue reciben un techo conservador. `EUROSTAT_INDICATOR_CA_BUNDLE` solo es necesario si el CA store del runtime está desactualizado: mantener esa ruta fuera del repo. No usar TLS inseguro en la lane reproducible.

PLACSP usa dos queues para archivos ZIP y miembros Atom, y una tercera queue independiente para documentos. El parser inspecciona ZIP en streaming y falla ante límites de path, tamaño, ratio, records o documentos. `PLACSP_BULK_ARCHIVE_ARGS` permite ampliar meses/años sin cambiar el loader. No drenar la queue de `998,392` documentos con los defaults de muestra: definir primero presupuesto por host, ventana, concurrencia, origin remoto, coste y cohortes crecientes. Los imports son notices/awards publicados; no son pagos. Las señales de integridad quedan internas y requieren revisión humana.

Ningún resultado generado localmente sustituye las promociones reales por lane (`100k` documentos estratificados; `1M` actores/votos/ledger/dinero/indicadores). Los gates están desglosados en `docs/roadmap-tecnico.md` y su estado vive en el tracker.

## Notas (KISS)

- `ROADMAP.md` es la única fuente de verdad para el futuro y la secuencia del proyecto.
- `docs/roadmap.md` y `docs/roadmap-tecnico.md` son docs de soporte; no deben abrir scope nuevo por su cuenta.
- `docs/etl/e2e-scrape-load-tracker.md` es la única lista operativa de TODO.
- `intro.md` está ignorado por git (nota local); evita convertirlo en otro roadmap.
- No se versionan bases ni raws grandes: usa `etl/data/raw/samples/` y artefactos publicados pequeños.

## Contribución y gobernanza

- Contribuir: `CONTRIBUTING.md`
- Gobernanza: `GOVERNANCE.md`
- Código de conducta: `CODE_OF_CONDUCT.md`
- Seguridad y reporte responsable: `SECURITY.md`
- Citación: `CITATION.cff`
- Política para señales de integridad: `docs/method/integrity-signal-policy.md`
- Retos de fuentes: `docs/community/contributor-challenges-v1.md`
- Guía de integración: `docs/community/partner-integration-guide.md`
- Steward map: `docs/community/steward-map.md`
- Plantillas de issue: `.github/ISSUE_TEMPLATE/`
- Plantilla de PR: `.github/PULL_REQUEST_TEMPLATE.md`
- Responsables de código: `.github/CODEOWNERS`

## Licencia

- Código y documentación técnica: licencia MIT (`LICENSE`).
- Política de derechos de datos y reutilización: [`docs/legal/data-rights.md`](docs/legal/data-rights.md)
- Snapshots públicos (HF): `license: other` con condiciones mixtas por `source_id` documentadas en `sources/<source_id>.json`.
