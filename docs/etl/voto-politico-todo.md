# TODO: Cobertura de votos por político (todos los niveles)

Objetivo del proyecto: poder evaluar tendencias de decisión de cada político comparando lo que declara públicamente con su comportamiento de voto.\

## Alcance funcional

1. Cada voto nominal debe quedar trazable desde:\
   - `evento de votación` -> `persona` -> `decisión`.
2. Cada decisión debe estar contextualizada por `tema/expediente` y `nivel territorial`.
3. Debe incluirse una capa estatal de referencia con **reales decretos** (BOE), para detectar coherencia entre voto parlamentario y aprobación/ratificación de normas.

## 1) Datos base obligatorios (Fase 1)

- [ ] Inventariar y priorizar fuentes de voto nominal por nivel con evidencia de reproducibilidad.
  - Criterio: fuente oficial + identificador estable + metadatos de evento (`vote_event_id` estable + fecha + sesión + tipo de votación).
- [ ] Congresos autonómicos: validar si el voto es nominal (si no hay nominal, clasificar explícitamente como no nominal).
  - Criterio mínimo: al menos 2 fuentes activas con histórico >=5 años cuando exista.
- [ ] UE: incorporar fuente nominal de votación por diputado europeo (si existe API estable para cada votación y voto).
  - Criterio mínimo: cobertura por legislatura en curso + una anterior.
- [ ] Municipal/local: registrar explícitamente ausencia de voto nominal por diseño institucional y documentar excepciones cuando exista.

## 2) Capa estatal por votación parlamentaria (Fase 2)

- [ ] Finalizar ciclo completo de `congreso_votaciones` (todas legislaturas objetivo).
  - Output: `parl_vote_events` y `parl_vote_member_votes` estables por corrida.
  - Criterio: `%eventos_enlazados_con_iniciativa` y `%votos_con_person_id` medibles en `quality-report`.
- [ ] Cerrar cobertura de `senado_votaciones` sin huecos de 403/HTML.
  - Output: estrategia documentada para sesiones de respaldo (archivos locales capturados legalmente).
  - Criterio: `events_reingested>0` en backfill incremental para legislaturas objetivo.
- [ ] Enlazar votos->iniciativas con alta prioridad de confianza:
  1. expediente estable
  2. referencia textual determinista
  3. emparejamiento editorial manual (solo revisión humana y trazable)
  - Evidencia: `parl_vote_event_initiatives` con `link_method` y `confidence`.
- [ ] Normalizar catálogo de campos y sinónimos de posiciones (SI/NO/ABST/EMP/ABS)

## 3) Reales decretos y marco jurídico estatal (Fase 3)

- [ ] Añadir conector BOE API / feed oficial para decretos estatales (prioridad: `real decreto`, `real decreto-ley`, `RD-L`, `RDL`), con:
  - `legal_doc_id` estable (`BOE-A-YYYY-NNNN` o equivalente oficial), fecha de publicación, materia, texto y enlace.
  - extracción incremental por fecha + deduplicación.
- [ ] Modelar en esquema tablas dedicadas (nuevo `leg_documents` o extensión en `source_records`/`parl_initiatives`) para no mezclar norma y votación.
- [ ] Vincular decreos a iniciativas/votaciones conocidas de Congreso y Senado mediante expediente, fecha-acto y referencia legal explícita cuando exista.
  - Criterio: trazabilidad por evidencia JSON (texto de referencia + match method).
- [ ] Añadir `legal_topic` y tags jerárquicos (educación, salud, fiscalidad, etc.) para análisis de contradicciones.

## 4) Cobertura multinivel/autonómica (Fase 4)

- [ ] Revisar cada parlamento autonómico con estrategia explícita:
  - si tiene actas o datasets nominals -> integrar
  - si no, marcar como `no-nominal` y cubrir solo agenda temática
- [ ] Priorizar conexiones con `territory_id` en mandatos para navegación por nivel y filtro de contradicción.
- [ ] Añadir contratos de consulta `--from-file` cuando haya WAF, con trazabilidad y receta en tracker.

