# Seed 04: transparency dashboard y flujo de release notes

## Titulo sugerido

Crear transparency dashboard publico y flujo ligero de release notes

## Por que importa

Si el usuario no puede ver freshness, cobertura, snapshot actual y cambios recientes, la confianza depende demasiado de leer docs internas. Hace falta una capa minima de transparencia operativa.

## Alcance

- dashboard con freshness, cobertura, version publicada y cambios recientes
- flujo ligero para notas de release por snapshot o por corte publico relevante
- enlaces a artefactos publicados y a evidencia fuente cuando aplique

## Definition of Done

- el dashboard expone fecha de snapshot, freshness y resumen de cobertura
- existe una ubicacion estable para release notes publicas
- cada numero visible en dashboard o release tiene una fuente trazable
- el flujo no introduce otro backlog duplicado

## Contexto inicial

- `docs/audits/public-claims-audit.md`
- `docs/roadmap/public-roadmap.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `etl/data/published/`

## Labels sugeridos

- `area:ui`
- `area:docs`
- `type:release`
- `priority:medium`

## Milestone sugerido

`H1 - valor actual del producto`
