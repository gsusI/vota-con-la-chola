# Actores, Objetivos y Flujos Ideales (North Star)

Estado: `v1`  
Alcance: este documento define flujos ideales de producto, **independientes** de si hoy existen o no en la UI/ETL actual.

Companion de implementacion UX:
- `docs/flujos-ui-especificacion.md` (detalle por flujo: pantallas, controles, interacciones, charts y necesidades de datos `URGENT TODO`).

## 1) Actores/Personas y objetivos

| Persona | Objetivo 1 | Objetivo 2 |
|---|---|---|
| Ciudadania de respuesta rapida | Decidir en menos de 5 minutos sobre una preocupacion concreta | Comparar partidos en un caso concreto sin confusion de comparabilidad |
| Ciudadania esceptica (modo auditoria) | Verificar cualquier resumen con evidencia primaria | Entender y reducir incertidumbre (`unknown/no_signal`) |
| Ciudadania que comparte | Compartir una vista reproducible y segura | Consumir un enlace compartido y validar si sigue vigente |
| Usuario de leaderboards civicos | Testear hipotesis publicas con guardrails de muestra | Auditar por que un ranking da ese resultado |
| Analista de politicas (Temas) | Ejecutar analisis `dice vs hace` por tema/scope | Producir briefing tematico auditable |
| Monitor legislativo (Votaciones) | Seguir actividad parlamentaria relevante | Detectar cambios de postura relevantes en el tiempo |
| Explorador territorial (Radar politico) | Encontrar actores por territorio/nivel/partido | Entender la trayectoria de un actor concreto |
| Operador de calidad de datos (Fuentes y Calidad) | Priorizar backlog tecnico por impacto ciudadano | Gestionar bloqueos externos con trazabilidad publica |
| Power user SQL / investigador tecnico | Auditar de metrica a fila y fuente original | Ejecutar analisis custom reproducible por snapshot |
| Colaborador externo de datos (HF/snapshots) | Reproducir numeros publicados sin acceso interno | Comparar snapshots y detectar cambios significativos |
| Worker de revision manual (crowd/MTurk) | Etiquetar evidencia ambigua con contrato estricto | Mantener calidad y throughput sostenido |
| Revisor interno / adjudicador | Resolver desacuerdos y cerrar cola pendiente | Mantener SLA de revision y salud de cola |
| Maintainer / release owner | Publicar artefactos publicos con gates de privacidad/calidad | Responder a incidentes/regresiones con evidencia |

## 2) Flujos ideales por persona y objetivo

Formato: `F-XX - Persona - Objetivo`.

### F-01 - Ciudadania de respuesta rapida - Decidir en menos de 5 minutos
1. Entra desde home o enlace compartido.
2. Selecciona una preocupacion o pack sugerido.
3. El sistema propone 1-3 casos de alta comparabilidad.
4. Marca postura personal para el caso seleccionado.
5. Recibe una lectura accionable por partido con badge de comparabilidad.
6. Guarda decision local o la comparte.

### F-02 - Ciudadania de respuesta rapida - Comparar partidos en un caso concreto
1. Abre un caso concreto (no promedio agregado).
2. La UI fija denominador comun para todos los partidos.
3. Muestra postura, senal util y peso relativo por partido.
4. Permite abrir una evidencia representativa por partido en un click.
5. Exporta tarjeta comparativa simple (visual + link de auditoria).

### F-03 - Ciudadania esceptica - Verificar cualquier resumen con evidencia primaria
1. Hace click en un chip de postura/confianza.
2. Abre panel de linaje (metodo, cobertura, fecha, quality flags).
3. Baja a filas de evidencia para ese resumen.
4. Abre fuente original y valida contexto.
5. Marca veredicto local: verificado, dudoso o insuficiente.

### F-04 - Ciudadania esceptica - Entender y reducir incertidumbre
1. Hace click en `unknown`.
2. Ve descomposicion `no_signal`, `unclear`, `mixed`.
3. Ve causa principal y recomendacion accionable.
4. Salta a items con mayor impacto en incertidumbre.
5. Revisa si la incertidumbre baja en snapshot siguiente.

