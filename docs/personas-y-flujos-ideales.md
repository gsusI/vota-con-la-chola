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

## 1.1) Personas prioritarias con identidad

Estas seis personas concretan el north-star para decisiones de producto, UX y priorizacion. No sustituyen la tabla anterior: la vuelven operativa para las rutas y tradeoffs que mas valor aportan hoy.

### Alba Moreno - Ciudadania de respuesta rapida

- Mapa: `Ciudadania de respuesta rapida`.
- Flujos clave: `F-01`, `F-02`, `F-05`.
- Identidad: 29 años, administrativa en Malaga, sigue la politica lo justo y llega a la plataforma desde movil cuando una conversacion o un titular le obliga a tomar postura.
- Jobs-to-be-done: decidir rapido sobre vivienda, coste de vida o sanidad; comparar partidos sobre un caso concreto sin leer veinte paginas.
- Momento activador: ve un enlace compartido o entra dias antes de votar porque quiere una respuesta util en menos de cinco minutos.
- Exito: sale con una decision provisional clara, entiende que partidos son comparables en ese caso y puede guardar o compartir la vista.
- Curiosidades que podria encontrar: que un partido habla mucho de vivienda pero apenas tiene senal util en los casos comparables; que dos partidos que ella daba por iguales divergen mucho en un tema concreto; que el caso mas util para decidir no es el mas mediatico.
- Curiosidades de alto interes y potencial viral:
  - que el partido que mas habla de alquiler casi no tiene senal comparable cuando se mira precio, desahucio o parque publico por separado.
  - que dos partidos que su entorno trata como casi iguales votan distinto justo en una medida muy cotidiana, como IVA reducido, dependencia o transporte.
  - que el partido que mejor le sale en `combined` cae mucho cuando cambia a `votes`, y el que parecia flojo sube.
  - que una preocupacion menos mediatica, como plazas PMR, cliente financiero o ayudas a suministros, separa mas a los partidos que vivienda o sanidad en general.
  - que el caso que mas cambia su decision no es una gran ley, sino una votacion pequena con impacto muy directo en bolsillo o servicios.
- Necesita confiar en: lenguaje directo, badges claros de comparabilidad, y una evidencia representativa accesible sin cambiar de contexto.
- Se frustra cuando: la UI mezcla promedios con casos concretos, hay demasiados terminos metodologicos al principio, o no queda claro por que un partido sale mejor o peor.
- El producto no debe: pedirle una curva de aprendizaje de analista ni esconder la incertidumbre detras de una respuesta falsa de alta confianza.

### Sergio Llorente - Ciudadania esceptica en modo auditoria

- Mapa: `Ciudadania esceptica (modo auditoria)`.
- Flujos clave: `F-03`, `F-04`, `F-17`.
- Identidad: 41 años, profesor de instituto en Zaragoza, desconfia de rankings civicos y solo acepta un resumen si puede bajar de la tarjeta a la fuente original.
- Jobs-to-be-done: comprobar si una postura agregada esta bien fundada; entender si `unknown` significa falta de datos, conflicto real o una decision metodologica debil.
- Momento activador: detecta una afirmacion fuerte en citizen o en un enlace compartido y quiere desmontarla o validarla por su cuenta.
- Exito: puede recorrer metrica -> evidencia -> fuente sin perderse, y termina con un veredicto propio de verificado, dudoso o insuficiente.
- Curiosidades que podria encontrar: cuantos resumenes descansan en `votes` frente a `declared`; por que un `unknown` viene de `no_signal` y no de conflicto; que una conclusion aparentemente solida cambia mucho al mirar cobertura real.
- Curiosidades de alto interes y potencial viral:
  - que un ranking muy compartido descansa en solo `2` o `3` temas comparables y cambia por completo al subir un poco el umbral de cobertura.
  - que un `unknown` enorme no significa falta total de datos, sino una mezcla muy concreta de `mixed`, `unclear` y texto no comparable.
  - que una postura presentada como firme viene casi toda de `declared` y apenas tiene respaldo en `votes`.
  - que dos tarjetas opuestas del mismo partido salen del mismo expediente porque una usa texto previo y otra texto votado posterior.
  - que una diferencia muy vistosa entre partidos se explica por un solo caso con peso desproporcionado.
