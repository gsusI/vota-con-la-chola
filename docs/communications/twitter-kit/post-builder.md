# Post de builder (para acompañar el vídeo)

Escrito en primera persona, para la comunidad tech o builder de X. Hay dos versiones: un post largo (X Premium) y un hilo. Las cifras salen del snapshot `voting_aid_generales_v1.json`, del registro de bloqueos de acceso y de la historia del repo (primer commit: 12-02-2026; commits en 27 días distintos; el test se montó el 11 y el 12 de octubre). Procedencia de los votos del test: 34 de 41 están en la base del 18-03-2026 (`politicos-es-005`), descargados con el ETL de votaciones del Congreso de los días 12 y 13 de febrero; los 7 más recientes (de abril a septiembre de 2026) se descargaron el 11 de octubre con ese mismo ETL. Bloqueos del Congreso: vistos el 25 de febrero y el 8 de marzo y resueltos el 11 de octubre; no hay pruebas de un bloqueo continuo durante meses.

## Versión post largo

```
Llevo 8 meses, en ratos libres, explorando una idea: ¿se puede reconstruir qué hacen de verdad los políticos solo con datos públicos? Votaciones, cargos, parlamentos, contratos públicos…

De esa exploración sale esto. El test lo he montado en dos días, reutilizando las votaciones del Congreso que ya tenía descargadas. Os lo cuento 👇

EL PROBLEMA

En España prometer no obliga. La Constitución prohíbe el mandato imperativo (art. 67.2): un programa electoral no es un contrato y nadie puede exigir que se cumpla.

Una legislatura dura cuatro años y la campaña, dos semanas. Lo que se promete se recuerda. Lo que se vota, no.

Pero hay algo que sí queda: cada votación nominal del Congreso es pública, con nombre, fecha y sentido del voto. Es el único dato político que no depende de quién te lo cuente.

LA IDEA

Los test de afinidad de siempre te preguntan por lo que los partidos dicen que piensan. Yo quería lo contrario: que respondas a lo que de verdad se votó y ver quién votó como tú.

Así nace «¿Con quién coincides?»: 33 afirmaciones sacadas de 41 votaciones reales de la legislatura que acaba de cerrarse, 12 partidos y cada voto con su enlace oficial a congreso.es. Si te quedas con ganas, hay un modo infinito con 334 votaciones.

CÓMO ESTÁ HECHO (para builders)

· El test reutiliza lo que ya tenía. El ETL de votaciones del Congreso fue de lo primero que hice, en febrero: 34 de las 41 votaciones del test salen de aquella descarga, y las 7 más recientes las he bajado ahora con el mismo código. El resto de estos meses se ha ido en explorar otras fuentes (Senado, parlamentos autonómicos, contratación pública) que el test no usa.
· Un ETL descarga los JSON oficiales de votaciones del Congreso y los mete en un único SQLite reproducible. Guardo el payload crudo de cada fuente: cualquier cifra se puede reconducir a su origen.
· La posición de un partido es lo que votó la mayoría de sus diputados. Sin interpretación editorial.
· Las afirmaciones están redactadas en los dos sentidos, para que contestar siempre «de acuerdo» no te empuje hacia un bloque. Lo mido: en 15 afirmaciones solo el PSOE queda del lado del «de acuerdo», y en 12 solo el PP.
· La web es estática. Tus respuestas no salen de tu móvil: ni cuentas, ni base de datos de usuarios. Lo único que compartes, si quieres, es tu podio.
· El código es abierto (licencia MIT) y los datos del test se pueden descargar tal cual desde la web.
· Lo he construido con agentes de IA como equipo. La IA también ha revisado las afirmaciones: dos revisores independientes por afirmación, contra el texto oficial y sin ver cómo votó cada partido. Pero eso no basta, y la web lo dice en un banner: falta la revisión humana.

LO QUE ME HE ENCONTRADO

Que los datos públicos no siempre son públicos. En febrero y marzo, los datos abiertos de votaciones del Congreso me devolvían errores 403 (hoy funcionan). El Senado y los parlamentos de Galicia y Navarra también me bloquearon el acceso automatizado. Lo apunto todo en un registro público con fechas y evidencia, porque bloquear datos que tienen que ser públicos también es noticia.

Y que la realidad es más interesante que los bloques:

· El trasvase Tajo-Segura se decidió por un voto (170 a 171). Podemos se abstuvo; con sus 4 votos a favor, habría salido.
· Vox y Podemos votaron lo mismo sobre cobrar parte de la pensión y seguir trabajando.
· PSOE y PP votaron igual: no a la proposición para subir el impuesto a la gran banca.
· El PP votó sí a tramitar la regularización de inmigrantes. Solo Vox votó no.

Todo el mundo tiene algún «no me lo esperaba».

LO QUE NO ES

No te dice a quién votar. No es una encuesta. Es para explorar, no un veredicto. Si no hay datos de un partido en un tema, sale como «sin datos»: no se inventa nada.

LO QUE NECESITO

· Que lo rompáis. Si veis un error, decídmelo y lo corrijo en público.
· Gente de ciencia política o periodismo de datos que quiera hacer la revisión humana.
· Builders que quieran meterle mano: ETL, datos, front.
· Que lo compartáis antes del 29 de noviembre.

Pruébalo (2 minutos): https://votaconlachola.org/citizen/vota/
Código: https://github.com/gsusI/vota-con-la-chola
```

