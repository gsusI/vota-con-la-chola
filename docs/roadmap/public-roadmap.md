# Roadmap publico

Este documento explica la ruta publica del proyecto para usuarios, colaboradores y posibles partners.

Nota (`2026-04-12`):
- `ROADMAP.md` es la fuente de verdad canónica para el futuro del proyecto.
- Este documento es un resumen publico derivado y no debe abrir scope nuevo por su cuenta.

No sustituye a las fuentes de verdad operativas:

- futuro y secuencia canonica: `ROADMAP.md`
- vision y destino: `docs/roadmap.md`
- ejecucion de corto plazo: `docs/roadmap-tecnico.md`
- estado real de conectores, blockers y gates: `docs/etl/e2e-scrape-load-tracker.md`

## Punto de partida

La base minima para abrir el proyecto a colaboradores ya existe:

- tesis y limites publicos: `docs/strategy/project-thesis.md` y `docs/strategy/non-goals.md`
- auditoria de claims publicos: `docs/audits/public-claims-audit.md`
- separacion entre licencia de codigo y derechos de datos: `LICENSE` y `docs/legal/data-rights.md`
- pack basico de gobernanza y GitHub: `README.md`, `CONTRIBUTING.md`, `docs/ops/github-about.md`, `docs/governance/decision-log-process.md`
- camino rapido de desarrollo local: `docs/dev/quickstart.md`

La pregunta ya no es "si hay base", sino como convertir esa base en:

1. un producto publico claramente util hoy,
2. una plataforma donde externos puedan construir,
3. un framework de accountability capaz de comparar promesas, acciones e impacto con evidencia.

## Hito 0

Antes de abrir nuevas superficies, el proyecto mantiene tres reglas:

- no duplicar backlog operativo fuera de `docs/etl/e2e-scrape-load-tracker.md`
- no convertir el roadmap publico en otra checklist tecnica
- no prometer cobertura o causalidad por delante de la evidencia disponible

## Horizonte 1: valor actual del producto

Objetivo: hacer que el valor publico actual sea evidente, compartible y auditable sin pedir fe al usuario.

Resultado esperado:

- una propuesta publica principal, facil de explicar
- reglas explicitas de verdad, cobertura e incertidumbre
- al menos dos superficies compartibles: una para explicar votos y otra para mostrar bloqueos de acceso a datos
- un dashboard minimo de frescura, cobertura y cambios publicados

| Paso | Delta visible | Seed |
|---|---|---|
| Elegir wedge publico y contrato de verdad | El proyecto deja de presentarse como "muchas cosas a medio hacer" y pasa a liderar con un caso de uso principal y un lenguaje honesto de cobertura | [`01-public-wedge-and-truth-contract.md`](../issues-seed/01-public-wedge-and-truth-contract.md) |
| Vote explainer MVP | Una pagina compartible responde que se voto, que paso, quien voto como, que fuentes oficiales lo respaldan y que caveats aplican | [`02-vote-explainer-mvp.md`](../issues-seed/02-vote-explainer-mvp.md) |
| Obstruction tracker MVP | Una pagina/feed publico hace visible donde el acceso a datos publicos esta bloqueado y cuanto dano operativo produce | [`03-obstruction-tracker-mvp.md`](../issues-seed/03-obstruction-tracker-mvp.md) |
| Transparency dashboard y flujo de release notes | El usuario puede ver freshness, cobertura, ultima version publicada y cambios recientes sin abrir la DB | [`04-transparency-dashboard-and-release-notes.md`](../issues-seed/04-transparency-dashboard-and-release-notes.md) |

## Horizonte 2: plataforma contributiva

Objetivo: hacer que el repo sea extensible por terceros sin depender de conocimiento tribal ni de tocar todo el monolito a la vez.

Resultado esperado:

- ontologia minima y contratos de plugin claros
- API de evidencia reutilizable para UI, investigadores y herramientas externas
- perfiles y dossiers publicos basados en evidencia, no solo tablas crudas
- starter issues y guias para que nuevos colaboradores aterricen rapido

| Paso | Delta visible | Seed |
|---|---|---|
| Core ontology v1 + plugin architecture | El proyecto deja de crecer solo por costumbre interna y pasa a tener interfaces claras para conectores, extractores y publicadores | [`05-core-ontology-and-plugin-architecture.md`](../issues-seed/05-core-ontology-and-plugin-architecture.md) |
| Evidence API v1 | Los consumidores internos y externos dejan de depender de SQL ad hoc para reconstruir evidencia, confianza y freshness | [`06-evidence-api-v1.md`](../issues-seed/06-evidence-api-v1.md) |
| Actor dossiers y public profiles | El sistema pasa de snapshots agregados a perfiles navegables de personas, partidos e instituciones con drill-down a evidencia | [`07-actor-dossiers-and-public-profiles.md`](../issues-seed/07-actor-dossiers-and-public-profiles.md) |
| Contributor challenge pack + partner guide | El camino de entrada para contributors, media labs y civic hackers deja de ser implicito y pasa a ser un paquete operativo | [`08-contributor-challenge-pack-and-partner-guide.md`](../issues-seed/08-contributor-challenge-pack-and-partner-guide.md) |

## Horizonte 3: framework completo de accountability

Objetivo: comparar lo que se promete, lo que se hace y lo que cambia despues, con caveats metodologicos y trazabilidad por defecto.

Resultado esperado:

- ingesta reproducible de claims y promesas
- conectores iniciales fuera del parlamento para dinero publico, acuerdos, geopolitica e indicadores
- identidad temporal robusta para personas, partidos e instituciones
- motor de comparacion entre promesas/posiciones y acciones
- una primera capa de preguntas respondibles con evidencia y estados explicitos de "no se puede responder aun"

| Paso | Delta visible | Seed |
|---|---|---|
| Promises and claims ingestion MVP | Ya no dependemos solo de votos: se incorpora "lo que dicen" con evidencia textual y reglas de incertidumbre | [`09-promises-and-claims-ingestion-mvp.md`](../issues-seed/09-promises-and-claims-ingestion-mvp.md) |
| External action connectors | El marco sale del parlamento e incorpora al menos una fuente inicial de gasto, acuerdos/influencia, geopolitica e indicadores | [`10-external-action-connectors.md`](../issues-seed/10-external-action-connectors.md) |
| Entity resolution + comparison engine + evidence-backed Q&A | El proyecto puede responder comparaciones serias entre discurso y accion, y devolver evidencia con estados de comparabilidad | [`11-entity-resolution-comparison-and-qa.md`](../issues-seed/11-entity-resolution-comparison-and-qa.md) |

## Orden de lectura recomendado

- Si quieres entender el "por que": `docs/strategy/project-thesis.md`
- Si quieres entender el "que no prometemos": `docs/strategy/non-goals.md`
- Si quieres ver el roadmap canónico: `ROADMAP.md`
- Si quieres ver el estado real hoy: `docs/etl/e2e-scrape-load-tracker.md`
- Si quieres entrar a construir: `docs/dev/quickstart.md` y `docs/issues-seed/README.md`

## Como usar este roadmap

- Cuando un paso se vuelva trabajo inmediato, se abre o actualiza su issue real en GitHub usando el seed correspondiente.
- Cuando cambie la direccion del producto, se actualiza primero `ROADMAP.md` y despues este resumen publico.
- Cuando cambie solo el estado operativo, se actualiza el tracker o el roadmap tecnico, no este documento.