- Necesita confiar en: linaje visible, fechas, metodo usado, cobertura y acceso inmediato a `source_url` o drill-down equivalente.
- Se frustra cuando: la trazabilidad queda escondida, el sistema usa etiquetas cerradas sin explicar la cobertura, o `unknown` se trata como ruido sin causa.
- El producto no debe: obligarle a confiar en copy interpretativo ni impedirle reconstruir la conclusion con sus propios criterios.

### Irene Campos - Analista de politicas tematicas

- Mapa: `Analista de politicas (Temas)`.
- Flujos clave: `F-09`, `F-10`, `F-18`.
- Identidad: 35 años, consultora de politicas publicas en Madrid, trabaja con briefs y necesita separar lo que es robusto de lo que solo parece una buena historia.
- Jobs-to-be-done: ejecutar analisis `dice vs hace` por tema y scope; producir un briefing auditable con deltas, unknown y evidencia enlazada.
- Momento activador: recibe un encargo sobre un tema concreto, por ejemplo vivienda o energia, y necesita una base reproducible antes de redactar conclusiones.
- Exito: obtiene tablas exportables, puede filtrar por metodo y cobertura, y cada afirmacion relevante queda respaldada por evidencia primaria.
- Curiosidades que podria encontrar: en que temas `declared` y `votes` chocan mas; que partidos tienen mucha visibilidad pero poca base comparable; que subtemas concentran la mayor parte de incoherencias o `unknown`.
- Curiosidades de alto interes y potencial viral:
  - que la mayor incoherencia de un partido no esta en el tema macro de su discurso, sino en un subtema pequeno que se repite mucho en votaciones concretas.
  - que un partido parece coherente en vivienda hasta que se separan alquiler, desahucio, fiscalidad y suelo.
  - que el choque mas fuerte entre `declared` y `votes` se concentra en una sola familia de iniciativas, no en el tema entero.
  - que el partido con mas visibilidad publica sobre un asunto es tambien el que peor denominador comparable tiene.
  - que la mitad de un briefing aparentemente robusto depende de muy pocos casos con evidencia fuerte, mientras el resto es `unknown` o cobertura fragil.
- Necesita confiar en: versionado de metodo, filtros por scope/periodo, comparabilidad visible y posibilidad real de exportar datos y referencias.
- Se frustra cuando: el sistema mezcla `votes`, `declared` y `combined` sin explicar precedencia, o no puede aislar un subconjunto defensible.
- El producto no debe: empujarla a un ranking unico ni dejar que una narrativa tape la falta de muestra o la baja cobertura.

### Oscar Vidal - Monitor legislativo

- Mapa: `Monitor legislativo (Votaciones)`.
- Flujos clave: `F-11`, `F-12`.
- Identidad: 38 años, periodista freelance en Valencia, sigue varias instituciones a la vez y necesita detectar movimientos relevantes antes de que la conversacion publica se cierre.
- Jobs-to-be-done: vigilar actividad parlamentaria por tema, partido e institucion; detectar posibles cambios de postura con suficiente contexto para publicar o investigar.
- Momento activador: se abre una sesion relevante o una watchlist marca un evento nuevo que puede alterar una historia en curso.
- Exito: identifica rapido que paso, quienes se movieron, y si el aparente cambio de postura es comparable o un falso positivo por contexto distinto.
- Curiosidades que podria encontrar: que una iniciativa menor explica mejor una fractura interna que una gran votacion mediatica; que ciertos partidos cambian mas por tipo de procedimiento que por tema; que algunos eventos concentran mucha actividad pero muy poca claridad sustantiva.
- Curiosidades de alto interes y potencial viral:
  - que la votacion que mejor revela una fractura interna no es el pleno estrella, sino una enmienda o toma en consideracion casi invisible.
  - que un mismo partido parece girar en una semana, pero el supuesto giro desaparece al comparar version de texto y procedimiento correctos.
  - que Congreso y Senado cuentan historias distintas sobre el mismo asunto y el conflicto real esta en la cadena iniciativa -> texto -> voto.
  - que una iniciativa con casi nula cobertura mediatica anticipa mejor una ruptura futura que las votaciones mas comentadas.
  - que un evento con muchisimos votos emitidos produce poquisima claridad sustantiva porque casi todo el valor esta en el contexto procedimental.
- Necesita confiar en: feeds claros, linking voto -> iniciativa, ventanas temporales consistentes y explicacion de nivel de confianza en cualquier flip detectado.
- Se frustra cuando: los eventos llegan sin contexto, los enlaces a iniciativas fallan o la deteccion de cambios confunde votos sobre textos no equivalentes.
- El producto no debe: vender como giro politico lo que solo es ruido procedimental o falta de normalizacion sustantiva.

