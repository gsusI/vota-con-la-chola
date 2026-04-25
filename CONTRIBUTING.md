# Contribución

Gracias por aportar en un proyecto de infraestructura pública y verificable.

## Antes de empezar

1. Revisa la tesis de proyecto: `docs/strategy/project-thesis.md`.
2. Revisa el roadmap canónico: `ROADMAP.md`.
3. Usa `docs/roadmap.md` solo como marco macro de producto/datos/arquitectura.
4. Lee la política de gobernanza: `GOVERNANCE.md` y `docs/governance/decision-log-process.md`.
5. Confirma que existe una tarea abierta o un issue de seguimiento.

## Flujo de contribución recomendado

1. Abre un issue (si no existe) y clasifícalo con plantillas.
   - Usa la plantilla de issue adecuada desde `.github/ISSUE_TEMPLATE/`.
2. Crea una rama corta desde `main` con nombre descriptivo (`feat/...`, `fix/...`, `docs/...`, `ops/...`).
3. Haz cambios pequeños y con foco único.
4. Documenta decisiones puntuales en el log (si aplica).
5. Abre PR contra `main`.
6. Pide revisión, integra feedback y vuelve a pasar checklist.

## Tipos de cambios

### Cambios de datos / ETL

- Añade `source_url` y `source_hash` cuando se publique información nueva.
- Si el cambio altera contratos públicos (snapshots/HF), actualiza documentación de release y validación.

### Cambios de UI/API

- Mantén los cambios acotados a una ruta o capacidad.
- Incluye captura mental del flujo o ejemplos de uso cuando cambie experiencia.

### Cambios de documentación

- Prefiere ejemplos concretos y decisiones explícitas.
- Alinea nuevos docs con `docs/README.md`.

## Plantillas obligatorias

- Usa una plantilla de issue para abrir o discutir la tarea antes del PR.
- Usa `.github/PULL_REQUEST_TEMPLATE.md` como base para el cuerpo del PR.

## Checklist de PR (mínimo)

- [ ] Scope explícito y acotado (no mezclar refactor grande + cambio funcional).
- [ ] Evidencia y contexto incluidos (issue o contexto técnico enlazado).
- [ ] Cambios públicos o de contrato: documentación / release actualizado.
- [ ] Si hay riesgo legal/ética: `docs/legal/data-rights.md` revisado en el alcance.
- [ ] Pruebas mínimas ejecutadas si aplica (o justificación de no ejecutar).

## Revisión y merge

- Revisión por codeowner según `CODEOWNERS`.
- El merge debe cumplir checks de CI.
- Para cambios sensibles de esquema o publicación, aplicar doble aprobación de equipo core.

## Gobernanza operativa

- Para cambios con impacto en decisión, trazabilidad o alcance público, registrar decisión en:
  - `docs/governance/decision-log-process.md`
- Para cambios de procesos del repo (labels, policies, plantilla de release), actualizar también:
  - `docs/ops/github-about.md`
