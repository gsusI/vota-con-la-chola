# Kit de Twitter/X: campaña «¿Con quién coincides?»

Parte de la [campaña guerrilla](../campana-guerrilla-vota.md). Imágenes en `img/` (1200×675, el formato que X muestra sin recortar). Se regeneran con `node docs/communications/twitter-kit/render.mjs`.

## Dónde estamos / a dónde vamos / qué sigue

- **Ahora**: 15 imágenes y unos 30 tweets listos. Las cifras salen del snapshot `voting_aid_generales_v1.json` y se han comprobado partido a partido.
- **Vamos**: un hilo de lanzamiento el 20 oct y luego una pareja de preguntas al día hasta el 12 nov; las fichas «Dijeron / Votaron» se publican del 13 al 23 nov.
- **Siguiente**: (1) la revisión humana de los datos (fecha límite: 18 oct) desbloquea todo; (2) cuando exista la ruta `/v/twitter`, sustituir los enlaces.

## Reglas para publicar

1. **Nada sale antes de la revisión humana.** Hay que abrir el enlace oficial de cada votación y confirmar el dato. Las fichas `14-dv-*` y `15-dv-*` necesitan también la revisión de la hemeroteca.
2. **Parejas de bloques el mismo día.** Si un tweet incomoda a la izquierda, el mismo día sale otro que incomode a la derecha. Las parejas ya están montadas en el calendario.
3. **La pregunta va en el tweet y la respuesta en la primera respuesta del hilo.** La imagen nunca revela qué votó cada partido, salvo en las tarjetas de revelación (07, 14 y 15). El enlace va siempre en la respuesta, porque X penaliza los enlaces en el tweet principal.
4. **Cada respuesta lleva su enlace oficial a congreso.es.** Si alguien detecta un error, se agradece en público y se corrige.
5. **Nunca decir «tu partido es X» ni pedir el voto.** Del 24 al 28 nov no se publica nada que parezca un sondeo. El 28 y el 29 no se publica nada.
6. **Sin hashtags de partido.** Como mucho `#29N` o `#EleccionesGenerales`, y solo en el tweet principal.

Enlaces (cámbialos por `/v/twitter/...` cuando exista la ruta):
- Juego: `https://votaconlachola.org/citizen/vota/`
- Pregunta concreta: `https://votaconlachola.org/citizen/vota/t/<id>/`. Abre el juego en esa pregunta y lleva su propia tarjeta de vista previa.

---

## Calendario

| Día | Pieza A | Pieza B (contrapeso) |
|---|---|---|
| Mar 20 oct | Hilo de lanzamiento (01, 02, 03) | — |
| Mié 21 oct | Trasvase (04): incómodo para todos | — |
| Jue 22 oct | Banca (05): incómodo para la izquierda | Regularización (06): incómodo para la derecha |
| Vie 23 oct | Vox = Podemos (07): incómodo para todos | «Prometer no obliga» (03), sin imagen nueva |
| Lun 26 oct | Saharauis (08): PSOE no, PP sí | — |
| Mar 27 oct | Toros (11): incómodo para la izquierda | Lobo (10): incómodo para los nacionalistas |
| Mié 28 oct | Jornada de 35 h (09): incómodo para Junts y la derecha | Educación especial (12): incómodo para la izquierda |
| Sem. 2–12 nov | Se reciclan los ganchos según la respuesta + reto a los partidos | |
| 13–23 nov | Pareja «Dijeron / Votaron»: amnistía PSOE (14) + regularización PP (15) | Promesas de mitin → votación en ≤ 24 h |
| 24–27 nov | Kit para la familia (13) | |
| 28–29 nov | **Nada** | |

---

## 0. Vídeo (horizontal, 1920×1080, 62 s)

Archivo: `video/vota-con-la-chola-x.mp4`. Se regenera con `node docs/communications/twitter-kit/render-video.mjs`.

Contenido: la legislatura se ha cerrado → «Prometer no obliga» → 4 preguntas con cuenta atrás y respuesta (trasvase, banca, regularización, pensiones; una por bloque y dos que incomodan a todos) → llamada a hacer el test. Sin audio: X reproduce los vídeos en silencio.

Tweet:
```
La legislatura se ha cerrado. Ya no pueden cambiar lo que votaron.

4 votaciones reales del Congreso. ¿Aciertas quién votó qué antes de que salga la respuesta?

#29N
```
Respuesta (con el enlace):
```
Haz el test completo y mira con quién coincides tú. 2 minutos, sin registro:
https://votaconlachola.org/citizen/vota/

Cada voto lleva su enlace oficial a congreso.es. Si ves un error, dínoslo y lo corregimos en público.
```
Variante corta, si se publica solo el vídeo:
```
Prometer no obliga. Votar queda registrado.

¿Aciertas quién votó qué? 👇 https://votaconlachola.org/citizen/vota/
```

