# Seed 11: entity resolution, comparison engine y evidence-backed Q&A

## Titulo sugerido

Construir la capa de entity resolution temporal, comparison engine y preguntas respondibles con evidencia

## Por que importa

El proyecto se vuelve realmente util cuando puede responder preguntas consistentes sobre una misma persona, partido o institucion a traves del tiempo, y comparar promesas o posiciones contra acciones sin esconder los casos no comparables.

## Alcance

- implementar entity resolution temporal para personas, partidos, instituciones y aliases
- definir el comparison engine de promesas/posiciones vs acciones
- exponer un primer subset de preguntas respondibles con evidencia y estados de confianza

## Definition of Done

- existe una capa temporal de identidad con reglas y failure modes documentados
- el comparison engine soporta estados como `aligned`, `conflicted`, `insufficient_evidence`, `ambiguous_mapping` y `not_comparable`
- al menos cinco preguntas iniciales pueden responderse con evidencia, freshness y caveats
- la salida nunca colapsa la incertidumbre a un veredicto unico

## Contexto inicial

- `docs/roadmap.md`
- `docs/roadmap/public-roadmap.md`
- tablas actuales de personas, mandatos, votos, topics y evidencia

## Labels sugeridos

- `area:etl`
- `area:ui`
- `type:enhancement`
- `priority:high`

## Milestone sugerido

`H3 - framework completo de accountability`