## Versión hilo (sin Premium)

1/ (con el vídeo)
```
Llevo 8 meses, en ratos libres, explorando si se puede reconstruir qué hacen de verdad los políticos solo con datos públicos.

De ahí sale esto: respondes a lo que se votó en el Congreso y ves quién votó como tú.

El test, en dos días, con datos que ya tenía 🧵
```
2/
```
El problema: en España prometer no obliga. La Constitución prohíbe el mandato imperativo (art. 67.2). Un programa no es un contrato.

La legislatura dura 4 años; la campaña, 2 semanas. Lo prometido se recuerda. Lo votado, no.
```
3/
```
Pero una cosa sí queda: cada votación nominal del Congreso es pública, con nombre, fecha y sentido del voto.

Es el único dato político que no depende de quién te lo cuente. Así que construí el test al revés: no lo que dicen que piensan, sino lo que votaron.
```
4/
```
Qué es:
· 33 afirmaciones sacadas de 41 votaciones reales de la legislatura que acaba de cerrarse
· 12 partidos
· Cada voto con su enlace oficial a congreso.es
· Un modo infinito con 334 votaciones
```
5/
```
Para builders:
· ETL con los JSON oficiales del Congreso → un único SQLite reproducible
· Guardo el payload crudo: cualquier cifra se reconduce a su origen
· Posición de partido = lo que votó la mayoría de sus diputados
· Web estática, código abierto (MIT)
```
6/
```
Sesgo: las afirmaciones están redactadas en los dos sentidos, para que decir siempre «sí» no te empuje hacia un bloque. En 15 solo el PSOE queda del lado del «sí»; en 12, solo el PP.

Privacidad: tus respuestas no salen de tu móvil. Sin cuentas ni base de datos de usuarios.
```
7/
```
Lo he construido con agentes de IA como equipo. La IA también ha revisado las afirmaciones: dos revisores independientes, contra el texto oficial, sin ver los votos.

No basta, y la web lo dice en un banner: falta la revisión humana. Ahí entráis vosotros.
```
8/
```
Lo que me he encontrado: los datos públicos no siempre son públicos.

En febrero y marzo el Congreso me devolvía errores 403 (hoy funciona). El Senado, Galicia y Navarra también me bloquearon. Lo apunto en un registro público con fecha y evidencia.
```
9/
```
Y la realidad es más interesante que los bloques:

· El trasvase Tajo-Segura se decidió por 1 voto; Podemos se abstuvo
· Vox y Podemos votaron igual sobre la jubilación activa
· PSOE y PP, igual sobre el impuesto a la banca
· PP sí a tramitar la regularización; solo Vox, no
```
10/
```
No te dice a quién votar ni es una encuesta. Es para explorar.

Necesito que lo rompáis, revisores de ciencia política o periodismo de datos y builders que quieran meterle mano.

https://votaconlachola.org/citizen/vota/
https://github.com/gsusI/vota-con-la-chola
```
