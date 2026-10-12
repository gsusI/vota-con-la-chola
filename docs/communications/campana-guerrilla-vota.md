# Campaña guerrilla: «¿Con quién coincides?»

Fecha: 2026-10-12 · Objetivo: `https://votaconlachola.org/citizen/vota/`

## Dónde estamos / a dónde vamos / qué sigue

- **Ahora**: el test funciona (33 temas clave + 334 votaciones en modo infinito, 12 partidos, cada voto con enlace oficial). Tiene botón «Compartir mi podio» (sin respuestas) y una página con vista previa para cada pregunta. Sin tráfico orgánico y sin medición.
- **Vamos**: que la gente lo juegue porque *le pica la curiosidad*, no porque se lo pidamos: «¿quién votó eso?» → revelación → «mira mi podio».
- **Siguiente**: elecciones generales el **29 de noviembre de 2026**. Cerrar la Fase 0 antes del 18 oct (revisión humana incluida) para lanzar el 20 oct.

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

**Ejemplos de promesas incumplidas: siempre de varios partidos a la vez.** Regla: no se publica un ejemplo de un partido sin otro de un partido del bloque contrario el mismo día, ambos con su fuente. Los casos verificados están en la sección siguiente.

## Ángulo «Dijeron / Votaron»: señal, no ruido

Investigación del 2026-10-12. Los votos salen de las votaciones nominales oficiales del Congreso (JSON de `congreso.es/webpublica/opendata/votaciones`) y los argumentos, del Diario de Sesiones. **Pendiente: revisión humana de cada ficha antes de publicarla.**

### Filtro de señal: un caso solo se publica si pasa las cuatro pruebas

1. **Lo dicho es concreto y tiene fecha**: programa, acuerdo firmado o declaración literal. «Defiende X» en general no vale.
2. **Lo votado es el mismo asunto**: votación nominal o acto oficial (BOE, contrato). Una votación sobre un tema parecido no vale.
3. **El voto de cada diputado es público**: votación nominal, no asentimiento.
4. **Toca la vida diaria**: agua, vivienda, impuestos, migración, pensiones, modelo territorial.

Cada ficha incluye **su defensa en una línea**: lo que el partido dijo para justificar el voto. Sin eso es propaganda, no información.

Veredictos posibles:
- **Contradicción**: dijo X y votó o hizo lo contrario.
- **Doble discurso territorial**: dice X en una comunidad y lo contrario en otra, y en el Congreso vota en bloque con su grupo.
- **Coherente, aunque sorprenda**: también es señal.
- **Ruido**: no se publica como incumplimiento (ómnibus, promesa votada a favor que se perdió, ausencias que no cambian nada).

### Caso estrella: el trasvase Tajo-Segura (13-05-2025). Neutral por diseño

Toma en consideración de la ley de la Asamblea Regional de Murcia para mantener el trasvase. **Rechazada por 170 a 171, con 4 abstenciones.** Votaron sí PP (136), Vox (33) y UPN; votaron no PSOE (118), Sumar, ERC, Junts, EH Bildu, PNV, BNG y CC; Podemos (4) se abstuvo.

| Partido | Qué dijo | Qué votó | Su defensa |
|---|---|---|---|
| PSOE | Francisco Lucas, líder del PSOE de Murcia y diputado por Murcia, dijo en tribuna que el PSOE no va a cerrar el trasvase | No, igual que los otros 117 diputados socialistas | «Hoy no se vota trasvase sí o trasvase no»: la ley rompía el Pacto del Agua de Murcia de 2018 y contradecía sentencias del Supremo |
| PP | En Castilla-La Mancha, el PP regional defiende el Pacto del Agua de CLM; Paco Núñez sostiene que solo una «necesidad real» justifica trasvasar | Sí, los 136 diputados presentes, también los elegidos en CLM | Garantizar el agua al Levante. Matiz: la postura de Núñez es condicional, así que esto es doble discurso, no contradicción literal |
| Podemos | En el mismo debate dijo que siempre ha reconocido la importancia del trasvase para Murcia | Abstención. **Con sus 4 votos a favor, la ley habría salido (174 a 171)** | La iniciativa «nace viciada» (se aprobó en Murcia con apoyo de tránsfugas); rechazan la «guerra del agua» |

