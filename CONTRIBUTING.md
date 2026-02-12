# Contributing (minimal)

Modelo: `trunk-based development` con ramas de corta duración.

## Flujo
1. Crea o toma un issue.
2. Haz un cambio pequeño en una rama corta.
3. Abre PR.
4. Corrige feedback y merge.

## Requisitos de merge
- [ ] Checks en verde.
- [ ] Aprobación de 1 codeowner.
- [ ] Si hay datos publicados: `source_url` + `source_hash`.
- [ ] Si cambia comportamiento público: docs actualizadas.

## Convenciones
- PR ideal: < 300 líneas netas.
- Evita mezclar refactor grande con cambio funcional en la misma PR.

## Entorno recomendado
- Usa Docker para ejecutar ETL de forma reproducible.
- Usa `just` para los comandos de tarea.
- Comandos base:
  - `just etl-build`
  - `just etl-init`
  - `just etl-samples`
  - `just etl-stats`
  - `just etl-tracker-status`
  - `just etl-tracker-gate`
  - `just graph-ui`
