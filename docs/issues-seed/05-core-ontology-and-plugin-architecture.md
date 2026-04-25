# Seed 05: core ontology v1 y plugin architecture

## Titulo sugerido

Definir core ontology v1 y plugin architecture v1 para crecimiento modular

## Por que importa

Sin vocabulario comun ni interfaces estables, cualquier nuevo conector o modulo aumenta el acoplamiento y vuelve mas dificil la contribucion externa.

## Alcance

- escribir `docs/data-model/core-ontology-v1.md`
- escribir `docs/architecture/plugin-system-v1.md`
- definir entidades nucleares, relaciones, manifiesto de plugin y hooks basicos

## Definition of Done

- la ontologia cubre actores, organizaciones, evidencias, documentos, iniciativas, votos, acuerdos, gasto, indicadores y outcomes
- la arquitectura de plugin define contratos minimos para connectors, extractors, linkers, scorers y publishers
- los docs dejan claro que partes son API estable y que partes siguen experimentales

## Contexto inicial

- `docs/roadmap.md`
- `docs/roadmap/public-roadmap.md`
- `etl/load/sqlite_schema.sql`
- `scripts/ingestar_politicos_es.py`
- `scripts/ingestar_parlamentario_es.py`

## Labels sugeridos

- `area:docs`
- `area:etl`
- `type:enhancement`
- `priority:high`

## Milestone sugerido

`H2 - plataforma contributiva`