### Nadia Ferrer - Operadora de calidad de datos

- Mapa: `Operador de calidad de datos (Fuentes y Calidad)`.
- Flujos clave: `F-15`, `F-16`, `F-24`.
- Identidad: 33 años, ingeniera de datos en Barcelona, vive entre conectores, quality gates y bloqueos de fuentes oficiales; mide su trabajo por impacto ciudadano real, no por volumen de logs.
- Jobs-to-be-done: priorizar backlog tecnico segun dano visible en producto; registrar bloqueos externos con evidencia y evitar ciclos inutiles de reintento.
- Momento activador: cae una fuente, baja una cobertura clave o una area de citizen empieza a mostrar mas `unknown` del aceptable.
- Exito: sabe que issue arreglar primero, deja evidencia publica verificable cuando algo externo bloquea, y puede demostrar mejora en KPI o cobertura tras el fix.
- Curiosidades que podria encontrar: que una sola fuente bloqueada hunde un concern entero en citizen; que pequenos fixes de linking cambian mucho mas la utilidad publica que grandes backfills; que algunos bloqueos externos afectan mas a la confianza que al volumen de filas.
- Curiosidades de alto interes y potencial viral:
  - que un solo `linker` roto explica mas dano ciudadano visible que varios conectores grandes en rojo.
  - que una fuente bloqueada no baja mucho el total de filas, pero deja ciego justo el concern pack mas compartible en citizen.
  - que un fix de `text versioning` cambia mas tarjetas publicas que una semana entera de scraping nuevo.
  - que la peor incidencia no borra datos: dispara falsos `unknown` en partidos que antes eran comparables.
  - que un bloqueo externo pequeno en apariencia altera mas la confianza publica que una caida tecnica grande pero contenida.
- Necesita confiar en: paneles de impacto, runbooks claros, incidentes append-only y una relacion directa entre calidad tecnica y dano en flujos de usuario.
- Se frustra cuando: el backlog tecnico no distingue ruido de problemas con efecto en producto, o se repiten probes sin un lever nuevo.
- El producto no debe: empujarla a marcar falso DONE, esconder bloqueos externos o separar demasiado la salud del ETL de la experiencia ciudadana.

### Tomas Rivas - Maintainer y release owner

- Mapa: `Maintainer / release owner`.
- Flujos clave: `F-25`, `F-26`, `F-19`.
- Identidad: 44 años, responsable tecnico del proyecto en Sevilla, piensa en snapshots, privacidad, publicacion estatica y reputacion publica del sistema como un solo problema.
- Jobs-to-be-done: publicar artefactos seguros y reproducibles; responder a incidentes o regresiones con evidencia, no con improvisacion.
- Momento activador: toca release, aparece una regresion en rutas publicas o falla un gate de privacidad, integridad o calidad.
- Exito: puede ejecutar el checklist, validar artefactos publicos, publicar GH Pages y snapshot externo, y dejar un rastro claro de lo que cambio.
- Curiosidades que podria encontrar: que un cambio pequeño en export rompe varias rutas publicas a la vez; que un snapshot nuevo mejora mucho la explicabilidad pero no la cobertura; que las regresiones mas caras no siempre vienen de ETL sino de publish, routing o contratos estaticos.
- Curiosidades de alto interes y potencial viral:
  - que un cambio minusculo en naming de artefactos rompe a la vez citizen, explorer y rutas legacy sin tocar el ETL.
  - que una release mejora mucho la explicabilidad visible pero deja exactamente igual la cobertura real del snapshot.
  - que el incidente mas caro de una semana viene de publish o routing estatico, no de ingesta ni base de datos.
  - que una fuga potencial no sale de contenido politico sino de una ruta local o un artefacto tecnico mal sanitizado.
  - que `main` y la superficie publica parecen sincronizados, pero un solo companion file viejo cambia lo que ve el usuario final.
- Necesita confiar en: gates automaticos, manifests legibles, artefactos comparables entre snapshots y evidencia suficiente para decidir rollback, hotfix o bloqueo documentado.
- Se frustra cuando: la publicacion depende de pasos ambiguos, hay riesgo de filtrar datos sensibles o los cambios de producto no llegan acompanados de validacion reproducible.
- El producto no debe: exigir memoria tribal para publicar ni permitir que una release rompa trazabilidad, privacidad o sincronizacion entre `main` y la superficie publica.

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
