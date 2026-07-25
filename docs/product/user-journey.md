# Recorrido de usuario: el recibo del agua de Andalucía 2026

Supuesto: el usuario principal es **Sergio Llorente, ciudadanía escéptica en modo auditoría**, definido en `docs/personas-y-flujos-ideales.md`; no hay todavía evidencia de uso real que valide esta elección.

Producto enfocado: una sola página compartible que responda «¿qué comprometió el nuevo Gobierno andaluz sobre agua, qué ha ocurrido después y qué sigue sin probarse?».

## Parte A — Marco de una página

### 1. CINCO ESTADOS DEL USUARIO

1. **Ruido ajeno** — Cree que otra web política solo añadirá opinión, cifras y trabajo.
2. **Duda concreta** — Quiere comprobar una afirmación específica sobre agua sin leer programas, diarios y boletines enteros.
3. **Prueba visible** — Ve el compromiso exacto, el responsable, el estado, la fuente oficial y los límites, y siente que puede verificarlo por sí mismo.
4. **Utilidad repetida** — Comprueba qué cambió desde el corte anterior y cree que volver le ahorra tiempo.
5. **Prueba compartida** — Comparte el recibo porque otra persona puede abrir el mismo corte y reconstruir la conclusión.

### 2. CUATRO TRANSICIONES

**Transición 1 — Ruido ajeno → Duda concreta**
Trigger: recibe un enlace o ve una afirmación sobre los compromisos de agua de la nueva legislatura.
Value given: obtiene en una frase cuántos compromisos se vigilan y si existe alguna actuación posterior.
Ask made: nada.

**Transición 2 — Duda concreta → Prueba visible**
Trigger: abre uno de los tres compromisos de investidura.
Value given: recibe texto exacto, localizador, responsable, estado, evidencia posterior y desconocidos.
Ask made: nada.

**Transición 3 — Prueba visible → Utilidad repetida**
Trigger: existe un snapshot posterior al que vio por última vez.
Value given: recibe un antes/después limitado a nueva evidencia oficial.
Ask made: guardar «Agua» localmente en su dispositivo.

**Transición 4 — Utilidad repetida → Prueba compartida**
Trigger: necesita respaldar una conversación, artículo o decisión con una fuente.
Value given: recibe un enlace estable con snapshot, conclusión, límites y fuente primaria.
Ask made: compartir el recibo.

Transición más frágil: la 3. El primer recibo ya está publicado y verificable, pero todavía no existe un segundo snapshot que permita demostrar cambio, retorno o utilidad repetida.

### 3. EL MOMENTO AHA

Hipótesis: **abrir el mismo compromiso en dos snapshots dentro de 30 días** predice uso recurrente. No hay datos reales para medirlo todavía.

### 4. EL CUELLO DE BOTELLA

La respuesta inicial ya existe: tres compromisos revisados, un corte vigente y fuentes oficiales en una página pequeña. El cuello de botella pasa a ser temporal y humano: producir un segundo corte comparable y comprobar con cinco usuarios si el recibo ahorra tiempo y merece una segunda visita.

## Parte B — Apéndice operativo

### Por qué este producto y este momento