### F-05 - Ciudadania que comparte - Compartir vista reproducible y segura
1. Pulsa `Compartir`.
2. Previsualiza que estado se incluye (y que no).
3. Genera URL con snapshot + estado, via fragment.
4. Copia y envia enlace.
5. Receptor abre exactamente la misma vista.

### F-06 - Ciudadania que comparte - Consumir enlace y validar vigencia
1. Abre enlace compartido.
2. Carga estado exacto del enlace.
3. Compara con snapshot mas reciente.
4. Ve delta de cambios y posibles impactos.
5. Puede bifurcar a su propia version compartible.

### F-07 - Usuario de leaderboards - Testear hipotesis con guardrails
1. Selecciona una hipotesis predefinida.
2. Configura umbral de comparables y robustez (shrinkage).
3. Ejecuta ranking solo con filas elegibles.
4. Ajusta sensibilidad y observa estabilidad.
5. Guarda resultado con metadata metodologica.

### F-08 - Usuario de leaderboards - Auditar resultado de ranking
1. Click en una celda/rank.
2. Abre subconjunto comparable exacto usado por la metrica.
3. Inspecciona partidos/temas que explican el valor.
4. Navega a evidencia SQL/fuente.
5. Exporta cita reproducible (query + snapshot + links).

### F-09 - Analista de politicas - Analisis `dice vs hace`
1. Define scope temporal e institucional.
2. Selecciona metodos (`votes`, `declared`, `combined`).
3. Ejecuta metrica de coherencia con incertidumbre explicita.
4. Filtra por high-stakes y cobertura minima.
5. Descarga tabla tecnica + grafico + supuestos.

### F-10 - Analista de politicas - Briefing tematico auditable
1. Selecciona topic set y temas objetivo.
2. Genera resumen por actor/partido con deltas y unknown.
3. Adjunta evidencia top por afirmacion.
4. Revisa lenguaje y neutralidad.
5. Exporta briefing (markdown/pdf) con referencias.

### F-11 - Monitor legislativo - Seguir actividad relevante
1. Define watchlist de temas/partidos/instituciones.
2. Recibe feed de eventos nuevos.
3. Abre evento con contexto + resultado.
4. Revisa desglose por grupo y enlaces a iniciativa.
5. Guarda seguimiento o alerta para cambios.

### F-12 - Monitor legislativo - Detectar cambios de postura
1. Selecciona actor/partido y ventana temporal.
2. Sistema calcula cambios sobre eventos comparables.
3. Muestra posibles flips con nivel de confianza.
4. Permite ver antes/despues con evidencia.
5. Emite alerta suscribible o reporte puntual.

### F-13 - Explorador territorial - Encontrar actores por territorio
1. Ingresa municipio/codigo postal/territorio.
2. El sistema resuelve nivel territorial efectivo.
3. Lista representantes activos por institucion y partido.
4. Permite filtrar por rol, estado y fuente.
5. Abre ficha de actor o partido.

### F-14 - Explorador territorial - Entender trayectoria de actor
1. Abre perfil de persona.
2. Ve timeline de mandatos, partidos y cargos.
3. Ve huella tematica/votaciones asociadas.
4. Revisa cambios de afiliacion o rol.
5. Exporta timeline con evidencias.

### F-15 - Operador de calidad - Priorizar backlog por impacto
1. Abre panel operativo.
2. Ranking de issues por impacto usuario x severidad x frescura.
3. Selecciona issue y ejecuta runbook guiado.
4. Aplica fix o marca bloqueo con evidencia.
5. Registra delta de KPI y cierra loop.

### F-16 - Operador de calidad - Gestionar bloqueos externos
1. Ejecuta una sola prueba estricta reproducible.
2. Captura señal verificable (`403`, challenge, timeout patron).
3. Crea incidente publico append-only.
4. Define siguiente escalacion y criterio de reintento.
5. Publica estado real sin marcar falso DONE.

