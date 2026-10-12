# Post de builder (para acompañar el vídeo)

Escrito en primera persona, para la comunidad tech o builder de X. Hay dos versiones: un post largo (X Premium) y un hilo. Las cifras salen del snapshot `voting_aid_generales_v1.json`, del registro de bloqueos de acceso y de la historia del repo (primer commit: 12-02-2026).

## Versión post largo

```
Llevo 8 meses construyendo una herramienta para que nadie te tenga que contar qué votaron los partidos. Os cuento qué he hecho, por qué, y lo que me he encontrado por el camino 👇

EL PROBLEMA

En España prometer no obliga. La Constitución prohíbe el mandato imperativo (art. 67.2): un programa electoral no es un contrato y nadie puede exigir que se cumpla.

Una legislatura dura cuatro años y la campaña, dos semanas. Lo que se promete se recuerda. Lo que se vota, no.

Pero hay algo que sí queda: cada votación nominal del Congreso es pública, con nombre, fecha y sentido del voto. Es el único dato político que no depende de quién te lo cuente.

LA IDEA

Los test de afinidad de siempre te preguntan por lo que los partidos dicen que piensan. Yo quería lo contrario: que respondas a lo que de verdad se votó y ver quién votó como tú.

Así nace «¿Con quién coincides?»: 33 afirmaciones sacadas de 41 votaciones reales de la legislatura que acaba de cerrarse, 12 partidos y cada voto con su enlace oficial a congreso.es. Si te quedas con ganas, hay un modo infinito con 334 votaciones.

CÓMO ESTÁ HECHO (para builders)

· Un ETL descarga los JSON oficiales de votaciones del Congreso y los mete en un único SQLite reproducible. Guardo el payload crudo de cada fuente: cualquier cifra se puede reconducir a su origen.
· La posición de un partido es lo que votó la mayoría de sus diputados. Sin interpretación editorial.
· Las afirmaciones están redactadas en los dos sentidos, para que contestar siempre «de acuerdo» no te empuje hacia un bloque. Lo mido: en 15 el «de acuerdo» coincide con el PSOE y en 12 con el PP.
· La web es estática. Tus respuestas no salen de tu móvil: ni cuentas, ni base de datos de usuarios. Lo único que compartes, si quieres, es tu podio.
· Datos abiertos en Hugging Face y código con licencia MIT.
· Lo he construido con agentes de IA como equipo. La IA también ha revisado las afirmaciones: dos revisores independientes por afirmación, contra el texto oficial y sin ver cómo votó cada partido. Pero eso no basta, y la web lo dice en un banner: falta la revisión humana.

LO QUE ME HE ENCONTRADO

Que los datos públicos no siempre son públicos. El Congreso me devolvió errores 403 durante meses (ahora funciona). El Senado y los parlamentos de Galicia y Navarra siguen bloqueando el acceso automatizado. Lo apunto todo en un registro público con fechas y evidencia, porque bloquear datos que tienen que ser públicos también es noticia.

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
Llevo 8 meses construyendo una herramienta para que nadie te tenga que contar qué votaron los partidos.

Respondes a lo que de verdad se votó en el Congreso y ves quién votó como tú.

Os cuento qué he hecho, por qué y lo que me he encontrado 🧵
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
· Web estática, datos abiertos en Hugging Face, código MIT
```
6/
```
Sesgo: las afirmaciones están redactadas en los dos sentidos, para que contestar siempre «de acuerdo» no te empuje hacia un bloque. En 15 el «sí» coincide con el PSOE y en 12 con el PP.

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

El Congreso me devolvió errores 403 durante meses (ya funciona). El Senado, Galicia y Navarra siguen bloqueando el acceso automatizado. Lo apunto en un registro público con fecha y evidencia.
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
