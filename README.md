# Vota Con La Chola

![Vota Con La Chola - portada](docs/screenshots/cover-graph-congreso-diputados-depth-3-active-lens-all.png)

[![ETL Tracker Gate](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml/badge.svg)](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml)
![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Estado del proyecto](https://img.shields.io/badge/status-mvp-orange.svg)
[![HF Dataset](https://img.shields.io/badge/HF-dataset-blue)](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data)

Herramienta abierta y orientada a la evidencia para ayudar a decidir tu voto: cruza tus prioridades con lo que actores políticos y partidos **dicen** y **hacen**, con explicaciones trazables y fuentes auditables.

Este repo es intencionalmente **ultraligero**: un solo SQLite, snapshots reproducibles y trazabilidad por defecto.

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

## Notas (KISS)

- `ROADMAP.md` es la única fuente de verdad para el futuro y la secuencia del proyecto.
- `docs/roadmap.md` y `docs/roadmap-tecnico.md` son docs de soporte; no deben abrir scope nuevo por su cuenta.
- `docs/etl/e2e-scrape-load-tracker.md` es la única lista operativa de TODO.
- `intro.md` está ignorado por git (nota local); evita convertirlo en otro roadmap.
- No se versionan bases ni raws grandes: usa `etl/data/raw/samples/` y artefactos publicados pequeños.

## Contribución y gobernanza

- Contribuir: `CONTRIBUTING.md`
- Gobernanza: `GOVERNANCE.md`
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
