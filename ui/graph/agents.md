# Explorer Político UI agents

## Versión activa
- Archivo: `ui/graph/explorer-sports.html` (vista política)
- Versión actual: `1.1.12`
- Última actualización: `2026-02-13`

## Cambios incluidos en esta versión
- Trazabilidad verbose en cliente y servidor para seleccionar territorio en `explorer-politico`.
- Fix de filtro territorial para que siempre aplique desde cliente y se loguee el comportamiento.
- Ajuste de matching de filtros territoriales (códigos + nombres).
- Añadido número de versión visible en título y encabezado.
- Implementada vista treemap en "Partidos del nivel" para el nivel `all`, manteniendo filtros/atajos y navegación al detalle de partido.
- Jerarquía explícita de cargos y orden por nivel territorial + jerarquía de responsabilidades en la lista de políticos de partido (incluye Alcalde > Teniente de alcalde).
- Agrupación visual por nivel y rol (una fila por rol): Alcalde/Presidencia, Teniente/Vice, Concejal, etc.
- Corrección de jerarquía: "Teniente de alcalde" se fuerza a fila separada de "Alcalde".
- Ranking de municipios con "políticos por 100k hab." en el panel izquierdo de `explorer-politico`.
- Ajuste de treemap para `Partidos del nivel: Todos los niveles` a layout de áreas tipo Windirstat (treemap por área/proporción, con expansión vertical real cuando hay muchos partidos).
- En la ficha de político (modal), se añaden enlaces directos a la(s) fuente(s) usando `default_url` (una por cada `source_id` presente en mandatos).
- Agregación de partidos con 1 solo integrante en una tarjeta unificada "Otros", reutilizando el flujo de detalle y filtrado de tarjetas.
- Treemap: altura base fijada a **100vh** en el contenedor y en el cálculo inicial, conservando expansión vertical automática cuando la distribución requiere más espacio.
- El botón «Volver» en el panel de detalle de partido pasa a posición superior izquierda del componente (layout de encabezado en columna con botón primero).
- Treemap fijo a `100vh`, sin scroll interno: contenedor no desborda y la altura ya no se autoexpande en base al contenido de nodos.
- Ajuste de scroll del contenedor de partidos: se usa `.content-scroll.team-treemap` solo en modo treemap para forzar 100vh sin scroll interno del wrapper.
- Añadida re-renderización del treemap en `resize` de ventana y encapsulado del modo treemap en un toggle de layout dedicado.
- Finalizada integración del módulo de **Votaciones recientes** en `explorer-politico` (`/api/votes/summary`), con panel reactivo, desglose por grupo parlamentario y filtro por partido/partido seleccionado.

## Proceso de versionado
- Antes de cada cambio funcional en `explorer-sports.html`, actualizar:
  - `EXPLORER_SPORTS_VERSION` (o el valor visible en `title`/`h1`) en `ui/graph/explorer-sports.html`.
  - Este bloque de `agents.md` (`Versión actual` + `Última actualización`).
- Mantener sincronizada la versión que aparece en la pestaña y en la UI.

---

# Explorer Sources UI agents

## Versión activa
- Archivo: `ui/graph/explorer-sources.html`
- Versión actual: `1.0.2`
- Última actualización: `2026-02-14`

## Cambios incluidos en esta versión
- Reestructuración del dashboard para que todo esté organizado por `scope` (ámbito): progreso mínimo, estado operativo, fuentes configuradas, roadmap sin conector y pendientes.
- Reducción de ruido: se elimina el “detalle técnico por fuente” como tabla global; ahora está dentro de cada ámbito como listas colapsables.
- “Filtros avanzados” quedan colapsables y se aplican al dashboard por ámbito.
- Acciones del tracker sin `source_id` se agrupan por ámbito usando `scope` inferido desde el tracker (servidor).

## Proceso de versionado
- Antes de cada cambio funcional en `explorer-sources.html`, actualizar:
  - el número visible en el encabezado (pestaña/UI)
  - este bloque de `agents.md` (versión + fecha + resumen)