- **Ruido que no hay que inflar**: Feijóo no votó. Con su voto habría quedado 171 a 171, y en el Congreso un empate que se repite rechaza la iniciativa igualmente (Reglamento, art. 88). No decidió nada.
- **El mensaje**: «En Murcia todos defienden el trasvase. En Madrid cada grupo votó en bloque. Tu diputado vota con su grupo, no con tu provincia: mira el voto del grupo».
- Lo dijo el propio Podemos en tribuna: PP y PSOE dicen una cosa en Murcia y la contraria en Castilla-La Mancha. Y su propia abstención decidió la votación. Ningún partido sale limpio, y por eso es el mejor caso de la campaña.
- Enlace: `/citizen/vota/t/campo-trasvase-tajo-segura/`

### Contradicciones verificadas (se publican por parejas de bloques)

| Tema | Dijeron | Votaron / hicieron | Su defensa | En el test |
|---|---|---|---|---|
| Amnistía (PSOE) | Antes del 23-J de 2023, Sánchez y el PSOE sostenían que la amnistía no cabía en la Constitución | 14-03-2024: el PSOE vota sí; aprobada 178 a 172 | Sánchez reconoció en enero de 2024 un «cambio de opinión» porque la situación en Cataluña había evolucionado | `territorio-amnistia` |
| Regularización de inmigrantes (PP) | 09-04-2024: los 136 diputados presentes del PP votan sí a tramitar la ILP; aprobada 310 a 33, solo Vox en contra | Septiembre de 2024: enmiendas restrictivas. En 2026 Feijóo critica la regularización y estudia recurrir el decreto | Su sí era a debatirla con condiciones (caso a caso, sin antecedentes penales) | `inmigracion-regularizacion` |
| Armas con Israel (Gobierno, Interior) | Compromiso oficial de no comprar ni vender armamento a Israel desde la guerra de Gaza (nota de Interior, oct. 2024) | Abril de 2025: se formaliza un contrato de munición con IMI Systems; se rescinde días después tras la presión de IU/Sumar | La Abogacía del Estado desaconsejaba rescindir en esa fase | `exterior-armas-israel` (acto de Gobierno, no votación: indicarlo) |

Pareja para publicar el mismo día: Amnistía (PSOE) + Regularización (PP).

Se descarta por el filtro: **Sáhara (PSOE)**. El cambio de 2022 (de la autodeterminación al plan de autonomía marroquí) es un acto de Gobierno, y la votación del test sobre la nacionalidad de los saharauis es otro asunto (no pasa la prueba 2). Puede ir en una pieza propia, pero no como «votó contra lo que prometió».

### Coherente, aunque sorprenda

- **Junts y la jornada de 37,5 horas** (10-09-2025: la ley se devolvió al Gobierno por 178 a 170). Junts votó con PP y Vox, pero lo había anunciado y lo justificó: la jornada debe negociarse convenio a convenio, no por ley. No es una promesa incumplida. Sí es información útil para quien votó a Junts pensando lo contrario.

### Ruido: lo que NO es una promesa incumplida (y hay que explicarlo)

- **Decretos ómnibus.** El 22-01-2025, PP, Vox y Junts tumbaron el decreto que mezclaba la subida de las pensiones con las ayudas al transporte, la DANA y otras medidas. Después, PP y Junts apoyaron el decreto separado (convalidado en febrero de 2025); Vox fue el único que votó en contra de este segundo, que incluía el escudo social. Ninguno votó «contra las pensiones»: votaron contra paquetes. El juego ya permite excluir las votaciones ómnibus.
- **Prometer y perder.** La jornada de 37,5 horas estaba en el acuerdo de coalición PSOE-Sumar. Ambos votaron a favor y la tumbaron otros. No es un incumplimiento: la votación dice quién la bloqueó.
- **Ausencias que no deciden**, como la de Feijóo en el trasvase.

### Pendiente

- **Vox y PNV**: todavía no hay ningún caso que pase el filtro. Hay que comparar el programa de 2023 con las votaciones nominales. Hasta tenerlo no se publica nada de ellos; tampoco se rellena el hueco con casos flojos.
- **Producto**: ficha «Dijeron / Votaron» en la página de cada pregunta (`/citizen/vota/t/<id>/`), tras la revisión humana.

