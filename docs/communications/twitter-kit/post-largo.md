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
