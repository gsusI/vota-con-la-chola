He hecho un test para comparar tus opiniones con lo que votaron los partidos en el Congreso.

Respondes a 33 afirmaciones. Cada una corresponde a una votación real de la última legislatura. Al final ves qué partidos votaron como tú. Cada voto enlaza a su fuente oficial en congreso.es.

Pruébalo: https://votaconlachola.org/citizen/vota/

Por qué votaciones y no programas

Un programa electoral no obliga. La Constitución prohíbe el mandato imperativo (art. 67.2), así que nadie puede exigir que se cumpla. Las votaciones nominales, en cambio, quedan registradas con su fecha y el voto de cada diputado. Son el dato más fiable de lo que hace cada partido.

Qué incluye

· 33 afirmaciones basadas en 41 votaciones nominales del Congreso, de febrero de 2024 a septiembre de 2026.
· 12 partidos.
· Un modo sin fin con 334 votaciones, para quien quiera seguir.

Cómo se calcula

· La posición de un partido en una votación es lo que votó la mayoría de sus diputados.
· Las afirmaciones están redactadas en los dos sentidos, para que contestar siempre «de acuerdo» no favorezca a ningún bloque. En 15 afirmaciones solo el PSOE está del lado del «de acuerdo»; en 12, solo el PP.
· Si no hay datos de un partido en una votación, aparece como «sin datos». No se rellena.

Privacidad

La web es estática. Tus respuestas se quedan en tu navegador: no hay cuentas ni base de datos de usuarios. Solo se comparte tu podio, y solo si tú quieres.

Cómo lo he hecho

Es un proyecto personal en el que llevo 8 meses, en ratos libres. La pregunta de fondo es si se puede reconstruir lo que hacen los políticos solo con datos públicos: votaciones, cargos, parlamentos, contratos.

El test lo he montado en dos días. Reutiliza el programa que escribí en febrero para descargar las votaciones del Congreso: 34 de las 41 votaciones salen de aquella descarga, y las 7 más recientes las he descargado ahora con el mismo programa. Todo se guarda en una base SQLite junto con la respuesta original de cada fuente, para poder comprobar cualquier cifra.

He trabajado con agentes de IA. La IA también ha revisado las afirmaciones: dos revisiones independientes por afirmación, contrastadas con el texto oficial y sin ver cómo votó cada partido. Falta una revisión humana, y la web lo avisa. La metodología completa, con los prompts, está publicada.

Accesos bloqueados

En febrero y marzo, el Congreso me devolvía errores 403 al descargar sus datos abiertos de votaciones. Ahora funcionan. El Senado y los parlamentos de Galicia y Navarra también me bloquearon el acceso automatizado. Lo registro todo, con fechas y pruebas, en un documento público del repositorio.

Algunos resultados

· Trasvase Tajo-Segura (mayo de 2025): la proposición de ley para mantenerlo se rechazó por 170 votos a favor y 171 en contra. Podemos se abstuvo; con sus 4 votos a favor, se habría aprobado.
· Cobrar parte de la pensión y seguir trabajando (enero de 2025): Vox y Podemos votaron lo mismo, en contra.
· Impuesto a los beneficios extraordinarios de la gran banca (abril de 2024): PSOE y PP votaron igual, en contra de la proposición.
· Regularización de inmigrantes sin papeles (abril de 2024): el PP votó a favor de tramitarla. Solo Vox votó en contra.

Lo que no es

No recomienda a quién votar y no es una encuesta. Sirve para comparar tus respuestas con votaciones concretas.

Lo que busco

· Que me digáis los errores que encontréis. Los corregiré en público.
· Personas de ciencia política o periodismo de datos que quieran hacer la revisión humana.
· Desarrolladores que quieran colaborar.
· Que lo compartáis antes de las elecciones del 29 de noviembre.

Test: https://votaconlachola.org/citizen/vota/
Metodología: https://votaconlachola.org/citizen/vota/metodologia/
Código: https://github.com/gsusI/vota-con-la-chola