## 1. Hilo de lanzamiento (20 oct)

**1/5**, imagen `01-lanzamiento.png`
```
Las Cortes se disolvieron el 6 de octubre. La legislatura está cerrada: ya no pueden cambiar lo que votaron.

Hemos convertido sus votaciones en un test. Respondes a lo que de verdad se votó en el Congreso y ves qué partidos votaron como tú. 🧵
```
Alt: «La legislatura se ha cerrado. Ya no pueden cambiar lo que votaron. Compara sus votos con lo que te prometan en campaña.»

**2/5**, imagen `02-como-funciona.png`
```
Cómo funciona:

1. Respondes a preguntas sacadas de votaciones nominales reales.
2. Ves qué votó cada partido, con el enlace oficial a congreso.es.
3. Te sale tu podio.

Sin registro. Tus respuestas no salen de tu móvil.
```
Alt: «Cómo funciona: responde a lo que de verdad se votó, mira qué votó cada partido y descubre tu podio.»

**3/5**, imagen `03-prometer-no-obliga.png`
```
¿Por qué votaciones y no programas?

Porque prometer no obliga. La Constitución prohíbe el mandato imperativo (art. 67.2): nadie puede exigir a un diputado que cumpla su programa.

Un programa es una promesa. Un voto nominal queda registrado, con nombre y fecha.
```
Alt: «Prometer no obliga. Votar queda registrado. Artículo 67.2 de la Constitución.»

**4/5**
```
Tres avisos:

· Es para explorar, no un veredicto. No te decimos a quién votar.
· 12 partidos, todos con el mismo trato.
· Si encuentras un error, dínoslo y lo corregimos en público.
```

**5/5**
```
Pruébalo (2 minutos) y luego compara tu podio con quien quieras:

https://votaconlachola.org/citizen/vota/
```

---

## 2. Ganchos «Adivina quién votó» (21 oct – 12 nov)

### Trasvase Tajo-Segura · `04-trasvase.png` · 21 oct

Principal:
```
13 de mayo de 2025. El Congreso vota garantizar por ley el trasvase Tajo-Segura.

170 sí. 171 no.

Se decidió por un voto. Y el grupo que podía inclinar la balanza no votó ni sí ni no.

¿Cuál? 👇
```
Respuesta 1:
```
Podemos se abstuvo con sus 4 diputados. Con esos 4 votos a favor, habría salido adelante por 174 a 171.

Sí: PP, Vox y UPN.
No: PSOE, Sumar, ERC, Junts, EH Bildu, PNV, BNG y CC.
```
Respuesta 2:
```
En Murcia casi todos dicen defender el trasvase. En Madrid cada grupo votó en bloque, también sus diputados de Murcia y de Castilla-La Mancha.

Tu diputado vota con su grupo, no con tu provincia.

https://votaconlachola.org/citizen/vota/t/campo-trasvase-tajo-segura/
```
Alt: «Garantizar por ley el trasvase Tajo-Segura. 170 sí, 171 no, 4 abstenciones. Se decidió por 1 voto. 13 de mayo de 2025.»

### Impuesto a la banca · `05-banca.png` · 22 oct (pareja con regularización)

Principal:
```
Abril de 2024. Se vota en el Congreso subir el impuesto sobre los beneficios extraordinarios de la gran banca.

41 a favor. 294 en contra.

¿Qué partidos votaron que no? Piénsalo antes de mirar 👇
```
Respuesta:
```
No: PSOE, PP, Vox, PNV, CC y UPN.
Abstención: Junts.
Sí: Sumar, Podemos, ERC, EH Bildu y BNG.

Ojo: no se votaba «impuesto sí o no», sino una proposición concreta del Grupo Mixto. El texto está en el enlace.

https://votaconlachola.org/citizen/vota/t/coste-vida-impuesto-banca/
```
Alt: «¿Quién votó no a subir el impuesto a la gran banca? 41 sí, 294 no, 7 abstenciones. 9 de abril de 2024.»

### Regularización · `06-regularizacion.png` · 22 oct (pareja con banca)