- La elección andaluza se celebró el `2026-05-17`; los resultados oficiales ya están publicados por la [Junta Electoral de Andalucía](https://www.juntadeandalucia.es/boja/2026/108/1.html).
- El Parlamento de la XIII legislatura se constituyó el `2026-06-11` y Juan Manuel Moreno fue [investido el 2026-07-02](https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/actualidad/comunicadosdeprensa.do?id=203654).
- El [discurso de investidura](https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/pdf.do?id=203574&tipodoc=diario) contiene tres compromisos verificables sobre agua: llevar a la Cámara la primera ley andaluza de regadío, aprobar un nuevo reglamento de planificación y proponer la actualización de la Ley de Aguas de Andalucía.
- El repo ya contiene una cadena histórica útil para `campo_agua`: votos revisados, cambios BOJA, actor administrativo parcial, una partida presupuestaria y contratos oficiales. Sirve como baseline; no demuestra cumplimiento posterior.
- La ventana de captura del punto de partida está abierta ahora. Esperar a completar toda la plataforma destruiría esa ventaja temporal.

### Evidencia por estado

| Estado | Qué puede crearlo hoy | Hueco real |
|---|---|---|
| Ruido ajeno | La home ofrece muchas entradas por tema, actor, decisión y datos. | No formula una pregunta actual ni da un primer resultado concreto. |
| Duda concreta | `/elecciones/andalucia-2026/` abre con una respuesta actual y tres compromisos de agua. | Falta medir si una persona entiende el propósito en menos de `30 s`. |
| Prueba visible | El recibo publica texto y localizador revisados, fuentes oficiales, estado, responsable, checkpoint y límites. | No hay todavía un hito formal posterior a la investidura; la reiteración del `2026-07-16` no cuenta como progreso. |
| Utilidad repetida | El modelo usa snapshots, fechas y estados de frescura. | No existe diff ciudadano por compromiso ni señal agregada de retorno. |
| Prueba compartida | Cada compromiso tiene ancla estable, bloque de cita, límite visible y enlace a fuente primaria. | Falta observar compartidos y reaperturas reales. |

### Transición 1 — De ruido a duda concreta

Superficies: home, enlace directo y tarjeta social del recibo. La ruta ya abre con la pregunta ciudadana, no con cobertura, arquitectura o número de filas. Falta probar esa entrada con cinco personas. Métrica: `water_receipt_open / landing_view`.

### Transición 2 — De duda a prueba visible

Superficie: tres recibos de compromiso. Cada uno separa declaración, actuación posterior, responsable/competencia, dinero/ejecución y desconocidos, sin convertir proximidad en mérito o culpa. El texto de investidura, el corte posterior al `2026-07-02` y el contrato compacto ya están revisados; falta observar si el usuario abre la fuente. Métrica: `primary_source_open / commitment_open`.

### Transición 3 — De prueba visible a utilidad repetida

Superficies: badge de frescura, «cambió desde tu última visita» y preferencia local. El usuario se estanca si vuelve y ve la misma masa de datos sin saber qué cambió. Ya existen snapshots reproducibles; faltan diff por compromiso, fecha de último control y guardado local. Métrica: `commitment_revisit_30d / unique_commitment_viewer`.

### Transición 4 — De utilidad repetida a prueba compartida

Superficies: enlace estable, bloque de cita y vista social. La ruta por fragmento y la acción explícita de compartir ya conservan compromiso, snapshot, límites y fuentes. Faltan metadatos sociales específicos por compromiso y uso real. Métrica: `receipt_share / returning_viewer`.

### Personas secundarias

- **Óscar, monitor legislativo**: necesita el mismo recibo como material citable y amplifica su descubrimiento. Requiere fecha, cambio desde snapshot anterior y fuente, no más dashboards.
- **Alba, ciudadanía de respuesta rápida**: necesita una versión resumida: qué se prometió, qué estado tiene y qué no sabemos. Puede ignorar el detalle metodológico hasta pedirlo.
- **Irene, analista**: necesita descargar el recibo y sus referencias, pero su export técnico no debe dominar la página pública.
- **Nadia y Tomás**: son roles internos de calidad y publicación. Sus colas, comandos y métricas operativas deben vivir fuera del camino ciudadano.

### Plan de medición

Eventos mínimos propuestos:

- `water_receipt_open`
- `commitment_open`
- `primary_source_open`
- `commitment_saved_local`
- `commitment_snapshot_revisit`
- `receipt_share`

La app Next pública no emite hoy estos eventos. El citizen legado conserva telemetría solo en `localStorage`, por lo que no prueba uso agregado. Antes de añadir recogida remota, medir manualmente cinco sesiones observadas y diez enlaces distribuidos; si se instrumenta, usar conteos agregados sin preferencias ni identificadores personales.

### Riesgos y preguntas abiertas

| Riesgo | Prueba barata |
|---|---|
| Agua no genera interés suficiente. | Mostrar un prototipo a cinco usuarios de Andalucía y comparar comprensión frente a la página actual. |
| Los tres compromisos son demasiado vagos para marcar progreso. | Revisarlos manualmente y exigir actor, acto verificable y siguiente checkpoint antes de publicar. |
| El baseline previo se confunde con cumplimiento del nuevo mandato. | Rotular toda evidencia anterior al `2026-07-02` como contexto histórico, nunca como avance. |
| La atribución mezcla competencias autonómicas y estatales. | Añadir campo de competencia y bloquear cualquier actor no respaldado por fuente. |
| Un estado de «sin cambios» parece abandono. | Publicar fecha de último control y fuentes revisadas, incluso cuando no aparece evidencia nueva. |
| La medición invade privacidad. | Empezar manualmente; no persistir temas políticos en servidor por defecto. |
