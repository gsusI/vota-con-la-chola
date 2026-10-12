# Campaña guerrilla: «¿Con quién coincides?»

Fecha: 2026-10-12 · Objetivo: `https://votaconlachola.org/citizen/vota/`

## Dónde estamos / a dónde vamos / qué sigue

- **Ahora**: el test funciona (33 temas clave + 334 votaciones en modo infinito, 12 partidos, cada voto con enlace oficial). Tiene botón «Compartir mi podio» (sin respuestas). Sin tráfico orgánico, sin vista previa al compartir y sin medición.
- **Vamos**: que la gente lo juegue porque *le pica la curiosidad*, no porque se lo pidamos: «¿quién votó eso?» → revelación → «mira mi podio».
- **Siguiente**: cerrar los 4 bloqueantes de la Fase 0 antes de gastar un euro o pegar una pegatina.

## Mensaje central: vota por lo que hicieron, no por lo que prometen

Es la idea que sostiene toda la campaña. Cada pieza, de la pegatina al vídeo, debe empujar hacia ella:

1. **Prometer no obliga.** En España un programa electoral no es un contrato. La Constitución prohíbe el mandato imperativo (art. 67.2 CE): ningún diputado está obligado por lo que prometió, y no hay ningún mecanismo para exigir que se cumpla.
2. **Cuentan con que se nos olvide.** Una legislatura dura cuatro años y la campaña dos semanas. Lo que se prometió se recuerda, lo que se votó no.
3. **El voto queda registrado.** Cada votación nominal del Congreso es pública, con nombre y fecha. Es lo único que se puede comprobar.
4. **El método:** ¿qué habría votado yo? Responde a lo que de verdad se votó y mira quién votó como tú. Ese es tu partido, digan lo que digan en campaña.

Frases para piezas:
- «Prometer no obliga. Votar queda registrado.»
- «No les preguntes qué harán. Mira qué votaron.»
- «Tú también habrías votado. Compara.»
- «Su programa es una promesa. Su voto es un hecho.»
- (Arriesgada, por el doble sentido) el refrán «Prometer hasta meter…», solo en canales informales.

**Ejemplos de promesas incumplidas: siempre de varios partidos a la vez.** La amnistía es el caso más citado (se descartó antes de las elecciones de 2023 y se aprobó después), pero si es el único ejemplo, la campaña se lee como una campaña contra un partido y pierde la neutralidad. Regla: no se publica un ejemplo de promesa incumplida sin otro de un partido del bloque contrario, ambos con su fuente (declaración fechada + votación oficial). Antes de usarlos, hay que buscarlos y verificarlos (posible fuente: los datos de promesas en `/promises/`).

## Concepto

**«Lo que votaron, no lo que dicen.»** Lema corto: *Vota con la chola, no con la tripa.*

El motor es la **revelación**: todo votante de cualquier partido tiene al menos un «no me lo esperaba». La campaña vende esa sorpresa en la calle y en redes, y el clic se la da.

Regla de oro (neutralidad): **nunca se publica una sorpresa incómoda para un bloque sin publicar el mismo día una incómoda para el otro.** Si nos etiquetan de un lado, el proyecto muere.

## Ganchos (salen del snapshot, cada uno con su votación oficial)

| Gancho | Dato | A quién sorprende |
|---|---|---|
| «Se decidió por **un voto**» | Trasvase Tajo-Segura con reglas de 2014: 170 sí / 171 no | Murcia, Alicante, Almería, Castilla-La Mancha |
| «¿Quién votó **en contra** de subir el impuesto a la gran banca?» | 41 sí / 294 no; PSOE y PP votaron lo mismo (no) | Izquierda |
| «¿Quién apoyó la **regularización** de inmigrantes sin papeles?» | 310 sí / 33 no; PP a favor, solo VOX en contra | Derecha |
| «VOX y Podemos votaron **igual**» | Jubilación activa (cobrar parte de la pensión y trabajar): 298 / 51 | Todos |
| «¿Quién votó **no** a la nacionalidad para saharauis nacidos bajo España?» | PSOE en contra; PP, Sumar y Podemos a favor | Izquierda |
| «¿Quién tumbó la jornada de **35 horas**?» | 162 / 178; Junts con PP y VOX | Votantes de Junts y de izquierda |
| «¿Quién votó con PP y VOX sobre el **lobo**?» | 180 / 155; Junts y PNV con PP y VOX | Nacionalistas |
| «Toros: el PSOE **se abstuvo**» | 57 sí / 169 no / 118 abst. | Izquierda |
| «Elegir centro de **educación especial**» | 170 / 177; PP, VOX, UPN a favor; resto en contra | Familias, centro |

⚠️ Las 33 afirmaciones están revisadas con IA, **no por personas** (lo dice el propio banner). Ningún gancho se imprime ni se publica sin que una persona haya abierto el enlace oficial y confirmado el dato.

## Fase 0 · Bloqueantes (13–26 oct)

