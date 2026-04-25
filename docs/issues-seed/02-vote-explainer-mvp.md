# Seed 02: vote explainer MVP

## Titulo sugerido

Construir el vote explainer MVP con fuentes oficiales y caveats visibles

## Por que importa

Una pagina de voto compartible puede convertirse en la primera pieza que circula entre ciudadanos, periodistas y verificadores. Debe explicar el evento de voto completo sin obligar al usuario a navegar por tablas crudas.

## Alcance

- redactar y/o cerrar `docs/product/vote-explainer-spec.md`
- implementar una ruta publica canonica para un voto
- mostrar que se voto, que paso, quien voto como, fuentes oficiales y caveats
- enlazar a explorer/drill-down cuando exista evidencia mas profunda

## Definition of Done

- existe una ruta estable para el vote explainer
- la pagina muestra fuente oficial primaria y fecha del snapshot
- hay badges de caveat/freshness/coverage alineados con el truth contract
- hay pruebas basicas del contrato JSON o del render minimo

## Contexto inicial

- `docs/roadmap/public-roadmap.md`
- `docs/audits/public-claims-audit.md`
- `docs/gh-pages/legacy/citizen/data/citizen_votes.json`
- `etl/data/published/`

## Labels sugeridos

- `area:ui`
- `area:docs`
- `type:enhancement`
- `priority:high`

## Milestone sugerido

`H1 - valor actual del producto`
