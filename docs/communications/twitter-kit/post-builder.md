# Post de builder (para acompañar el vídeo)

Escrito en primera persona, para la comunidad tech o builder de X. Hay dos versiones: un post largo (X Premium) y un hilo. Las cifras salen del snapshot `voting_aid_generales_v1.json`, del registro de bloqueos de acceso y de la historia del repo (primer commit: 12-02-2026; commits en 27 días distintos; el test se montó el 11 y el 12 de octubre). Procedencia de los votos del test: 34 de 41 están en la base del 18-03-2026 (`politicos-es-005`), descargados con el ETL de votaciones del Congreso de los días 12 y 13 de febrero; los 7 más recientes (de abril a septiembre de 2026) se descargaron el 11 de octubre con ese mismo ETL. Bloqueos del Congreso: vistos el 25 de febrero y el 8 de marzo y resueltos el 11 de octubre; no hay pruebas de un bloqueo continuo durante meses.

## Versión post largo

Copia lista para pegar: [post-largo.md](post-largo.md). Hilo conductor: la pregunta personal → por qué las votaciones → el trabajo y los bloqueos → las elecciones lo vuelven concreto → el test → el espejo («si eres como yo…») → por qué fiarse → qué pido.

```
Llevo 8 meses dedicando ratos libres a explorar una idea: ¿se puede saber qué hacen de verdad los políticos usando solo datos públicos?

La pregunta viene de algo que me pasa en cada elección. Decido mi voto con lo que recuerdo de la campaña: promesas, debates, titulares. Y las promesas no obligan a nada. La Constitución prohíbe el mandato imperativo (art. 67.2): ningún diputado está obligado a cumplir su programa.

Pero hay algo que sí queda. Cada votación nominal del Congreso es pública: qué se votó, cuándo y qué votó cada diputado. El problema es que casi nadie la consulta, porque está repartida en miles de archivos en la web del Congreso.

Así que empecé por ahí. En febrero escribí un programa que descarga esas votaciones y las guarda en una base de datos junto con el archivo original, para poder comprobar cualquier cifra. Y fui tirando del hilo hacia otras fuentes: cargos públicos, Senado, parlamentos autonómicos, contratos.

Por el camino descubrí que los datos públicos no siempre son accesibles. En febrero y marzo, el Congreso me devolvía errores 403 al descargar sus datos abiertos (ahora funcionan). El Senado y los parlamentos de Galicia y Navarra también me bloquearon. Lo registro todo, con fechas y pruebas, en un documento público.

El 6 de octubre se disolvieron las Cortes y hay elecciones el 29 de noviembre. Ahí la idea se volvió concreta: en lugar de preguntarte qué opinas de cada partido, ¿por qué no preguntarte qué habrías votado tú, y compararlo con lo que votaron ellos?

Eso es el test. Lo he montado en dos días, reutilizando las votaciones que ya tenía. Respondes a 33 afirmaciones, cada una basada en votaciones reales de la legislatura que acaba de terminar, y al final ves qué partidos votaron como tú. Cada voto enlaza a su fuente oficial en congreso.es. Si te quedas con ganas, hay un modo sin fin con 334 votaciones.

Si eres como yo, crees saber más o menos dónde está cada partido. Los datos tienen sorpresas para todos:

· Trasvase Tajo-Segura (mayo de 2025): la proposición de ley para mantenerlo se rechazó por un voto, 170 a 171. Podemos se abstuvo; con sus 4 votos a favor, habría salido adelante.
· Cobrar parte de la pensión y seguir trabajando (enero de 2025): Vox y Podemos votaron lo mismo, en contra.
· Impuesto a los beneficios extraordinarios de la gran banca (abril de 2024): PSOE y PP votaron igual, en contra de la proposición.
· Regularización de inmigrantes sin papeles (abril de 2024): el PP votó a favor de tramitarla. Solo Vox votó en contra.

He intentado que sea justo y comprobable. La posición de un partido es lo que votó la mayoría de sus diputados. Las afirmaciones están redactadas en los dos sentidos, para que contestar siempre «de acuerdo» no te empuje hacia ningún bloque. Si falta un dato, aparece como «sin datos». Y tus respuestas se quedan en tu navegador: no hay cuentas ni base de datos de usuarios.

He trabajado con agentes de IA, que también han revisado cada afirmación contra el texto oficial, sin ver cómo votó cada partido. Pero falta una revisión humana, y la web lo avisa. La metodología completa, con los prompts, está publicada.

No te dice a quién votar. Te enseña lo que votaron, para que lo compares con lo que te prometan estas semanas.

Es un proyecto personal, así que tendrá errores. Si encuentras uno, dímelo y lo corrijo en público. Si sabes de ciencia política o periodismo de datos y quieres ayudar con la revisión, o eres desarrollador y quieres colaborar, escríbeme. Y si te parece útil, compártelo antes del 29 de noviembre.

Test: https://votaconlachola.org/citizen/vota/
Metodología: https://votaconlachola.org/citizen/vota/metodologia/
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

Test: https://votaconlachola.org/citizen/vota/
Metodología: https://votaconlachola.org/citizen/vota/metodologia/
Código: https://github.com/gsusI/vota-con-la-chola
```
