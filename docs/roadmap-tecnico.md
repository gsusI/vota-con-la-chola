# Roadmap técnico

Nota:
- Visión macro y marco "acción revelada + impacto": `docs/roadmap.md`.
- Este documento se centra en la ejecución de corto plazo para cerrar el loop "dicen/hacen", fiabilidad y recomendación con trazabilidad.
- Estimación de esfuerzo en puntos (misma escala que `docs/roadmap.md`).
- Backlog operativo + estado real: `docs/etl/e2e-scrape-load-tracker.md` y dashboard `/explorer-sources`.

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

### Fase 0 — Reforzar base de datos y calidad (`ENG: 8`)

Entregables:
- Endurecer esquema para evidencias textuales sin romper compatibilidad.
- Consolidar identidad de personas: `persons` + `person_identifiers` + normalización de nombres.
- Consolidar analítica por temas: `topic_sets`, `topics`, `topic_evidence`, `topic_positions` (seed/versionado: `etl/data/seeds/topic_taxonomy_es.json`).
- Añadir índices recomendados para joins frecuentes.
- Ajustar `scripts/publicar_votaciones_es.py` para incluir campos de calidad por fila.
- Cerrar contrato de calidad con `--enforce-gate` para fuentes críticas.

Criterios de salida:
- `quality-report` de votaciones con `--enforce-gate` en verde en entorno CI local.
- `PRAGMA foreign_key_check` sin errores.
- KPIs mínimos en verde para fuentes `DONE` (ver `docs/etl/e2e-scrape-load-tracker.md`).

### Fase 1 — Cerrar loop de “lo que hacen” (`ENG: 8`)

Entregables:
- Finalizar cobertura nacional reproducible de votaciones con linking estable a iniciativa/tema.
- Publicación periódica del snapshot de votaciones + KPIs.
- Resolver `person_id` en máximo volumen posible en votos nominales.
- Añadir auditoría de causa de no-mapeo con muestra revisable.
- Definir “doble entrada” para acciones: señales comunicacionales (ej. referencias del Consejo de Ministros) deben validarse contra registros con efectos (ej. BOE) cuando exista correspondencia.

Métricas de aceptación:
- `>= 95%` eventos con fecha.
- `>= 95%` eventos con iniciativa enlazada (permitir `derived` cuando el catálogo oficial sea incompleto).
- `>= 90%` votos nominales con `person_id` cuando exista censo disponible.
- Seguimiento visible de `latest_events_with_topic_evidence_pct` (eventos de la legislatura activa presentes en `topic_evidence`).
- Trazabilidad completa: cada registro publicado con `source_id` y `source_url`.

### Fase 2 — Posiciones públicas y señal de coherencia (`ENG: 13`)

Entregables:
- Pipeline mínimo para textos programáticos/declarativos (programas, comunicados, propuestas).
- Extracción de claims con actor, tema, postura, evidencia textual y confianza base por fuente.
- Capa de normalización de postura: `a favor`, `en contra`, `mixta`, `incierta`.
- Unión de claims + votos en la misma ontología de temas.

Controles:
- `% rows con source_url y source_hash = 100%` para contenido publicado.
- Regla de revisión humana (`low_confidence` y cambios de tópico ambiguo).

### Fase 3 — Motor de recomendación y fiabilidad (`ENG: 13`)

Entregables:
- `POST /api/recommendation/run` (local o CLI equivalente) que reciba preferencias, pesos social/personal y circunscripción/ámbito.
- Score de alineación por actor con explicación por tema.
- Score de fiabilidad por actor y tema con incertidumbre (conservador con pocas muestras).
- Vistas: “alineación”, “evidencia”, “vacíos de evidencia”.

Modelo de base:
- Alineación = suma ponderada de coincidencia tema-postura.
- Fiabilidad = función de consistencia voto-habla y consistencia temporal de comportamiento.
- Presentar siempre `count` y nivel de confianza, no solo numeritos.

### Fase 4 — UX + comunidad + operaciones (`ENG: 8`)

Entregables:
- Onboarding de preferencias en 60 segundos.
- Matriz final actor/partido por alineación y evidencia verificable.
- Página de “cómo se calculó” con links a evidencias.
- Integración de revisión comunitaria de claims (PR + checklist 2ª mirada).
- Pipeline de publicación canónica para `topics.json`, `claims.json`, `recommendation-kpis.json`.

### Fase 5 — Cobertura multinivel (`ENG: 21+`)

Prioridad por impacto:
- Electoralmente: CCAA y municipal donde haya fuente reproducible.
- UE: votaciones/roll-call en formato usable para voto-nominal.
- Información territorial: mapa de competencias.
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

## 6) KPIs de programa

- Cobertura de tracking: fuentes críticas en estado `ok` en ejecución e2e.
- Cobertura política: eventos con iniciativa enlazada; % votos nominales con persona resuelta; % evidencia con `topic_id`.
- Productividad: tiempo de `etl` por snapshot; costo de reintentos por fuente.
- Calidad de recomendación: porcentaje de temas con evidencia suficiente; tasa de cambios en recomendaciones tras nueva evidencia.

## 7) Próximo paso operativo

`MILESTONE-1` (cerrar `Fase 0` + dejar encaminada `Fase 1`):

Hecho:
- Pipeline reproducible de votaciones con gate + KPIs: `just parl-publish-votaciones`.
- Baseline operativo en tracker: `docs/etl/e2e-scrape-load-tracker.md` + dashboard `/explorer-sources`.

Pendiente (siguiente foco):
- Congreso: el linking voto -> iniciativa está cubierto vía fallback `derived` cuando no hay match oficial; el KPI clave ahora es subir la **cobertura oficial** (`events_with_official_initiative_link_pct`) si decidimos invertir en eso (p.ej. incorporar tipos faltantes como PNL/mociones).
- Reemplazar el KPI “tema enlazado” por un KPI real de clasificación a `topic_id` (no confundir “hay texto” con “hay tema”).
- Consolidar `backfill-topic-analytics` como parte del loop E2E (votos -> evidencia -> posiciones) y visibilizarlo en `/explorer-temas`.
- Intervenciones (says): subir `declared_evidence_with_signal_pct` con `just parl-backfill-declared-stance` (stance regex v2, conservador) y mantener `topic_evidence_reviews` como cola de casos ambiguos para auditoría humana.
- Materializar `computed_method=combined` (`just parl-backfill-combined-positions`) y usarlo como vista por defecto en producto para evitar mezclar “says/does” en tiempo real.
- Siguiente bloque técnico: drill-down de coherencia por `topic_set/topic/scope` para priorizar revisión donde la incoherencia sea material.
- Cerrar loop de revisión (KISS): `review-queue` + `review-decision` para pasar `pending -> resolved/ignored` con nota y recompute determinista (`declared` + `combined`).
