# Transparency dashboard

Estado: `v1 implementado`
Fecha: `2026-08-19`

## Decisión

La ruta pública `/transparency/` es el punto compacto para comprobar el estado real del proyecto. No sustituye al tracker, al registro de obstrucciones, al manifiesto durable ni a las notas de versión. Los resume y enlaza.

Contrato máquina:

- ruta: `/transparency/data/transparency.json`;
- schema: `transparency_dashboard_v1`;
- presupuesto: `<= 1 MB`;
- generación: `just transparency-dashboard-export`;
- validación independiente: `scripts/validate_transparency_dashboard_snapshot.py`.

## Preguntas que responde

1. ¿Cuándo se refrescó el estado de las fuentes?
2. ¿Cuántas fuentes están `ok`, degradadas o todavía sin ejecutar?
3. ¿Cuántas obstrucciones siguen abiertas y cuánta evidencia pública las respalda?
4. ¿Cuál es el último snapshot durable verificado?
5. ¿Cuántas filas, ficheros y corpus contiene ese origen remoto?
6. ¿Qué diferencia existe entre el origen remoto publicado y el readiness local posterior?
7. ¿Qué cambios públicos tienen nota de versión y evidencia?

## Fuentes canónicas

| Bloque | Fuente | Regla |
| --- | --- | --- |
| salud y último refresco | `ui/gh-pages-next/public/explorer-sources/data/status.json` | no recalcular desde copy de UI |
| obstrucciones | `ui/gh-pages-next/public/obstruction-tracker/data/obstructions.json` y su manifest | conservar incidentes y caveat de no atribución |
| readiness local | `etl/data/published/scale-readiness-latest.json` | `0` promociones sigue siendo resultado válido |
| snapshot durable | verificación live de HF registrada en `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/hf-scale-origin-live-verification-20260812.json` | mostrar warnings de drift, no ocultarlos |
| cambios | `docs/release-notes/releases.json` | solo releases reales con nota y evidencia existentes |

## Contrato de trazabilidad

Cada métrica pública incluye:

- `id` estable;
- `value` entero;
- `unit`;
- `source_path` repo-relative;
- `source_url` pública.

Cada nota de versión incluye checksum SHA-256 de la nota y de sus evidencias registradas. El dashboard renderiza todas las métricas y releases del feed; no aplica truncado silencioso.

## Frescura

Se reutiliza el contrato de `docs/method/truth-contract.md`:

- `fresh`: `0-7` días;
- `aging`: `8-30` días;
- `stale`: más de `30` días;
- `future` y `unknown`: inconsistencia o fechas insuficientes.

Los cortes viejos permanecen visibles con warning. No se reemplazan por datos inventados ni por valores vacíos que parezcan actuales.

## Diferencia crítica: publicado no significa promovido

El dashboard separa:

- origen durable remoto: siete corpus, `5,414,326` filas y `8,597` data files en el último puntero público firmado y verificado;
- readiness local: siete corpus validados, tres lanes por encima de un millón y cero lanes promovidas;
- metadata actual: el origin remoto contiene el registry/readiness local vigente, con paridad sin warnings.

Esta diferencia debe seguir visible hasta una publicación nueva. No se infiere paridad.

## Política de datos

- Solo datos oficiales reales y releases verificables.
- Prohibidos registros sintéticos, mock, placeholders o releases inventadas.
- La información personal oficial de dominio público se retiene para accountability.
- Solo se excluyen secretos, sesiones privadas, trazas de workstation y datos no públicos.

## Definition of Done

- exporter y validator pasan;
- todas las métricas reconcilian con su bloque fuente;
- todos los paths de nota/evidencia existen y tienen SHA-256;
- ruta y feed entran en el audit público;
- build estático, real-only y publication-hygiene pasan;
- desktop y móvil se inspeccionan;
- route/asset audit live pasa tras publicar.

## Siguiente evolución

- registrar cada nueva release antes de su publicación;
- añadir diff de snapshot solo desde manifests reales comparables;
- añadir métricas históricas de respuesta y recuperación solo cuando haya resoluciones reales;
- publicar un scorecard comunitario cuando existan contribuciones y tiempos suficientes para medirlo.