Fuentes: votaciones nominales oficiales del Congreso (Leg. 15: sesión 110, 13-05-2025, votación 1; sesión 34, 09-04-2024, votación 1); [Diario de Sesiones nº 114](https://www.congreso.es/public_oficiales/L15/CONG/DS/PL/DSCD-15-PL-114.PDF); [Maldita, hemeroteca de la amnistía](https://maldita.es/malditahemeroteca/20250627/pedro-sanchez-amnistia-constitucion/); [elDiario.es, Feijóo y la regularización](https://www.eldiario.es/politica/feijoo-critica-ahora-regularizacion-personas-migrantes-defender-podian-tranquilos_1_12938361.html); [Interior, rescisión del contrato de munición](https://www.interior.gob.es/opencms/ca/detalle/articulo/Interior-inicia-el-proceso-para-rescindir-el-contrato-de-compra-de-municion-a-una-empresa-israeli/); [El Independiente, formalización del contrato](https://www.elindependiente.com/espana/2025/04/23/interior-se-ve-obligado-a-comprar-armas-a-israel-a-pesar-de-que-marlaska-ordeno-no-hacerlo/); [Moncloa.com, el PP y el Pacto del Agua de CLM](https://www.moncloa.com/2024/04/24/pp-pacto-agua-castilla-mancha-2568128/); [iAgua, el PSOE de Murcia y el trasvase](https://www.iagua.es/noticias/europa-press/psoe-murcia-apuesta-complementar-trasvase-desalacion-y-modernizacion-regadios); [Maldita, el decreto ómnibus](https://maldita.es/malditobulo/20250128/decreto-omnibus-medidas-por-separado/); [elDiario.es, la convalidación de las pensiones](https://www.eldiario.es/politica/congreso-convalida-revalorizacion-pensiones-ayudas-transporte-publico-segundo_1_12047053.amp.html); [El Salto, Junts y la jornada](https://www.elsaltodiario.com/reduccion-jornada/junts-traslada-yolanda-diaz-no-reduccion-jornada-peligra-posible-aprobacion); [Menorca.info, el PSOE y el Sáhara](https://www.menorca.info/actualidad/nacional/2022/03/25/1714563/psoe-sahara-autodeterminacion-plan-autonomia-marruecos.html).

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

## Calendario: elecciones generales del 29 de noviembre de 2026

Las Cortes se disolvieron el 6 de octubre (RD 806/2026). La campaña oficial va del **viernes 13 al viernes 27 de noviembre**, el 28 es jornada de reflexión y el 29 se vota. Quedan siete semanas: todo el plan se comprime para llegar antes del 29N.

Nuevo gancho que da la disolución: **«La legislatura se ha cerrado. Ya no pueden cambiar lo que votaron.»** Los cuatro años de votos están fijos; ahora toca compararlos con lo que prometan en campaña.

| Semana | Fase | Hito clave |
|---|---|---|
| 12–18 oct | 0 · Bloqueantes | Revisión humana cerrada el **18 oct**; pedido de imprenta el **19 oct** |
| 19 oct – 12 nov | 1 · Precampaña «Adivina quién votó» | Lanzamiento digital el **20 oct**; reto a los partidos enviado el **20 oct**, tabla pública el **9 nov** |
| 13–23 nov | 2 · Campaña «Dijeron / Votaron» | Cada promesa de mitin, contrastada con su votación en ≤ 24 h |
| 24–27 nov | 3 · Recta final | Kit para el grupo familiar de WhatsApp; sin nada que parezca una encuesta |
| 28–29 nov | Reflexión y votación | Pausa total: nada nuevo, nada en la calle; la web sigue abierta |
| 30 nov – 23 dic | Después | «Guardamos sus promesas»: archivo para la nueva legislatura |

### Fase 0 · Bloqueantes (12–18 oct)

1. ✅ **Vista previa al compartir** (2026-10-12). `/citizen/vota/` tiene tarjeta OG (`/citizen/vota/og/inicio.png`) y cada uno de los 33 temas tiene su página `/citizen/vota/t/<statement_id>/` con su PNG (`/citizen/vota/og/<statement_id>.png`, insignia «Se decidió por N votos» si la diferencia es ≤ 5) que abre el juego en esa pregunta. Tras responder, «Retar a alguien con esta pregunta» comparte ese enlace sin la respuesta. La tarjeta nunca revela qué votó cada partido.
2. **Revisión humana en una semana.** Dos personas independientes revisan las 33 afirmaciones y las fichas «Dijeron / Votaron». Hay que reclutarlas hoy mismo (politólogos, periodistas de datos). «Cazadores de errores» pasa a ser una invitación pública permanente, no un requisito previo.
3. **Medición sin rastrear personas.** Cloudflare Web Analytics (sin cookies) + rutas cortas por canal (`/v/bar`, `/v/campus`, `/v/tiktok`, `/v/prensa`…). Cada QR físico apunta a su ruta. Nada de datos de usuario en la URL.
4. **Kit de prensa de una página**: qué es, método, limitaciones, 3 ganchos, contacto. Las redacciones cierran ahora sus especiales electorales: hay que estar en ellos.
5. **Imprenta**: posavasos y pegatinas encargados el 19 oct (entrega en 5–7 días). Sin nombres ni logos de partidos en ninguna pieza física.

### Fase 1 · Precampaña «Adivina quién votó» (19 oct – 12 nov)

- **20 oct, lanzamiento digital**: Menéame y r/spain con un post honesto («la legislatura se ha cerrado: estas son sus votaciones convertidas en un test; datos abiertos; buscad errores»).
- **Twitter/X**: tweets, calendario por parejas e imágenes en [`twitter-kit/`](twitter-kit/README.md).
- **Vídeo corto** (TikTok / Reels / Shorts), un vídeo al día, tres formatos: *Calle* («¿quién crees que votó…?» → revelación), *Reacciono a mi podio* y *Abuela/o vs nieta/o*.
- **Periodistas de datos y especiales electorales**: un gancho regional distinto para cada medio (Tajo-Segura → prensa murciana y manchega).
- **Reto a los 12 partidos** (carta el 20 oct, plazo hasta el 6 nov, tabla pública el 9 nov): pedimos a un candidato de cada uno que haga el test *sin mirar* y publique su podio. Se publica antes de la campaña, cuando los equipos todavía contestan.
- **Calle desde el 26 oct** (en cuanto llegue la imprenta): posavasos en bares con permiso, pegatinas en tablones de campus y bibliotecas, mesa «Juega 5 preguntas» en campus y mercados.

### Fase 2 · Campaña «Dijeron / Votaron» (13–23 nov)

La campaña es la temporada alta de promesas: es el momento del mensaje central.

- **Promesa de mitin → votación en ≤ 24 h.** Cuando un partido promete algo sobre un tema del test, se publica la ficha «Dijeron / Votaron» con su votación oficial. Se aplica el filtro de señal y la regla de publicar por parejas de bloques.
- **Debates de televisión**: hilo en directo con las votaciones de cada tema que salga («dicen esto; votaron esto»).
- **Calle los fines de semana** (14–15 y 21–22 nov): mesas en mercados y ferias, con permiso.
- **Respuesta factual a políticos**, solo desde la cuenta oficial del proyecto, sin opinión ni adjetivos.

### Fase 3 · Recta final (24–27 nov)

- **Kit para el grupo familiar de WhatsApp**: «Antes de votar, 10 preguntas. Después, comparad podios.» Una imagen + un enlace, pensada para reenviar el fin de semana anterior.
- **Del 24 al 28 nov está prohibido publicar sondeos.** El test no es una encuesta, pero no se publica nada que lo parezca: nunca datos agregados del tipo «el X % de los usuarios coincide con…» (de todos modos no los recogemos).

### Reflexión y votación (28–29 nov)

Ni piezas nuevas, ni calle, ni respuestas a políticos. La web sigue abierta (es información, no propaganda), pero no se promociona. El 29, nada cerca de los colegios electorales.

### Después (30 nov – 23 dic): «Guardamos sus promesas»

Las nuevas Cortes se constituyen el 23 de diciembre. Durante la campaña se archivan las promesas con fecha y fuente (programas, mítines y debates) para compararlas con lo que voten en la nueva legislatura. Así la campaña se convierte en un seguimiento continuo: «Lo prometieron el 18 de noviembre. Así lo votaron.»

## Líneas rojas

- Neutralidad: sorpresas para todos los bloques, mismo día, mismo tono.
- Nada de cuentas falsas, granjas de bots ni astroturfing. Todo sale de cuentas identificadas del proyecto o de gente real que quiere.
- No usar logos ni colores de partidos de forma que parezca propaganda suya.
- Cada dato con su enlace oficial; si hay un error, se corrige en público.
- «Para explorar, no como veredicto»: nunca decir «tu partido es X».
- Sin pegar en propiedad ajena ni mobiliario urbano.
- Ley electoral (LOREG): neutralidad total, sin pedir el voto para nadie; nada que parezca un sondeo del 24 al 28 nov; pausa el 28 y el 29. Antes de la Fase 2 conviene una consulta rápida con alguien experto en derecho electoral (esto no es asesoría legal).

## Métricas (DoD de la campaña)

| KPI | Cómo se mide | Objetivo al 29N |
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
| Kit de WhatsApp (imagen + enlace) | 0 € |
| **Total** | **~270 €** |