Principal:
```
Abril de 2024. El Congreso vota si tramita la iniciativa popular para regularizar a los inmigrantes que viven en España sin papeles.

310 sí. 33 no.

¿Quién votó sí? 👇
```
Respuesta:
```
Todos los grupos menos uno: PSOE, PP, Sumar, Podemos, ERC, Junts, EH Bildu, PNV, BNG, CC y UPN.

Solo Vox votó no.

Ojo: era la toma en consideración (empezar a debatirla), no la ley final.

https://votaconlachola.org/citizen/vota/t/inmigracion-regularizacion/
```
Alt: «¿Quién apoyó tramitar la regularización de inmigrantes sin papeles? 310 sí, 33 no. 9 de abril de 2024.»

### Jubilación activa · `07-jubilacion-activa.png` · 23 oct

Principal (la imagen ya lo revela):
```
Vox y Podemos votaron lo mismo.

Enero de 2025: decreto para poder cobrar parte de la pensión y seguir trabajando. Aprobado por 298 a 51.

¿Tú qué habrías votado?
```
Respuesta:
```
No: Vox, Podemos, Junts, EH Bildu y BNG.
Sí: PSOE, PP, Sumar, ERC, PNV, CC y UPN.

Haz el test y mira con quién coincides tú:
https://votaconlachola.org/citizen/vota/t/empleo-jubilacion-activa/
```
Alt: «Cobrar parte de la pensión y seguir trabajando. Sí: PSOE, PP, Sumar, ERC, PNV, CC y UPN. No: Vox, Podemos, Junts, EH Bildu y BNG. 22 de enero de 2025, 298 sí y 51 no.»

### Saharauis · `08-saharauis.png` · 26 oct

Principal:
```
Febrero de 2025. Se vota dar la nacionalidad española por vía especial a los saharauis nacidos bajo administración española.

195 sí. 116 no. 33 abstenciones.

¿Quién votó no? 👇
```
Respuesta:
```
No: PSOE.
Abstención: Vox.
Sí: PP, Sumar, Podemos, ERC, Junts, EH Bildu, PNV, BNG, CC y UPN.

PP y Podemos votaron lo mismo.

https://votaconlachola.org/citizen/vota/t/inmigracion-nacionalidad-saharauis/
```
Alt: «¿Quién votó no a la nacionalidad para los saharauis nacidos bajo administración española? 195 sí, 116 no, 33 abstenciones. 25 de febrero de 2025.»

### Toros · `11-toros.png` · 27 oct (pareja con lobo)

Principal:
```
Octubre de 2025. Una iniciativa popular pide que los toros dejen de estar protegidos por ley como patrimonio cultural.

57 sí. 169 no. 118 abstenciones.

118 abstenciones son casi un grupo entero. ¿Cuál? 👇
```
Respuesta:
```
Se abstuvo el PSOE.
No: PP, Vox y UPN.
Sí: Sumar, Podemos, ERC, Junts, EH Bildu, PNV y BNG.

https://votaconlachola.org/citizen/vota/t/cultura-tauromaquia/
```
Alt: «Quitar a los toros la protección como patrimonio cultural. 57 sí, 169 no, 118 abstenciones. 7 de octubre de 2025.»

### Lobo · `10-lobo.png` · 27 oct (pareja con toros)

Principal:
```
Abril de 2024. El PP propone permitir el control de la población de lobos para proteger a la ganadería.

180 sí. 155 no.

PP y Vox no llegan a 180. ¿Quién más votó sí? 👇
```
Respuesta:
```
Junts y PNV votaron con PP y Vox.
Abstención: EH Bildu y CC.
No: PSOE, Sumar, Podemos, ERC y BNG.

https://votaconlachola.org/citizen/vota/t/campo-lobo/
```
Alt: «¿Qué partidos votaron con PP y Vox sobre el control del lobo? 180 sí, 155 no, 7 abstenciones. 23 de abril de 2024.»

### Jornada de 35 horas · `09-jornada-35.png` · 28 oct (pareja con educación especial)

Principal:
```
Octubre de 2025. Se vota bajar la jornada laboral máxima a 35 horas semanales.

162 sí. 178 no.

¿Quién la tumbó? 👇
```
Respuesta:
```
No: PP, Vox, Junts y UPN.
Abstención: PNV y CC.
Sí: PSOE, Sumar, Podemos, ERC, EH Bildu y BNG.

Junts ya había anunciado su postura: quiere negociar la jornada convenio a convenio, no por ley.

https://votaconlachola.org/citizen/vota/t/empleo-jornada-35/
```
Alt: «¿Quién tumbó la jornada laboral de 35 horas? 162 sí, 178 no, 6 abstenciones. 14 de octubre de 2025.»

### Educación especial · `12-educacion-especial.png` · 28 oct (pareja con 35 horas)