### F-17 - Power user SQL - Auditoria de metrica a fuente
1. Parte desde una metrica en UI.
2. Abre SQL/subconjunto exacto usado.
3. Recorre FKs hasta evidencia atomica.
4. Abre `source_url`/hash y valida.
5. Guarda consulta reproducible.

### F-18 - Power user SQL - Analisis custom reproducible
1. Elige snapshot/version.
2. Ejecuta query builder o SQL directo.
3. Guarda consulta con checksum de snapshot.
4. Genera permalink de resultados.
5. Exporta artefacto para terceros.

### F-19 - Colaborador externo HF - Reproducir numeros publicados
1. Descarga `latest.json` + manifest del snapshot.
2. Ejecuta notebook/plantilla oficial de replica.
3. Contrasta KPIs calculados vs publicados.
4. Reporta pass/fail de reproducibilidad.
5. Publica issue o PR con evidencia.

### F-20 - Colaborador externo HF - Comparar snapshots
1. Selecciona snapshot A/B.
2. Corre diff de esquema y metricas.
3. Inspecciona filas/materialidad del cambio.
4. Etiqueta causa probable (ingesta, mapeo, metodo).
5. Emite changelog tecnico.

### F-21 - Worker MTurk - Etiquetar evidencia ambigua
1. Recibe tarea con excerpt, topic y contexto minimo.
2. Aplica decision tree y taxonomia de labels.
3. Informa stance, confianza y nota breve.
4. Pasa validaciones de formato/calidad.
5. Envia tarea para agregacion.

### F-22 - Worker MTurk - Mantener calidad y throughput
1. Ve feedback de gold tasks y desacuerdos.
2. Ajusta ritmo y foco segun precision.
3. Prioriza tareas acorde a fortalezas.
4. Mantiene consistencia de notas y labels.
5. Cierra lote con calidad objetivo.

### F-23 - Revisor interno - Resolver desacuerdos
1. Abre cola priorizada por impacto y antiguedad.
2. Ve votos de workers + evidencia cruda.
3. Decide `resolved`/`ignored` con nota trazable.
4. Aplica lote al DB.
5. Lanza recomputo de posiciones derivadas.

### F-24 - Revisor interno - Mantener SLA de cola
1. Monitorea aging y volumen por `review_reason`.
2. Prepara siguiente batch con cupo optimo.
3. Repite loop preparar -> revisar -> aplicar.
4. Verifica que baja la cola accionable.
5. Reporta estado operativo.

### F-25 - Maintainer/Release owner - Publicacion segura
1. Ejecuta checklist de release.
2. Corre gates de privacidad/integridad/calidad.
3. Construye artefactos estaticos y snapshot externo.
4. Previsualiza y valida rutas publicas.
5. Publica GH Pages + HF + manifiestos.

### F-26 - Maintainer/Release owner - Respuesta a incidentes
1. Detecta alerta/regresion.
2. Triaga con runbook y evidencia.
3. Decide rollback, hotfix o bloqueo documentado.
4. Regenera y publica correccion.
5. Registra incidente y remediacion.

## 3) Requisitos transversales para cualquier flujo ideal

1. Evidencia primero: cualquier claim debe tener drill-down inmediato.
2. Incertidumbre explicita: nunca imputar silenciosamente.
3. Reproducibilidad fuerte: estado compartible + snapshot/version + checksum.
4. Comparabilidad visible: mostrar umbrales y elegibilidad muestral.
5. Privacidad por defecto: preferencias locales; share solo opt-in.
6. Trazabilidad E2E: de tarjeta/resumen a fila y fuente original.
7. Performance acotada: UX util con artefactos estaticos y payloads limitados.
8. Observabilidad de producto: eventos de embudo, auditoria y confianza.

## 4) Criterios de aceptacion (north-star)

1. Para cada persona existe al menos un flujo de decision y uno de auditoria/revision.
2. Cada flujo termina en un output verificable (decision, reporte, incidente o artefacto).
3. Ningun flujo depende de opacidad metodologica para ser util.
4. Cualquier resultado puede re-ejecutarse sobre el mismo snapshot y reproducirse.
