# Especificacion UX por Flujo (Pantallas, Controles, Interacciones y Datos)

Estado: `v1`  
Alcance: blueprint de producto para los flujos `F-01` a `F-26` definidos en `docs/personas-y-flujos-ideales.md`.

## 0) Convenciones de este documento

- Cada flujo lista:
  - pantallas/rutas requeridas,
  - botones/controles requeridos,
  - interacciones/estados requeridos,
  - visualizaciones/charts requeridos,
  - necesidades de datos con `URGENT TODO`.
- Los `URGENT TODO` se etiquetan como `DATA-P0-XX`.
- "Ideal" significa north-star: no asume que exista hoy en la implementacion.

## 1) Backlog urgente de datos (P0)

### DATA-P0-01 - Comparable denominator service
- Contrato para fijar denominador comun por caso/partido y exponer elegibilidad comparable.
- Campos minimos: `topic_id`, `party_id`, `members_total`, `members_with_signal`, `unknown_total`, `comparable_ok`.

### DATA-P0-02 - Stance lineage contract
- Linaje auditable de cualquier stance mostrado en UI.
- Campos minimos: `computed_method`, `computed_version`, `as_of_date`, `coverage`, `confidence`, `evidence_ids`, `source_urls`.

### DATA-P0-03 - Unknown explainability dataset
- Descomposicion de `unknown` por causa (`no_signal`, `unclear`, `mixed`) y recomendacion accionable.

### DATA-P0-04 - Snapshot diff feed
- Diff A/B por entidad/metrica con nivel de materialidad y causa probable.

### DATA-P0-05 - Ranking engine with robustness
- Motor de ranking con umbrales de comparables, shrinkage y analisis de sensibilidad.

### DATA-P0-06 - Event watchlist feed
- Feed de eventos para suscripciones por tema/partido/institucion.

### DATA-P0-07 - Longitudinal stance shift model
- Deteccion de cambios de postura sobre eventos comparables en ventana temporal.

### DATA-P0-08 - Person trajectory timeline model
- Historial normalizado persona->mandato->rol->partido->territorio con evidencias.

### DATA-P0-09 - Ops issue impact scoring
- Scoring de issues tecnicos: impacto ciudadano, severidad, frescura, cobertura afectada.

### DATA-P0-10 - Blocker incident ledger
- Registro append-only de bloqueos externos con evidencia reproducible y estado.

### DATA-P0-11 - Metric-to-SQL trace manifest
- Manifiesto que conecte cada KPI/tarjeta con query/subconjunto exacto usado.

### DATA-P0-12 - Query permalink artifact
- Persistencia de consultas + checksum snapshot + parametros para compartir resultados.

### DATA-P0-13 - Public reproducibility kit
- Plantillas notebook + checks de replica para HF snapshots.

### DATA-P0-14 - Changelog generator
- Generador de changelog tecnico entre snapshots con diff de schema/metricas/filas.

### DATA-P0-15 - MTurk quality telemetry
- Telemetria de calidad por worker: gold accuracy, disagreement rate, rejection causes.

### DATA-P0-16 - Review queue SLA metrics
- Metricas de cola manual: aging, throughput, backlog por `review_reason`, SLA breach.

### DATA-P0-17 - Release gate audit trail
- Evidencia firmada de gates de privacidad, calidad e integridad por release.

### DATA-P0-18 - Incident response artifact pack
- Bundle de incidente con timeline, decision log, impacto y remediacion.

## 2) Especificacion por flujo

### F-01 - Ciudadania de respuesta rapida - Decidir en menos de 5 minutos
- Pantallas:
  - `/citizen/start` (entrada y recomendacion inicial),
  - `/citizen/concerns` (packs/preocupaciones),
  - `/citizen/case/:topic_id` (caso recomendado),
  - `/citizen/result` (decision accionable).
- Botones/controles:
  - `Aplicar pack`, `Elegir preocupacion`, `Abrir caso recomendado`,
  - `Yo: a favor`, `Yo: en contra`, `Guardar decision`.
- Interacciones:
  - quick path con progreso `0/4 -> 4/4`,
  - bloqueo de pasos no cumplidos,
  - CTA de "siguiente mejor accion".