Principal:
```
Septiembre de 2025. ¿Deben las familias de alumnos con necesidades educativas especiales poder elegir un centro de educación especial?

Se votó una proposición del PP: 170 sí, 177 no.

¿Tú qué habrías votado?
```
Respuesta:
```
Sí: PP, Vox y UPN.
No: PSOE, Sumar, Podemos, ERC, Junts, EH Bildu, PNV, BNG y CC.

https://votaconlachola.org/citizen/vota/t/educacion-educacion-especial/
```
Alt: «¿Deben las familias poder elegir un centro de educación especial? 170 sí, 177 no. Se decidió por 7 votos. 9 de septiembre de 2025.»

### Comodines (sin imagen, para cualquier día)

```
No les preguntes qué harán. Mira qué votaron.

4 años de votaciones del Congreso convertidas en un test de 2 minutos:
https://votaconlachola.org/citizen/vota/
```
```
Su programa es una promesa. Su voto es un hecho.

¿Con quién coincides de verdad? Respóndelo con votaciones reales, no con eslóganes.
```
```
Tú también habrías votado. Compara.
```

### Reto a los partidos (20 oct y 9 nov)

20 oct:
```
Hemos invitado a los 12 partidos con representación en el Congreso a que un candidato haga el test sin mirar y publique su podio.

Plazo: 6 de noviembre. El 9 publicamos quién ha respondido.

¿Coincidirán con su propio grupo?
```
9 nov (rellenar con lo que haya pasado):
```
Reto a los 12 partidos: [N] han respondido.

[lista de partidos que han respondido, con enlace a su podio]

Los demás aún están a tiempo.
```

---

## 3. «Dijeron / Votaron» (13–23 nov) · ⚠️ pendiente de revisión humana

Se publican **juntas el mismo día**. Cada una lleva su defensa en una línea.

### Amnistía (PSOE) · `14-dv-amnistia-psoe.png`

Principal:
```
DIJERON: antes del 23-J de 2023, Sánchez y el PSOE sostenían que la amnistía no cabía en la Constitución.

VOTARON: el 14 de marzo de 2024, el PSOE votó sí. Aprobada por 178 a 172.

SU DEFENSA: en enero de 2024, Sánchez habló de un «cambio de opinión».
```
Respuesta:
```
Votación nominal oficial del Congreso y hemeroteca, en los enlaces:
https://votaconlachola.org/citizen/vota/t/territorio-amnistia/
https://maldita.es/malditahemeroteca/20250627/pedro-sanchez-amnistia-constitucion/
```

### Regularización (PP) · `15-dv-regularizacion-pp.png`

Principal:
```
VOTARON: el 9 de abril de 2024, los 136 diputados del PP presentes votaron sí a tramitar la regularización de inmigrantes. 310 a 33.

DIJERON: en 2026, Feijóo critica la regularización y estudia recurrir el decreto.

SU DEFENSA: su sí era a debatirla con condiciones.
```
Respuesta:
```
Votación nominal oficial y hemeroteca:
https://votaconlachola.org/citizen/vota/t/inmigracion-regularizacion/
https://www.eldiario.es/politica/feijoo-critica-ahora-regularizacion-personas-migrantes-defender-podian-tranquilos_1_12938361.html
```

### Plantilla para promesas de mitin (≤ 24 h)

Pasa primero el [filtro de señal](../campana-guerrilla-vota.md#filtro-de-señal-un-caso-solo-se-publica-si-pasa-las-cuatro-pruebas): las cuatro pruebas.
```
DIJERON ([fecha], [acto]): «[cita literal breve]»

VOTARON ([fecha]): [voto del grupo]. [resultado].

SU DEFENSA: [una línea, con sus propias palabras]
```

### Debate en televisión (hilo en directo)
```
[Tema] en el debate. Lo que votaron sus grupos:

[Partido A]: [sí/no/abst.] · [Partido B]: … 

Votación nominal del [fecha]: [enlace]
```

---

## 4. Recta final (24–27 nov) · `13-whatsapp-familia.png`

```
Antes de votar, 10 preguntas. Después, comparad podios.

Para mandar al grupo de la familia este fin de semana:
https://votaconlachola.org/citizen/vota/
```
Alt: «Antes de votar, 10 preguntas. Después, comparad podios. Para el grupo de la familia.»

Ojo: del 24 al 28 nov no se publica nada que parezca un sondeo, como «el X % coincide con…».

## 5. Después (desde el 30 nov)
```
Hemos guardado lo que prometieron en campaña, con fecha y fuente.

En la nueva legislatura lo compararemos con lo que voten. «Lo prometieron el 18 de noviembre. Así lo votaron.»
```
