# Seed 06: evidence API v1

## Titulo sugerido

Diseñar e implementar evidence API v1 para consumo interno y externo

## Por que importa

La evidencia no puede quedar encerrada en consultas SQL internas. Hace falta un contrato reutilizable para UI, periodistas, notebooks y futuros partners.

## Alcance

- escribir `docs/api/evidence-api-v1.md`
- implementar endpoints o salidas equivalentes para actores, temas, eventos y evidencias
- incluir freshness, confidence y enlaces de drill-down

## Definition of Done

- existe especificacion de rutas o contratos JSON estables
- al menos un consumidor real usa la API
- cada respuesta incluye metadatos de evidencia suficientes para auditoria
- hay pruebas del contrato basico

## Contexto inicial

- `scripts/graph_ui_server.py`
- `ui/graph/explorer.html`
- `docs/roadmap/public-roadmap.md`
- `docs/audits/public-claims-audit.md`

## Labels sugeridos

- `area:etl`
- `area:ui`
- `type:enhancement`
- `priority:high`

## Milestone sugerido

`H2 - plataforma contributiva`
