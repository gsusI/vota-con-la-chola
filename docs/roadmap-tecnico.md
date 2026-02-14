# Roadmap técnico

_Fecha base: 2026-02-13_

## 1) Objetivo del roadmap

Entregar una versión técnica robusta de Vota Con La Chola que permita:
- Expresar preferencias del usuario.
- Comparar esas preferencias con posiciones públicas y trazables.
- Calcular fiabilidad por actor y tema con evidencia verificable.
- Publicar resultados reproducibles por snapshot.
- Mantener trazabilidad completa por defecto en SQLite y en JSON publicado.

## 2) Estado base actual

Componentes ya operativos:
- ETL de representantes y mandatos a un único SQLite.
- Ingesta de múltiples fuentes de cargos públicos con idempotencia `(source_id, source_record_id)`.
- Ingesta de votaciones/iniciativas de Congreso y Senado.
- Cargas y publicación de snapshots (`representantes-es-<snapshot>.json` y `votaciones-es-<snapshot>.json`).
- UI de grafo y explorador SQLite con navegación por esquema y FKs.

Brechas críticas pendientes:
- Relación sólida entre votos/iniciativas y “posiciones públicas”.
- Modelo de recomendación explicable para usuario final.
- Capa de confiabilidad con incertidumbre (y señales de cobertura).
- Cobertura multinivel estable para voto útil más allá de nacional.
- Cobertura holística de “acciones” fuera del parlamento: normativa (BOE), acción ejecutiva (Consejo de Ministros), dinero público (contratación PLACSP, subvenciones BDNS) y transparencia (agendas/declaraciones) con trazabilidad.

## 3) Arquitectura objetivo (corto alcance)

Mantener el monolito ultra-lean y avanzar por capas:
- `Ingesta -> Normalización -> Enriquecimiento -> KPIs -> Publicación -> API -> UI`
- Una sola base SQLite de operación.
- Una sola forma de snapshot canónico por fecha.
- Backend mínimo en Python sin agregar frameworks pesados.

## 4) Roadmap por fases

### Fase 0 — Reforzar base de datos y calidad (Semanas 1-4)

Entregables:
- Endurecer esquema para evidencias textuales sin romper compatibilidad.
- Unificar tablas de:
  - personas candidatas (`persons`, `person_identifiers`)
  - temas (`topics`)
  - afirmaciones/acciones (`claims`, `person_topic_actions`)
- Añadir índices recomendados para joins frecuentes.
- Ajustar `scripts/publicar_votaciones_es.py` para incluir campos de calidad por fila.
- Cerrar contrato de calidad con `--enforce-gate` para fuentes críticas.

Criterios de salida:
- `quality-report` de votaciones con `--enforce-gate` en verde en entorno CI local.
- `PRAGMA foreign_key_check` sin errores.
- KPIs mínimos en verde para fuentes `DONE` (ver `docs/etl/e2e-scrape-load-tracker.md`).

### Fase 1 — Cerrar loop de “lo que hacen” (Semanas 5-8)

Entregables:
- Finalizar cobertura nacional reproducible de votaciones con linking estable a iniciativa/tema.
- Publicación periódica del snapshot de votaciones + KPIs.
- Resolver `person_id` en máximo volumen posible en votos nominales.
- Añadir auditoría de causa de no-mapeo con muestra revisable.
- Definir “doble entrada” para acciones: señales comunicacionales (ej. referencias del Consejo de Ministros) deben validarse contra registros con efectos (ej. BOE) cuando exista correspondencia.

Métricas de aceptación:
- `>= 95%` eventos con fecha.
- `>= 95%` eventos con tema enlazado en fuentes nacionales.
- `>= 90%` votos nominales con `person_id` cuando exista censo disponible.
- Trazabilidad completa: cada registro publicado con `source_id` y `source_url`.

### Fase 2 — Posiciones públicas y señal de coherencia (Semanas 9-14)

