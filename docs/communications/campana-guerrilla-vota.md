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