- Charts:
  - bar comparativa por partido (senal util),
  - indicador de comparabilidad (badge semaforo).
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-01]` denominador comun por caso/partido,
  - `[URGENT TODO][DATA-P0-02]` linaje minimo para resultado final.

### F-02 - Ciudadania de respuesta rapida - Comparar partidos en un caso concreto
- Pantallas:
  - `/citizen/case/:topic_id`,
  - `/citizen/case/:topic_id/compare`.
- Botones/controles:
  - `Ver todo`, `Ordenar por comparabilidad`, `Abrir evidencia`, `Exportar tarjeta`.
- Interacciones:
  - ordenar/sort sin perder denominador fijo,
  - hover de definiciones (`cobertura`, `confianza`, `unknown`),
  - focus party persistente.
- Charts:
  - barra dual: `senal util` y `peso relativo`,
  - mini heatmap de match/mismatch vs postura personal.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-01]` comparable flags y ratio por partido,
  - `[URGENT TODO][DATA-P0-02]` evidencia enlazada por fila de comparativa.

### F-03 - Ciudadania esceptica - Verificar cualquier resumen con evidencia primaria
- Pantallas:
  - `/citizen/audit/:topic_id/:party_id`,
  - `/explorer/trace/:trace_id`.
- Botones/controles:
  - `Ver linaje`, `Abrir evidencia SQL`, `Abrir fuente original`, `Marcar verificado`.
- Interacciones:
  - panel de linaje expandible por capas,
  - breadcrumbs metrica -> fila -> fuente,
  - registro local de veredicto.
- Charts:
  - waterfall de transformaciones (raw -> evidence -> position),
  - tabla de evidencia con filtros por tipo/fecha.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-02]` contrato de linaje completo,
  - `[URGENT TODO][DATA-P0-11]` traza KPI -> query exacta.

### F-04 - Ciudadania esceptica - Entender y reducir incertidumbre
- Pantallas:
  - `/citizen/uncertainty/:topic_id`,
  - `/citizen/uncertainty/actions`.
- Botones/controles:
  - `Desglosar unknown`, `Ver causas`, `Priorizar casos`, `Seguir evolucion`.
- Interacciones:
  - drilldown causa -> filas impactadas,
  - filtro por impacto estimado en incertidumbre,
  - comparacion contra snapshot previo.
- Charts:
  - stacked bar `unknown` (`no_signal`, `unclear`, `mixed`),
  - tendencia temporal de incertidumbre.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-03]` dataset de explainability por causa,
  - `[URGENT TODO][DATA-P0-04]` diff temporal por snapshot.

### F-05 - Ciudadania que comparte - Compartir vista reproducible y segura
- Pantallas:
  - `/citizen/share-preview`,
  - modal `share`.
- Botones/controles:
  - `Generar enlace`, `Copiar`, `Abrir preview`, `Excluir preferencias`.
- Interacciones:
  - preview de payload compartido,
  - validacion de hash canonico,
  - aviso de privacidad explicito.
- Charts:
  - no obligatorio; chip resumen de estado compartido.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-12]` artefacto de permalink con checksum snapshot,
  - `[URGENT TODO][DATA-P0-17]` auditoria de que no se filtran preferencias sensibles.

### F-06 - Ciudadania que comparte - Consumir enlace y validar vigencia
- Pantallas:
  - `/citizen/shared`,
  - `/citizen/shared/diff`.
- Botones/controles:
  - `Comparar con ultimo snapshot`, `Mantener vista original`, `Actualizar`.
- Interacciones:
  - restore de estado exacto,
  - banner de drift si hay cambios,
  - fork de enlace.
- Charts:
  - diff card `antes vs ahora`,
  - contador de cambios materiales.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-04]` feed de diff snapshot,
  - `[URGENT TODO][DATA-P0-12]` metadatos de snapshot en enlace.

### F-07 - Usuario de leaderboards - Testear hipotesis con guardrails
- Pantallas:
  - `/citizen/leaderboards`,
  - `/citizen/leaderboards/:hypothesis_id/config`.
- Botones/controles:
  - `Ejecutar hipotesis`, `Aplicar umbral`, `Activar shrinkage`, `Guardar resultado`.
- Interacciones:
  - recalculo en vivo al cambiar umbrales,
  - bloqueo de ranking para filas no elegibles,
  - panel de sensibilidad.
