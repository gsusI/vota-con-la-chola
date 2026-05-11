# GitHub About and repository governance settings

Última actualización: 2026-02-24

Este documento guarda la configuración de GitHub que no puede vivir en código fuente (About, Topics, labels, branch rules).

## GitHub About (texto sugerido)

**Name (no cambiar):** `vota-con-la-chola`

**Short description:**
- `Infraestructura cívica de evidencia pública para decisiones políticas informadas, reproducible y rastreable.`

**About / featured text (opcional):**
- `Proyecto orientado a trazabilidad: conecta lo que actores políticos dicen con lo que hacen, con evidencia pública y contratos de datos claros.`

**Website:**
- https://gsusI.github.io/vota-con-la-chola/

**Topics sugeridos:**
- civic-tech
- open-data
- politics
- democracy
- transparency
- data-governance
- reproducible-research
- parliamentary-data

**Badges sugeridos en README:**
- `etl-tracker-gate.yml` workflow status
- `license-MIT`
- `HF dataset`

## Maintainer roles

Define roles de primer nivel en docs y PR:

- **Project Steward**: visión global, prioridades, riesgos de producto.
- **Data Steward**: calidad, cobertura, trazabilidad y bloqueos de fuentes.
- **Infrastructure Steward**: Docker/Just, pipelines, CI y publicación de artefactos.

Mapeo inicial:
- `@gsusI` → Project Steward
- `@gsusI` → Data Steward
- `@gsusI` → Infrastructure Steward

`CODEOWNERS` se mantiene para rutas en esta fase:
- `*` → Project Steward
- `/etl/` → Data Steward
- `/scripts/` → Infrastructure Steward

## Plantillas de issue habilitadas

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/data_source_request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`

## Taxonomía de labels (recomendada)

Crear en Settings → Labels del repositorio:

### Dominio
- `area:etl`
- `area:ui`
- `area:docs`
- `area:legal`
- `area:governance`

### Tipo
- `type:bug`
- `type:enhancement`
- `type:data-source`
- `type:release`

### Estado
- `status:needs-repro`
- `status:ready-for-review`
- `status:blocked`
- `status:needs-maintainer`

### Prioridad
- `priority:low`
- `priority:medium`
- `priority:high`

## Plantilla de PR y proceso de revisión

- PRs deben seguir `.github/PULL_REQUEST_TEMPLATE.md`.
- Mantener PRs pequeñas (< 1 objetivo funcional).
- Si el cambio es sensible (esquema / contrato público / release), requiere 2 aprobaciones.

## Release checklist (manual, antes de publicar)

1. Confirmar estado de snapshots:
   - `docs/etl/e2e-scrape-load-tracker.md` actualizado
2. Ejecutar gate de publicación correspondiente.
3. Verificar diff de evidencias y KPIs nuevos.
4. Publicar nota de cambios en `docs/release-notes/` o equivalente.
5. Sincronizar `docs/gh-pages` si aplica.
6. Registrar decision log si la publicación cambia alcance o contrato.

## Cambios manuales que no pueden vivir en el repo

- Tópicos y descripción final del repo.
- Protección de ramas y required reviews.
- Configuración final de labels en la UI de GitHub.
- Ajuste de about page (short description, URL, topics).
