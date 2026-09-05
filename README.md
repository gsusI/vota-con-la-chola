# Vota Con La Chola

**[Explorar adjudicaciones](https://votaconlachola.org/spending/) · [Reproducir una consulta](docs/examples/placsp-launch/README.md) · [Contribuir](docs/community/placsp-launch-tasks.md)**

Pregunta de entrada: ¿a quién se adjudicó, cuánto y en qué expedientes? La demo muestra un corte histórico parcial con fuentes verificables. Alfa técnica; revisión comunitaria pendiente.

![Vota Con La Chola - portada](docs/screenshots/cover-graph-congreso-diputados-depth-3-active-lens-all.png)

[![ETL Tracker Gate](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml/badge.svg)](https://github.com/gsusI/vota-con-la-chola/actions/workflows/etl-tracker-gate.yml)
![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Estado del proyecto](https://img.shields.io/badge/status-mvp-orange.svg)
[![HF Dataset](https://img.shields.io/badge/HF-dataset-blue)](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data)

Herramienta abierta y orientada a la evidencia para ayudar a decidir tu voto: cruza tus prioridades con lo que actores políticos y partidos **dicen** y **hacen**, con explicaciones trazables y fuentes auditables.

Este repo es intencionalmente **ultraligero**: SQLite reproducible para control/snapshots, objetos content-addressed para documentos, artefactos analíticos/publicación acotados y trazabilidad por defecto.

## Prioridad inmediata: lanzamiento útil para la comunidad

Primera entrega: investigar contratación pública con un corte fechado y explícitamente parcial de PLACSP. Pregunta de entrada: **«¿A quién adjudicó este organismo, cuánto y en qué expedientes, dentro de este corte?»**. El recorrido previsto une pregunta, consulta, resultado, expediente oficial y reproducción.

**Ahora:** [alfa técnica publicada](https://github.com/gsusI/vota-con-la-chola/releases/tag/v0.1.0-placsp-alpha.1), demo y descarga anónima verificadas. **Destino:** una respuesta comprobable y reutilizable por desarrolladores de datos, periodistas y fiscalizadores cívicos. **Siguiente:** recoger reproducciones externas y revisar adopción. Una adjudicación no equivale a un pago; el corte no representa toda la contratación pública.

Los seis hitos siguientes resumen el [plan canónico y sus condiciones de aceptación](ROADMAP.md#hitos-de-lanzamiento); su estado operativo se mantiene en el [tracker de lanzamiento](docs/etl/e2e-scrape-load-tracker.md#lanzamiento-comunitario-con-foco-2026-09-05).

1. **L0 — Corte defendible.** Fijar release inmutable, procedencia, fechas, cobertura, exclusiones y hashes; reconciliar anuncios, adjudicaciones, lotes y versiones, con fuentes verificables para cada resultado.
2. **L1 — Reutilización real.** Entregar CSV/Parquet, tres consultas SQL parametrizadas, resultados esperados, diccionario y reproducción desde descarga anónima en un entorno vacío.
3. **L2 — Demo pública.** Ampliar `/spending/` con órgano, proveedor y periodo; resultado compartible, CSV y acceso directo a evidencia. Mostrar fecha y límites del mismo corte validado.
4. **L3 — Entrada de colaboradores.** Facilitar reproducción y tres rutas de aportación, con seis tareas pequeñas que indiquen entrada, salida, validación y responsable; reconocer contribuciones por dataset, consulta y revisión.
5. **L4 — Verificación.** Comprobar recorrido, privacidad, datos reales y coincidencia de hashes/resultados entre descarga y web. Buscar tres pruebas externas del recorrido y dos reproducciones de consultas; mientras falten, identificar la entrega como alfa técnica con validación comunitaria pendiente.
6. **L5 — Presentación y adopción.** Publicar release GitHub, vídeo de 60–90 segundos y ejemplo reproducible; preparar convocatoria para una tarea concreta. Enviar solo con autorización específica y revisar adopción real a los 14 días de difusión.

Comandos y secuencia de implementación: [roadmap técnico](docs/roadmap-tecnico.md#lanzamiento-comunitario-primer-trabajo). Este lanzamiento acotado tiene prioridad sobre la expansión; no cierra los requisitos globales de escala ni sustituye la misión ciudadana.

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

## Qué hay hoy

- [Demo de contratación](https://votaconlachola.org/spending/): corte parcial de 120 resultados, decisiones del 1–3 de enero de 2025; fuente y captura XML por resultado.
- [Reproducción con Python](docs/examples/placsp-launch/README.md): CSV/Parquet, tres consultas SQL y hashes; sin claves ni base previa.
- [Seis primeras tareas](docs/community/placsp-launch-tasks.md): consultas, verificación y documentación, con entradas, resultados y validación definidos.
- ETL de representantes, votaciones, contratación, subvenciones e indicadores; SQLite, artefactos analíticos y evidencia oficial.

El lanzamiento es una alfa técnica. Validación comunitaria pendiente. Estado de escala y bloqueos globales: [tracker](docs/etl/e2e-scrape-load-tracker.md) y [roadmap](ROADMAP.md); esta entrega no los cierra.

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

Comandos de escala, adquisición, publicación y gates: [guía ETL](docs/etl/README.md) y [roadmap técnico](docs/roadmap-tecnico.md). Para analizar el corte PLACSP basta con la [guía de reproducción](docs/examples/placsp-launch/README.md).

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