## 5) Análisis de coherencia pública vs voto (Fase 5)

- [ ] Crear pipeline de ingestión de posicionamiento público (compromisos, votos de campaña, manifiestos, enmiendas presentadas).
- [ ] Definir `claim taxonomy` y `policy fields` compartidos con votación (salud, empleo, inmigración, fiscalidad, etc.).
- [ ] Implementar score base de consistencia:
  - apoyo previo -> voto contrario
  - apoyo en votación -> mensaje contradictorio
  - clasificar por confiabilidad del soporte de texto (fuente y fecha).
- [ ] Publicar vistas SQL o tabla `parl_consistency_signals` para UI/API.

## 6) Calidad, reproducibilidad y operaciones (Fase 6)

- [ ] Expandir `quality-report` con KPIs específicos por nivel:
  - `%eventos con person_id`
  - `%votos con evidencia legal asociada` (si aplica)
  - `%eventos con coverage legal`
- [ ] Añadir `--strict-network` con umbral duro por fuente nueva (votación/decreto).
- [ ] Añadir tracker entries y receta `just` por nueva superficie.
- [ ] Snapshot temporal mensual/quincenal para:
  - votos
  - enlaces a temas/leyes
  - señales de coherencia

## Lista sugerida de siguientes 10 pasos (para retomar hoy)

1. Cerrar la publicación de KPIs con corrida completa para `senado_votaciones` + `congreso_votaciones`.
2. Marcar en tracker el estado legal de `real decreto` y abrir conector BOE en rama `feat/legal-docs`.
3. Diseñar esquema mínimo `legal_documents` + `vote_event_legal_links` (aditivo).
4. Definir `field taxonomy` de temas y mapear a iniciativas actuales.
5. Agregar query inicial de contradicción por político + tema en SQL de reporting.
6. Priorizar una CCAA con voto nominal público y probar la integración piloto.
7. Unificar `source_id`/`territory_id` para filtro por nivel en Explorer.
8. Cerrar la semántica de votos no nominales.
9. Documentar procedimiento manual para sesiones bloqueadas (WAF/403).
10. Revisar riesgo de inferencia en claims públicos y anotar incertidumbre por señal.

## Estado operativo actual (actualización de trabajo)

- Fecha referencia interna: `2026-02-13`.
- KPIs con `quality-report --source-ids congreso_votaciones,senado_votaciones`:
  - `events_with_date_pct: 0.1862896` (objetivo: `>= 0.95`) ❌
  - `events_with_totals_pct: 0.1862896` (objetivo: `>= 0.95`) ❌
  - `events_with_theme_pct: 0.0469580` (objetivo: `>= 0.95`) ❌
  - `member_votes_with_person_id_pct: 0.9030027` ✅
- Cobertura residual de `senado_votaciones` sin detalle (evento sin fecha/totales):
  - `10: 159`
  - `12: 530`
  - `14: 4049`
  - `15: 4`
- Últimos avances ejecutados:
  - `backfill-senado-details --legislature 11 --max-events 20` => `events_reingested=3`, `member_votes_loaded=795`.
  - `backfill-senado-details --legislature 10 --max-events 300` => `events_reingested=163`, `member_votes_loaded=5191`.
  - `backfill-senado-details --legislature 12 --max-events 300` => `events_reingested=293`, `member_votes_loaded=5167`.
  - `backfill-senado-details --legislature 14 --max-events 50` => `events_reingested=25`, `member_votes_loaded=6424`.
  - `backfill-senado-details --vote-event-ids \"url:https://www.senado.es/legis14/votaciones/ses_21_245.xml\"` => `events_reingested=1`, `member_votes_loaded=256`.
  - `backfill-senado-details --vote-event-ids \"ses_21_217..221\"` => `events_reingested=5`, `member_votes_loaded=1280`.
- Siguiente acción prioritaria:
  - Enfocar en `senado_votaciones` legislatura 14 (lote pequeño y controlado), continuar por bloques de `vote-event-ids` ordenados por sesión para extraer rápidamente los grupos con mayor `events_with_member_votes` (ej. `ses_21_*`, luego `ses_22_*`).