- Charts:
  - ranking bar chart,
  - tornado/sensitivity chart.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-05]` motor robusto de ranking + sensibilidad,
  - `[URGENT TODO][DATA-P0-01]` comparables por fila.

### F-08 - Usuario de leaderboards - Auditar resultado de ranking
- Pantallas:
  - `/citizen/leaderboards/:hypothesis_id/result`,
  - `/citizen/leaderboards/:hypothesis_id/evidence`.
- Botones/controles:
  - `Abrir celdas comparables`, `Ver SQL`, `Exportar cita`.
- Interacciones:
  - click celda -> subset exacto,
  - pivot por partido/tema,
  - descarga bundle de evidencia.
- Charts:
  - heatmap de contribucion por tema/partido,
  - tabla trazable exportable.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-11]` traza completa de calculo,
  - `[URGENT TODO][DATA-P0-05]` componentes de score auditables.

### F-09 - Analista de politicas - Analisis `dice vs hace`
- Pantallas:
  - `/explorer-temas/analysis`,
  - `/explorer-temas/coherence`.
- Botones/controles:
  - `Metodo: votes/declared/combined`, `Aplicar filtros`, `Exportar`.
- Interacciones:
  - filtros por scope/periodo/high-stakes,
  - comparador side-by-side entre metodos,
  - persistencia de query state.
- Charts:
  - coherence matrix,
  - mismatch trend line.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-02]` versionado consistente de metodos,
  - `[URGENT TODO][DATA-P0-04]` temporalidad por snapshot.

### F-10 - Analista de politicas - Briefing tematico auditable
- Pantallas:
  - `/briefings/new`,
  - `/briefings/:id/editor`,
  - `/briefings/:id/export`.
- Botones/controles:
  - `Generar borrador`, `Adjuntar evidencia`, `Validar neutralidad`, `Exportar`.
- Interacciones:
  - composicion asistida por evidencia,
  - checklist de trazabilidad obligatorio,
  - preview antes de export.
- Charts:
  - small multiples por tema,
  - distribution chart de stance/unknown.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-11]` referencias trazables por afirmacion,
  - `[URGENT TODO][DATA-P0-13]` plantilla reproducible de anexos tecnicos.

### F-11 - Monitor legislativo - Seguir actividad relevante
- Pantallas:
  - `/explorer-votaciones/feed`,
  - `/explorer-votaciones/event/:event_id`.
- Botones/controles:
  - `Crear watchlist`, `Seguir tema`, `Seguir partido`, `Guardar evento`.
- Interacciones:
  - feed cronologico filtrable,
  - resumen rapido + detalle en panel lateral,
  - estado leido/no leido.
- Charts:
  - timeline de eventos,
  - stacked breakdown por resultado de voto.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-06]` feed de watchlist y suscripciones,
  - `[URGENT TODO][DATA-P0-02]` links completos evento -> evidencia.

### F-12 - Monitor legislativo - Detectar cambios de postura
- Pantallas:
  - `/explorer-votaciones/shifts`,
  - `/explorer-votaciones/shifts/:actor_id`.
- Botones/controles:
  - `Calcular cambios`, `Configurar ventana`, `Ver before/after`, `Crear alerta`.
- Interacciones:
  - slider de ventana temporal,
  - explicacion de comparabilidad del cambio,
  - dismiss/confirm alerta.
- Charts:
  - slope chart de cambios,
  - confidence band por deteccion.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-07]` modelo longitudinal de shifts,
  - `[URGENT TODO][DATA-P0-06]` alerting feed.

### F-13 - Explorador territorial - Encontrar actores por territorio
- Pantallas:
  - `/explorer-politico/search`,
  - `/explorer-politico/territory/:territory_code`.
- Botones/controles:
  - `Buscar territorio`, `Nivel territorial`, `Solo activos`, `Abrir ficha`.
- Interacciones:
  - autocompletado territorio,
  - filtros combinados (nivel, partido, rol),
  - cambios de vista individual/agregado.
- Charts:
  - mapa territorial clickable,
  - leaderboard de densidad representativa.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-08]` normalizacion robusta de territorio/persona/mandato,
  - `[URGENT TODO][DATA-P0-01]` cobertura por territorio para evitar sesgo.

### F-14 - Explorador territorial - Entender trayectoria de actor
- Pantallas:
  - `/explorer-politico/person/:person_id`,
  - modal `historial`.
- Botones/controles:
  - `Ver timeline`, `Filtrar por periodo`, `Ver votaciones asociadas`, `Exportar`.
- Interacciones:
  - timeline zoom (anio/legislatura),
  - jump a eventos clave,
  - comparacion rol actual vs historico.
- Charts:
  - timeline chart de mandatos/cargos,
  - sankey partido/rol (opcional).
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-08]` modelo de trayectoria consolidado,
  - `[URGENT TODO][DATA-P0-02]` enlaces a evidencia por hito.