Entregables:
- Pipeline mínimo para textos programáticos/declarativos (programas, comunicados, propuestas).
- Extracción de claims con:
  - actor
  - tema
  - postura
  - evidencia textual
  - confianza base por fuente.
- Capa de normalización de postura:
  - `a favor`, `en contra`, `mixta`, `incierta`.
- Unión de claims + votos en la misma ontología de temas.

Controles:
- `% rows con source_url y source_hash = 100%` para contenido publicado.
- Regla de revisión humana (`low_confidence` y cambios de tópico ambiguo).

### Fase 3 — Motor de recomendación y fiabilidad (Semanas 15-20)

Entregables:
- `POST /api/recommendation/run` (local o CLI equivalente) que reciba:
  - preferencias
  - pesos social/personal
  - circunscripción/ámbito.
- Score de alineación por actor con explicación por tema.
- Score de fiabilidad por actor y tema con incertidumbre (conservador con pocas muestras).
- Vistas: “alineación”, “evidencia”, “vacíos de evidencia”.

Modelo de base:
- Alineación = suma ponderada de coincidencia tema-postura.
- Fiabilidad = función de consistencia voto-habla y consistencia temporal de comportamiento.
- Presentar siempre `count` y nivel de confianza, no solo numeritos.

### Fase 4 — UX + comunidad + operaciones (Semanas 21-24)

Entregables:
- Onboarding de preferencias en 60 segundos.
- Matriz final actor/partido por:
  - alineación
- evidencia verificable.
- Página de “cómo se calculó” con links a evidencias.
- Integración de revisión comunitaria de claims (PR + checklist 2ª mirada).
- Pipeline de publicación canónica para:
  - `topics.json`
  - `claims.json`
  - `recommendation-kpis.json`

### Fase 5 — Cobertura multinivel (desde Semana 25)

Prioridad por impacto:
- Electoralmente: CCAA y municipal donde haya fuente reproducible.
- UE: votaciones/roll-call en formato usable para voto-nominal.
- Información territorial:
  - mapa de competencias
- Ajuste de recomendaciones por nivel con mismo formato de scores.

## 5) Gestión técnica de riesgos

Riesgo de red anti-bot:
- Mantener modo manual con evidencia reproducible por snapshots `--from-file`.
- Documentar fallback y estado en `ingestion_runs.message`.

Riesgo de sesgo metodológico:
- Publicar metodología, pesos y fuentes antes de cada release.
- Separar evidencia declarativa de evidencia de voto y mostrar cobertura por tema.

Riesgo de legalidad y privacidad:
- Evitar persistir preferencias sensibles en servidor por defecto.
- Minimizar datos personales; priorizar cómputo local cuando sea viable.

## 6) Plan de entregas (resumen)

M1 (semana 1): esquema extendido + calidad y estabilidad de ingestión.
M2 (semana 4): cobertura nacional de votos + linking + publicación de KPIs.
M3 (semana 8): claims públicos + unión de acción y voto.
M4 (semana 12): motor de recomendación v1 con trazabilidad.
M5 (semana 16): interfaz final de explicación y revisión comunitaria.
M6 (semana 20): expansión de cobertura por nivel cuando exista fuente estable.

## 7) KPIs de programa

- Cobertura de tracking:
  - fuentes críticas en estado `ok` en ejecución e2e.
- Cobertura política:
  - eventos con tema enlazado.
  - porcentaje de votos nominales con persona resuelta.
- Productividad:
  - tiempo de `etl` por snapshot.
  - costo de reintentos por fuente.
- Calidad de recomendación:
  - porcentaje de temas con evidencia suficiente.
  - tasa de cambios en recomendaciones tras nueva evidencia.

## 8) Próximo paso operativo

Crear un `MILESTONE-1` con este alcance:
- Cerrar `Fase 0` y `Fase 1`.
- Añadir una tarea a `justfile` para publicar `votaciones-kpis-es-<snapshot>.json` en cada corrida planificada.
- Registrar el baseline de KPIs en `docs/etl/e2e-scrape-load-tracker.md`.
