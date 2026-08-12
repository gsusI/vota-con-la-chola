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
- UI local para explorar el esquema y la evidencia: `just graph-ui` (ver `docs/etl/README.md`).

Estado de escala (`2026-08-12`): solo datos capturados de fuentes oficiales cuentan. `just etl-scale-readiness` valida todos los ficheros, bytes, SHA-256, filas, `source_id` y hosts de seis corpora actuales:

- votos nominales: `1,809,222` filas / `8,373` shards; URL pública y source record `100%`; `102,172` apuntan a un endpoint oficial HTTP;
- Eurostat: `1,755,809` observaciones / `37` Parquet; full validation y replay `26/26`;
- PLACSP: `263,302` facts / `50` Parquet; `128,849/128,849` nombres e identificadores de contraparte publicados por la fuente se conservan exactamente; full validation y replay `50/50`;
- BDNS: `100,000` facts / `1` Parquet; nombres `100,000/100,000` e identificadores source `39,539/39,539` retenidos exactamente; full validation y replay `1/1`;
- accountability ledger: `126,770` facts / `15` Parquet; full validation y replay `15/15`;
- actores: `88,031` mandatos / `108` Parquet; full validation y replay `108/108`.

Hay `2` lanes reales por encima de un millón, `6` corpora registrados y `0` lanes promocionadas. BDNS pasa `R1`, pero sigue en `100,000/1M`, sin historia representativa, segundo snapshot, origin público ni clean restore. Candidaturas nominales siguen en `0` por bloqueo del origen oficial. El inventario documental real contiene `21,398` instancias / `19,538` hashes. Estado honesto: `real_foundation_ready_scale_incomplete`. Ver `etl/data/published/scale-readiness-latest.json`, `docs/etl/real-corpus-registry.json` y `ROADMAP.md`.

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