1. ✅ **Vista previa al compartir** (2026-10-12). `/citizen/vota/` tiene tarjeta OG (`/citizen/vota/og/inicio.png`) y cada uno de los 33 temas tiene su página `/citizen/vota/t/<statement_id>/` con su PNG (`/citizen/vota/og/<statement_id>.png`, insignia «Se decidió por N votos» si la diferencia es ≤ 5) que abre el juego en esa pregunta. Tras responder, «Retar a alguien con esta pregunta» comparte ese enlace sin la respuesta. La tarjeta nunca revela qué votó cada partido.
2. **Revisión humana de los ganchos.** Dos personas independientes revisan al menos las 9 de la tabla. Convertirlo en campaña: «Cazadores de errores», invitar a periodistas de datos y politólogos a revisar en público; cada error encontrado se corrige y se agradece. Credibilidad > alcance.
3. **Medición sin rastrear personas.** Cloudflare Web Analytics (sin cookies) + rutas cortas por canal que redirigen al test (`/v/bar`, `/v/campus`, `/v/tiktok`, `/v/prensa`…). Cada QR físico apunta a su ruta. Nada de datos de usuario en la URL.
4. **Kit de prensa de una página**: qué es, método (mayoría del grupo en votación nominal), limitaciones, 3 ganchos, contacto.

## Fase 1 · «Adivina quién votó» digital (27 oct – 16 nov)

- **Vídeo corto (TikTok / Reels / Shorts)**, 3 formatos fijos, 1 vídeo/día:
  - *Calle*: «¿Quién crees que votó en contra de subir el impuesto a la banca?» → respuesta → revelación en pantalla con el enlace oficial.
  - *Reacciono a mi podio*: alguien juega 10 preguntas y reacciona a su resultado.
  - *Abuela/o vs nieta/o*: dos generaciones, mismo test, comparan podios.
- **Launch en comunidades de datos abiertos**: Menéame y r/spain con un post honesto («334 votaciones reales del Congreso convertidas en un test; código y datos abiertos; buscad errores»). La invitación a encontrar errores es el gancho para estas audiencias.
- **Periodistas de datos** (Civio, Maldita, Newtral, secciones de datos de medios nacionales y regionales): pitch con un gancho regional distinto para cada medio (Tajo-Segura → prensa murciana y manchega).
- **Respuesta factual a políticos**, solo desde la cuenta oficial del proyecto: cuando un partido presume o ataca sobre un tema que está en el test, responder con «Así votó cada partido: [enlace]». Sin opinión, sin adjetivos.

## Fase 2 · Calle (17 nov – 14 dic)

- **Posavasos de bar** (con permiso del bar): cara A «¿Discusión política en la barra? Resolvedla con datos.»; cara B una pregunta de la tabla + QR a `/v/bar`. ~5.000 uds ≈ 150 €.
- **Pegatinas «Adivina quién»**: una pregunta + QR, solo en tablones de libre uso, campus (vía asociaciones de estudiantes), bibliotecas y comercios que lo permitan. Nunca en mobiliario urbano ni propiedad ajena sin permiso (multas por ordenanza y mala imagen).
- **Mesa «Juega 5 preguntas»** en campus, mercados y ferias (con permiso): tablet, 5 preguntas, la persona se lleva su podio en el móvil. Foto del podio solo si quiere.
- **Reto a los 12 partidos**: carta pública a cada partido: «¿Coinciden vuestros diputados con lo que votó vuestro grupo?» Pedimos a un candidato de cada uno que haga el test *sin mirar* y publique su podio. Tabla pública de quién aceptó y quién no (factual, sin adjetivos). Noticia garantizada y neutral por diseño.

## Fase 3 · «Kit anti-cuñado» navideño (15 dic – 6 ene)

La cena de Navidad es la mayor discusión política del año. Pieza central: «Antes de discutir, juega 10 preguntas. Después, comparad podios.»
- Tarjeta imprimible para la mesa (PDF) con 3 preguntas y QR.
- Reel «Cómo ganar la discusión de Nochebuena con datos del Congreso».
- Producto (opcional, si da tiempo): **modo duelo**, comparar mi enlace de respuestas con el de otra persona («coincidimos en un 64 %»).

## Después: aprovechar la actualidad

Cada votación sonada del Congreso se publica en el modo infinito en ≤ 48 h y sale como gancho («Esta semana se votó X. ¿Quién crees que votó a favor?»). Antes de las generales (como tarde, ago–sep 2027) se repite la campaña a mayor escala con la revisión humana ya cerrada.

## Líneas rojas

- Neutralidad: sorpresas para todos los bloques, mismo día, mismo tono.
- Nada de cuentas falsas, granjas de bots ni astroturfing. Todo sale de cuentas identificadas del proyecto o de gente real que quiere.
- No usar logos ni colores de partidos de forma que parezca propaganda suya.
- Cada dato con su enlace oficial; si hay un error, se corrige en público.
- «Para explorar, no como veredicto»: nunca decir «tu partido es X».
- Sin pegar en propiedad ajena ni mobiliario urbano.
- Elecciones convocadas: revisar con la normativa electoral (LOREG) antes de cada acción en periodo de campaña.

## Métricas (DoD de la campaña)

| KPI | Cómo se mide | Objetivo a 6 semanas |
|---|---|---|
| Visitas por canal | Rutas cortas `/v/*` + analítica sin cookies | 25.000 |
| Canal ganador | Visitas por ruta / coste | identificar 2 canales a doblar |
| Menciones en prensa | Recuento manual | 5 piezas, 2 regionales |
| Reto a partidos | Partidos que responden | ≥ 3 de 12 |
| Errores reportados y corregidos | Issues / correo | todos cerrados en ≤ 72 h |

## Presupuesto orientativo

| Partida | Coste |
|---|---|
| 5.000 posavasos | ~150 € |
| 1.000 pegatinas | ~60 € |
| Roll-up para la mesa | ~60 € |
| Tarjetas Navidad (impresión casera / PDF) | 0 € |
| **Total** | **~270 €** |
