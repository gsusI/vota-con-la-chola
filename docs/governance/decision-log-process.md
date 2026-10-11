# Proceso de decision log

## Objetivo

Mantener trazabilidad de decisiones de gobernanza, cambios de contrato y decisiones de publicación que afectan a colaboradores o al comportamiento público del proyecto.

## Cuándo registrar una decisión

Registra una entrada para decisiones con alguno de estos impactos:

- Cambios de alcance funcional visible.
- Ajustes de esquema, contratos de datos o convenciones de evidencia.
- Política de publicación (snapshots, HF, GH Pages, privacy).
- Cambios de fuente crítica o método de ingestión masivo.
- Cambios de reglas de revisión, release o seguridad.

No registrar:

- Cambios mecánicos de documentación sin impacto operativo.
- Correcciones de estilo o refactors no funcionales.

## Ubicación del log

Conservar este documento como bitácora append-only en la sección de historial.

## Formato de entrada

Cada entrada usa esta plantilla:

- **ID**: `YYYY-MM-DD-<slug>`
- **Fecha**: `YYYY-MM-DD`
- **Decisor principal**: equipo o persona responsable
- **Decisión**: qué se decidió
- **Alternativas descartadas**: alternativas evaluadas y motivo del descarte
- **Impacto**: riesgo, alcance y alcance de la decisión
- **Implementación**: PR/commit asociado
- **Seguimiento**: pruebas/checklist o evidencia post-decision

## Reglas de proceso

1. Toda entrada debe enlazar evidencia o artefacto verificable.
2. Debe existir un responsable y un estado (`en progreso`, `aprobada`, `revertida`).
3. Cualquier rollback de una decisión debe quedar registrado en una nueva entrada.
4. Para decisiones públicas (release o cambio de contrato), cerrar con comprobación y fecha de validación.

## Historial

### 2026-02-24: docs/ops/github-about y templates de GitHub
- **ID:** 2026-02-24-github-onboarding-pack
- **Decisor principal:** Core maintainer inicial
- **Decisión:** Centralizar metadatos de repo (About, topics, labels, roles, release checklist) en `docs/ops/github-about.md` y crear templates de issue/PR.
- **Alternativas descartadas:** Mantener metadatos solo en archivos dispersos de CI o en `README`.
- **Impacto:** Mejora onboarding para externos, reduce barreras de colaboración y deja explícitos límites de gobernanza.
- **Implementación:** `README.md`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/ops/github-about.md`, `docs/governance/decision-log-process.md`.
- **Seguimiento:** Sin evidencia pública adicional pendiente.
- **Estado:** aprobada


### 2026-09-05: prioridad de lanzamiento y reutilización comunitaria

- **ID:** 2026-09-05-public-launch-focus
- **Fecha:** 2026-09-05
- **Decisor principal:** mantenedor del proyecto; recomendación operativa preparada por Dev.
- **Decisión:** traducir la petición de foco y utilidad pública a [L0–L5 del roadmap canónico](../../ROADMAP.md#prioridad-inmediata-lanzamiento-útil-para-la-comunidad). PLACSP es la entrega recomendada, todavía sujeta al gate L0; no se presenta la elección como aprobación externa ni el plan como implementación.
- **Alternativas descartadas para la primera entrega:** completar toda la escala documental, abrir más dominios, crear otra plataforma/SDK o condicionar el lanzamiento al apoyo de una persona concreta.
- **Impacto:** prioriza reutilización y contribuciones sobre expansión; conserva misión ciudadana, backlog, requisitos de evidencia, publicación y estados incompletos. No autoriza mensajes a terceros ni da por aprobadas alegaciones.
- **Implementación:** documentación local en ROADMAP, roadmap técnico y tracker; sin commit ni modificación remota.
- **Seguimiento:** [auditoría pública del 2026-09-05](../etl/sprints/PUBLIC-LAUNCH-20260905/evidence/launch-audit.md), gates de lanzamiento y adopción definidos exclusivamente en ROADMAP.
- **Estado:** en progreso; planificación preparada, L0 y lanzamiento pendientes.
