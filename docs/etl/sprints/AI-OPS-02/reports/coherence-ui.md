# Coherence UI (AI-OPS-02)

## Scope

Se actualizo `ui/graph/explorer-temas.html` para exponer la capa de coherencia `says vs does` sobre el tema seleccionado, manteniendo el patron actual de exploracion por esquema (topic_set -> topic -> positions -> evidence + enlaces SQL).

## Cambios UI

- Nueva seccion visible: **Coherencia (says vs does)** en el panel `3) Posiciones y evidencia`.
- Se muestran tres metricas resumen por tema/scope:
  - `overlap`
  - `coherent`
  - `incoherent`
- La seccion muestra tambien contexto (`scope`, `as_of`, `groups`, `explicit`) para auditoria rapida.

## Interaccion (drill-down)

1. Seleccionar `topic_set`.
2. Seleccionar `topic`.
3. En bloque de **Coherencia**, hacer click en un bucket (`overlap`, `coherent`, `incoherent`).
4. La columna **Evidencia** cambia a modo `COHERENCE bucket`, y carga filas de `topic_evidence` para ese bucket.
5. Cada fila mantiene enlaces de auditoria a Explorer SQL (`topic_evidence` por `evidence_id`) y `source_url` cuando existe.

## Comportamiento por modo

- `live`:
  - Usa backend:
    - `GET /api/topics/coherence`
    - `GET /api/topics/coherence/evidence`
  - Buckets habilitados segun conteos (`> 0`).
- `preview` (snapshot estatico):
  - Seccion visible pero no interactiva.
  - Mensaje indica que requiere API local (`just explorer` + `?api=http://127.0.0.1:9010`).

## Compatibilidad con flujo existente

- Se conserva el flujo actual de seleccion por persona para evidencia detallada.
- Al seleccionar una persona en `Posiciones`, la vista vuelve a modo evidencia por persona.
- Se conservan controles existentes (`Method`, `Stance`, filtros de evidencia, paginacion, enlaces SQL).

## Verificacion operativa

- Sanity JS embebido:
  - `node --check` sobre script extraido de `ui/graph/explorer-temas.html`.
- Smoke backend para soporte del drill-down:
  - `build_topics_coherence_payload(...)` retorna conteos no vacios en staging.
  - `build_topics_coherence_evidence_payload(bucket='incoherent', ...)` retorna filas de evidencia.
- Integridad:
  - `PRAGMA foreign_key_check;` sin filas.
