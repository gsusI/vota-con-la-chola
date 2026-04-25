# Seed 03: obstruction tracker MVP

## Titulo sugerido

Publicar el obstruction tracker MVP con evidencia reproducible de bloqueo

## Por que importa

El proyecto tiene una ventaja diferencial fuerte: no solo mide politica, tambien deja rastro cuando las instituciones obstaculizan el acceso a datos publicos. Esa capa debe ser visible y citable.

## Alcance

- construir una pagina o feed publico de salud de fuentes
- mostrar fuentes bloqueadas, ultima evidencia, impacto en cobertura y siguiente accion
- enlazar incidentes a `docs/etl/name-and-shame-access-blockers.md`
- reutilizar el tracker operativo sin duplicar backlog

## Definition of Done

- existe una superficie publica que lista fuentes `ok/blocked/degraded`
- cada fuente bloqueada tiene enlace a evidencia verificable
- el usuario puede entender que parte del producto queda afectada por el bloqueo
- la pagina no inventa estado: consume artefactos publicados o salidas reproducibles

## Contexto inicial

- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/name-and-shame-access-blockers.md`
- `docs/roadmap/public-roadmap.md`

## Labels sugeridos

- `area:ui`
- `area:etl`
- `type:enhancement`
- `priority:high`

## Milestone sugerido

`H1 - valor actual del producto`