### F-15 - Operador de calidad - Priorizar backlog por impacto
- Pantallas:
  - `/explorer-sources/ops`,
  - `/explorer-sources/issues/:issue_id`.
- Botones/controles:
  - `Recalcular prioridades`, `Abrir runbook`, `Marcar mitigado`, `Registrar evidencia`.
- Interacciones:
  - orden automatico por score impacto,
  - filtros por dominio/fuente/estado,
  - asignacion de owner.
- Charts:
  - bubble chart impacto vs esfuerzo,
  - burnup de issues mitigados.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-09]` scoring operacional estandarizado,
  - `[URGENT TODO][DATA-P0-16]` SLA operativo por issue.

### F-16 - Operador de calidad - Gestionar bloqueos externos
- Pantallas:
  - `/explorer-sources/blockers`,
  - `/explorer-sources/blockers/new`.
- Botones/controles:
  - `Ejecutar probe estricto`, `Adjuntar log`, `Crear incidente`, `Programar reintento`.
- Interacciones:
  - wizard de incidente con evidencia obligatoria,
  - policy de no-loop,
  - estado append-only con resolucion.
- Charts:
  - timeline de bloqueos por institucion,
  - tasa de bloqueo por fuente.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-10]` ledger de incidentes bloqueantes,
  - `[URGENT TODO][DATA-P0-09]` impacto ciudadano del bloqueo.

### F-17 - Power user SQL - Auditoria de metrica a fuente
- Pantallas:
  - `/explorer/sql-trace`,
  - `/explorer/sql-trace/:trace_id`.
- Botones/controles:
  - `Mostrar SQL`, `Ver FKs`, `Abrir evidencia`, `Abrir source_url`.
- Interacciones:
  - expand/collapse de steps de pipeline,
  - navegación jerarquica KPI -> rows -> source,
  - snapshot pinning.
- Charts:
  - DAG de dependencia de tablas,
  - tabla de trace steps con latencia.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-11]` manifiesto de trazas por metrica,
  - `[URGENT TODO][DATA-P0-17]` firma de integridad de query usada.

### F-18 - Power user SQL - Analisis custom reproducible
- Pantallas:
  - `/explorer/query-lab`,
  - `/explorer/query-artifacts/:artifact_id`.
- Botones/controles:
  - `Run`, `Guardar query`, `Generar permalink`, `Exportar CSV/Parquet`.
- Interacciones:
  - history local + versionado,
  - comparacion resultados A/B,
  - advertencia de query no determinista.
- Charts:
  - preview chart automatico segun schema,
  - stats panel (rows, nulls, cardinalidad).
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-12]` artefacto de query compartible,
  - `[URGENT TODO][DATA-P0-04]` comparacion entre snapshots.

### F-19 - Colaborador externo HF - Reproducir numeros publicados
- Pantallas:
  - `/hf-repro/start`,
  - `/hf-repro/report`.
- Botones/controles:
  - `Descargar manifest`, `Ejecutar notebook`, `Subir reporte`.
- Interacciones:
  - wizard de replica paso a paso,
  - validacion automatica de checksums,
  - semaforo pass/fail.
- Charts:
  - diff chart KPI publicado vs recalculado,
  - tabla de checks reproducibilidad.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-13]` kit publico de replica,
  - `[URGENT TODO][DATA-P0-17]` manifest firmado de release.

### F-20 - Colaborador externo HF - Comparar snapshots
- Pantallas:
  - `/hf-repro/diff`,
  - `/hf-repro/diff/:snapshot_a/:snapshot_b`.
- Botones/controles:
  - `Seleccionar A/B`, `Calcular diff`, `Exportar changelog`.
- Interacciones:
  - filtros por tabla/metrica,
  - drilldown a filas afectadas,
  - anotacion de causa probable.
- Charts:
  - waterfall de variacion de metricas,
  - top changes table.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-14]` generador de changelog tecnico,
  - `[URGENT TODO][DATA-P0-04]` feed estructurado de diff.

### F-21 - Worker MTurk - Etiquetar evidencia ambigua
- Pantallas:
  - `/review/mturk/task/:task_id`,
  - `/review/mturk/submit`.
- Botones/controles:
  - radio `support/oppose/mixed/unclear/no_signal`,
  - `Confianza`, `Enviar`.
- Interacciones:
  - validacion de campos obligatorios,
  - bloqueo si no hay nota,
  - timer y control de calidad basico.
- Charts:
  - no requerido en tarea; progreso de lote opcional.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-15]` telemetria de calidad por tarea/worker,
  - `[URGENT TODO][DATA-P0-16]` aging por lote para priorizacion.

### F-22 - Worker MTurk - Mantener calidad y throughput
- Pantallas:
  - `/review/mturk/worker-dashboard`.
- Botones/controles:
  - `Ver feedback`, `Reintentar gold`, `Pausar lote`.
- Interacciones:
  - feedback casi en tiempo real,
  - alertas de drift de calidad,
  - sugerencia de foco por tipo de tarea.
- Charts:
  - accuracy trend,
  - disagreement distribution.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-15]` scoring de calidad por worker,
  - `[URGENT TODO][DATA-P0-16]` metrica throughput/sla.

### F-23 - Revisor interno - Resolver desacuerdos
- Pantallas:
  - `/review/adjudication/queue`,
  - `/review/adjudication/item/:evidence_id`.
- Botones/controles:
  - `Resolver`, `Ignorar`, `Aplicar lote`, `Recomputar`.
- Interacciones:
  - compare panel workers vs evidencia,
  - nota obligatoria por decision,
  - bulk actions por stance.
- Charts:
  - queue composition chart por `review_reason`.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-16]` cola priorizada por impacto/edad,
  - `[URGENT TODO][DATA-P0-02]` lineage post-adjudicacion.

### F-24 - Revisor interno - Mantener SLA de cola
- Pantallas:
  - `/review/adjudication/sla`.
- Botones/controles:
  - `Generar batch`, `Asignar lote`, `Cerrar ciclo`.
- Interacciones:
  - deteccion automatica de SLA breach,
  - simulacion de capacidad necesaria,
  - cierre de ciclo con evidencia.
- Charts:
  - aging histogram,
  - throughput vs backlog line chart.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-16]` contrato SLA completo,
  - `[URGENT TODO][DATA-P0-09]` impacto de backlog en calidad ciudadana.

### F-25 - Maintainer/Release owner - Publicacion segura
- Pantallas:
  - `/release/checklist`,
  - `/release/preview`,
  - `/release/publish`.
- Botones/controles:
  - `Run privacy gate`, `Run quality gates`, `Build`, `Publish`.
- Interacciones:
  - secuencia bloqueante de gates,
  - evidencias adjuntas por gate,
  - rollback plan visible antes de publicar.
- Charts:
  - gate status board (ok/degraded/failed),
  - release diff summary.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-17]` trail de auditoria de gates,
  - `[URGENT TODO][DATA-P0-14]` resumen de cambios para release notes.

### F-26 - Maintainer/Release owner - Respuesta a incidentes
- Pantallas:
  - `/incidents`,
  - `/incidents/:incident_id`,
  - `/incidents/new`.
- Botones/controles:
  - `Abrir incidente`, `Clasificar severidad`, `Aplicar rollback`, `Cerrar incidente`.
- Interacciones:
  - timeline con decisiones y evidencias,
  - asignacion de owner y ETA,
  - postmortem obligatorio al cierre.
- Charts:
  - incident timeline,
  - mttr trend y recurrencia.
- Datos (URGENT TODO):
  - `[URGENT TODO][DATA-P0-18]` bundle estandar de incidente,
  - `[URGENT TODO][DATA-P0-17]` enlace a gates/releases afectadas.

## 3) Priorizacion de implementacion recomendada (delivery)

1. Pista ciudadana critica: `F-01`, `F-02`, `F-03`, `F-04`, `F-07`, `F-08`.
2. Pista de auditabilidad tecnica: `F-09`, `F-11`, `F-17`, `F-18`.
3. Pista de operacion y confiabilidad: `F-15`, `F-16`, `F-25`, `F-26`.
4. Pista de workflows humanos: `F-21`, `F-22`, `F-23`, `F-24`.
5. Pista de colaboracion externa: `F-19`, `F-20`.

## 4) Definition of Done para cada flujo

1. Pantallas renderizan en desktop y mobile sin perdida de informacion critica.
2. Botones principales tienen texto claro, estado disabled/loading y confirmacion cuando aplica.
3. Interacciones clave dejan evidencia observable (eventos de producto o logs auditables).
4. Charts muestran comparabilidad/uncertainty cuando aplique, nunca solo score "magico".
5. Todos los `URGENT TODO` asociados al flujo tienen owner y fecha objetivo.

